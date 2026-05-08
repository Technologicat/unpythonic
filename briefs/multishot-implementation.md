# CC Brief: Multi-shot generator macros for unpythonic

## Goal

Promote the working proof-of-concept in `unpythonic/syntax/tests/test_conts_multishot.py` to a real public-API macro module. Resolves issue #80 (milestone 2.2.0).

Ships `@multishot` (decorator macro), `myield` (name/expr macro, four forms), and `MultishotIterator` (pure-Python adapter conforming to a subset of the generator protocol). Multi-shot continuations: a `@multishot` function can be resumed *from any earlier `myield`, arbitrarily many times*, branching execution into independent timelines.

Sits alongside raw `call_cc[]` (which stays as the alien-grade primitive) and `get_cc()` (the human-friendly Racket-`let/cc`-styled name binding). `@multishot`/`myield` is the third tier — ergonomic, generator-shaped, for the pattern that motivates `get_cc` in the first place.

## Reference

- Source: `unpythonic/syntax/tests/test_conts_multishot.py` (the working demo, including `@multishot`, `myield`, and `MultishotIterator`)
- Earlier didactic version: `unpythonic/syntax/tests/test_conts_gen.py` (single-shot `dlet`-based generators, kept as teaching cross-reference)
- Existing precedent for syntax-module + adapter pairing: `unpythonic.syntax.continuations` + `unpythonic.fun` helpers
- Continuations primitives used: `call_cc`, `get_cc`, `iscontinuation` (already public)
- Documentation home: `doc/macros.md` (chapter on continuations) — new subsection parallel to "Topology of continuations" and "Scoping of locals in continuations" added during #82

## Design decisions (confirmed in pre-build discussion 2026-05-06)

### Module layout

```
unpythonic/syntax/multishot.py       # @multishot, myield, MultishotIterator together
unpythonic/syntax/tests/test_multishot.py
```

