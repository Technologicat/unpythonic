# -*- coding: utf-8 -*-
"""Extended if-expressions."""

from ...syntax import macros, aif, it, cond, local

def test():
    # Anaphoric if: aif[test, then, otherwise]
    # Magic identifier "it" refers to the test result.
    assert aif[2*21,
               "it is {}".format(it),
               "it is False"] == "it is 42"

    # Lispy "cond" - a human-readable multi-branch conditional for lambdas.
    answer = lambda x: cond[x == 2, "two",
                            x == 3, "three",
                            "something else"]
    assert answer(42) == "something else"

    # implicit do: in any part of aif or cond, use extra brackets for a do[] environment
    print("Testing aif/cond with implicit do")
    assert aif[[local(x << 2*21), 2*x],
               [print("hi"), "it is {}".format(it)],
               [print("ho"), "it is False"]] == "it is 84"

    # each "test" and "then" branch with multiple expressions should have its own
    # extra brackets. (Similarly for the final "otherwise" branch.)
    answer = lambda x: cond[[local(y << 2*x), y == 4], [print("hi again"), "two"],
                            x == 3, "three",
                            "something else"]
    assert answer(2) == "two"

    print("All tests PASSED")

if __name__ == '__main__':
    test()
