# -*- coding: utf-8 -*-
"""Tests for `with test:` block forms — `expect[]`, `return` deprecation, error cases."""

from ...syntax import macros, test, test_raises, the, expect  # noqa: F401
from ...test.fixtures import session, testset

import warnings


def _expand(source, filename="<test_testingtools>"):
    """Expand `source` with macros active. Returns the expanded module AST."""
    import mcpyrate.activate  # noqa: F401
    from mcpyrate.compiler import expand
    return expand(source, filename)


_HEADER = """\
from unpythonic.syntax import macros, test, expect
from unpythonic.test.fixtures import session, testset
"""


def runtests():
    with testset("expect[] inside `with test:` block"):
        # Basic positive case: a `with test:` block declares its tested
        # expression via `expect[expr]`. Failure of the test wouldn't be
        # observed inside the block; success is the default contract.
        with test:
            x = 21
            expect[x + x == 42]

        # Comparison: implicit `the[]` is injected on the LHS, so the failure
        # message of an `expect[lhs == rhs]` would report the value of `lhs`.
        # Here we just assert the path runs.
        with test:
            value = "green tea"
            expect[value == "green tea"]

        # Explicit `the[]` inside `expect[]` overrides the implicit-LHS rule.
        with test:
            container = ["a", "b", "c"]
            expect["b" in the[container]]

        # No `expect[]` and no `return`: asserts the block completes normally.
        with test:
            x = 0
            for _ in range(3):
                x += 1
            # no expect[]

    with testset("expect[] error cases (caught at macro expansion)"):
        # Two `expect[]` in the same block — SyntaxError.
        src = _HEADER + """
def f():
    with test:
        expect[1 == 1]
        expect[2 == 2]
"""
        try:
            _expand(src, "<two-expects>")
        except Exception as e:
            cur = e
            while cur.__cause__ is not None:
                cur = cur.__cause__
            test[type(cur) is SyntaxError]
            test[the["at most one `expect[]`" in str(cur)]]
        else:
            test[False, "expected SyntaxError for two expect[]"]

        # `expect[]` and `return` together — SyntaxError.
        src = _HEADER + """
def f():
    with test:
        expect[1 == 1]
        return 2 == 2
"""
        try:
            _expand(src, "<both-forms>")
        except Exception as e:
            cur = e
            while cur.__cause__ is not None:
                cur = cur.__cause__
            test[type(cur) is SyntaxError]
            test[the["both `expect[]` and `return`" in str(cur)]]
        else:
            test[False, "expected SyntaxError for expect[] + return together"]

        # `expect[]` outside `with test:` — SyntaxError from the macro itself.
        src = _HEADER + """
expect[1 == 1]
"""
        try:
            _expand(src, "<bare-expect>")
        except Exception as e:
            cur = e
            while cur.__cause__ is not None:
                cur = cur.__cause__
            test[type(cur) is SyntaxError]
        else:
            test[False, "expected SyntaxError for bare expect[]"]

    with testset("`return` form emits DeprecationWarning at expansion time"):
        src = _HEADER + """
def f():
    with test:
        return 2 + 2 == 4
"""
        with warnings.catch_warnings(record=True) as captured:
            warnings.simplefilter("always")
            _expand(src, "<return-deprecation>")
        deprecations = [w for w in captured if issubclass(w.category, DeprecationWarning)]
        test[the[len(deprecations)] == 1]
        msg = str(deprecations[0].message)
        test[the["`return`" in msg and "deprecated" in msg and "expect[]" in msg]]
        # The warning carries the user-visible filename and line of the offending `return`.
        test[deprecations[0].filename == "<return-deprecation>"]
        # `_HEADER` is two lines, blank line ends it; `def f():` is line 4,
        # `with test:` is line 5, `return ...` is line 6.
        test[deprecations[0].lineno == 6]


if __name__ == '__main__':  # pragma: no cover
    with session(__file__):
        runtests()
