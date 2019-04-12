# -*- coding: utf-8 -*-

from ...syntax import macros, nb, dbg, pop_while
from ...misc import call

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

    prt = lambda *args, **kwargs: print(*args)
    with dbg(prt):  # can specify a custom print function
        x = 2
        prt(x)    # transformed
        print(x)  # not transformed, because custom print function specified

    with dbg(prt):
        x = 2
        y = 3
        prt(x, y, 17 + 23)

    # now for some proper unit testing
    prt = lambda *args, **kwargs: args
    with dbg(prt):
        x = 2
        assert prt(x) == (("x",), (2,))

        x = 2
        y = 3
        assert prt(x, y, 17 + 23) == (("x", "y", "(17 + 23)"), (2, 3, 40))

    # the expression variant can be used in any expression position
    x = dbg[25 + 17]
    assert x == 42

    # Customize the expression debug printer.
    #
    # Here must be done in a different scope, so that the above use of dbg[]
    # resolves to the global default dbgprint_expr, and this test to the
    # local customized dbgprint_expr.
    @call
    def just_a_scope():
        dbgprint_expr = lambda *args, **kwargs: args
        x = dbg[2 + 3]
        assert x == ("(2 + 3)", 5)

    print("All tests PASSED")

if __name__ == '__main__':
    test()
