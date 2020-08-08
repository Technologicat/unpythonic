# -*- coding: utf-8 -*-

from ...syntax import macros, nb  # noqa: F401

def test():
    with nb:
        assert _ is None  # noqa: F821, the `nb` macro defines `_` implicitly.
        2 + 3          # top-level expressions autoprint, and auto-assign result to _
        assert _ == 5  # ...and only expressions do that, so...  # noqa: F821
        _ * 42         # ...here _ still has the value from the first line.  # noqa: F821
        assert _ == 210  # noqa: F821

    try:
        from sympy import symbols, pprint
    except ImportError:
        print("*** SymPy not installed, skipping symbolic math test ***")
    else:
        with nb(pprint):  # you can specify a custom print function (first positional arg)
            assert _ is None  # noqa: F821
            x, y = symbols("x, y")
            x * y
            assert _ == x * y  # noqa: F821
            3 * _  # noqa: F821
            assert _ == 3 * x * y  # noqa: F821

    print("All tests PASSED")

if __name__ == '__main__':
    test()
