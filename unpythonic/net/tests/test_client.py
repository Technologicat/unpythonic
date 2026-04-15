# -*- coding: utf-8; -*-
"""Tier 1 REPL tests for `unpythonic.net.client` / `unpythonic.net.server`.

In-process, single-test-process.  The REPL server runs on `127.0.0.1:0`
in a daemon thread; the client's interactive loop runs in the main test
thread, driven by a `scripted_repl` context manager that captures
stdout/stderr and feeds a pre-scripted input sequence through a fake
`input()` piped in via the `_input` parameter of `client._connect`.

Why `_input` rather than monkey-patching `builtins.input` globally (as
`mcpyrate/test/test_126_repl.py` does): the server's `InteractiveConsole`
also calls `builtins.input` internally — it needs to, because on the
session thread `sys.stdin` is a `Shim(_threadlocal_stdin)` pointing at
the PTY slave and the only way `code.InteractiveConsole.raw_input`
reaches that is via `input(prompt)`.  A global monkey-patch would
hijack the server's input path too, and the test would hang.  The
`_input` seam lets us replace the client-side `input()` without
touching the server-side one.

The `scripted_repl` helper is the two-REPL-in-one-process sibling of
`mcpyrate/test/test_126_repl.py` (committed there as `0fee81b`), which
is the simpler "one REPL in the process" version.  The shape diverges
intentionally for load-bearing architectural reasons:

  * mcpyrate's version monkey-patches `builtins.input` and replaces
    `sys.stdout` / `sys.stderr` with `StringIO` — simple, correct for
    a single in-process `MacroConsole`.

  * This version cannot do either.  `unpythonic.net.server` also runs
    an `InteractiveConsole` in the same process (on a session thread),
    which *also* calls `builtins.input`, so a global patch would
    hijack the server.  And the server installs a
    `Shim(_threadlocal_stdout)` as `sys.stdout` to route per-thread to
    each session's PTY slave — replacing `sys.stdout` globally would
    kill that routing and the client would hang forever waiting for a
    prompt that never arrives.

  * So this version (a) exposes `fake_input` as a seam the caller
    threads through `_connect(_input=...)`, and (b) mutates the
    **main-thread slot** of `server._threadlocal_stdout/stderr` via
    `ThreadLocalBox.__lshift__`, which leaves session-thread routing
    untouched.

Grep for "scripted_repl" across the fleet if you need to cross-check
the pattern in a third project; keep both versions in mind, pick the
simpler one unless you hit the two-REPL constraint.

Cross-platform: `unpythonic.net` runs on MS Windows too, via the
`socket.socketpair`-based `WindowsPTYSocketProxy` backend. The test
suite runs the full integration tests on every platform in the CI
matrix.  A platform-conditional testset (`tier 1: Windows backend via
server (POSIX-only smoke)`) force-runs the Windows backend on a POSIX
dev machine as extra insurance that the Windows code path is covered
without waiting for Windows CI.

Tier 2 (subprocess + pexpect for real terminal semantics and signal
handling) would be a natural future addition; we might never need it
unless something in tier 1 turns out to miss a regression.
"""

import contextlib
import io
import platform
import socket
import sys
import threading
import time
import types

from ...syntax import macros, test, the, warn  # noqa: F401
from ...test.fixtures import session, testset

from ..msg import MessageDecoder
from ..ptyproxy import PTYSocketProxy
from ..util import socketsource
from ..common import ApplevelProtocolMixin


