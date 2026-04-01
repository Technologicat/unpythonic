# unpythonic Phase 1 Audit Report — Python 3.10–3.14 Modernization

**Date:** 2026-03-11
**Scope:** Audit for Python 3.10–3.14 support (version 2.0.0), mcpyrate 4.0.0 dependency

## Summary

| Category | Count | Will break | Will warn | Cleanup only |
|----------|------:|:----------:|:---------:|:------------:|
| mcpyrate 4.0.0 breakage | 21 | 21 | — | — |
| 3.13 compat (`hasattr`) | 8 | 2 | — | 6 |
| 3.13 compat (AST constructors) | 2 | — | 2 | — |
| Floor bump cleanup (`sys.version_info`) | 18 | — | — | 18 |
| Feature gap (`autoreturn` + match/case) | 1 | — | — | 1 |
| Direct AST ref in string | 1 | — | — | 1 |
| Version metadata | 15+ | — | — | 15+ |
| TODOs now actionable | 20+ | — | — | 20+ |

---

## 1. `unpythonic/syntax/lambdatools.py`

| Line | Issue | Category | Severity |
|-----:|-------|----------|----------|
| 17 | Imports `getconstant`, `Str` from `mcpyrate.astcompat` — both removed in 4.0.0 | mcpyrate 4.0.0 breakage | **will break** |
| 371 | `type(k) in (Constant, Str)` — collapse to `type(k) is Constant` | mcpyrate 4.0.0 breakage | **will break** |
| 372 | `getconstant(k)` — replace with `k.value` | mcpyrate 4.0.0 breakage | **will break** |
| 403 | `if hasattr(tree, "lineno"):` on Lambda AST node — always True in 3.13; creates name like `"<lambda at file.py:None>"` for macro-generated lambdas | 3.13 compat | cleanup (cosmetic) |
| 454 | `if hasattr(a, "posonlyargs"):` — version check for 3.8+ `arguments` field; always True at floor 3.10 but harmless | floor bump cleanup | cleanup only |
| 539 | `tree.ctx if hasattr(tree, "ctx") else None` — safe by accident in 3.13 (macro nodes get `ctx=None`, result is the same) | 3.13 compat | cleanup (safe) |

## 2. `unpythonic/syntax/letdoutil.py`

| Line | Issue | Category | Severity |
|-----:|-------|----------|----------|
| 14 | Imports `getconstant`, `Str` from `mcpyrate.astcompat` — both removed in 4.0.0 | mcpyrate 4.0.0 breakage | **will break** |
| 25 | `if sys.version_info >= (3, 9, 0):` — `ast.Index` wrapper removal; always true | floor bump cleanup | cleanup only |
| 30 | `if sys.version_info >= (3, 9, 0):` — same, setter variant | floor bump cleanup | cleanup only |
| 186 | `type(mode[0]) in (Constant, Str)` — collapse to `type(mode[0]) is Constant` | mcpyrate 4.0.0 breakage | **will break** |
| 187 | `getconstant(mode[0])` — replace with `mode[0].value` | mcpyrate 4.0.0 breakage | **will break** |
| 731 | `type(newk) not in (Constant, Str)` — collapse to `type(newk) is not Constant` | mcpyrate 4.0.0 breakage | **will break** |
| 732 | Error message string mentions `ast.Str` — update for accuracy | direct AST ref | cleanup only |
| 744 | `getconstant(newk)` — replace with `newk.value` | mcpyrate 4.0.0 breakage | **will break** |
| 763 | `if hasattr(oldb, "lineno") and hasattr(oldb, "col_offset"):` — always True in 3.13; passes `None` values to `Tuple()` constructor instead of letting mcpyrate fix them | 3.13 compat | **will break** |

## 3. `unpythonic/syntax/tailtools.py`

| Line | Issue | Category | Severity |
|-----:|-------|----------|----------|
| 25 | Imports `getconstant`, `NameConstant` from `mcpyrate.astcompat` — both removed in 4.0.0 | mcpyrate 4.0.0 breakage | **will break** |
| 685–716 | `autoreturn`'s `TailStatementTransformer` does not handle `ast.Match` (match/case). With floor at 3.10, match/case is always available. | feature gap | cleanup only |
| 1038 | `type(theexpr) in (Constant, NameConstant) and getconstant(theexpr) is None` — collapse to `type(theexpr) is Constant and theexpr.value is None` | mcpyrate 4.0.0 breakage | **will break** |
| 1043 | Same pattern as 1038 but on `tree` | mcpyrate 4.0.0 breakage | **will break** |
| 1112–1119 | `arguments()` constructor omits `posonlyargs`; adds it conditionally after. In 3.13, omitting required fields emits DeprecationWarning (error in 3.15) | 3.13 compat (constructors) | **will warn** |
| 1118 | `if sys.version_info >= (3, 8, 0):` — always true at floor 3.10 | floor bump cleanup | cleanup only |

