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

__all__ = ["s", "imathify", "gmathify", "slift1", "slift2",
           "sadd", "ssub", "sabs", "spos", "sneg", "sinvert", "smul", "spow",
           "struediv", "sfloordiv", "smod", "sdivmod",
           "sround", "strunc", "sfloor", "sceil",
           "slshift", "srshift", "sand", "sxor", "sor",
           "cauchyprod", "diagonal_reduce",
           "fibonacci", "triangular", "primes"]

from collections.abc import Callable, Iterable, Iterator
from itertools import repeat, takewhile, count
from functools import wraps
from operator import (add as atom_add, mul as atom_mul,
                      pow as atom_pow, mod as atom_mod,
                      floordiv as atom_floordiv, truediv as atom_truediv,
                      sub as atom_sub,
                      neg as atom_neg, pos as atom_pos,
                      and_ as atom_and, xor as atom_xor, or_ as atom_or,
                      lshift as atom_lshift, rshift as atom_rshift,
                      invert as atom_invert,
                      lt as atom_lt, le as atom_le,
                      eq as atom_eq, ne as atom_ne,
                      ge as atom_ge, gt as atom_gt)

from typing import Any, Literal, TypeVar

# TODO: When floor bumps to 3.12, use inline `[T]` syntax on `slift1`
# and `slift2` (PEP 695). Also consider making `imathify` generic
# (`class imathify[T]`) — currently impractical because element types
# are determined at runtime and arithmetic mixes types.
T = TypeVar('T')

from .it import take, rev, window
from .gmemo import imemoize, gmemoize
from .numutil import almosteq

class _NoSuchType:
    pass

# stuff to support float, mpf and SymPy expressions transparently
#
from math import log as math_log, copysign, trunc, floor, ceil
try:
    from mpmath import mpf, almosteq as mpf_almosteq
except ImportError:  # pragma: no cover, optional at runtime, but installed at development time.
    # Can't use a gensym here since `mpf` must be a unique *type*.
    mpf = _NoSuchType
    mpf_almosteq = None

try:
    import sympy
except ImportError:  # pragma: no cover, optional at runtime, but installed at development time.
    sympy = None

def _numsign(x: Any) -> int:
    """The sign function, for numeric inputs."""
    if x == 0:
        return 0
    return int(copysign(1.0, x))

try:
    from sympy import log as _symlog, Expr as _symExpr, sign as _symsign
    def log(x: Any, b: Any = None) -> Any:
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
    def sign(x: Any) -> Any:
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