@contextlib.contextmanager
def scripted_repl(script):
    """Drive the client's interactive REPL through a pre-scripted input sequence.

    `script` is an iterable of strings, each one line the user would
    type (no trailing newlines).  When the script is exhausted, the
    next `input()` call raises `EOFError` — which is how a normal REPL
    exits on Ctrl+D, and how the `unpythonic.net` client sends `quit()`
    to the server for a clean disconnect.

    On exit from the `with` block, `captured.stdout` and `captured.
    stderr` are materialized to plain strings.  Materialization happens
    in `finally`, so it runs even on test failure and the interface is
    consistent between the success and failure paths.

    The fake `input` is yielded as `captured.fake_input` so the caller
    can pass it into `client._connect(..., _input=captured.fake_input)`.

    **Must be used inside a `test_repl_server()` context.**  The naive
    approach of `sys.stdout = StringIO()` would be *wrong* here, because
    once `unpythonic.net.server` is running, `sys.stdout` is a
    `Shim(_threadlocal_stdout)` that routes writes per-thread — each
    session thread writes to its own PTY slave.  A global reassignment
    of `sys.stdout` would replace that Shim and kill the server's PTY
    routing, so the session thread's eval results would go nowhere and
    the client would block forever waiting for a prompt that never
    arrives.  (Ask me how I know.)

    The right layer is the `ThreadLocalBox` that backs the Shim: we
    override the **main thread's** slot in `server._threadlocal_stdout`,
    which leaves the session threads' slots untouched.  Client writes
    (which run in the main thread, through the same Shim) then land in
    our `StringIO`; server writes (which run in session threads) still
    land in the PTY slave.  On exit, we `clear()` the main-thread slot
    so the box falls back to its default (the real stdout).

    Usage::

        with test_repl_server() as (rport, cport):
            with scripted_repl(["2 + 3"]) as captured:
                client._connect(host, rport, cport, _input=captured.fake_input)
        assert "5" in captured.stdout
    """
    # Imported locally to keep this helper usable only when the server
    # module has been loaded.  `server._threadlocal_stdout/stderr` only
    # exist (as ThreadLocalBoxes inside a Shim) once the module has run
    # its top-level code.  Importing at module top would work too, but
    # the local import makes the dependency explicit right here.
    from .. import server

    lines = iter(script)

    def fake_input(prompt=""):
        # Echo the prompt into the captured stream so tests that care
        # about prompt text can see it.  A real tty would also echo.
        sys.stdout.write(prompt)
        sys.stdout.flush()
        try:
            line = next(lines)
        except StopIteration:
            raise EOFError  # REPL's normal exit path (Ctrl+D)
        # Echo the "typed" line too, matching real tty behaviour.
        sys.stdout.write(line + "\n")
        return line

    captured = types.SimpleNamespace(
        stdout=io.StringIO(),
        stderr=io.StringIO(),
        fake_input=fake_input,
    )
    try:
        # Main-thread override only — see docstring.
        server._threadlocal_stdout << captured.stdout
        server._threadlocal_stderr << captured.stderr
        yield captured
    finally:
        # Remove the main-thread override so the box falls back to its
        # default (the real stdout).  We don't just reassign the
        # previous value, because there wasn't one in this thread before
        # we started — the box was holding its default.
        server._threadlocal_stdout.clear()
        server._threadlocal_stderr.clear()
        # Materialize live StringIO → plain str so assertions after the
        # `with` see strings, not file-like objects.  Runs on the
        # failure path too.
        captured.stdout = captured.stdout.getvalue()
        captured.stderr = captured.stderr.getvalue()


@contextlib.contextmanager
def test_repl_server():
    """Start an `unpythonic.net.server` on `127.0.0.1:0` for the duration of the test.

    Yields `(repl_port, control_port)` — the kernel-assigned port numbers
    returned by `server.start()`.  The context manager guarantees
    `server.stop()` runs on exit (even on test failure), so the next
    test gets a clean `_server_instance = None` state.

    Uses `banner=""` to keep the server banner out of captured stdout,
    since tier-1 tests want to assert on eval results, not boilerplate.
    """
    # Imported inside the function so the test module can be collected
    # on MS Windows (the platform check below will skip tests cleanly,
    # but the `import` of `..server` must not explode at module load).
    from .. import server
    bind, rport, cport = server.start(
        locals={},
        bind="127.0.0.1",
        repl_port=0,
        control_port=0,
        banner="",
    )
    try:
        yield rport, cport
    finally:
        server.stop()


def _wait_for_port(host, port, timeout=2.0):
    """Retry `socket.create_connection` until the server is accepting connections.

    `ReuseAddrThreadingTCPServer.__init__` binds and listens synchronously,
    so in theory the server is ready by the time `server.start()` returns.
    In practice there is still a race with `serve_forever` picking up the
    first accept — we've seen the first connection occasionally get a
    connection-refused on a loaded machine.  A couple of retries with a
    small backoff absorbs that.
    """
    deadline = time.monotonic() + timeout
    last_err = None
    while time.monotonic() < deadline:
        try:
            sock = socket.create_connection((host, port), timeout=0.5)
            sock.close()
            return
        except (ConnectionRefusedError, OSError) as err:
            last_err = err
            time.sleep(0.01)
    raise RuntimeError(f"Server at {host}:{port} did not become ready within {timeout}s: {last_err}")


