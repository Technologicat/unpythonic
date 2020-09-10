# -*- coding: utf-8 -*-
"""Detect let and do forms, and destructure them writably."""

from ...syntax import macros, test, test_raises, warn, the  # noqa: F401
from ...test.fixtures import session, testset

from macropy.core.quotes import macros, q, name  # noqa: F811, F401
# from macropy.core.hquotes import macros, hq  # noqa: F811, F401
# from macropy.tracing import macros, show_expanded

from ...syntax import (macros, let, letrec, dlet, dletrec,  # noqa: F811, F401
                       do, local,
                       curry)

from ast import Tuple, Name, Num, Lambda, BinOp, Attribute

from macropy.core import unparse

from ...syntax.letdoutil import (canonize_bindings,
                                 isenvassign, islet, isdo,
                                 UnexpandedEnvAssignView,
                                 UnexpandedLetView, ExpandedLetView,
                                 UnexpandedDoView, ExpandedDoView)

def runtests():
    with testset("canonize_bindings"):
        # canonize_bindings takes in a list of bindings, and outputs a list of bindings.
        def validate(lst):
            for b in lst:
                if type(b) is not Tuple or len(b.elts) != 2:
                    return False  # pragma: no cover, only reached if the test fails.
                k, v = b.elts
                if type(k) is not Name:
                    return False  # pragma: no cover, only reached if the test fails.
            return True
        # known fake location information
        locref = q[name["here"]]
        locref.lineno = 9001
        locref.col_offset = 9
        test[validate(the[canonize_bindings(q[k0, v0].elts, locref)])]  # noqa: F821, it's quoted.
        test[validate(the[canonize_bindings(q[((k0, v0),)].elts, locref)])]  # noqa: F821
        test[validate(the[canonize_bindings(q[(k0, v0), (k1, v1)].elts, locref)])]  # noqa: F821

    # The let[] and do[] macros, used in the tests of islet() and isdo(),
    # need this utility, so we must test it first.
    with testset("isenvassign"):
        test[not isenvassign(q[x])]  # noqa: F821
        test[isenvassign(q[x << 42])]  # noqa: F821

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

        testdata = q[definitelynotdo[x << 21,  # noqa: F821
                                     2 * x]]  # noqa: F821
        testdata.value.id = "do"
        test[isdo(the[testdata], expanded=False) == "do"]

        testdata = q[definitelynotdo[23,  # noqa: F821
                                     x << 21,  # noqa: F821
                                     2 * x]]  # noqa: F821
        testdata.value.id = "do0"
        test[isdo(the[testdata], expanded=False) == "do0"]

        testdata = q[someothermacro[x << 21,  # noqa: F821
                                    2 * x]]  # noqa: F821
        test[not isdo(the[testdata], expanded=False)]

    with testset("envassign destructuring"):
        testdata = q[x << 42]  # noqa: F821
        view = UnexpandedEnvAssignView(testdata)

        # read
        test[view.name == "x"]
        test[type(the[view.value]) is Num and view.value.n == 42]  # TODO: Python 3.8: ast.Constant, no ast.Num

        # write
        view.name = "y"
        view.value = q[23]
        test[view.name == "y"]
        test[type(the[view.value]) is Num and view.value.n == 23]

        # it's a live view
        test[unparse(testdata) == "(y << 23)"]

        # error cases
        test_raises[TypeError,
                    UnexpandedEnvAssignView(q[x]),  # noqa: F821
                    "not an env assignment"]
        with test_raises(TypeError, "name must be str"):
            view.name = 1234

    with testset("let destructuring (unexpanded)"):
        def testletdestructuring(testdata):
            view = UnexpandedLetView(testdata)

            # read
            # In the unexpanded form, the outer container of bindings is a `list`.
            test[len(view.bindings) == 2]
            test[unparse(view.bindings[0]) == "(x, 21)"]  # the variable names are identifiers
            test[unparse(view.bindings[1]) == "(y, 2)"]
            test[unparse(view.body) == "(y * x)"]

            # write
            #
            # It's also legal to edit the AST nodes in view.bindings directly.
            # But the job of the setter, which we want to test here,
            # is to handle reassigning `view.bindings`.
            newbindings = q[(z, 21), (t, 2)].elts  # noqa: F821
            view.bindings = newbindings  # ...like this.
            view.body = q[z * t]  # noqa: F821
            test[len(view.bindings) == 2]
            test[unparse(view.bindings[0]) == "(z, 21)"]
            test[unparse(view.bindings[1]) == "(t, 2)"]
            test[unparse(view.body) == "(z * t)"]

        # lispy expr
        testdata = q[definitelynotlet((x, 21), (y, 2))[y * x]]  # noqa: F821
        testdata.value.func.id = "let"
        testletdestructuring(testdata)

        # haskelly let-in
        testdata = q[definitelynotlet[((x, 21), (y, 2)) in y * x]]  # noqa: F821
        testdata.value.id = "let"
        testletdestructuring(testdata)

        # haskelly let-where
        testdata = q[definitelynotlet[y * x, where((x, 21), (y, 2))]]  # noqa: F821
        testdata.value.id = "let"
        testletdestructuring(testdata)

        # disembodied haskelly let-in (just the content, no macro invocation)
        testdata = q[((x, 21), (y, 2)) in y * x]  # noqa: F821
        testletdestructuring(testdata)

        # disembodied haskelly let-where (just the content, no macro invocation)
        testdata = q[y * x, where((x, 21), (y, 2))]  # noqa: F821
        testletdestructuring(testdata)

        # decorator
        with q as testdata:  # pragma: no cover
            @definitelynotdlet((x, 21), (y, 2))  # noqa: F821
            def f3():
                return 2 * x  # noqa: F821
        testdata[0].decorator_list[0].func.id = "dlet"

        # read
        view = UnexpandedLetView(testdata[0].decorator_list[0])
        test[len(view.bindings) == 2]
        test[unparse(view.bindings[0]) == "(x, 21)"]
        test[unparse(view.bindings[1]) == "(y, 2)"]
        test_raises[TypeError,
                    view.body,
                    "decorator let does not have an accessible body"]

        # write
        newbindings = q[(z, 21), (t, 2)].elts  # noqa: F821
        view.bindings = newbindings
        test[len(view.bindings) == 2]
        test[unparse(view.bindings[0]) == "(z, 21)"]
        test[unparse(view.bindings[1]) == "(t, 2)"]
        with test_raises(TypeError, "decorator let does not have an accessible body"):
            view.body = q[x]  # noqa: F821

        test_raises[TypeError,
                    UnexpandedLetView(q[x]),  # noqa: F821
                    "not a let form"]

    with testset("let destructuring (expanded let)"):
        def testletdestructuring(testdata):
            view = ExpandedLetView(testdata)

            # read
            # In the expanded form, the outer container of bindings is an `ast.Tuple`.
            test[len(view.bindings.elts) == 2]
            test[unparse(view.bindings.elts[0]) == "('x', 21)"]  # the variable names are strings
            test[unparse(view.bindings.elts[1]) == "('y', 2)"]

            # Reading an expanded let body is painful:
            lam = view.body  # lambda e: e.y * e.x
            test[type(lam) is Lambda]
            lambody = lam.body
            test[type(lambody) is BinOp]
            test[type(the[lambody.left]) is Attribute and lambody.left.attr == "y"]
            test[type(the[lambody.right]) is Attribute and lambody.right.attr == "x"]

            # write
            newbindings = q[("z", 21), ("t", 2)]  # noqa: F821
            view.bindings = newbindings
            test[len(view.bindings.elts) == 2]
            test[unparse(view.bindings.elts[0]) == "('z', 21)"]
            test[unparse(view.bindings.elts[1]) == "('t', 2)"]

            # edit an expanded let body
            envname = view.envname
            newbody = q[lambda _: name[envname].z * name[envname].t]  # noqa: F821
            view.body = newbody  # the body lambda gets the correct envname auto-injected as its arg

            lam = view.body  # lambda e: e.z * e.t
            test[type(lam) is Lambda]
            lambody = lam.body
            test[type(lambody) is BinOp]
            test[type(the[lambody.left]) is Attribute and lambody.left.attr == "z"]
            test[type(the[lambody.right]) is Attribute and lambody.right.attr == "t"]

        # lispy expr
        testdata = q[let((x, 21), (y, 2))[y * x]]  # noqa: F821
        testletdestructuring(testdata)

        # haskelly let-in
        testdata = q[let[((x, 21), (y, 2)) in y * x]]  # noqa: F821
        testletdestructuring(testdata)

        # haskelly let-where
        testdata = q[let[y * x, where((x, 21), (y, 2))]]  # noqa: F821
        testletdestructuring(testdata)

        # decorator
        with q as testdata:  # pragma: no cover
            @dlet((x, 21), (y, 2))  # noqa: F821
            def f4():
                return 2 * x  # noqa: F821
        view = ExpandedLetView(testdata[0].decorator_list[0])
        test_raises[TypeError,
                    view.body,
                    "decorator let does not have an accessible body"]
        with test_raises(TypeError, "decorator let does not have an accessible body"):
            view.body = q[x]  # noqa: F821
        test[view.envname is None]  # dlet decorator doesn't have an envname, either

        # let with implicit do (extra bracket syntax)
        #
        # with show_expanded:
        #     let[((x, 21)) in [local[z << 2],
        #                       z * x]]
        #
        # After macro expansion:
        #   letter((('x', 21),),
        #          namelambda('let_body')((lambda e1:
        #              dof(namelambda('do_line1')((lambda e: e._set('z', 2))),
        #                  namelambda('do_line2')((lambda e: (e.z * e1.x)))))),
        #          mode='let')
        #
        testdata = q[let[((x, 21)) in [local[z << 2],  # noqa: F821
                                       z * x]]]  # noqa: F821
        view = ExpandedLetView(testdata)
        lam = view.body
        test[isdo(the[lam.body])]

        test_raises[TypeError,
                    ExpandedLetView(q[x]),  # noqa: F821
                    "not an expanded let form"]

    with testset("let destructuring (expanded letrec)"):
        def testletdestructuring(testdata):
            view = ExpandedLetView(testdata)

            # With an expanded letrec, even reading the bindings gets painful:
            def testbindings(*expected):
                for b, (k, v) in zip(view.bindings.elts, expected):
                    test[len(b.elts) == 2]
                    bk, lam = b.elts
                    # outer quotes, source code; inner quotes, str within that source
                    test[the[unparse(bk)] == the["'{}'".format(k)]]
                    test[type(lam) is Lambda]
                    lambody = lam.body
                    test[type(the[lambody]) is Num and lambody.n == the[v]]  # TODO: Python 3.8: ast.Constant, no ast.Num

            # read
            test[len(view.bindings.elts) == 2]
            testbindings(('x', 21), ('y', 2))

            # Reading an expanded letrec body
            lam = view.body  # lambda e: e.y * e.x
            test[type(lam) is Lambda]
            lambody = lam.body
            test[type(lambody) is BinOp]
            test[type(the[lambody.left]) is Attribute and lambody.left.attr == "y"]
            test[type(the[lambody.right]) is Attribute and lambody.right.attr == "x"]

            # write
            newbindings = q[("z", lambda _: 21), ("t", lambda _: 2)]  # noqa: F821
            view.bindings = newbindings  # each binding lambda gets the correct envname auto-injected as its arg
            test[len(view.bindings.elts) == 2]
            testbindings(('z', 21), ('t', 2))

            # Editing an expanded letrec body
            envname = view.envname
            newbody = q[lambda _: name[envname].z * name[envname].t]  # noqa: F821
            view.body = newbody  # the body lambda gets the correct envname auto-injected as its arg

            lam = view.body  # lambda e: e.z * e.t
            test[type(lam) is Lambda]
            lambody = lam.body
            test[type(lambody) is BinOp]
            test[type(the[lambody.left]) is Attribute and lambody.left.attr == "z"]
            test[type(the[lambody.right]) is Attribute and lambody.right.attr == "t"]

        # lispy expr
        testdata = q[letrec[((x, 21), (y, 2)) in y * x]]  # noqa: F821
        testletdestructuring(testdata)

        # haskelly let-in
        testdata = q[letrec[((x, 21), (y, 2)) in y * x]]  # noqa: F821
        testletdestructuring(testdata)

        # haskelly let-where
        testdata = q[letrec[y * x, where((x, 21), (y, 2))]]  # noqa: F821
        testletdestructuring(testdata)

        # decorator, letrec
        with q as testdata:  # pragma: no cover
            @dletrec((x, 21), (y, 2))  # noqa: F821
            def f5():
                return 2 * x  # noqa: F821
        view = ExpandedLetView(testdata[0].decorator_list[0])
        test_raises[TypeError,
                    view.body,
                    "decorator let does not have an accessible body"]
        with test_raises(TypeError, "decorator let does not have an accessible body"):
            view.body = q[x]  # noqa: F821
        test[view.envname is not None]  # dletrec decorator has envname in the bindings

    with testset("let destructuring (expanded) integration with curry"):
        warn["TODO: This testset not implemented yet."]
        # with q as testdata:
        #     with curry:  # pragma: no cover
        #         pass

    with testset("do destructuring"):
        warn["TODO: This testset not implemented yet."]
        # TODO: UnexpandedDoView
        # TODO: ExpandedDoView

if __name__ == '__main__':  # pragma: no cover
    with session(__file__):
        runtests()
