# CC Brief: Python 3.15 support (unpythonic side)

Companion to `mcpyrate/briefs/python-3.15-support.md`, which carries the full AST survey and the expander-side work. This one is the unpythonic half, written to stand on its own for anyone looking only at this repo.

Three fleet projects read the Python AST directly and so are the ones a CPython minor version can break: `mcpyrate`, `unpythonic`, and `pyan` (which has its own brief at `pyan/briefs/python-3.15-support.md`, and is the only one with a confirmed 3.15 crash).

## Context

CPython 3.15 reached rc1 in August 2026. `unpythonic`'s `requires-python = ">=3.10,<3.15"` cap is deliberate and stays until this work lands: a macro layer running against an AST grammar it does not know invites a crash, or worse, a silent misexpansion. Raising the cap is the last step.

`mcpyrate` goes first, being the dependency. Nothing here can be finished before the expander understands the new grammar.

Prior art for the analysis shape: issue #93 (closed), which tracked the 3.10–3.12 AST changes by asking, per new form, which macro-layer components must learn to detect it.

## What changed in the AST

Three field changes, no new node types, from two PEPs. Verified 2026-08-16 by diffing `Parser/Python.asdl` between the 3.14 and 3.15 tags.

```
-          | Import(alias* names)
-          | ImportFrom(identifier? module, alias* names, int? level)
+          | Import(alias* names, int? is_lazy)
+          | ImportFrom(identifier? module, alias* names, int? level, int? is_lazy)
-         | DictComp(expr key, expr value, comprehension* generators)
+         | DictComp(expr key, expr? value, comprehension* generators)
```

- **PEP 810, lazy imports** — `lazy import json`, `lazy from pathlib import Path`. Module scope only.
  - `lazy` is a soft keyword admitted only before `import` / `from`, so it does **not** collide with this library's own `lazy` macro. `lazy[...]`, `from unpythonic.syntax import macros, lazy` and `lazy = 5` all parse exactly as before. This was checked specifically, in the grammar, because the name clash looks alarming.
- **PEP 798, unpacking in comprehensions** — two different AST consequences:
  - `{**d for d in dicts}` builds `DictComp(key=d, value=None)`. The mapping lands in `key`; `value` being `None` *is* the marker. Previously `value` was always a node, so this is the one that can fail silently.
  - `[*L for L in lists]`, `{*s for s in sets}`, `(*L for L in lists)` put a `Starred` in `elt`. No grammar change was needed for these, and CPython's unparser needed no new code — existing `Starred` handling covers them.

Also, AST node constructors now raise `TypeError` for a missing required field or an unknown kwarg, promoted from the `DeprecationWarning` in force since 3.13.

## What is already verified about this repo

- **No AST-constructor deprecations remain.** Full suite on 3.14.6 under `-W error::DeprecationWarning`, with bytecode caches cleared first so every macro genuinely re-expands: 3830 pass, 0 fail, 2 errors, neither AST-related. The 3.13-era `arguments(posonlyargs=[])` cleanup holds.
  - Clearing the caches is not optional for this check. A warm cache skips expansion entirely, and the run then proves nothing while looking identical. See the `runtests.py` item in `TODO_DEFERRED.md`.
- **A value-less `DictComp` traverses safely.** `mcpyrate`'s `ASTVisitor` / `ASTTransformer` inherit CPython's `generic_visit`, which leaves a field alone when its value is neither a list nor an `AST` — so `value=None` passes through every walker in this library without special handling.
- **`scopeanalyzer` needs no change.** Its comprehension branch (`scopeanalyzer.py:242`) reads only `generators`; its import branch (`:337`) reads only `names`. Neither `is_lazy` nor a value-less `DictComp` reaches it.

## Work items

All of these need a real 3.15 to settle; they cannot be resolved by reading. Python 3.15.0rc1 is installed on the personal machine.

1. **`lazify` with a `Starred` comprehension element.** `lazify.py` has no comprehension-specific handling at all, and its `Starred` handling is scoped to call arguments (line 537) and container literals (line 770). A `Starred` in `elt` position is a new shape reaching the generic path. The hazard is wrapping the starred value in a promise, since `*promise` fails at unpacking. Test `with lazify:` over all four new comprehension forms.
2. **`autocurry` and `tailtools` over the same forms.** Same question, same reason; `tailtools.py:1011,1026` already reasons about `Starred` in a different context.
3. **Any macro that dereferences a `DictComp` field directly.** The walkers are safe, but a macro reading the fields is not, and there are two distinct ways to be wrong:
   - assuming `value` is a node — it is `None` for the unpacking form;
   - assuming `key` is a key — in the unpacking form it holds the whole mapping expression, so the field name lies.

   The second is the easier one to miss, because nothing raises: the code runs and quietly treats a mapping as a key. Note also that the convention is mirrored from the dict *literal* encoding, where `{**a}` is `Dict(keys=[None], values=[Name('a')])` — `None` in `keys`, mapping in `values`, i.e. the opposite halves from the comprehension. Reasoning from the literal to the comprehension gives the wrong answer. Audit both fields, and re-grep once 3.15 can parse the new forms into test fixtures.
4. **Test modules for the new syntax**, version-suffix gated so they skip on older interpreters — the same mechanism `mcpyrate` uses for `test_020_unparser_3_13.py` / `_3_14.py`.
5. **Raise the cap, last.** `pyproject.toml`: `>=3.10,<3.15` → `>=3.10,<3.16`, plus the `Programming Language :: Python :: 3.15` classifier, plus the CI matrix. Keep the upper bound rather than removing it — an unbounded floor makes the resolver seek a version valid for every future Python, and it will silently fall back to an ancient release rather than fail.

## Adjacent finding

`unpythonic/tests/test_typecheck.py:205` errors under `-W error::DeprecationWarning` because `isinstance` against `typing.ByteString` reaches `collections.abc.ByteString`, deprecated and slated for removal in 3.17. Python 3.15 widens the warning to mere import or attribute access. Not a blocker for 3.15, but it needs version gating before 3.17 regardless.