def s(*spec: Any) -> "imathify":
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

    def is_almost_int(x: Any) -> bool:
        try:
            if sympy and isinstance(x, sympy.Expr):
                x = sympy.N(x)
            return almosteq(float(round(x)), x)
        except TypeError:  # likely a SymPy expression that didn't simplify to a number
            return False

    def analyze(*spec: Any) -> tuple[str, Any, Any | None]:
        """Classify a raw sequence spec (the elements before ``...``) into a description.

        Returns ``(seqtype, x0, k)`` where:

        - ``seqtype``: ``"const"``, ``"arith"``, ``"geom"``, or ``"power"``
        - ``x0``: initial value (first element)
        - ``k``: sequence parameter — ``None`` for const, common difference ``d``
          for arith, common ratio ``r`` for geom, exponent ``p`` for power

        Requires 1–3 spec elements to identify the sequence type. More elements
        are accepted if consistent (checked by analyzing overlapping triplets).

        Cyclic sequences and ``Ellipsis`` handling are done by the caller (``s()``)
        before ``analyze`` is called; this function only sees the numeric elements.
        """
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
            raise SyntaxError(f"Specification did not match any supported formula: '{origspec}'")
        else:  # more elements are optional but must be consistent
            data = [analyze(*triplet) for triplet in window(3, spec)]
            seqtypes, x0s, ks = zip(*data)
            def isconst(xs: tuple[Any, ...]) -> bool:
                first, *rest = xs
                return all(almosteq(x, first) for x in rest)
            if not isconst(seqtypes) or not isconst(ks):
                # This case is only triggered if all triplets specify some
                # recognized sequence, but the specifications don't agree.
                raise SyntaxError(f"Inconsistent specification '{origspec}'")
            return data[0]

    infty = float("inf")
    def nofterms(desc: tuple[str, Any, Any | None], elt: Any) -> int | float | bool:
        """Compute total number of terms for a finite sequence with a final element.

        ``desc`` is a sequence descriptor ``(seqtype, x0, k)`` as returned by
        ``analyze``. ``elt`` is the final element specified by the user.

        Returns the total term count (``int``), ``float("+inf")`` if the length
        cannot be determined (constant sequence matching its own value), or
        ``False`` if ``elt`` does not belong to the described sequence.

        For geometric and power sequences, an alternating-sign parity check
        ensures ``elt`` has the correct sign for its position.
        """
        seqtype, x0, k = desc
        if seqtype == "const":
            if elt == x0:
                return infty
        elif seqtype == "arith":
            a = (elt - x0) / k  # elt = x0 + a*k
            if is_almost_int(a) and a > 0:
                return int(1 + round(a))  # fencepost
        elif seqtype == "geom":
            a = log(abs(elt / x0), abs(k))  # elt = x0*(k**a)
            if is_almost_int(a) and a > 0:
                if not almosteq(x0 * (k**a), elt):  # parity check for alternating sequences
                    return False
                return int(1 + round(a))
        else:  # seqtype == "power":
            a = log(log(abs(elt), abs(x0)), abs(k))  # elt = x0**(k**a)
            if is_almost_int(a) and a > 0:
                if not almosteq(x0**(k**a), elt):  # parity check
                    return False
                return int(1 + round(a))
        return False

    def iscyclic(spec: tuple[Any, ...]) -> bool:
        """Check whether ``spec`` describes a cyclic sequence.

        A cyclic spec has a ``list`` as its last element, marking the repeating
        cycle: ``(*initials, [*repeats])``. The list must be non-empty.
        """
        assert len(spec) >= 1
        *maybe_initial, maybe_repeating = spec
        if isinstance(maybe_repeating, list):
            if not maybe_repeating:
                raise SyntaxError("Expected non-empty list of repeating elements for cyclic sequence.")
            return True
        return False

    # Analyze the specification. We parse from the right, peeling off the trailing elements to determine which case we're in.
    if Ellipsis not in spec:  # no `...` — convenience fallback, explicit enumeration of all elements.
        if iscyclic(spec):  # a finite sequence can't be cyclic
            raise SyntaxError("Expected final ... for cyclic sequence.")
        return imathify(x for x in spec)
    else:  # has a `...`
        # Peel off the last element to see where the `...` is.
        *spec, last = spec
        if last is Ellipsis:  # s(a0, a1, ...) or s([*repeats], ...) — infinite sequence.
            if not spec:
                raise SyntaxError(f"Expected s(a0, a1, ...) or s(a0, a1, ..., an), s([*repeats], ...), or s(*initials, [*repeats], ...); got '{origspec}'")
            assert spec  # not empty
            if iscyclic(spec):
                seqtype = "cyclic"
                *initial, repeating = spec
                n = infty
            else:
                seqtype, x0, k = analyze(*spec)
                n = infty
        else:  # s(a0, a1, ..., an) — finite sequence with final element `last`.
            # Peel off the `...` (now second-to-last) and analyze the formula.
            *spec, dots = spec
            if not (dots is Ellipsis and spec):
                raise SyntaxError(f"Expected s(a0, a1, ...) or s(a0, a1, ..., an), s([*repeats], ...), or s(*initials, [*repeats], ...); got '{origspec}'")
            assert spec  # not empty
            desc = analyze(*spec)
            n = nofterms(desc, last)
            if n is False:
                raise SyntaxError(f"The final element, if present, must belong to the specified sequence; got '{origspec}'")
            elif n is infty:
                raise SyntaxError(f"The length of a constant sequence cannot be determined from a final element; got '{origspec}'")
            seqtype, x0, k = desc

    # generate the sequence
    if seqtype == "const":
        return imathify(repeat(x0) if n is infty else repeat(x0, n))
    elif seqtype == "cyclic":
        def cyclic() -> Iterator[Any]:
            yield from initial
            while True:
                yield from repeating
        return imathify(cyclic())
    elif seqtype == "arith":
        # itertools.count doesn't avoid accumulating roundoff error for floats, so we implement our own.
        # This should be, for any j, within 1 ULP of the true result.
        def arith() -> Iterator[Any]:
            j = 0
            while True:
                yield x0 + j * k
                j += 1
        return imathify(arith() if n is infty else take(n, arith()))
    elif seqtype == "geom":
        if isinstance(k, _symExpr) or abs(k) >= 1:
            def geom() -> Iterator[Any]:
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
            def geom() -> Iterator[Any]:
                j = 0
                while True:
                    yield x0 / (kinv**j)
                    j += 1
        return imathify(geom() if n is infty else take(n, geom()))
    else:  # seqtype == "power":
        if isinstance(k, _symExpr) or abs(k) >= 1:
            def power() -> Iterator[Any]:
                j = 0
                while True:
                    yield x0**(k**j)
                    j += 1
        else:
            kinv = 1 / k
            def power() -> Iterator[Any]:
                j = 0
                while True:
                    yield x0**(1 / (kinv**j))
                    j += 1
        return imathify(power() if n is infty else take(n, power()))