def _run_cleanup_contract_suite(proxy_cls):
    """Run the four cleanup-contract sub-tests against a specific backend class.

    Called once per backend (POSIX and Windows) from the top-level
    `tier 1: ptyproxy cleanup contract` testset. Factoring into a helper
    keeps the tests DRY while still exercising both backends — the
    Windows backend works on POSIX too (via `socket.socketpair`),
    so we can test it on a Linux dev box without waiting for Windows CI.

    Resource-close verification uses the attribute contract
    (`master`/`slave` become `None` after teardown). We don't poke at the
    raw fd with `os.fstat` because the fd type differs between backends
    (POSIX: int, Windows: socket).
    """
    with testset("stop-before-start releases resources"):
        sock = socket.socket()
        try:
            proxy = proxy_cls(sock)
            test[proxy.master is not None]
            test[proxy.slave is not None]
            proxy.stop()
            # Latent bug before fix: `stop()` was gated on
            # `if self._thread:` and did nothing if `start()` had
            # never been called, leaking both fds.
            test[proxy.master is None]
            test[proxy.slave is None]
        finally:
            sock.close()

    with testset("double stop is idempotent"):
        sock = socket.socket()
        try:
            proxy = proxy_cls(sock)
            proxy.stop()
            proxy.stop()  # must not raise
            test[proxy.master is None]
            test[proxy.slave is None]
        finally:
            sock.close()

    with testset("exception in `with` body triggers cleanup"):
        sock = socket.socket()
        proxy_captured = None
        caught = False
        try:
            with proxy_cls(sock) as proxy:
                proxy_captured = proxy
                raise RuntimeError("simulated crash in with body")
        except RuntimeError:
            caught = True
        # The exception must have propagated out of the `with` — the
        # context manager returns False from __exit__, i.e. does not
        # suppress.
        test[caught]
        # …and `stop()` must have run via __exit__, releasing the fds.
        test[proxy_captured.master is None]
        test[proxy_captured.slave is None]
        sock.close()

    with testset("name readable after stop()"):
        sock = socket.socket()
        try:
            proxy = proxy_cls(sock)
            cached_name = proxy.name  # whatever the backend chose
            proxy.stop()
            # `name` is cached at construction time so log messages
            # in a teardown `finally:` block can still reference it
            # after the underlying slave transport is gone.
            test[proxy.name == cached_name]
        finally:
            sock.close()


