# Deferred Issues

Next unused item code: D12

- **D5**: `dispatch.py` — moved to GitHub issue #99. Dispatch-layer improvements for parametric ABCs (warn/error on indistinguishable multimethods). Typecheck-layer part resolved.


- **D8: Audit typing: abstract parameter types, concrete return types**: Parameters should use abstract types from `collections.abc` (`Mapping`, `Sequence`, `Iterable`) for widest-possible-accepted semantics. Return types should use concrete lowercase builtins (`tuple[int, int]`, `list[int]`, `dict[str, int]`) — PEP 585, Python 3.9+. The capitalized `typing` forms (`Dict`, `List`, `Tuple`) are deprecated aliases for the builtins and offer no extra width — avoid them. Audit existing type hints across the codebase for consistency. (Discovered during raven-cherrypick compare mode planning, 2026-03-30.)


- **D9: Port `unpythonic.net` (REPL server/client) to MS Windows**: The remote-REPL subsystem (`unpythonic.net.server`, `unpythonic.net.client`, `unpythonic.net.ptyproxy`) is currently documented as POSIX-only (see 2.0.0 CHANGELOG). The blockers are in `ptyproxy.py`, which uses `termios`, `fcntl`, `pty`, and `select` to create a pseudoterminal pair for the server-side `code.InteractiveConsole` to read/write through. None of those modules exist on Windows.

  **Rough list of Windows equivalents**, in order of plausibility:

  - **`pywinpty`** (third-party, ~active maintenance) — the preferred option. Wraps the Windows **Pseudo Console API** (ConPTY, introduced in Windows 10 1809, October 2018). Used by JupyterLab's terminal and by `xterm.js`-based backends. Provides a pty-like interface that `ptyproxy.py` could consume with a thin adapter. Would need to become a Windows-only optional dependency of unpythonic.
  - **`msvcrt`** (stdlib) — low-level Windows console I/O. NOT a pty equivalent: it's just console-focused character access (`kbhit`, `getch`, `getwch`, etc.). Probably not useful on its own for this purpose — it doesn't give you the "line discipline + bidirectional pipe" semantics that `pty` provides on POSIX.
  - **`winpty`** (pre-ConPTY, C-level library, third-party) — the older Cygwin-era solution. ConPTY supersedes it and `pywinpty` can use ConPTY directly on recent Windows. Only relevant if we need to support Windows versions before 10-1809, which we don't.
  - **`ptyprocess` / `pexpect`** — pexpect has a Windows backend, but it uses `wexpect` under the hood and has historically been finicky. Not currently recommended as the primary approach, but could serve as a higher-level wrapper *on top of* pywinpty.
  - **Raw Windows API via `ctypes`** — `CreatePseudoConsole()`, `ResizePseudoConsole()`, `ClosePseudoConsole()` can be called directly through `ctypes` if we want to avoid the `pywinpty` dependency. More work; smaller dep footprint. Decision to make at design time.

  **Likely decomposition** of the work:

  1. Split `ptyproxy.py` into a platform-dispatch wrapper that imports either a `ptyproxy_posix` submodule (current code) or a new `ptyproxy_windows` submodule. Both expose the same `PTYSocketProxy` class.
  2. Implement `ptyproxy_windows` using `pywinpty` — or, if that turns out to be heavy for an optional dep, using direct `ctypes` calls to ConPTY. ConPTY's semantics differ from Unix pty in subtle ways (output buffering, line-discipline equivalent, terminal-resize signalling), so this will need careful testing against the existing unit/integration tests once those exist (see the interactive-REPL testing strategy designed in this same session).
  3. Make `pywinpty` (or whatever is chosen) a Windows-only optional dep via `[project.optional-dependencies]` — e.g. `windows = ["pywinpty>=2.0"]` — with a helpful ImportError message if someone tries to use `unpythonic.net.{server,client}` on Windows without it installed.
  4. Add Windows cells to `unpythonic.net`'s test matrix (which depends on tests existing in the first place — currently `unpythonic.net` has no tests, also covered by the testing-strategy discussion this session).
  5. Update the 2.0.0 CHANGELOG entry that currently documents `unpythonic.net` as POSIX-only once this lands.

  **Why deferred**: this is a non-trivial port that probably deserves its own design session — at minimum a careful read of pywinpty's API surface, a mapping of pty primitives to their ConPTY equivalents, and a plan for how to test the result without having a Windows dev machine. User currently has only Linux dev boxes; any debugging would be entirely via CI, which is feasible but slow-iterating.

  **Related**: the `parse_and_bind` Darwin-branch fix in `net/client.py` (2026-04-15) was a prerequisite refactor — `net/client.py` is now in the right shape for the Windows port to plug into. Also, the three-tier hybrid readline fallback pattern documented in `raven.librarian.minichat` and `mcpyrate.repl.macropython` (same session) is directly reusable for `net/client.py` once `net/client.py`'s top-level `import readline` is moved inside the client function and guarded.

  (Added 2026-04-15, based on audit + discussion during the Windows-CI expansion session.)