Adapter (`MultishotIterator`) lives **alongside the macro**, not in a separate pure-Python module. Rationale: the adapter is unusable without `@multishot`, and grouping the public surface in one file keeps the contract obvious. Re-export both macros and the adapter via `unpythonic/syntax/__init__.py` (and from there into the top-level `__init__.py`'s star-import set, per project convention).

### Naming

`@multishot`, `myield`, `MultishotIterator`. Keep the demo's names — `myield` is consistent with unpythonic's `m`-prefixed style, and grep-friendly enough with `\bmyield\b`.

### Scope: separate API, not a replacement

`@multishot` is an additional ergonomic layer on top of `call_cc[]`/`get_cc()`. It does **not** supersede them. Users who want the low-level form keep it. unpythonic is partly a pedagogic project; raw `call_cc` stays for readers studying continuations.

### `with continuations` is required and explicit

`@multishot` only works inside an enclosing `with continuations:` block. The macro does not auto-wrap. Zen of Python: explicit is better than implicit. Document the requirement at the top of the docstring; raise a clear macro-expansion-time error if the user forgets (detectable when `call_cc` isn't macro-imported in scope, or — failing that — fall through to whatever error the unconverted `call_cc[]` produces and document the symptom).

### `myield` placement constraint

Statement-only, top-level-only inside the `@multishot` body. This is a real limitation of `call_cc[]`, not negotiable. Document loudly. Macro raises `SyntaxError` at expansion time if `myield` is found outside the top level of a `@multishot` `def` (the demo already does this).

### `MultishotIterator` API surface (v1)

Standard generator protocol subset:
- `__iter__`
- `__next__`
- `send(value)`
- `throw(typ_or_exc)` — quirky semantics documented (no paused frame to throw into; re-entering the continuation makes it raise)
- `close()` — quirky semantics documented (closing rejects further `next`/`send` unless `self.k` is overwritten)

Generator introspection attributes:
- `gi_frame` — **always `None`**. A multi-shot generator has no paused frame: every `myield` terminated its frame and returned a continuation closure; state lives in closure cells, not a frame. The real-generator idiom `gen.gi_frame is None ↔ exhausted` does **not** apply here — there's never a paused frame, by construction. Document loudly under "Differences from standard Python generators".
- `gi_code` — `self.k.__code__` while live; `None` after `close()`. This is what consumers should use as the liveness signal. Gives debuggers the code object that the next advance will run.
- `gi_running` — **always `False`**. Nothing is ever paused: every continuation is a separately-activated closure.
- `gi_yieldfrom` — `None` in v1 (no `myield_from` yet). Becomes meaningful in the post-v1 follow-up.

Beyond the standard surface:
- `__copy__` — fork the iterator. Both copies share the current continuation; subsequent advances diverge into independent timelines. **This is the entire point of multi-shot, exposed through the stdlib `copy` protocol.** Docstring should mention the technical distinction — standard Python generators don't support `copy.copy()` at all — since that's what makes the protocol meaningful here. Suggested docstring: *"Forks this multi-shot iterator at the current continuation; subsequent advances of the two iterators are independent. Unlike standard Python generators, multi-shot generators are copyable."*
- `__deepcopy__` — raises `TypeError("multi-shot iterators cannot be deep-copied; use copy.copy() to fork")`. The continuation closes over caller state we can't meaningfully deep-copy, and the stdlib's default deep-copy fallback (recurse into `__dict__`) would either error obscurely or produce a nonsensical clone. Fail loudly and point the user at the right tool.
- `__del__` calls `close()`. Mostly cosmetic for multishot (no paused frame to clean up), but mirrors generator GC semantics.

Not in v1, with documented rationale:
- `myield_from` — planned as the immediate follow-up changeset (see "Post-v1, while CI engines are still warm" below). v1 ships without.
- Async multi-shot generators (`__aiter__`, `asend`, `athrow`, `aclose`) — out of scope. unpythonic has no async support yet across the library; deferred until that's a project. Note in docs as future work.
- Pickling / `__reduce__` — continuations are closures; not picklable. Note and skip.
- `yield from` *across* a real generator and a multishot — wontfix. Real generators have paused state, multishots don't; the semantic mismatch can't be papered over. Documented as a known limitation.

### PEP 479 boundary

`return value` inside `@multishot` is rewritten to `raise StopIteration(value)` (the demo already does this). PEP 479's "StopIteration leaking out of a generator becomes RuntimeError" applies inside *real* generator frames; the multishot body is a regular function under the hood, so the rewrite produces a `StopIteration` that the `MultishotIterator` wrapper catches and re-raises cleanly to the caller. Add a test confirming `return 42` surfaces as `StopIteration(42)` to the iterator consumer, not `RuntimeError`.

### Documentation

New subsection in `doc/macros.md` under the existing continuations chapter, parallel to "Topology of continuations" and "Scoping of locals in continuations" added during #82. Sections:

1. **Why multi-shot.** One-paragraph framing: classical Python generator + can resume from any earlier `myield` arbitrarily many times.
2. **Usage.** `@multishot` + `myield` four-form table (the one already in the demo's docstring), plus the `MultishotIterator` wrapper for generator-protocol-shaped consumption.
3. **Differences from standard Python generators.** `copy()` is the headline: *"Unlike standard generators, multi-shot generators support `copy.copy()`. The fork shares the current continuation; subsequent advances of the two iterators diverge into independent timelines."* Then the limitations: no `yield from` across real/multishot, exception/`finally` semantics differ across `myield` boundaries, no async form, no pickling, statement-only top-level `myield`.
4. **Cross-references.** Pointer to `test_conts_gen.py` (single-shot didactic version, raw `call_cc`) and `test_conts_multishot.py` — wait, that one *is* the implementation, will be replaced. Cross-link to whatever didactic example survives, plus the new `test_multishot.py` for the canonical usage.

TOC updated.

### Tests

New file `unpythonic/syntax/tests/test_multishot.py`. Promote/rewrite from `test_conts_multishot.py`, dropping the multi-phase compilation scaffolding (the real module won't need it — users just import). Keep `test_conts_gen.py` as the didactic single-shot raw-`call_cc` example, cross-referenced from the new docs. Retire `test_conts_multishot.py` once the new tests cover its content (it's superseded by the real module + tests).

Test coverage targets:
- Each of the four `myield` forms.
- Basic linear consumption via `MultishotIterator` (matches the demo's `[x for x in mi] == [1, 2, 3]`).
- `send` round-trip into `var = myield`.
- `throw` re-entry into a continuation.
- `close` rejecting subsequent `next`.
- **Multi-shot fork via `copy.copy`** — the headline test. Two iterators from the same continuation, advance independently, assert the timelines differ.
- `copy.deepcopy(mi)` raises `TypeError`.
- `gi_running is False` always (including mid-iteration, sampled between `next` calls).
- `gi_frame is None` always (including mid-iteration and after `close()`).
- `gi_code` matches `self.k.__code__` while live, becomes `None` after `close()`.
- `gi_yieldfrom is None` (becomes meaningful after `myield_from` lands).
- `return value` inside `@multishot` raises `StopIteration(value)` to the consumer, not `RuntimeError`.
- `myield` outside a `@multishot` raises `SyntaxError` at macro-expansion time.
- `myield` inside a nested scope (lambda, comprehension, nested `def`) raises `SyntaxError` at expansion time.

## Post-v1, while CI engines are still warm

Add `myield_from` as an immediate follow-up changeset:
- New name/expr macro `myield_from(other_multishot)` that delegates to another `@multishot`'s continuation.
- Restricted to multishot-to-multishot; cross-talk with real generators stays wontfix.
- Update `gi_yieldfrom` to point to the inner iterator's current continuation while delegating.
- Tests + doc subsection.

Treat `myield_from` as a separate PR/commit on top of the v1 module landing — keeps the v1 review surface manageable and gives a clean point to bail if `myield_from` turns out harder than it looks.

## CHANGELOG

Under 2.2.0 in-progress section, **Added**:
- `@multishot` and `myield` macros + `MultishotIterator` adapter (`unpythonic.syntax.multishot`). Multi-shot generators that can resume from any earlier `myield` arbitrarily many times. See `doc/macros.md`.

`myield_from` follow-up gets its own line under **Added** when it lands.

## Out of scope

- Async multishot generators.
- Pickling support.
- `yield from` across real and multishot generators.
- Removing `call_cc[]` or `get_cc()` from the public API. They stay.

## Open questions to resolve during implementation

- `__copy__` is shallow: `MultishotIterator(self.k)`. Both forks legitimately share the same closure cells — that's the multi-shot semantics. Document this in the `__copy__` docstring.
