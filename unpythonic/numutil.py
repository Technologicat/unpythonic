# -*- coding: utf-8 -*-
"""Low-level utilities for numerics."""

__all__ = ["almosteq", "ulp",
           "fixpoint",
           "partition_int", "partition_int_triangular"]

from itertools import takewhile
from math import floor, log2
import sys

from .it import iterate1, last, within
from .symbol import sym

# HACK: break dependency loop mathseq -> numutil -> mathseq
_init_done = False
triangular = sym("triangular")  # doesn't matter what the value is, will be overwritten later
def _init_module():  # called by unpythonic.__init__ when otherwise done
    global triangular, _init_done
    from .mathseq import triangular
    _init_done = True

class _NoSuchType:
    pass

try:
    from mpmath import mpf, almosteq as mpf_almosteq
except ImportError:  # pragma: no cover, optional at runtime, but installed at development time.
    # Can't use a gensym here since `mpf` must be a unique *type*.
    mpf = _NoSuchType
    mpf_almosteq = None


# TODO: Overhaul `almosteq` in v0.16.0, should work like mpf for consistency.
def almosteq(a, b, tol=1e-8):
    """Almost-equality that supports several formats.

    The tolerance ``tol`` is used for the builtin ``float`` and ``mpmath.mpf``.

    For ``mpmath.mpf``, we just delegate to ``mpmath.almosteq``, with the given
    ``tol``. For ``float``, we use the strategy suggested in:

        https://floating-point-gui.de/errors/comparison/

    Anything else, for example SymPy expressions, strings, and containers
    (regardless of content), is tested for exact equality.
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
    min_normal = sys.float_info.min
    max_float = sys.float_info.max
    d = abs(a - b)
    if a == 0 or b == 0 or d < min_normal:
        return d < tol * min_normal
    return d / min(abs(a) + abs(b), max_float) < tol


def ulp(x):  # Unit in the Last Place
    """Given a float x, return the unit in the last place (ULP).

    This is the numerical value of the least-significant bit, as a float.
    For x = 1.0, the ULP is the machine epsilon (by definition of machine epsilon).

    See:
        https://en.wikipedia.org/wiki/Unit_in_the_last_place
    """
    eps = sys.float_info.epsilon
    # m_min = abs. value represented by a mantissa of 1.0, with the same exponent as x has
    m_min = 2**floor(log2(abs(x)))
    return m_min * eps


def fixpoint(f, x0, tol=0):
    """Compute the (arithmetic) fixed point of f, starting from the initial guess x0.

    (Not to be confused with the logical fixed point with respect to the
    definedness ordering.)

    The fixed point must be attractive for this to work. See the Banach
    fixed point theorem.
    https://en.wikipedia.org/wiki/Banach_fixed-point_theorem

    If the fixed point is attractive, and the values are represented in
    floating point (hence finite precision), the computation should
    eventually converge down to the last bit (barring roundoff or
    catastrophic cancellation in the final few steps). Hence the default tol
    of zero.

    CAUTION: an arbitrary function from ℝ to ℝ **does not** necessarily
    have a fixed point. Limit cycles and chaotic behavior of `f` will cause
    non-termination. Keep in mind the classic example:
    https://en.wikipedia.org/wiki/Logistic_map

    Examples::
        from math import cos, sqrt
        from unpythonic import fixpoint, ulp
        c = fixpoint(cos, x0=1)

        # Actually "Newton's" algorithm for the square root was already known to the
        # ancient Babylonians, ca. 2000 BCE. (Carl Boyer: History of mathematics)
        def sqrt_newton(n):
            def sqrt_iter(x):  # has an attractive fixed point at sqrt(n)
                return (x + n / x) / 2
            return fixpoint(sqrt_iter, x0=n / 2)
        assert abs(sqrt_newton(2) - sqrt(2)) <= ulp(1.414)
    """
    return last(within(tol, iterate1(f, x0)))


def partition_int(n, lower=1, upper=None):
    """Yield all ordered sequences of smaller positive integers that sum to `n`.

    `n` must be an integer >= 1.

    `lower` is an optional lower limit for each member of the sum. Each member
    of the sum must be `>= lower`.

    (Most of the splits are a ravioli consisting mostly of ones, so it is much
    faster to not generate such splits than to filter them out from the result.
    The default value `lower=1` generates everything.)

    `upper` is, similarly, an optional upper limit; each member of the sum
    must be `<= upper`. The default `None` means no upper limit (effectively,
    in that case `upper=n`).

    It must hold that `1 <= lower <= upper <= n`.

    Not to be confused with `unpythonic.it.partition`, which partitions an
    iterable based on a predicate.

    **CAUTION**: The number of possible partitions grows very quickly with `n`,
    so in practice this is only useful for small numbers, or with a lower limit
    that is not too much smaller than `n / 2`. A possible use case for this
    function is to determine the number of letters to allocate for each
    component of an anagram that may consist of several words.

    See:
        https://en.wikipedia.org/wiki/Partition_(number_theory)
    """
    # sanity check the preconditions, fail-fast
    if not isinstance(n, int):
        raise TypeError(f"n must be integer; got {type(n)} with value {repr(n)}")
    if not isinstance(lower, int):
        raise TypeError(f"lower must be integer; got {type(lower)} with value {repr(lower)}")
    if upper is not None and not isinstance(upper, int):
        raise TypeError(f"upper must be integer; got {type(upper)} with value {repr(upper)}")
    upper = upper if upper is not None else n
    if n < 1:
        raise ValueError(f"n must be positive; got {n}")
    if lower < 1 or upper < 1 or lower > n or upper > n or lower > upper:
        raise ValueError(f"it must hold that 1 <= lower <= upper <= n; got lower={lower}, upper={upper}")

    return _partition_int(n, range(min(n, upper), lower - 1, -1))  # instantiate the generator

def partition_int_triangular(n, lower=1, upper=None):
    """Like `partition_int`, but allow only triangular numbers in the result.

    Triangular numbers are 1, 3, 6, 10, ...

    This function answers the timeless question: if I have `n` stackable plushies,
    what are the possible stack configurations? Example::

        configurations = partition_int_triangular(78, lower=10)
        print(frozenset(tuple(sorted(c)) for c in configurations))

    Result::

        frozenset({(10, 10, 10, 10, 10, 28),
                   (10, 10, 15, 15, 28),
                   (15, 21, 21, 21),
                   (21, 21, 36),
                   (78,)})

    Here `lower` sets the minimum number of plushies to allocate for one stack.
    """
    if not isinstance(n, int):
        raise TypeError(f"n must be integer; got {type(n)} with value {repr(n)}")
    if not isinstance(lower, int):
        raise TypeError(f"lower must be integer; got {type(lower)} with value {repr(lower)}")
    if upper is not None and not isinstance(upper, int):
        raise TypeError(f"upper must be integer; got {type(upper)} with value {repr(upper)}")
    upper = upper if upper is not None else n
    if n < 1:
        raise ValueError(f"n must be positive; got {n}")
    if lower < 1 or upper < 1 or lower > n or upper > n or lower > upper:
        raise ValueError(f"it must hold that 1 <= lower <= upper <= n; got lower={lower}, upper={upper}")

    triangulars_upto_n = takewhile(lambda m: m <= n,
                                   triangular())
    return _partition_int(n, filter(lambda m: lower <= m <= upper,
                                    triangulars_upto_n))

def _partition_int(n, components):
    """Implementation for `partition_int`, `partition_triangular`.

    `n`: integer to partition.
    `components`: iterable of ints; numbers that are allowed to appear
                  in the partitioning result. Each number `m` must
                  satisfy `1 <= m <= n`.
    """
    # TODO: Check contracts on input? This is an internal function for now, so no validation.
    components = tuple(components)
    for k in components:
        m = n - k
        if m == 0:
            yield (k,)
        else:
            out = []
            for item in _partition_int(m, (x for x in components if x <= m)):
                out.append((k,) + item)
            for term in out:
                yield term
