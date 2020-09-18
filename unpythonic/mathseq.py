# -*- coding: utf-8 -*-
"""Mathematical sequences.

We provide a compact syntax to create lazy constant, arithmetic, geometric and
power. Numeric (int, float, mpmath) and symbolic (SymPy) formats are supported.
We avoid accumulating roundoff error when used with floating-point.

We also provide arithmetic operation support for iterables (termwise).

The function versions of the arithmetic operations have an **s** prefix (short
for mathematical **sequence**), because in Python the **i** prefix (which could
stand for *iterable*) is already used to denote the in-place operators.

We provide the Cauchy product, and its generalization, the diagonal
combination-reduction, for two (possibly infinite) iterables.

Finally, we provide ready-made generators that yield some common sequences
(currently, the Fibonacci numbers and the prime numbers).
"""

__all__ = ["s", "imathify", "gmathify",
           "m", "mg",  # old names, pre-0.14.3, will go away in 0.15.0
           "almosteq",
           "sadd", "ssub", "sabs", "spos", "sneg", "sinvert", "smul", "spow",
           "struediv", "sfloordiv", "smod", "sdivmod",
           "sround", "strunc", "sfloor", "sceil",
           "slshift", "srshift", "sand", "sxor", "sor",
           "cauchyprod", "diagonal_reduce",
           "fibonacci", "primes"]

from warnings import warn
from itertools import repeat, takewhile, count
from functools import wraps
from operator import (add as primitive_add, mul as primitive_mul,
                      pow as primitive_pow, mod as primitive_mod,
                      floordiv as primitive_floordiv, truediv as primitive_truediv,
                      sub as primitive_sub,
                      neg as primitive_neg, pos as primitive_pos,
                      and_ as primitive_and, xor as primitive_xor, or_ as primitive_or,
                      lshift as primitive_lshift, rshift as primitive_rshift,
                      invert as primitive_invert,
                      lt as primitive_lt, le as primitive_le,
                      eq as primitive_eq, ne as primitive_ne,
                      ge as primitive_ge, gt as primitive_gt)

from .it import take, rev, window
from .gmemo import imemoize, gmemoize

class _NoSuchType:
    pass

# stuff to support float, mpf and SymPy expressions transparently
#
from sys import float_info
from math import log as math_log, copysign, trunc, floor, ceil
try:
    from mpmath import mpf, almosteq as mpf_almosteq
except ImportError:  # pragma: no cover, optional at runtime, but installed at development time.
    # Can't use a gensym here since `mpf` must be a unique *type*.
    mpf = _NoSuchType
    mpf_almosteq = None

def _numsign(x):
    """The sign function, for numeric inputs."""
    if x == 0:
        return 0
    return int(copysign(1.0, x))

try:
    from sympy import log as _symlog, Expr as _symExpr, sign as _symsign
    def log(x, b=None):
        """The logarithm function.

        Works for both numeric and symbolic (`SymPy.Expr`) inputs.

        Default base `b=None` means `e`, i.e. take the natural logarithm.
        """
        if isinstance(x, _symExpr):
            # https://stackoverflow.com/questions/46129259/how-to-simplify-logarithm-of-exponent-in-sympy
            if b is not None:
                return _symlog(x, b).expand(force=True)
            else:
                return _symlog(x).expand(force=True)
        if b is not None:
            return math_log(x, b)
        else:
            return math_log(x)
    def sign(x):
        """The sign function.

        Works for both numeric and symbolic (`SymPy.Expr`) inputs.
        """
        if isinstance(x, _symExpr):
            return _symsign(x)
        return _numsign(x)
except ImportError:  # pragma: no cover, optional at runtime, but installed at development time.
    log = math_log
    sign = _numsign
    _symExpr = _NoSuchType

