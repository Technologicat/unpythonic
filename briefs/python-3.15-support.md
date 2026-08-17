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

## How to start (2026-08-17)

**mcpyrate's side is done**, so this is unblocked: its import hook, unparser and lazy
macro-import rejection all landed, and its suite is green on 3.15.0rc1. Two practical notes
before touching anything.

**Run the full suite on 3.15 first, before working from the list below.** The static survey in
this brief is triage, not evidence of health. `pyan`'s equivalent brief predicted exactly one
bug and there were two — the second being a `symtable` rename that broke every module
containing a lambda, invisible to the ASDL diff (not a grammar change) and invisible to an
import check (the import succeeds). Only running the suite found it. Clear the bytecode caches
first (`macropython -C .`), or the expander does not re-run and the pass proves nothing.

**Getting a 3.15 interpreter here needs a workaround until the cap moves.** `requires-python`
is still `>=3.10,<3.15`, so `pdm venv create 3.15` will refuse. Either raise the cap first, or
run against a standalone 3.15 venv with `PYTHONPATH` pointed at the repo — the latter needs
`mcpyrate` importable and `colorama` installed, since `unpythonic` pulls in mcpyrate's
colorizer path.

**Do not tag a release for this alone.** `mcpyrate` and `unpythonic` ship together, once
verified against each other; mcpyrate's 3.15 work is already sitting unreleased in its `4.2.1`
in-progress section waiting for this. See the `release` skill.

## Measured on 3.15.0rc1 (2026-08-17) — the open questions are answered

**The suite is green on 3.15**: 3862 pass, 0 fail, 0 error, with bytecode caches cleared first
so every macro genuinely re-expanded. For comparison 3.14.6 gives 3883 — the 21-test gap is
SymPy and mpmath missing from the ad-hoc 3.15 venv, not a 3.15 difference. Note the earlier
figure of 3830 in this brief came from a run under `-W error::DeprecationWarning`, where two
errors cut their testsets short; it is not comparable.

**That result is weaker than it looks, and does not close the work.** No existing test contains
PEP 798 or PEP 810 syntax, so a green suite shows only that nothing *broke* — it never exercises
the new forms at all. Probing them directly is what settles it, and that probe is now run:

| construct | `lazify` | `autocurry` | `tco` |
|---|---|---|---|
| `[*items(k) for k in ks]` | ok | ok | ok |
| `(*items(k) for k in ks)` | ok | — | — |
| `{**mapping(k) for k in ks}` | ok | ok | ok |

All produce correct values. **So items 1-3 below need no code change.** The specific hazard
anticipated for `lazify` — wrapping the `Starred`'s value in a promise, so that `*promise` fails
at unpacking — does not occur.

What remains is therefore small: turn that probe into version-gated tests so the invariant is
kept rather than rediscovered, and move the version metadata.

## Work items

Items 1-3 are settled as above and need tests rather than fixes. Python 3.15.0rc1 is installed on both machines.

**Release ordering is forced, and the CI matrix has to wait for it.** `unpythonic` declares
`mcpyrate>=4.2.0`, and **mcpyrate 4.2.0 as published cannot import any module under 3.15** —
verified by installing it into a clean 3.15 venv, where importing an ordinary module dies with
`TypeError: source_to_xcode() takes 3 positional arguments but 4 were given`. So a 3.15 job in
`unpythonic`'s CI would resolve `mcpyrate` from PyPI, get 4.2.0, and fail for reasons that have
nothing to do with the code under test. The sequence is therefore:

1. Land unpythonic's code changes — tests, `requires-python` cap, classifier. No CI matrix entry.
2. Release **mcpyrate 4.2.1** (its work is already done and waiting).
3. In `unpythonic`, bump the pin to `mcpyrate>=4.2.1` **and** add `"3.15"` to the CI matrix with
   `allow-prereleases: true`, in one commit. Only now can that job pass.
4. Release **unpythonic 2.3.1**.

"Released together" therefore means same sitting, verified against each other — not simultaneous.
The verification itself is already done: unpythonic's suite was run against the working-tree
mcpyrate and passed 3862/3862.

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
