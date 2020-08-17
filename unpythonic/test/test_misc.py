# -*- coding: utf-8 -*-

from ..syntax import macros, test, test_raises  # noqa: F401
from .fixtures import testset

from operator import add
from functools import partial
from collections import deque
from sys import float_info
from queue import Queue
from time import sleep
import threading

from ..misc import (call, callwith, raisef, tryf, pack, namelambda, timer,
                    getattrrec, setattrrec, Popper, CountingIterator, ulp, slurp,
                    async_raise)
from ..fun import withself
from ..env import env

def runtests():
    with testset("unpythonic.misc"):
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
                        ...  # more code here
            test[result == (6, 7)]

            # can also be used normally
            test[call(add, 2, 3) == add(2, 3)]

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

        # raisef: raise an exception from an expression position
        with testset("raisef (raise exception from an expression)"):
            myfunc = lambda: raisef(ValueError("all ok"))  # the argument works the same as in `raise ...`
            test_raises[ValueError, myfunc()]
            try:
                myfunc()
            except ValueError as err:
                test[err.__cause__ is None]  # like plain `raise ...`, no cause set (default behavior)

            # using the `cause` parameter, raisef can also perform a `raise ... from ...`
            exc = TypeError("oof")
            myfunc = lambda: raisef(ValueError("all ok"), cause=exc)
            test_raises[ValueError, myfunc()]
            try:
                myfunc()
            except ValueError as err:
                test[err.__cause__ is exc]  # cause specified, like `raise ... from ...`

            # raisef with old-style parameters (as of v0.14.2, deprecated, will be dropped in v0.15.0)
            myfunc = lambda: raisef(ValueError, "all ok")
            test_raises[ValueError, myfunc()]

        # tryf: handle an exception in an expression position
        with testset("tryf (try/except/finally in an expression)"):
            test[tryf(lambda: "hello") == "hello"]
            test[tryf(lambda: "hello",
                      elsef=lambda: "there") == "there"]
            test[tryf(lambda: myfunc(),
                      (ValueError, lambda: "got a ValueError")) == "got a ValueError"]
            test[tryf(lambda: "hello",
                      (ValueError, lambda: "got a ValueError"),
                      elsef=lambda: "there") == "there"]
            test[tryf(lambda: raisef(ValueError("oof")),
                      (TypeError, lambda: "got a TypeError"),
                      ((TypeError, ValueError), lambda: "got a TypeError or a ValueError"),
                      (ValueError, lambda: "got a ValueError")) == "got a TypeError or a ValueError"]

            e = env(finally_ran=False)
            test[e.finally_ran is False]
            test[tryf(lambda: "hello",
                      elsef=lambda: "there",
                      finallyf=lambda: e << ("finally_ran", True)) == "there"]
            test[e.finally_ran is True]

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

        # Unit in the Last Place, float utility
        # https://en.wikipedia.org/wiki/Unit_in_the_last_place
        with testset("ulp (unit in the last place; float utility)"):
            eps = float_info.epsilon
            test[ulp(1.0) == eps]
            # test also at some base-2 exponent switch points
            test[ulp(2.0) == 2 * eps]
            test[ulp(0.5) == 0.5 * eps]

        with testset("slurp"):
            q = Queue()
            for k in range(10):
                q.put(k)
            test[slurp(q) == list(range(10))]

        # async_raise - evil ctypes hack to inject an asynchronous exception into another running thread
        with testset("async_raise"):
            try:
                # Test whether the Python we're running on provides ctypes. At least CPython and PyPy3 do.
                # For PyPy3, the general rule is "if it imports, it should work", so let's go along with that.
                import ctypes  # noqa: F401
                out = []  # box, really, but let's not depend on unpythonic.collections in this unrelated unit test module
                def test_async_raise_worker():
                    try:
                        for j in range(10):
                            sleep(0.1)
                    except KeyboardInterrupt:  # normally, KeyboardInterrupt is only raised in the main thread
                        pass
                    out.append(j)
                t = threading.Thread(target=test_async_raise_worker)
                t.start()
                sleep(0.1)  # make sure we're in the while loop
                async_raise(t, KeyboardInterrupt)
                t.join()
                test[out[0] < 9]  # terminated early due to the injected KeyboardInterrupt
            except NotImplementedError:
                test[False, "async_raise not supported on this Python interpreter."]

if __name__ == '__main__':
    runtests()
