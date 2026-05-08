# CC Brief: `befunge` — a source-level dialect for Befunge-93

## Goal

Add a new dialect `unpythonic.dialects.befunge` that compiles Befunge-93
source into a thin Python shim that invokes a runtime interpreter. Lands
as the second pedagogic example of `mcpyrate`'s `transform_source` hook,
complementing `unpythonic.dialects.bf`.

## Why a second `transform_source` example

`bf` already covers the basic territory: an exotic 1-D source language
gets rewritten into legible, structured Python. Loops in brainfuck are
lexically nested, the language is essentially linear, and `bf_compile`
output reads as Python the way a textbook bf-to-Python translation would.

Befunge-93 deliberately doesn't fit that mould:

- **2-D playfield** with the IP moving in four directions. There is no
  syntactic loop structure for `transform_source` to lower to a `while`.
- **Self-modifying code** via `p` (put) and `g` (get). At "compile time"
  no static analysis can tell what a cell *means*: the same cell may be
  entered going east as a digit and going north as a string-mode quote,
  and may be overwritten mid-run.
- **`?` random direction**, **string mode (`"`)**, **`#` skip-next**, and
  the toroidal grid all conspire so that control flow is fundamentally
  IP-driven, not lexical.

So `compile` cannot produce Python that mirrors the program. The honest
compilation strategy is: emit a one-line shim that hands the playfield
text to a runtime interpreter shipped in this module.

That makes Befunge a *complementary* example, not a redundant one.
Where `bf` demonstrates `transform_source` as a transpiler — exotic
syntax in, structured Python out — Befunge demonstrates `transform_source`
as a *reader* for non-Python-flavored, non-line-oriented source: the
playfield is data, the interpreter does the work, and the dialect's job
is to wrap the file body in a single function call. The contrast is
the teaching value.

The module docstring states this contrast explicitly. We do not pretend
the compiled output is informative the way `bf`'s is.

## Layout

```
unpythonic/dialects/befunge.py                 # Playfield, run, Befunge dialect class
unpythonic/dialects/tests/test_befunge.py      # runtests() per existing convention
```

Same shape as `bf`, mirroring the existing dialect-examples convention
(one module per dialect, tests in `dialects/tests/`).

## Public API

```python
from unpythonic.dialects.befunge import dialects, Befunge   # dialect activation
from unpythonic.dialects.befunge import run                 # programmatic entry point
from unpythonic.dialects.befunge import Playfield           # exposed for testability
from unpythonic.dialects.befunge import UnknownOpcodeError        # raised on unknown opcode
```

`__all__ = ["Befunge", "UnknownOpcodeError", "Playfield", "run"]`.

`run(src, *, seed=None)` is the only public entry point with kwargs,
and `seed` is the single irreducible kwarg — see "I/O capture" below for
why `stdin` and `stdout` are *not* kwargs.

## Prerequisite — separate prior commit: rename `bf_compile` → `compile`

Before the Befunge work lands, do a tiny standalone commit on the `bf`
dialect:

- `bf_compile` → `compile` in `unpythonic/dialects/bf.py`.
- Update `__all__`, the dialect class's `transform_source`, the module
  docstring, and the test imports in `unpythonic/dialects/tests/test_bf.py`.

Rationale:

- `unpythonic.dialects.bf.compile(src)` reads better than `bf_compile`;
  the `bf_` prefix duplicates the module name.
