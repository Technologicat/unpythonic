# Deferred Issues

Next unused item code: D8

- **D4**: `typecheck.py` — expand runtime type checker to support more `typing` features.

  **Set 1 — Easy wins**: DONE (`665cc4b`)
  **Set 2 — Useful for dispatch**: DONE (this commit)
  - `NamedTuple`: specific subclasses already work via `isinstance` fallback; no special handling needed.
  **Dispatch integration tests** for Sets 1 and 2: DONE (this commit)

  **Set 3 — Hard / questionable value** (defer or discuss):
  - `Protocol` — full structural subtyping, heavy
  - `TypedDict` — required vs. optional keys, medium-hard
  - `Generic` — abstract, unclear semantics for value checking
  - `ForwardRef` — needs a namespace to resolve the string

- **D5**: `typecheck.py` / `dispatch.py` — parametric forms of existing one-trick ponies (e.g. `Iterator[int]`, `Iterable[str]`) raise `NotImplementedError`. The bare forms work. The `NotImplementedError` is arguably correct fail-fast behavior, since ignoring the type arg would silently accept wrong element types and make dispatching on e.g. `Iterable[int]` vs. `Iterable[float]` silently misroute. Same situation already exists for `Callable`, `Generator`, `ContextManager`, and async types. Possible improvements (dispatch layer, not typecheck):
  - Emit a warning when a type arg is silently ignored during dispatch.
  - Raise `TypeError` when registering indistinguishable multimethods (e.g. `Iterable[int]` then `Iterable[float]`).
  (Discovered during D4 Set 2 work.)

- **D7**: `doc/features.md` — the `isoftype` section needs updating: add examples for new typing features (D4 Sets 1+2), remove stale Python 3.6–3.9 CAUTION, add a note that this is a non-destructive runtime typechecker (which limits what it can check — e.g. element types of iterators, arg/return types of callables). Also consider noting this in the `@generic` docstring. (Discovered during D4 work.)

