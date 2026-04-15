# Deferred Issues

Next unused item code: D13

- **D5**: `dispatch.py` — moved to GitHub issue #99. Dispatch-layer improvements for parametric ABCs (warn/error on indistinguishable multimethods). Typecheck-layer part resolved.


- **D8: Audit typing: abstract parameter types, concrete return types**: Parameters should use abstract types from `collections.abc` (`Mapping`, `Sequence`, `Iterable`) for widest-possible-accepted semantics. Return types should use concrete lowercase builtins (`tuple[int, int]`, `list[int]`, `dict[str, int]`) — PEP 585, Python 3.9+. The capitalized `typing` forms (`Dict`, `List`, `Tuple`) are deprecated aliases for the builtins and offer no extra width — avoid them. Audit existing type hints across the codebase for consistency. (Discovered during raven-cherrypick compare mode planning, 2026-03-30.)


- **D10: Tier 2 REPL tests (subprocess + pty) for `unpythonic.net` client/server**: Tier 1 coverage for `unpythonic.net.client` and `unpythonic.net.server` uses a server-in-thread + in-process client pattern (see `unpythonic/net/tests/`) with scripted input via `builtins.input` monkey-patch and captured stdout/stderr via `io.StringIO`. Fast, single-process, no subprocess boundary needed — the server speaks TCP to `127.0.0.1` and the client loop runs in the same pytest process. **We might never need tier 2.**

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


- **D12: Unit tests for `unpythonic.net.util.ReceiveBuffer`**: The `ReceiveBuffer` class in `unpythonic/net/util.py` is used internally by `unpythonic.net.msg.MessageDecoder` (exercised transitively by the REPL test suite), but it also has a real external consumer in production — `raven.common.netutil.multipart_x_mixed_replace_payload_extractor`, which reuses it as a general-purpose append/set/getvalue buffer for message-boundary-aware reads. As part of the public `unpythonic.net.util` API (`__all__`), it deserves its own targeted unit tests rather than only being covered through `MessageDecoder`'s indirect use. Cheap to add — a new test module in `unpythonic/net/tests/` exercising `append`, `set`, `getvalue`, and the type-check error paths. (Noticed 2026-04-16 during the D9 Windows port.)


