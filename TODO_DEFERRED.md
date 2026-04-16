# Deferred Issues

Next unused item code: D14

- **D5**: `dispatch.py` — moved to GitHub issue #99. Dispatch-layer improvements for parametric ABCs (warn/error on indistinguishable multimethods). Typecheck-layer part resolved.


- **D8: Audit typing: abstract parameter types, concrete return types**: Parameters should use abstract types from `collections.abc` (`Mapping`, `Sequence`, `Iterable`) for widest-possible-accepted semantics. Return types should use concrete lowercase builtins (`tuple[int, int]`, `list[int]`, `dict[str, int]`) — PEP 585, Python 3.9+. The capitalized `typing` forms (`Dict`, `List`, `Tuple`) are deprecated aliases for the builtins and offer no extra width — avoid them. Audit existing type hints across the codebase for consistency. (Discovered during raven-cherrypick compare mode planning, 2026-03-30.)


- **D10: Tier 2 REPL tests (subprocess + pty) for `unpythonic.net` client/server**: Tier 1 coverage for `unpythonic.net.client` and `unpythonic.net.server` uses a server-in-thread + in-process client pattern (see `unpythonic/net/tests/`) with scripted input via a private `_input` seam on `client._connect(..., _input=fake_input)` and captured stdout/stderr via `io.StringIO`. Fast, single-process, no subprocess boundary needed — the server speaks TCP to `127.0.0.1` and the client loop runs in the same test process. **We might never need tier 2.**

  **Important framing**: tier 1 is a *protocol and plumbing test*, not a terminal-UX test.  The `_input` seam replaces the entire `input()` pathway before readline is ever reached, so readline's line editor, history, completer binding, and interrupt-during-input are **not partially covered — they are 0% covered**.  A regression in `readline.parse_and_bind`, in the custom remote completer wiring, or in the SIGINT-during-readline path would pass tier 1 silently.  Tier 2 isn't "a safety net for edge cases" — it's the only place these things get exercised at all.

  A second tier would spawn the server and client as real subprocesses, with each end driven through a pseudo-terminal (`pexpect` / `ptyprocess`), to catch things tier 1 cannot reach:

  - Real GNU-readline binding behaviour on the client side — tab completion against the remote completer, history recall, multi-line input rendering.
  - Terminal escape sequences from the colorizer on both sides.
  - Signal handling — Ctrl+C from the client forwarded to the remote REPL, Ctrl+D disconnecting cleanly.
  - The ptyproxy machinery itself, end-to-end. Tier 1 stubs around the pty by running the `InteractiveConsole` directly against in-memory streams; tier 2 would actually exercise `unpythonic.net.ptyproxy.PTYSocketProxy` with a real master/slave pair.

  Cost:
  - ~0.5–1 s startup per test × two processes per test (client + server) = ~1–2 s per test. Matters for suite size.
  - POSIX-only naturally. Since D9 landed (2026-04-16), `unpythonic.net` runs on Windows too via `socket.socketpair`, but tier 2 still needs real pseudo-terminals — on Windows that means ConPTY, which D9 deliberately avoided (see the D9 discussion). If tier 2 ever materializes, its Windows variant is an independent design problem.
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


- **D13: Teaching-friendly monad abstractions**: Port the monad hacks from https://github.com/Technologicat/python-3-scicomp-intro/tree/master/examples (monads.py) into unpythonic. `MonadicList` already exists in `amb.py` as precedent; the teaching examples include additional monad abstractions that could be generally useful. Some overlap with OSlash, but unpythonic already duplicates stdlib/third-party functionality where it adds value in its own voice (conditions/restarts, fold/scan suite). (Noted 2026-04-16.)