# TODO: Overhaul `almosteq` in v0.15.0, should work like mpf for consistency.
# TODO: Also move it to `unpythonic.misc`, where `ulp` already is. Or make a `numutil`.
def almosteq(a, b, tol=1e-8):
    """Almost-equality that supports several formats.

    The tolerance ``tol`` is used for the builtin ``float`` and ``mpmath.mpf``.

    For ``mpmath.mpf``, we just delegate to ``mpmath.almosteq``, with the given
    ``tol``. For ``float``, we use the strategy suggested in:

        https://floating-point-gui.de/errors/comparison/

    Anything else, for example SymPy expressions, strings, and containers
    (regardless of content), is tested for exact equality.

    **CAUTION**: Although placed in ``unpythonic.mathseq``, this function
    **does not** support iterables; rather, it is a low-level tool that is
    exposed in the public API in the hope it may be useful elsewhere.
    """
    if a == b:  # infinities and such, plus any non-float type
        return True

    if isinstance(a, mpf) and isinstance(b, mpf):
        return mpf_almosteq(a, b, tol)
    # compare as native float if only one is an mpf
    elif isinstance(a, mpf) and isinstance(b, (float, int)):
        a = float(a)
    elif isinstance(a, (float, int)) and isinstance(b, mpf):
        b = float(b)

    if not all(isinstance(x, (float, int)) for x in (a, b)):
        return False  # non-float type, already determined that a != b
    min_normal = float_info.min
    max_float = float_info.max
    d = abs(a - b)
    if a == 0 or b == 0 or d < min_normal:
        return d < tol * min_normal
    return d / min(abs(a) + abs(b), max_float) < tol

