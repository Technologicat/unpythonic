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

**Reading test results**: The framework reports Pass/Fail/Error/Total per testset. "Error" means an unexpected exception inside a `test[]` expression — this includes intentional skip-with-message patterns (e.g. "SymPy not installed"), so a few errors from optional-dependency tests are normal. Look at the actual error messages, not just the count. Nested testsets show hierarchy with indentation and asterisk depth (`**`, `****`, `******`, etc.).

## Linting

```bash
# As in CI — hard errors (syntax errors, undefined names)
flake8 . --config=flake8rc --select=E9,F63,F7,F82 --show-source

# Soft warnings
flake8 . --config=flake8rc --exit-zero --max-line-length=127
```

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
