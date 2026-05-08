# -*- coding: utf-8 -*-
"""Test the bf dialect: Tape class, bf.compile, and dialect activation."""

import io
from contextlib import redirect_stdout

from mcpyrate.compiler import create_module, run

from ...syntax import macros, test, test_raises, the  # noqa: F401
from ...test.fixtures import session, testset

from ...misc import redirect_stdin
from ..bf import BF, Tape  # noqa: F401
from .. import bf  # for bf.compile (qualified to avoid shadowing builtins.compile)


def _print_string_program(s):
    """Hand-build a simple bf program that writes `s` using only cell 0.

    Not optimal (no multiplication loops), but unambiguously correct and
    exercises run-folding on long `+` / `-` sequences.
    """
    parts = []
    cur = 0
    for ch in s:
        diff = ord(ch) - cur
        if diff > 0:
            parts.append("+" * diff)
        elif diff < 0:
            parts.append("-" * (-diff))
        parts.append(".")
        cur = ord(ch)
    return "".join(parts)


def _run_bf(src):
    """Compile `src` and exec it, returning the captured stdout."""
    buf = io.StringIO()
    code = bf.compile(src)
    ns = {}
    with redirect_stdout(buf):
        exec(compile(code, "<bf-compiled>", "exec"), ns)
    return buf.getvalue()