# -----------------------------------------------------------------------------

class imathify:
    """Endow any iterable with infix math support (termwise).

    The original iterable is saved to an attribute, and ``imathify.__iter__`` redirects
    to it. No caching is performed, so performing a math operation on the imathified
    iterable will still consume the iterable (if it is consumable, for example
    a generator).

    This adds infix math only; to apply a function (e.g. ``sin``) termwise to
    an iterable, use ``slift1`` (or ``slift2`` for binary operations)::

        from math import sin
        ssin = slift1(sin)
        sinseq = ssin(s(1, 2, ...))

    Or, for one-off use, wrap a generator expression in ``imathify``::

        sinseq = imathify(sin(x) for x in a)

    The mathematical sequences (Python-technically, iterables) returned by
    ``s()`` are automatically imathified, as is the result of any infix arithmetic
    operation performed on an already imathified iterable.

    **CAUTION**: When an operation meant for general iterables is applied to an
    m'd iterable, the math support vanishes (because the operation returns a
    general iterable, not an imathified one), but can be restored by m'ing again.

    **NOTE**: The function versions of the operations (``sadd`` etc.) work on
    general iterables (so you don't need to ``imathify`` their inputs), and return
    an imathified iterable. The ``imathify`` operation is only needed for infix math,
    to make arithmetic-heavy code more readable.

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
    def __init__(self, iterable: Iterable[Any]) -> None:
        self._g = iterable
    def __iter__(self) -> Iterator[Any]:
        return iter(self._g)
    def __add__(self, other: Any) -> "imathify":
        return sadd(self, other)
    def __radd__(self, other: Any) -> "imathify":
        return sadd(other, self)
    def __sub__(self, other: Any) -> "imathify":
        return ssub(self, other)
    def __rsub__(self, other: Any) -> "imathify":
        return ssub(other, self)
    def __abs__(self) -> "imathify":
        return sabs(self)
    def __pos__(self) -> "imathify":
        return spos(self)
    def __neg__(self) -> "imathify":
        return sneg(self)
    def __invert__(self) -> "imathify":
        return sinvert(self)
    def __mul__(self, other: Any) -> "imathify":
        return smul(self, other)
    def __rmul__(self, other: Any) -> "imathify":
        return smul(other, self)
    def __truediv__(self, other: Any) -> "imathify":
        return struediv(self, other)
    def __rtruediv__(self, other: Any) -> "imathify":
        return struediv(other, self)
    def __floordiv__(self, other: Any) -> "imathify":
        return sfloordiv(self, other)
    def __rfloordiv__(self, other: Any) -> "imathify":
        return sfloordiv(other, self)
    def __divmod__(self, other: Any) -> "imathify":
        return sdivmod(self, other)
    def __rdivmod__(self, other: Any) -> "imathify":
        return sdivmod(other, self)
    def __mod__(self, other: Any) -> "imathify":
        return smod(self, other)
    def __rmod__(self, other: Any) -> "imathify":
        return smod(other, self)
    def __pow__(self, other: Any, mod: int | None = None) -> "imathify":
        return spow(self, other, mod)
    def __rpow__(self, other: Any) -> "imathify":
        return spow(other, self)
    def __round__(self, ndigits: int | None = None) -> "imathify":
        return sround(self, ndigits)
    def __trunc__(self) -> "imathify":
        return strunc(self)
    def __floor__(self) -> "imathify":
        return sfloor(self)
    def __ceil__(self) -> "imathify":
        return sceil(self)
    def __lshift__(self, other: Any) -> "imathify":
        return slshift(self, other)
    def __rlshift__(self, other: Any) -> "imathify":
        return slshift(other, self)
    def __rshift__(self, other: Any) -> "imathify":
        return srshift(self, other)
    def __rrshift__(self, other: Any) -> "imathify":
        return srshift(other, self)
    def __and__(self, other: Any) -> "imathify":
        return sand(self, other)
    def __rand__(self, other: Any) -> "imathify":
        return sand(other, self)
    def __xor__(self, other: Any) -> "imathify":
        return sxor(self, other)
    def __rxor__(self, other: Any) -> "imathify":
        return sxor(other, self)
    def __or__(self, other: Any) -> "imathify":
        return sor(self, other)
    def __ror__(self, other: Any) -> "imathify":
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
    def __lt__(self, other: Any) -> "imathify":  # type: ignore[override]  # termwise, not scalar
        return slt(self, other)
    def __le__(self, other: Any) -> "imathify":  # type: ignore[override]  # termwise, not scalar
        return sle(self, other)
    def __eq__(self, other: Any) -> "imathify":  # type: ignore[override]  # termwise, not scalar
        return seq(self, other)
    def __ne__(self, other: Any) -> "imathify":  # type: ignore[override]  # termwise, not scalar
        return sne(self, other)
    def __ge__(self, other: Any) -> "imathify":  # type: ignore[override]  # termwise, not scalar
        return sge(self, other)
    def __gt__(self, other: Any) -> "imathify":  # type: ignore[override]  # termwise, not scalar
        return sgt(self, other)

Iterable.register(imathify)

def gmathify(gfunc: Callable[..., Iterable[Any]]) -> Callable[..., imathify]:
    """Decorator: make gfunc imathify() the returned generator instances.

    Return a new gfunc, which passes all its arguments to the original ``gfunc``.

    Example::

        a = gmathify(imemoize(s(1, 2, ...)))
        assert last(take(5, a())) == 5
        assert last(take(5, a())) == 5
        assert last(take(5, a() + a())) == 10
    """
    @wraps(gfunc)
    def mathify(*args: Any, **kwargs: Any) -> imathify:
        return imathify(gfunc(*args, **kwargs))
    return mathify

# -----------------------------------------------------------------------------
# We expose the full set of "imathify" operators also as functions à la the ``operator`` module.
# Prefix "s", short for "mathematical Sequence".
# https://docs.python.org/3/library/operator.html
#
# But first, let's define some factories.

def slift1(op: Callable[..., T], *settings: Any) -> Callable[[Iterable[T] | T], imathify | T]:
    """Lift a scalar unary operation to work termwise on iterables.

    Returns a function that, given an iterable, lazily applies ``op`` to
    each element and returns an imathified generator. Scalar inputs
    are passed through to ``op`` directly. Recurses into nested iterables.

    Any extra ``settings`` are appended to each call to ``op``, e.g.
    ``slift1(round, 2)`` gives termwise ``round(x, 2)``.

    Example::

        from math import sin
        ssin = slift1(sin)
        result = ssin(s(1, 2, 3, ...))  # termwise sin

    All the built-in ``s``-prefixed unary operators (``sabs``, ``sneg``, ...)
    are defined using this mechanism.
    """
    def stream_op(a: Iterable[T] | T) -> imathify | T:
        if isinstance(a, Iterable):
            return imathify(stream_op(x) for x in a)
        return op(a, *settings)
    return stream_op

def slift2(op: Callable[..., T], *settings: Any) -> Callable[[Iterable[T] | T, Iterable[T] | T], imathify | T]:
    """Lift a scalar binary operation to work termwise on iterables.

    Returns a function that, given two inputs (either or both iterables),
    lazily applies ``op`` termwise and returns an imathified generator.
    When both inputs are iterables, ``zip`` semantics apply (terminates at
    the shorter). When one input is scalar, it is broadcast. Recurses into
    nested iterables.

    Any extra ``settings`` are appended to each call to ``op``, e.g.
    ``slift2(pow, 5)`` gives termwise ``pow(a, b, 5)``.

    Example::

        from math import atan2
        satan2 = slift2(atan2)
        result = satan2(s(1, 2, 3, ...), s(4, 5, 6, ...))  # termwise atan2

    All the built-in ``s``-prefixed binary operators (``sadd``, ``smul``, ...)
    are defined using this mechanism.
    """
    def stream_op(a: Iterable[T] | T, b: Iterable[T] | T) -> imathify | T:
        isiterable = [isinstance(x, Iterable) for x in (a, b)]
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

# With these factories, the operators are just:

sadd = slift2(atom_add)
sadd.__doc__ = """Termwise a + b when one or both are iterables."""
ssub = slift2(atom_sub)
ssub.__doc__ = """Termwise a - b when one or both are iterables."""
sabs = slift1(abs)
sabs.__doc__ = """Termwise abs(a) for an iterable."""
spos = slift1(atom_pos)
spos.__doc__ = """Termwise +a for an iterable."""
sneg = slift1(atom_neg)
sneg.__doc__ = """Termwise -a for an iterable."""
smul = slift2(atom_mul)
smul.__doc__ = """Termwise a * b when one or both are iterables."""

_spow = slift2(atom_pow)  # 2-arg form
def spow(a: Any, b: Any, mod: int | None = None) -> Any:
    """Termwise a ** b when one or both are iterables.

    An optional third argument is supported, and passed through to the
    built-in ``pow`` function.
    """
    stream_op = slift2(pow, mod) if mod is not None else _spow
    return stream_op(a, b)

struediv = slift2(atom_truediv)
struediv.__doc__ = """Termwise a / b when one or both are iterables."""
sfloordiv = slift2(atom_floordiv)
sfloordiv.__doc__ = """Termwise a // b when one or both are iterables."""
smod = slift2(atom_mod)
smod.__doc__ = """Termwise a % b when one or both are iterables."""
sdivmod = slift2(divmod)
sdivmod.__doc__ = """Termwise (a // b, a % b) when one or both are iterables."""

