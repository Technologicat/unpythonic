# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What is unpythonic

A Python library providing language extensions and utilities inspired by Lisp, Haskell, and functional programming. Three-tier architecture:

1. **Pure Python layer** (`unpythonic/`): ~45 modules of functional utilities (curry, memoize, fold, TCO, conditions/restarts, dynamic variables, linked lists, etc.). No macro dependency.
2. **Macro layer** (`unpythonic/syntax/`): Syntactic macros via `mcpyrate` providing cleaner syntax for let-bindings, autocurry, lazify, TCO, continuations, etc.
3. **Dialect layer** (`unpythonic/dialects/`): Full language variants (Lispython, Listhell, Pytkell) built on the macro layer.

## API stability

Released as 2.0.0 in March 2026 (floor bump + mcpyrate 4.0.0 dependency). The public API (everything in `__all__`) should remain backward-compatible. Prefer non-breaking solutions when possible.

## Build and development

Uses PDM with `pdm-backend`. Python 3.10–3.14, also PyPy 3.11.

```bash
# Set up development environment
pdm install              # creates .venv/ and installs deps
pdm use --venv in-project
```

Prefix commands with `pdm run` if the venv is not active.

The project venv is managed by PDM (`pdm venv create`, `pdm use --venv in-project`). To switch Python versions, remove the old venv and create a new one:

```bash
pdm venv remove in-project
pdm config venv.in_project true
pdm venv create 3.14   # or whichever version
pdm use --venv in-project
pdm install
```

**Critical**: Never compile `.py` files in this project using `py_compile`, `python -m compileall`, `--compile`, or any other mechanism that bypasses the macro expander. Stale `.pyc` files compiled without macro support will break macro imports (symptom: `ImportError: cannot import name 'macros' from 'mcpyrate.quotes'`). If this happens, clean the caches with `macropython -c unpythonic` and re-run.

## Running tests

Custom test framework (`unpythonic.test.fixtures`, not pytest). Tests use macros (`test[]`, `test_raises[]`) and conditions/restarts for reporting. The test runner does not need the `macropython` wrapper—it activates macros via `import mcpyrate.activate`. Note: test *framework* is at `unpythonic/test/` (singular); actual *tests* are in `tests/` (plural) subdirectories.

```bash
# Run all tests (from repo root)
python runtests.py

# Run a single test module directly
python -c "import mcpyrate.activate; from unpythonic.tests.test_fun import runtests; runtests()"

# Run macro tests similarly
python -c "import mcpyrate.activate; from unpythonic.syntax.tests.test_letdo import runtests; runtests()"
```

Test suites discovered by `runtests.py`:
- `unpythonic/tests/test_*.py` — pure Python features
- `unpythonic/net/tests/test_*.py` — REPL server/client
- `unpythonic/syntax/tests/test_*.py` — macro features
- `unpythonic/dialects/tests/test_*.py` — dialect features

Each test module exports a `runtests()` function. Tests are grouped with `testset()` context managers.

**Reading test results**: The framework reports Pass/Fail/Error/Total (plus optional `+ N Warn`) per testset. Nested testsets show hierarchy with indentation and asterisk depth (`**`, `****`, `******`, etc.). The distinction between Fail and Error is semantically load-bearing — see the next subsection.

### The `unpythonic.test.fixtures` framework

Part of unpythonic's **public API** (`unpythonic.test.fixtures`, `unpythonic.test.runner`). Reusable by any project that writes macro-enabled Python tests. Rationale for not using pytest:

