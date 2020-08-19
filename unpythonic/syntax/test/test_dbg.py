# -*- coding: utf-8 -*-

from ...syntax import macros, test  # noqa: F401
from ...test.fixtures import session, testset

from ...syntax import macros, dbg  # noqa: F401, F811
from ...misc import call

def runtests():
    # some usage examples
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
    with testset("basic usage"):
        prt = lambda *args, **kwargs: args
        with dbg(prt):
            x = 2
            test[prt(x) == (("x",), (2,))]

            x = 2
            y = 3
            test[prt(x, y, 17 + 23) == (("x", "y", "(17 + 23)"), (2, 3, 40))]

        # the expression variant can be used in any expression position
        x = dbg[25 + 17]
        test[x == 42]

    with testset("customization of dbgprint_expr"):
        # Customize the expression debug printer.
        #
        # Here must be done in a different scope, so that the above use of dbg[]
        # resolves to the global default dbgprint_expr, and this test to the
        # local customized dbgprint_expr.
        @call
        def just_a_scope():
            dbgprint_expr = lambda *args, **kwargs: args  # noqa: F841, the `dbg[]` macro implicitly uses `dbgprint_expr`.
            x = dbg[2 + 3]
            test[x == ("(2 + 3)", 5)]

if __name__ == '__main__':
    with session(__file__):
        runtests()