## 4. `unpythonic/syntax/autoref.py`

| Line | Issue | Category | Severity |
|-----:|-------|----------|----------|
| 12 | Imports `getconstant` from `mcpyrate.astcompat` — removed in 4.0.0 | mcpyrate 4.0.0 breakage | **will break** |
| 237 | `getconstant(get_resolver_list(tree)[-1])` — replace with `.value` | mcpyrate 4.0.0 breakage | **will break** |

## 5. `unpythonic/syntax/util.py`

| Line | Issue | Category | Severity |
|-----:|-------|----------|----------|
| 21 | Imports `getconstant` from `mcpyrate.astcompat` — removed in 4.0.0 | mcpyrate 4.0.0 breakage | **will break** |
| 358 | `getconstant(tree.test)` inside try/except — replace with `tree.test.value` (guard `type(tree.test) is Constant` first) | mcpyrate 4.0.0 breakage | **will break** |

## 6. `unpythonic/syntax/letdo.py`

| Line | Issue | Category | Severity |
|-----:|-------|----------|----------|
| 478 | `hasctx = hasattr(tree, "ctx")` — in 3.13, always True; macro-created nodes get `ctx=None`, so `type(None) is not Load` → True → incorrect early return. **Breaks let-binding envify.** | 3.13 compat | **will break** |
| 593–596 | `arguments()` constructor omits `posonlyargs`; adds it conditionally. DeprecationWarning in 3.13, error in 3.15 | 3.13 compat (constructors) | **will warn** |
| 595 | `if sys.version_info >= (3, 8, 0):` — always true at floor 3.10 | floor bump cleanup | cleanup only |

## 7. `unpythonic/syntax/scopeanalyzer.py`

| Line | Issue | Category | Severity |
|-----:|-------|----------|----------|
| 389 | `hasattr(tree, "ctx") and type(tree.ctx) is Store` — hasattr always True in 3.13; works by accident (`type(None) is Store` → False) but fragile | 3.13 compat | cleanup (fragile) |
| 411 | `hasattr(tree, "ctx") and type(tree.ctx) is Del` — same as above | 3.13 compat | cleanup (fragile) |
| 428 | `if hasattr(a, "posonlyargs"):` — always True at floor 3.10 | floor bump cleanup | cleanup only |

## 8. `unpythonic/syntax/testingtools.py`

| Line | Issue | Category | Severity |
|-----:|-------|----------|----------|
| 803 | `q[u[tree.lineno]] if hasattr(tree, "lineno") else q[None]` — safe in 3.13 (gets `None` either way) | 3.13 compat | cleanup (safe) |
| 883 | `if sys.version_info >= (3, 9, 0):` — `ast.Index` wrapper; always true | floor bump cleanup | cleanup only |
| 904 | Same safe `hasattr` lineno pattern as 803 | 3.13 compat | cleanup (safe) |
| 941 | Same safe `hasattr` lineno pattern on `first_stmt` | 3.13 compat | cleanup (safe) |
| 1013 | Same safe `hasattr` lineno pattern on `first_stmt` | 3.13 compat | cleanup (safe) |

## 9. `unpythonic/syntax/dbg.py`

| Line | Issue | Category | Severity |
|-----:|-------|----------|----------|
| 229 | `tree.lineno if hasattr(tree, "lineno") else None` — safe in 3.13 | 3.13 compat | cleanup (safe) |
| 240 | `q[u[tree.lineno]] if hasattr(tree, "lineno") else q[None]` — safe in 3.13 | 3.13 compat | cleanup (safe) |

## 10. `unpythonic/syntax/letsyntax.py`

| Line | Issue | Category | Severity |
|-----:|-------|----------|----------|
| 372 | `if sys.version_info >= (3, 9, 0):` — `ast.Index` wrapper; always true | floor bump cleanup | cleanup only |

## 11. `unpythonic/syntax/prefix.py`

| Line | Issue | Category | Severity |
|-----:|-------|----------|----------|
| 197 | `if sys.version_info >= (3, 9, 0):` — `ast.Index` wrapper; always true | floor bump cleanup | cleanup only |

## 12. `unpythonic/syntax/nameutil.py`

