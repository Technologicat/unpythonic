# CC Brief: Monad subpackage for unpythonic

## Goal

Port the teaching-code monads from `~/Documents/python-opetus-2017/examples/monads.py` into unpythonic as a new subpackage `unpythonic.monads`, plus a `with monadic_do(M):` macro in `unpythonic.syntax`. Adapt to fit unpythonic idioms; do not import to top-level (subpackage-only access, similar to how `from unpythonic.env import env` is the standard import for `env`).

Resolves deferred item D13.

## Reference

- Source: `~/Documents/python-opetus-2017/examples/monads.py` (1521 lines, 6 monads + helpers)
- Existing precedent: `unpythonic/amb.py` (`MonadicList`, `forall`, `choice`, `insist`, `deny`)
- Existing macro precedent: `unpythonic/syntax/forall.py`
- mcpyrate `ASTMarker` for tracking processed AST nodes (see mcpyrate's source/docs and `unpythonic.syntax.tailtools` for usage examples)
- `unpythonic.syntax.letdoutil` — binding parser/destructurer (already understands modern `[x := mx, y := my(x)]` and discordian-deprecated `[x << mx, y << my(x)]`; we reuse it for **parsing only**, not for runtime expansion)
- `unpythonic.llist.nil` — singleton used in place of a new `Empty` sentinel (see List monad below)
- `unpythonic.slicing.Sliced` — model for the ABC-with-inheritance pattern we'll use for `Monad`

## Design decisions (all confirmed in pre-build discussion)

### Subpackage layout

```
unpythonic/monads/
├── __init__.py     # re-exports public API of subpackage; NOT re-exported at top level
├── abc.py          # Monad Protocol (runtime-checkable, structural)
├── core.py         # liftm, liftm2, liftm3 (no function-form do-notation; punted)
├── identity.py
├── maybe.py
├── either.py       # NEW (parallel to Maybe, carrying error value)
├── list.py         # the new home of MonadicList → renamed List
├── writer.py
├── state.py
├── reader.py
└── tests/
    └── test_*.py

unpythonic/syntax/monadic_do.py            # `with monadic_do(M) as result:` macro
unpythonic/syntax/tests/test_monadic_do.py
```

The top-level `unpythonic/__init__.py` does **not** star-import from `monads`. Users write `from unpythonic.monads import Maybe, Either, ...` explicitly. This is an exception to the usual top-level re-export convention; it mirrors how `from unpythonic.env import env` is the standard import path for `env`. Composition with the rest of unpythonic is fine — see "Integration tests" below.

### Seven monads

`Identity`, `Maybe`, `Either`, `List`, `Writer`, `State`, `Reader`. `Either` is added beyond the teaching code (natural complement to `Maybe`, carrying an error value). Faithful ports otherwise — minor adaptations to unpythonic style, no behavior changes intended.

### Bind / sequence spelling

- Bind: `>>` (Python's `>>=` is `__irshift__`, in-place, can't chain)
- Sequence: `.then(other_monad)`
- Unit: the class constructor itself (so `Identity(x)`, `Maybe(x)`, `List(x)` are units)

These match the teaching code; keep.

### `Monad` ABC, `LiftableMonad(Monad)` ABC

Real ABCs with inheritance, modeled on `unpythonic.slicing.Sliced`. Two-level split because `lift` (`f: a -> b → a -> M b`) doesn't make sense for every monad — `State.lift` and `Reader.lift` are not implementable in the obvious way (the teaching code's `State.lift` raises `NotImplementedError`, `Reader.lift` is missing).

**`Monad` (base ABC)** — required for all monads:

- `__init__` (unit) — `@abstractmethod`
- `fmap(self, f)` — `@abstractmethod`
- `join(self)` — `@abstractmethod`

Default (non-abstract) implementations:
- `__rshift__(self, f)` (bind) = `self.fmap(f).join()` — override only for efficiency (e.g., `Writer` overrides to avoid double-logging)
- `then(self, f)` = `self >> (lambda _: f)` — override usually unnecessary

