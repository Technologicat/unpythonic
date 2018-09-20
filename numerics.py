#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Test/usage example: numerical tricks in FP."""

from operator import add, mul
from itertools import repeat
from math import sin, pi, log2

from unpythonic.fun import curry
from unpythonic.it import unpack, drop, take, tail, first, second, last, iterate1
from unpythonic.fold import scanl, scanl1

def test():
    # http://learnyouahaskell.com/higher-order-functions
    def collatz(n):
        if n < 1:
            raise ValueError()
        while True:
            yield n
            if n == 1:
                break
            n = n // 2 if n % 2 == 0 else 3 * n + 1
    assert tuple(collatz(13)) == (13, 40, 20, 10, 5, 16, 8, 4, 2, 1)
    assert tuple(collatz(10)) == (10, 5, 16, 8, 4, 2, 1)
    assert tuple(collatz(30)) == (30, 15, 46, 23, 70, 35, 106, 53, 160, 80, 40, 20, 10, 5, 16, 8, 4, 2, 1)
    def len_gt(k, s):
        a, _ = unpack(1, drop(k, s))
        return a  # None if no item
    islong = curry(len_gt, 15)
    assert sum(1 for n in range(1, 101) if islong(collatz(n))) == 66

    # Implicitly defined infinite streams, using generators.
    #
    def adds(s1, s2):
        """Add two infinite streams (elementwise)."""
        return map(add, s1, s2)
    def muls(s, c):
        """Multiply an infinite stream by a constant."""
        return map(lambda x: c * x, s)

    # will eventually crash (stack overflow)
    def ones_fp():
        yield 1
        yield from ones_fp()
    def nats_fp(start=0):
        yield start
        yield from adds(nats_fp(start), ones_fp())
    def fibos_fp():
        yield 1
        yield 1
        yield from adds(fibos_fp(), tail(fibos_fp()))
    def powers_of_2():
        yield 1
        yield from muls(powers_of_2(), 2)
    assert tuple(take(10, ones_fp())) == (1,) * 10
    assert tuple(take(10, nats_fp())) == tuple(range(10))
    assert tuple(take(10, fibos_fp())) == (1, 1, 2, 3, 5, 8, 13, 21, 34, 55)
    assert tuple(take(10, powers_of_2())) == (1, 2, 4, 8, 16, 32, 64, 128, 256, 512)

    # The scanl equations are sometimes useful. The conditions
    #   rs[0] = s0
    #   rs[k+1] = rs[k] + xs[k]
    # are equivalent with
    #   rs = scanl(add, s0, xs)
    # https://www.vex.net/~trebla/haskell/scanl.xhtml
    def zs():  # s0 = 0, rs = [0, ...], xs = [0, ...]
        yield from scanl(add, 0, zs())
    def os():  # s0 = 1, rs = [1, ...], xs = [0, ...]
        yield from scanl(add, 1, zs())
    def ns(start=0):  # s0 = start, rs = [start, start+1, ...], xs = [1, ...]
        yield from scanl(add, start, os())
    def fs():  # s0 = 1, scons(1, rs) = fibos, xs = fibos
        yield 1
        yield from scanl(add, 1, fs())
    def p2s():  # s0 = 1, rs = xs = [1, 2, 4, ...]
        yield from scanl(add, 1, p2s())
    assert tuple(take(10, zs())) == (0,) * 10
    assert tuple(take(10, os())) == (1,) * 10
    assert tuple(take(10, ns())) == tuple(range(10))
    assert tuple(take(10, fs())) == (1, 1, 2, 3, 5, 8, 13, 21, 34, 55)
    assert tuple(take(10, p2s())) == (1, 2, 4, 8, 16, 32, 64, 128, 256, 512)

    # better Python: simple is better than complex (also no stack overflow)
    def ones():
        return repeat(1)
    def nats(start=0):
        return scanl(add, start, ones())
    def fibos():
        a, b = 1, 1
        while True:
            yield a
            a, b = b, a + b
    def pows():
        return scanl(mul, 1, repeat(2))
    assert tuple(take(10, ones())) == (1,) * 10
    assert tuple(take(10, nats())) == tuple(range(10))
    assert tuple(take(10, fibos())) == (1, 1, 2, 3, 5, 8, 13, 21, 34, 55)
    assert tuple(take(10, pows())) == (1, 2, 4, 8, 16, 32, 64, 128, 256, 512)

    # How to improve accuracy of numeric differentiation with FP tricks.
    #
    # See:
    #   Hughes, 1984: Why Functional Programming Matters, p. 11 ff.
    #   http://www.cse.chalmers.se/~rjmh/Papers/whyfp.html
    #
    def easydiff(f, x, h):  # as well known, wildly inaccurate
        return (f(x + h) - f(x)) / h
    def halve(x):
        return x / 2
    def differentiate(h0, f, x):
        return map(curry(easydiff, f, x), iterate1(halve, h0))
    def within(eps, s):
        while True:
            # unpack with peek (but be careful, the rewinded tail is a tee'd copy)
            a, b, s = unpack(2, s, k=1)
            if abs(a - b) < eps:
                return b
    def differentiate_with_tol(h0, f, x, eps):
        return within(eps, differentiate(h0, f, x))
    assert abs(differentiate_with_tol(0.1, sin, pi/2, 1e-8)) < 1e-7

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
            yield (b*2**n - a) / (2**(n - 1))
    def improve(s):
        """Eliminate asymptotically dominant error term from s.

        Consumes the first three terms to estimate the order.
        """
        return eliminate_error(order(s), s)
    def better_differentiate_with_tol(h0, f, x, eps):
        return within(eps, improve(differentiate(h0, f, x)))
    assert abs(better_differentiate_with_tol(0.1, sin, pi/2, 1e-8)) < 1e-9

    def super_improve(s):
        return map(second, iterate1(improve, s))
    def best_differentiate_with_tol(h0, f, x, eps):
        return within(eps, super_improve(differentiate(h0, f, x)))
    assert abs(best_differentiate_with_tol(0.1, sin, pi/2, 1e-8)) < 1e-12

    # pi approximation with Euler series acceleration
    #
    # See SICP, 2nd ed., sec. 3.5.3.
    #
    # This implementation originally by Jim Hoover, in Racket, from:
    # https://sites.ualberta.ca/~jhoover/325/CourseNotes/section/Streams.htm
    #
    partial_sums = curry(scanl1, add)
    def pi_summands(n):  # π/4 = 1 - 1/3 + 1/5 - 1/7 + ...
        sign = +1
        while True:
            yield sign / n
            n += 2
            sign *= -1
    pi_stream = muls(partial_sums(pi_summands(1)), 4)

    # http://mathworld.wolfram.com/EulerTransform.html
    # https://en.wikipedia.org/wiki/Series_acceleration#Euler%27s_transform
    def euler_transform(s):
        while True:
            a, b, c, s = unpack(3, s, k=1)
            yield c - ((c - b)**2 / (a - 2*b + c))
    faster_pi_stream = euler_transform(pi_stream)

    def super_accelerate(transform, s):
        return map(first, iterate1(transform, s))
    fastest_pi_stream = super_accelerate(euler_transform, pi_stream)

    assert abs(last(take(6, pi_stream)) - pi) < 0.2
    assert abs(last(take(6, faster_pi_stream)) - pi) < 1e-3
    assert abs(last(take(6, fastest_pi_stream)) - pi) < 1e-15

    print("All tests PASSED")

if __name__ == '__main__':
    test()
