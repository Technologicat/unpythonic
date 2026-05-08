# -*- coding: utf-8 -*-
"""Test the befunge dialect: Playfield class, run, and dialect activation."""

import io
from contextlib import redirect_stdout

from mcpyrate.compiler import create_module, run as run_module

from ...syntax import macros, test, test_raises, the  # noqa: F401
from ...test.fixtures import session, testset

from ...misc import redirect_stdin
from ..befunge import Befunge, Playfield, UnknownOpcodeError, run  # noqa: F401


def _capture(src, *, seed=None, stdin=None):
    """Run a Befunge program; return captured stdout."""
    buf = io.StringIO()
    if stdin is not None:
        with redirect_stdout(buf), redirect_stdin(stdin):
            run(src, seed=seed)
    else:
        with redirect_stdout(buf):
            run(src, seed=seed)
    return buf.getvalue()


def runtests():
    with testset("Playfield class"):
        # Default: 80x25 of spaces.
        pf = Playfield()
        test[pf[(0, 0)] == ord(" ")]
        test[pf[(79, 24)] == ord(" ")]

        # Source shorter than 25 lines pads.
        pf = Playfield("ab\ncd")
        test[pf[(0, 0)] == ord("a")]
        test[pf[(1, 0)] == ord("b")]
        test[pf[(0, 1)] == ord("c")]
        test[pf[(1, 1)] == ord("d")]
        test[pf[(2, 0)] == ord(" ")]  # right-pad
        test[pf[(0, 24)] == ord(" ")]  # bottom-pad

        # Trailing blank lines stripped before count.
        pf = Playfield("a" + "\n" * 30)  # 1 row of "a", 30 trailing blanks
        test[pf[(0, 0)] == ord("a")]

        # >25 rows raises SyntaxError.
        too_tall = "\n".join(["x"] * 26)
        test_raises[SyntaxError, Playfield(too_tall)]

        # Line >80 cols raises SyntaxError.
        too_wide = "x" * 81
        test_raises[SyntaxError, Playfield(too_wide)]

        # OOB access (read and write).
        pf = Playfield("hi")
        test_raises[IndexError, pf[(80, 0)]]
        test_raises[IndexError, pf[(0, 25)]]
        test_raises[IndexError, pf[(-1, 0)]]
        test_raises[IndexError, pf[(0, -1)]]

        def _oob_write():
            pf[(80, 0)] = 42
        test_raises[IndexError, _oob_write()]

        # In-bounds write masks to byte.
        pf[(0, 0)] = 0x1FF
        test[pf[(0, 0)] == 0xFF]
        pf[(0, 0)] = -1
        test[pf[(0, 0)] == 0xFF]

    with testset("run: arithmetic"):
        # 9 5 - .  →  push 9, push 5, subtract, print int → "4 "
        test[_capture("95-.@") == "4 "]
        # Add, multiply, mod.
        test[_capture("23+.@") == "5 "]
        test[_capture("23*.@") == "6 "]
        test[_capture("73%.@") == "1 "]
        # Division by zero pushes 0 (per spec).
        test[_capture("50/.@") == "0 "]
        test[_capture("50%.@") == "0 "]
        # Logical not.
        test[_capture("0!.@") == "1 "]
        test[_capture("5!.@") == "0 "]
        # Greater-than.
        test[_capture("53`.@") == "1 "]
        test[_capture("35`.@") == "0 "]

    with testset("run: stack ops"):
        # : duplicate
        test[_capture("5:..@") == "5 5 "]
        # \ swap
        test[_capture("12\\..@") == "1 2 "]
        # $ discard
        test[_capture("12$.@") == "1 "]
        # Stack underflow returns 0.
        test[_capture(".@") == "0 "]
        test[_capture("+.@") == "0 "]  # 0 + 0

    with testset("run: string mode and char output"):
        # "A", prints 'A'.
        test[_capture('"A",@') == "A"]
        # Multi-char string mode.
        test[_capture('"!iH",,,@') == "Hi!"]

    with testset("run: trampoline #"):
        # # skips the next cell. Here, skip a `9` that would push 9.
        test[_capture("1#9.@") == "1 "]

    with testset("run: conditional direction _ and |"):
        # _ pops; 0 → east, nonzero → west.
        # `0_>1.@`: push 0, _ pops 0 → east, > east, push 1, print "1 ", halt.
        test[_capture("0_>1.@") == "1 "]

        # | pops; 0 → south, nonzero → north.
        # IP travels south to a v that keeps it going south, hitting `2.@`.
        prog = (
            "v\n"
            ">0|\n"
            "  v\n"
            "  2\n"
            "  .\n"
            "  @\n"
        )
        test[_capture(prog) == "2 "]

    with testset("run: ? random direction (seeded determinism)"):
        # Seed reaches the rng: same seed, same output.
        # Program `?@` halts whichever direction is chosen (toroidal wrap
        # eventually reaches @ at (1, 0) when going east).
        out_a = _capture("?@", seed=42)
        out_b = _capture("?@", seed=42)
        test[the[out_a] == out_b]

        # ? without seed: just verify it runs without error.
        # No assertion on output (nondeterministic).
        _capture("?@")

    with testset("run: p (put) and g (get)"):
        # Round-trip: put 65 at (3, 1), then get it back, print as char.
        # Stack layout for p: ..., v, x, y. We need: 65 (val), 3 (x), 1 (y).
        # Push 65 = '6' '5' '*' '+' won't be exact... Use string mode.
        # "A" pushes 65. Then push 3 (x), push 1 (y). p stores at (3, 1).
        # Then push 3 (x), push 1 (y). g reads, push value. , prints char.
        prog = '"A"31p31g,@'
        test[_capture(prog) == "A"]

        # OOB g → IndexError. Push x=99 (=9*11=99), y=0. Need x>=80.
        # 99* = 9, 9, * = push 81. Then 0, g → reads (81, 0). OOB.
        test_raises[IndexError, run("99*0g.@")]

        # OOB p → IndexError. Push v=0, x=81, y=0.
        test_raises[IndexError, run("099*0p@")]

    with testset("run: toroidal IP wrap"):
        # IP at (3, 0) going east hits @ before wrapping.
        # To exercise wrap: program at column 0..N where the @ is at col N,
        # but the IP needs to traverse.
        # Simplest: `v\n@` — IP at (0,0) `v` south, (0,1) `@` halt.
        # Wrap test: program at (0, 0) is `<`, redirect west. IP wraps to
        # (79, 0). Need @ somewhere on the wrap path.
        # `<` at col 0 → IP goes west, wraps to col 79.
        # Need to halt eventually. Place @ at col 79.
        prog = "<" + " " * 78 + "@"  # 80 chars: < at 0, spaces, @ at 79
        # IP at (0,0) `<` west, wrap to (79, 0) `@` halt.
        # Output: nothing.
        test[_capture(prog) == ""]

        # Vertical wrap.
        # IP at (0, 0) `^` north, wrap to (0, 24).
        # Place @ at (0, 24). Build 25-line program.
        prog = "^\n" + "\n".join([" "] * 23) + "\n@"
        test[_capture(prog) == ""]

    with testset("run: @ halts"):
        # Trivial halt; second @ never reached.
        test[_capture("@,@") == ""]

    with testset("run: unknown opcode"):
        # `Z` is not a Befunge command. Has to be reached as an instruction
        # (not in string mode). So just put it at (0, 0).
        test_raises[UnknownOpcodeError, run("Z")]

    with testset("run: & integer input and ~ char input"):
        # & reads whitespace-delimited int.
        test[_capture("&.@", stdin=io.StringIO("42\n")) == "42 "]
        # & EOF pushes 0.
        test[_capture("&.@", stdin=io.StringIO("")) == "0 "]
        # & with non-int: pushes 0.
        test[_capture("&.@", stdin=io.StringIO("abc\n")) == "0 "]

        # ~ reads one char.
        test[_capture("~,@", stdin=io.StringIO("X")) == "X"]
        # ~ EOF pushes 0.
        test[_capture("~.@", stdin=io.StringIO("")) == "0 "]

    with testset("run: Hello from Befunge!"):
        # Family-tradition Hello World, exercising string mode, the :#,_@
        # print loop, and toroidal westward re-entry through `>`.
        program = '"!egnufeB morf olleH">:#,_@'
        test[_capture(program) == "Hello from Befunge!"]

    with testset("Befunge dialect activation"):
        # A blank line between the dialect-import and the program is the
        # natural form. Without leading-blank-line stripping, that blank
        # line would become row 0 (all spaces) and the IP would loop
        # toroidally on it forever instead of reaching the program.
        src = (
            'from unpythonic.dialects.befunge import dialects, Befunge\n'
            '\n'
            '"!egnufeB morf olleH">:#,_@\n'
        )
        mod = create_module("_befunge_dialect_activation_test")
        buf = io.StringIO()
        with redirect_stdout(buf):
            run_module(src, mod)
        test[buf.getvalue() == "Hello from Befunge!"]


if __name__ == '__main__':
    with session(__file__):
        runtests()