- `mcpyrate.compiler.compile` sets the precedent — fleet consistency.
- `bf.py` doesn't itself call `builtins.compile` anywhere, so shadowing
  inside the module is harmless. The module docstring will recommend
  qualified access via `from unpythonic.dialects import bf` followed by
  `bf.compile(src)`, matching the project-wide `from … import …` import
  style, rather than `from … import compile` (which would shadow the
  builtin in the importer's namespace).
- `bf_compile` is only public in 2.2.0-dev (not yet released), so the
  rename costs nothing in compatibility terms.

After the rename: `bf` exports `compile` and `befunge` exports `run`.
Symmetric in style: the public function in each dialect module is named
for what that dialect's pedagogic entry point actually does — `bf`
compiles to Python; `befunge` runs an interpreter.

## Design decisions

### Dialect is source-level only

`Befunge` overrides `transform_source` and leaves `transform_ast` at its
default (returns `NotImplemented`). Same as `bf` — the whole point of
this and the `bf` example is to demonstrate `transform_source`.

### Strict Befunge-93

Canonical behavior, not a relaxed superset:

- **80×25 grid**, fixed.
- **Byte-valued cells** (0–255), wrapping on `p` (put masks `value & 0xFF`).
- **Stack of unbounded Python `int`s.** The 93 spec is fuzzy on stack
  width; Python `int` is the natural idiom and matches how integers
  behave elsewhere in `unpythonic`. Cells stay byte-valued — that part
  is non-negotiable.
- **IP wraparound is toroidal.** Off the right edge → column 0 of the
  same row, etc. Canonical.
- **Stack underflow on `pop`** returns 0. Canonical.

### Out-of-bounds grid access raises `IndexError`

Both `g` (read) and `p` (write) raise `IndexError` if the requested
`(x, y)` falls outside the 80×25 grid.

Rationale:

- Strict-93 says the grid *is* 80×25; there is no "outside" to read
  zeros from. The "OOB read returns 0" convention is from Befunge-98,
  which we are explicitly not implementing.
- Symmetric policy is easier to document and reason about: same
  boundary, same reaction.
- Surfaces bugs in computed-coordinate arithmetic (off-by-one in
  stack juggling) instead of silently returning 0.
- The stack-underflow=0 precedent doesn't push toward returning 0
  here: stack underflow is *in* the 93 spec; OOB grid access is
  *un*specified.

The IP itself never goes OOB — the toroidal wraparound is a separate
concern and applies only to IP movement, not to `g`/`p`.

### `?` random direction — seedable

`run(src, *, seed=None)`. Internally:

```python
import random
rng = random.Random(seed)
# `?` does: dx, dy = rng.choice([(1,0), (-1,0), (0,1), (0,-1)])
```

`random.Random(seed)` as an *instance* — does not touch the global RNG,
so a Befunge program can't perturb the user's process-wide random state.
`seed=None` gives normal nondeterminism (OS entropy via `Random()`'s
default behavior).

`seed` is a kwarg because there is no stdlib mechanism to "redirect
`random.Random()` instances at a distance" — the seed has to be
injected at the call site.

### I/O — operator semantics differ from bf

In Befunge the four I/O commands have distinct integer-vs-character
flavors:

- `.` pops and prints an **integer** (followed by a space, per spec).
- `,` pops and prints a **character** (`chr(value & 0xFF)`).
- `&` reads a whitespace-delimited integer from stdin and pushes it.
- `~` reads one character from stdin and pushes its `ord`.

EOF on `&` and `~` pushes 0. Matches `bf`'s EOF=0 convention.

The module docstring calls out that `.` and `,` swap roles relative to
`bf` — readers comparing the two examples could otherwise be tripped up.

### I/O capture — no `stdin`/`stdout` kwargs

`run` does not take `stdin` or `stdout` kwargs. Tests capture I/O
through stdlib mechanisms (or, for stdin, the unpythonic gap-filler —
see next subsection):

- stdout: `redirect_stdout(io.StringIO())` (from `contextlib`) around
  the call.
- stdin: `redirect_stdin(io.StringIO("..."))` (from `unpythonic`) around
  the call.

Rationale: `seed` is irreducible (no stdlib equivalent), but
`stdin`/`stdout` redirection is a solved problem at the stream level.
Adding kwargs solely for I/O capture would expand the API surface
without giving the caller anything they can't already do with a
context manager. `bf` already follows this approach; `befunge` matches.

### Prerequisite — separate prior commit: `unpythonic.misc.redirect_stdin`

`contextlib` ships `redirect_stdout` (3.4) and `redirect_stderr` (3.5),
but not `redirect_stdin`. This is the textbook "stdlib almost gets it
right, then punts" pattern that unpythonic's gap-filling charter targets.
`tests/test_bf.py` already has a local `_redirect_stdin` helper for
this; the Befunge tests are about to need the same, and an obvious
recurring use case elsewhere puts this past the bar for promotion.

Add it to `unpythonic.misc`, alongside the other small stdlib
gap-fillers (`maybe_open`, `UnionFilter`, `si_prefix`, `timer`,
`safeissubclass`):

Subclass `contextlib._RedirectStream` directly. Yes, the underscore
makes it private API — but `_RedirectStream` was extracted in 3.5
specifically so that `redirect_stdout` and `redirect_stderr` could
share machinery, and its shape has been stable across every release
since. unpythonic's floor is 3.10, so we're well downstream of any
shake-out. We're explicitly the third sibling; using the same
machinery is the most honest expression of that.

```python
from contextlib import _RedirectStream

class redirect_stdin(_RedirectStream):
    """Context manager that redirects ``sys.stdin`` to *target*.

    The third sibling: `contextlib` ships `redirect_stdout` (3.4) and
    `redirect_stderr` (3.5), but punted on `redirect_stdin`. This
    fills the gap, sharing `contextlib._RedirectStream` machinery so
    behavior matches its stdlib siblings exactly — including the
    per-instance stack that supports nested re-entry on the same
    instance.

    Like its stdlib siblings, this redirects the global ``sys.stdin``
    and is **not** safe under concurrent use from multiple threads —
    parallel redirects from different threads will stomp on each other.
    For tests (the primary use case), single-threaded use is the norm.
    """
    _stream = "stdin"
```

Thread safety note: matches stdlib's choice deliberately. A truly
thread-aware variant would need `sys.stdin` replaced by a proxy that
dispatches per-thread (similar in spirit to `unpythonic.dynassign.dyn`
but at the file-like-object level), and that's a different abstraction
worth its own design discussion — not a refinement of this gap-filler.

Same commit:

- Add to `unpythonic/misc.py`; update `__all__`.
- Re-export from top-level `unpythonic/__init__.py` (already happens
  via `from .misc import *`).
- Add `redirect_stdin` unit tests in `unpythonic/tests/test_misc.py`
  (basic redirect, exception path restores `sys.stdin`, nested redirects
  on the same instance unwind correctly).
- Add a documentation entry under the **Other** section of
  `doc/features.md`, alongside `maybe_open` and `environ_override` —
  fellow stdlib gap-fillers in the same file/stream/process-state
  category. Both the navigation TOC link near the top of the file and
  the per-feature subsection later in the file.
- Replace the local `_redirect_stdin` helper in
  `unpythonic/dialects/tests/test_bf.py` with the public function.
- CHANGELOG entry under 2.2.0 "Added".

### Documentation in the prologue — prefer a module docstring

Befunge-93 has no comment syntax; `#` is a real command (skip-next-cell).
Trying to recognize Python comments inside the body would necessarily
involve guessing — any rule like "lines starting with `# ` are Python
comments" is a heuristic that picks a convention rather than a clean
parse. We don't do this.

The unambiguous answer is: **commentary goes above the dialect-import
line.** `split_at_dialectimport` preserves the prologue verbatim as
Python text, so anything before the dialect-import is plain Python.

The *recommended* form is a **module docstring**, not stand-alone `#`
comments. A docstring shows up in `help(module)`, so a Befunge program
imported as a Python module documents itself the same way any other
Python module does:

```python
"""Hello from Befunge!

Demonstrates string-mode push, the ":#,_@" print loop, and the v/^
vertical IP-redirect cells.
"""

from unpythonic.dialects.befunge import dialects, Befunge

<the actual Hello-from-Befunge program — to be hand-written and
 verified during implementation>
```

`# noqa` / Python-tooling directives go in the prologue too, as
ordinary Python comments — same boundary, same machinery.

The canonical "how to use" example in this module's docstring will
be the docstring-headed form; bare-comment files still work but are
the less idiomatic choice.

Nothing supports comments inside the body or after the program —
Befunge has no end-of-program textual marker (`@` is a *runtime*
halt), so trailing comments are equally ambiguous.

### `transform_source` body

Following `bf`'s shape, with `split_at_dialectimport`:

```python
class Befunge(Dialect):
    def transform_source(self, text):
        r = split_at_dialectimport(text, type(self).__name__, self.lineno)
        if r is None:
            return text
        prologue, other, body = r
        body = _strip_leading_blank_lines(body)
        shim = (
            "from unpythonic.dialects.befunge import run\n"
            f"run({body!r})\n"
        )
        return prologue + "".join(other) + shim


def _strip_leading_blank_lines(text: str) -> str:
    lines = text.splitlines(keepends=True)
    while lines and not lines[0].strip():
        lines.pop(0)
    return "".join(lines)
```

**Leading blank lines must be stripped.** A typical dialect-activated
file looks like:

```python
"""Hello, World."""

from unpythonic.dialects.befunge import dialects, Befunge

>25*"!dlrow ,olleH":v
...
```

`split_at_dialectimport` returns `body` starting at the line *after* the
dialect-import — including the blank line that separates it from the
program. If we don't strip, that blank line becomes row 0 of the
playfield (all spaces); the IP starts at `(0, 0)` going east, walks
80 no-op cells, wraps toroidally back to `(0, 0)`, and loops forever.

The strip is *line-level*: lines whose stripped form is empty get
removed from the start of `body`. **Leading spaces inside a non-blank
line are preserved** — those are meaningful no-op cells in the
playfield and column alignment matters. Trailing blank lines are not
stripped (harmless; `Playfield(src)` pads to 25 rows anyway).

The playfield text is then embedded as a string literal via `repr()`,
which handles escaping and preserves every remaining character verbatim,
including in-line whitespace.

### `Playfield` class

```python
class Playfield:
    """Strict Befunge-93 playfield: 80×25 byte cells.

    Reads and writes outside the grid raise `IndexError`. Used by the
    interpreter, and exposed publicly so that grid layout, padding,
    truncation, and OOB policy can be unit-tested in isolation from
    the interpreter loop.
    """
    WIDTH = 80
    HEIGHT = 25

    def __init__(self, src: str = ""): ...
    def __getitem__(self, xy: tuple[int, int]) -> int: ...
    def __setitem__(self, xy: tuple[int, int], value: int) -> None: ...
```

The constructor parses `src`:

- Split on newlines.
- Strip leading and trailing entirely-blank lines (in-line leading
  spaces on a non-blank line are preserved — those are no-op cells).
- If the remaining line count exceeds 25, raise
  `SyntaxError("befunge: program exceeds 25-row grid (got N rows)")`.
- If any line exceeds 80 characters, raise
  `SyntaxError("befunge: line K exceeds 80-column grid (got M cols)")`.
- Otherwise: pad with blank rows up to 25, right-pad each line with
  spaces to 80.
- Cells store `ord(ch) & 0xFF` (academic for ASCII source, keeps the
  contract uniform with `__setitem__`).

**Why `SyntaxError`, not silent truncation.** Strict Befunge-93's
grid is fixed at 80×25; an oversize program *is not* Befunge-93.
Silent truncation could drop the `@` halt and turn a finite program
into an infinite loop — the worst possible failure mode (a program
that compiles, runs, and never returns). Failing loudly at compile/
load time is symmetric with the runtime `IndexError` policy for
out-of-grid `g`/`p`: out-of-grid is an error, period.

### `run(src, *, seed=None)`

The interpreter loop. Pseudo-code:

```python
def run(src: str, *, seed: int | None = None) -> None:
    import sys
    rng = random.Random(seed)
    pf = Playfield(src)
    stack: list[int] = []
    def push(v): stack.append(v)
    def pop(): return stack.pop() if stack else 0

    x, y = 0, 0
    dx, dy = 1, 0
    string_mode = False

    while True:
        cell = pf[(x, y)]
        ch = chr(cell)
        if string_mode:
            if ch == '"':
                string_mode = False
            else:
                push(cell)
        else:
            # dispatch on ch: digits, + - * / % ! `, < > ^ v ?, _ |, " :, \\, $, ., ,, &, ~, #, p, g, @, space
            ...
        x = (x + dx) % Playfield.WIDTH
        y = (y + dy) % Playfield.HEIGHT
        if ch == '@':  # halt — handled inside dispatch by `return`
            break
```

(Halt actually short-circuits inside the dispatch with `return`; the
sketch is illustrative.)

Operator coverage — the full Befunge-93 set:

| Char            | Meaning                                                |
|-----------------|--------------------------------------------------------|
| `0`–`9`         | push digit                                             |
| `+ - * / %`     | arithmetic; `/` and `%` by zero push 0 (per spec)      |
| `!`             | logical not                                            |
| `` ` ``         | greater-than                                           |
| `> < ^ v`       | set IP direction                                       |
| `?`             | random direction (uses `rng`)                          |
| `_`             | horizontal if: pop; if 0 go right, else left           |
| `\|`            | vertical if: pop; if 0 go down, else up                |
| `"`             | toggle string mode                                     |
| `:`             | duplicate top                                          |
| `\\`            | swap top two                                           |
| `$`             | discard top                                            |
| `.`             | pop, print int + space                                 |
| `,`             | pop, print char (`chr(value & 0xFF)`)                  |
| `&`             | read int, push                                         |
| `~`             | read char, push `ord`                                  |
| `#`             | trampoline: skip next cell                             |
| `p`             | put: pop y, x, v; `pf[(x, y)] = v`                     |
| `g`             | get: pop y, x; push `pf[(x, y)]`                       |
| `@`             | halt                                                   |
| (space)         | no-op                                                  |

Anything else: raise `UnknownOpcodeError(f"unknown command at ({x}, {y}): {ch!r}")`.
Strict mode — Befunge-93 has a fixed command set, and silently treating
unknowns as no-ops would hide source-corruption bugs.

`UnknownOpcodeError` is a custom exception subclassing `RuntimeError`. The
case for inventing a type rather than reusing a stdlib one: this is a
VM hitting an unknown opcode, which doesn't fit any stdlib category
cleanly — `SyntaxError` is reserved by convention for parse-time use,
`RuntimeError` is too generic, `ValueError` doesn't quite match
("inappropriate value" is a stretch for "byte at this cell isn't a
command"). The pattern is "stdlib has no clean fit for the domain
concept, so define a domain exception": `pickle.UnpicklingError` and
`struct.error` follow the same principle.

Subclassing `RuntimeError` keeps blanket runtime-error catchers
working; the specific class enables targeted `except UnknownOpcodeError`.

This error fires at *runtime*, not at `Playfield(src)` load time. A
Befunge source can be entirely valid (every cell is printable ASCII)
yet contain a cell that's never a recognized command. Self-modifying
code (`p`) can also write arbitrary bytes into cells. Detection
necessarily happens when the IP actually visits the cell as an
instruction.

Three distinct error categories, three distinct conditions:

- `SyntaxError` — source-level malformation at `Playfield(src)`
  construction (oversize grid). Pre-execution.
- `IndexError` — out-of-grid runtime access via `g`/`p`. Sequence-subscript
  convention.
- `UnknownOpcodeError` — in-grid byte at the IP isn't a recognized command.
  Runtime, custom domain exception.

Each picks the most precise type available; we only invent where
stdlib has no clean answer.

## Testing

`unpythonic/dialects/tests/test_befunge.py`, with the usual `runtests()`
entry point. Coverage:

- **`Playfield` unit tests**:
  - 80×25 dimensions; default-blank cells read as `ord(' ')`.
  - Source shorter than 25 lines pads with blank rows.
  - Source with >25 lines raises `SyntaxError`.
  - Lines shorter than 80 cols right-pad with spaces.
  - Lines longer than 80 cols raise `SyntaxError`.
  - Trailing blank lines are stripped before the dimension check
    (so a 25-line program with a trailing blank line still loads).
  - OOB read raises `IndexError`.
  - OOB write raises `IndexError`.
  - In-bounds write masks to byte (`pf[(0, 0)] = 0x1FF; pf[(0, 0)] == 0xFF`).

- **Interpreter unit tests** via direct `run` calls with captured stdout:
  - Arithmetic: `9 5 - .` style.
  - String mode: `"!dlroW">:#,_@`-style print loop.
  - Stack ops: `:`, `\\`, `$`.
  - `#` trampoline.
  - `_` and `|` conditional direction.
  - `?` with seeded rng — assert deterministic output for fixed seed.
  - `p` / `g` round-trip on in-bounds coordinates.
  - `g` / `p` raise `IndexError` for OOB coordinates.
  - Toroidal IP wrap (program at `x = 79` moving east lands at `x = 0`).
  - Empty stack underflow returns 0.
  - `@` halts.
  - Unknown command raises `UnknownOpcodeError`.

- **`Hello from Befunge!`**: a custom Hello World matching the
  Lispython / Pytkell / bf family tradition. Rewards the curious reader
  of CI logs, and exercises the full machinery — string mode, the
  `:#,_@` print loop, vertical IP-redirect cells, halt.

- **Dialect activation test**: a minimal Befunge-in-`.py` snippet
  loaded through the dialect machinery (`mcpyrate.compiler.create_module`
  + `run`, same idiom as `test_bf.py`) actually executes and produces
  the expected stdout. Cover the realistic case with **a blank line
  between the dialect-import and the program** — verifies the
  leading-blank-line strip; without it the program would loop
  forever on a blank row 0.

- **`&` / `~` smoke test** using `redirect_stdin` (public, from
  `unpythonic`, added in commit 1); EOF returns 0.

## Non-goals

- Befunge-98 features: unbounded grid, multiple IPs, stack-of-stacks,
  fingerprints, `k` (iterate), etc. Strict-93 only.
- Optimization. The interpreter is a clean dispatch loop. No JIT, no
  basic-block caching, no peephole optimizations, no static analysis
  of common Befunge idioms. (And in any case, full Befunge static
  analysis is defeated by `p` — self-modifying code can change a cell
  between any two visits, so a pre-execution analysis can never be
  sound for general programs.) Pedagogic transparency trumps cleverness,
  same call as `bf`.
- Compile-time tracing or partial evaluation. Befunge-93 is Turing
  complete; symbolic execution at compile time would over-promise and
  under-deliver, and would conflate compilation with interpretation
  in a way `bf` deliberately avoided.
- A `befunge_compile` (or `compile`) function that returns a Python
  source string. The shim's only content is `run(src!r)`, which has no
  pedagogic value to expose as a separate API.

## Delivery style

Conventional `unpythonic.dialects` module style — matter-of-fact
docstrings, commit messages, and test names, matching `bf` and the
other sibling dialect modules. The `transform_source` contrast with
`bf` is presented as a design observation in the module docstring.

## Milestone

2.2.0. Three commits:

1. `unpythonic.misc.redirect_stdin` + tests + CHANGELOG; replace the
   local helper in `test_bf.py`.
2. `bf` rename: `bf_compile` → `compile` (small, isolated).
3. Befunge dialect: module + tests + CHANGELOG entry.

Commits 1 and 2 are mutually independent; both must land before
commit 3. All three on `master` for the in-progress 2.2.0 release.
Memory's "Queued for the 2.2.0 release" list grows accordingly.