**`LiftableMonad(Monad)`** — adds `lift` for monads where it makes sense:

- `lift(cls, f)` = `lambda x: cls(f(x))` — default classmethod; subclasses may override

Membership:
- `LiftableMonad`: `Identity`, `Maybe`, `Either`, `List`, `Writer`
- `Monad` directly (no lift): `State`, `Reader`

**Docstrings** make clear for each method whether it's `@abstractmethod` (must override), has a default implementation (override is optional, usually for efficiency), or is a final concrete method.

Lives in `unpythonic/monads/abc.py`. Whether these also dispatch into the new D4/D5 typecheck layer is a follow-up — flag in TODO_DEFERRED if deeper integration looks valuable after the basic port lands.

### State.join — fill in during port

The teaching code's `State.join` is a TODO-punt (raises `NotImplementedError`), not a fundamental obstacle. The standard Haskell definition (`join mm = State $ \s -> let (m, s') = runState mm s in runState m s'`) ports cleanly to Python. Implement it during the port. State is a proper monad with a well-defined join; no `JoinableMonad` split is needed.

**Docstring / code comment** for `State.join` should explain the operation in plain words, since the abstract definition is dense:

> Given `mm : State(s -> (State(s -> (a, s)), s))`, run the outer state function to get `(inner_m, s')`, then run the inner with `s'` — standard "thread the state" pattern.

Reader's `join` already works in the teaching code — only `lift` is missing, which `LiftableMonad` already handles.

### `MonadicList` migration

- Move the implementation to `unpythonic/monads/list.py`, renamed `List`.
- Add back the **varargs constructor** (`List(1, 2, 3)`) we reviewed-and-removed from `MonadicList` recently — turns out monadic-list ergonomics specifically need it, because monadic `unit` is then literally the class (`List(x)` = singleton list containing `x`).
- Use `nil` from `unpythonic.llist` in place of a fresh `Empty` sentinel (avoid proliferating singletons).
- Keep all the richer protocol from `MonadicList`: full `Sequence` ABC interface (`__len__`, `__eq__`, `__contains__`, `__reversed__`, `index`, `count`, ABC registration), type annotations.
- `unpythonic.amb.MonadicList` becomes a silent alias of `unpythonic.monads.List` (no `DeprecationWarning` on import — gentle path).
- Add a `# TODO(3.0.0): remove MonadicList alias` comment at the alias site.
- Add a `TODO_DEFERRED.md` entry tracking the alias removal for 3.0.0.

### Do-notation: macro only

No function-form `monadic_do`. The eval-based codegen approach in `amb.forall` is the cautionary tale we shouldn't repeat. Macro can do the same job cleanly via AST rewriting. Users who don't want do-notation just use `>>` chains directly with any monad.

### Macro syntax

```python
with monadic_do(Maybe) as result:
    [x := mx,
     y := my(x)] in
    result << M.unit(x + y)
```

Cultural note: `let-in` is arguably the only correct syntax for monadic do, since this whole tradition is Haskell.

**Body shape**: a single `Expr` statement whose `.value` is a `Compare` with `In` op. LHS is a `List` of `NamedExpr` bindings. RHS is `BinOp(LShift, Name('result'), final_monadic_expr)`.

**Bindings**: `:=` is the modern operator; `<<` is supported as a discordian-deprecated alternative (`letdoutil` already understands both — we reuse). Sequencing-only lines (Haskell `do { mx; ... }` using `>>` not `>>=`) are spelled `_ := mexpr`. The throwaway `_` makes intent visible in teaching contexts.

**Empty bindings**: `[] in result << M.unit(x)` is supported. Reduces beautifully as `len(bindings) → 0`.

**Strict RHS**: must be `result << expr` (the `as result` name on the LHS, `<<` on the RHS). Anything else is a macro-time error. Strict because `<<` makes data flow visible and matches the `with ... as result` declaration.

