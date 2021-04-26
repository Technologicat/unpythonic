# -*- coding: utf-8 -*-
"""Detect let and do forms, and destructure them writably."""

from ...syntax import macros, test, test_raises, warn, the  # noqa: F401
from ...test.fixtures import session, testset

from mcpyrate.quotes import macros, q, n  # noqa: F401, F811
from mcpyrate.metatools import macros, expandrq  # noqa: F811

from ...syntax import (macros, let, letrec, dlet, dletrec,  # noqa: F811, F401
                       do, local,
                       autocurry)

from ast import Tuple, Name, Constant, Lambda, BinOp, Attribute, Call
import sys

from mcpyrate import unparse

from ...syntax.astcompat import getconstant, Num
from ...syntax.letdoutil import (canonize_bindings,
                                 isenvassign, islet, isdo,
                                 UnexpandedEnvAssignView,
                                 UnexpandedLetView, ExpandedLetView,
                                 UnexpandedDoView, ExpandedDoView)
from ...syntax.nameutil import isx

def runtests():
    # --------------------------------------------------------------------------------
    # Internal-ish utilities

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
        locref = q[n["here"]]
        locref.lineno = 9001
        locref.col_offset = 9
        test[validate(the[canonize_bindings(q[k0, v0].elts, locref)])]  # noqa: F821, it's quoted.
        test[validate(the[canonize_bindings(q[((k0, v0),)].elts, locref)])]  # noqa: F821
        test[validate(the[canonize_bindings(q[(k0, v0), (k1, v1)].elts, locref)])]  # noqa: F821

    # --------------------------------------------------------------------------------
    # AST structure matching

    # The let[] and do[] macros, used in the tests of islet() and isdo(),
    # need this utility, so we must test it first.
    with testset("isenvassign"):
        test[not isenvassign(q[x])]  # noqa: F821
        test[isenvassign(q[x << 42])]  # noqa: F821

    with testset("islet"):
        test[not islet(q[x])]  # noqa: F821
        test[not islet(q[f()])]  # noqa: F821

        test[islet(the[expandrq[let[(x, 21)][2 * x]]]) == ("expanded_expr", "let")]  # noqa: F821, `let` defines `x`
        test[islet(the[expandrq[let[(x, 21) in 2 * x]]]) == ("expanded_expr", "let")]  # noqa: F821
        test[islet(the[expandrq[let[2 * x, where(x, 21)]]]) == ("expanded_expr", "let")]  # noqa: F821

        with expandrq as testdata:  # pragma: no cover
            @dlet((x, 21))  # noqa: F821
            def f1():
                return 2 * x  # noqa: F821
        test[islet(the[testdata[0].decorator_list[0]]) == ("expanded_decorator", "let")]

        testdata = q[let[(x, 21)][2 * x]]  # noqa: F821
        test[islet(the[testdata], expanded=False) == ("lispy_expr", "let")]

        # one binding special case for haskelly let-in
        testdata = q[let[(x, 21) in 2 * x]]  # noqa: F821
        test[islet(the[testdata], expanded=False) == ("in_expr", "let")]

        testdata = q[let[((x, 21), (y, 2)) in y * x]]  # noqa: F821
        test[islet(the[testdata], expanded=False) == ("in_expr", "let")]

        testdata = q[let[2 * x, where(x, 21)]]  # noqa: F821
        test[islet(the[testdata], expanded=False) == ("where_expr", "let")]

        # some other macro invocation
        test[not islet(the[q[someothermacro((x, 21))[2 * x]]], expanded=False)]  # noqa: F821
        test[not islet(the[q[someothermacro[(x, 21) in 2 * x]]], expanded=False)]  # noqa: F821

        # invalid syntax for haskelly let-in
        testdata = q[let[a in b]]  # noqa: F821
        test[not islet(the[testdata], expanded=False)]

        with q as testdata:  # pragma: no cover
            @dlet((x, 21))  # noqa: F821
            def f2():
                return 2 * x  # noqa: F821
        test[islet(the[testdata[0].decorator_list[0]], expanded=False) == ("decorator", "dlet")]

    with testset("islet integration with autocurry"):
        # NOTE: We have to be careful with how we set up the test data here.
        #
        # The quasiquote operator must be outside the `with autocurry` block,
        # because otherwise `autocurry` will attempt to curry the AST-lifted
        # representation, leading to arguably funny but nonsensical things like
        # `ctx=currycall(ast.Load)`.
        with expandrq as testdata:
            with autocurry:  # pragma: no cover
                let((x, 21))[2 * x]  # noqa: F821  # note this goes into an ast.Expr
        thelet = testdata[0].value
        test[islet(the[thelet]) == ("curried_expr", "let")]

        with expandrq as testdata:
            with autocurry:  # pragma: no cover
                let[(x, 21) in 2 * x]  # noqa: F821
        thelet = testdata[0].value
        test[islet(the[thelet]) == ("curried_expr", "let")]

        with expandrq as testdata:
            with autocurry:  # pragma: no cover
                let[2 * x, where(x, 21)]  # noqa: F821
        thelet = testdata[0].value
        test[islet(the[thelet]) == ("curried_expr", "let")]

    with testset("isdo"):
        test[not isdo(q[x])]  # noqa: F821
        test[not isdo(q[f()])]  # noqa: F821

        test[isdo(the[expandrq[do[x << 21,  # noqa: F821
                                  2 * x]]]) == "expanded"]  # noqa: F821

        with expandrq as testdata:  # pragma: no cover
            with autocurry:
                do[x << 21,  # noqa: F821
                   2 * x]  # noqa: F821
        thedo = testdata[0].value
        test[isdo(the[thedo]) == "curried"]

        testdata = q[do[x << 21,  # noqa: F821
                        2 * x]]  # noqa: F821
        test[isdo(the[testdata], expanded=False) == "do"]

        testdata = q[do0[23,  # noqa: F821
                         x << 21,  # noqa: F821
                         2 * x]]  # noqa: F821
        test[isdo(the[testdata], expanded=False) == "do0"]

        testdata = q[someothermacro[x << 21,  # noqa: F821
                                    2 * x]]  # noqa: F821
        test[not isdo(the[testdata], expanded=False)]

    # --------------------------------------------------------------------------------
    # Destructuring - envassign

    with testset("envassign destructuring"):
        testdata = q[x << 42]  # noqa: F821
        view = UnexpandedEnvAssignView(testdata)

        # read
        test[view.name == "x"]
        test[type(the[view.value]) in (Constant, Num) and getconstant(view.value) == 42]  # Python 3.8: ast.Constant

        # write
        view.name = "y"
        view.value = q[23]
        test[view.name == "y"]
        test[type(the[view.value]) in (Constant, Num) and getconstant(view.value) == 23]  # Python 3.8: ast.Constant

        # it's a live view
        test[unparse(testdata) == "(y << 23)"]

        # error cases
        test_raises[TypeError,
                    UnexpandedEnvAssignView(q[x]),  # noqa: F821
                    "not an env assignment"]
        with test_raises(TypeError, "name must be str"):
            view.name = 1234

    # --------------------------------------------------------------------------------
    # Destructuring - unexpanded let - the phase where all sensible people do their AST edits

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
        testdata = q[let[(x, 21), (y, 2)][y * x]]  # noqa: F821
        testletdestructuring(testdata)

        # haskelly let-in
        testdata = q[let[((x, 21), (y, 2)) in y * x]]  # noqa: F821
        testletdestructuring(testdata)

        # haskelly let-where
        testdata = q[let[y * x, where((x, 21), (y, 2))]]  # noqa: F821
        testletdestructuring(testdata)

        # disembodied haskelly let-in (just the content, no macro invocation)
        testdata = q[((x, 21), (y, 2)) in y * x]  # noqa: F821
        testletdestructuring(testdata)

        # disembodied haskelly let-where (just the content, no macro invocation)
        testdata = q[y * x, where((x, 21), (y, 2))]  # noqa: F821
        testletdestructuring(testdata)

        # decorator
        with q as testdata:  # pragma: no cover
            @dlet((x, 21), (y, 2))  # noqa: F821
            def f3():
                return 2 * x  # noqa: F821

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

    # --------------------------------------------------------------------------------
    # Destructuring - expanded let - for those unfortunate macros that expand after let[]
    # (yet need to edit its AST for interop purposes)

    def testexpandedletdestructuring(testdata):
        view = ExpandedLetView(testdata)

        # read
        # In the expanded form, the outer container of bindings is an `ast.Tuple`.
        test[len(view.bindings.elts) == 2]
        test[unparse(view.bindings.elts[0]) == "('x', 21)"]  # the variable names are strings
        test[unparse(view.bindings.elts[1]) == "('y', 2)"]

        # Reading an expanded let body is painful:
        lam = view.body  # lambda e: e.y * e.x
        test[type(the[lam]) is Lambda]
        lambody = lam.body
        test[type(the[lambody]) is BinOp]
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

    with testset("let destructuring (expanded let)"):
        # lispy expr
        testdata = expandrq[let[(x, 21), (y, 2)][y * x]]  # noqa: F821
        testexpandedletdestructuring(testdata)

        # haskelly let-in
        testdata = expandrq[let[((x, 21), (y, 2)) in y * x]]  # noqa: F821
        testexpandedletdestructuring(testdata)

        # haskelly let-where
        testdata = expandrq[let[y * x, where((x, 21), (y, 2))]]  # noqa: F821
        testexpandedletdestructuring(testdata)

        # decorator
        with expandrq as testdata:  # pragma: no cover
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
        # with step_expansion:
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
        testdata = expandrq[let[((x, 21)) in [local[z << 2],  # noqa: F821
                                              z * x]]]  # noqa: F821
        view = ExpandedLetView(testdata)
        lam = view.body
        test[isdo(the[lam.body])]

        test_raises[TypeError,
                    ExpandedLetView(q[x]),  # noqa: F821
                    "not an expanded let form"]

    # --------------------------------------------------------------------------------
    # Destructuring - expanded letrec - for the truly desperate

    def testexpandedletrecdestructuring(testdata):
        view = ExpandedLetView(testdata)

        # With an expanded letrec, even reading the bindings gets painful:
        def testbindings(*expected):
            for b, (k, v) in zip(view.bindings.elts, expected):
                test[len(b.elts) == 2]
                bk, lam = b.elts
                # outer quotes, source code; inner quotes, str within that source
                test[the[unparse(bk)] == the[f"'{k}'"]]
                test[type(the[lam]) is Lambda]
                lambody = lam.body
                test[type(the[lambody]) in (Constant, Num) and getconstant(lambody) == the[v]]  # Python 3.8: ast.Constant

        # read
        test[len(view.bindings.elts) == 2]
        testbindings(('x', 21), ('y', 2))

        # Reading an expanded letrec body
        lam = view.body  # lambda e: e.y * e.x
        test[type(the[lam]) is Lambda]
        lambody = lam.body
        test[type(the[lambody]) is BinOp]
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

    with testset("let destructuring (expanded letrec)"):
        # lispy expr
        testdata = expandrq[letrec[((x, 21), (y, 2)) in y * x]]  # noqa: F821
        testexpandedletrecdestructuring(testdata)

        # haskelly let-in
        testdata = expandrq[letrec[((x, 21), (y, 2)) in y * x]]  # noqa: F821
        testexpandedletrecdestructuring(testdata)

        # haskelly let-where
        testdata = expandrq[letrec[y * x, where((x, 21), (y, 2))]]  # noqa: F821
        testexpandedletrecdestructuring(testdata)

        # decorator, letrec
        with expandrq as testdata:  # pragma: no cover
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

    # --------------------------------------------------------------------------------
    # Destructuring - expanded let and letrec, integration with autocurry

    with testset("let destructuring (expanded) integration with autocurry"):
        with expandrq as testdata:
            with autocurry:  # pragma: no cover
                let[((x, 21), (y, 2)) in y * x]  # noqa: F821  # note this goes into an ast.Expr
        thelet = testdata[0].value
        testexpandedletdestructuring(thelet)

        with expandrq as testdata:
            with autocurry:  # pragma: no cover
                letrec[((x, 21), (y, 2)) in y * x]  # noqa: F821
        thelet = testdata[0].value
        testexpandedletrecdestructuring(thelet)

    # --------------------------------------------------------------------------------
    # Destructuring - unexpanded do

    with testset("do destructuring (unexpanded)"):
        testdata = q[do[local[x << 21],  # noqa: F821
                        2 * x]]  # noqa: F821
        view = UnexpandedDoView(testdata)
        # read
        thebody = view.body
        if sys.version_info >= (3, 9, 0):  # Python 3.9+: the Index wrapper is gone.
            thing = thebody[0].slice
        else:
            thing = thebody[0].slice.value
        test[isenvassign(the[thing])]
        # write
        # This mutates the original, but we have to assign `view.body` to trigger the setter.
        thebody[0] = q[local[x << 9001]]  # noqa: F821
        view.body = thebody

        # implicit do, a.k.a. extra bracket syntax
        testdata = q[let[[local[x << 21],  # noqa: F821
                          2 * x]]]  # noqa: F821
        if sys.version_info >= (3, 9, 0):  # Python 3.9+: the Index wrapper is gone.
            theimplicitdo = testdata.slice
        else:
            theimplicitdo = testdata.slice.value
        view = UnexpandedDoView(theimplicitdo)
        # read
        thebody = view.body
        if sys.version_info >= (3, 9, 0):  # Python 3.9+: the Index wrapper is gone.
            thing = thebody[0].slice
        else:
            thing = thebody[0].slice.value
        test[isenvassign(the[thing])]
        # write
        thebody[0] = q[local[x << 9001]]  # noqa: F821
        view.body = thebody

        test_raises[TypeError,
                    UnexpandedDoView(q[x]),  # noqa: F821
                    "not a do form"]

    # --------------------------------------------------------------------------------
    # Destructuring - expanded do

    with testset("do destructuring (expanded)"):
        testdata = expandrq[do[local[x << 21],  # noqa: F821
                               2 * x]]  # noqa: F821
        view = ExpandedDoView(testdata)
        test[view.envname is not None]

        # read
        # e._set('x', 21)
        thebody = view.body
        lam = thebody[0]
        test[type(the[lam.body]) is Call and
             type(lam.body.func) is Attribute and
             lam.body.func.attr == "_set" and
             unparse(lam.body.args[0]) == "'x'"]
        # write
        # This mutates the original, but we have to assign `view.body` to trigger the setter.
        envname = view.envname
        thebody[0] = q[lambda _: name[envname]._set('x', 9001)]  # noqa: F821
        view.body = thebody  # the body lambdas gets the correct envname auto-injected as their arg

        test_raises[TypeError,
                    ExpandedDoView(q[x]),  # noqa: F821
                    "not an expanded do form"]

    with testset("do destructuring (expanded) integration with autocurry"):
        with expandrq as testdata:  # pragma: no cover
            with autocurry:
                do[local[x << 21],  # noqa: F821
                   2 * x]  # noqa: F821
        thedo = testdata[0].value
        view = ExpandedDoView(thedo)
        test[view.envname is not None]

        # read
        # currycall(e._set, 'x', 21)
        thebody = view.body
        lam = thebody[0]
        test[type(the[lam.body]) is Call and
             isx(lam.body.func, "currycall") and
             type(lam.body.args[0]) is Attribute and
             lam.body.args[0].attr == "_set" and
             unparse(lam.body.args[1]) == "'x'"]
        # write
        # This mutates the original, but we have to assign `view.body` to trigger the setter.
        envname = view.envname
        thebody[0] = q[lambda _: name[envname]._set('x', 9001)]  # noqa: F821
        view.body = thebody  # the body lambdas gets the correct envname auto-injected as their arg

if __name__ == '__main__':  # pragma: no cover
    with session(__file__):
        runtests()