def s(*spec):
    """Create a lazy mathematical sequence.

    The sequence is returned as a generator object that supports infix math
    (see ``m``).

    **Formats**

    Below, any ellipsis ``...`` inside an ``s()`` is meant literally.

    The sequence specification may have an optional final element, which must
    belong to the sequence being described. If a final element is specified,
    a finite sequence is returned, terminating after the given final element.

    *Convenience fallback*:

    As a fallback, we accept an explicit enumeration of all elements of the
    desired sequence. This returns a genexpr that reads from a tuple, but
    adds infix math support. Syntax::

        s(1, 2, 3, 4, 5)

    This mainly exists so that the ``...``, if any, can be quickly dropped
    when testing/debugging the user program.

    *Constant sequence*: ``[a0, identity] -> a0, a0, a0, ...``

    Syntax::

        s(1, ...)

    Constant sequences **do not** support the optional-final-element termination
    syntax, because the number of terms cannot be computed from the value of the
    final element.

    *Cyclic sequence*:

    Convenience feature. Tag the repeating cycle of elements with a list
    (must be a list, not a tuple). The list must have at least one element.
    A final ``...``, after the list, is mandatory. Syntax::

        s([*repeats], ...)
        s(*initials, [*repeats], ...)

    Examples::

        s([1, 2], ...)        # --> 1, 2, 1, 2, 1, 2, ...
        s(1, 2, [3, 4], ...)  # --> 1, 2, 3, 4, 3, 4, ... (3, 4 repeat)

    Cyclic sequences **do not** support the optional-final-element termination
    syntax.

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

    Sequences returned by ``s()`` support infix math syntax, so the above
    expressions with ``s()`` are valid Python code.

    A symbolic example::

        from sympy import symbols
        x = symbols("x", real=True)
        powers_of_x = lambda: s(1, x, x**2, ...)
        univariate_polynomial = lambda coeffs: coeffs * powers_of_x()
        s1 = univariate_polynomial(s(1, 3, 5, ...))  # 1, 3*x, 5*x**2, ...
        s2 = univariate_polynomial(s(2, 4, 6, ...))  # 2, 4*x, 6*x**2, ...

    In the example, the lambda is needed because the iterable produced
    by `s(...)` is consumable; hence we must instantiate a new copy of
    the powers of x each time `univariate_polynomial` is called.
    We could also use `gmathify(imemoize(...))`:

        powers_of_x = gmathify(imemoize(s(1, x, x**2, ...)))
        univariate_polynomial = lambda coeffs: coeffs * powers_of_x()

    The rest as above.

    **Notes**

    Symbolic input will create a generator that yields SymPy expressions.

    For floating-point input, the created generators avoid accumulating roundoff
    error (unlike e.g. ``itertools.count``). Even for a long but finite arithmetic
    sequence where the start value and the diff are not exactly representable
    by base-2 floats, the final value should be within 1 ULP of the true value.
    This is because once the input has been analyzed, the terms are generated
    from the closed-form formula for the nth term of the sequence that was
    described by the input; nothing is actually accumulated.

    Note this reverse-engineers the given numbers to figure out which case the
    input corresponds to. Although we take some care to avoid roundoff errors
    in this analysis when used with floating-point input, it may sometimes occur
    that roundoff prevents correct detection of the sequence (especially for
    power sequences, since their detection requires taking logarithms).

    Inspired by Haskell's sequence notation.
    """
    origspec = spec  # for error messages

    def is_almost_int(x):
        try:
            return almosteq(float(round(x)), x)
        except TypeError:  # likely a SymPy expression that didn't simplify to a number
            return False

    def analyze(*spec):  # raw spec (part before '...' if any) --> description
        n = len(spec)
        if n == 1:
            a0 = spec[0]
            return ("const", a0, None)
        elif n == 2:
            a0, a1 = spec
            d1 = a1 - a0
            if d1 == 0:
                return ("const", a0, None)
            return ("arith", a0, d1)
        elif n == 3:
            a0, a1, a2 = spec
            d1 = a1 - a0
            d2 = a2 - a1
            if d2 == d1 == 0:         # a0, a0, a0, ...             [a0, identity]
                return ("const", a0, None)
            if almosteq(d2, d1):      # a0, a0 + d, a0 + 2 d, ...   [a0, +d]
                if d1 == d2:
                    d = d1
                else:
                    # Note: even an arithmetic sequence will now become float.
                    d = (d1 + d2) / 2  # average to give roundoff errors a chance to cancel
                return ("arith", a0, d)
            if a0 != 0 and a1 != 0 and a2 != 0:
                r1 = a1 / a0
                r2 = a2 / a1
                if almosteq(r2, r1):  # a0, a0*r, a0*r**2, ...      [a0, *r]
                    if all(isinstance(a, int) for a in (a0, a1, a2)) and a1 // a0 == r1 and a2 // a1 == r2:
                        r = a1 // a0
                    else:
                        # becomes float
                        r = (r1 + r2) / 2
                    return ("geom", a0, r)
            if abs(a0) != 1 and a1 != 0 and a2 != 0:
                p1 = log(abs(a1), abs(a0))
                p2 = log(abs(a2), abs(a1))
                if almosteq(p1, p2):  # a0, a0**p, (a0**p)**p, ...  [a0, **p]
                    p = (p1 + p2) / 2
                    return ("power", a0, p)
            # Most unrecognized sequences trigger this case.
            raise SyntaxError("Specification did not match any supported formula: '{}'".format(origspec))
        else:  # more elements are optional but must be consistent
            data = [analyze(*triplet) for triplet in window(iterable=spec, n=3)]
            seqtypes, x0s, ks = zip(*data)
            def isconst(xs):
                first, *rest = xs
                return all(almosteq(x, first) for x in rest)
            if not isconst(seqtypes) or not isconst(ks):
                # This case is only triggered if all triplets specify some
                # recognized sequence, but the specifications don't agree.
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
                return int(1 + round(a))  # fencepost
        elif seqtype == "geom":
            # elt = x0*(k**a) --> k**a = (elt/x0) --> a = logk(elt/x0)
            a = log(abs(elt / x0), abs(k))
            if is_almost_int(a) and a > 0:
                if not almosteq(x0 * (k**a), elt):  # check parity of final term, could be an alternating sequence
                    return False
                return int(1 + round(a))
        else:  # seqtype == "power":
            # elt = x0**(k**a) --> k**a = logx0 elt --> a = logk (logx0 elt)
            a = log(log(abs(elt), abs(x0)), abs(k))
            if is_almost_int(a) and a > 0:
                if not almosteq(x0**(k**a), elt):  # parity
                    return False
                return int(1 + round(a))
        return False

    # v0.14.3+: cyclic infinite sequences
    def iscyclic(spec):
        assert len(spec) >= 1
        *maybe_initial, maybe_repeating = spec
        if isinstance(maybe_repeating, list):
            if not maybe_repeating:
                raise SyntaxError("Expected non-empty list of repeating elements for cyclic sequence.")
            return True
        return False

    # analyze the specification
    if Ellipsis not in spec:  # convenience fallback
        if iscyclic(spec):
            raise SyntaxError("Expected final ... for cyclic sequence.")
        return imathify(x for x in spec)
    else:
        *spec, last = spec
        if last is Ellipsis:
            if not spec:
                raise SyntaxError("Expected s(a0, a1, ...), s(a0, a1, ..., an), s([*repeats], ...), or s(*initials, [*repeats], ...); got '{}'".format(origspec))
            assert spec  # not empty
            # v0.14.3+: cyclic infinite sequences
            if iscyclic(spec):
                seqtype = "cyclic"
                *initial, repeating = spec
                n = infty
            else:
                seqtype, x0, k = analyze(*spec)
                n = infty
        else:
            *spec, dots = spec
            if not (dots is Ellipsis and spec):
                raise SyntaxError("Expected s(a0, a1, ...) or s(a0, a1, ..., an), s([*repeats], ...), or s(*initials, [*repeats], ...); got '{}'".format(origspec))
            assert spec  # not empty
            desc = analyze(*spec)
            n = nofterms(desc, last)
            if n is False:
                raise SyntaxError("The final element, if present, must belong to the specified sequence; got '{}'".format(origspec))
            elif n is infty:
                raise SyntaxError("The length of a constant sequence cannot be determined from a final element; got '{}'".format(origspec))
            seqtype, x0, k = desc

    # generate the sequence
    if seqtype == "const":
        return imathify(repeat(x0) if n is infty else repeat(x0, n))
    elif seqtype == "cyclic":
        def cyclic():
            yield from initial
            while True:
                yield from repeating
        return imathify(cyclic())
    elif seqtype == "arith":
        # itertools.count doesn't avoid accumulating roundoff error for floats, so we implement our own.
        # This should be, for any j, within 1 ULP of the true result.
        def arith():
            j = 0
            while True:
                yield x0 + j * k
                j += 1
        return imathify(arith() if n is infty else take(n, arith()))
    elif seqtype == "geom":
        if isinstance(k, _symExpr) or abs(k) >= 1:
            def geoimathify():
                j = 0
                while True:
                    yield x0 * (k**j)
                    j += 1
        else:
            # e.g. "3" can be represented exactly as a base-2 float, but "1/3" can't,
            # so it's better to do the arithmetic with the inverse and then use division.
            #
            # Note that 1/(1/3) --> 3.0 even for floats, so we don't actually
            # need to modify the detection algorithm to account for this.
            kinv = 1 / k
            def geoimathify():
                j = 0
                while True:
                    yield x0 / (kinv**j)
                    j += 1
        return imathify(geoimathify() if n is infty else take(n, geoimathify()))
    else:  # seqtype == "power":
        if isinstance(k, _symExpr) or abs(k) >= 1:
            def power():
                j = 0
                while True:
                    yield x0**(k**j)
                    j += 1
        else:
            kinv = 1 / k
            def power():
                j = 0
                while True:
                    yield x0**(1 / (kinv**j))
                    j += 1
        return imathify(power() if n is infty else take(n, power()))