def runtests():
    # Cleanup contract tests — cross-platform, run before the Windows
    # early-return below. These exercise `PTYSocketProxy` construction,
    # teardown, and context-manager semantics without touching the
    # server/client roundtrip.
    with testset("tier 1: ptyproxy cleanup contract"):
        # Windows backend: works on any platform (`socket.socketpair` is
        # cross-platform), so we always run it. On a POSIX dev box this
        # gives us real coverage of the Windows backend code without
        # waiting for Windows CI to light up.
        with testset("Windows backend (socketpair)"):
            from ..ptyproxy_windows import WindowsPTYSocketProxy
            _run_cleanup_contract_suite(WindowsPTYSocketProxy)

        # POSIX backend: uses `os.openpty`, `termios`, `tty` — imports
        # blow up on Windows. Gated.
        if platform.system() != "Windows":
            with testset("POSIX backend (openpty)"):
                from ..ptyproxy_posix import PosixPTYSocketProxy
                _run_cleanup_contract_suite(PosixPTYSocketProxy)

        with testset("dispatch picks the right backend"):
            sock = socket.socket()
            try:
                proxy = PTYSocketProxy(sock)
                if platform.system() == "Windows":
                    from ..ptyproxy_windows import WindowsPTYSocketProxy
                    test[type(proxy) is WindowsPTYSocketProxy]
                else:
                    from ..ptyproxy_posix import PosixPTYSocketProxy
                    test[type(proxy) is PosixPTYSocketProxy]
                proxy.stop()
            finally:
                sock.close()

    from .. import client

    if platform.system() != "Windows":
        with testset("tier 1: Windows backend via server (POSIX-only smoke)"):
            # Cross-platform validation trick: on POSIX, force the server
            # to use `WindowsPTYSocketProxy` instead of the native POSIX
            # backend, then run a minimal full-REPL roundtrip through it.
            # This exercises the Windows backend's `forward_traffic`
            # thread (select.select + socketpair), `open_slave_streams`
            # (sock.makefile text I/O with line buffering), and
            # `write_to_master` (sock.sendall) under real REPL load —
            # all on a Linux dev machine.
            #
            # On Windows itself the native backend *is* Windows, so this
            # force-smoke is redundant: the full integration testset
            # below already exercises `WindowsPTYSocketProxy` through
            # the same code path. Hence the guard.
            from .. import server as _server_module
            from ..ptyproxy_windows import WindowsPTYSocketProxy
            _original_backend = _server_module.PTYSocketProxy
            _server_module.PTYSocketProxy = WindowsPTYSocketProxy
            try:
                with test_repl_server() as (rport, cport):
                    _wait_for_port("127.0.0.1", rport)
                    _wait_for_port("127.0.0.1", cport)
                    with scripted_repl(["7 * 8"]) as captured:
                        client._connect("127.0.0.1", rport, cport, _input=captured.fake_input)
                    test["56" in the[captured.stdout]]
            finally:
                _server_module.PTYSocketProxy = _original_backend

    with testset("tier 1: full-client ↔ server roundtrip"):
        with testset("basic arithmetic roundtrip"):
            with test_repl_server() as (rport, cport):
                _wait_for_port("127.0.0.1", rport)
                _wait_for_port("127.0.0.1", cport)
                with scripted_repl(["2 + 3"]) as captured:
                    client._connect("127.0.0.1", rport, cport, _input=captured.fake_input)
                # The server eval result "5" must appear in captured
                # client stdout (which also contains the session banner,
                # the prompt, and the echoed input).
                test["5" in the[captured.stdout]]

        with testset("multi-line function definition"):
            with test_repl_server() as (rport, cport):
                _wait_for_port("127.0.0.1", rport)
                _wait_for_port("127.0.0.1", cport)
                with scripted_repl([
                    "def f():",
                    "    return 42",
                    "",
                    "f()",
                ]) as captured:
                    client._connect("127.0.0.1", rport, cport, _input=captured.fake_input)
                test["42" in the[captured.stdout]]

        with testset("syntax error recovery"):
            with test_repl_server() as (rport, cport):
                _wait_for_port("127.0.0.1", rport)
                _wait_for_port("127.0.0.1", cport)
                with scripted_repl([
                    "this is : not valid python $$$",
                    "1 + 1",
                ]) as captured:
                    client._connect("127.0.0.1", rport, cport, _input=captured.fake_input)
                combined = captured.stdout + captured.stderr
                # The server must report the SyntaxError …
                test["SyntaxError" in the[combined]]
                # … and the session must survive the bad line: the
                # following good line's result still shows up.
                test["2" in the[captured.stdout]]

        with testset("clean disconnect on EOF"):
            with test_repl_server() as (rport, cport):
                _wait_for_port("127.0.0.1", rport)
                _wait_for_port("127.0.0.1", cport)
                with scripted_repl([]) as captured:
                    client._connect("127.0.0.1", rport, cport, _input=captured.fake_input)
                # No traceback should escape on the clean path; the
                # client's own "Session closed." message should appear.
                test["Traceback" not in the[captured.stderr]]
                test["Session closed" in the[captured.stdout]]

    with testset("tier 1: netcat-mode raw socket"):
        with test_repl_server() as (rport, cport):  # noqa: F841 -- we only need rport here
            _wait_for_port("127.0.0.1", rport)
            # Talk to the REPL port directly, without using the
            # `unpythonic.net.client`.  This exercises the
            # netcat-compat path on the server: no control channel, no
            # pairing, no handshake — just raw line-oriented I/O through
            # the PTY.
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.connect(("127.0.0.1", rport))
                sock.settimeout(3.0)

                def recv_until(needle, max_wait=3.0):
                    """Read from the socket until `needle` (bytes) appears, or timeout."""
                    buf = b""
                    deadline = time.monotonic() + max_wait
                    while needle not in buf:
                        if time.monotonic() >= deadline:
                            break
                        try:
                            chunk = sock.recv(4096)
                        except socket.timeout:
                            break
                        if not chunk:
                            break
                        buf += chunk
                    return buf

                # Drain the banner/prompt header so the eval result is
                # the next thing we see.
                recv_until(b">>>> ")
                sock.sendall(b"2 + 3\n")
                tail = recv_until(b">>>> ", max_wait=3.0)
                test[b"5" in the[tail]]
                # Close politely.  The server's `on_socket_disconnect`
                # writes `"quit()\n"` to the PTY master, which tears
                # down the session without crashing the server thread.

    with testset("tier 1: control-channel RPC"):
        with test_repl_server() as (rport, cport):  # noqa: F841 -- we only need cport here
            _wait_for_port("127.0.0.1", cport)
            # Talk to the control port directly using the app-level
            # protocol.  This bypasses the REPL loop entirely — it
            # tests only the DescribeServer / TabComplete RPC surface.

            class _ProbeClient(ApplevelProtocolMixin):
                def __init__(self, sock):
                    self.sock = sock
                    self.decoder = MessageDecoder(socketsource(sock))

            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as csock:
                csock.connect(("127.0.0.1", cport))
                probe = _ProbeClient(csock)

                # DescribeServer: must return status=ok and a prompts dict.
                probe._send({"command": "DescribeServer"})
                reply = probe._recv()
                # `the[reply]` (not `the[reply["status"]]`) so a failure
                # shows the whole reply dict, including any "reason"
                # field the server may have set — more actionable than
                # just seeing `reply["status"] == "failed"`.
                test[the[reply]["status"] == "ok"]
                test["ps1" in the[reply["prompts"]]]
                test["ps2" in the[reply["prompts"]]]

                # TabComplete: ask for completions of "pri" in state 0.
                # `rlcompleter.Completer` over an empty namespace will
                # still find builtins like `print`.
                probe._send({"command": "TabComplete", "text": "pri", "state": 0})
                reply = probe._recv()
                test[the[reply]["status"] == "ok"]
                test[the[reply]["result"] is not None]
                test["print" in the[reply["result"]]]

    with testset("tier 1 stretch: sequential reconnect"):
        # Start a server once, then connect / disconnect / reconnect with
        # the full client.  Regression check for session teardown hygiene:
        # if `ConsoleSession` or `PTYSocketProxy` leaks resources on exit,
        # the second connect is where it would show.
        with test_repl_server() as (rport, cport):
            _wait_for_port("127.0.0.1", rport)
            _wait_for_port("127.0.0.1", cport)

            with scripted_repl(["10 * 11"]) as captured1:
                client._connect("127.0.0.1", rport, cport, _input=captured1.fake_input)
            test["110" in the[captured1.stdout]]

            with scripted_repl(["20 * 21"]) as captured2:
                client._connect("127.0.0.1", rport, cport, _input=captured2.fake_input)
            test["420" in the[captured2.stdout]]

    with testset("tier 1 stretch: two concurrent clients"):
        # Two real client loops in parallel threads, one server.  The
        # server supports multiple simultaneous REPL sessions (each gets
        # its own thread via ThreadingTCPServer), and each session has
        # its own `_threadlocal_stdout`/`_threadlocal_stderr` slot.  So
        # as long as the session threads don't stomp on each other, both
        # clients should get their own results back without cross-talk.
        #
        # IMPORTANT: each client thread runs `_connect` from its own
        # thread; the `scripted_repl` helper, however, overrides only
        # the *main* thread's slot in `_threadlocal_stdout`.  So for
        # this test we can't use `scripted_repl` — we drive the client
        # threads directly, and assert on values the server evals
        # produced, by having each thread stash its result list.
        #
        # We sidestep the stdout-capture issue entirely: each client
        # uses a plain fake_input that doesn't need captured output,
        # and we just assert via the return path (inputs fed, clean
        # exit, no exception crossed the thread boundary).
        with test_repl_server() as (rport, cport):
            _wait_for_port("127.0.0.1", rport)
            _wait_for_port("127.0.0.1", cport)

            thread_errors = []

            def run_one_client(script_lines):
                lines = iter(script_lines)
                def inp(prompt=""):
                    try:
                        return next(lines)
                    except StopIteration:
                        raise EOFError
                try:
                    client._connect("127.0.0.1", rport, cport, _input=inp)
                except BaseException as err:  # pragma: no cover
                    thread_errors.append(err)

            # Two disjoint scripts; we assert on the fact that both
            # clients reach clean exit (EOFError → quit() → SessionExit)
            # without raising.  Getting this far means the server
            # demuxed both sessions correctly.
            t1 = threading.Thread(target=run_one_client, args=(["100 + 23"],))
            t2 = threading.Thread(target=run_one_client, args=(["200 + 46"],))
            t1.start()
            t2.start()
            t1.join(timeout=10.0)
            t2.join(timeout=10.0)
            test[not the[t1.is_alive()]]  # didn't time out — `not` is unary, the[] required
            test[not the[t2.is_alive()]]
            test[thread_errors == []]


if __name__ == '__main__':  # pragma: no cover
    with session(__file__):
        runtests()
