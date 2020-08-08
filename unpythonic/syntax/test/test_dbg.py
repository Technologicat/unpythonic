# -*- coding: utf-8 -*-

from ...syntax import macros, dbg  # noqa: F401
from ...misc import call

def test():
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
        dbgprint_expr = lambda *args, **kwargs: args  # noqa: F841, the `dbg[]` macro implicitly uses `dbgprint_expr`.
        x = dbg[2 + 3]
        assert x == ("(2 + 3)", 5)

    print("All tests PASSED")

if __name__ == '__main__':
    test()