_sround = slift1(round)  # 1-arg form
def sround(a: Any, ndigits: int | None = None) -> Any:
    """Termwise round(a) for an iterable.

    An optional second argument is supported, and passed through to the
    built-in ``round`` function.

    As with the built-in, rounding is correct taking into account the float
    representation, which is base-2.

        https://docs.python.org/3/library/functions.html#round
    """
    stream_op = slift1(round, ndigits) if ndigits is not None else _sround
    return stream_op(a)

strunc = slift1(trunc)
strunc.__doc__ = """Termwise math.trunc(a) for an iterable."""
sfloor = slift1(floor)
sfloor.__doc__ = """Termwise math.floor(a) for an iterable."""
sceil = slift1(ceil)
sceil.__doc__ = """Termwise math.ceil(a) for an iterable."""

# bit twiddling operations
slshift = slift2(atom_lshift)
slshift.__doc__ = """Termwise a << b when one or both are iterables."""
srshift = slift2(atom_rshift)
srshift.__doc__ = """Termwise a >> b when one or both are iterables."""
sand = slift2(atom_and)
sand.__doc__ = """Termwise a & b when one or both are iterables."""
sxor = slift2(atom_xor)
sxor.__doc__ = """Termwise a ^ b when one or both are iterables."""
sor = slift2(atom_or)
sor.__doc__ = """Termwise a | b when one or both are iterables."""
sinvert = slift1(atom_invert)
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
# sbool = slift1(bool)
# sbool.__doc__ = """Termwise bool(a) for an iterable."""
# scomplex = slift1(complex)
# scomplex.__doc__ = """Termwise complex(a) for an iterable."""
# sint = slift1(int)
# sint.__doc__ = """Termwise int(a) for an iterable."""
# sfloat = slift1(float)
# sfloat.__doc__ = """Termwise float(a) for an iterable."""

