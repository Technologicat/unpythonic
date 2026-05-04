# Deferred TODOs

## Dispatch: indistinguishable parametric ABC multimethods (GitHub #99)

Dispatch-layer improvements for parametric ABCs — warn/error on indistinguishable multimethods. Tricky because checkability is value-dependent (Sized vs opaque iterator). Typecheck-layer part is resolved.


## Type annotations — remaining hard-tier modules

As of v2.1.0, 32 of 34 pure-Python modules are annotated. Two remain — genuinely resistant to static typing:

- `dispatch.py` (7 exports) — runtime multiple dispatch, `typing` module introspection, multimethod resolution.
- `typecheck.py` (1 export) — deeply introspective runtime type checking; the function *is* the type system.

Also within already-annotated modules, some functions were deliberately left unannotated: `curry`, `compose*` family, `flatten*` family (dynamic arity, `Values` unpacking, recursive type flattening). Convention established: `F = TypeVar('F', bound=Callable)` for callables, `T = TypeVar('T')` for data values; `fillvalue` parameters use `Any` (sentinel may differ from element type). The original audit concern (abstract params, concrete returns, no deprecated `typing` forms) should be checked against the annotations added. PEP 695 TODOs left in `arity.py` and `conditions.py` for when floor bumps to 3.12.

Updated 2026-04-17.


## Tier 2 REPL tests (subprocess + pty) for `unpythonic.net` client/server

Tier 1 coverage for `unpythonic.net.client` and `unpythonic.net.server` uses a server-in-thread + in-process client pattern (see `unpythonic/net/tests/`) with scripted input via a private `_input` seam on `client._connect(..., _input=fake_input)` and captured stdout/stderr via `io.StringIO`. Fast, single-process, no subprocess boundary needed — the server speaks TCP to `127.0.0.1` and the client loop runs in the same test process. **We might never need tier 2.**

**Important framing**: tier 1 is a *protocol and plumbing test*, not a terminal-UX test.  The `_input` seam replaces the entire `input()` pathway before readline is ever reached, so readline's line editor, history, completer binding, and interrupt-during-input are **not partially covered — they are 0% covered**.  A regression in `readline.parse_and_bind`, in the custom remote completer wiring, or in the SIGINT-during-readline path would pass tier 1 silently.  Tier 2 isn't "a safety net for edge cases" — it's the only place these things get exercised at all.

A second tier would spawn the server and client as real subprocesses, with each end driven through a pseudo-terminal (`pexpect` / `ptyprocess`), to catch things tier 1 cannot reach:

- Real GNU-readline binding behaviour on the client side — tab completion against the remote completer, history recall, multi-line input rendering.
- Terminal escape sequences from the colorizer on both sides.
- Signal handling — Ctrl+C from the client forwarded to the remote REPL, Ctrl+D disconnecting cleanly.
- The ptyproxy machinery itself, end-to-end. Tier 1 stubs around the pty by running the `InteractiveConsole` directly against in-memory streams; tier 2 would actually exercise `unpythonic.net.ptyproxy.PTYSocketProxy` with a real master/slave pair.

Cost:

- ~0.5–1 s startup per test × two processes per test (client + server) = ~1–2 s per test. Matters for suite size.
- POSIX-only naturally. Since D9 landed (2026-04-16), `unpythonic.net` runs on Windows too via `socket.socketpair`, but tier 2 still needs real pseudo-terminals — on Windows that means ConPTY, which D9 deliberately avoided. If tier 2 ever materializes, its Windows variant is an independent design problem.
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

**When to actually do it**: only if tier 1 coverage turns out to miss something important (a regression hits prod that tier 1 would not have caught). The in-thread server + scripted client approach already exercises most of the protocol surface; tier 2 is primarily a safety net for terminal-semantics and signal-path bugs. Until one of those bites, tier 1 is the main win.

Added 2026-04-15, alongside the tier 1 bring-up.


## Flexible view variant

An older, more flexible implementation of `view` exists somewhere in the ancient git history, supporting more advanced slicing at the cost of worse performance. Could be resurrected as an alternative for use cases where flexibility matters more than speed. Dig through the history to find it.

Noted 2026-04-16.


## Audit bare `{path}` interpolation for repr/raw asymmetry on Windows

Fleet-wide audit across all projects. The known failure mode (mcpyrate `cacbfd2`, 2026-04-15): an f-string interpolates a file path with bare `{__file__}`, producing raw backslashes (`C:\a\b`), while the other side of a comparison uses `repr()`/`unparse()` output with escaped backslashes (`C:\\a\\b`) — mismatch on Windows, passes on POSIX by accident. Fix is `{__file__!r}` so both sides speak the same dialect. The risk is NOT f-string reinterpretation (that's safe), but asymmetry when a bare-interpolated path is compared against, compiled as, or embedded into Python source. Grep hints: `__file__` in f-strings; also any path value interpolated into strings that later reach `compile()`, `eval()`, `ast.unparse()`, assertions, or similar.

Noted 2026-04-17.


## CI: PyPy-3.11 / macOS / Windows — `test_dbg` errors via `inspect.getframeinfo`

`unpythonic.syntax.tests.test_dbg` errors out twice on PyPy-3.11 / macOS-latest and PyPy-3.11 / windows-latest, with `TypeError: unsupported operand type(s) for -: 'NoneType' and 'int'` raised at `inspect.py:1728` (`start = lineno - 1 - context//2`, with `lineno=None`). Trigger path: `test[]` macro → `_observe` → `testexpr` (frame at `line -1`, i.e. macro-generated) → `unpythonic.misc.callsite_filename` → `inspect.stack()`. Linux PyPy-3.11 unaffected.

**Pre-existing**: appeared between 2026-04-24 (CI green on `8182293`) and 2026-05-04 (CI red on `5bcf3d4`) without any code change to the affected paths. PyPy version string unchanged (3.11.15) — most likely a runner-image bump on the floating `macos-latest`/`windows-latest` tags introduced a PyPy binary or environment change that exposes the macro-frame `lineno=None` case in upstream `inspect.getframeinfo`.

**Mitigation options**: guard `unpythonic.misc.callsite_filename` against `None`-`lineno` frames (skip them or substitute 1); or pin PyPy's tooled subversion in CI. The first is more robust to upstream churn and helps any user running on PyPy with macro frames in the stack.

Noted 2026-05-04.


## Remove `unpythonic.amb.MonadicList` alias (3.0.0)

As part of the monads port, `MonadicList` was moved to `unpythonic.monads.List` with a varargs constructor (`List(1, 2, 3)` instead of `MonadicList([1, 2, 3])`). A silent alias `MonadicList = List` is kept in `unpythonic/amb.py` for backward-name compatibility during the 2.x series. Remove the alias in 3.0.0 along with the accompanying `TODO(3.0.0)` comment at the alias site. Users must then import `List` directly from `unpythonic.monads`. Note: this is name-only compat — the constructor signature changed at 2.0.0, so existing callers of `MonadicList([...])` already needed to switch to varargs or `from_iterable(...)` at 2.0.0.

Noted 2026-04-17.
