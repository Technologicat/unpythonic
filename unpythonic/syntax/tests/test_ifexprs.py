# -*- coding: utf-8 -*-
"""Extended if-expressions."""

from ...syntax import macros, test  # noqa: F401
from ...test.fixtures import session, testset

from ...syntax import macros, aif, it, cond, local  # noqa: F401, F811

def runtests():
    with testset("aif (anaphoric if, you're `it`!)"):
        # Anaphoric if: aif[test, then, otherwise]
        # Magic identifier "it" refers to the test result.
        test[aif[2 * 21,
                 f"it is {it}",
                 "it is False"] == "it is 42"]

    with testset("cond (lispy multi-branch conditional expression)"):
        answer = lambda x: cond[x == 2, "two",
                                x == 3, "three",
                                "something else"]
        test[answer(2) == "two"]
        test[answer(3) == "three"]
        test[answer(42) == "something else"]

    # implicit do: in any part of aif or cond, use extra brackets for a do[] environment
    with testset("integration with implicit do"):
        print("Testing aif/cond with implicit do")
        test[aif[[local[x << 2 * 21], 2 * x],  # noqa: F821, the `local[]` macro defines the name on the LHS of the `<<`.
                 [print("hi"), f"it is {it}"],
                 [print("ho"), "it is False"]] == "it is 84"]

        # each "test" and "then" branch with multiple expressions should have its own
        # extra brackets. (Similarly for the final "otherwise" branch.)
        answer = lambda x: cond[[local[y << 2 * x], y == 4], [print("hi again"), "two"],  # noqa: F821
                                x == 3, "three",
                                "something else"]
        test[answer(2) == "two"]
        test[answer(3) == "three"]
        test[answer(4) == "something else"]

if __name__ == '__main__':  # pragma: no cover
    with session(__file__):
        runtests()
