# -*- coding: utf-8; -*-
"""PTY/socket proxy. Useful for serving terminal applications for remote use.

This module defines `PTYSocketProxy`, an abstract base class that plugs a
bidirectional byte channel between a network socket and in-process code that
wants to look like it's running behind a terminal. The concrete implementation
is chosen at construction time based on platform:

  - **POSIX**: `ptyproxy_posix.PosixPTYSocketProxy` uses a real pseudo-terminal
    (`os.openpty` + raw mode on master). `os.isatty()` returns `True` inside
    code that reads the slave.
  - **Windows**: `ptyproxy_windows.WindowsPTYSocketProxy` uses
    `socket.socketpair()` as the master/slave byte channel. `os.isatty()`
    returns `False` (the framework itself doesn't care, but user code inside
    a REPL session *may*).

Instantiating `PTYSocketProxy(...)` dispatches to the right subclass
automatically — you don't need to import the backend module yourself.
`isinstance(obj, PTYSocketProxy)` works transparently for both backends.

In-tree consumer: `unpythonic.net.server`, which plugs the slave side into a
`code.InteractiveConsole` so a remote client can drive an in-process REPL
(sharing the server's state — the whole point of `unpythonic.net.server`,
which is a hot-patching back door, not a pseudo-shell). The class itself is
general, though: anything that wants "code in this process that looks like
it's behind a tty from a socket's point of view" can use it.
"""

import platform
from abc import ABC, abstractmethod

__all__ = ["PTYSocketProxy"]


class PTYSocketProxy(ABC):
    """Plug a (P)TY between a network socket and in-process code that expects a terminal.

    Having a (pseudo-)terminal enables the "interactive" features of terminal
    applications. This class differs from many online examples in that **we do
    not** use `pty.spawn`; the code running on the slave side doesn't need to
    be a separate process, and instead runs on a thread in the same process
    as the server.

    **Construction**: call `PTYSocketProxy(sock, on_socket_disconnect,
    on_slave_disconnect)` — dispatch to `PosixPTYSocketProxy` or
    `WindowsPTYSocketProxy` happens inside `__new__`, based on
    `platform.system()`. Direct instantiation of a specific subclass also
    works (e.g. for tests that want to force a backend).

    **Callbacks**:

    `on_socket_disconnect`, if set, is a one-argument callable called when
    an EOF is detected on the socket. It receives the `PTYSocketProxy`
    instance, and can e.g. `proxy.write_to_master(some_disconnect_command)`
    to tell the software connected on the slave side to exit.

    What that command is, is up to the protocol your specific software
    speaks, so we just provide a general mechanism to send it. In other
    words, you get a disconnect event for free, but you need to know how
    to tell your specific software to end the session when that event fires.

    `on_slave_disconnect`, if set, is a similar callable called when an
    EOF is detected on the slave side.

    **Public interface** (all abstract, implemented by subclasses):

      - `start()` — begin forwarding traffic in a daemon thread.
      - `stop()` — shut down and release resources.
      - `write_to_master(data)` — inject bytes on the master side; they
        appear as input on the slave.
      - `open_slave_streams()` — context manager yielding text
        `(rfile, wfile)` over the slave side, suitable for wiring into
        `code.InteractiveConsole`.
      - `name` — human-readable slave-side name for log messages.

    Based on a solution by SO user gowenfawr:
        https://stackoverflow.com/questions/48781155/how-to-connect-inet-socket-to-pty-device-in-python

    On PTYs in Python and in general, see:
        https://sqizit.bartletts.id.au/2011/02/14/pseudo-terminals-in-python/
        http://rachid.koucha.free.fr/tech_corner/pty_pdip.html
        https://matthewarcus.wordpress.com/2012/11/04/embedded-python-interpreter/
        https://terminallabs.com/blog/a-better-cli-passthrough-in-python/
        http://man7.org/linux/man-pages/man7/pty.7.html
    """

    def __new__(cls, *args, **kwargs):
        # When the abstract base class itself is instantiated, dispatch to the
        # platform-specific concrete subclass. Explicit subclass instantiation
        # (cls is a subclass, not PTYSocketProxy itself) bypasses the dispatch
        # and just runs normally — useful for tests that want a specific
        # backend regardless of platform.
        #
        # `__new__` returning a subclass instance causes Python to still call
        # `__init__` on it (because the returned object is-a `cls`), and the
        # lookup resolves to the subclass's `__init__` — so `*args, **kwargs`
        # land in the right place without us needing to forward them manually.
        if cls is PTYSocketProxy:
            if platform.system() == "Windows":
                from .ptyproxy_windows import WindowsPTYSocketProxy
                cls = WindowsPTYSocketProxy
            else:
                from .ptyproxy_posix import PosixPTYSocketProxy
                cls = PosixPTYSocketProxy
        return super().__new__(cls)

    def __enter__(self):
        """Enable ``with PTYSocketProxy(...) as proxy:`` usage.

        The context manager just guarantees `stop()` runs on exit from the
        ``with`` block — whether the body completes normally, raises, or is
        interrupted. This is the recommended way to use the proxy, so that
        the master/slave transport cannot leak on exceptional paths.

        The `start()` call is deliberately *not* pulled into `__enter__`,
        because some callers may want to do setup between construction and
        the start of forwarding. Call `proxy.start()` explicitly inside the
        ``with`` body.
        """
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()
        return False  # don't suppress exceptions

    @abstractmethod
    def start(self):
        """Start forwarding traffic between the master endpoint and the socket."""

    @abstractmethod
    def stop(self):
        """Shut down. Also closes the master/slave transport.

        **Must be idempotent**: calling `stop()` on a proxy that was never
        started, or calling it twice, must be safe. This is load-bearing
        for `__exit__` — the context manager always calls `stop()`, even
        if the caller also called it explicitly inside the ``with`` body.
        """

    @abstractmethod
    def write_to_master(self, data):
        """Write raw bytes to the master side, as if typed by the client.

        Bytes written here appear on the slave side as input, so e.g.
        `proxy.write_to_master(b"quit()\\n")` injects a line of input into
        whatever code is reading the slave stream. Useful to programmatically
        tell a REPL (or other terminal application on the slave side) to exit.

        `data` must be a `bytes` object.
        """

    @abstractmethod
    def open_slave_streams(self, encoding="utf-8"):
        """Context manager yielding ``(rfile, wfile)`` text streams over the slave side.

        Both streams are closed on exit from the ``with`` block; the
        underlying slave transport itself remains managed by the proxy
        and is closed by `stop()`.

        The returned streams are suitable for wiring into
        `code.InteractiveConsole` as its input/output.

        Concrete implementations should decorate with
        `@contextlib.contextmanager`; this declaration is just the contract.
        """

    @property
    @abstractmethod
    def name(self):
        """Human-readable name of the slave side, for log messages.

        On POSIX this is the tty name (`os.ttyname`); on Windows it's a
        synthetic identifier, since no tty is involved. Safe to read after
        `stop()` — subclasses cache it up front.
        """
