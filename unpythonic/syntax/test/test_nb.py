# -*- coding: utf-8 -*-

from ...syntax import macros, test, error  # noqa: F401
from ...test.fixtures import session, testset

from ...syntax import macros, nb  # noqa: F401, F811

def runtests():
    with testset("basic usage"):
        with nb:
            test[_ is None]  # noqa: F821, the `nb` macro defines `_` implicitly.
            2 + 3          # top-level expressions autoprint, and auto-assign result to _
            test[_ == 5]  # ...and only expressions do that, so...  # noqa: F821
            _ * 42         # ...here _ still has the value from the first line.  # noqa: F821
            test[_ == 210]  # noqa: F821

    with testset("integration with symbolic math"):
        try:
            from sympy import symbols, pprint
        except ImportError:  # pragma: no cover
            error["SymPy not installed in this Python, cannot test symbolic math in nb."]
        else:
            with nb(pprint):  # you can specify a custom print function (first positional arg)
                test[_ is None]  # noqa: F821
                x, y = symbols("x, y")
                x * y
                test[_ == x * y]  # noqa: F821
                3 * _  # noqa: F821
                test[_ == 3 * x * y]  # noqa: F821

if __name__ == '__main__':  # pragma: no cover
    with session(__file__):
        runtests()