# -----------------------------------------------------------------------------

class imathify:
    """Endow any iterable with infix math support (termwise).

    The original iterable is saved to an attribute, and ``m.__iter__`` redirects
    to it. No caching is performed, so performing a math operation on the m'd
    iterable will still consume the iterable (if it is consumable, for example
    a generator).

    This adds infix math only; to apply a function (e.g. ``sin``) termwise to
    an iterable, use the comprehension syntax or ``map``, as usual.

    The mathematical sequences (Python-technically, iterables) returned by
    ``s()`` are automatically m'd, as is the result of any infix arithmetic
    operation performed on an already m'd iterable.

    **CAUTION**: When an operation meant for general iterables is applied to an
    m'd iterable, the math support vanishes (because the operation returns a
    general iterable, not an m'd one), but can be restored by m'ing again.

    **NOTE**: The function versions of the operations (``sadd`` etc.) work on
    general iterables (so you don't need to ``m`` their inputs), and return
    an m'd iterable. The ``m`` operation is only needed for infix math, to make
    arithmetic-heavy code more readable.

    Examples::

        a = s(1, 3, ...)
        b = s(2, 4, ...)
        c = a + b
        assert isinstance(c, m)  # the result still has math support
        assert tuple(take(5, c)) == (3, 7, 11, 15, 19)  # + was applied termwise

        d = 1 / (a**2 + b**2)
        assert isinstance(d, m)

        e = take(5, c)     # general iterable operation drops math support...
        assert not isinstance(e, m)

        f = imathify(take(5, c))  # ...and it can be restored by m'ing again.
        assert isinstance(f, m)

        g = imathify((1, 2, 3, 4, 5))
        h = imathify((2, 3, 4, 5, 6))
        assert tuple(g + h) == (3, 5, 7, 9, 11)

    See the relevant part of the Python language reference:

        https://docs.python.org/3/reference/datamodel.html#emulating-numeric-types
    """
    def __init__(self, iterable):
        self._g = iterable
    def __iter__(self):
        return iter(self._g)
    def __add__(self, other):
        return sadd(self, other)
    def __radd__(self, other):
        return sadd(other, self)
    def __sub__(self, other):
        return ssub(self, other)
    def __rsub__(self, other):
        return ssub(other, self)
    def __abs__(self):
        return sabs(self)
    def __pos__(self):
        return spos(self)
    def __neg__(self):
        return sneg(self)
    def __invert__(self):
        return sinvert(self)
    def __mul__(self, other):
        return smul(self, other)
    def __rmul__(self, other):
        return smul(other, self)
    def __truediv__(self, other):
        return struediv(self, other)
    def __rtruediv__(self, other):
        return struediv(other, self)
    def __floordiv__(self, other):
        return sfloordiv(self, other)
    def __rfloordiv__(self, other):
        return sfloordiv(other, self)
    def __divmod__(self, other):
        return sdivmod(self, other)
    def __rdivmod__(self, other):
        return sdivmod(other, self)
    def __mod__(self, other):
        return smod(self, other)
    def __rmod__(self, other):
        return smod(other, self)
    def __pow__(self, other, *mod):
        return spow(self, other, *mod)
    def __rpow__(self, other):
        return spow(other, self)
    def __round__(self, *ndigits):
        return sround(self, *ndigits)
    def __trunc__(self):
        return strunc(self)
    def __floor__(self):
        return sfloor(self)
    def __ceil__(self):
        return sceil(self)
    def __lshift__(self, other):
        return slshift(self, other)
    def __rlshift__(self, other):
        return slshift(other, self)
    def __rshift__(self, other):
        return srshift(self, other)
    def __rrshift__(self, other):
        return srshift(other, self)
    def __and__(self, other):
        return sand(self, other)
    def __rand__(self, other):
        return sand(other, self)
    def __xor__(self, other):
        return sxor(self, other)
    def __rxor__(self, other):
        return sxor(other, self)
    def __or__(self, other):
        return sor(self, other)
    def __ror__(self, other):
        return sor(other, self)
    # Can't do this because each of these conversion operators must return an
    # instance of that primitive type.
    # def __bool__(self):
    #     return sbool(self)
    # def __complex__(self):
    #     return scomplex(self)
    # def __int__(self):
    #     return sint(self)
    # def __float__(self):
    #     return sfloat(self)
    def __lt__(self, other):
        return slt(self, other)
    def __le__(self, other):
        return sle(self, other)
    def __eq__(self, other):
        return seq(self, other)
    def __ne__(self, other):
        return sne(self, other)
    def __ge__(self, other):
        return sge(self, other)
    def __gt__(self, other):
        return sgt(self, other)

