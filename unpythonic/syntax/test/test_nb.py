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
        x = 2
        y = 3
        print(x, y, 17 + 23)

    prt = lambda *args: print(*args)
    with dbg(prt):  # can specify a custom print function
        x = 2
        prt(x)    # transformed
        print(x)  # not transformed, because custom print function specified

    with dbg(prt):
        x = 2
        y = 3
        prt(x, y, 17 + 23)

    # now for some proper unit testing
    prt = lambda *args: args
    with dbg(prt):
        x = 2
        assert prt(x) == (("x",), (2,))

        x = 2
        y = 3
        assert prt(x, y, 17 + 23) == (("x", "y", "(17 + 23)"), (2, 3, 40))

    print("All tests PASSED")

if __name__ == '__main__':
    test()
