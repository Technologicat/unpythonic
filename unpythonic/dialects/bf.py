# -*- coding: utf-8 -*-
"""bf: the classical human-incomprehensible automaton as a Python dialect.

This module provides a `bf` → Python source-to-source compiler, wrapped
as an `mcpyrate` dialect so that a file ending in ``.py`` can contain
a `bf` program directly::

    from unpythonic.dialects.bf import dialects, BF

    ++++++++[>++++++++<-]>+.

Running the file (under `macropython`, or by `import`) compiles the body to
Python, then executes the result. The same compiler is also available as a
plain function::

    from unpythonic.dialects.bf import bf_compile
    print(bf_compile(bf_program_str))

This prints the Python that the dialect would run. Useful for the pedagogic
side of things — reading a non-trivial `bf` program by rewriting it in a
language a human can actually read.

Design

- **Cells**: 8-bit wrapping, `dict[int, int]` with `collections.defaultdict`
  semantics, implemented by the `Tape` class. The tape auto-extends in both
  directions; untouched cells read as zero.

- **Folding**: consecutive identical commands collapse (`+++` → `tape[ptr] +=
  3`). No cancellation of opposites (`+-`, `><` do **not** annihilate).
  What you wrote is what you get, just collapsed where collapse is lossless.

- **Loops**: `[` → `while tape[ptr]:` plus indent; `]` → dedent. An empty
  loop body (only comments or nothing) gets a `pass` to keep the output
  parseable as Python.

- **I/O**: `.` writes `chr(tape[ptr])` to `stdout`; `,` reads one character
  from `stdin`. On EOF, `,` stores 0 in the current cell.

- **Comments**: classical `bf` treats any non-command character as a no-op.
  We preserve the text: consecutive runs of non-command characters compile
  into Python `# ...` comments, positioned where they appeared in the source.
  If an author-written comment already begins with `# ` (or just `#`), one
  leading `#` is stripped before the compiler prepends its own, so
  ``# real comment`` and ``real comment`` both come out as ``# real comment``
  in the output.

- **`reset`**: a line whose stripped content is exactly ``reset`` compiles to
  ``tape.clear(); ptr = 0``. This lets several `bf` programs share a file.

- **Blank lines**: passed through, with consecutive blanks collapsed to one.
"""

__all__ = ["BF", "Tape", "bf_compile"]

from collections import defaultdict

from mcpyrate.dialects import Dialect, split_at_dialectimport


class Tape(defaultdict):
    """The `bf` Turing tape.

    A `defaultdict[int, int]` that masks assigned values to 0–255, giving the
    canonical 8-bit wrapping cells while leaving the pointer unbounded in
    either direction.
    """
    def __init__(self):
        super().__init__(int)

    def __setitem__(self, key, value):
        super().__setitem__(key, value & 0xFF)


def bf_compile(src: str) -> str:
    """Compile a `bf` program to Python source.

    `src` is the raw `bf` program text (no surrounding Python, no dialect
    import). The returned string is self-contained, runnable Python — it
    imports `Tape` from this module, initialises state, and performs the
    operations the `bf` program describes.
    """
    INDENT = "    "
    lines_out = []
    indent = 0
    loop_stack = []  # indices into lines_out of open `while tape[ptr]:` lines

    def emit(s: str = "") -> None:
        lines_out.append(INDENT * indent + s if s else "")

    def emit_run(cmd: str, count: int) -> None:
        if cmd == "+":
            emit(f"tape[ptr] += {count}")
        elif cmd == "-":
            emit(f"tape[ptr] -= {count}")
        elif cmd == ">":
            emit(f"ptr += {count}")
        elif cmd == "<":
            emit(f"ptr -= {count}")

    def emit_comment(buf: str) -> None:
        text = buf.strip()
        if not text:
            return
        # Strip one author-written leading `#` so we don't double it.
        if text.startswith("# "):
            text = text[2:]
        elif text.startswith("#"):
            text = text[1:]
        text = text.strip()
        if not text:
            return
        emit(f"# {text}")

    # Prelude
    emit("from sys import stdin, stdout")
    emit("from unpythonic.dialects.bf import Tape")
    emit("tape = Tape()")
    emit("ptr = 0")
    emit()
    prev_blank = True

    for raw_line in src.splitlines():
        stripped = raw_line.strip()

        if stripped == "reset":
            if indent != 0:
                raise SyntaxError("bf: `reset` is only valid at top level (outside all `[...]` loops)")
            emit("# reset")
            emit("tape.clear()")
            emit("ptr = 0")
            prev_blank = False
            continue

        if not stripped:
            if not prev_blank:
                emit()
                prev_blank = True
            continue

        cur_char = None  # last seen +/-/>/< command char in the current run
        cur_count = 0
        comment_buf = ""

        for ch in raw_line:
            if ch in "+-><":
                if comment_buf:
                    emit_comment(comment_buf)
                    comment_buf = ""
                if ch == cur_char:
                    cur_count += 1
                else:
                    if cur_char is not None:
                        emit_run(cur_char, cur_count)
                    cur_char = ch
                    cur_count = 1
            elif ch in "[].,":
                if comment_buf:
                    emit_comment(comment_buf)
                    comment_buf = ""
                if cur_char is not None:
                    emit_run(cur_char, cur_count)
                    cur_char = None
                    cur_count = 0
                if ch == "[":
                    emit("while tape[ptr]:")
                    loop_stack.append(len(lines_out) - 1)
                    indent += 1
                elif ch == "]":
                    if not loop_stack:
                        raise SyntaxError("bf: unmatched `]`")
                    while_idx = loop_stack.pop()
                    # Python requires a non-empty suite; emit `pass` if the
                    # loop body contained only comments (or nothing at all).
                    has_stmt = any(
                        ln.strip() and not ln.strip().startswith("#")
                        for ln in lines_out[while_idx + 1:]
                    )
                    if not has_stmt:
                        emit("pass")
                    indent -= 1
                elif ch == ".":
                    emit("stdout.write(chr(tape[ptr])); stdout.flush()")
                else:  # ch == ","
                    emit('tape[ptr] = ord(stdin.read(1) or "\\x00")')
            else:
                if cur_char is not None:
                    emit_run(cur_char, cur_count)
                    cur_char = None
                    cur_count = 0
                comment_buf += ch

        if cur_char is not None:
            emit_run(cur_char, cur_count)
        if comment_buf:
            emit_comment(comment_buf)

        prev_blank = False

    if loop_stack:
        raise SyntaxError("bf: unmatched `[`")

    while lines_out and lines_out[-1] == "":
        lines_out.pop()

    return "\n".join(lines_out) + "\n"


class BF(Dialect):
    """Brainfuck as a whole-module source-to-source transformer.

    Text before the dialect-import line is passed through unchanged (keeps
    the encoding declaration and module docstring intact); text after it
    is treated as `bf` source and compiled via `bf_compile`. Any other
    dialect-imports in the module are preserved so that further dialect
    processing can find them.
    """
    def transform_source(self, text):
        r = split_at_dialectimport(text, type(self).__name__, self.lineno)
        if r is None:
            return text
        prologue, other, body = r
        return prologue + "".join(other) + bf_compile(body)
