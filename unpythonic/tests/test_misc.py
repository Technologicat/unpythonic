# -*- coding: utf-8 -*-

from ..syntax import macros, test, test_raises, error, warn, the  # noqa: F401
from ..test.fixtures import session, testset

from operator import add
from functools import partial
from collections import deque
from queue import Queue

from ..misc import (call, callwith,
                    pack,
                    namelambda,
                    timer,
                    getattrrec, setattrrec,
                    Popper, CountingIterator,
                    slurp,
                    callsite_filename,
                    safeissubclass)
from ..fun import withself

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
        m = map(callwith(3), [lambda x: 2 * x, lambda x: x**2, lambda x: x**(1 / 2)])
        test[tuple(m) == (6, 9, 3**(1 / 2))]

        # pythonic solution - use comprehension notation:
        m = (f(3) for f in [lambda x: 2 * x, lambda x: x**2, lambda x: x**(1 / 2)])
        test[tuple(m) == (6, 9, 3**(1 / 2))]

    with testset("pack"):
        myzip = lambda lol: map(pack, *lol)
        lol = ((1, 2), (3, 4), (5, 6))
        test[tuple(myzip(lol)) == ((1, 3, 5), (2, 4, 6))]

    with testset("namelambda"):
        square = lambda x: x**2
        test[square.__code__.co_name == "<lambda>"]
        test[square.__name__ == "<lambda>"]
        test[square.__qualname__ == "runtests.<locals>.<lambda>"]
        square = namelambda("square")(square)
        test[square.__code__.co_name == "square"]
        test[square.__name__ == "square"]
        test[square.__qualname__ == "runtests.<locals>.square"]

        # CAUTION: in case of nested lambdas, the inner doesn't see the outer's new name:
        nested = namelambda("outer")(lambda: namelambda("inner")(withself(lambda self: self)))
        test[nested.__qualname__ == "runtests.<locals>.outer"]
        test[nested().__qualname__ == "runtests.<locals>.<lambda>.<locals>.inner"]

        # TODO: Can't raise TypeError; @fploop et al. do-it-now-and-replace-def-with-result
        # TODO: decorators need to do this.
        test[namelambda("renamed")(42) == 42]  # not a function

    # simple performance timer as a context manager
    with testset("timer"):
        with timer() as tictoc:
            for _ in range(int(1e6)):
                pass
        test[tictoc.dt > 0]  # elapsed time in seconds (float)

        with timer(p=True):  # auto-print mode for convenience
            for _ in range(int(1e6)):
                pass

    # access underlying data in an onion of wrappers
    with testset("getattrrec, setattrrec (de-onionizers)"):
        class Wrapper:
            def __init__(self, x):
                self.x = x

        w = Wrapper(Wrapper(42))
        test[type(getattr(w, "x")) == Wrapper]
        test[type(getattrrec(w, "x")) == int]
        test[getattrrec(w, "x") == 42]

        setattrrec(w, "x", 23)
        test[type(getattr(w, "x")) == Wrapper]
        test[type(getattrrec(w, "x")) == int]
        test[getattrrec(w, "x") == 23]

    # pop-while iterator
    with testset("Popper (pop-while iterator)"):
        inp = deque(range(5))  # efficiency: deque can popleft() in O(1) time
        out = []
        for x in Popper(inp):
            out.append(x)
        test[inp == deque([])]
        test[out == list(range(5))]

        inp = deque(range(3))
        out = []
        for x in Popper(inp):
            out.append(x)
            if x < 10:
                inp.appendleft(x + 10)
        test[inp == deque([])]
        test[out == [0, 10, 1, 11, 2, 12]]

        # works for a list, too, although not efficient (pop(0) takes O(n) time)
        inp = list(range(5))
        out = []
        for x in Popper(inp):
            out.append(x)
        test[inp == []]
        test[out == list(range(5))]

    # iterator that counts how many items have been yielded (as a side effect)
    with testset("CountingIterator"):
        inp = range(5)
        it = CountingIterator(inp)
        test[it.count == 0]
        _ = list(it)
        test[it.count == 5]

        inp = range(5)
        it = CountingIterator(inp)
        test[it.count == 0]
        for k, _ in enumerate(it, start=1):
            test[it.count == k]
        test[it.count == 5]

    with testset("slurp (drain a queue into a list)"):
        q = Queue()
        for k in range(10):
            q.put(k)
        test[slurp(q) == list(range(10))]

    with testset("callsite_filename"):
        test["test_misc.py" in the[callsite_filename()]]

    # Like issubclass, but if `cls` is not a class, swallow the `TypeError` and return `False`.
    with testset("safeissubclass"):
        class MetalBox:
            pass
        class PlasticBox:
            pass
        class Safe(MetalBox):
            pass
        test[safeissubclass(Safe, MetalBox)]
        test[not safeissubclass(Safe, PlasticBox)]
        test[safeissubclass(Safe, (PlasticBox, MetalBox))]
        test[not safeissubclass("definitely not a class", MetalBox)]

if __name__ == '__main__':  # pragma: no cover
    with session(__file__):
        runtests()
