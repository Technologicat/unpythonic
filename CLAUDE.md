# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What is unpythonic

A Python library providing language extensions and utilities inspired by Lisp, Haskell, and functional programming. Three-tier architecture:

1. **Pure Python layer** (`unpythonic/`): ~45 modules of functional utilities (curry, memoize, fold, TCO, conditions/restarts, dynamic variables, linked lists, etc.). No macro dependency.
2. **Macro layer** (`unpythonic/syntax/`): Syntactic macros via `mcpyrate` providing cleaner syntax for let-bindings, autocurry, lazify, TCO, continuations, etc.
3. **Dialect layer** (`unpythonic/dialects/`): Full language variants (Lispython, Listhell, Pytkell) built on the macro layer.

## Build and development

Uses PDM with `pdm-backend`. Python 3.8–3.12, also PyPy 3.8–3.10.

```bash
# Set up development environment
pdm install              # creates .venv/ and installs deps
pdm use --venv in-project
source .venv/bin/activate
```

**Critical**: When installing from source, never use `--compile` / precompilation. Precompiled bytecode without macro support breaks macro imports like `from unpythonic.syntax import macros, let`.

## Running tests

Custom test framework (not pytest). Tests use macros (`test[]`, `test_raises[]`) and conditions/restarts for reporting. The test runner does not need the `macropython` wrapper—it activates macros via `import mcpyrate.activate`.

```bash
# Run all tests (from repo root, with venv activated)
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
- **Line width** ~110 characters. Docstrings in reStructuredText.
- **Module size target**: ~100–300 SLOC, rough max ~700 lines.
- **Dependencies**: Avoid external dependencies. `mcpyrate` is the only allowed external dep and must remain strictly optional for the pure-Python layer.

## Key cross-cutting concerns

- `curry` has cross-cutting behavior — grep for it when investigating interactions.
- `@generic` (multiple dispatch) similarly has cross-cutting concerns.
- The `lazify` macro: also grep for `passthrough_lazy_args` and `maybe_force_args`.
- The `continuations` macro builds on `tco` — read `tco` first when studying continuations.
- `unpythonic.syntax.scopeanalyzer` implements lexical scope analysis for macros that interact with Python's scoping rules (notably `let`).
