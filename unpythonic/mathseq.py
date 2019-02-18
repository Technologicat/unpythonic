# -*- coding: utf-8 -*-
"""Lazy constant, arithmetic, geometric and power sequences with compact syntax.

Numeric (int, float, mpmath) and symbolic (SymPy) formats are supported.

Avoids accumulating roundoff error when used with floating-point.
"""

__all__ = ["s", "sadd", "smul", "spow", "cauchyprod"]

from itertools import repeat
from .it import take, rev
from .gmemo import imemoize

from operator import add as primitive_add, mul as primitive_mul, pow as primitive_pow

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

    The sequence ``a0, a0**2, a0**3, ...`` is just a special case of a geometric
    sequence, with ``r = a0``, so e.g. ``s(3, 9, 27, ...)`` works as expected.

    *Power sequence*: ``[a0, **p] -> a0, a0**p, a0**(p**2), ...``

    Three terms required, more allowed if consistent. Syntax::

        s(2, 4, 16, ...)
        s(2, 2**2, 2**4, ...)  # equivalent
        s(2, 2**(1/2), 2**(1/4), ...)

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

        x0, k = symbols("x0, k", positive=True)
        s(x0, x0**k, x0**(k**2), ...)
        s(x0, x0**k, x0**(k**2), ..., x0**(k**5))

    For a symbolic geometric sequence with a final term, it is important that
    SymPy can determine the correct sign; hence in this example we have declared
    ``k`` as positive.

    **Composition**

    We support only these four basic kinds of sequences, because many more
    can be built using them as building blocks. For example::

        1, 4, 9, 16, ...:       s(1, 2, ...)**2
        1, 1/2, 1/3, 1/4, ...:  1 / s(1, 2, ...)

        x = symbols("x", real=True)  # SymPy
        px = lambda stream: stream * s(1, x, x**2, ...)
        s1 = px(s(1, 3, 5, ...))  # 1, 3*x, 5*x**2, ...
        s2 = px(s(2, 4, 6, ...))  # 2, 4*x, 6*x**2, ...

    Sequences returned by ``s()`` support infix math syntax.

    **Notes**

    Symbolic input will create a generator that yields SymPy expressions.

    For floating-point input, the created generators avoid accumulating roundoff
    error (unlike e.g. ``itertools.count``). Even for a long but finite arithmetic
    sequence where the start value and the diff are not exactly representable
    by base-2 floats, the final value should be within 1 ULP of the true value.

    Note this reverse-engineers the given numbers to figure out which case the
    input corresponds to. Although we take some care to avoid roundoff errors
    with floating-point input, it may sometimes occur that roundoff prevents
    correct detection of the sequence (especially for power sequences, since
    their detection requires taking logarithms).

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
            return eq(float(round(x)), x)
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
                d = (d1 + d2)/2  # average to give roundoff errors a chance to cancel
                return ("arith", a0, d)
            if a0 != 0 and a1 != 0 and a2 != 0:
                r1 = a1/a0
                r2 = a2/a1
                if eq(r2, r1):  # a0, a0*r, a0*r**2, ...      [a0, *r]
                    r = (r1 + r2)/2
                    return ("geom", a0, r)
            if abs(a0) != 1 and a1 != 0 and a2 != 0:
                p1 = log(abs(a1), abs(a0))
                p2 = log(abs(a2), abs(a1))
                if eq(p1, p2):  # a0, a0**p, (a0**p)**p, ...  [a0, **p]
                    p = (p1 + p2)/2
                    return ("power", a0, p)
            raise SyntaxError("Specification did not match any supported formula: '{}'".format(origspec))
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
    def nofterms(desc, elt):  # return total number of terms in sequence or False
        seqtype, x0, k = desc
        if seqtype == "const":
            if elt == x0:
                return infty  # cannot determine how many items in a '...''d constant sequence
        elif seqtype == "arith":
            # elt = x0 + a*k --> a = (elt - x0) / k
            a = (elt - x0) / k
            if is_almost_int(a) and a > 0:
                return 1 + round(a)  # fencepost
        elif seqtype == "geom":
            # elt = x0*(k**a) --> k**a = (elt/x0) --> a = logk(elt/x0)
            a = log(abs(elt/x0), abs(k))
            if is_almost_int(a) and a > 0:
                if not eq(x0*(k**a), elt):  # check parity of final term, could be an alternating sequence
                    return False
                return 1 + round(a)
        else: # seqtype == "power":
            # elt = x0**(k**a) --> k**a = logx0 elt --> a = logk (logx0 elt)
            a = log(log(abs(elt), abs(x0)), abs(k))
            if is_almost_int(a) and a > 0:
                if not eq(x0**(k**a), elt):  # parity
                    return False
                return 1 + round(a)
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
        return MathStream(repeat(x0) if n is infty else repeat(x0, n))
    elif seqtype == "arith":
        # itertools.count doesn't avoid accumulating roundoff error for floats, so we implement our own.
        # This should be, for any j, within 1 ULP of the true result.
        def arith():
            j = 0
            while True:
                yield x0 + j*k
                j += 1
        return MathStream(arith() if n is infty else take(n, arith()))

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
        return MathStream(geom() if n is infty else take(n, geom()))
    else: # seqtype == "power":
        if isinstance(k, _symExpr) or abs(k) >= 1:
            def power():
                j = 0
                while True:
                    yield x0**(k**j)
                    j += 1
        else:
            kinv = 1/k
            def power():
                j = 0
                while True:
                    yield x0**(1/(kinv**j))
                    j += 1
        return MathStream(power() if n is infty else take(n, power()))

