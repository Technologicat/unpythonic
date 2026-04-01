# CC Brief: unpythonic Modernization — Phases 2–5 (Implementation)

**Prerequisite**: Phase 1 audit report reviewed and approved. This brief incorporates its findings.

## Goal

Update unpythonic from Python 3.8–3.12 to 3.10–3.14. This is a **major version bump to 2.0.0** — floor bump + mcpyrate 4.0.0 dependency is breaking.

Four phases, each a separate commit (or small group of commits). Don't mix cleanup with compat work — we need clean bisect boundaries.

unpythonic has three tiers: pure Python layer, macro layer (`syntax/`), and dialect layer (`dialects/`). The macro layer is where almost all the work is. The pure Python layer has a few version guards to clean up. The dialect layer is clean (confirmed by audit).

## Reference

- Phase 1 audit report (attached/in context).
- unpythonic CLAUDE.md (in repo root) — architecture, conventions.
- unpythonic issue #93: consolidated AST change notes.
- mcpyrate 4.0.0 source tree: `~/Documents/koodit/mcpyrate/` — consult for current `astcompat` exports, API details.

---

## Phase 2: Floor bump to 3.10

Drop support for Python 3.8 and 3.9. Remove dead code paths and version guards. This is mechanical cleanup.

### `sys.version_info` guards — remove dead branches (18 sites)

All `>= (3, 8)` and `>= (3, 9)` guards are always true at floor 3.10. Delete the `else` branches and the conditionals, keeping only the true branch.

**`ast.Index` wrapper guards** (always true, `>= (3, 9)`):
- `syntax/letdoutil.py` lines ~25, ~30
- `syntax/letsyntax.py` line ~372
- `syntax/prefix.py` line ~197
- `syntax/testingtools.py` line ~883
- `syntax/nameutil.py` line ~127
- `syntax/tests/test_letdoutil.py` lines ~611, ~624, ~631, ~650, ~663, ~670
- `syntax/tests/test_conts_multishot.py` line ~194

**Positional-only args guards** (always true, `>= (3, 8)`):
- `syntax/tailtools.py` line ~1118
- `syntax/letdo.py` line ~595

**Other version guards:**
- `typecheck.py` line ~187: `>= (3, 10)` — `types.UnionType`. Always true, remove guard.
- `misc.py` line ~109: `>= (3, 8)` — `CodeType()` construction. Remove else branch with fragile positional construction.
- `tests/test_fun.py` line ~259: `< (3, 11)` — still needed (runs on 3.10 only). Leave as-is.

**`hasattr` version guards** (always true with floor 3.10, not 3.13-related):
- `syntax/lambdatools.py` line ~454: `hasattr(a, "posonlyargs")` — always true since 3.8. Remove guard.
- `syntax/scopeanalyzer.py` line ~428: `hasattr(a, "posonlyargs")` — same.

### Newly actionable TODOs — macro arg brackets

With the floor at 3.10+, the bracket syntax (`macro[args]`) for macro arguments is always available. The codebase has TODOs saying "remove parens syntax once we bump minimum Python." However, the parens branches are small (2–4 lines each) and keeping backward compat doesn't hurt. **Don't remove parens support.** Instead:

- **Verify** that the bracket syntax alternative works everywhere parens syntax is accepted. If it doesn't, that's a bug — fix it now.
- **Update tests** to prefer bracket syntax as the modern idiom. Keep at least one test per macro that exercises the parens syntax code path, with a comment like `# Test deprecated parens syntax (backward compat)`.
- **Update TODO comments** to say: "Parens syntax deprecated; kept for backward compatibility."

Sites with these TODOs:
- `syntax/letdoutil.py` lines ~200, ~217, ~500, ~529
- `syntax/letsyntax.py` lines ~331, ~392, ~448
- `syntax/letdo.py` line ~931: walrus in subscripts (requires 3.10)
- `syntax/__init__.py` line ~84: decorator macro invocations
- `syntax/tests/test_letdo.py` lines ~5, ~31
- `syntax/tests/test_letdoutil.py` line ~42

### Version metadata

**pyproject.toml:**
- Bump version to `2.0.0`
- `requires-python`: `">=3.8,<3.13"` → `">=3.10,<3.15"`
- `mcpyrate` dependency: `"mcpyrate>=3.6.4"` → `"mcpyrate>=4.0.0"`
- Classifiers: remove 3.8, 3.9; add 3.13, 3.14

**.pdm-build/pyproject.toml:** Sync all changes from main `pyproject.toml`.

