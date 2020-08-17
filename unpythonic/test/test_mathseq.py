# -*- coding: utf-8 -*-

from ..syntax import macros, test, test_raises  # noqa: F401
from .fixtures import testset, fail

from operator import mul

from ..mathseq import s, m, mg, sadd, smul, spow, cauchyprod, primes, fibonacci
from ..it import take, last
from ..fold import scanl
from ..gmemo import imemoize
from ..misc import timer, ulp

def runtests():
    with testset("unpythonic.mathseq"):
        # explicitly listed elements, same as a genexpr using tuple input
        with testset("s, convenience"):
            test[tuple(s(1)) == (1,)]
            test[tuple(s(1, 2, 3, 4, 5)) == (1, 2, 3, 4, 5)]

        # constant sequence: [a0, identity] -> a0, a0, a0, ...
        # always infinite length, because final element cannot be used to deduce length.
        with testset("s, constant sequence"):
            test[tuple(take(10, s(1, ...))) == (1,) * 10]

        # arithmetic sequence [a0, +d] -> a0, a0 + d, a0 + 2 d + ...
        with testset("s, arithmetic sequence"):
            test[tuple(take(10, s(1, 2, ...))) == tuple(range(1, 11))]     # two elements is enough
            test[tuple(take(10, s(1, 2, 3, ...))) == tuple(range(1, 11))]  # more is allowed if consistent

        # geometric sequence [a0, *r] -> a0, a0*r, a0*r**2, ...
        # three elements is enough, more allowed if consistent
        with testset("s, geometric sequence"):
            test[tuple(take(10, s(1, 2, 4, ...))) == (1, 2, 4, 8, 16, 32, 64, 128, 256, 512)]
            test[tuple(take(10, s(1, 2, 4, 8, ...))) == (1, 2, 4, 8, 16, 32, 64, 128, 256, 512)]
            test[tuple(take(10, s(1, 1 / 2, 1 / 4, ...))) == (1, 1 / 2, 1 / 4, 1 / 8, 1 / 16, 1 / 32, 1 / 64, 1 / 128, 1 / 256, 1 / 512)]
            test[tuple(take(10, s(1, 1 / 2, 1 / 4, 1 / 8, ...))) == (1, 1 / 2, 1 / 4, 1 / 8, 1 / 16, 1 / 32, 1 / 64, 1 / 128, 1 / 256, 1 / 512)]
            test[tuple(take(5, s(3, 9, 27, ...))) == (3, 9, 27, 81, 243)]

        # specify a final element to get a finite sequence (except constant sequences)
        # this is an abbreviation for take(...), computing n for you
        # (or takewhile(...) with the appropriate end condition)
        with testset("s with final element (terminating sequence)"):
            test[tuple(s(1, 2, ..., 10)) == tuple(range(1, 11))]
            test[tuple(s(1, 2, 4, ..., 512)) == (1, 2, 4, 8, 16, 32, 64, 128, 256, 512)]
            test[tuple(s(1, 1 / 2, 1 / 4, ..., 1 / 512)) == (1, 1 / 2, 1 / 4, 1 / 8, 1 / 16, 1 / 32, 1 / 64, 1 / 128, 1 / 256, 1 / 512)]

        with testset("s, alternating geometric sequence"):
            test[tuple(take(5, s(1, -1, 1, ...))) == (1, -1, 1, -1, 1)]
            test[tuple(take(5, s(-1, 1, -1, ...))) == (-1, 1, -1, 1, -1)]
            test[tuple(take(10, s(1, -2, 4, ...))) == (1, -2, 4, -8, 16, -32, 64, -128, 256, -512)]
            test[tuple(take(10, s(1, -1 / 2, 1 / 4, ...))) == (1, -1 / 2, 1 / 4, -1 / 8, 1 / 16, -1 / 32, 1 / 64, -1 / 128, 1 / 256, -1 / 512)]
            test[tuple(s(1, -2, 4, ..., -512)) == (1, -2, 4, -8, 16, -32, 64, -128, 256, -512)]
            test[tuple(s(1, -1 / 2, 1 / 4, ..., -1 / 512)) == (1, -1 / 2, 1 / 4, -1 / 8, 1 / 16, -1 / 32, 1 / 64, -1 / 128, 1 / 256, -1 / 512)]
            test[tuple(take(5, s(3, -9, 27, ...))) == (3, -9, 27, -81, 243)]
            test[tuple(take(5, s(-3, 9, -27, ...))) == (-3, 9, -27, 81, -243)]
            test[tuple(take(5, s(1, 32, 1024, ...))) == (1, 32, 1024, 32768, 1048576)]  # 2**0, 2**5, 2**10, ...
            test[tuple(take(5, s(1, 1 / 32, 1 / 1024, ...))) == (1, 1 / 32, 1 / 1024, 1 / 32768, 1 / 1048576)]

        # power sequence [a0, **p] -> a0, a0**p, a0**(p**2), ...
        # three elements is enough, more allowed if consistent
        with testset("s, power sequence"):
            test[tuple(take(5, s(2, 4, 16, ...))) == (2, 4, 16, 256, 65536)]                # 2, 2**2, 2**4, 2**8, ...
            test[tuple(take(5, s(2, 4, 16, 256, ...))) == (2, 4, 16, 256, 65536)]
            test[tuple(take(5, s(2, 1 / 4, 16, ...))) == (2, 1 / 4, 16, 1 / 256, 65536)]    # 2, 2**-2, 2**4, 2**-8, ...
            test[tuple(take(5, s(-2, 4, 16, ...))) == (-2, 4, 16, 256, 65536)]              # -2, (-2)**2, (-2)**4, ...
            test[tuple(take(5, s(-2, 1 / 4, 16, ...))) == (-2, 1 / 4, 16, 1 / 256, 65536)]  # -2, (-2)**(-2), (-2)**4, ...
            test[tuple(take(5, s(2, 4, 16, ..., 65536))) == (2, 4, 16, 256, 65536)]
            test[tuple(take(5, s(2, 2**(1 / 2), 2**(1 / 4), ...))) == (2, 2**(1 / 2), 2**(1 / 4), 2**(1 / 8), 2**(1 / 16))]
            test[last(s(2, 2**(1 / 2), 2**(1 / 4), ..., 2**(1 / 1048576))) == 2**(1 / 1048576)]

        with testset("arithmetic operations"):
            test[tuple(take(5, sadd(s(1, 3, ...), s(2, 4, ...)))) == (3, 7, 11, 15, 19)]
            test[tuple(take(5, sadd(1, s(1, 3, ...)))) == (2, 4, 6, 8, 10)]
            test[tuple(take(5, sadd(s(1, 3, ...), 1))) == (2, 4, 6, 8, 10)]

            test[tuple(take(5, smul(s(1, 3, ...), s(2, 4, ...)))) == (2, 12, 30, 56, 90)]
            test[tuple(take(5, smul(2, s(1, 3, ...)))) == (2, 6, 10, 14, 18)]
            test[tuple(take(5, smul(s(1, 3, ...), 2))) == (2, 6, 10, 14, 18)]

            test[tuple(take(5, spow(s(1, 3, ...), s(2, 4, ...)))) == (1, 3**4, 5**6, 7**8, 9**10)]
            test[tuple(take(5, spow(s(1, 3, ...), 2))) == (1, 3**2, 5**2, 7**2, 9**2)]
            test[tuple(take(5, spow(2, s(1, 3, ...)))) == (2**1, 2**3, 2**5, 2**7, 2**9)]

        with testset("cauchyprod"):
            test[tuple(take(3, cauchyprod(s(1, 3, 5, ...), s(2, 4, 6, ...)))) == (2, 10, 28)]
            test[tuple(take(3, cauchyprod(s(1, 3, 5, ...), s(2, 4, 6, ...), require="all"))) == (2, 10, 28)]

            test[tuple(cauchyprod((1, 3), (2, 4))) == (2, 10, 12)]
            test[tuple(cauchyprod((1, 3, 5), (2, 4))) == (2, 10, 22, 20)]
            test[tuple(cauchyprod((1, 3, 5), (2,))) == (2, 6, 10)]
            test[tuple(cauchyprod((2, 4), (1, 3, 5))) == (2, 10, 22, 20)]
            test[tuple(cauchyprod((2,), (1, 3, 5))) == (2, 6, 10)]

            test[tuple(cauchyprod((1, 3), (2, 4), require="all")) == (2, 10)]
            test[tuple(cauchyprod((1, 3, 5), (2, 4), require="all")) == (2, 10)]
            test[tuple(cauchyprod((1, 3, 5), (2,), require="all")) == (2,)]
            test[tuple(cauchyprod((2, 4), (1, 3, 5), require="all")) == (2, 10)]
            test[tuple(cauchyprod((2,), (1, 3, 5), require="all")) == (2,)]

        with testset("m, mg (infix syntax for arithmetic)"):
            # Sequences returned by `s` are `m`'d implicitly.
            test[tuple(take(5, s(1, 3, 5, ...) + s(2, 4, 6, ...))) == (3, 7, 11, 15, 19)]
            test[tuple(take(5, 1 + s(1, 3, ...))) == (2, 4, 6, 8, 10)]
            test[tuple(take(5, 1 - s(1, 3, ...))) == (0, -2, -4, -6, -8)]
            test[tuple(take(5, s(1, 3, ...) + 1)) == (2, 4, 6, 8, 10)]
            test[tuple(take(5, s(1, 3, ...) - 1)) == (0, 2, 4, 6, 8)]

            test[tuple(take(5, s(1, 3, ...) * s(2, 4, ...))) == (2, 12, 30, 56, 90)]
            test[tuple(take(5, 2 * s(1, 3, ...))) == (2, 6, 10, 14, 18)]
            test[tuple(take(5, s(1, 3, ...) * 2)) == (2, 6, 10, 14, 18)]
            test[tuple(take(5, s(2, 4, ...) / 2)) == (1, 2, 3, 4, 5)]
            test[tuple(take(5, 1 / s(1, 2, ...))) == (1, 1 / 2, 1 / 3, 1 / 4, 1 / 5)]

            test[tuple(take(5, s(1, 3, ...)**s(2, 4, ...))) == (1, 3**4, 5**6, 7**8, 9**10)]
            test[tuple(take(5, s(1, 3, ...)**2)) == (1, 3**2, 5**2, 7**2, 9**2)]
            test[tuple(take(5, 2**s(1, 3, ...))) == (2**1, 2**3, 2**5, 2**7, 2**9)]

            a = s(1, 3, ...)
            b = s(2, 4, ...)
            c = a + b
            test[isinstance(c, m)]
            test[tuple(take(5, c)) == (3, 7, 11, 15, 19)]

            d = 1 / (a + b)
            test[isinstance(d, m)]

            e = take(5, c)
            test[not isinstance(e, m)]

            f = m(take(5, c))
            test[isinstance(f, m)]

            g = m((1, 2, 3, 4, 5))
            h = m((2, 3, 4, 5, 6))
            test[tuple(g + h) == (3, 5, 7, 9, 11)]

            # `mg`: make a gfunc `m` the returned generator instances.
            a = mg(imemoize(s(1, 2, ...)))
            test[last(take(5, a())) == 5]
            test[last(take(5, a())) == 5]
            test[last(take(5, a() + a())) == 10]

        with testset("no accumulating roundoff error"):
            # values not exactly representable in base-2; the sequence terms should roundoff the same way as the RHS
            test[tuple(s(1, 1 / 10, 1 / 100, ..., 1 / 10000)) == (1, 0.1, 0.01, 0.001, 0.0001)]
            test[tuple(s(1, 1 / 10, 1 / 100, 1 / 1000, ..., 1 / 10000)) == (1, 0.1, 0.01, 0.001, 0.0001)]
            test[tuple(s(1, 1 / 10, 1 / 100, ..., 1 / 10000)) == (1, 1 / 10, 1 / 100, 1 / 1000, 1 / 10000)]
            test[tuple(s(1, 1 / 10, 1 / 100, 1 / 1000, ..., 1 / 10000)) == (1, 1 / 10, 1 / 100, 1 / 1000, 1 / 10000)]
            test[tuple(s(1, 1 / 3, 1 / 9, ..., 1 / 81)) == (1, 1 / 3, 1 / 9, 1 / 27, 1 / 81)]
            test[tuple(s(1, 1 / 3, 1 / 9, 1 / 27, ..., 1 / 81)) == (1, 1 / 3, 1 / 9, 1 / 27, 1 / 81)]

            # a long arithmetic sequence where the start value and the diff are not exactly representable
            # in IEEE-754 double precision; the final value should be within an ULP of the true value
            test[abs(last(s(0.01, 0.02, ..., 100)) - 100.0) <= ulp(100.0)]
            test[abs(last(s(0.01, 0.02, ..., 1000)) - 1000.0) <= ulp(1000.0)]
            test[abs(last(s(0.01, 0.02, ..., 10000)) - 10000.0) <= ulp(10000.0)]

        with testset("error cases"):
            test_raises[SyntaxError,
                        s(1, ..., 1),
                        "should detect that the length of a constant sequence cannot be determined from a final element"]
            test_raises[SyntaxError,
                        s(1, 2, ..., 10.5),
                        "should detect that the final element, if given, must be in the specified sequence"]
            test_raises[SyntaxError,
                        s(1, 2, ..., -10),
                        "should detect that the final element, if given, must be in the specified sequence"]
            test_raises[SyntaxError,
                        s(2, 4, 0, ...),
                        "should detect that a geometric sequence must have no zero elements"]
            test_raises[SyntaxError,
                        s(2, 3, 5, 7, 11, ...),
                        "should detect that s() is not that smart!"]
            test_raises[SyntaxError,
                        s(1, 1, 2, 3, 5, ...),
                        "should detect that s() is not that smart!"]

        with testset("symbolic input with SymPy"):
            try:
                from sympy import symbols
            except ImportError:
                test[fail, "SymPy not installed in this Python, cannot test symbolic input for mathseq."]
            else:
                x0 = symbols("x0", real=True)
                k = symbols("k", positive=True)  # important for geometric series

                test[tuple(take(4, s(x0, ...))) == (x0, x0, x0, x0)]
                test[tuple(take(4, s(x0, x0 + k, ...))) == (x0, x0 + k, x0 + 2 * k, x0 + 3 * k)]
                test[tuple(take(4, s(x0, x0 * k, x0 * k**2, ...))) == (x0, x0 * k, x0 * k**2, x0 * k**3)]

                test[tuple(s(x0, x0 + k, ..., x0 + 3 * k)) == (x0, x0 + k, x0 + 2 * k, x0 + 3 * k)]
                test[tuple(s(x0, x0 * k, x0 * k**2, ..., x0 * k**3)) == (x0, x0 * k, x0 * k**2, x0 * k**3)]
                test[tuple(s(x0, x0 * k, x0 * k**2, ..., x0 * k**5)) == (x0, x0 * k, x0 * k**2, x0 * k**3, x0 * k**4, x0 * k**5)]

                test[tuple(s(x0, -x0 * k, x0 * k**2, ..., -x0 * k**3)) == (x0, -x0 * k, x0 * k**2, -x0 * k**3)]

                test_raises[SyntaxError,
                            tuple(s(x0, x0 * k, ..., x0 * k**3)) == (x0, x0 * k, x0 * k**2, x0 * k**3),
                            "too few terms for geometric sequence, the analyzer should (incorrectly) try an arithmetic sequence and think the final element does not match"]

                x0, k = symbols("x0, k", positive=True)
                test[tuple(s(x0, x0**k, x0**(k**2), ..., x0**(k**5))) == (x0, x0**k, x0**(k**2), x0**(k**3), x0**(k**4), x0**(k**5))]

                x = symbols("x", real=True)
                px = lambda stream: stream * s(1, x, x**2, ...)
                s1 = px(s(1, 3, 5, ...))
                s2 = px(s(2, 4, 6, ...))
                test[tuple(take(3, cauchyprod(s1, s2))) == (2, 10 * x, 28 * x**2)]

        with testset("some special sequences"):
            test[tuple(take(10, primes())) == (2, 3, 5, 7, 11, 13, 17, 19, 23, 29)]
            test[tuple(take(10, fibonacci())) == (1, 1, 2, 3, 5, 8, 13, 21, 34, 55)]

            factorials = imemoize(scanl(mul, 1, s(1, 2, ...)))  # 0!, 1!, 2!, ...
            test[last(take(6, factorials())) == 120]

        # TODO: need some kind of benchmarking tools to do this properly.
        with testset("performance benchmark"):
            n = 5000
            with timer() as tictoc:
                last(take(n, primes()))
            print("First {:d} primes: {:g}s".format(n, tictoc.dt))

            test[last(take(3379, primes())) == 31337]

if __name__ == '__main__':
    runtests()
