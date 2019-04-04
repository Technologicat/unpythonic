# -*- coding: utf-8 -*-

from ...syntax import macros, nb, dbg

def test():
    with nb:
        assert _ is None
        2 + 3          # top-level expressions autoprint, and auto-assign result to _
        assert _ == 5  # ...and only expressions do that, so...
        _ * 42         # ...here _ still has the value from the first line.
        assert _ == 210

    try:
        from sympy import symbols, pprint
    except ImportError:
        print("*** SymPy not installed, skipping symbolic math test ***")
    else:
        with nb(pprint):  # you can specify a custom print function (first positional arg)
            assert _ is None
            x, y = symbols("x, y")
            x * y
            assert _ == x * y
            3 * _
            assert _ == 3 * x * y

    with dbg:
        x = 3
        print(x)

    prt = lambda *args: print(*args)
    with dbg(prt):
        x = 5
        prt(x)

    print("All tests PASSED")

if __name__ == '__main__':
    test()