| Line | Issue | Category | Severity |
|-----:|-------|----------|----------|
| 127 | `if sys.version_info >= (3, 9, 0):` — `ast.Index` wrapper; always true | floor bump cleanup | cleanup only |

## 13. `unpythonic/syntax/tests/test_letdoutil.py`

| Line | Issue | Category | Severity |
|-----:|-------|----------|----------|
| 7 | Imports `getconstant`, `Num` from `mcpyrate.astcompat` — both removed in 4.0.0 | mcpyrate 4.0.0 breakage | **will break** |
| 253 | `type(the[view.value]) in (Constant, Num) and getconstant(view.value) == 42` — collapse type check, use `.value` | mcpyrate 4.0.0 breakage | **will break** |
| 259 | Same pattern, value 23 | mcpyrate 4.0.0 breakage | **will break** |
| 277 | Same pattern, value 42 | mcpyrate 4.0.0 breakage | **will break** |
| 283 | Same pattern, value 23 | mcpyrate 4.0.0 breakage | **will break** |
| 528 | Same pattern, variable value | mcpyrate 4.0.0 breakage | **will break** |
| 611, 624, 631, 650, 663, 670 | Six `if sys.version_info >= (3, 9, 0):` guards — `ast.Index` wrapper; always true | floor bump cleanup | cleanup only |

## 14. `unpythonic/syntax/tests/test_util.py`

| Line | Issue | Category | Severity |
|-----:|-------|----------|----------|
| 7 | Imports `getconstant`, `Num`, `Str` from `mcpyrate.astcompat` — all removed in 4.0.0 | mcpyrate 4.0.0 breakage | **will break** |
| 159 | `type(lam.body) in (Constant, Num)` — collapse to `type(lam.body) is Constant` | mcpyrate 4.0.0 breakage | **will break** |
| 160 | `getconstant(lam.body) == 42` — replace with `lam.body.value == 42` | mcpyrate 4.0.0 breakage | **will break** |
| 188 | `type(tree.value) in (Constant, Str)` — collapse | mcpyrate 4.0.0 breakage | **will break** |
| 189 | `getconstant(tree.value)` — replace with `tree.value.value` | mcpyrate 4.0.0 breakage | **will break** |
| 196 | `type(tree.value) in (Constant, Str) and getconstant(tree.value) == "hello"` — collapse and use `.value` | mcpyrate 4.0.0 breakage | **will break** |

## 15. `unpythonic/syntax/tests/test_conts_multishot.py`

| Line | Issue | Category | Severity |
|-----:|-------|----------|----------|
| 68 | `if hasattr(tree, "ctx") and type(tree.ctx) is not ast.Load:` — always True in 3.13; macro-created nodes get `ctx=None`, `type(None) is not Load` → True → incorrect early return | 3.13 compat | **will break** |
| 194 | `if sys.version_info >= (3, 9, 0):` — `ast.Index` wrapper; always true | floor bump cleanup | cleanup only |

## 16. `unpythonic/misc.py`

| Line | Issue | Category | Severity |
|-----:|-------|----------|----------|
| 109 | `if version_info >= (3, 8, 0):` — always true at floor 3.10; else branch uses fragile `CodeType()` positional construction | floor bump cleanup | cleanup only |

## 17. `unpythonic/typecheck.py`

| Line | Issue | Category | Severity |
|-----:|-------|----------|----------|
| 187 | `if sys.version_info >= (3, 10, 0):` — always true at floor 3.10; `isinstance(T, typing.NewType)` is the only path needed | floor bump cleanup | cleanup only |

## 18. `unpythonic/tests/test_fun.py`

| Line | Issue | Category | Severity |
|-----:|-------|----------|----------|
| 259 | `if sys.version_info < (3, 11, 0):` — always false at floor 3.10; entire block is dead code (uninspectable builtins test) | floor bump cleanup | cleanup only |

## 19. Dialect files (NOT affected by 3.13 AST change)

`lispython.py:45,82`, `listhell.py:29`, `pytkell.py:45` — all check `hasattr(self, "lineno")` on **Dialect instances**, not AST nodes. The mcpyrate 3.6.0+ compat check is unrelated to the 3.13 AST field change. **No action needed.**

---

## 20. `autoreturn` and `match`/`case` — Feature Gap Detail

`TailStatementTransformer` in `tailtools.py:685–716` handles:
- `If` → recurse into both branches
- `With`/`AsyncWith` → recurse into body
- `Try`/`TryStar` → recurse into else (or body if no else) + each except handler; skip finally
- `FunctionDef`/`AsyncFunctionDef`/`ClassDef` → append `return <name>`
- `Expr` → convert to `return expr`