class m(imathify):  # pragma: no cover
    """Alias for `imathify`, for backward compatibility.

    Will be removed in 0.15.0."""
    def __init__(self, iterable):
        warn("`m` has been renamed `imathify`, which is more descriptive; this alias will be removed in 0.15.0.", FutureWarning)
        super().__init__(iterable)

def gmathify(gfunc):
    """Decorator: make gfunc imathify() the returned generator instances.

    Return a new gfunc, which passes all its arguments to the original ``gfunc``.

    Example::

        a = gmathify(imemoize(s(1, 2, ...)))
        assert last(take(5, a())) == 5
        assert last(take(5, a())) == 5
        assert last(take(5, a() + a())) == 10
    """
    @wraps(gfunc)
    def mathify(*args, **kwargs):
        return imathify(gfunc(*args, **kwargs))
    return mathify

def mg(gfunc):  # pragma: no cover
    """Alias for `gmathify`, for backward compatibility.

    Will be removed in 0.15.0.
    """
    warn("`mg` has been renamed `gmathify`, which is more descriptive; this alias will be removed in 0.15.0.", FutureWarning)
    return gmathify(gfunc)

# -----------------------------------------------------------------------------
# We expose the full set of "imathify" operators also as functions à la the ``operator`` module.
# Prefix "s", short for "mathematical Sequence".
# https://docs.python.org/3/library/operator.html

# The *settings mechanism is used by round and pow.
# These are recursive to support iterables containing iterables (e.g. an iterable of math sequences).
def _make_termwise_stream_unop(op, *settings):
    def stream_op(a):
        if hasattr(a, "__iter__"):
            return imathify(stream_op(x) for x in a)
        return op(a, *settings)
    return stream_op
