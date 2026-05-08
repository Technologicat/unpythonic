# CC Brief: `bf` — a source-level dialect for brainfuck

## Goal

Add a new dialect `unpythonic.dialects.bf` that compiles brainfuck source into
macro-enabled Python and runs it. Fills the one remaining gap in unpythonic's
dialect-example collection: the existing dialects (Lispython, Lispy, Listhell,
Pytkell) all demonstrate `transform_ast`. None demonstrate `transform_source`,
the mcpyrate hook for full-module source-text transformers — the modern
equivalent of what old Lisp folks called a *reader macro*.

mcpyrate's own `Dialect.transform_source` docstring uses brainfuck as its
illustrative example and ends with the line *"Implementing the actual
BF->Python transpiler is left as an exercise"*. This brief picks up that
gauntlet.

Two simultaneous goals on a single code path:

1. **Practical joke**: canonical-brainfuck-compatible dialect that lets you
   put `++++++[>++++++++<-]>.` in a `.py` file and run it.
2. **Pedagogic tool**: `bf_compile(src)` returns human-readable Python source,
   useful for understanding what a given brainfuck program does by rewriting
   it in a language a human can actually read.

The dialect activation just runs what `bf_compile` produces. The pedagogic
value is a consequence of insisting the compiled output be legible Python;
we do not maintain two compilation modes.

## Layout

```
unpythonic/dialects/bf.py                 # Tape, bf_compile, BF dialect class
unpythonic/dialects/tests/test_bf.py      # runtests() per existing convention
```

Matches the existing dialect-examples layout (one module per dialect, tests in
`dialects/tests/`).

## Public API

```python
from unpythonic.dialects.bf import dialects, BF   # dialect activation
from unpythonic.dialects.bf import bf_compile     # pedagogic / pure function
from unpythonic.dialects.bf import Tape           # exposed for testability
```

`__all__ = ["BF", "bf_compile", "Tape"]`.

## Design decisions (all confirmed in pre-build discussion)

### Dialect is source-level only

`BF` overrides `transform_source` and leaves `transform_ast` at its default
(returns `NotImplemented`). This is the whole point of the exercise — the
other dialects in the package already demonstrate `transform_ast` extensively.

A previous iteration of the design put `reset` behind a `@namemacro`, but
that conflicted with the pedagogic goal: the output of `bf_compile` must be
self-contained runnable Python, not a bare identifier that only resolves
during AST expansion. So `reset` is handled entirely in the source
transformer. This also keeps the dialect purely single-layer, which sharpens
the example.

### Cell semantics: 8-bit wrapping via a `Tape` class

```python
class Tape(defaultdict):
    def __init__(self):
        super().__init__(int)
    def __setitem__(self, key, value):
        super().__setitem__(key, value & 0xFF)
```

Because `tape[i] += n` desugars to `tape[i] = tape[i] + n`, overriding
`__setitem__` alone covers `=`, `+=`, `-=` uniformly. Masking at the setter
means the compiled body stays free of `& 0xFF` noise, which preserves
legibility.

Rationale for wrapping rather than using unbounded ints: compatibility with
canonical brainfuck programs that rely on `255 + 1 == 0`. The "Hello, World!"
superposition demands it.

### Tape structure: `defaultdict(int)`

`tape[ptr]` auto-extends in both directions (negative and positive indices)
and reads zero for untouched cells. No explicit size, no circular wrapping of
the pointer.

### EOF on `,` returns 0

Classical brainfuck has three conventions (`0`, `-1`, cell-unchanged). We
pick `0`. Documented in the module docstring.

### Folding

Consecutive *identical* command chars fold into one statement:

- `+++++++` → `tape[ptr] += 7`
- `>>>` → `ptr += 3`

No cancellation of opposites (`+-`, `><` do not annihilate). Compilation is
honest: what you wrote is what you get, just collapsed where collapse is
lossless.

### Loop structure

`[` → `while tape[ptr]:` plus indent; `]` → dedent. No label arithmetic.
Indentation carries the structure — the goto-hell of brainfuck becomes
ordinary Python `while` loops, which is already a pedagogic payoff on its
own.

### I/O

- `.` → `stdout.write(chr(tape[ptr])); stdout.flush()`
- `,` → reads one byte; EOF → 0

`stdin` and `stdout` are imported in the emitted prelude from `sys`.

### Comments — the "everything-not-a-command is a comment" rule

Classical brainfuck treats any non-command character as a no-op. We preserve
that semantics *and* the comment text: consecutive runs of non-command
characters compile into Python comments, positioned where they appeared in
the source.

Per-line handling:

- Line (stripped) equals `reset`: emit the reset block (see below).
- Otherwise, walk the line alternating between command runs and non-command
  runs:
  - Command runs emit folded statements.
  - Non-command runs, if they contain non-whitespace text, emit as
    `# <stripped text>` on their own output line, in position.
  - `[` and `]` govern indentation as described above.
- Fully-blank lines pass through; consecutive blanks collapse to one.

If a non-command run already begins with `# ` or `#`, one leading `#` (and
its trailing space) is stripped before we re-prepend `# `. This makes the
bf-author-style `# real comment` and the bare `real comment` both come out as
`# real comment` in the output. Uniform.

Example: `+++ move right >>>` compiles to

```python
tape[ptr] += 3
# move right
ptr += 3
```

### `reset` — source-level keyword

Triggered *only* when a line, stripped, equals exactly `reset`. Substrings
in longer comments (`"we reset here"`) do not trigger. Compiles to:

```python
# reset
tape.clear()
ptr = 0
```

Enables multiple brainfuck programs in the same file.

### Emitted prelude

Every compiled module starts with:

```python
from collections import defaultdict
from sys import stdin, stdout
from unpythonic.dialects.bf import Tape
tape = Tape()
ptr = 0
```

`bf_compile(src)` output is thus self-contained and runnable (given
`unpythonic` installed) without going through the dialect machinery.

## Testing

`unpythonic/dialects/tests/test_bf.py` with the usual `runtests()` entry
point. Coverage:

- **`bf_compile` snapshot tests**: fixed bf input → expected Python output,
  for a handful of inputs exercising folding, loops, comments, `reset`, and
  `#`-style comments.
- **`Tape` unit tests**: wrap at 256, negative indices, default zero.
- **End-to-end execution tests**: compile → exec → capture stdout. Programs:
  - `"Hello from bf!"` printer (parallels `"Hello from Lispython!"` etc.
    in sibling dialect tests — rewards the curious reader of CI logs).
  - A trivial multi-program file using `reset` between programs.
  - A small arithmetic-loop smoke test.
- **Dialect activation test**: a minimal bf-in-`.py` snippet loaded through
  the dialect machinery actually runs and produces the expected stdout.

No `cat`-style `,`-using test in the initial batch — stdin redirection for
the dialect-activated path is awkward and not worth the machinery for a
smoke test. A direct unit test of the compiled `,` behavior at the Python
level covers the semantics.

## Non-goals

- Optimization beyond run-folding. No `[-]` → `tape[ptr] = 0`, no balanced
  `[->+<]` → copy-loop recognition, no loop-invariant motion. Pedagogic
  transparency trumps cleverness.
- Arbitrary-precision cells. Canonical 8-bit behavior.
- Multiple tapes, variable cell widths, or any of the brainfuck-dialect
  extensions (`brainfuck++`, etc.).
- Error reporting beyond a single exception on unbalanced brackets during
  compilation.

## Delivery style

Conventional `unpythonic.dialects` module style — matter-of-fact
docstrings, commit messages, and test names. Module docstring treats
brainfuck as a target language; no commentary on the choice.
