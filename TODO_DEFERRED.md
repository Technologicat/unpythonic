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


## Unify `accepts_arity` helpers across `excutil` and `conditions`

`unpythonic.excutil._accepts_arity(f, n)` (introduced alongside `withf` in 2.2.0) is the single source of truth for `tryf` / `withf`'s "n-arg form vs 0-arg thunk" dispatch, with the policy "default to the n-arg form on `UnknownArity`". `unpythonic.conditions.signal` (around line 199) defines its own private `accepts_arg(f)` helper with the same shape (n=1 hardcoded, returns `True` on `UnknownArity`). It would be natural to share one helper.

**Caveat**: the right *policy* may be context-dependent. `tryf` and `withf` are user-facing combinators where defaulting to the n-arg form is the more flexible choice when introspection fails. The condition system's handler-dispatch is part of a fault-handling pathway — if anyone ever wants a stricter or more conservative default there (e.g. raise instead of guess, or default to thunk to avoid double-failure), that should be a deliberate decision per call site, not a side effect of unification. So a shared helper would either need a `default_on_unknown` parameter, or stay split into two helpers documenting the policy choice.

Discovered during #76 (2026-05-05).


## Remove `unpythonic.amb.MonadicList` alias (3.0.0)

As part of the monads port, `MonadicList` was moved to `unpythonic.monads.List` with a varargs constructor (`List(1, 2, 3)` instead of `MonadicList([1, 2, 3])`). A silent alias `MonadicList = List` is kept in `unpythonic/amb.py` for backward-name compatibility during the 2.x series. Remove the alias in 3.0.0 along with the accompanying `TODO(3.0.0)` comment at the alias site. Users must then import `List` directly from `unpythonic.monads`. Note: this is name-only compat — the constructor signature changed at 2.0.0, so existing callers of `MonadicList([...])` already needed to switch to varargs or `from_iterable(...)` at 2.0.0.

Noted 2026-04-17.


## `isec` misses non-bare-name escape continuations, and does so silently

`unpythonic/syntax/util.py`'s `isec` matches an escape continuation only through
`getname(..., accept_attr=False)`, and says so itself: "**CAUTION**: Only bare-name references are
supported." So an ec reached as `obj.ec(...)` is not recognized as an escape, and the `tco` /
`continuations` machinery does not transform the call.

**The right fix is to resolve statically what the binding points to**, where that can be done (Juha,
2026-08-16). What that leaves open is the case where it cannot — an ec stored in a container, chosen
at runtime, or reached through a name the expander cannot follow.

**A cheap interim step, before solving the hard half.** The failure is currently silent, and a missed
rewrite is not a mild degradation: the construct is rewritten *because* it needs rewriting, so what
follows is a crash, or worse, quietly wrong behaviour. `dbg` already handles the same class the other
way — a custom print function given as anything but a bare name raises `SyntaxError("Custom debug
print function must be specified by a bare name")`, with an in-source TODO recording that `Attribute`
support is wanted and why it is awkward (AST nodes do not compare). Making `isec` loud in the same
style would convert an invisible miss into a diagnosable one, and is independent of whether the
static resolution ever gets built.

Worth checking whether other `accept_attr=False` sites share the problem. Most do not: `prefix`'s
`q`/`u`/`kw`, the `let` binding scanners and `autoref`'s internal markers all match names that can
only be bare, so there is nothing to resolve there.

Discovered while writing the fleet's `unpythonic` skill (2026-08-16).


## Documentation gaps found by writing an outside summary of the library

Writing the fleet's `unpythonic` and `macro-enabled-python` skills was, incidentally, a test of whether
the docs communicate to a reader who has not written the library. Most of it held up — the
troubleshooting entries, `main.md` on macro-imports, and "macro expansion time where exactly?" all
landed on one reading. Several things did not, and they share a shape: **the caveat lives somewhere other
than next to the thing it is about.**

