# -*- coding: utf-8 -*-

from sys import float_info
from math import floor, log2

from ..mathseq import s, m, sadd, smul, spow, cauchyprod
from ..it import take, last

def test():
    # convenience: explicitly listed elements, same as a genexpr using tuple input
    assert tuple(s(1)) == (1,)
    assert tuple(s(1, 2, 3, 4, 5)) == (1, 2, 3, 4, 5)

    # constant sequence: [a0, identity] -> a0, a0, a0, ...
    # always infinite length, because final element cannot be used to deduce length.
    assert tuple(take(10, s(1, ...))) == (1,)*10

    # arithmetic sequence [a0, +d] -> a0, a0 + d, a0 + 2 d + ...
    assert tuple(take(10, s(1, 2, ...))) == tuple(range(1, 11))     # two elements is enough
    assert tuple(take(10, s(1, 2, 3, ...))) == tuple(range(1, 11))  # more is allowed if consistent

    # geometric sequence [a0, *r] -> a0, a0*r, a0*r**2, ...
    # three elements is enough, more allowed if consistent
    assert tuple(take(10, s(1, 2, 4, ...))) == (1, 2, 4, 8, 16, 32, 64, 128, 256, 512)
    assert tuple(take(10, s(1, 2, 4, 8, ...))) == (1, 2, 4, 8, 16, 32, 64, 128, 256, 512)
    assert tuple(take(10, s(1, 1/2, 1/4, ...))) == (1, 1/2, 1/4, 1/8, 1/16, 1/32, 1/64, 1/128, 1/256, 1/512)
    assert tuple(take(10, s(1, 1/2, 1/4, 1/8, ...))) == (1, 1/2, 1/4, 1/8, 1/16, 1/32, 1/64, 1/128, 1/256, 1/512)
    assert tuple(take(5, s(3, 9, 27, ...))) == (3, 9, 27, 81, 243)

    # specify a final element to get a finite sequence (except constant sequences)
    # this is an abbreviation for take(...), computing n for you
    # (or takewhile(...) with the appropriate end condition)
    assert tuple(s(1, 2, ..., 10)) == tuple(range(1, 11))
    assert tuple(s(1, 2, 4, ..., 512)) == (1, 2, 4, 8, 16, 32, 64, 128, 256, 512)
    assert tuple(s(1, 1/2, 1/4, ..., 1/512)) == (1, 1/2, 1/4, 1/8, 1/16, 1/32, 1/64, 1/128, 1/256, 1/512)

    # alternating geometric sequences also ok
    assert tuple(take(5, s(1, -1, 1, ...))) == (1, -1, 1, -1, 1)
    assert tuple(take(5, s(-1, 1, -1, ...))) == (-1, 1, -1, 1, -1)
    assert tuple(take(10, s(1, -2, 4, ...))) == (1, -2, 4, -8, 16, -32, 64, -128, 256, -512)
    assert tuple(take(10, s(1, -1/2, 1/4, ...))) == (1, -1/2, 1/4, -1/8, 1/16, -1/32, 1/64, -1/128, 1/256, -1/512)
    assert tuple(s(1, -2, 4, ..., -512)) == (1, -2, 4, -8, 16, -32, 64, -128, 256, -512)
    assert tuple(s(1, -1/2, 1/4, ..., -1/512)) == (1, -1/2, 1/4, -1/8, 1/16, -1/32, 1/64, -1/128, 1/256, -1/512)
    assert tuple(take(5, s(3, -9, 27, ...))) == (3, -9, 27, -81, 243)
    assert tuple(take(5, s(-3, 9, -27, ...))) == (-3, 9, -27, 81, -243)
    assert tuple(take(5, s(1, 32, 1024, ...))) == (1, 32, 1024, 32768, 1048576)  # 2**0, 2**5, 2**10, ...
    assert tuple(take(5, s(1, 1/32, 1/1024, ...))) == (1, 1/32, 1/1024, 1/32768, 1/1048576)

    # power sequence [a0, **p] -> a0, a0**p, a0**(p**2), ...
    # three elements is enough, more allowed if consistent
    assert tuple(take(5, s(2, 4, 16, ...))) == (2, 4, 16, 256, 65536)          # 2, 2**2, 2**4, 2**8, ...
    assert tuple(take(5, s(2, 4, 16, 256, ...))) == (2, 4, 16, 256, 65536)
    assert tuple(take(5, s(2, 1/4, 16, ...))) == (2, 1/4, 16, 1/256, 65536)    # 2, 2**-2, 2**4, 2**-8, ...
    assert tuple(take(5, s(-2, 4, 16, ...))) == (-2, 4, 16, 256, 65536)        # -2, (-2)**2, (-2)**4, ...
    assert tuple(take(5, s(-2, 1/4, 16, ...))) == (-2, 1/4, 16, 1/256, 65536)  # -2, (-2)**(-2), (-2)**4, ...
    assert tuple(take(5, s(2, 4, 16, ..., 65536))) == (2, 4, 16, 256, 65536)
    assert tuple(take(5, s(2, 2**(1/2), 2**(1/4), ...))) == (2, 2**(1/2), 2**(1/4), 2**(1/8), 2**(1/16))
    assert last(s(2, 2**(1/2), 2**(1/4), ..., 2**(1/1048576))) == 2**(1/1048576)

    # operations
    assert tuple(take(5, sadd(s(1, 3, ...), s(2, 4, ...)))) == (3, 7, 11, 15, 19)
    assert tuple(take(5, sadd(1, s(1, 3, ...)))) == (2, 4, 6, 8, 10)
    assert tuple(take(5, sadd(s(1, 3, ...), 1))) == (2, 4, 6, 8, 10)

    assert tuple(take(5, smul(s(1, 3, ...), s(2, 4, ...)))) == (2, 12, 30, 56, 90)
    assert tuple(take(5, smul(2, s(1, 3, ...)))) == (2, 6, 10, 14, 18)
    assert tuple(take(5, smul(s(1, 3, ...), 2))) == (2, 6, 10, 14, 18)

    assert tuple(take(5, spow(s(1, 3, ...), s(2, 4, ...)))) == (1, 3**4, 5**6, 7**8, 9**10)
    assert tuple(take(5, spow(s(1, 3, ...), 2))) == (1, 3**2, 5**2, 7**2, 9**2)
    assert tuple(take(5, spow(2, s(1, 3, ...)))) == (2**1, 2**3, 2**5, 2**7, 2**9)

    assert tuple(take(3, cauchyprod(s(1, 3, 5, ...), s(2, 4, 6, ...)))) == (2, 10, 28)
    assert tuple(cauchyprod((1, 3), (2, 4))) == (2, 10, 12)
    assert tuple(cauchyprod((1, 3, 5), (2, 4))) == (2, 10, 22, 20)
    assert tuple(cauchyprod((1, 3, 5), (2,))) == (2, 6, 10)
    assert tuple(cauchyprod((2, 4), (1, 3, 5))) == (2, 10, 22, 20)
    assert tuple(cauchyprod((2,), (1, 3, 5))) == (2, 6, 10)

    # infix syntax for operations
    assert tuple(take(5, s(1, 3, 5, ...) + s(2, 4, 6, ...))) == (3, 7, 11, 15, 19)
    assert tuple(take(5, 1 + s(1, 3, ...))) == (2, 4, 6, 8, 10)
    assert tuple(take(5, 1 - s(1, 3, ...))) == (0, -2, -4, -6, -8)
    assert tuple(take(5, s(1, 3, ...) + 1)) == (2, 4, 6, 8, 10)
    assert tuple(take(5, s(1, 3, ...) - 1)) == (0, 2, 4, 6, 8)

    assert tuple(take(5, s(1, 3, ...) * s(2, 4, ...))) == (2, 12, 30, 56, 90)
    assert tuple(take(5, 2 * s(1, 3, ...))) == (2, 6, 10, 14, 18)
    assert tuple(take(5, s(1, 3, ...) * 2)) == (2, 6, 10, 14, 18)
    assert tuple(take(5, s(2, 4, ...) / 2)) == (1, 2, 3, 4, 5)
    assert tuple(take(5, 1 / s(1, 2, ...))) == (1, 1/2, 1/3, 1/4, 1/5)

    assert tuple(take(5, s(1, 3, ...)**s(2, 4, ...))) == (1, 3**4, 5**6, 7**8, 9**10)
    assert tuple(take(5, s(1, 3, ...)**2)) == (1, 3**2, 5**2, 7**2, 9**2)
    assert tuple(take(5, 2**s(1, 3, ...))) == (2**1, 2**3, 2**5, 2**7, 2**9)

    a = s(1, 3, ...)
    b = s(2, 4, ...)
    c = a + b
    assert isinstance(c, m)
    assert tuple(take(5, c)) == (3, 7, 11, 15, 19)

    d = 1 / (a + b)
    assert isinstance(d, m)

    e = take(5, c)
    assert not isinstance(e, m)

    f = m(take(5, c))
    assert isinstance(f, m)

    # Our generators avoid accumulating roundoff error

    # values not exactly representable in base-2; the sequence terms should roundoff the same way as the RHS
    assert tuple(s(1, 1/10, 1/100, ..., 1/10000)) == (1, 0.1, 0.01, 0.001, 0.0001)
    assert tuple(s(1, 1/10, 1/100, 1/1000, ..., 1/10000)) == (1, 0.1, 0.01, 0.001, 0.0001)
    assert tuple(s(1, 1/10, 1/100, ..., 1/10000)) == (1, 1/10, 1/100, 1/1000, 1/10000)
    assert tuple(s(1, 1/10, 1/100, 1/1000, ..., 1/10000)) == (1, 1/10, 1/100, 1/1000, 1/10000)
    assert tuple(s(1, 1/3, 1/9, ..., 1/81)) == (1, 1/3, 1/9, 1/27, 1/81)
    assert tuple(s(1, 1/3, 1/9, 1/27, ..., 1/81)) == (1, 1/3, 1/9, 1/27, 1/81)

    # a long arithmetic sequence where the start value and the diff are not exactly representable
    # in IEEE-754 double precision; the final value should be within an ULP of the true value
    def ulp(x):  # Unit in the Last Place
        eps = float_info.epsilon
        # m_min = abs. value represented by a mantissa of 1.0, with the same exponent as x has
        m_min = 2**floor(log2(abs(x)))
        return m_min * eps
    assert abs(last(s(0.01, 0.02, ..., 100)) - 100.0) <= ulp(100.0)
    assert abs(last(s(0.01, 0.02, ..., 1000)) - 1000.0) <= ulp(1000.0)
    assert abs(last(s(0.01, 0.02, ..., 10000)) - 10000.0) <= ulp(10000.0)

    try:
        s(1, ..., 1)  # length of a constant sequence cannot be determined from a final element
    except SyntaxError:
        pass
    else:
        assert False

    try:
        s(1, 2, ..., 10.5)  # the final element, if given, must be in the specified sequence
    except SyntaxError:
        pass
    else:
        assert False

    try:
        s(1, 2, ..., -10)
    except SyntaxError:
        pass
    else:
        assert False

    try:
        s(2, 4, 0, ...)  # geometric sequence must have no zero elements
    except SyntaxError:
        pass
    else:
        assert False

    try:
        s(2, 3, 5, 7, 11, ...)  # not that smart!
    except SyntaxError:
        pass
    else:
        assert False

    try:
        s(1, 1, 2, 3, 5, ...)  # ditto
    except SyntaxError:
        pass
    else:
        assert False

    # works for symbolic input, too
    try:
        from sympy import symbols
        x0 = symbols("x0", real=True)
        k = symbols("k", positive=True)  # important for geometric series

        assert tuple(take(4, s(x0, ...))) == (x0, x0, x0, x0)
        assert tuple(take(4, s(x0, x0 + k, ...))) == (x0, x0 + k, x0 + 2*k, x0 + 3*k)
        assert tuple(take(4, s(x0, x0*k, x0*k**2, ...))) == (x0, x0*k, x0*k**2, x0*k**3)

        assert tuple(s(x0, x0 + k, ..., x0 + 3*k)) == (x0, x0 + k, x0 + 2*k, x0 + 3*k)
        assert tuple(s(x0, x0*k, x0*k**2, ..., x0*k**3)) == (x0, x0*k, x0*k**2, x0*k**3)
        assert tuple(s(x0, x0*k, x0*k**2, ..., x0*k**5)) == (x0, x0*k, x0*k**2, x0*k**3, x0*k**4, x0*k**5)

        assert tuple(s(x0, -x0*k, x0*k**2, ..., -x0*k**3)) == (x0, -x0*k, x0*k**2, -x0*k**3)

        try:  # too few terms, should think it's supposed to be an arithmetic sequence
            assert tuple(s(x0, x0*k, ..., x0*k**3)) == (x0, x0*k, x0*k**2, x0*k**3)
        except SyntaxError:
            pass
        else:
            assert False

        x0, k = symbols("x0, k", positive=True)
        assert tuple(s(x0, x0**k, x0**(k**2), ..., x0**(k**5))) == (x0, x0**k, x0**(k**2), x0**(k**3), x0**(k**4), x0**(k**5))

        x = symbols("x", real=True)
        px = lambda stream: stream * s(1, x, x**2, ...)
        s1 = px(s(1, 3, 5, ...))
        s2 = px(s(2, 4, 6, ...))
        assert tuple(take(3, cauchyprod(s1, s2))) == (2, 10*x, 28*x**2)

    except ImportError:
        print("*** SymPy not installed, skipping symbolic math sequence test ***")

    print("All tests PASSED")

if __name__ == '__main__':
    test()