- **D10: Tier 2 REPL tests (subprocess + pty) for `unpythonic.net` client/server**: Tier 1 coverage for `unpythonic.net.client` and `unpythonic.net.server` uses a server-in-thread + in-process client pattern (see `unpythonic/net/tests/`) with scripted input via `builtins.input` monkey-patch and captured stdout/stderr via `io.StringIO`. Fast, single-process, no subprocess boundary needed — the server speaks TCP to `127.0.0.1` and the client loop runs in the same pytest process. **We might never need tier 2.**

  A second tier would spawn the server and client as real subprocesses, with each end driven through a pseudo-terminal (`pexpect` / `ptyprocess`), to catch things tier 1 cannot reach:

  - Real GNU-readline binding behaviour on the client side — tab completion against the remote completer, history recall, multi-line input rendering.
  - Terminal escape sequences from the colorizer on both sides.
  - Signal handling — Ctrl+C from the client forwarded to the remote REPL, Ctrl+D disconnecting cleanly.
  - The ptyproxy machinery itself, end-to-end. Tier 1 stubs around the pty by running the `InteractiveConsole` directly against in-memory streams; tier 2 would actually exercise `unpythonic.net.ptyproxy.PTYSocketProxy` with a real master/slave pair.

  Cost:
  - ~0.5–1 s startup per test × two processes per test (client + server) = ~1–2 s per test. Matters for suite size.
  - POSIX-only naturally. Windows support depends on D9 (port `unpythonic.net` to MS Windows) landing first — no point designing tier 2 for a subsystem that doesn't run on Windows yet. If/when D9 lands, Windows tier 2 can use the same ConPTY backend that D9 introduces.
  - `pexpect` would become a new dev dep. Small but non-zero.

  **Rough shape if we ever do it:**
  ```python
  import pexpect
  server = pexpect.spawn(f"{sys.executable} -m unpythonic.net.server", ...)
  server.expect(r"Listening on \S+")
  client = pexpect.spawn(f"{sys.executable} -m unpythonic.net.client", ...)
  client.expect(r">>> ")
  client.sendline("2 + 3")
  client.expect(r"5\s*\n>>> ")
  client.sendcontrol("d")
  client.expect(pexpect.EOF)
  server.terminate()
  ```

  **When to actually do it**: only if tier 1 coverage turns out to miss something important (a regression hits prod that tier 1 would not have caught). The in-thread server + scripted client approach already exercises most of the protocol surface; tier 2 is primarily a safety net for terminal-semantics and signal-path bugs. Until one of those bites, tier 1 is the main win. (Added 2026-04-15, alongside the tier 1 bring-up.)


