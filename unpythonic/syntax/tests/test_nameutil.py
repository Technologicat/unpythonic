# -*- coding: utf-8 -*-
"""Utilities for working with identifiers in macros."""

from ...syntax import macros, test
from ...test.fixtures import session, testset

from mcpyrate.quotes import macros, q, h  # noqa: F401, F811

from mcpyrate.expander import MacroExpander

from ...syntax.nameutil import (isx, getname,
                                is_unexpanded_expr_macro, is_unexpanded_block_macro)

from ast import Call

# test data
def capture_this():  # the function must be defined at top level so h[] can pickle the object
    pass  # pragma: no cover

def runtests():
    with testset("isx"):
        barename = q[ok]  # noqa: F821
        captured = q[h[capture_this]()]
        attribute = q[someobj.ok]  # noqa: F821

        test[isx(barename, "ok")]
        test[type(captured) is Call]
        test[isx(captured.func, "capture_this")]
        test[isx(attribute, "ok")]
        test[not isx(attribute, "ok", accept_attr=False)]

    with testset("getname"):
        test[getname(barename) == "ok"]
        test[getname(captured.func) == "capture_this"]
        test[getname(attribute) == "ok"]
        test[getname(attribute, accept_attr=False) is None]

    with testset("is_unexpanded_expr_macro"):
        def dummymacro(tree, **kw):
            return tree
        m = MacroExpander({"dummy": dummymacro}, filename="<fake filename for tests in test_nameutil.py>")

        # we need a macro that is bound in the expander we pass to the analyzer.
        test[is_unexpanded_expr_macro(dummymacro, m, q[dummy[blah]])]  # noqa: F821, only quoted
        test[not is_unexpanded_expr_macro(dummymacro, m, q[notdummy[blah]])]  # noqa: F821, only quoted
        test[not is_unexpanded_expr_macro(dummymacro, m, q[42])]

    with testset("is_unexpanded_block_macro"):
        with q as quoted:
            with dummy:  # noqa: F821, only quoted
                ...
        test[is_unexpanded_block_macro(dummymacro, m, quoted[0])]

        with q as quoted:
            with notdummy:  # noqa: F821, only quoted
                ...
        test[not is_unexpanded_block_macro(dummymacro, m, quoted[0])]

        with q as quoted:
            a = 42  # noqa: F841
        test[not is_unexpanded_block_macro(dummymacro, m, quoted[0])]

if __name__ == '__main__':  # pragma: no cover
    with session(__file__):
        runtests()
