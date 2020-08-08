# -*- coding: utf-8 -*-
"""Multi-expression lambdas with implicit do; named lambdas."""

from ...syntax import (macros, multilambda, namedlambda, quicklambda, f, _,  # noqa: F401
                       envify, local, let, curry, autoreturn)

from functools import wraps

# Not really redefining "curry". The first one went into MacroPy's macro registry,
# and this one is a regular run-time function.
# (Although this does mean the docstring of the macro will not be accessible from here.)
from ...fun import withself, curry  # noqa: F811
from ...tco import trampolined, jump
from ...fploop import looped_over

def test():
    with multilambda:
        # use brackets around the body of a lambda to denote a multi-expr body
        echo = lambda x: [print(x), x]
        assert echo("hi there") == "hi there"

        count = let((x, 0))[  # noqa: F821, the `let` macro defines `x` here.
                  lambda: [x << x + 1,  # noqa: F821
                           x]]  # redundant, but demonstrating multi-expr body.  # noqa: F821
        assert count() == 1
        assert count() == 2

        test = let((x, 0))[  # noqa: F821
                 lambda: [x << x + 1,      # x belongs to the surrounding let  # noqa: F821
                          local[y << 42],  # y is local to the implicit do  # noqa: F821
                          (x, y)]]  # noqa: F821
        assert test() == (1, 42)
        assert test() == (2, 42)

        myadd = lambda x, y: [print("myadding", x, y),
                              local[tmp << x + y],  # noqa: F821, `local[]` defines the name on the LHS of the `<<`.
                              print("result is", tmp),  # noqa: F821
                              tmp]  # noqa: F821
        assert myadd(2, 3) == 5

        # only the outermost set of brackets denote a multi-expr body:
        t = lambda: [[1, 2]]
        assert t() == [1, 2]

    with namedlambda:
        f1 = lambda x: x**3                      # assignment: name as "f1"
        assert f1.__name__ == "f1"
        gn, hn = let((x, 42), (g, None), (h, None))[[  # noqa: F821
                       g << (lambda x: x**2),               # env-assignment: name as "g"  # noqa: F821
                       h << f1,                        # still "f1" (RHS is not a literal lambda)  # noqa: F821
                       (g.__name__, h.__name__)]]      # noqa: F821
        assert gn == "g"
        assert hn == "f1"

        foo = let[(f7, lambda x: x) in f7]       # let-binding: name as "f7"  # noqa: F821
        assert foo.__name__ == "f7"

        # function call with named arg
        def foo(func1, func2):
            assert func1.__name__ == "func1"
            assert func2.__name__ == "func2"
        foo(func1=lambda x: x**2,  # function call with named arg: name as "func1"
            func2=lambda x: x**2)  # function call with named arg: name as "func2"

        def bar(func1, func2):
            assert func1.__name__ == "<lambda>"
            assert func2.__name__ == "<lambda>"
        bar(lambda x: x**2, lambda x: x**2)  # no naming when passed positionally

        def baz(func1, func2):
            assert func1.__name__ == "<lambda>"
            assert func2.__name__ == "func2"
        baz(lambda x: x**2, func2=lambda x: x**2)

        # dictionary literal
        d = {"f": lambda x: x**2,  # literal string key in a dictionary literal: name as "f"
             "g": lambda x: x**2}  # literal string key in a dictionary literal: name as "g"
        assert d["f"].__name__ == "f"
        assert d["g"].__name__ == "g"

    # naming a decorated lambda
    with namedlambda:
        f2 = trampolined(withself(lambda self, n, acc=1: jump(self, n - 1, acc * n) if n > 1 else acc))
        f2(5000)  # no crash since TCO
        assert f2.__name__ == "f2"

        # works also with custom decorators
        def mydeco(f):
            @wraps(f)  # important! (without this the name is "decorated", not "f")
            def decorated(*args, **kwargs):
                return f(*args, **kwargs)
            return decorated
        f3 = mydeco(lambda x: x**2)
        assert f3(10) == 100
        assert f3.__name__ == "f3"

        # parametric decorators are defined as usual
        def mypardeco(a, b):
            def mydeco(f):
                @wraps(f)
                def decorated(*args, **kwargs):
                    return (a, b, f(*args, **kwargs))
                return decorated
            return mydeco
        f4 = mypardeco(2, 3)(lambda x: x**2)
        assert f4(10) == (2, 3, 100)
        assert f4.__name__ == "f4"

        # to help readability of invocations of parametric decorators on lambdas,
        # we recognize also curry with a lambda as the last argument
        f5 = curry(mypardeco, 2, 3,
                     lambda x: x**2)
        assert f5(10) == (2, 3, 100)
        assert f5.__name__ == "f5"

    # also autocurry with a lambda as the last argument is recognized
    # TODO: fix MacroPy #21 properly; https://github.com/azazel75/macropy/issues/21
    with namedlambda:
        with curry:
            f6 = mypardeco(2, 3, lambda x: x**2)
            assert f6(10) == (2, 3, 100)
            assert f6.__name__ == "f6"

    # presence of autocurry should not confuse the first-pass output
    with namedlambda:
        with curry:
            foo = let[(f7, None) in f7 << (lambda x: x)]  # noqa: F821
            assert foo.__name__ == "f7"

            f6 = mypardeco(2, 3, lambda x: x**2)
            assert f6(10) == (2, 3, 100)
            assert f6.__name__ == "f6"

    # looped_over overwrites with the result, so nothing to name
    with namedlambda:
        result = looped_over(range(10), acc=0)(lambda loop, x, acc: loop(acc + x))
        assert result == 45
        try:
            result.__name__
        except AttributeError:
            pass
        else:
            assert False, "should have returned an int (which has no __name__)"

        result = curry(looped_over, range(10), 0,
                         lambda loop, x, acc:
                           loop(acc + x))
        assert result == 45

    with quicklambda, multilambda:
        func = f[[local[x << _],  # noqa: F821, F823, `quicklambda` implicitly defines `f[]` to mean `lambda`.
                  local[y << _],  # noqa: F821
                  x + y]]  # noqa: F821
        assert func(1, 2) == 3

    # formal parameters as an unpythonic env
    with envify:
        def foo(x):
            x = 3  # should become a write into the env
            assert x == 3
        foo(10)

        def foo(x):
            x = 3
            assert x == 3
            del x
            try:
                x  # noqa: F821, the undefined name is the whole point of this test
            except AttributeError:  # note it's AttributeError since it's in an env
                pass
            else:
                assert False, "should have deleted x from the implicit env"
        foo(10)

    # Star-assignment also works, since Python performs the actual unpacking/packing.
    # We just use a different target for the store.
    with envify:
        def foo(n):
            a, *n, b = (1, 2, 3, 4, 5)  # noqa: F841, `a` and `b` are unused, this is just a silly test.
            assert n == [2, 3, 4]
        foo(10)

    # The main use case is with lambdas, to do things like this:
    with envify:
        def foo(n):
            return lambda i: n << n + i
        f = foo(10)
        assert f(1) == 11
        assert f(1) == 12

    # solution to PG's accumulator puzzle with the fewest elements in the original unexpanded code
    # http://paulgraham.com/icad.html
    with autoreturn, envify:
        def foo(n):
            lambda i: n << n + i
        f = foo(10)
        assert f(1) == 11
        assert f(1) == 12

    # or as a one-liner
    with autoreturn, envify:
        foo = lambda n: lambda i: n << n + i
        f = foo(10)
        assert f(1) == 11
        assert f(1) == 12

    # pythonic solution with optimal bytecode (doesn't need an extra location to store the accumulator)
    def foo(n):
        def accumulate(i):
            nonlocal n
            n += i
            return n
        return accumulate
    f = foo(10)
    assert f(1) == 11
    assert f(1) == 12

    print("All tests PASSED")

if __name__ == '__main__':
    test()