**Missing:** `Match` (Python 3.10+ structural pattern matching). The handler would follow the same pattern — recurse into `case.body[-1]` for each `match_case`. Approximately 3–5 lines of code plus an `ast.Match` import. `scopeanalyzer.py` already handles match/case for scope analysis, so the infrastructure is in place.

There is also a TODO for `For`/`AsyncFor`/`While` at line 687, which is explicitly documented as intentionally unhandled (loops don't have a natural tail-position value).

---

## 21. Version Metadata

### Packaging

| File | Line | Current | Target |
|------|-----:|---------|--------|
| `pyproject.toml` | 7 | `requires-python = ">=3.8,<3.13"` | `">=3.10,<3.15"` |
| `pyproject.toml` | 22 | `"mcpyrate>=3.6.4"` | `"mcpyrate>=4.0.0"` |
| `pyproject.toml` | 29–40 | Classifiers for 3.8–3.12 | Remove 3.8, 3.9; add 3.13, 3.14 |
| `.pdm-build/pyproject.toml` | 7 | Same as above | Sync with main |
| `.pdm-build/pyproject.toml` | 38–42 | Same classifiers | Sync with main |

### CI

| File | Line | Current | Target |
|------|-----:|---------|--------|
| `.github/workflows/python-package.yml` | 20 | `["3.8", "3.9", "3.10", "3.11", "3.12", pypy-3.8, pypy-3.9, pypy-3.10]` | `["3.10", "3.11", "3.12", "3.13", "3.14", pypy-3.10]` |
| `.github/workflows/coverage.yml` | 18 | `["3.10"]` | Consider updating to `["3.12"]` or `["3.13"]` |

### Documentation

| File | Line(s) | What to update |
|------|---------|----------------|
| `CLAUDE.md` | 15, 19 | Version range mentions ("3.8–3.12", "1.1.0" plan → actual 2.0.0 state) |
| `README.md` | 20 | "CPython 3.8, 3.9 and 3.10, 3.11, 3.12, and PyPy3 (language versions 3.8, 3.9, 3.10)" |
| `CONTRIBUTING.md` | 121 | "main target platforms are CPython 3.8 and PyPy3 3.7" (very outdated) |
| `CHANGELOG.md` | — | Will need a 2.0.0 entry |

### Newly actionable TODOs (selected high-value items)

| File | Line | TODO |
|------|-----:|------|
| `syntax/letdoutil.py` | 200, 217, 500, 529 | "Python 3.9+: remove once we bump minimum Python to 3.9" — remove parens syntax for macro args |
| `syntax/letsyntax.py` | 331, 392, 448 | Same — remove parens syntax support |
| `syntax/letdo.py` | 931 | "Remove the parens when we bump minimum Python to 3.10" — walrus in subscripts |
| `syntax/tests/test_letdo.py` | 5, 31 | Switch macro args to brackets; remove parens |
| `syntax/tests/test_letdoutil.py` | 42 | Remove the parens |
| `syntax/tests/test_scopeanalyzer.py` | 17, 18 | "Add tests for match/case once we bump to 3.10" / "Add tests for try/except* once we bump to 3.11" — **both now actionable** |
| `syntax/__init__.py` | 84 | "Change decorator macro invocations to use [] instead of ()" — now actionable at floor 3.10 |

---

## Migration patterns

### `getconstant(node)` → `node.value`

```python
# Before
from mcpyrate.astcompat import getconstant
value = getconstant(tree.test)

# After
# Just access .value on the Constant node directly
value = tree.test.value
```

Where `getconstant` was called inside a try/except (e.g., `util.py:358`), guard with `type(node) is Constant` first.

### `type(x) in (Constant, Str/Num/NameConstant)` → `type(x) is Constant`

All legacy node types (`Str`, `Num`, `Bytes`, `NameConstant`, `Ellipsis`) have been unified into `ast.Constant` since Python 3.8. With floor at 3.10, only `Constant` exists.

### `hasattr(node, "field")` → `node.field is not None`

For optional AST fields that may be `None` on macro-generated nodes in 3.13:

```python
# Before
if hasattr(tree, "ctx"):
    ...use tree.ctx...

# After
if tree.ctx is not None:
    ...use tree.ctx...
```

### `arguments()` constructor — add `posonlyargs=[]`

```python
# Before
noargs = arguments(args=[], kwonlyargs=[], vararg=None, kwarg=None,
                   defaults=[], kw_defaults=[])

# After
noargs = arguments(args=[], kwonlyargs=[], vararg=None, kwarg=None,
                   defaults=[], kw_defaults=[], posonlyargs=[])
```
