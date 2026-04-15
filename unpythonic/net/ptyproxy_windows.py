# -*- coding: utf-8; -*-
"""Windows backend for `PTYSocketProxy`. See `ptyproxy.py` for the public interface.

No real pseudo-terminal is involved: we use `socket.socketpair()` as a pair
of connected loopback sockets standing in for the pty master/slave
endpoints. The forwarding loop is identical in shape to the POSIX backend
(byte shovelling between `sock` and `master`), just with `select.select`
instead of `select.poll` (Windows has no `poll` for sockets) and with
socket methods instead of raw fd `os.read`/`os.write`.

**What we lose compared to a real PTY**: `os.isatty()` on code running
against the slave side returns `False`. The framework itself (`code.
InteractiveConsole`, `unpythonic.net.server`) does not depend on
`isatty()`; user code *inside* a REPL session that checks
`sys.stdin.isatty()` will see the Windows result. This is the one
documented wart of the Windows port — see the 2.0.x CHANGELOG entry.

**Why not ConPTY / pywinpty**: ConPTY is architected around launching a
*child process* attached to a pseudoconsole. There is no supported
"attach my own process's existing thread to this pseudoconsole"
primitive, and spawning a subprocess per REPL session would defeat the
whole point of `unpythonic.net.server`, which is to let a remote client
inspect and hot-patch state in the *host* Python process — that requires
the REPL to run in the same process as the server.

The right question isn't "how do we get ConPTY", it's "what do we
actually need". The answer: two connected bidirectional byte streams.
`socket.socketpair()` provides exactly that, stdlib-only, with lines
of code that mirror the POSIX backend almost 1:1.

**Why the Windows backend also works on POSIX**: `socket.socketpair()` is
available on every platform Python supports. The Windows-specific
constraint is that it returns AF_INET loopback sockets there (POSIX
defaults to AF_UNIX, which is also fine). This lets us unit-test
`WindowsPTYSocketProxy` on a Linux/macOS dev machine by explicit
instantiation, without needing a Windows box.
"""

import contextlib
import select
import socket
import threading

from .ptyproxy import PTYSocketProxy

__all__ = ["WindowsPTYSocketProxy"]


class WindowsPTYSocketProxy(PTYSocketProxy):
    """Windows implementation of `PTYSocketProxy` using `socket.socketpair()`.

    See the `PTYSocketProxy` base class for the public interface contract.
    """

    def __init__(self, sock, on_socket_disconnect=None, on_slave_disconnect=None):
        # No `openpty`; a connected socketpair stands in for the pty
        # master/slave endpoints. Both ends are full-duplex sockets, so
        # "master" and "slave" are labels for roles, not transport
        # distinctions — unlike on POSIX where master/slave have
        # asymmetric kernel-level semantics.
        master, slave = socket.socketpair()
        # Transactional: if anything between here and the end of __init__
        # raises, we own two open sockets and the caller will never get
        # a reference to close them. Release them before re-raising.
        try:
            # Synthetic name for log messages — no `ttyname` equivalent
            # here. Low-order bits of `id(self)` give a short,
            # human-readable tag that distinguishes concurrent proxies.
            self._name = f"(socketpair#{id(self) & 0xffff:04x})"
        except BaseException:
            try:
                master.close()
            except OSError:
                pass
            try:
                slave.close()
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
        self.master.sendall(data)

    @contextlib.contextmanager
    def open_slave_streams(self, encoding="utf-8"):
        # `socket.makefile` uses a reference-counting scheme: each call
        # increments `_io_refs` on the underlying socket, and closing the
        # wrapper decrements it. The raw socket is only closed once
        # `_io_refs` hits zero *and* `socket.close()` has been called
        # explicitly. So closing the wfile/rfile wrappers here does NOT
        # close the underlying slave socket — that's left to `stop()`,
        # matching the POSIX backend's `closefd=False` semantics.
        #
        # `buffering=1` on the writer = line buffering. This matters
        # because socket writers default to block-buffered (~8 KB), which
        # would stall REPL prompts until enough bytes accumulated. With
        # line buffering, every `\n` flushes — and `builtins.input()`
        # also explicitly calls `sys.stdout.flush()` before reading, so
        # bare prompts (no trailing newline) also reach the client
        # promptly.
        #
        # `newline=""` on the writer disables `\n` → `os.linesep`
        # translation — a CRITICAL Windows fix, because `os.linesep` is
        # `\r\n` there, and the default `newline=None` would translate
        # every `\n` the application writes into `\r\n` on the wire.
        # That would pollute the client's display with stray `\r`s and
        # potentially break the prompt-detection / session-ID-parsing
        # regex on `net.client`. On POSIX the setting is a no-op (since
        # `os.linesep == "\n"`), so it's also safe to run on Linux —
        # and crucially it means the Linux test suite validates exactly
        # the same code path that Windows will execute.
        #
        # The reader uses default `newline=None` (universal newlines),
        # which returns `\n`-terminated lines regardless of the actual
        # on-wire ending — exactly what `code.InteractiveConsole`
        # expects from `sys.stdin.readline()`.
        with contextlib.ExitStack() as stack:
            wfile = stack.enter_context(self.slave.makefile("w", buffering=1, encoding=encoding, newline=""))
            rfile = stack.enter_context(self.slave.makefile("r", encoding=encoding))
            yield rfile, wfile

    def start(self):
        if self._thread:
            raise RuntimeError("Already running.")

        # Windows has no `select.poll` for sockets (Python's `select.poll`
        # exists on Windows but only for a limited file-descriptor set —
        # sockets are not supported). `select.select` handles sockets on
        # all platforms, so we use that here. The 1-second timeout is the
        # same as the POSIX `poll(1000)` — it bounds the latency for
        # `stop()` to notice `self._terminated` flipping.
        def forward_traffic():
            while not self._terminated:
                try:
                    rs, _ws, _es = select.select([self.sock, self.master], [], [], 1.0)
                    for s in rs:
                        if s is self.master:
                            request = self.master.recv(4096)
                            if len(request) == 0:  # disconnect by slave-side code
                                self.on_slave_disconnect(self)
                                return
                            self.sock.send(request)
                        else:
                            request = self.sock.recv(4096)
                            if len(request) == 0:  # disconnect by client behind socket
                                self.on_socket_disconnect(self)
                                return
                            self.master.send(request)
                except ConnectionResetError:
                    self.on_socket_disconnect(self)
                    return

        self._terminated = False
        self._thread = threading.Thread(target=forward_traffic, name=f"PTY on {self._name}", daemon=True)
        self._thread.start()

    def stop(self):
        # Decoupled and idempotent: the socket teardown runs regardless
        # of whether the forwarding thread was ever started, and each
        # close is guarded so a failure on one socket doesn't leak the
        # other.
        if self._thread is not None:
            self._terminated = True
            self._thread.join()
            self._thread = None
        if self.master is not None:
            try:
                self.master.close()
            except OSError:
                pass
            self.master = None
        if self.slave is not None:
            try:
                self.slave.close()
            except OSError:
                pass
            self.slave = None
