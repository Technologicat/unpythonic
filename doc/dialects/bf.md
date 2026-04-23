**Navigation**

- [README](../../README.md)
- [Pure-Python feature set](../features.md)
- [Syntactic macro feature set](../macros.md)
- [Examples of creating dialects using `mcpyrate`](../dialects.md)
  - [Lispython](lispython.md)
  - [Listhell](listhell.md)
  - [Pytkell](pytkell.md)
  - **BF**
- [REPL server](../repl.md)
- [Troubleshooting](../troubleshooting.md)
- [Design notes](../design-notes.md)
- [Essays](../essays.md)
- [Additional reading](../readings.md)
- [Contribution guidelines](../../CONTRIBUTING.md)

<!-- markdown-toc start - Don't edit this section. Run M-x markdown-toc-refresh-toc -->
**Table of Contents**

- [BF: the classical human-incomprehensible automaton](#bf-the-classical-human-incomprehensible-automaton)
    - [Features](#features)
    - [What BF is](#what-bf-is)
    - [Comboability](#comboability)
    - [CAUTION](#caution)
    - [Etymology?](#etymology)

<!-- markdown-toc end -->

# BF: the classical human-incomprehensible automaton

A [BF](https://en.wikipedia.org/wiki/Brainfuck) program, compiled to Python.

Powered by [`mcpyrate`](https://github.com/Technologicat/mcpyrate/) and `unpythonic`.

```python
from unpythonic.dialects.bf import dialects, BF  # noqa: F401

# 'A' via a 5 × 13 multiplication loop
+++++++++++++[>+++++<-]>.
```

## Features

  - **Cell semantics**: 8-bit wrapping cells. The tape is a `defaultdict[int, int]` subclass (`unpythonic.dialects.bf.Tape`) whose `__setitem__` masks assigned values to the range `0..255`. The pointer is unbounded in either direction; untouched cells read as zero.
  - **Folding**: consecutive identical commands collapse (`+++` → `tape[ptr] += 3`). No cancellation of opposites — `+-` and `><` emit both operations, what you wrote is what you get.
  - **Loops**: `[` compiles to `while tape[ptr]:` plus an indent; `]` dedents. An empty loop body gets a `pass`.
  - **I/O**: `.` writes `chr(tape[ptr])` to `stdout`; `,` reads one character from `stdin`. On EOF, `,` stores `0` in the current cell.
  - **Comments**: classical BF treats any non-command character as a no-op. The dialect preserves the text — consecutive runs of non-command characters compile into Python `# ...` comments, positioned where they appeared in the source. A leading `# ` in the BF source is passed through cleanly, so both `# real comment` and bare `real comment` come out as `# real comment` in the compiled Python.
  - **`reset`**: a line whose stripped content is exactly `reset` compiles to `tape.clear(); ptr = 0`. This lets several BF programs share one file.

The same compiler is available as a plain function:

```python
from unpythonic.dialects.bf import bf_compile
print(bf_compile(bf_program_str))
```

`bf_compile(src)` returns self-contained runnable Python — useful for reading a non-trivial BF program by rewriting it in a language a human can actually read.

## What BF is

BF is a dialect of Python implemented as a whole-module *source-to-source* transform. The dialect definition lives in [`unpythonic.dialects.bf`](../../unpythonic/dialects/bf.py). Usage examples can be found in [the unit tests](../../unpythonic/dialects/tests/test_bf.py).

It's also a minimal example of how to make a **source-transforming** dialect, the modern equivalent of what old Lisp folks used to call a *reader macro*. All other dialects in this collection — Lispython, Listhell, Pytkell — are AST-transforming, built on top of `unpythonic`'s macro layer. BF shares none of that machinery: the body of a BF file is not parseable as Python at all, so the compiler runs at the text level, before `mcpyrate`'s AST-level dialect stage. It picks up a line from `mcpyrate`'s own `Dialect.transform_source` docstring: *"Implementing the actual BF->Python transpiler is left as an exercise"*.

## Comboability

Source-transforming dialects consume the whole module body, so combining BF with another source-transforming dialect on the same file doesn't really make sense. Composition with **AST-transforming** dialects is supported: `from X import dialects, BF, SomeOptimizer` (or on separate `from` lines) places `SomeOptimizer` after BF in the transform chain, running its AST pass on the output of the BF compiler.

The mechanism is the `mcpyrate.dialects.split_at_dialectimport` helper (new in `mcpyrate` 4.1.0): BF's `transform_source` uses it to peel off its own dialect-import line while preserving any others for the next round of dialect processing.

## CAUTION

Not intended for serious use.

## Etymology?

Wikipedia has [more on the name](https://en.wikipedia.org/wiki/Brainfuck#Etymology) than is strictly appropriate here.
