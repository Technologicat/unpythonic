# -*- coding: utf-8 -*-

from ..syntax import macros, test, test_raises, error  # noqa: F401
from ..test.fixtures import session, testset

import sys

from ..numutil import almosteq, ulp

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

if __name__ == '__main__':  # pragma: no cover
    with session(__file__):
        runtests()