def _make_termwise_stream_binop(op, *settings):
    def stream_op(a, b):
        isiterable = [hasattr(x, "__iter__") for x in (a, b)]
        if all(isiterable):
            # it's very convenient here that zip() terminates when the shorter input runs out.
            return imathify(stream_op(x, y) for x, y in zip(a, b))
        elif isiterable[0]:
            c = b
            return imathify(stream_op(x, c) for x in a)
        elif isiterable[1]:
            c = a
            return imathify(stream_op(c, y) for y in b)  # careful; op might not be commutative
        else:  # not any(isiterable):
            return op(a, b, *settings)
    return stream_op

sadd = _make_termwise_stream_binop(primitive_add)
sadd.__doc__ = """Termwise a + b when one or both are iterables."""
ssub = _make_termwise_stream_binop(primitive_sub)
ssub.__doc__ = """Termwise a - b when one or both are iterables."""
sabs = _make_termwise_stream_unop(abs)
sabs.__doc__ = """Termwise abs(a) for an iterable."""
spos = _make_termwise_stream_unop(primitive_pos)
spos.__doc__ = """Termwise +a for an iterable."""
sneg = _make_termwise_stream_unop(primitive_neg)
sneg.__doc__ = """Termwise -a for an iterable."""
smul = _make_termwise_stream_binop(primitive_mul)
smul.__doc__ = """Termwise a * b when one or both are iterables."""

_pow = _make_termwise_stream_binop(primitive_pow)  # 2-arg form
def spow(a, b, *mod):
    """Termwise a ** b when one or both are iterables.

    An optional third argument is supported, and passed through to the
    built-in ``pow`` function.
    """
    op = _make_termwise_stream_binop(pow, mod[0]) if mod else _pow
    return op(a, b)

struediv = _make_termwise_stream_binop(primitive_truediv)
struediv.__doc__ = """Termwise a / b when one or both are iterables."""
sfloordiv = _make_termwise_stream_binop(primitive_floordiv)
sfloordiv.__doc__ = """Termwise a // b when one or both are iterables."""
smod = _make_termwise_stream_binop(primitive_mod)
smod.__doc__ = """Termwise a % b when one or both are iterables."""
sdivmod = _make_termwise_stream_binop(divmod)
sdivmod.__doc__ = """Termwise (a // b, a % b) when one or both are iterables."""

_round = _make_termwise_stream_unop(round)  # 1-arg form
def sround(a, *ndigits):
    """Termwise round(a) for an iterable.

    An optional second argument is supported, and passed through to the
    built-in ``round`` function.

    As with the built-in, rounding is correct taking into account the float
    representation, which is base-2.

        https://docs.python.org/3/library/functions.html#round
    """
    op = _make_termwise_stream_unop(round, ndigits[0]) if ndigits else _round
    return op(a)

strunc = _make_termwise_stream_unop(trunc)
strunc.__doc__ = """Termwise math.trunc(a) for an iterable."""
sfloor = _make_termwise_stream_unop(floor)
sfloor.__doc__ = """Termwise math.floor(a) for an iterable."""
sceil = _make_termwise_stream_unop(ceil)
sceil.__doc__ = """Termwise math.ceil(a) for an iterable."""

# bit twiddling operations
slshift = _make_termwise_stream_binop(primitive_lshift)
slshift.__doc__ = """Termwise a << b when one or both are iterables."""
srshift = _make_termwise_stream_binop(primitive_rshift)
srshift.__doc__ = """Termwise a >> b when one or both are iterables."""
sand = _make_termwise_stream_binop(primitive_and)
sand.__doc__ = """Termwise a & b when one or both are iterables."""
sxor = _make_termwise_stream_binop(primitive_xor)
sxor.__doc__ = """Termwise a ^ b when one or both are iterables."""
sor = _make_termwise_stream_binop(primitive_or)
sor.__doc__ = """Termwise a | b when one or both are iterables."""
sinvert = _make_termwise_stream_unop(primitive_invert)
sinvert.__doc__ = """Termwise ~a for an iterable.

Note this is a bitwise invert, which is usually not what you want.

However, there is no ``__not__`` method for object instances,
only the interpreter core defines that operation.

See:
    https://docs.python.org/3/library/operator.html#operator.not_
"""