**Why `<<` on the RHS instead of `return`**: `return` at the top level of a `with` breaks reader expectations (usually exits the surrounding function). The "send to box" idiom (`result << expr`) is what unpythonic uses elsewhere (e.g., conditions/restarts subsystem) for this same problem.

**Xmas-tree placement**: `monadic_do` is always the innermost `with`.

```python
# xmas-tree macros (any combination thereof)
with prefix, autoreturn, quicklambda, multilambda, envify, lazify, namedlambda, autoref, autocurry, tco:
    with monadic_do(M) as result:
        [x := mx, y := my(x)] in result << M.unit(x + y)
```

**Rationale — forced and correct:**

The "innermost" position is both *forced* (by body shape) and *correct* (edit order works out):

- **Forced**: `monadic_do`'s body must be a single `Expr` statement of the form `[bindings] in result << expr`. It syntactically *cannot* contain `with X:` statements, so lexically wrapping anything else inside a `monadic_do` block is impossible by construction.

- **Correct**: two-pass macros (`lazify`, `tco`, `continuations`, `autocurry`, `envify`, `namedlambda`, `autoref`) do their first pass, then explicitly expand inner macros via `dyn._macro_expander.visit_recursively(body)`, then their second pass. `monadic_do` (one-pass outside-in) fires during the outer macro's `visit_recursively`, producing the bind chain. The outer macro's second pass then edits the expanded chain — exactly the order we want (autocurry curries the calls, lazify force-wraps references, tco optimizes tails, CPS transforms for continuations). One-pass outside-in surface-syntax macros (`prefix`, `autoreturn`, `quicklambda`, `multilambda`) normalize their body before descending, so `monadic_do` sees normal Python when it fires.

**Always in its own nested `with`** — unlike the other xmas-tree macros which chain in one `with` for brevity, `monadic_do(M) as result` has both an argument and an `as` binding, making same-`with` chaining syntactically awkward. Call this out explicitly in the macro's docstring.

**Dialects**: the same analysis applies transparently. Dialects (e.g., Lispython) wrap a module in block macros at parse-assembly time; `monadic_do` sits innermost within whatever the dialect adds. No dialect-specific integration testing is prioritized — the generic integration tests cover the same underlying macros.

**Expansion**: the whole `with` is rewritten away into nested lambda binds:

```python
result = mx >> (lambda x: my(x) >> (lambda y: M.unit(x + y)))
```

The `with monadic_do(M) as result:` is purely syntactic — `monadic_do(M)` is never called at runtime. Same pattern as `with continuations:`, `with autocurry:`, `with lazify:`.

**Implementation pattern**:
- mcpyrate visitor that processes `with monadic_do(...)` statements
- `letdoutil` (`UnexpandedLetView` and friends) to parse/destructure the bindings list — **parsing only**; no env-based runtime is involved
- Expansion target is plain nested lambdas. Each `x := mx` becomes `mx >> (lambda x: <rest>)`. Python's lexical scoping handles name shadowing in nested lambdas correctly — no `env` runtime needed.
- `ASTMarker` to mark rewritten nodes during expansion
- Require single-statement body; helpful error message if violated

### Lazify interaction — analysis (no special handling expected)

Verified by reading `lazify.py` source and tests:

1. Lazify computes `userlambdas = detect_lambda(body)` in its **first** (outside-in) pass, then expands inner macros via `dyn._macro_expander.visit_recursively(body)`. The lambdas `monadic_do` produces during that expansion have node ids *not* in `userlambdas` → lazify treats them as macro-introduced and skips the `passthrough_lazy_args` wrapping. It still recurses into the lambda body, applying normal force/lazyrec on references and call args.
2. The bind-chain expansion `mx >> (lambda x: my(x) >> (lambda y: ...))` provides natural deferral via lambda boundaries — `my(x)` is inside the lambda body, only invoked when the first bind fires. No extra `lazy[]` wrapping adds anything for nested bindings.
3. The first binding's RHS has to be evaluated to produce the receiver of `>>` anyway — wrapping it in `lazy[]` and immediately needing to call `__rshift__` on it (which `Lazy` doesn't have) would just need a `force()` to undo, net no-op.
4. References to outer-scope names get auto-`force()`'d in Load context (existing lazify behavior on `Name` nodes), so a `lazy_var` from surrounding scope gets unwrapped before being used as a `>>` receiver.

