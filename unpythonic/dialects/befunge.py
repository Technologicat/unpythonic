# -*- coding: utf-8 -*-
"""befunge: Befunge-93 as a Python dialect.

Activate via::

    \"\"\"Hello from Befunge!\"\"\"

    from unpythonic.dialects.befunge import dialects, Befunge

    "!egnufeB morf olleH">:#,_@

The body of a `befunge`-dialect file is parsed as a Befunge-93 playfield
and run by a runtime interpreter shipped in this module.

Unlike `unpythonic.dialects.bf`, the compiled output is a thin shim — the
dialect's `transform_source` wraps the playfield text in a single call to
`run`. Befunge's semantics live in this module's interpreter, by necessity:

- The IP moves in two dimensions on a fixed 80×25 toroidal playfield.
- `p` (put) lets a program rewrite its own cells at runtime, so no
  static analysis of the playfield can be sound.
- Control flow is fundamentally IP-driven: `?` random direction,
  `_`/`|` direction-from-stack, `#` skip-next, string mode (`"`).

Where `bf`'s `compile` produces structured Python that mirrors the program,
`befunge`'s `transform_source` produces only an interpreter invocation.
That contrast is itself the pedagogic value of having two dialects.

I/O operator names differ from `bf`. In Befunge:

- `.` pops and prints an integer (followed by a space, per spec)
- `,` pops and prints a character (`chr(value & 0xFF)`)
- `&` reads a whitespace-delimited integer from stdin and pushes it
- `~` reads one character from stdin and pushes its `ord`

EOF on `&` and `~` pushes 0 (matches `bf`'s convention).

Errors

- `SyntaxError` — source-level malformation at `Playfield(src)` construction
  (more than 25 rows, any line longer than 80 columns).
- `IndexError` — runtime out-of-grid access via `g`/`p`. The IP itself
  never goes out of grid; its motion wraps toroidally.
- `UnknownOpcodeError` — runtime: the IP visited a cell whose byte value
  isn't a recognized Befunge command. Subclasses `RuntimeError`.

Stack and cells

- Stack: unbounded Python `int`s. Underflow on pop returns 0 (per spec).
- Playfield cells: bytes (0–255). `p` masks the stored value to a byte;
  `g` returns the byte value.

Random direction (`?`)

The `?` command picks a direction with `random.Random`, an instance kept
per `run` call. ``run(src, *, seed=...)`` lets tests pin the RNG for
deterministic output; ``seed=None`` uses OS entropy.
"""

__all__ = ["Befunge", "Playfield", "UnknownOpcodeError", "run"]

import random
import sys

from mcpyrate.dialects import Dialect, split_at_dialectimport


WIDTH = 80
HEIGHT = 25


class UnknownOpcodeError(RuntimeError):
    """Raised when the Befunge interpreter visits a cell with no
    recognized command, including bytes written by `p` that don't
    map to any opcode.

    Subclasses ``RuntimeError`` so blanket runtime-error catchers still
    work; the specific class enables targeted ``except UnknownOpcodeError``.
    """


class Playfield:
    """Strict Befunge-93 playfield: 80×25 cells, byte-valued.

    Cells outside the grid raise ``IndexError`` on both read and write.
    The grid is fixed; the IP wraps toroidally during motion (handled
    by `run`, not by this class).

    Exposed for unit testing the layout and out-of-bounds policy in
    isolation from the interpreter loop.
    """
    WIDTH = WIDTH
    HEIGHT = HEIGHT

    def __init__(self, src: str = "") -> None:
        lines = src.splitlines()
        # Strip leading and trailing entirely-blank lines. In-line leading
        # spaces on a non-blank line are preserved — those are no-op cells.
        while lines and not lines[0].strip():
            lines.pop(0)
        while lines and not lines[-1].strip():
            lines.pop()
        if len(lines) > HEIGHT:
            raise SyntaxError(
                f"befunge: program exceeds {HEIGHT}-row grid (got {len(lines)} rows)"
            )
        for k, ln in enumerate(lines):
            if len(ln) > WIDTH:
                raise SyntaxError(
                    f"befunge: line {k} exceeds {WIDTH}-column grid (got {len(ln)} cols)"
                )
        # Pad to HEIGHT rows of WIDTH bytes; default-blank cells read as ord(' ').
        self._cells = bytearray(b" " * (WIDTH * HEIGHT))
        for y, ln in enumerate(lines):
            for x, ch in enumerate(ln):
                self._cells[y * WIDTH + x] = ord(ch) & 0xFF

    def __getitem__(self, xy: tuple) -> int:
        x, y = xy
        if not (0 <= x < WIDTH and 0 <= y < HEIGHT):
            raise IndexError(f"befunge: cell ({x}, {y}) out of grid")
        return self._cells[y * WIDTH + x]

    def __setitem__(self, xy: tuple, value: int) -> None:
        x, y = xy
        if not (0 <= x < WIDTH and 0 <= y < HEIGHT):
            raise IndexError(f"befunge: cell ({x}, {y}) out of grid")
        self._cells[y * WIDTH + x] = value & 0xFF