# Can't do this because each of these conversion operators must return an
# instance of that primitive type.
#
# sbool = _make_termwise_stream_unop(bool)
# sbool.__doc__ = """Termwise bool(a) for an iterable."""
# scomplex = _make_termwise_stream_unop(complex)
# scomplex.__doc__ = """Termwise complex(a) for an iterable."""
# sint = _make_termwise_stream_unop(int)
# sint.__doc__ = """Termwise int(a) for an iterable."""
# sfloat = _make_termwise_stream_unop(float)
# sfloat.__doc__ = """Termwise float(a) for an iterable."""

slt = _make_termwise_stream_binop(primitive_lt)
slt.__doc__ = """Termwise a < b when one or both are iterables."""
sle = _make_termwise_stream_binop(primitive_le)
sle.__doc__ = """Termwise a <= b when one or both are iterables."""
seq = _make_termwise_stream_binop(primitive_eq)
seq.__doc__ = """Termwise a == b when one or both are iterables."""
sne = _make_termwise_stream_binop(primitive_ne)
sne.__doc__ = """Termwise a != b when one or both are iterables."""
sge = _make_termwise_stream_binop(primitive_ge)
sge.__doc__ = """Termwise a >= b when one or both are iterables."""
sgt = _make_termwise_stream_binop(primitive_gt)
sgt.__doc__ = """Termwise a > b when one or both are iterables."""

# -----------------------------------------------------------------------------

def cauchyprod(a, b, *, require="any"):
    """Cauchy product of two (possibly infinite) iterables.

    Defined by::

        c[k] = suimathify(a[j] * b[k-j], j = 0, 1, ..., k),  k = 0, 1, ...

    As a table::

              j
              0 1 2 3 ...
            +-----------
        i 0 | 0 1 2 3
          1 | 1 2 3
          2 | 2 3 .
          3 | 3     .
        ... |         .

    The element ``c[k]`` of the product is formed by summing all such
    ``a[i]*b[j]`` for which the table entry at ``(i, j)`` is ``k``.

    For more details (esp. the option ``require``, used for finite inputs),
    see the docstring of ``diagonal_reduce``, which is the general case of
    this diagonal construction, when we allow custom operations to take the
    roles of ``*`` and ``sum``.
    """
    return diagonal_reduce(a, b, require=require, combine=smul, reduce=sum)

