"""PTY/socket proxy. Useful for serving terminal applications for remote use."""

import os
import tty
import termios
import select
import threading

# What this does for us in a remote REPL session in unpythonic.net.server is that:
#   >>> import os
#   >>> os.isatty(sys.stdin.fileno())
#   True
# whereas without the PTY, the same code returns False.
#
class PTYSocketProxy:
    """Plug a PTY between a network socket and Python code that expects to run in a terminal.

    Generally, having a PTY enables the "interactive" features of some *nix terminal apps.

    This is different from many online examples in that **we do not** use `pty.spawn`,
    so the code that runs on the PTY slave side doesn't need to be a separate process.

    Based on solution by SO user gowenfawr:
        https://stackoverflow.com/questions/48781155/how-to-connect-inet-socket-to-pty-device-in-python

    On PTYs in Python and in general, see:
        https://sqizit.bartletts.id.au/2011/02/14/pseudo-terminals-in-python/
        http://rachid.koucha.free.fr/tech_corner/pty_pdip.html
        https://matthewarcus.wordpress.com/2012/11/04/embedded-python-interpreter/
        https://terminallabs.com/blog/a-better-cli-passthrough-in-python/
        http://man7.org/linux/man-pages/man7/pty.7.html
    """
    def __init__(self, sock, on_socket_disconnect=None, on_slave_disconnect=None):
        """Open the PTY. The slave FD becomes available as `self.slave`.

        `on_socket_disconnect`, if set, is a one-argument callable that is called
        when an EOF is detected on the socket. It receives the `PTYSocketProxy`
        instance and can e.g. `os.write(proxy.master, some_disconnect_command)`
        to tell the software connected on the slave side to exit.

        What the command is, is up to the protocol your specific software
        speaks, so we just provide a general mechanism to send a command to it.
        In other words, you get a disconnect event for free, but you need to
        know how to tell your specific software to end the session when that
        event fires.

        `on_slave_disconnect`, if set, is a similar callable that is called when
        an EOF is detected on the PTY slave.

        **NOTE**: `slave` is a raw file descriptor (just a small integer),
        not a Python stream. If you need a stream, `open()` the file descriptor
        (twice if you need to read *and* write; make sure to set `closefd` to
        `False`, as `PTYSocketProxy` will manage the closing).
        """
        # master is the "pty side", slave is the "tty side".
        master, slave = os.openpty()
        tty.setraw(master, termios.TCSANOW)  # http://man7.org/linux/man-pages/man3/termios.3.html
        self.sock = sock
        self.master, self.slave = master, slave
        self.on_socket_disconnect = on_socket_disconnect
        self.on_slave_disconnect = on_slave_disconnect
        self._terminated = True
        self._thread = None

    def start(self):
        """Start forwarding traffic between the PTY master and the socket."""
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

        self._terminated = False
        self._thread = threading.Thread(target=forward_traffic, name="PTY on {}".format(os.ttyname(self.slave)), daemon=True)
        self._thread.start()

    def stop(self):
        """Shut down. This also closes the PTY."""
        if self._thread:
            self._terminated = True
            self._thread.join()
            self._thread = None
            os.close(self.master)
            self.master = None
            os.close(self.slave)
            self.slave = None