slt = slift2(atom_lt)
slt.__doc__ = """Termwise a < b when one or both are iterables."""
sle = slift2(atom_le)
sle.__doc__ = """Termwise a <= b when one or both are iterables."""
seq = slift2(atom_eq)
seq.__doc__ = """Termwise a == b when one or both are iterables."""
sne = slift2(atom_ne)
sne.__doc__ = """Termwise a != b when one or both are iterables."""
sge = slift2(atom_ge)
sge.__doc__ = """Termwise a >= b when one or both are iterables."""
sgt = slift2(atom_gt)
sgt.__doc__ = """Termwise a > b when one or both are iterables."""

# -----------------------------------------------------------------------------

def cauchyprod(a: Iterable[Any], b: Iterable[Any], *,
               require: Literal["all", "any"] = "any") -> imathify:
    """Cauchy product of two (possibly infinite) iterables.

    Defined by::

        c[k] = sum_j imathify(a[j] * b[k-j], j = 0, 1, ..., k),  k = 0, 1, ...

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

def diagonal_reduce(a: Iterable[Any], b: Iterable[Any], *,
                    combine: Callable[[Iterable[Any], Iterable[Any]], Iterable[Any]],
                    reduce: Callable[[Iterable[Any]], Any],
                    require: Literal["all", "any"] = "any") -> imathify:
    """Diagonal combination-reduction for two (possibly infinite) iterables.

    Defined by::

        c[k] = reduce_j(combine(a[j], b[k-j]), j = 0, 1, ..., k),  k = 0, 1, ...

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

    The output is automatically imathified so that it supports infix arithmetic.

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
    if not all(isinstance(x, Iterable) for x in (a, b)):
        raise TypeError(f"Expected two iterables, got {type(a)}, {type(b)}")
    if require not in ("all", "any"):
        raise ValueError(f"require must be 'all' or 'any'; got '{require}'")
    ga = imemoize(a)
    gb = imemoize(b)
    def diagonal() -> Iterator[Any]:
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

