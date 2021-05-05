# -*- coding: utf-8 -*-
"""Low-level utilities for numerics."""

__all__ = ["almosteq", "ulp"]

from math import floor, log2
import sys

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
