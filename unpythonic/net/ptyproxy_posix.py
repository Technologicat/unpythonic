# -*- coding: utf-8; -*-
"""POSIX backend for `PTYSocketProxy`. See `ptyproxy.py` for the public interface."""

import contextlib
import os
import tty
import termios
import select
import threading

from .ptyproxy import PTYSocketProxy

__all__ = ["PosixPTYSocketProxy"]


# What this does for us in a remote REPL session in `unpythonic.net.server` is:
#   >>> import os
#   >>> os.isatty(sys.stdin.fileno())
#   True
# whereas without the PTY, the same code returns False. On Windows, where no
# real pty is available, that property is lost — see `ptyproxy_windows`.
class PosixPTYSocketProxy(PTYSocketProxy):
    """POSIX implementation of `PTYSocketProxy` using `os.openpty`.

    See the `PTYSocketProxy` base class for the public interface contract.
    """

    def __init__(self, sock, on_socket_disconnect=None, on_slave_disconnect=None):
        # master is the "pty side", slave is the "tty side".
        master, slave = os.openpty()
        # Transactional: if anything between here and the end of __init__
        # raises, we own two open fds and the caller will never get a
        # reference to close them. Release them before re-raising.
        try:
            tty.setraw(master, termios.TCSANOW)  # http://man7.org/linux/man-pages/man3/termios.3.html
            # `os.ttyname` is cached up front so `self.name` still works
            # after `stop()` has closed the slave fd — callers use it in
            # log messages during teardown. Also part of the transaction:
            # if the slave fd is somehow already invalid, fail early.
            self._name = os.ttyname(slave)
        except BaseException:
            try:
                os.close(master)
            except OSError:
                pass
            try:
                os.close(slave)
            except OSError:
                pass
            raise
        self.sock = sock
        self.master, self.slave = master, slave
        self.on_socket_disconnect = on_socket_disconnect
        self.on_slave_disconnect = on_slave_disconnect
        self._terminated = True
        self._thread = None

    @property
    def name(self):
        return self._name

    def write_to_master(self, data):
        os.write(self.master, data)

    @contextlib.contextmanager
    def open_slave_streams(self, encoding="utf-8"):
        # `closefd=False` on both: the raw slave fd is owned by this proxy
        # and will be released by `stop()`, not by the stream wrappers.
        with contextlib.ExitStack() as stack:
            wfile = stack.enter_context(open(self.slave, "wt", encoding=encoding, closefd=False))
            rfile = stack.enter_context(open(self.slave, "rt", encoding=encoding, closefd=False))
            yield rfile, wfile

    def start(self):
        if self._thread:
            raise RuntimeError("Already running.")

        # Note we use raw fds (file descriptors) and the low-level os.read, os.write functions,
        # which bypass all niceties file objects have.
        # https://docs.python.org/3/library/os.html
        def forward_traffic():
            mypoll = select.poll()
            mypoll.register(self.sock, select.POLLIN)
            mypoll.register(self.master, select.POLLIN)
            while not self._terminated:
                try:
                    fdlist = mypoll.poll(1000)
                    for fd, event in fdlist:
                        if fd == self.master:
                            request = os.read(fd, 4096)
                            if len(request) == 0:  # disconnect by PTY slave
                                self.on_slave_disconnect(self)
                                return
                            self.sock.send(request)
                        else:
                            request = self.sock.recv(4096)
                            if len(request) == 0:  # disconnect by client behind socket
                                self.on_socket_disconnect(self)
                                return
                            os.write(self.master, request)
                except ConnectionResetError:
                    self.on_socket_disconnect(self)
                    return

        self._terminated = False
        self._thread = threading.Thread(target=forward_traffic, name=f"PTY on {os.ttyname(self.slave)}", daemon=True)
        self._thread.start()

    def stop(self):
        # Decoupled and idempotent: the fd teardown runs regardless of
        # whether the forwarding thread was ever started, and each close
        # is guarded so a failure on one fd doesn't leak the other.
        if self._thread is not None:
            self._terminated = True
            self._thread.join()
            self._thread = None
        if self.master is not None:
            try:
                os.close(self.master)
            except OSError:
                pass
            self.master = None
        if self.slave is not None:
            try:
                os.close(self.slave)
            except OSError:
                pass
            self.slave = None
