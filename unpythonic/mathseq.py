# -*- coding: utf-8 -*-
"""Create lazy constant, arithmetic and geometric sequences with compact syntax.

Numeric (int, float, mpmath) and symbolic (SymPy) formats are supported.

Avoids accumulating roundoff error when used with floating-point.
"""

__all__ = ["s"]

from itertools import repeat
from .it import take

# stuff to support float, mpf and SymPy expressions transparently
#
from sys import float_info
from math import log as math_log, copysign
try:
    from mpmath import mpf, almosteq
except ImportError:
    mpf = almosteq = None

def _numsign(x):
    if x == 0:
        return 0
    return int(copysign(1.0, x))

try:
    from sympy import log as _symlog, Expr as _symExpr, sign as _symsign
    def log(x, b):
        if isinstance(x, _symExpr):
            # https://stackoverflow.com/questions/46129259/how-to-simplify-logarithm-of-exponent-in-sympy
            return _symlog(x, b).expand(force=True)
        return math_log(x, b)
    def sign(x):
        if isinstance(x, _symExpr):
            return _symsign(x)
        return _numsign(x)
except ImportError:
    log = math_log
    sign = _numsign

def s(*spec):
    """Create a lazy mathematical sequence.

    The sequence is returned as a generator object.

    **Formats**

    Any ellipsis ``...`` inside an ``s()`` is meant literally.

    The sequence specification may have an optional final element, which must
    belong to the sequence being described. If a final element is specified,
    a finite sequence is returned.

    *Convenience fallback*:

    As a fallback, we accept an explicit enumeration of all elements of the
    desired sequence. This returns a genexpr that reads from a tuple. Syntax::

        s(1, 2, 3, 4, 5)

    This mainly exists so that the ``...``, if any, can be quickly dropped
    when testing/debugging the user program.

    *Constant sequence*: ``[a0, identity] -> a0, a0, a0, ...``

    Syntax::

        s(1, ...)

    Constant sequences **do not** support the optional-final-element termination
    syntax, because the number of terms cannot be computed from the value of the
    final element.

    *Arithmetic sequence*: ``[a0, +d] -> a0, a0 + d, a0 + 2 d, ...``

    Two terms required, more allowed if consistent. Syntax::

        s(1, 2, ...)
        s(1, 2, 3, ...)
        s(1, 2, 3, ..., 10)

    *Geometric sequence*: ``[a0, *r] -> a0, a0*r, a0*r**2, ...``

    Three terms required, more allowed if consistent. Syntax::

        s(1, 2, 4, ...)
        s(1, -2, 4, ...)  # alternating geometric sequence
        s(1, 2, 4, ..., 512)
        s(1, -2, 4, ..., -512)
        s(1, 1/2, 1/4, ...)
        s(1, -1/2, 1/4, ...)
        s(1, 1/2, 1/4, ..., 1/512)
        s(1, -1/2, 1/4, ..., -1/512)

    Specified as ``s(a0, a1, a2, ...)``, it must hold that ``a0, a1, a2 != 0``.

    Note the sequence ``a0, a0**2, a0**3, ...`` is a special case of a geometric
    sequence, with ``r = a0``.

    *Power sequence*: ``[a0, **p] -> a0, a0**p, a0**(2 p), ...``

    Three terms required, more allowed if consistent. Syntax::

        s(2, 32, 1024, ...)        #  2,      2**5,       2**10,  ...
        s(2, 1/32, 1/1024, ...)    #  2,    2**(-5),    2**(-10), ...
        s(-2, -32, 1024, ...)      # -2,   (-2)**5,    (-2)**10,  ...
        s(-2, -1/32, 1/1024, ...)  # -2, (-2)**(-5), (-2)**(-10), ...

    Specified as ``s(a0, a1, a2, ...)``, it must hold that ``|a0| != 1`` and
    ``a1, a2 != 0``.

    If ``spec`` matches none of the above, ``SyntaxError`` is raised at runtime.

    **Symbolic input**

    We support symbolic (SymPy) input for any of the formats::

        from sympy import symbols
        x0 = symbols("x0", real=True)
        k = symbols("x0", positive=True)

        s(x0, ...)
        s(x0, x0 + k, ...)
        s(x0, x0 + k, ..., x0 + 5*k)
        s(x0, x0*k, x0*k**2, ...)
        s(x0, -x0*k, x0*k**2, ...)
        s(x0, x0*k, x0*k**2, ..., x0*k**5)
        s(x0, -x0*k, x0*k**2, ..., -x0*k**5)

    For a symbolic geometric sequence with a final term, it is important that
    SymPy can determine the correct sign; hence in this example we have declared
    ``k`` as positive.

    **Composition**

    We support only these four basic kinds of sequences, because many more
    can be built using them as building blocks. For example::

        1, 4, 9, 16, ...:       (x**2 for x in s(1, 2, ...))
        1, 1/2, 1/3, 1/4, ...:  (1/x for x in s(1, 2, ...))

    **Notes**

    Symbolic input will create a generator that yields SymPy expressions.

    For floating-point input, the created generators avoid accumulating roundoff
    error (unlike e.g. ``itertools.count``). Even for a long but finite arithmetic
    sequence where the start value and the diff are not exactly representable
    by base-2 floats, the final value should be within 1 ULP of the true value.

    Inspired by Haskell's sequence notation.
    """
    origspec = spec  # for error messages

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
        except TypeError:  # likely a SymPy expression that didn't simplify to a number
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
            if d2 == d1 == 0:   # a0, a0, a0, ...             [a0, identity]
                return ("const", a0, None)
            if eq(d2, d1):      # a0, a0 + d, a0 + 2 d, ...   [a0, +d]
                return ("arith", a0, d1)
            if a0 != 0 and a1 != 0 and a2 != 0:
                r1 = a1/a0
                r2 = a2/a1
                if eq(r2, r1):  # a0, a0*r, a0*r**2, ...      [a0, *r]
                    return ("geom", a0, r1)
            if abs(a0) != 1 and a1 != 0 and a2 != 0:
                p1 = log(abs(a1), abs(a0))
                p2 = log(abs(a2), abs(a0))
                if is_almost_int(p2/p1):  # a0, a0**p, a0**(2*p), ...   [a0, **p]
                    return ("power", a0, p1)
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

    # final term handler for finite sequences - compute how many terms we should generate in total
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
        elif seqtype == "geom":
            # elt = x0*(k**a) --> k**a = (elt/x0) --> a = logk(elt/x0)
            a = log(abs(elt/x0), abs(k))
            if is_almost_int(a) and a > 0:
                if k < 0:  # check parity of final term for alternating geometric sequence
                    m = +1 if int(a) % 2 == 0 else -1
                    if not (sign(elt) == m*sign(x0)):
                        return False
                return 1 + int(a)
        else: # seqtype == "power":
            # elt = x0**(a*k) --> k a = logx0 elt --> a = (logx0 elt) / k
            a = log(abs(elt), abs(x0)) / k
            if is_almost_int(a) and a > 0:
                if x0 < 0:  # alternating power sequence
                    m = +1 if int(a) % 2 == 0 else -1
                    if not (sign(elt) == m*sign(x0)):
                        return False
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
    elif seqtype == "geom":
        if isinstance(k, _symExpr) or abs(k) >= 1:
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
    else: # seqtype == "power":
        def power():
            yield x0
            j = 1
            while True:
                yield x0**(j*k)
                j += 1
        return power() if n is infty else take(n, power())
