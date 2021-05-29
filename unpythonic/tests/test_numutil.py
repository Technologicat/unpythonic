# -*- coding: utf-8 -*-

from ..syntax import macros, test, test_raises, error, the  # noqa: F401
from ..test.fixtures import session, testset

from math import cos, sqrt
import sys

from ..numutil import almosteq, fixpoint, partition_int, partition_int_triangular, ulp

def runtests():
    with testset("ulp (unit in the last place; float utility)"):
        test[ulp(1.0) == sys.float_info.epsilon]
        # test also at some base-2 exponent switch points
        test[ulp(2.0) == 2 * sys.float_info.epsilon]
        test[ulp(0.5) == 0.5 * sys.float_info.epsilon]

    with testset("almosteq"):
        # For anything but floating-point inputs, it's exact equality.
        test[almosteq("abc", "abc")]
        test[not almosteq("ab", "abc")]

        test[almosteq(1.0, 1.0 + ulp(1.0))]

        # TODO: counterintuitively, need a large tolerance here, because when one operand is zero,
        # TODO: the final tolerance is actually tol*min_normal.
        min_normal = sys.float_info.min
        test[almosteq(min_normal / 2, 0, tol=1.0)]

        too_large = 2**int(1e6)
        test_raises[OverflowError, float(too_large), "UPDATE THIS, need a float overflow here."]
        test[almosteq(too_large, too_large + 1)]  # works, because 1/too_large is very small.

        try:
            from mpmath import mpf
        except ImportError:  # pragma: no cover
            error["mpmath not installed in this Python, cannot test arbitrary precision input for mathseq."]
        else:
            test[almosteq(mpf(1.0), mpf(1.0 + ulp(1.0)))]
            test[almosteq(1.0, mpf(1.0 + ulp(1.0)))]
            test[almosteq(mpf(1.0), 1.0 + ulp(1.0))]

    # Arithmetic fixed points.
    with testset("fixpoint (arithmetic fixed points)"):
        c = fixpoint(cos, x0=1)
        test[the[c] == the[cos(c)]]  # 0.7390851332151607

        # Actually "Newton's" algorithm for the square root was already known to the
        # ancient Babylonians, ca. 2000 BCE. (Carl Boyer: History of mathematics)
        def sqrt_newton(n):
            def sqrt_iter(x):  # has an attractive fixed point at sqrt(n)
                return (x + n / x) / 2
            return fixpoint(sqrt_iter, x0=n / 2)
        # different algorithm, so not necessarily equal down to the last bit
        # (caused by the fixpoint update becoming smaller than the ulp, so it
        #  stops there, even if the limit is still one ulp away).
        test[abs(the[sqrt_newton(2)] - the[sqrt(2)]) <= the[ulp(1.414)]]

    # partition_int: split a small positive integer, in all possible ways, into smaller integers that sum to it
    with testset("partition_int"):
        test[tuple(partition_int(4)) == ((4,), (3, 1), (2, 2), (2, 1, 1), (1, 3), (1, 2, 1), (1, 1, 2), (1, 1, 1, 1))]
        test[tuple(partition_int(5, lower=2)) == ((5,), (3, 2), (2, 3))]
        test[tuple(partition_int(5, lower=2, upper=3)) == ((3, 2), (2, 3))]
        test[tuple(partition_int(10, lower=3, upper=5)) == ((5, 5), (4, 3, 3), (3, 4, 3), (3, 3, 4))]
        test[all(sum(terms) == 10 for terms in partition_int(10))]
        test[all(sum(terms) == 10 for terms in partition_int(10, lower=3))]
        test[all(sum(terms) == 10 for terms in partition_int(10, lower=3, upper=5))]

        test_raises[TypeError, partition_int("not a number")]
        test_raises[TypeError, partition_int(4, lower="not a number")]
        test_raises[TypeError, partition_int(4, upper="not a number")]
        test_raises[ValueError, partition_int(-3)]
        test_raises[ValueError, partition_int(4, lower=-1)]
        test_raises[ValueError, partition_int(4, lower=5)]
        test_raises[ValueError, partition_int(4, upper=-1)]
        test_raises[ValueError, partition_int(4, upper=5)]
        test_raises[ValueError, partition_int(4, lower=3, upper=2)]

    # partition_int_triangular: like partition_int, but in the output, allow triangular numbers only.
    # Triangular numbers are 1, 3, 6, 10, ...
    with testset("partition_int_triangular"):
        test[frozenset(tuple(sorted(c)) for c in partition_int_triangular(78, lower=10)) ==
             frozenset({(10, 10, 10, 10, 10, 28),
                        (10, 10, 15, 15, 28),
                        (15, 21, 21, 21),
                        (21, 21, 36),
                        (78,)})]

if __name__ == '__main__':  # pragma: no cover
    with session(__file__):
        runtests()
