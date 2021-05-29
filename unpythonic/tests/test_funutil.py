# -*- coding: utf-8 -*-

from ..syntax import macros, test, the  # noqa: F401
from ..test.fixtures import session, testset

from operator import add
from functools import partial

# `Values` is also tested where function composition utilities that use it are.
from ..funutil import call, callwith, Values, valuify

def runtests():
    with testset("@call (def as code block)"):
        # def as a code block (function overwritten by return value)
        @call
        def result():
            return "hello"
        test[result == "hello"]

        # use case 1: make temporaries fall out of scope
        @call
        def x():
            a = 2  # many temporaries that help readability...
            b = 3  # ...of this calculation, but would just pollute locals...
            c = 5  # ...after the block exits
            return a * b * c
        test[x == 30]

        # use case 2: multi-break out of nested loops
        @call
        def result():
            for x in range(10):
                for y in range(10):
                    if x * y == 42:
                        return (x, y)
                    ...  # more code here  # pragma: no cover
        test[result == (6, 7)]

        # can also be used normally
        test[the[call(add, 2, 3)] == the[add(2, 3)]]

    with testset("@callwith (argument freezer), and pythonic solutions to avoid it"):
        # to pass arguments when used as decorator, use @callwith instead
        @callwith(3)
        def result(x):
            return x**2
        test[result == 9]

        # specialize for given arguments, choose function later
        apply23 = callwith(2, 3)
        def myadd(a, b):
            return a + b
        def mymul(a, b):
            return a * b
        test[apply23(myadd) == 5]
        test[apply23(mymul) == 6]

        # callwith is not essential; we can do the same pythonically like this:
        a = [2, 3]
        test[myadd(*a) == 5]
        test[mymul(*a) == 6]

        # build up the argument list as we go
        #   - note curry does not help, must use partial; this is because curry
        #     will happily call "callwith" (and thus terminate the gathering step)
        #     as soon as it gets at least one argument.
        p1 = partial(callwith, 2)
        p2 = partial(p1, 3)
        p3 = partial(p2, 4)
        apply234 = p3()  # terminate gathering step by actually calling callwith
        def add3(a, b, c):
            return a + b + c
        def mul3(a, b, c):
            return a * b * c
        test[apply234(add3) == 9]
        test[apply234(mul3) == 24]

        # pythonic solution:
        a = [2]
        a += [3]
        a += [4]
        test[add3(*a) == 9]
        test[mul3(*a) == 24]

        # callwith in map, if we want to vary the function instead of the data
        m = map(callwith(3), [lambda x: 2 * x,
                              lambda x: x**2,
                              lambda x: x**(1 / 2)])
        test[tuple(m) == (6, 9, 3**(1 / 2))]

        # pythonic solution - use comprehension notation:
        m = (f(3) for f in [lambda x: 2 * x,
                            lambda x: x**2,
                            lambda x: x**(1 / 2)])
        test[tuple(m) == (6, 9, 3**(1 / 2))]

    # The `Values` abstraction is used by various parts of `unpythonic` that
    # deal with function composition; particularly `curry`, the `compose` and
    # `pipe` families, and the `with continuations` macro.
    with testset("Values (multiple-return-values, named return values)"):
        def f():
            return Values(1, 2, 3)
        result = f()
        test[isinstance(result, Values)]
        test[result.rets == (1, 2, 3)]
        test[not result.kwrets]
        test[result[0] == 1]
        test[result[:-1] == (1, 2)]
        a, b, c = result  # if no kwrets, can be unpacked like a tuple
        a, b, c = f()

        def g():
            return Values(x=3)  # named return value
        result = g()
        test[isinstance(result, Values)]
        test[not result.rets]
        test[result.kwrets == {"x": 3}]  # actually a `frozendict`
        test["x" in result]  # `in` looks in the named part
        test[result["x"] == 3]
        test[result.get("x", None) == 3]
        test[result.get("y", None) is None]
        test[tuple(result.keys()) == ("x",)]  # also `values()`, `items()`

        def h():
            return Values(1, 2, x=3)
        result = h()
        test[isinstance(result, Values)]
        test[result.rets == (1, 2)]
        test[result.kwrets == {"x": 3}]
        a, b = result.rets  # positionals can always be unpacked explicitly
        test[result[0] == 1]
        test["x" in result]
        test[result["x"] == 3]

        def silly_but_legal():
            return Values(42)
        result = silly_but_legal()
        test[result.rets[0] == 42]
        test[result.ret == 42]  # shorthand for single-value case

    with testset("valuify (convert tuple as multiple-return-values into Values)"):
        @valuify
        def f(x, y, z):
            return x, y, z
        test[isinstance(f(1, 2, 3), Values)]
        test[f(1, 2, 3) == Values(1, 2, 3)]

if __name__ == '__main__':  # pragma: no cover
    with session(__file__):
        runtests()
