# -*- coding: utf-8 -*-

from ..syntax import macros, test, test_raises, the  # noqa: F401
from ..test.fixtures import session, testset

from collections import deque
import logging
import os
from queue import Queue
import sys
import tempfile

from ..misc import (pack,
                    namelambda,
                    timer,
                    getattrrec, setattrrec,
                    Popper, CountingIterator,
                    slurp,
                    callsite_filename,
                    safeissubclass,
                    maybe_open,
                    UnionFilter,
                    si_prefix)
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
        test[type(getattr(w, "x")) is Wrapper]
        test[type(getattrrec(w, "x")) is int]
        test[getattrrec(w, "x") == 42]

        setattrrec(w, "x", 23)
        test[type(getattr(w, "x")) is Wrapper]
        test[type(getattrrec(w, "x")) is int]
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

    # --------------------------------------------------------------------------
    # maybe_open

    with testset("maybe_open"):
        # With an actual file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as tmp:
            tmp.write("hello")
            tmpname = tmp.name
        try:
            with maybe_open(tmpname, "r", sys.stdin) as f:
                test[the[f.read()] == "hello"]
        finally:
            os.unlink(tmpname)

        # With None filename, yields the fallback stream
        import io
        fallback = io.StringIO("fallback content")
        with maybe_open(None, "r", fallback) as f:
            test[f is fallback]
            test[the[f.read()] == "fallback content"]

    # --------------------------------------------------------------------------
    # UnionFilter

    with testset("UnionFilter"):
        f1 = logging.Filter("myapp.core")
        f2 = logging.Filter("myapp.io")
        uf = UnionFilter(f1, f2)

        rec_core = logging.LogRecord("myapp.core.engine", logging.INFO,
                                     "", 0, "msg", (), None)
        rec_io = logging.LogRecord("myapp.io.disk", logging.INFO,
                                   "", 0, "msg", (), None)
        rec_other = logging.LogRecord("otherapp.main", logging.INFO,
                                      "", 0, "msg", (), None)

        test[uf.filter(rec_core)]
        test[uf.filter(rec_io)]
        test[not uf.filter(rec_other)]

        # Empty UnionFilter matches nothing
        empty = UnionFilter()
        test[not empty.filter(rec_core)]

    # --------------------------------------------------------------------------
    # si_prefix

    with testset("si_prefix"):
        # No prefix (magnitude in [1, 1000))
        test[the[si_prefix(0)] == "0.00"]
        test[the[si_prefix(42)] == "42.00"]
        test[the[si_prefix(999)] == "999.00"]

        # Large prefixes
        test[the[si_prefix(1000)] == "1.00 k"]
        test[the[si_prefix(1500)] == "1.50 k"]
        test[the[si_prefix(2_500_000)] == "2.50 M"]
        test[the[si_prefix(1e9)] == "1.00 G"]
        test[the[si_prefix(1e12)] == "1.00 T"]

        # Small prefixes
        test[the[si_prefix(0.001)] == "1.00 m"]
        test[the[si_prefix(0.0015)] == "1.50 m"]
        test[the[si_prefix(0.000001)] == "1.00 \N{MICRO SIGN}"]
        test[the[si_prefix(0.0000025)] == "2.50 \N{MICRO SIGN}"]
        test[the[si_prefix(1e-9)] == "1.00 n"]
        test[the[si_prefix(1e-12)] == "1.00 p"]

        # Negative numbers
        test[the[si_prefix(-1500)] == "-1.50 k"]
        test[the[si_prefix(-42)] == "-42.00"]
        test[the[si_prefix(-0.001)] == "-1.00 m"]

        # Custom precision
        test[the[si_prefix(1500, precision=0)] == "2 k"]
        test[the[si_prefix(1500, precision=4)] == "1.5000 k"]
        test[the[si_prefix(42, precision=1)] == "42.0"]

        # Binary (IEC) mode
        test[the[si_prefix(0, binary=True)] == "0.00"]
        test[the[si_prefix(500, binary=True)] == "500.00"]
        test[the[si_prefix(1024, binary=True)] == "1.00 Ki"]
        test[the[si_prefix(1536, binary=True)] == "1.50 Ki"]
        test[the[si_prefix(1024**2, binary=True)] == "1.00 Mi"]
        test[the[si_prefix(2.5 * 1024**2, binary=True)] == "2.50 Mi"]
        test[the[si_prefix(1024**3, binary=True)] == "1.00 Gi"]
        test[the[si_prefix(1024**4, binary=True)] == "1.00 Ti"]
        test[the[si_prefix(-1536, binary=True)] == "-1.50 Ki"]
        test[the[si_prefix(0.5, binary=True)] == "0.50"]

if __name__ == '__main__':  # pragma: no cover
    with session(__file__):
        runtests()