class MathStream:
    """Base class for a numeric or symbolic mathematical sequence.

    This is used to enable infix arithmetic on sequences.
    """
    def __init__(self, generator_instance):
        self._g = generator_instance
    def __iter__(self):
        return self._g
    # TODO: the rest of the numeric methods
    # https://docs.python.org/3/reference/datamodel.html#emulating-numeric-types
    def __add__(self, other):
        return sadd(self, other)
    def __radd__(self, other):
        return sadd(other, self)
    def __sub__(self, other):
        return sadd(self, smul(other, -1))
    def __rsub__(self, other):
        return sadd(other, smul(self, -1))
    def __mul__(self, other):
        return smul(self, other)
    def __rmul__(self, other):
        return smul(other, self)
    def __truediv__(self, other):
        return smul(self, spow(other, -1))
    def __rtruediv__(self, other):
        return smul(other, spow(self, -1))
    def __pow__(self, other):
        return spow(self, other)
    def __rpow__(self, other):
        return spow(other, self)
    def __neg__(self):
        return smul(self, -1)
    def __pos__(self):
        return self
    def __abs__(self):
        return MathStream(abs(x) for x in iter(self))

def _make_termwise_stream_op(op):
    def sop(s1, s2):
        ig = [hasattr(x, "__iter__") for x in (s1, s2)]
        if all(ig):
            # it's very convenient here that zip() terminates when the shorter input runs out.
            return MathStream(op(a, b) for a, b in zip(s1, s2))
        elif not any(ig):
            return op(s1, s2)
        elif ig[0]:
            c = s2
            return MathStream(op(a, c) for a in s1)
        else: # ig[1]:
            c = s1
            return MathStream(op(c, a) for a in s2)  # careful; op might not be commutative
    return sop

_add = _make_termwise_stream_op(primitive_add)
def sadd(s1, s2):
    """a + b when one or both are streams (generators). If both, then termwise."""
    return _add(s1, s2)

_mul = _make_termwise_stream_op(primitive_mul)
def smul(s1, s2):
    """a*b when one or both are streams (generators). If both, then termwise."""
    return _mul(s1, s2)

_pow = _make_termwise_stream_op(primitive_pow)
def spow(s1, s2):
    """a**b when one or both are streams (generators). If both, then termwise."""
    return _pow(s1, s2)

def cauchyprod(s1, s2):
    """Cauchy product of infinite sequences.

    Formula::

        out[k] = sum(s1[j]*s2[k-j], j = 0, 1, ..., k)

    **CAUTION**: This will ``imemoize`` both inputs; the usual caveats apply.
    """
    if not all(hasattr(x, "__iter__") for x in (s1, s2)):
        raise TypeError("Expected two generators, got '{}', '{}'".format(type(s1), type(s2)))
    g_s1 = imemoize(s1)
    g_s2 = imemoize(s2)
    def cauchy():
        n = 1
        while True:
            a = take(n, g_s1())
            b = rev(take(n, g_s2()))
            terms = tuple(smul(a, b))
            if len(terms) < n:  # at least one of the inputs ran out
                break
            yield sum(terms)
            n += 1
    return MathStream(cauchy())