def diagonal_reduce(a, b, *, combine, reduce, require="any"):
    """Diagonal combination-reduction for two (possibly infinite) iterables.

    Defined by::

        c[k] = reduce(combine(a[j], b[k-j]), j = 0, 1, ..., k),  k = 0, 1, ...

    As a table::

              j
              0 1 2 3 ...
            +-----------
        i 0 | 0 1 2 3
          1 | 1 2 3
          2 | 2 3 .
          3 | 3     .
        ... |         .

    The element ``c[k]`` is formed by reducing over all combinations of
    ``a[i], b[j]`` for which the table entry at ``(i, j)`` is ``k``.

    The Cauchy product is the special case with ``combine=smul, reduce=sum``.

    The output is automatically m'd so that it supports infix arithmetic.

    The operations:

        - ``combine = combine(a, b)`` is a binary operation that accepts
          two iterables, and combines them termwise into a new iterable.

          Roughly speaking, it gets the slices ``a[:(k+1)]`` and ``b[k::-1]``
          as its input iterables. (Roughly speaking, because of caching and
          finite input handling.) The inputs are guaranteed to have the same
          length.

        - ``reduce = reduce(a)`` is a unary operation that accepts one iterable,
          and produces a scalar. The reduction is only invoked if there is
          at least one term to process.

    The computations for ``a[i]`` and ``b[j]`` are triggered only once (ever)
    for each value of ``i`` or ``j``. The values then enter a local cache.

    The computational cost for the term ``c[k]`` is ``O(k)``, because although
    ``a[i]`` and ``b[j]`` are cached, the reduction itself consists of ``k + 1``
    terms that are all formed with new combinations of ``i`` and ``j``. This means
    the total cost of computing the ``n`` first terms of ``c`` is ``O(n**2)``.

    **CAUTION**: The caching works by applying ``imemoize`` to both inputs;
    the usual caveats apply.

    **Finite inputs**

    **When** ``require="any"``, we run with increasing ``k`` as long **any**
    combination appearing inside the above reduction can be formed. When ``k``
    has reached a value for which no combinations can be formed, the generator
    raises ``StopIteration``.

    In terms of the above table, the table is cut by vertical and horizontal lines
    just after the maximum possible ``i`` and ``j``, and only the terms in the
    upper left quadrant contribute to the reduction (since these are the only
    terms that can be formed).

    For example, if both ``a`` and ``b`` have length 2, and we are computing the
    Cauchy product, then the iterable ``c`` will consist of *three* terms:
    ``c[0] = a[0]*b[0]``, ``c[1] = a[0]*b[1] + a[1]*b[0]``, and
    ``c[2] = a[1]*b[1]``.

    **When** ``require="all"``, we run with increasing ``k`` until either end
    of the diagonal falls of the end of the shorter input. (In the case of inputs
    of equal length, both ends fall off simultaneously.) In other words, ``c[k]``
    is formed only if **all** combinations that would contribute to it (in the
    infinite case) can be formed.

    In terms of the above table, the diagonal marked with the value ``k`` is
    considered, and ``c[k]`` is formed only if all its combinations of
    ``a[i], b[j]`` can be formed from the given finite inputs.

    For example, if both ``a`` and ``b`` have length 2, and we are computing the
    Cauchy product, then the iterable ``c`` will consist of *two* terms:
    ``c[0] = a[0]*b[0]``, and ``c[1] = a[0]*b[1] + a[1]*b[0]``. The term ``c[2]``
    is not formed, because the terms ``a[0]*b[2]`` and ``a[2]*b[0]`` (that would
    contribute to it in the infinite case) cannot be formed from length-2 inputs.
    """
    if not all(hasattr(x, "__iter__") for x in (a, b)):
        raise TypeError("Expected two iterables, got {}, {}".format(type(a), type(b)))
    if require not in ("all", "any"):
        raise ValueError("require must be 'all' or 'any'; got '{}'".format(require))
    ga = imemoize(a)
    gb = imemoize(b)
    def diagonal():
        n = 1  # how many terms to take from a and b; output index k = n - 1
        while True:
            xs, ys = (tuple(take(n, g())) for g in (ga, gb))
            lx, ly = len(xs), len(ys)
            if require == "all" and (lx < n or ly < n):
                break
            if (lx == ly and lx < n) or lx < ly or ly < lx:
                xs = xs[(n - ly):]
                ys = ys[(n - lx):]
            assert len(xs) == len(ys)  # TODO: maybe take this out later?
            if not xs:
                break
            yield reduce(combine(xs, rev(ys)))
            n += 1
    return imathify(diagonal())

# -----------------------------------------------------------------------------

def fibonacci():
    """Return the Fibonacci numbers 1, 1, 2, 3, 5, 8, ... as a lazy sequence."""
    def fibos():
        a, b = 1, 1
        while True:
            yield a
            a, b = b, a + b
    return imathify(fibos())

# See test_gmemo.py for history. This is an FP-ized sieve of Eratosthenes.
#
# This version wins in speed for moderate n (1e5) on typical architectures where
# the memory bus is a bottleneck, since the rule for generating new candidates is
# simple arithmetic. Contrast memo_primes3, which needs to keep a table that gets
# larger as n grows (so memory transfers dominate for large n). That strategy
# seems faster for n ~ 1e3, though.
@gmemoize
def _primes():
    yield 2
    for n in count(start=3, step=2):
        if not any(n % p == 0 for p in takewhile(lambda x: x * x <= n, _primes())):
            yield n

@gmemoize
def _fastprimes():
    memo = []
    def primes():
        memo.append(2)
        yield 2
        for n in count(start=3, step=2):
            if not any(n % p == 0 for p in takewhile(lambda x: x * x <= n, memo)):
                memo.append(n)
                yield n
    return primes()

def primes(optimize="speed"):
    """Return the prime numbers 2, 3, 5, 7, 11, 13, ... as a lazy sequence.

    FP sieve of Eratosthenes with memoization.

    ``optimize`` is one of ``"memory"`` or ``"speed"``. The memory-optimized
    version shares one global memo, which is re-used also in the tight inner loop,
    whereas the speed-optimized one keeps exactly one more copy of the results
    as an internal memo (double memory usage, but faster, as it skips the very
    general ``gmemoize`` machinery in the inner loop).
    """
    if optimize not in ("memory", "speed"):
        raise ValueError("optimize must be 'memory' or 'speed'; got '{}'".format(optimize))
    if optimize == "speed":
        return imathify(_fastprimes())
    else:  # optimize == "memory":
        return imathify(_primes())