_DIRECTIONS = ((1, 0), (-1, 0), (0, 1), (0, -1))  # E, W, S, N


def run(src: str, *, seed: int = None) -> None:
    """Run a Befunge-93 program.

    `src` is the playfield text. Output goes to ``sys.stdout``; input
    is read from ``sys.stdin``.

    `seed` (keyword-only, default ``None``) seeds the RNG used by `?`.
    Pass an explicit integer for deterministic output in tests; leave at
    ``None`` for normal nondeterminism via OS entropy.
    """
    rng = random.Random(seed)
    pf = Playfield(src)
    stack: list = []

    def push(v: int) -> None:
        stack.append(v)

    def pop() -> int:
        return stack.pop() if stack else 0

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
        elif ch == '@':
            return
        elif "0" <= ch <= "9":
            push(int(ch))
        elif ch == "+":
            b = pop()
            a = pop()
            push(a + b)
        elif ch == "-":
            b = pop()
            a = pop()
            push(a - b)
        elif ch == "*":
            b = pop()
            a = pop()
            push(a * b)
        elif ch == "/":
            # Per spec: division by zero pushes 0.
            b = pop()
            a = pop()
            push(a // b if b != 0 else 0)
        elif ch == "%":
            b = pop()
            a = pop()
            push(a % b if b != 0 else 0)
        elif ch == "!":
            push(0 if pop() != 0 else 1)
        elif ch == "`":
            b = pop()
            a = pop()
            push(1 if a > b else 0)
        elif ch == ">":
            dx, dy = 1, 0
        elif ch == "<":
            dx, dy = -1, 0
        elif ch == "v":
            dx, dy = 0, 1
        elif ch == "^":
            dx, dy = 0, -1
        elif ch == "?":
            dx, dy = rng.choice(_DIRECTIONS)
        elif ch == "_":
            dx, dy = (1, 0) if pop() == 0 else (-1, 0)
        elif ch == "|":
            dx, dy = (0, 1) if pop() == 0 else (0, -1)
        elif ch == '"':
            string_mode = True
        elif ch == ":":
            v = pop()
            push(v)
            push(v)
        elif ch == "\\":
            b = pop()
            a = pop()
            push(b)
            push(a)
        elif ch == "$":
            pop()
        elif ch == ".":
            sys.stdout.write(f"{pop()} ")
        elif ch == ",":
            sys.stdout.write(chr(pop() & 0xFF))
        elif ch == "&":
            # Read a whitespace-delimited integer from stdin.
            # EOF or unparseable input pushes 0.
            c = sys.stdin.read(1)
            while c and c.isspace():
                c = sys.stdin.read(1)
            if not c:
                push(0)
            else:
                buf = c
                while True:
                    c = sys.stdin.read(1)
                    if not c or c.isspace():
                        break
                    buf += c
                try:
                    push(int(buf))
                except ValueError:
                    push(0)
        elif ch == "~":
            c = sys.stdin.read(1)
            push(ord(c) if c else 0)
        elif ch == "#":
            # Trampoline: skip the next cell. Advance one extra step now.
            x = (x + dx) % WIDTH
            y = (y + dy) % HEIGHT
        elif ch == "p":
            py = pop()
            px = pop()
            v = pop()
            pf[(px, py)] = v
        elif ch == "g":
            py = pop()
            px = pop()
            push(pf[(px, py)])
        elif ch == " ":
            pass
        else:
            raise UnknownOpcodeError(
                f"befunge: unknown command at ({x}, {y}): {ch!r}"
            )

        x = (x + dx) % WIDTH
        y = (y + dy) % HEIGHT


def _strip_leading_blank_lines(text: str) -> str:
    lines = text.splitlines(keepends=True)
    while lines and not lines[0].strip():
        lines.pop(0)
    return "".join(lines)


class Befunge(Dialect):
    """Befunge-93 as a whole-module source-to-source transformer.

    Text before the dialect-import line is passed through unchanged
    (keeps the encoding declaration and module docstring intact); text
    after it is treated as a Befunge-93 playfield and embedded verbatim
    into a call to `run`. Any other dialect-imports in the module are
    preserved so further dialect processing can find them.

    Leading entirely-blank lines in the body are stripped before the
    playfield is built — without this, the blank line that typically
    follows the dialect-import would become row 0 (all spaces), the IP
    would walk a no-op row toroidally forever, and the program would
    never reach its first instruction.
    """
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
