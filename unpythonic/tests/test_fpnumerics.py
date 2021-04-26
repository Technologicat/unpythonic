#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Integration test/usage example: numerical tricks in FP.

Based on various sources; links provided in the source code comments.
"""

from ..syntax import macros, test  # noqa: F401
from ..test.fixtures import session, testset, returns_normally

from operator import add, mul
from itertools import repeat
from math import sin, pi, log2

from ..fun import curry
from ..it import unpack, drop, take, tail, first, second, last, iterate1, within
from ..fold import scanl, scanl1, unfold
from ..mathseq import gmathify, imathify
from ..gmemo import gmemoize
from ..gtco import gtrampolined

def runtests():
    with testset("collatz sequence"):
        # http://learnyouahaskell.com/higher-order-functions
        def collatz(n):
            # fail-fast sanity check
            if not isinstance(n, int):  # pragma: no cover
                raise TypeError(f"Expected integer n, got {type(n)} with value {repr(n)}")
            if n < 1:  # pragma: no cover
                raise ValueError(f"n must be >= 1, got {n}")
            def collatz_gen(n):
                while True:
                    yield n
                    if n == 1:
                        break
                    n = n // 2 if n % 2 == 0 else 3 * n + 1
            return collatz_gen(n)
        test[tuple(collatz(13)) == (13, 40, 20, 10, 5, 16, 8, 4, 2, 1)]
        test[tuple(collatz(10)) == (10, 5, 16, 8, 4, 2, 1)]
        test[tuple(collatz(30)) == (30, 15, 46, 23, 70, 35, 106, 53, 160, 80, 40, 20, 10, 5, 16, 8, 4, 2, 1)]
        def len_gt(k, s):
            # see also unpythonic.slicing.islice; could implement as  return islice(s)[k + 1]
            a, _ = unpack(1, drop(k, s))
            return a  # None if no item
        islong = curry(len_gt, 15)
        test[sum(1 for n in range(1, 101) if islong(collatz(n))) == 66]

    # Implicitly defined infinite streams, using generators.
    #
    # The trick is to specify just enough terms explicitly to bootstrap the
    # recursive rule (just like in the corresponding pen-and-paper definitions
    # in mathematics).

    # @gmemoize (from unnpythonic.gmemo) prevents the stack overflow crash.
    # Only one copy of the actual generator runs; any already computed items
    # are yielded directly from the memo.
    #
    # Memory use still grows per-item, because, beside the memoized sequence
    # itself, each instance spawned here (which is then actually an interface
    # to the memoized sequence) must keep track of its position within the
    # sequence.
    #
    # In ones_fp specifically, where the only recursive call is in the tail
    # position, we use @gtrampolined (from unpythonic.gtco), which allows
    # the sequence to tail-chain into a new instance of itself.
    #
    with testset("implicit infinite streams"):
        @gmathify
        @gtrampolined
        def ones_fp():
            yield 1
            return ones_fp()
        @gmathify
        @gmemoize
        def nats_fp(start=0):
            yield start
            yield from nats_fp(start) + ones_fp()
        @gmathify
        @gmemoize
        def fibos_fp():
            yield 1
            yield 1
            yield from fibos_fp() + tail(fibos_fp())
        @gmathify
        @gmemoize
        def powers_of_2():
            yield 1
            yield from 2 * powers_of_2()
        test[tuple(take(10, ones_fp())) == (1,) * 10]
        test[tuple(take(10, nats_fp())) == tuple(range(10))]
        test[tuple(take(10, fibos_fp())) == (1, 1, 2, 3, 5, 8, 13, 21, 34, 55)]
        test[tuple(take(10, powers_of_2())) == (1, 2, 4, 8, 16, 32, 64, 128, 256, 512)]
        test[returns_normally(last(take(5000, fibos_fp())))]

        # The scanl equations are sometimes useful. The conditions
        #   rs[0] = s0
        #   rs[k+1] = rs[k] + xs[k]
        # are equivalent with
        #   rs = scanl(add, s0, xs)
        # https://www.vex.net/~trebla/haskell/scanl.xhtml
        #
        # In Python, though, these will eventually crash due to stack overflow.
        @gmathify
        def zs():  # s0 = 0, rs = [0, ...], xs = [0, ...]
            yield from scanl(add, 0, zs())
        @gmathify
        def os():  # s0 = 1, rs = [1, ...], xs = [0, ...]
            yield from scanl(add, 1, zs())
        @gmathify
        def ns(start=0):  # s0 = start, rs = [start, start+1, ...], xs = [1, ...]
            yield from scanl(add, start, os())
        @gmathify
        def fs():  # s0 = 1, scons(1, rs) = fibos, xs = fibos
            yield 1
            yield from scanl(add, 1, fs())
        @gmathify
        def p2s():  # s0 = 1, rs = xs = [1, 2, 4, ...]
            yield from scanl(add, 1, p2s())
        test[tuple(take(10, zs())) == (0,) * 10]
        test[tuple(take(10, os())) == (1,) * 10]
        test[tuple(take(10, ns())) == tuple(range(10))]
        test[tuple(take(10, fs())) == (1, 1, 2, 3, 5, 8, 13, 21, 34, 55)]
        test[tuple(take(10, p2s())) == (1, 2, 4, 8, 16, 32, 64, 128, 256, 512)]

        # Better Python: simple is better than complex. No stack overflow, no tricks needed.
        @gmathify
        def ones():
            return repeat(1)
        @gmathify
        def nats(start=0):
            return scanl(add, start, ones())
        @gmathify
        def fibos():
            def nextfibo(a, b):
                return a, b, a + b
            return unfold(nextfibo, 1, 1)
        @gmathify
        def pows():
            return scanl(mul, 1, repeat(2))
        test[tuple(take(10, ones())) == (1,) * 10]
        test[tuple(take(10, nats())) == tuple(range(10))]
        test[tuple(take(10, fibos())) == (1, 1, 2, 3, 5, 8, 13, 21, 34, 55)]
        test[tuple(take(10, pows())) == (1, 2, 4, 8, 16, 32, 64, 128, 256, 512)]

    # Numerical differentiation with FP.
    #
    # See:
    #   Hughes, 1984: Why Functional Programming Matters, p. 11 ff.
    #   http://www.cse.chalmers.se/~rjmh/Papers/whyfp.html
    #
    with testset("numerical differentiation"):
        def easydiff(f, x, h):  # as well known, wildly inaccurate
            return (f(x + h) - f(x)) / h
        def halve(x):
            return x / 2
        def differentiate(h0, f, x):
            return map(curry(easydiff, f, x), iterate1(halve, h0))
        def differentiate_with_tol(h0, f, x, eps):
            return last(within(eps, differentiate(h0, f, x)))
        test[abs(differentiate_with_tol(0.1, sin, pi / 2, 1e-8)) < 1e-7]

        def order(s):
            """Estimate asymptotic order of s, consuming the first three terms."""
            a, b, c, _ = unpack(3, s)
            return round(log2(abs((a - c) / (b - c)) - 1))
        def eliminate_error(n, s):
            """Eliminate error term of given asymptotic order n.

            The stream s must be based on halving h at each step
            for the formula used here to work."""
            while True:
                a, b, s = unpack(2, s, k=1)
                yield (b * 2**n - a) / (2**(n - 1))
        def improve(s):
            """Eliminate asymptotically dominant error term from s.

            Consumes the first three terms to estimate the order.
            """
            return eliminate_error(order(s), s)
        def better_differentiate_with_tol(h0, f, x, eps):
            return last(within(eps, improve(differentiate(h0, f, x))))
        test[abs(better_differentiate_with_tol(0.1, sin, pi / 2, 1e-8)) < 1e-9]

        def super_improve(s):
            # s: stream
            # improve(s): stream
            # iterate1(improve, s) --> stream of streams: (s, improve(s), improve(improve(s)), ...)
            # map(second, ...) --> stream, consisting of the second element from each of these streams
            return map(second, iterate1(improve, s))
        def best_differentiate_with_tol(h0, f, x, eps):
            return last(within(eps, super_improve(differentiate(h0, f, x))))
        # Thanks to super_improve, this actually requires taking only three terms.
        test[abs(best_differentiate_with_tol(0.1, sin, pi / 2, 1e-8)) < 1e-11]

    # pi approximation with Euler series acceleration
    #
    # See SICP, 2nd ed., sec. 3.5.3.
    #
    # This implementation originally by Jim Hoover, in Racket, from:
    # https://sites.ualberta.ca/~jhoover/325/CourseNotes/section/Streams.htm
    #
    with testset("pi approximation with Euler series acceleration"):
        partial_sums = lambda s: imathify(scanl1(add, s))
        def pi_summands(n):
            """Yield the terms of the sequence π/4 = 1 - 1/3 + 1/5 - 1/7 + ... """
            sign = +1
            while True:
                yield sign / n
                n += 2
                sign *= -1
        pi_stream = 4 * partial_sums(pi_summands(1))

        def euler_transform(s):
            """Accelerate convergence of an alternating series.

            See:
                http://mathworld.wolfram.com/EulerTransform.html
                https://en.wikipedia.org/wiki/Series_acceleration#Euler%27s_transform
            """
            while True:
                a, b, c, s = unpack(3, s, k=1)
                yield c - ((c - b)**2 / (a - 2 * b + c))
        faster_pi_stream = euler_transform(pi_stream)

        def super_accelerate(transform, s):
            # iterate1(transform, s) --> stream of streams: (s, transform(s), transform(transform(s)), ...)
            return map(first, iterate1(transform, s))
        fastest_pi_stream = super_accelerate(euler_transform, pi_stream)

        test[abs(last(take(6, pi_stream)) - pi) < 0.2]
        test[abs(last(take(6, faster_pi_stream)) - pi) < 1e-3]
        test[abs(last(take(6, fastest_pi_stream)) - pi) < 1e-15]

if __name__ == '__main__':  # pragma: no cover
    with session(__file__):
        runtests()
