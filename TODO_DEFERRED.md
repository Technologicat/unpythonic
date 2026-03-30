# Deferred Issues

Next unused item code: D9

- **D5**: `dispatch.py` — moved to GitHub issue #99. Dispatch-layer improvements for parametric ABCs (warn/error on indistinguishable multimethods). Typecheck-layer part resolved.


- **D8: Audit typing: abstract parameter types, concrete return types**: Parameters should use abstract types from `collections.abc` (`Mapping`, `Sequence`, `Iterable`) for widest-possible-accepted semantics. Return types should use concrete lowercase builtins (`tuple[int, int]`, `list[int]`, `dict[str, int]`) — PEP 585, Python 3.9+. The capitalized `typing` forms (`Dict`, `List`, `Tuple`) are deprecated aliases for the builtins and offer no extra width — avoid them. Audit existing type hints across the codebase for consistency. (Discovered during raven-cherrypick compare mode planning, 2026-03-30.)
