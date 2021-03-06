# -*- coding: utf-8 -*-
"""Implicit return statements."""

from ...syntax import macros, test, test_raises  # noqa: F401
from ...test.fixtures import session, testset

from ...syntax import macros, autoreturn  # noqa: F401, F811

from ...env import env

def runtests():
    # - in a function body, any expression "expr" in tail position
    #   (along any code path) is transformed to "return expr".
    # - if/elif/else, try/except/else/finally and "with" blocks are supported.
    # - a loop (for/else, while) in tail position is considered to always return None.
    #   - if you need a loop in tail position to have a return value,
    #     use an explicit return, or the constructs from unpythonic.fploop.
    # - any explicit return statements are left alone, so "return" can be used normally.
    with testset("basic usage"):
        with autoreturn:
            def f():
                "I'll just return this"
            test[f() == "I'll just return this"]

            def f2():
                return "I'll just return this"  # explicit return, not transformed
            test[f2() == "I'll just return this"]

    with testset("if, elif, else"):
        with autoreturn:
            def g(x):
                if x == 1:
                    "one"
                elif x == 2:
                    "two"
                else:
                    "something else"
            test[g(1) == "one"]
            test[g(2) == "two"]
            test[g(42) == "something else"]

    with testset("except, else"):
        with autoreturn:
            def h(x):
                try:
                    if x == 1:
                        raise ValueError("h doesn't like the number 'one'")
                except ValueError:
                    "error"  # there's a tail position in each "except" clause
                else:  # if an "else" clause is present in a try, the tail position of the main path is there
                    2 * x
            test[h(10) == 20]
            test[h(1) == "error"]

    with testset("except, body of the try"):
        with autoreturn:
            def h2(x):
                try:
                    if x == 1:
                        raise ValueError("h doesn't like the number 'one'")
                    x  # no else clause, the tail position of the main path is in the "try"
                except ValueError:
                    "error"  # also in this case there's a tail position in each "except" clause
            test[h2(10) == 10]
            test[h2(1) == "error"]

    with testset("with block"):
        with autoreturn:
            def ctx():
                with env(x="hi") as e:  # just need some context manager for testing, doesn't matter which
                    e.x  # tail position in a with block
            test[ctx() == "hi"]

    with testset("function definition"):  # v0.15.0+
        with autoreturn:
            def outer():
                def inner():
                    "inner function"
            test[callable(outer())]  # returned a function
            test[outer()() == "inner function"]

    with testset("class definition"):  # v0.15.0+
        with autoreturn:
            def classdefiner():
                class InnerClassDefinition:
                    pass
            test[isinstance(classdefiner(), type)]  # returned a class
            test[classdefiner().__name__ == "InnerClassDefinition"]

if __name__ == '__main__':  # pragma: no cover
    with session(__file__):
        runtests()