**Short-circuit preservation (the real concern)**: for monads like `Maybe` and `Either` that short-circuit on the failure path, bindings after the short-circuit point must *not* be forced. This holds automatically because:

- The macro puts later bindings *inside* lambda bodies (`leftM >> (lambda x: rightM >> (lambda y: ...))`)
- `rightM` becomes a Load-context Name, so lazify wraps it as `force(rightM)` — but that wrapping is itself inside the lambda body
- When `leftM` is `Left(err)` (or `Maybe(Empty)`), `__rshift__` returns `self` without invoking the passed lambda → the `force(rightM)` is never reached

This is the guarantee that would break if we got the macro expansion wrong — e.g., by hoisting binding RHSs to an outer scope for "efficiency." Don't. **A dedicated integration test pins this down**: a `Maybe`/`Either` do-block inside `with lazify`, where a later binding RHS contains an observable side effect (e.g., `nonlocal counter; counter += 1; return M.unit(42)`) or would raise (`1/0`). Trigger the short-circuit path. Assert the side effect didn't happen / no exception raised.

**Conclusion**: `monadic_do` should require no macro-side intervention to compose with `with lazify`. The integration test and the short-circuit test verify the contract. If either fails, revisit and consider explicit lazy-marking via `letdoutil` or directly in the macro.

## Test plan

- `monads/tests/test_*.py` — one file per monad, exercising unit, bind, sequence, fmap, join, guard, lift; classical examples (sqrt chain for Maybe, multivalued sqrt for List, Pythagorean triples for List, log accumulation for Writer, state-passing counter for State, env-reading for Reader, Either left/right paths)
- `monads/tests/test_core.py` — `liftm`, `liftm2`, `liftm3`; `Monad` Protocol structural check
- `monads/tests/test_abc.py` — `isinstance(x, Monad)` works for all seven monads (via inheritance), fails for non-monads; default `then`/`__rshift__` from the ABC actually fire
- `syntax/tests/test_monadic_do.py` — macro tests: each monad through do-notation; `:=` and `<<` both accepted; `_ := mexpr` sequencing; empty bindings; strict-RHS error case; nested do-blocks; the Pythagorean-triples canonical test
- `tests/test_amb.py` — confirm the `MonadicList` alias still works (existing tests should pass unchanged)

All tests use the `unpythonic.test.fixtures` framework (`test[]`, `test_raises[]`). Use `the[]` **only when the default auto-capture (LHS of a comparison) is not what we want** — e.g., to capture a container instead of a leaf, or to capture multiple subexpressions, or in non-comparison assertions.

### Integration tests (separate module, e.g. `syntax/tests/test_monadic_do_integration.py`)

`monadic_do` shouldn't fall apart when nested inside other unpythonic block macros. Use one nested `with` per outer macro (no chaining in the same `with` per `doc/macros.md`). Xmas-tree ordering applies — `monadic_do` is the inner block in all combinations.

**Must test**:
- `with continuations:` — bind chain inside a continuations block
- `with autocurry:` — autocurry shouldn't munge the bind chain (`__rshift__` is a method call, but `>>` operator uses dunder dispatch — should be transparent)
- `with lazify:` — **especially important** (Haskellism; see "Lazify interaction" above for the analysis)
- `with tco:` — deep do-blocks produce a lambda tower that ends in tail calls to `>>`; verify no stack issues, or document that TCO doesn't reach into bind chains

