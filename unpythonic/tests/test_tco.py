# -*- coding: utf-8 -*-

from ..syntax import macros, test, test_raises, fail  # noqa: F401
from ..test.fixtures import session, testset, returns_normally

from sys import stderr
import gc

from ..tco import trampolined, jump

from ..ec import call_ec
from ..fun import withself
from ..let import letrec
from ..misc import timer

def runtests():
    with testset("tail recursion"):
        @trampolined
        def fact(n, acc=1):
            if n == 0:
                return acc
            return jump(fact, n - 1, n * acc)
        test[fact(4) == 24]

        # tail recursion in a lambda
        t = trampolined(withself(lambda self, n, acc=1:
                                 acc if n == 0 else jump(self, n - 1, n * acc)))
        test[t(4) == 24]
        test[returns_normally(t(5000))]  # no crash

    with testset("mutual tail recursion"):
        @trampolined
        def even(n):
            if n == 0:
                return True
            return jump(odd, n - 1)
        @trampolined
        def odd(n):
            if n == 0:
                return False
            return jump(even, n - 1)
        test[even(42) is True]
        test[odd(4) is False]
        test[even(10000) is True]  # no crash

        # trampolined lambdas in a letrec
        t = letrec(evenp=lambda e:
                         trampolined(lambda x:
                                       (x == 0) or jump(e.oddp, x - 1)),
                   oddp=lambda e:
                        trampolined(lambda x:
                                       (x != 0) and jump(e.evenp, x - 1)),
                   body=lambda e:
                        e.evenp(10000))
        test[t is True]

    # explicit continuations - DANGER: functional spaghetti code!
    with testset("functional spaghetti code"):
        class SpaghettiError(Exception):
            pass
        @trampolined
        def foo():
            return jump(bar)
        @trampolined
        def bar():
            return jump(baz)
        @trampolined
        def baz():
            raise SpaghettiError("Look at the call stack, bar() was zapped by TCO!")
        test_raises[SpaghettiError, foo()]

    with testset("integration with call_ec"):
        @trampolined
        @call_ec
        def withec(ec):
            ec(42)
        test[withec == 42]

    with testset("error cases"):
        # Printing a warning is the best some of these cases can do, unfortunately, due to how `__del__` works.
        print("*** These error cases SHOULD PRINT A WARNING:", file=stderr)

        print("** Attempted jump into an inert data value:", file=stderr)
        with test_raises[RuntimeError]:
            @trampolined
            def errorcase1():
                return jump(42)
            errorcase1()
        gc.collect()

        print("** No surrounding trampoline:", file=stderr)
        def bar2():
            fail["This line should not be reached."]  # pragma: no cover
        def foo2():
            return jump(bar2)
        foo2()
        gc.collect()  # Need to request garbage collection on PyPy, because otherwise no guarantee when it'll happen.

        print("** Missing 'return' in 'return jump':", file=stderr)
        def foo3():
            jump(bar2)
        foo3()
        gc.collect()  # Need to request garbage collection on PyPy, because otherwise no guarantee when it'll happen.

    # TODO: need some kind of benchmarking tools to do this properly.
    with testset("performance benchmark"):
        n = 100000

        with timer() as ip:
            for _ in range(n):
                pass

        with timer() as fp1:
            @trampolined
            def dowork(i=0):
                if i < n:
                    return jump(dowork, i + 1)
            dowork()

        print(f"do-nothing loop, {n:d} iterations:")
        print(f"  builtin for {ip.dt:g}s ({(ip.dt / n):g}s/iter)")
        print(f"  @trampolined {fp1.dt:g}s ({(fp1.dt / n):g}s/iter)")
        print(f"@trampolined slowdown {(fp1.dt / ip.dt):g}x")

if __name__ == '__main__':  # pragma: no cover
    with session(__file__):
        runtests()
