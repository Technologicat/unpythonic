# CC Brief: unpythonic Modernization — Phase 1 (Audit)

## Context

unpythonic is being updated from Python 3.8–3.12 to 3.10–3.14. This follows the mcpyrate 4.0.0 update — unpythonic is mcpyrate's primary downstream consumer. Version will be 2.0.0 (floor bump + mcpyrate 4.0.0 dependency is breaking).

unpythonic has three tiers: pure Python layer (`unpythonic/`), macro layer (`unpythonic/syntax/`), and dialect layer (`unpythonic/dialects/`). The macro and dialect layers depend on mcpyrate. The pure Python layer has no mcpyrate dependency at runtime.

No code changes in this phase, only a report.

## Reference

- unpythonic CLAUDE.md (in repo root) — architecture, conventions.
- unpythonic issue #93: consolidated AST change notes (covers mcpyrate, unpythonic, Pyan3).
- mcpyrate 4.0.0 changelog: removed `getconstant()`, `Num`, `Str`, `Bytes`, `NameConstant`, `Ellipsis`, `Index`, `ExtSlice` from `astcompat` public API.
- mcpyrate 4.0.0 source tree: `~/Documents/koodit/mcpyrate/` — consult when you need to check what `astcompat` exports, how the unparser handles new nodes, or any other mcpyrate 4.0.0 API details.

## What to audit

### 1. Imports from mcpyrate.astcompat (mcpyrate 4.0.0 breakage)

mcpyrate 4.0.0 removed these from `astcompat`: `getconstant`, `Num`, `Str`, `Bytes`, `NameConstant`, `Ellipsis`, `Index`, `ExtSlice`.

**Find all imports from `mcpyrate.astcompat`** and flag any that reference removed names.

**Known instances** (verify — there may be more):
- `syntax/lambdatools.py`: imports `getconstant`, `Str`, `NamedExpr`
- `syntax/letdoutil.py`: imports `getconstant`, `Str`, `NamedExpr`
- `syntax/tailtools.py`: imports `getconstant`, `NameConstant`, `TryStar`
- `syntax/autoref.py`: imports `getconstant`
- `syntax/util.py`: imports `getconstant`
- `syntax/autocurry.py`: imports `TypeAlias` (still valid)
- `syntax/lazify.py`: imports `TypeAlias` (still valid)
- `syntax/scopeanalyzer.py`: imports `TryStar`, `MatchStar`, `MatchMapping`, `MatchClass`, `MatchAs` (still valid)
- `syntax/tests/test_letdoutil.py`: imports `getconstant`, `Num`
- `syntax/tests/test_util.py`: imports `getconstant`, `Num`, `Str`

For each removed import, find all usage sites in that file. Most will be type checks like `type(k) in (Constant, Str)` that collapse to `type(k) is Constant`, and `getconstant(node)` calls that become `node.value`.

### 2. `hasattr` checks on AST node fields (3.13)

In Python 3.13, omitted optional fields on AST nodes are set to `None` instead of being absent. Code that uses `hasattr(node, "field")` to detect absence will now always return `True`, breaking guards that relied on absence to detect "not set".

**Known instances** (scan for more):

**Dialect files:**
- `dialects/listhell.py` (~line 29): `if hasattr(self, "lineno"):`
- `dialects/lispython.py` (~lines 45, 82): `if hasattr(self, "lineno"):`
- `dialects/pytkell.py` (~line 45): `if hasattr(self, "lineno"):`

Note: these check `hasattr(self, "lineno")` on dialect classes, not directly on AST nodes. The comment says "mcpyrate 3.6.0+". Check whether `self` here is an AST node or a dialect instance — if it's a dialect instance, the 3.13 AST field change doesn't apply.

**Macro layer:**
- `syntax/testingtools.py` (~lines 803, 904, 941, 1013): `hasattr(tree, "lineno")` / `hasattr(first_stmt, "lineno")`
- `syntax/dbg.py` (~lines 229, 240): `hasattr(tree, "lineno")`
- `syntax/lambdatools.py` (~line 403): `if hasattr(tree, "lineno"):`
- `syntax/lambdatools.py` (~line 539): `tree.ctx if hasattr(tree, "ctx") else None`
- `syntax/scopeanalyzer.py` (~lines 389, 411): `hasattr(tree, "ctx") and type(tree.ctx) is Store/Del`
- `syntax/letdoutil.py` (~line 763): `hasattr(oldb, "lineno") and hasattr(oldb, "col_offset")`
- `syntax/letdo.py` (~line 478): `hasattr(tree, "ctx")`

