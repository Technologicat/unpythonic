# -*- coding: utf-8 -*-
"""Detect let and do forms, and destructure them writably."""

from ...syntax import macros, test, test_raises, warn, the  # noqa: F401
from ...test.fixtures import session, testset

from macropy.core.quotes import macros, q, name  # noqa: F811, F401
# from macropy.core.hquotes import macros, hq  # noqa: F811, F401
# from macropy.tracing import macros, show_expanded

from ...syntax import macros, let, dlet, do, curry

from ast import Tuple, Name

from macropy.core import unparse

from ...syntax.letdoutil import (canonize_bindings,
                                 islet, isdo, isenvassign,
                                 UnexpandedLetView, UnexpandedDoView, UnexpandedEnvAssignView,
                                 ExpandedLetView, ExpandedDoView)

def runtests():
    with testset("canonize_bindings"):
        # canonize_bindings takes in a list of bindings, and outputs a list of bindings.
        def validate(lst):
            for b in lst:
                if type(b) is not Tuple or len(b.elts) != 2:
                    return False
                k, v = b.elts
                if type(k) is not Name:
                    return False
            return True
        # known fake location information
        locref = q[name["here"]]
        locref.lineno = 9001
        locref.col_offset = 9
        test[validate(the[canonize_bindings(q[k0, v0].elts, locref)])]  # noqa: F821, it's quoted.
        test[validate(the[canonize_bindings(q[((k0, v0),)].elts, locref)])]  # noqa: F821
        test[validate(the[canonize_bindings(q[(k0, v0), (k1, v1)].elts, locref)])]  # noqa: F821

    with testset("islet"):
        test[not islet(q[x])]  # noqa: F821
        test[not islet(q[f()])]  # noqa: F821

        # Lispers NOTE: in MacroPy, the quasiquote `q` (similarly hygienic
        # quasiquote `hq`) is a macro, not a special operator; it **does not**
        # prevent the expansion of any macros invoked in the quoted code.
        # It just lifts source code into the corresponding AST representation.
        #
        # (MacroPy-technically, it's a second-pass macro, so any macros nested inside
        #  have already expanded when the quote macro runs.)
        test[islet(the[q[let((x, 21))[2 * x]]]) == ("expanded_expr", "let")]  # noqa: F821, `let` defines `x`
        test[islet(the[q[let[(x, 21) in 2 * x]]]) == ("expanded_expr", "let")]  # noqa: F821
        test[islet(the[q[let[2 * x, where(x, 21)]]]) == ("expanded_expr", "let")]  # noqa: F821

        with q as testdata:  # pragma: no cover
            @dlet((x, 21))  # noqa: F821
            def f1():
                return 2 * x  # noqa: F821
        test[islet(the[testdata[0].decorator_list[0]]) == ("expanded_decorator", "let")]

        # So, to test the detector for unexpanded let forms, we cheat. We don't
        # actually invoke the let macro here, but arrange the tree being
        # analyzed so that it looks like an invocation for a let macro.
        #
        # Another way would be not to import the let macro in this module,
        # but then we couldn't test the detector for expanded let forms.
        testdata = q[definitelynotlet((x, 21))[2 * x]]  # noqa: F821
        testdata.value.func.id = "let"
        test[islet(the[testdata], expanded=False) == ("lispy_expr", "let")]

        # one binding special case for haskelly let-in
        testdata = q[definitelynotlet[(x, 21) in 2 * x]]  # noqa: F821
        testdata.value.id = "let"
        test[islet(the[testdata], expanded=False) == ("in_expr", "let")]

        testdata = q[definitelynotlet[((x, 21), (y, 2)) in y * x]]  # noqa: F821
        testdata.value.id = "let"
        test[islet(the[testdata], expanded=False) == ("in_expr", "let")]

        testdata = q[definitelynotlet[2 * x, where(x, 21)]]  # noqa: F821
        testdata.value.id = "let"
        test[islet(the[testdata], expanded=False) == ("where_expr", "let")]

        # some other macro invocation
        test[not islet(the[q[someothermacro((x, 21))[2 * x]]], expanded=False)]  # noqa: F821
        test[not islet(the[q[someothermacro[(x, 21) in 2 * x]]], expanded=False)]  # noqa: F821

        # invalid syntax for haskelly let-in
        testdata = q[definitelynotlet[a in b]]  # noqa: F821
        testdata.value.id = "let"
        test[not islet(the[testdata], expanded=False)]

        with q as testdata:  # pragma: no cover
            @definitelynotdlet((x, 21))  # noqa: F821
            def f2():
                return 2 * x  # noqa: F821
        testdata[0].decorator_list[0].func.id = "dlet"
        test[islet(the[testdata[0].decorator_list[0]], expanded=False) == ("decorator", "dlet")]

    with testset("islet integration with curry"):
        # NOTE: We have to be careful with how we set up the test data here.
        #
        # The `q` must be outside the `with curry` block, because otherwise
        # `curry` will attempt to curry the AST-lifted representation, leading to
        # arguably funny but nonsensical things like `ctx=currycall(ast.Load)`.
        with q as testdata:
            with curry:  # pragma: no cover
                let((x, 21))[2 * x]  # noqa: F821  # note this goes into an ast.Expr
        thelet = testdata[0].value
        test[islet(the[thelet]) == ("curried_expr", "let")]

        with q as testdata:
            with curry:  # pragma: no cover
                let[(x, 21) in 2 * x]  # noqa: F821
        thelet = testdata[0].value
        test[islet(the[thelet]) == ("curried_expr", "let")]

        with q as testdata:
            with curry:  # pragma: no cover
                let[2 * x, where(x, 21)]  # noqa: F821
        thelet = testdata[0].value
        test[islet(the[thelet]) == ("curried_expr", "let")]

    with testset("isdo"):
        test[not isdo(q[x])]  # noqa: F821
        test[not isdo(q[f()])]  # noqa: F821

        test[isdo(the[q[do[x << 21,  # noqa: F821
                           2 * x]]]) == "expanded"]  # noqa: F821

        with q as testdata:  # pragma: no cover
            with curry:
                do[x << 21,  # noqa: F821
                   2 * x]  # noqa: F821
        thedo = testdata[0].value
        test[isdo(the[thedo]) == "curried"]

    with testset("isenvassign"):
        warn["TODO: This testset not implemented yet."]

    with testset("let destructuring"):
        warn["TODO: This testset not implemented yet."]

    with testset("do destructuring"):
        warn["TODO: This testset not implemented yet."]

if __name__ == '__main__':  # pragma: no cover
    with session(__file__):
        runtests()
