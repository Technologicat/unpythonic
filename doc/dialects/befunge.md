**Navigation**

- [README](../../README.md)
- [Pure-Python feature set](../features.md)
- [Syntactic macro feature set](../macros.md)
- [Examples of creating dialects using `mcpyrate`](../dialects.md)
  - [Lispython](lispython.md)
  - [Listhell](listhell.md)
  - [Pytkell](pytkell.md)
  - [BF](bf.md)
  - **Befunge**
- [REPL server](../repl.md)
- [Troubleshooting](../troubleshooting.md)
- [Design notes](../design-notes.md)
- [Essays](../essays.md)
- [Additional reading](../readings.md)
- [Contribution guidelines](../../CONTRIBUTING.md)

<!-- markdown-toc start - Don't edit this section. Run M-x markdown-toc-refresh-toc -->
**Table of Contents**

- [Befunge: two-dimensional, self-modifying, deeply confused](#befunge-two-dimensional-self-modifying-deeply-confused)
    - [Features](#features)
    - [Errors](#errors)
    - [What Befunge is](#what-befunge-is)
    - [Contrast with BF](#contrast-with-bf)
    - [Comboability](#comboability)
    - [CAUTION](#caution)
    - [Etymology?](#etymology)

<!-- markdown-toc end -->

# Befunge: two-dimensional, self-modifying, deeply confused

A [Befunge-93](https://en.wikipedia.org/wiki/Befunge) interpreter wrapped as a whole-module source dialect.

Powered by [`mcpyrate`](https://github.com/Technologicat/mcpyrate/).

```python
"""Hello from Befunge!"""

from unpythonic.dialects.befunge import dialects, Befunge  # noqa: F401

"!egnufeB morf olleH">:#,_@
```

The body of the file (everything after the dialect-import) is parsed as a Befunge-93 playfield and run by the runtime interpreter shipped in this module.

The recommended form for commentary is a **module docstring** above the dialect-import line, as shown — `help(some_befunge_module)` then displays it the same way it would for any documented Python module. Stand-alone `# …` comments above the dialect-import line work too. Below the dialect-import everything is the playfield; comments inside the body are not supported, because Befunge has no comment syntax (`#` is a real command — *trampoline / skip-next-cell*).

## Features

  - **Strict Befunge-93**: 80 × 25 toroidal playfield, byte-valued cells, unbounded-int stack.
    - The IP wraps toroidally on motion: off the right edge → column 0 of the same row, off the bottom → row 0 of the same column.
    - Stack underflow on `pop` returns 0 (per spec).
  - **All 93 commands supported**:
    - Arithmetic: `+`, `-`, `*`, `/`, `%` (division and modulo by zero push 0, per spec).
    - Comparison and logic: `!` (not), `` ` `` (greater-than).
    - Direction: `>`, `<`, `^`, `v`, `?` (random).
    - Conditional direction: `_` (pop; 0 → east, else west), `|` (pop; 0 → south, else north).
    - String mode: `"` toggles. While on, every cell pushes `ord(ch)` instead of executing.
    - Stack: `:` duplicate, `\` swap, `$` discard.
    - I/O: `.` print int (followed by a space), `,` print char, `&` read int, `~` read char.
    - Trampoline: `#` skip the next cell.
    - Self-modifying: `g` (get cell value), `p` (put cell value); both pop `(x, y)` first.
    - Halt: `@`.
    - Space is a no-op.
  - **`?` (random direction) is seedable for tests**: `run(src, *, seed=int)` uses a `random.Random` instance, so the seed reaches the dispatch and doesn't perturb the user's process-wide RNG. `seed=None` (the default) picks via OS entropy.

The same interpreter is available as a plain function:

```python
from unpythonic.dialects.befunge import run

run(playfield_source)
```

I/O goes through `sys.stdin` / `sys.stdout`. To capture output in tests, wrap the call with `contextlib.redirect_stdout`; for input, use `unpythonic.redirect_stdin` (the third sibling — `contextlib` ships only the output redirectors).

## Errors

Three distinct conditions, three distinct exception types:

  - **`SyntaxError`** — the source is malformed at `Playfield(src)` construction time: more than 25 rows, or any line longer than 80 columns. Pre-execution.
  - **`IndexError`** — runtime out-of-grid access via `g` or `p`. The IP itself never goes out of grid (its motion wraps toroidally); `IndexError` only fires on programs that compute their own coordinates and address outside the 80 × 25 bounds.
  - **`UnknownOpcodeError`** (a `RuntimeError` subclass exported from `unpythonic.dialects.befunge`) — the IP visited a cell whose byte value isn't a recognized command. Includes both source-level typos and `p`-modified cells that ended up holding a non-command byte.

## What Befunge is

Befunge is a dialect ~of Python~ implemented as a whole-module *source-to-source* transform — at the text level, before `mcpyrate`'s AST stage. The dialect definition and runtime interpreter both live in [`unpythonic.dialects.befunge`](../../unpythonic/dialects/befunge.py). Usage examples can be found in [the unit tests](../../unpythonic/dialects/tests/test_befunge.py).

The `transform_source` hook for the `Befunge` dialect class wraps the playfield text in a single `run(<source>)` call, so a Befunge-dialect file ultimately compiles to two lines of Python:

```python
from unpythonic.dialects.befunge import run
run(<the original playfield text>)
```

Leading entirely-blank lines in the body are stripped before the playfield is built. Without that strip, the blank line that typically follows the dialect-import would become row 0 (all spaces); the IP would walk the full no-op row, wrap toroidally back to column 0 of row 0, and loop forever before reaching the actual program.

## Contrast with BF

`unpythonic.dialects.bf` and `unpythonic.dialects.befunge` are the package's two source-level dialects, but they make complementary teaching points about `transform_source`:

  - **BF is a transpiler**. `bf.compile(src)` produces structured, legible Python that mirrors the input program. The pedagogic value is in the output text — you can read a BF program by reading the Python it compiles to.
  - **Befunge is a reader**. `transform_source` wraps the playfield in a runtime interpreter call; the compiled output is a thin shim, and the language's semantics live in the interpreter. This isn't a design failure: BF is structurally close to Python (linear stream, lexical loops), but Befunge is fundamentally IP-driven on a 2-D, self-modifying grid, and a legible static translation is impossible. (The `p` command rewrites the playfield at runtime, so no static analysis can be sound.)

The same `transform_source` hook serves both shapes; what differs is how much of the language's behavior the hook can statically lower into Python.

I/O operator names also differ between the two: BF uses `.` for character output, while Befunge uses `.` for *integer* output and `,` for character output. Worth keeping in mind when switching contexts.

## Comboability

Source-transforming dialects consume the whole module body, so combining Befunge with another source-transforming dialect (BF, or itself) on the same file doesn't really make sense. Composition with **AST-transforming** dialects is supported: `from … import dialects, Befunge, SomeOptimizer` (or on separate `from` lines) places `SomeOptimizer` after Befunge in the transform chain, running its AST pass on the output of the Befunge compiler — which, since Befunge's output is a one-liner `run(...)` call, mostly amounts to processing that one statement.

The mechanism is the `mcpyrate.dialects.split_at_dialectimport` helper (new in `mcpyrate` 4.1.0): the dialect's `transform_source` uses it to peel off its own dialect-import line while preserving any others for the next round of dialect processing.

## CAUTION

Not intended for ~serious~ use.

## Etymology?

See [Wikipedia](https://en.wikipedia.org/wiki/Befunge).