**Smoke test** (verify "doesn't crash", may interact in interesting ways):
- `with multilambda:` — `lambda: [a, b, c]` semantics could appear inside the body
- `with quicklambda:` — `f[...]` shorthand might appear in user expressions
- `with namedlambda:` — automatic naming of macro-introduced lambdas
- `with autoreturn:` — interaction with the `result << expr` exit pattern (`autoreturn` may try to inject `return` somewhere awkward)

**Likely orthogonal but smoke test for safety**:
- `with envify:`
- `with autoref:`

**Low priority (decide after smoke test)**:
- `with prefix:` — Listhell-specific. If the monads happen to work with it, nice; if not, not a priority. Smoke-test, see what happens, then decide whether to spend effort on interop.

If any combination needs real interaction work beyond "doesn't crash," flag in `TODO_DEFERRED.md` rather than expanding scope here.

## Out of scope

- Free monads, monad transformers, applicative-only structures
- IO monad (Python is impure already; no value-add)
- Continuation monad (we already have `with continuations:` — strictly more powerful)
- Deeper `@generic` / D4/D5 typecheck integration for `Monad` Protocol — flag for follow-up if the basic port suggests it would pay off
- Performance: faithful port; no optimization pass

## Order of work

1. `monads/abc.py` — `Monad` ABC (model on `unpythonic.slicing.Sliced`)
2. `monads/core.py` — `liftm`, `liftm2`, `liftm3`
3. `monads/identity.py` — simplest, sets the per-monad pattern
4. `monads/maybe.py`, `monads/either.py` — error handling pair
5. `monads/list.py` — port `MonadicList`, rename, varargs constructor, `nil` sentinel
6. `amb.py` — alias `MonadicList = unpythonic.monads.List`, TODO comment, TODO_DEFERRED entry
7. `monads/writer.py`, `monads/state.py`, `monads/reader.py`
8. `monads/__init__.py` — re-exports
9. Tests for the pure-Python layer (one per monad, plus core/abc)
10. `syntax/monadic_do.py` — the macro
11. Tests for the macro
12. **Pytkell dialect example update** — add monad usage examples to `unpythonic/dialects/tests/test_pytkell.py` (Pytkell is the Haskell-flavored joke dialect; no kell is complete without its monads). Faithful Haskell-do feel: at minimum show `Maybe`-chained sqrt, `List`-based Pythagorean triples, and `Writer`-based logging — all via `with monadic_do(M):`.
13. **Documentation**:
    - `doc/features.md` — document the new pure-Python API surface: `Monad` and `LiftableMonad` ABCs, the seven monads (`Identity`, `Maybe`, `Either`, `List`, `Writer`, `State`, `Reader`), `liftm`/`liftm2`/`liftm3`. Match the existing section style (brief intro, usage example, method reference where relevant).
    - `doc/macros.md` — document the `with monadic_do(M) as result:` macro: the binding syntax (`:=` and `<<`), the `result << expr` exit pattern, the always-own-`with` convention, the xmas-tree placement between `multilambda` and `envify`. Match the existing macro documentation style.
    - `README.md` — a short usage example in the style of the existing ones (likely a `Maybe`-chained computation or `List`-based Pythagorean triples, with enough prose to show the flavor without bloating the README).
    - `CHANGELOG.md`, `AUTHORS.md` as applicable.

Each significant step a separate commit. Don't mix the pure-Python port with the macro work — clean bisect boundaries.

## Conventions reminder

- `__all__` per module, ordered to mirror file order
- Type annotations on all new code
- reStructuredText docstrings, ~110 char line width
- `from ... import ...` style, no renaming with `as`
- Bind = `>>`, sequence = `.then`, unit = constructor
- `nil` (from `unpythonic.llist`) for empty-list sentinel in the List monad
- `:=` is primary bind syntax in macro; `<<` accepted as discordian-deprecated alternative