**CI (.github/workflows/python-package.yml):**
- Matrix: `["3.10", "3.11", "3.12", "3.13", "3.14", "pypy-3.11"]` (remove 3.8, 3.9, pypy-3.8, pypy-3.9, pypy-3.10; add 3.13, 3.14, pypy-3.11)

**CI (.github/workflows/coverage.yml):**
- Update from `["3.10"]` to `["3.12"]`.

**Documentation:**
- `CLAUDE.md` lines ~15, ~19: update version range and release plan
- `README.md` line ~20: update supported versions
- `CONTRIBUTING.md` line ~121: "main target platforms are CPython 3.8 and PyPy3 3.7" — very outdated, update

---

## Phase 3: mcpyrate 4.0.0 adaptation

Replace all usage of APIs removed in mcpyrate 4.0.0. This is mechanical — the patterns are uniform.

### `getconstant()` → `.value` (10+ call sites)

`getconstant(node)` becomes `node.value`. Where `getconstant` was called inside a try/except or guard, use `type(node) is Constant` first.

**Sites:**
- `syntax/lambdatools.py` line ~372: `getconstant(k)` → `k.value`
- `syntax/letdoutil.py` lines ~187, ~744: `getconstant(mode[0])` → `mode[0].value`, `getconstant(newk)` → `newk.value`
- `syntax/tailtools.py` lines ~1038, ~1043: `getconstant(theexpr)` → `theexpr.value`
- `syntax/autoref.py` line ~237: `getconstant(...)` → `....value`
- `syntax/util.py` line ~358: `getconstant(tree.test)` → `tree.test.value` (guard with `type(tree.test) is Constant` first — currently in a try/except)
- `syntax/tests/test_letdoutil.py` lines ~253, ~259, ~277, ~283, ~528: `getconstant(view.value)` → use intermediate variable, **never `.value.value`**:
```python
node = view.value          # the AST Constant node
test[node.value == 42]     # the Python value inside it
```
- `syntax/tests/test_util.py` lines ~160, ~189, ~196: same pattern — use intermediate variable, **never `.value.value`**

### Removed type imports — collapse type checks (11 sites)

`Str`, `Num`, `NameConstant` are removed from `mcpyrate.astcompat`. All type checks like `type(x) in (Constant, Str)` collapse to `type(x) is Constant`.

**Update imports** — remove `Str`, `Num`, `NameConstant`, `getconstant` from all `from mcpyrate.astcompat import ...` lines:
- `syntax/lambdatools.py` line ~17: remove `getconstant`, `Str` (keep `NamedExpr`)
- `syntax/letdoutil.py` line ~14: remove `getconstant`, `Str` (keep `NamedExpr`)
- `syntax/tailtools.py` line ~25: remove `getconstant`, `NameConstant` (keep `TryStar`)
- `syntax/autoref.py` line ~12: remove entire `from mcpyrate.astcompat` import
- `syntax/util.py` line ~21: remove entire `from mcpyrate.astcompat` import
- `syntax/tests/test_letdoutil.py` line ~7: remove `getconstant`, `Num`
- `syntax/tests/test_util.py` line ~7: remove `getconstant`, `Num`, `Str`

**Collapse type checks:**
- `syntax/lambdatools.py` line ~371: `type(k) in (Constant, Str)` → `type(k) is Constant`
- `syntax/letdoutil.py` line ~186: `type(mode[0]) in (Constant, Str)` → `type(mode[0]) is Constant`
- `syntax/letdoutil.py` line ~731: `type(newk) not in (Constant, Str)` → `type(newk) is not Constant`
- `syntax/tailtools.py` line ~1038: `type(theexpr) in (Constant, NameConstant)` → `type(theexpr) is Constant`
- `syntax/tailtools.py` line ~1043: same pattern
- `syntax/tests/test_letdoutil.py` lines ~253, ~259, ~277, ~283, ~528: `type(...) in (Constant, Num)` → `type(...) is Constant`
- `syntax/tests/test_util.py` lines ~159, ~188, ~196: collapse `Num`/`Str` branches

**Update error message:**
- `syntax/letdoutil.py` line ~732: error string mentions `ast.Str` — update to reference only `ast.Constant`

---

## Phase 4: Python 3.13 compatibility

### `hasattr` fixes — CRITICAL (2 sites that will break + 1 in tests)

