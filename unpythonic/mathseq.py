# -*- coding: utf-8 -*-
"""Create lazy constant, arithmetic and geometric sequences with compact syntax.

Numeric (int, float, mpmath) and symbolic (SymPy) formats are supported.

Avoids accumulating roundoff error when used with floating-point.
"""

__all__ = ["s"]

from itertools import repeat

from sys import float_info
from math import log as math_log
try:
    from mpmath import mpf, almosteq
except ImportError:
    mpf = almosteq = None

try:
    from sympy import log as _symlog, Expr as _symExpr
    def log(x, b):
        if isinstance(x, _symExpr):
            # https://stackoverflow.com/questions/46129259/how-to-simplify-logarithm-of-exponent-in-sympy
            return float(_symlog(x, b).expand(force=True))
        return math_log(x, b)
except ImportError:
    log = math_log

from .it import take

# TODO: support geometric sequences with negative elements
# TODO: support alternating-sign sequences (both arithmetic and geometric)
# TODO: support power sequences: x0, x0**2, x0**3, ...
def s(*spec):
    """Create a lazy mathematical sequence.

    Any ellipsis ``...`` in the following description is meant literally.

    **Formats**

    Convenience fallback: an explicit enumeration of all elements of the desired
    sequence. This makes a genexpr that reads from a tuple::

        s(1, 2, 3, 4, 5)

    This fallback mainly exists so that the ``...``, if any, can be quickly
    dropped when testing/debugging the user program.

    *Constant sequence*. Always infinite length::

        s(1, ...)

    *Arithmetic sequence*. Two terms required, more allowed if consistent. May
    have an optional final element (that must belong to the sequence). If a
    final element is specified, a finite sequence is returned::

        s(1, 2, ...)
        s(1, 2, 3, ...)
        s(1, 2, 3, ..., 10)

    *Geometric sequence*. Three terms required, more allowed if consistent.
    May have an optional final element::

        s(1, 2, 4, ...)
        s(1, 2, 4, ..., 512)
        s(1, 1/2, 1/4, ..., 1/512)

    We support also symbolic input::

        from sympy import symbols
        x0, k = symbols("x0, k", real=True)

        s(x0, ...)
        s(x0, x0 + k, ...)
        s(x0, x0 + k, ..., x0 + 5*k)
        s(x0, x0*k, x0*k**2, ...)
        s(x0, x0*k, x0*k**2, ..., x0*k**5)

    **Notes**

    Symbolic input will create a generator that yields SymPy expressions.

    For floating-point input, the created generators avoid accumulating roundoff
    error (unlike e.g. ``itertools.count``). Even for a long but finite arithmetic
    sequence where the start value and the diff are not exactly representable
    by base-2 floats, the final value should be within 1 ULP of the true value.

    Inspired by Haskell's sequence notation.
    """
    origspec = spec

    def eq(a, b, tol=1e-8):
        # https://floating-point-gui.de/errors/comparison/
        if a == b:  # infinities and such, plus any non-float type
            return True

        if isinstance(a, mpf) and isinstance(b, mpf):
            return almosteq(a, b, tol)
        # compare as native float if only one is an mpf
        elif isinstance(a, mpf) and isinstance(b, float):
            a = float(a)
        elif isinstance(a, float) and isinstance(b, mpf):
            b = float(b)

        if not all(isinstance(x, float) for x in (a, b)):
            return False  # non-float type, already determined that a != b
        min_normal = float_info.min
        max_float = float_info.max
        d = abs(a - b)
        if a == 0 or b == 0 or d < min_normal:
            return d < tol * min_normal
        return d / min(abs(a) + abs(b), max_float) < tol

    def is_almost_int(x):
        try:
            return eq(float(int(x)), x)
        except TypeError:  # SymPy expression that didn't simplify to a number
            return False

    def analyze(*spec):  # raw spec (part before '...' if any) --> description
        l = len(spec)
        if l == 1:
            a0 = spec[0]
            return ("const", a0, None)
        elif l == 2:
            a0, a1 = spec
            d1 = a1 - a0
            if d1 == 0:
                return ("const", a0, None)
            return ("arith", a0, d1)
        elif l == 3:
            a0, a1, a2 = spec[:3]
            d1 = a1 - a0
            d2 = a2 - a1
            if d2 == d1 == 0:
                return ("const", a0, None)
            if eq(d2, d1):
                return ("arith", a0, d1)
            if a0 == 0 or a1 == 0 or a2 == 0:
                raise SyntaxError("Unexpected zero in specification '{}'".format(origspec))
            r1 = a1/a0
            r2 = a2/a1
            if eq(r2, r1):
                return ("geom", a0, r1)
            raise SyntaxError("Unsupported specification '{}'".format(origspec))
        else:  # more elements are optional but must be consistent
            data = [analyze(*triplet) for triplet in zip(spec, spec[1:], spec[2:])]
            seqtypes, x0s, ks = zip(*data)
            def isconst(*xs):
                first, *rest = xs
                return all(eq(x, first) for x in rest)
            if not isconst(seqtypes) or not isconst(ks):
                raise SyntaxError("Inconsistent specification '{}'".format(origspec))
            return data[0]

    # final term handler for finite sequences
    infty = float("inf")
    def nofterms(desc, elt):  # return number of terms in sequence or False
        seqtype, x0, k = desc
        if seqtype == "const":
            if elt == x0:
                return infty  # cannot determine how many items in a '...''d constant sequence
        elif seqtype == "arith":
            # elt = x0 + a*k --> a = (elt - x0) / k
            a = (elt - x0) / k
            if is_almost_int(a) and a > 0:
                return 1 + int(a)  # fencepost
        else: # seqtype == "geom":
            # elt = x0*(k**a) --> k**a = (elt/x0) --> a = logk(elt/x0)
            a = log(elt/x0, k)
            if is_almost_int(a) and a > 0:
                return 1 + int(a)
        return False

    # analyze the specification
    if Ellipsis not in spec:  # convenience fallback
        return (x for x in spec)
    else:
        *spec, last = spec
        if last is Ellipsis:
            seqtype, x0, k = analyze(*spec)
            n = infty
        else:
            *spec, dots = spec
            if dots is not Ellipsis:
                raise SyntaxError("Expected s(a0, a1, ...) or s(a0, a1, ..., an); got '{}'".format(origspec))
            desc = analyze(*spec)
            n = nofterms(desc, last)
            if n is False:
                raise SyntaxError("The final element, if present, must belong to the specified sequence; got '{}'".format(origspec))
            elif n is infty:
                raise SyntaxError("The length of a constant sequence cannot be determined from a final element; got '{}'".format(origspec))
            seqtype, x0, k = desc
        if not spec:
            raise SyntaxError("Expected at least one term before the '...'; got '{}'".format(origspec))

    # generate the sequence
    if seqtype == "const":
        return repeat(x0) if n is infty else repeat(x0, n)
    elif seqtype == "arith":
        # itertools.count doesn't avoid accumulating roundoff error for floats, so we implement our own.
        # This should be, for any j, within 1 ULP of the true result.
        def arith():
            j = 0
            while True:
                yield x0 + j*k
                j += 1
        return arith() if n is infty else take(n, arith())
    else: # seqtype == "geom":
        if isinstance(k, _symExpr) or k > 1:
            def geom():
                j = 0
                while True:
                    yield x0*(k**j)
                    j += 1
        else:
            # e.g. "3" can be represented exactly as a base-2 float, but "1/3" can't,
            # so it's better to do the arithmetic with the inverse and then use division.
            #
            # Note that 1/(1/3) --> 3.0 even for floats, so we don't actually
            # need to modify the detection algorithm to account for this.
            kinv = 1/k
            def geom():
                j = 0
                while True:
                    yield x0/(kinv**j)
                    j += 1
        return geom() if n is infty else take(n, geom())
