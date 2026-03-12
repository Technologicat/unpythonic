# Deferred Issues

Next unused item code: D8

- **D5**: `typecheck.py` / `dispatch.py` — parametric forms of existing one-trick ponies (e.g. `Iterator[int]`, `Iterable[str]`) raise `NotImplementedError`. The bare forms work. The `NotImplementedError` is arguably correct fail-fast behavior, since ignoring the type arg would silently accept wrong element types and make dispatching on e.g. `Iterable[int]` vs. `Iterable[float]` silently misroute. Same situation already exists for `Callable`, `Generator`, `ContextManager`, and async types. Possible improvements (dispatch layer, not typecheck):
  - Emit a warning when a type arg is silently ignored during dispatch.
  - Raise `TypeError` when registering indistinguishable multimethods (e.g. `Iterable[int]` then `Iterable[float]`).
  (Discovered during D4 Set 2 work.)