- **D11: Implement tier 1 REPL tests for `unpythonic.net.client` / `unpythonic.net.server`**: Currently `unpythonic/net/tests/` has **no test files**. The design for how to bring `unpythonic.net` under test was worked out on 2026-04-15 in a session that also implemented the canonical tier-1 example in mcpyrate — that example lives at `mcpyrate/test/test_126_repl.py` (committed as `0fee81b`) and is the reference to crib from when picking this up.

  **Core approach**: in-process, single-test-process. No subprocess boundary. The server runs in a daemon thread on a throwaway `127.0.0.1` port; the client runs in the same process with its interactive loop driven by the `scripted_repl` context manager (monkey-patches `builtins.input`, captures stdout/stderr via `io.StringIO`). Both ends speak TCP to `127.0.0.1`, which keeps everything local and debuggable. The `scripted_repl` helper pattern to copy verbatim:

  - State changes (input swap, stdout swap, stderr swap) go **inside** the `try` block so a mid-setup failure still triggers the `finally` restoration — atomic from the caller's perspective.
  - `StringIO → str` materialization happens inside `finally`, so captured values are consistent between success and failure paths.
  - Scripted input ends by raising `EOFError` when the script is exhausted — that's how `code.InteractiveConsole.interact()` exits cleanly.

  **Where to put the tests**: new file `unpythonic/net/tests/test_client.py` (runtests.py auto-discovers `test_*.py` under each package). Use the unpythonic test-framework style: `runtests()` function, `with testset("..."):` blocks, `test[...]` assertion macros, `the[...]` value capture. See the CLAUDE.md "unpythonic.test.fixtures framework" subsection for the semantic Pass/Fail/Error/Warn distinction if uncertain about which is which.

  **Plumbing you'll need**:

  1. **Server-in-thread helper.** Something like:
     ```python
     def start_test_server() -> tuple[threading.Thread, int]:
         """Start a daemon server on 127.0.0.1:<random-free-port>.  Returns (thread, port)."""
         ...  # bind to port 0, retrieve the assigned port, hand off to run_server in a thread
     ```
     The tricky bit is "wait for server ready" before the client connects. Options: a `threading.Event` that the server sets after it binds; or `socket.create_connection` in a retry loop with a short backoff on the client side. Either works; the first is cleaner if `unpythonic.net.server.run_server` can accept a ready-event parameter, the second avoids touching server code.
  2. **Decide: is there a working `run_server(port=0, ...)` entry point today?** If not, you may need a small refactor in `server.py` to expose one. Check first — the existing code may already accept a port parameter.
  3. **Cleanup**. Daemon threads don't block interpreter shutdown, but a leaked socket on the server side can prevent a quick re-run. Implement a `stop_test_server()` helper that closes the listen socket cleanly, or use a `contextmanager`-style `with test_server() as (thread, port):` so the teardown is guaranteed.
  4. **Client-side**: `unpythonic.net.client.run_client(host="127.0.0.1", repl_port=port, control_port=...)` (check actual signature) driven inside a `scripted_repl` block. If the client has a module-level `import readline` that needs to be moved inside the client function to avoid import-time ImportError on Windows, do that refactor as a prerequisite — but for the initial Linux-only tier 1 it's not strictly necessary (and it's covered in more depth by the D9 Windows port).

  **Tests to start with** (5–6 is a good starting coverage, mirroring mcpyrate's test_126_repl structure):

  - `test_basic_roundtrip` — connect, submit `"2 + 3"`, expect `"5"` in client stdout.
  - `test_multiline_input` — `def f():` / `    return 42` / blank line / `f()` → `42` appears.
  - `test_syntax_error_recovery` — bad input produces a SyntaxError in the client output, then the next good input still evaluates. The remote eval runs on the server; the server should catch its own SyntaxError and respond, not crash.
  - `test_clean_disconnect` — empty script → EOFError → client disconnects → server continues running (verify by doing a second connect after).
  - `test_protocol_level_roundtrip` (bypassing the interactive loop) — connect directly to the TCP socket, send a framed message per the protocol in `unpythonic.net.msg`, verify the response. This covers the server/client boundary without going through `input()` at all and is the best place to catch regressions in the message protocol itself.
  - *Stretch*: `test_two_clients_concurrent` — if the server supports multiple simultaneous REPL sessions, connect two clients in separate threads and verify they don't interfere.

  **Watch out for**:

  - **Port collisions**: always bind to port 0 and ask the kernel for the actual port via `sock.getsockname()[1]`. Never hardcode a port in the test.
  - **Shutdown latency**: if a test leaves a bound socket behind, the next test run on the same port may fail. The daemon-thread approach helps but explicit cleanup via `SO_REUSEADDR` or an atexit hook is more robust.
  - **Stderr leakage**: the server may log to real stderr during the test. Either redirect via `sys.stderr = ...` inside the test (the `scripted_repl` helper already does this for the client), or arrange for the server to use its own logger that the test configures.
  - **macOS `parse_and_bind` branch** in `net/client.py` already lands via this same 2026-04-15 session (see CHANGELOG under 2.0.1 Fixed); tests should exercise this branch on macOS CI once they exist.

  **Why deferred**: the helper pattern is straightforward but the server-in-thread plumbing plus shutdown semantics deserves focused design attention, not a squeeze at the end of an already-long session. This entry is self-contained enough that a fresh CC session can pick it up cold.

  (Added 2026-04-15 at the same natural stopping point where D9 and D10 were added. Related: D10 is the tier 2 counterpart — subprocess + pty, deferred until we know tier 1 isn't enough.)