def runtests():
    with testset("Tape class"):
        t = Tape()
        # Default zero.
        test[t[0] == 0]
        test[t[999] == 0]
        test[t[-5] == 0]

        # Assignment masks to 0-255.
        t[0] = 256
        test[t[0] == 0]
        t[0] = 257
        test[t[0] == 1]
        t[0] = -1
        test[t[0] == 255]

        # += / -= go through __setitem__, so they wrap too.
        t2 = Tape()
        t2[0] += 300
        test[t2[0] == 44]  # 300 & 0xFF
        t2[0] = 0
        t2[0] -= 1
        test[t2[0] == 255]

        # clear() resets.
        t2[7] = 42
        t2.clear()
        test[t2[7] == 0]

    with testset("bf.compile: folding"):
        out = bf.compile("+++")
        test["tape[ptr] += 3" in the[out]]
        out = bf.compile("-----")
        test["tape[ptr] -= 5" in the[out]]
        out = bf.compile(">>>>")
        test["ptr += 4" in the[out]]
        out = bf.compile("<<")
        test["ptr -= 2" in the[out]]

    with testset("bf.compile: no cancellation of opposites"):
        # `+-` does not cancel: two separate runs, honest compilation.
        out = bf.compile("+-")
        test["tape[ptr] += 1" in the[out]]
        test["tape[ptr] -= 1" in the[out]]
        # `><` same.
        out = bf.compile("><")
        test["ptr += 1" in the[out]]
        test["ptr -= 1" in the[out]]

    with testset("bf.compile: loops"):
        out = bf.compile("[+]")
        test["while tape[ptr]:" in the[out]]
        test["tape[ptr] += 1" in the[out]]

        # Empty loop body becomes `pass` (Python requires a non-empty suite).
        out = bf.compile("[]")
        test["while tape[ptr]:" in the[out]]
        test["pass" in the[out]]

        # Comment-only body also needs `pass`.
        out = bf.compile("[ comment only ]")
        test["# comment only" in the[out]]
        test["pass" in the[out]]

        # Nested loops.
        out = bf.compile("[[+]]")
        # Two while statements, with deeper indent on the inner one.
        test[out.count("while tape[ptr]:") == 2]
        test["        tape[ptr] += 1" in the[out]]  # 8-space indent (nested)

    with testset("bf.compile: I/O"):
        out = bf.compile(".")
        test["stdout.write(chr(tape[ptr]))" in the[out]]
        out = bf.compile(",")
        test["stdin.read(1)" in the[out]]
        # EOF convention: empty string fallback to "\x00".
        test['"\\x00"' in the[out]]

    with testset("bf.compile: comments"):
        # Non-command text on its own line becomes a Python comment.
        out = bf.compile("hello world\n+")
        test["# hello world" in the[out]]
        test["tape[ptr] += 1" in the[out]]

        # Inline comment between command runs.
        out = bf.compile("+++ move right >>>")
        lines = out.splitlines()
        # Expect: `tape[ptr] += 3`, then `# move right`, then `ptr += 3`.
        idx_plus = next(i for i, ln in enumerate(lines) if "tape[ptr] += 3" in ln)
        idx_cmt = next(i for i, ln in enumerate(lines) if "# move right" in ln)
        idx_gt = next(i for i, ln in enumerate(lines) if "ptr += 3" in ln)
        test[the[idx_plus] < the[idx_cmt] < the[idx_gt]]

        # Author-written `#` comment does not get doubled.
        out = bf.compile("# a note\n+")
        test["# a note" in the[out]]
        test["# # a note" not in the[out]]

    with testset("bf.compile: reset"):
        out = bf.compile("+\nreset\n+")
        # Reset emits a labeled block.
        test["# reset" in the[out]]
        test["tape.clear()" in the[out]]
        test["ptr = 0" in the[out]]
        # Both `+` commands are present.
        test[out.count("tape[ptr] += 1") == 2]

        # reset inside a loop is an error.
        test_raises[SyntaxError, bf.compile("[\nreset\n]")]

        # reset as substring of a longer word does NOT trigger.
        out = bf.compile("# we may reset here eventually\n+")
        test["tape.clear()" not in the[out]]

    with testset("bf.compile: errors"):
        test_raises[SyntaxError, bf.compile("[")]
        test_raises[SyntaxError, bf.compile("]")]
        test_raises[SyntaxError, bf.compile("[[]")]

    with testset("bf.compile: execution — classic P-printer"):
        # `++++++++[>++++++++++<-]>.` — the standard building block.
        # Sets cell 1 to 8 * 10 = 80, then prints chr(80) = 'P'.
        out = _run_bf("++++++++[>++++++++++<-]>.")
        test[out == "P"]

    with testset("bf.compile: execution — single-cell string printer"):
        out = _run_bf(_print_string_program("Hi!"))
        test[out == "Hi!"]

        # The marquee test — rewards the curious CI-log reader.
        out = _run_bf(_print_string_program("Hello from bf!"))
        test[out == "Hello from bf!"]

    with testset("bf.compile: execution — reset between programs"):
        # Two programs in one file, separated by `reset`.
        # First prints 'A' (65), second prints 'B' (66).
        src = "+" * 65 + ".\nreset\n" + "+" * 66 + "."
        out = _run_bf(src)
        test[out == "AB"]

    with testset("bf.compile: execution — input with EOF"):
        # `,.` reads one char and echoes it.
        code = bf.compile(",.")
        ns = {}
        # Feed one char, then EOF.
        buf = io.StringIO()
        with redirect_stdout(buf), redirect_stdin(io.StringIO("Z")):
            exec(compile(code, "<bf-input>", "exec"), ns)
        test[buf.getvalue() == "Z"]

        # Empty stdin → EOF → cell stays 0 → `.` prints chr(0).
        buf = io.StringIO()
        with redirect_stdout(buf), redirect_stdin(io.StringIO("")):
            exec(compile(code, "<bf-eof>", "exec"), ns)
        test[buf.getvalue() == "\x00"]

    with testset("BF dialect activation"):
        # Run a small bf-in-Python program through the full dialect pipeline.
        src = ("from unpythonic.dialects.bf import dialects, BF\n"
               "\n"
               + _print_string_program("Hello from bf!"))
        mod = create_module("_bf_dialect_activation_test")
        buf = io.StringIO()
        with redirect_stdout(buf):
            run(src, mod)
        test[buf.getvalue() == "Hello from bf!"]


if __name__ == '__main__':
    with session(__file__):
        runtests()