**Tests:**
- `syntax/tests/test_conts_multishot.py` (~line 68): `hasattr(tree, "ctx")`

For `ctx` checks: these are likely checking whether a macro-generated node has had `ctx` set. In 3.13, `ctx` defaults to `Load()` on omission, so `hasattr` will always be `True` — but the node *does* have a meaningful `ctx` now (`Load()`). Determine whether this is a behavior change or harmless.

### 3. `sys.version_info` guards (floor bump cleanup)

With floor at 3.10, all `>= (3, 8)` and `>= (3, 9)` checks are always true. Find all and list.

**Known instances** (~14+ sites, mostly `ast.Index` wrapper removal):
- `syntax/testingtools.py` (~line 883): `>= (3, 9, 0)` — `ast.Index` wrapper
- `syntax/letsyntax.py` (~line 372): `>= (3, 9, 0)` — `ast.Index` wrapper
- `syntax/prefix.py` (~line 197): `>= (3, 9, 0)` — `ast.Index` wrapper
- `syntax/letdoutil.py` (~lines 25, 30): `>= (3, 9, 0)` — `ast.Index` wrapper
- `syntax/nameutil.py` (~line 127): `>= (3, 9, 0)` — `ast.Index` wrapper
- `syntax/letdo.py` (~line 595): `>= (3, 8, 0)` — positional-only args
- `syntax/tailtools.py` (~line 1118): `>= (3, 8, 0)` — positional-only args
- `syntax/tests/test_conts_multishot.py` (~line 194): `>= (3, 9, 0)` — `ast.Index`
- `syntax/tests/test_letdoutil.py` (~lines 611, 624, 631, 650, 663, 670): `>= (3, 9, 0)` — `ast.Index`
- `typecheck.py` (~line 187): `>= (3, 10, 0)` — `types.UnionType`. Always true with floor at 3.10.
- `tests/test_fun.py` (~line 259): `< (3, 11, 0)` — check what this guards

### 4. Direct references to deprecated/removed AST node types

Outside of `mcpyrate.astcompat` imports, check for any direct `ast.Num`, `ast.Str`, etc. references.

**Known instance:**
- `syntax/letdoutil.py` (~line 732): error message mentions `ast.Str` — just a string literal, but should be updated for accuracy.

### 5. `autoreturn` and `match`/`case` (feature gap from issue #93)

`autoreturn` in `syntax/tailtools.py` doesn't handle `match`/`case` statements. This is a known gap — it's a feature addition, not strictly a compat fix, but it's the most significant modernization issue identified in issue #93.

**Scope the work:** check how `autoreturn` handles other compound statements (`if`/`elif`/`else`, `try`/`except`, `with`). The `match`/`case` handler should follow the same pattern — autoreturn the last expression in each `case` body.

**Decision:** Include in 2.0.0. The 3.10 floor means `match`/`case` is always available, and the version bump is happening anyway. This is self-contained relative to the rest of the `autoreturn` machinery — the scary parts of unpythonic (TCO, lazify, autocurry, continuations) are not involved.

### 6. AST constructor calls (3.13 strictness)

In 3.13, omitting required fields or passing unknown kwargs on `ast.*` node constructors emits `DeprecationWarning` (becomes an error in 3.15). Scan for AST node constructor calls that omit required fields or pass unknown kwargs.

Focus on the macro layer (`syntax/*.py`) which constructs AST nodes extensively. The pure Python layer doesn't touch AST.

**Exception — `ctx` fields**: Many AST node constructors intentionally omit `ctx` — mcpyrate's `astfixers.fix_ctx()` auto-injects the correct `ctx` after macro expansion. In 3.13, omitted `ctx` defaults to `Load()`, which is harmless since `astfixers` overwrites it. Don't flag missing `ctx`.

### 7. Version metadata

- `pyproject.toml`: `python_requires`, classifiers, mcpyrate dependency version
- CI workflow: matrix versions, PyPy versions
- `CLAUDE.md`: version range mentions
- `README.md`: any version range mentions
- `CHANGELOG.md`: will need a 2.0.0 entry (not part of audit, just note)
- Module docstrings mentioning version ranges

## Deliverable

A report (markdown) listing all sites that need attention, grouped by file. For each site, note:
- File and line number
- What the issue is
- Category: mcpyrate 4.0.0 breakage / floor bump cleanup / 3.13 compat / 3.14 compat / feature gap
- Severity (will break / will warn / cleanup only)

No code changes.