def fibonacci() -> imathify:
    """Return the Fibonacci numbers 1, 1, 2, 3, 5, 8, ... as a lazy sequence."""
    def fibos() -> Iterator[int]:
        a, b = 1, 1
        while True:
            yield a
            a, b = b, a + b
    return imathify(fibos())

def triangular() -> imathify:
    """Return the triangular numbers 1, 3, 6, 10, ... as a lazy sequence.

    Etymology::

            x
           x x
          x x x
         x x x x
        ...
    """
    # We could just use Gauss's result  n * (n + 1) / 2  (which can be proved by induction),
    # but this algorithm is trivially correct.
    def _triangular() -> Iterator[int]:
        s = 1  # running total
        r = 2  # places in the next row of the triangle
        while True:
            yield s
            s += r
            r += 1
    return imathify(_triangular())

# See test_gmemo.py for history. This is an FP-ized sieve of Eratosthenes.
#
# This version wins in speed for moderate n (1e5) on typical architectures where
# the memory bus is a bottleneck, since the rule for generating new candidates is
# simple arithmetic. Contrast memo_primes3, which needs to keep a table that gets
# larger as n grows (so memory transfers dominate for large n). That strategy
# seems faster for n ~ 1e3, though.
@gmemoize
def _primes() -> Iterator[int]:
    yield 2
    for n in count(start=3, step=2):
        if not any(n % p == 0 for p in takewhile(lambda x: x * x <= n, _primes())):
            yield n

@gmemoize
def _fastprimes() -> Iterator[int]:
    memo: list[int] = []
    def primes() -> Iterator[int]:
        memo.append(2)
        yield 2
        for n in count(start=3, step=2):
            if not any(n % p == 0 for p in takewhile(lambda x: x * x <= n, memo)):
                memo.append(n)
                yield n
    return primes()

def primes(optimize: Literal["memory", "speed"] = "speed") -> imathify:
    """Return the prime numbers 2, 3, 5, 7, 11, 13, ... as a lazy sequence.

    FP sieve of Eratosthenes with memoization.

    ``optimize`` is one of ``"memory"`` or ``"speed"``. The memory-optimized
    version shares one global memo, which is re-used also in the tight inner loop,
    whereas the speed-optimized one keeps exactly one more copy of the results
    as an internal memo (double memory usage, but faster, as it skips the very
    general ``gmemoize`` machinery in the inner loop).
    """
    if optimize not in ("memory", "speed"):
        raise ValueError(f"optimize must be 'memory' or 'speed'; got '{optimize}'")
    if optimize == "speed":
        return imathify(_fastprimes())
    else:  # optimize == "memory":
        return imathify(_primes())