- pytest installs an import hook that rewrites `assert` statements (to give you the informative "assert x == 42 where x was 41" diagnostics you're used to).
- mcpyrate installs its own import hook to macro-expand source before compilation.
- Python only supports one source-rewriting import hook at a time; the two loaders can't be chained. So if you want both "nice assert messages" *and* "macro expansion", you have to pick one — and macro expansion is non-negotiable for code that uses macros.

`unpythonic.test.fixtures` is the answer: instead of overriding the `assert` keyword, it provides `test[expr]`, `test_raises[cls, expr]`, `test_signals[cls, expr]`, and `warn[msg]` **macros** that construct test assertions at the AST level, and route results through `mcpyrate`'s condition system. The result categories:

- **Pass**: the `test[...]` expression evaluated to a truthy value (or `test_raises[...]` saw exactly the expected exception, etc.). The test ran to completion and met its expectation.
- **Fail**: the test ran to completion, but the expectation was not met — `test[x == 42]` saw `x == 41`, or `test_raises[TypeError, ...]` saw the expression return normally. This is the "your code is wrong" category.
- **Error**: the test did **not** run to completion. An unhandled exception (or unhandled `error`/`cerror` condition) escaped the `test[...]` expression itself. This is the "the test infrastructure or the code *under* test crashed in a way the test didn't expect" category — semantically distinct from Fail, because the test never got to judge the expectation. An Error in CI means something is broken in a way that needs investigation, not just "the assertion didn't hold."
- **Warn**: advisory, emitted via `warn[msg]` (or by the runner itself for version-gated skips like "this test requires Python 3.14+, skipping on 3.13"). Does **not** count toward Pass/Fail/Error totals and does **not** fail the testset. Used for temporarily disabled tests, optional-dependency skips, and similar soft signals.

**Capturing values with `the[]`**: when a `test[]` fails, you want to see *what the interesting subexpression actually evaluated to*, not just "the assertion was falsy." The `the[...]` helper macro marks a subexpression for capture; at run time, when the test fires, the framework formats a failure message with the source text and captured value of each `the[]`. The name is chosen to mostly preserve English reading order at the use site (`test[the[x] == 42]` reads roughly as "test that the `x` equals 42"), and is also a nod to Common Lisp's `THE` special form — though CL's `THE` is a *type-declaration* construct, so it's a name pun, not a semantic port. Heads-up for grepping: `the` is a word-boundary nightmare; anchor searches with `\bthe\[`. Usage:

- `test[the[x] == 42]` → on failure, reports `x` and the value it had.
- `test[f(the[a]) == g(the[b])]` → reports both `a` and `b`, in evaluation order. A `test[]` can contain any number of `the[]`, including nested (`the[outer(the[inner])]`).
- **Default**: if the top-level expression of `test[]` is a comparison and no explicit `the[]` is present, the leftmost term is **implicitly** wrapped — so `test[x == 42]` already reports `x` without you having to write `the[x]`. This is the common case.
- Use explicit `the[]` when you want to capture something *other* than the LHS of the top-level comparison — e.g. a subexpression inside a function call, a term in a non-comparison assertion, or multiple values at once.
- The helper is smart enough to skip trivial captures (literal values), so `test[4 in the[(1, 2, 3)]]` won't clutter the output with `(1, 2, 3) = (1, 2, 3)`.
- **Not supported** inside `test_raises`, `test_signals`, `fail`, `error`, or `warn` — only in `test[...]` and `with test:` blocks.

**Debugging cheat sheet**: a small number of **Warn**s on CI is expected (optional dependencies, version gates). **Fail** means a real expectation mismatch — read the captured values from `the[]` in the message. **Error** is the one you should *always* look at first: it means control flow in the test went somewhere unexpected, and the count alone won't tell you where. The log above the summary line has the actual traceback.

## Linting

```bash
ruff check <changed .py files>   # primary linter (config in pyproject.toml)
```

Legacy `flake8rc` also present (used by Emacs flycheck, not by CI or CC).

## Code structure and conventions

- **Regular code** in `unpythonic/`, **macros** in `unpythonic/syntax/`, **REPL networking** in `unpythonic/net/`, **dialects** in `unpythonic/dialects/`.
- **Tests** are in `tests/` (plural) subdirectories under the code they test. The testing *framework* lives at `unpythonic/test/` (singular).
- Each module declares `__all__` explicitly for public API. The top-level `__init__.py` re-exports via star imports.
- **Import style**: Use `from ... import ...` (not `import ...`). The from-import syntax is mandatory for macro imports and used consistently throughout. Don't rename unpythonic features with `as`—macro code depends on original bare names.
- **No star imports** in user code (only in the top-level `__init__.py` for re-export).
- **Curry-friendly signatures**: Parameters that change least often go on the left. Use `def f(func, thing0, *things)` (not `def f(func, *things)`) when at least one `thing` is required, so `curry` knows when to trigger.
- **Macros are the nuclear option**: Only make a macro when a regular function can't do the job. Prefer a pure-Python core with a thin macro layer for UX.
- **Macro `**kw` passing**: Use `dyn` (dynamic variables) to pass `mcpyrate` `**kw` arguments through to syntax transformers, rather than threading them through parameter lists.
- **Variable names**: Descriptive but compact. Prefer `theconstant` over `node` when the type matters, `thebody` over `b` when scope is more than a few lines. Avoid generic names like `tmp`, `data`, `x` unless scope is trivially small. In test code using the `the[]` macro, avoid `the`-prefixed names — `the[theconstant]` isn't English. Use e.g. `constant_node` instead.
- **Line width** ~110 characters. Docstrings in reStructuredText.
- **Module size target**: ~100–300 SLOC, rough max ~700 lines. Some modules are longer when appropriate (e.g. `syntax/tailtools.py` at ~1600 lines). Never split just because the line count was exceeded.
- **Dependencies**: Avoid external dependencies. `mcpyrate` is the only allowed external dep and must remain strictly optional for the pure-Python layer.

## Key cross-cutting concerns

- `curry` has cross-cutting behavior — grep for it when investigating interactions.
- `@generic` (multiple dispatch) similarly has cross-cutting concerns.
- The `lazify` macro: also grep for `passthrough_lazy_args` and `maybe_force_args`.
- The `continuations` macro builds on `tco` — read `tco` first when studying continuations.
- `unpythonic.syntax.scopeanalyzer` implements lexical scope analysis for macros that interact with Python's scoping rules (notably `let`).
