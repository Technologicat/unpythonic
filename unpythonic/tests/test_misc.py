# -*- coding: utf-8 -*-

from ..syntax import macros, test, test_raises, the  # noqa: F401
from ..test.fixtures import session, testset

from collections import deque
from queue import Queue

from ..misc import (pack,
                    namelambda,
                    timer,
                    getattrrec, setattrrec,
                    Popper, CountingIterator,
                    slurp,
                    callsite_filename,
                    safeissubclass)
from ..fun import withself

def runtests():
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