- **`from unpythonic import env` gives the *module*, not the class.** `__init__.py` never star-imports
  `.env`, so the submodule attribute is what survives, and `env(x=1)` fails with "module is not
  callable". The correct form is `from unpythonic.env import env`. Nothing in the docs says this;
  it has to be discovered by trying it. This is the most user-facing of them — `env` is one of the
  most-used things in the library.

  **What the 3.0.0 fix would actually cost, measured rather than estimated (2026-08-16).** Six
  submodules already sit in the state `env` would move to — `llist`, `let`, `fix`, `fup`, `gtco`,
  `assignonce` are all shadowed by a same-named symbol from the star-import — so the question is
  answerable by experiment rather than argument. Testing against `llist`: `from unpythonic.llist
  import cons` works, `sys.modules["unpythonic.llist"]` works, and the internal `from ..llist import`
  form works. **Exactly one route breaks: attribute-style `unpythonic.llist.cons`**, because the
  import machinery resolves submodules through `sys.modules` while attribute access sees whatever the
  star-import left behind.

  Applied to `env`, that residual cost is close to nil, because `unpythonic/env.py`'s `__all__` is
  exactly `["env"]`. The only name anyone could want attribute-style is `unpythonic.env.env` — which
  the change turns into `unpythonic.env`, i.e. the thing we want. So "it becomes clumsy or impossible
  to refer to the module" does not really bind here: there is nothing else in the module to refer to.

  On the macro layer, state the observation and not more than it supports: nothing in
  `unpythonic/syntax/` currently matches `env` by name, and `syntax/lambdatools.py:25` reaches the
  class explicitly with `from ..env import env`. That is *not* evidence that macros do not need it
  (Juha, 2026-08-16) — the macros predate any heavy direct use of `env`, Raven included, so the
  absence may record what nobody needed at the time rather than what is unnecessary. A macro wanting
  to recognize a user-constructed `env` at a call site would want exactly the name-matching a
  package-level re-export makes possible. So treat this as neutral-to-favourable, not as a reason
  against.

  **The backward-compat cost is smaller than it looks, because the broken forms were never the
  recommended ones.** `from unpythonic import env` then `env.env(...)`, and `import unpythonic.env`
  then `unpythonic.env.env(...)`, both break — and both have always been discouraged. The form the
  change is *for* is `from unpythonic import env` then `env()`, which is the consistent spelling and
  does not work today.

  **A separate problem that this change does not fix, and that should be sized alongside it.** Some
  `unpythonic` functions take a parameter named `env`, which shadows the class of the same name in
  that scope. `unpythonic` already works around it internally: `lispylet.py:11` imports
  `from .env import env as _envcls` so that line 225's `env` parameter and line 228's `_envcls()`
  can coexist. Downstream, **9 Raven modules** carry `from unpythonic.env import env as envcls` for
  the same reason — a call site needs to construct an `env` to pass into a parameter called `env`.
  Re-exporting the class does nothing for this: the collision is parameter-versus-name in a local
  scope, independent of how the class was imported. Renaming that parameter is its own API break, so
  if both are wanted, 3.0.0 is where they go together.

  **Two fixes here, and only one of them is cheap** (Juha, 2026-08-16). Documenting the gotcha at the
  site is non-breaking and can land in any release. *Actually* re-exporting the class would change
  what `from unpythonic import env` returns, which breaks anyone relying on getting the module — so
  the real fix waits for **3.0.0**, and wants to go in together with whatever other API-breakage debt
  has accumulated. Size that first: the convention is an in-source `TODO(3.0.0)` marker plus an item
  here, so `grep -rn "TODO(3.0.0)" unpythonic/` is the inventory command. As of 2026-08-16 it finds
  one (the `MonadicList` alias in `amb.py`), which is almost certainly an undercount — the markers
  only exist where someone remembered to leave one.

The remaining work is the 3.0.0 half above. The documentation half is done: the fix was a sentence
at each site rather than new documents, and the sites were the ones a reader actually stands on —
`env`'s class docstring and its `features.md` section for the import gotcha, `amb.forall` and
`assignonce` docstrings for "prefer the other thing", `macros.md` for `prefix` being experimental
and for the `q`/`u` collision, and `macros.md`'s Sequencing section for `begin`/`begin0`.

Worth keeping as the lesson: in every one of these the caveat either existed somewhere already
(`prefix`'s module docstring, `begin`'s `CAUTION`, `design-notes.md` on `amb`) or was implied by an
example nobody would read as a warning. The gap was never that the author did not know — it was that
the note was not on the path the reader takes. Note the audience is not only human: an agent reading
the library through `help()` or an API inventory sees exactly the docstring, and nothing else.

Raised 2026-08-16, documentation half resolved the same day.

## Should `runtests.py` clear the bytecode caches?

`unpythonic`'s `runtests.py` does no cache clearing. `mcpyrate`'s does, via
`runtests(clear_bytecode_cache=True)` calling `mcpyrate.pycachecleaner.deletepycachedirs`, so the
mechanism is already available to import.

The argument for adopting it: with a warm cache the expander does not run, so any test whose subject
is *expansion-time* behaviour silently tests nothing. That is not hypothetical — checking both
projects for AST-constructor deprecations under `-W error::DeprecationWarning` required clearing the
caches by hand first, and a run without that step proves nothing while looking identical.

The argument against: re-expanding everything roughly doubles the suite's runtime, and the common
case is a developer re-running tests after touching one runtime-level function, where expansion
genuinely has not changed.

So the decision needs a measurement (how much is "roughly doubles", actually?) and a choice of
default — always clear, clear only in CI, or a flag defaulting to off with the reason documented at
the call site. Note that whichever way it goes, a suite that *can* skip expansion needs to say so in
its output the way `mcpyrate`'s does ("Using existing bytecode"), because the failure is invisible
otherwise.

Discovered during the Python 3.15 AST survey (2026-08-16).