**`syntax/letdo.py` line ~478** — **Breaks let-binding envify:**
```python
# Before (broken on 3.13):
hasctx = hasattr(tree, "ctx")
# ...later...
if hasctx and type(tree.ctx) is not Load:
    return tree  # early return

# In 3.13: hasctx=True, ctx=Load() (default), type(Load()) is not Load → False.
# This happens to be correct by accident, BUT the intent is to skip Store/Del.
# Make the intent explicit:

# After — check for what we actually care about:
if type(getattr(tree, "ctx", None)) in (Store, Del):
    return tree  # skip assignments and deletes
```
Also update the `ctx` copy at line ~482 (`if hasctx: attr_node.ctx = tree.ctx`). Since the `hasctx` variable is gone, just copy unconditionally: `attr_node.ctx = getattr(tree, "ctx", None)`. On 3.13+ this is always `Load()` at this point (Store/Del already returned); on pre-3.13 it may be `None` (mcpyrate's astfixers will fix it later).

**`syntax/letdoutil.py` line ~763** — passes `None` location values to constructor:
```python
# Before:
if hasattr(oldb, "lineno") and hasattr(oldb, "col_offset"):

# In 3.13: always True, but lineno/col_offset may be None
```
Fix: `if getattr(oldb, "lineno", None) is not None and getattr(oldb, "col_offset", None) is not None:`

**`syntax/tests/test_conts_multishot.py` line ~68** — same `ctx` pattern:
```python
# Before:
if hasattr(tree, "ctx") and type(tree.ctx) is not ast.Load:

# After — check for what we actually care about:
if type(getattr(tree, "ctx", None)) in (ast.Store, ast.Del):
```

### `hasattr` fixes — cleanup (6 sites, accidentally correct)

These are safe in 3.13 by coincidence but should be fixed for consistency and clarity:

**`syntax/scopeanalyzer.py`** lines ~389, ~411: `hasattr(tree, "ctx") and type(tree.ctx) is Store/Del` — works accidentally on 3.13 (`type(Load()) is Store` → False). Simplify to check directly: `type(getattr(tree, "ctx", None)) is Store` / `type(getattr(tree, "ctx", None)) is Del`.

**`syntax/lambdatools.py`** line ~539: `tree.ctx if hasattr(tree, "ctx") else None` — safe. Simplify to `getattr(tree, "ctx", None)`.

**`syntax/testingtools.py`** lines ~803, ~904, ~941, ~1013: `hasattr(tree, "lineno")` — safe (gets `None` either way). Simplify to `getattr(tree, "lineno", None)`.

**`syntax/dbg.py`** lines ~229, ~240: same safe lineno pattern. Simplify.

### `arguments()` constructor — include `posonlyargs` directly (2 sites)

In 3.13, omitting required fields emits DeprecationWarning (error in 3.15). Two sites construct `arguments()` and add `posonlyargs` conditionally afterward. Since the floor is 3.10, just include it in the constructor:

- `syntax/tailtools.py` lines ~1112–1119: add `posonlyargs=[]` to `arguments()` call, remove conditional.
- `syntax/letdo.py` lines ~593–596: same.

### Document `ctx` design constraint

In Python 3.13, AST nodes that omit `ctx` get `Load()` by default (previously the field was absent). This changes the failure mode for macros that create `Name` nodes without setting `ctx`:
- Pre-3.13: no `ctx` → invisible to code that checks `hasattr(tree, "ctx")`
- 3.13+: `ctx=Load()` → silently treated as a Load context node

The existing contract is: if you want `Store` or `Del` semantics, you **must** set `ctx` explicitly. `astfixers.fix_ctx()` handles this in the postprocessing pass, but any macro code that inspects `ctx` *during* expansion (before astfixers runs) relies on this contract.

**Document this in both projects:**

**mcpyrate** — in `doc/main.md` or wherever macro authoring best practices are documented:
- When constructing `Name`, `Starred`, `Subscript`, or `Attribute` nodes in a macro for an AST slot that expects `Store` or `Del` context (e.g. assignment targets, `del` targets, `for` loop variables, `with ... as` targets), you **must** set `ctx` explicitly. If you don't, Python 3.13+ will populate it with `Load()`, which is *incorrect* for that position. `astfixers.fix_ctx()` will unconditionally overwrite `ctx` based on tree position in the postprocessing pass, but it runs *after* all macros have expanded — so any macro code that inspects `ctx` during expansion will see the wrong value.
- On Python 3.12 and earlier, omitted `ctx` resulted in an absent attribute. On 3.13+, it results in `Load()`. Neither is correct for a Store/Del slot, but the failure mode is different: old behavior was "invisible to ctx checks", new behavior is "silently classified as Load, and the resulting AST will likely fail to compile."

**unpythonic** — in `doc/macros.md` or the macro authoring section:
- Same guidance, with specific reference to `scopeanalyzer` and `letdo` envify as code that inspects `ctx` during expansion.
- Note that unpythonic's own macros follow this contract: they do not create `Name` nodes in `Store` or `Del` context without explicitly setting `ctx`.

---

## Phase 5: Feature additions

### `autoreturn` + `match`/`case`

Add `ast.Match` handling to `TailStatementTransformer` in `syntax/tailtools.py` (lines ~685–716).

The handler follows the existing pattern — recurse into the tail statement of each case body:
```python
elif type(tree) is Match:
    for case in tree.cases:
        if case.body:
            case.body[-1] = self.visit(case.body[-1])
```

This is approximately 3–5 lines. Import `Match` directly from `ast` (exists since 3.10, which is the floor).

`scopeanalyzer.py` already handles match/case for scope analysis, so the infrastructure is in place.

### New tests

**`syntax/tests/test_scopeanalyzer.py`** line ~17: TODO says "Add tests for match/case once we bump to 3.10" — now actionable. Add scope analysis tests for match/case patterns.

**Verify `MatchCapturesCollector` correctness**: The collector walks `.patterns` and `.kwd_patterns` of `MatchMapping`/`MatchClass` looking for `Name` nodes. But in practice, captures appear as `MatchAs(name='x')` and `MatchStar(name='rest')` with bare strings — not `Name` nodes. The only `Name` nodes in match patterns are class references like `Point` in `MatchClass.cls` and dotted names in `MatchValue`. The comment at line ~358 says match/case "uses names in `Load` context to denote captures" — verify whether this is accurate, or whether `MatchCapturesCollector` is dead code (or worse, incorrectly collecting class references as captures). The new tests should cover nested patterns like `case {'key': Point(x, y)}:` to exercise this.

**`syntax/tests/test_scopeanalyzer.py`** line ~18: TODO says "Add tests for try/except* once we bump to 3.11" — now actionable. These tests must go in a **separate version-suffixed module** (e.g. `test_scopeanalyzer_3_11.py`) since `except*` syntax won't parse on 3.10. Add a TODO comment in the new file: "Merge into test_scopeanalyzer.py when floor bumps to Python 3.11+."

**Test runner**: Add version-suffix gating to `runtests.py`. The convention is: `test_*_3_NN.py` means "requires Python 3.NN+". Port the `_version_suffix` parsing function from mcpyrate's `runtests.py` (see `~/Documents/koodit/mcpyrate/runtests.py`), but integrate it differently — keep skipped modules in the test list and check inside the per-module `testset()` block:

```python
with testset(m):
    ver = _version_suffix(m)
    if ver is not None and sys.version_info < ver:
        # Log skip using framework idioms (maybe_colorize, TestConfig.printer)
        continue
    mod = import_module(m)
    mod.runtests()
```

Use `maybe_colorize` with the framework's `ColorScheme` (probably `GREYED_OUT` or `WARNING`) for the skip message — don't use mcpyrate's `colorize()` directly. This keeps the skip message visually consistent with the testset nesting structure. This is a new testing capability for unpythonic — up to now, all version-specific tests used AST-based approaches that didn't require the parser to handle newer syntax.

Note: `_version_suffix` parses module names (dotted), not filenames. Adjust the regex to match on the final component, e.g. `test_scopeanalyzer_3_11` at the end of `unpythonic.syntax.tests.test_scopeanalyzer_3_11`.

**`autoreturn` test**: Add a test in `test_autoret.py` verifying that `autoreturn` correctly returns from the tail of each `match`/`case` branch.

Use `unpythonic.test.fixtures` (`test[]`, `test_raises[]` macros, `testset()` context managers). Follow existing test examples in the codebase.

The `match`/`case` and `autoreturn` tests go in regular test modules (not version-suffixed) since the floor is 3.10 and `match`/`case` exists since 3.10. Only `except*` tests (3.11+) need a version-suffixed module.

### Changelog

After all phases are complete, update `CHANGELOG.md` with a 2.0.0 entry covering:
- Python version support: 3.10–3.14 (dropped 3.8, 3.9; added 3.13, 3.14)
- Requires mcpyrate >= 4.0.0
- Deprecated: parens syntax for macro arguments; use bracket syntax instead
- `autoreturn` now handles `match`/`case` statements
- Updated `hasattr` checks for Python 3.13 AST field defaults
- Updated `arguments()` constructors for Python 3.13 strictness
- New scopeanalyzer tests for match/case and try/except*

### Issue tracker

**Close with 2.0.0:**
- #92 — "Remove Python 3.8 support once EOL"
- #93 — "Support Python 3.10+ changes to the AST"

**Re-milestone from 1.1.0 to 2.1.0** (1.1.0 is not happening — it became 2.0.0; these are non-breaking and don't need to be in the major bump):
- #80, #82, #83, #97

If any of these turn out to introduce breaking changes upon closer inspection, move them to 2.0.0 and implement before release.

**#83** ("Support new source location fields in Python 3.8+") — the `hasattr` fixes in Phase 4 are partial progress, but the broader goal of propagating `end_lineno`/`end_col_offset` everywhere remains open. Keep the ticket open, note the partial progress.

**Post-release:** A full triage of all open tickets is overdue. Do this after 2.0.0 ships, not as part of the modernization work.

---

## Testing

Run the full test suite and all demos **after each phase**, on all supported versions:
- Python 3.10 (floor, known working)
- Python 3.11 (supported, not explicitly tested before)
- Python 3.12 (known working)
- Python 3.13
- Python 3.14

```bash
python runtests.py
```

Additionally, on 3.13, catch AST constructor warnings:

```bash
python -W error::DeprecationWarning runtests.py
```

---

## Files affected (summary)

| File | Phase 2 (floor bump) | Phase 3 (mcpyrate 4.0.0) | Phase 4 (3.13) | Phase 5 (features) |
|------|---------------------|--------------------------|----------------|-------------------|
| `syntax/lambdatools.py` | remove version guards | `getconstant`→`.value`, remove `Str` | `hasattr` cleanup | — |
| `syntax/letdoutil.py` | remove version guards, TODOs | `getconstant`→`.value`, remove `Str` | `hasattr` fix (**critical**) | — |
| `syntax/letdo.py` | remove version guard, TODOs | — | `hasattr` fix (**critical**), `arguments()` | — |
| `syntax/tailtools.py` | remove version guard | `getconstant`→`.value`, remove `NameConstant` | `arguments()` | `autoreturn` match/case |
| `syntax/autoref.py` | — | `getconstant`→`.value` | — | — |
| `syntax/util.py` | — | `getconstant`→`.value` | — | — |
| `syntax/scopeanalyzer.py` | remove version guard | — | `hasattr` cleanup | — |
| `syntax/testingtools.py` | remove version guard | — | `hasattr` cleanup | — |
| `syntax/dbg.py` | — | — | `hasattr` cleanup | — |
| `syntax/letsyntax.py` | remove version guard, TODOs | — | — | — |
| `syntax/prefix.py` | remove version guard | — | — | — |
| `syntax/nameutil.py` | remove version guard | — | — | — |
| `syntax/__init__.py` | macro arg brackets TODO | — | — | — |
| `syntax/tests/test_letdoutil.py` | remove version guards, TODO | `getconstant`→`.value`, remove `Num` | — | — |
| `syntax/tests/test_util.py` | — | `getconstant`→`.value`, remove `Num`/`Str` | — | — |
| `syntax/tests/test_conts_multishot.py` | remove version guard | — | `hasattr` fix (**critical**) | — |
| `syntax/tests/test_letdo.py` | TODO brackets | — | — | — |
| `syntax/tests/test_scopeanalyzer.py` | — | — | — | match/case + except* tests |
| `typecheck.py` | remove version guard | — | — | — |
| `misc.py` | remove version guard | — | — | — |
| `tests/test_fun.py` | leave as-is (3.11 guard still needed) | — | — | — |
| `runtests.py` | — | — | — | port version-suffix gating from mcpyrate |
| `syntax/tests/test_scopeanalyzer_3_11.py` | — | — | — | new: except* scope tests |
| `pyproject.toml` | version 2.0.0, deps, classifiers | — | — | — |
| `.pdm-build/pyproject.toml` | sync | — | — | — |
| CI workflows | update matrices | — | — | — |
| `README.md`, `CLAUDE.md`, `CONTRIBUTING.md` | update version ranges | — | — | — |
| `CHANGELOG.md` | — | — | — | add 2.0.0 entry |

## Style notes

Follow existing unpythonic conventions: `from ... import ...` style, ~110 char line width, reStructuredText docstrings. See CLAUDE.md in repo root for full conventions.

Don't rename unpythonic features with `as` — macro code depends on original bare names. The testing framework uses `test[]` and `test_raises[]` macros, not `assert`.
