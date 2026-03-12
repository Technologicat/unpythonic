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

    with testset("match/case"):  # Python 3.10+
        with autoreturn:
            def classify(x):
                match x:
                    case 1:
                        "one"
                    case 2:
                        "two"
                    case _:
                        "other"
            test[classify(1) == "one"]
            test[classify(2) == "two"]
            test[classify(42) == "other"]

            def classify_nested(x):
                match x:
                    case (a, b):
                        a + b
                    case [a, b, *rest]:
                        a + b + sum(rest)
                    case _:
                        0
            test[classify_nested((3, 4)) == 7]
            test[classify_nested([1, 2, 3, 4]) == 10]
            test[classify_nested("nope") == 0]

            def classify_with_guard(x):
                match x:
                    case n if n < 0:
                        "negative"
                    case 0:
                        "zero"
                    case n if n > 0:
                        "positive"
            test[classify_with_guard(-5) == "negative"]
            test[classify_with_guard(0) == "zero"]
            test[classify_with_guard(7) == "positive"]

if __name__ == '__main__':  # pragma: no cover
    with session(__file__):
        runtests()
