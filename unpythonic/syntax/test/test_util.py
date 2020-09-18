# -*- coding: utf-8 -*-
"""Utilities for building macros."""

from ...syntax import macros, do, local, test, test_raises, fail, the  # noqa: F401
from ...test.fixtures import session, testset

from macropy.core.quotes import macros, q, name  # noqa: F811
from macropy.core.hquotes import macros, hq  # noqa: F811, F401

from ...syntax.util import (isec, detect_callec,
                            detect_lambda,
                            is_decorator, has_tco, has_curry, has_deco,
                            suggest_decorator_index,
                            is_lambda_decorator, is_decorated_lambda,
                            destructure_decorated_lambda, sort_lambda_decorators,
                            transform_statements, eliminate_ifones,
                            splice, wrapwith, ismarker)

from ast import Call, Name, Expr, Num, Str, With, withitem

from ...ec import call_ec, throw  # just so hq[] captures them, like in real code

def runtests():
    with testset("escape continuation (ec) utilities"):
        def ec():
            pass  # pragma: no cover
        known_ecs = ["ec", "brk", "throw"]  # see `fallbacks` in `detect_callec`
        test[isec(q[ec(42)], known_ecs)]
        test[isec(hq[ec(42)], known_ecs)]
        test[isec(q[throw(42)], known_ecs)]
        test[isec(hq[throw(42)], known_ecs)]
        test[not isec(q[myfunc(42)], known_ecs)]  # noqa: F821

        test["my_fancy_ec" in the[detect_callec(q[call_ec(lambda my_fancy_ec: None)])]]
        with q as call_ec_testdata:
            @call_ec  # pragma: no cover
            def f(my_fancy_ec):
                pass  # pragma: no cover
        test["my_fancy_ec" in the[detect_callec(call_ec_testdata)]]

    with testset("detect_lambda"):
        # Lispers NOTE: in MacroPy, the quasiquote `q` (similarly hygienic
        # quasiquote `hq`) is a macro, not a special operator; it **does not**
        # prevent the expansion of any macros invoked in the quoted code.
        # It just lifts source code into the corresponding AST representation.
        #
        # (MacroPy-technically, it's a second-pass macro, so any macros nested inside
        #  have already expanded when the quote macro runs.)
        with q as detect_lambda_testdata:
            a = lambda: None  # noqa: F841  # pragma: no cover
            b = do[local[x << 21],  # noqa: F821, F841  # pragma: no cover
                   lambda y: x * y]  # noqa: F821
        test[len(detect_lambda.collect(detect_lambda_testdata)) == 2]

    with testset("decorator utilities"):
        test[is_decorator(q[decorate], "decorate")]  # noqa: F821
        test[is_decorator(q[decorate_with("flowers")], "decorate_with")]  # noqa: F821

        with q as has_tco_testdata1:
            @trampolined  # noqa: F821, just quoted.  # pragma: no cover
            def ihavetco():
                pass  # pragma: no cover
        with q as has_tco_testdata2:
            def idonthavetco():  # pragma: no cover
                pass  # pragma: no cover
        test[has_tco(has_tco_testdata1[0])]
        test[not has_tco(has_tco_testdata2[0])]
        test[not has_tco(q[lambda: None])]
        test[not has_tco(q[decorate(lambda: None)])]  # noqa: F821
        test[has_tco(q[trampolined(lambda: None)])]  # noqa: F821
        test[has_tco(q[decorate(trampolined(lambda: None))])]  # noqa: F821
        test[has_tco(q[trampolined(decorate(lambda: None))])]  # noqa: F821

        with q as has_curry_testdata1:
            @curry  # noqa: F821, just quoted.  # pragma: no cover
            def ihavecurry():
                pass  # pragma: no cover
        with q as has_curry_testdata2:
            def idonthavecurry():  # pragma: no cover
                pass  # pragma: no cover
        test[has_curry(has_curry_testdata1[0])]
        test[not has_curry(has_curry_testdata2[0])]
        test[not has_curry(q[lambda: None])]
        test[not has_curry(q[decorate(lambda: None)])]  # noqa: F821
        test[has_curry(q[curry(lambda: None)])]  # noqa: F821
        test[has_curry(q[decorate(curry(lambda: None))])]  # noqa: F821
        test[has_curry(q[curry(decorate(lambda: None))])]  # noqa: F821

        test[has_deco(["decorate"], q["surprise!"]) is None]  # wrong AST type, test not applicable

        with q as has_deco_testdata1:
            @artdeco  # noqa: F821, just quoted.  # pragma: no cover
            def ihaveartdeco():
                pass  # pragma: no cover
        with q as has_deco_testdata2:
            def idonthaveartdeco():  # pragma: no cover
                pass  # pragma: no cover
        test[has_deco(["artdeco"], has_deco_testdata1[0])]
        test[not has_deco(["artdeco"], has_deco_testdata2[0])]
        test[not has_deco(["artdeco"], q[lambda: None])]
        test[not has_deco(["artdeco"], q[postmodern(lambda: None)])]  # noqa: F821
        test[has_deco(["artdeco"], q[artdeco(lambda: None)])]  # noqa: F821
        test[has_deco(["artdeco"], q[postmodern(artdeco(lambda: None))])]  # noqa: F821
        test[has_deco(["artdeco"], q[artdeco(postmodern(lambda: None))])]  # noqa: F821

        # if more than one option, OR'd
        test[has_deco(["artdeco", "neoclassical"], has_deco_testdata1[0])]
        test[not has_deco(["artdeco", "neoclassical"], has_deco_testdata2[0])]
        test[not has_deco(["artdeco", "neoclassical"], q[lambda: None])]
        test[not has_deco(["artdeco", "neoclassical"], q[postmodern(lambda: None)])]  # noqa: F821
        test[has_deco(["artdeco", "neoclassical"], q[artdeco(lambda: None)])]  # noqa: F821
        test[has_deco(["artdeco", "neoclassical"], q[postmodern(artdeco(lambda: None))])]  # noqa: F821
        test[has_deco(["artdeco", "neoclassical"], q[artdeco(postmodern(lambda: None))])]  # noqa: F821

        # find correct insertion index of a known decorator
        with q as sdi_testdata1:
            # This set of decorators makes no sense, but we want to exercise
            # the different branches of the analysis code.
            @curry  # noqa: F821  # pragma: no cover
            @memoize  # noqa: F821  # pragma: no cover
            @call  # noqa: F821  # pragma: no cover
            def purespicy(a, b, c):
                pass  # pragma: no cover
        test[suggest_decorator_index("artdeco", sdi_testdata1[0].decorator_list) is None]  # unknown decorator
        test[suggest_decorator_index("namelambda", sdi_testdata1[0].decorator_list) == 0]  # before any of those already specified
        test[suggest_decorator_index("trampolined", sdi_testdata1[0].decorator_list) == 2]  # in the middle of those already specified
        test[suggest_decorator_index("passthrough_lazy_args", sdi_testdata1[0].decorator_list) == 3]  # after all of those already specified

        with q as sdi_testdata2:
            @artdeco  # noqa: F821  # pragma: no cover
            @neoclassical  # noqa: F821  # pragma: no cover
            def architectural():
                pass  # pragma: no cover
        test[suggest_decorator_index("trampolined", sdi_testdata2[0].decorator_list) is None]  # known decorator, but only unknown decorators in the decorator_list

    with testset("decorated lambda machinery"):
        # detect if a Call could be a decorator for a lambda
        test[is_lambda_decorator(q[decorate(...)])]  # noqa: F821
        test[is_lambda_decorator(q[decorate(...)], fname="decorate")]  # noqa: F821
        test[not is_lambda_decorator(q[decorate(...)], fname="artdeco")]  # noqa: F821
        test[not is_lambda_decorator(q[ihavenoargs()])]  # noqa: F821
        test[not is_lambda_decorator(q[ihavemorethanonearg(..., ...)])]  # noqa: F821

        # detect a chain of Call nodes terminating in a Lambda
        test[not is_decorated_lambda(q[lambda: None], "any")]
        test[is_decorated_lambda(q[artdeco(lambda: None)], "any")]  # noqa: F821
        test[not is_decorated_lambda(q[artdeco(lambda: None)], "known")]  # noqa: F821

        test[is_decorated_lambda(q[curry(lambda: None)], "any")]  # noqa: F821
        test[is_decorated_lambda(q[curry(lambda: None)], "known")]  # noqa: F821

        test[is_decorated_lambda(q[memoize(trampolined(curry(lambda: None)))], "known")]  # noqa: F821
        # mode="known" requires **all** the decorators to be recognized.
        test[not is_decorated_lambda(q[memoize(artdeco(curry(lambda: None)))], "known")]  # noqa: F821

        # extract the "decorator list" of a decorated lambda
        # (This returns the original AST nodes, for in-place transformations.)
        decos, lam = destructure_decorated_lambda(q[memoize(trampolined(curry(lambda: 42)))])  # noqa: F821
        test[len(decos) == 3]
        test[all(type(node) is Call and type(node.func) is Name for node in decos)]
        test[[node.func.id for node in decos] == ["memoize", "trampolined", "curry"]]
        test[type(lam.body) is Num]  # TODO: Python 3.8+: ast.Constant, no ast.Num
        test[lam.body.n == 42]  # TODO: Python 3.8+: ast.Constant, no ast.Num

        def test_sort_lambda_decorators(testdata):
            sort_lambda_decorators(testdata)
            decos, _ = destructure_decorated_lambda(testdata)
            # correct ordering according to unpythonic.regutil.decorator_registry
            test[[node.func.id for node in decos] == ["curry", "memoize", "trampolined"]]
        # input ordering correct, no effect
        test_sort_lambda_decorators(q[memoize(trampolined(curry(lambda: 42)))])  # noqa: F821
        # input ordering wrong, let the sorter fix it
        test_sort_lambda_decorators(q[curry(memoize(trampolined(lambda: 42)))])  # noqa: F821

    with testset("statement utilities"):
        with q as transform_statements_testdata:
            def myfunction(x):  # pragma: no cover
                "function body"
                try:  # pragma: no cover
                    "try"
                    if x:  # pragma: no cover
                        "if body"
                    else:
                        "if else"
                except ValueError:  # pragma: no cover
                    "except"
                finally:
                    "finally"
        collected = []
        def collectstrings(tree):
            # TODO: Python 3.8+: ast.Constant, no ast.Str
            if type(tree) is Expr and type(tree.value) is Str:
                collected.append(tree.value.s)
            return [tree]
        transform_statements(collectstrings, transform_statements_testdata)
        test[set(collected) == {"function body", "try", "if body", "if else", "finally", "except"}]

        def ishello(tree):
            # TODO: Python 3.8+: ast.Constant, no ast.Str
            return type(tree) is Expr and type(tree.value) is Str and tree.value.s == "hello"

        # numeric
        with q as eliminate_ifones_testdata1:
            if 1:
                "hello"
        result = eliminate_ifones(eliminate_ifones_testdata1)
        test[len(result) == 1 and ishello(result[0])]

        with q as eliminate_ifones_testdata2:
            if 0:  # pragma: no cover
                "hello"
        result = eliminate_ifones(eliminate_ifones_testdata2)
        test[len(result) == 0]

        # boolean
        with q as eliminate_ifones_testdata3:
            if True:
                "hello"
        result = eliminate_ifones(eliminate_ifones_testdata3)
        test[len(result) == 1 and ishello(result[0])]

        with q as eliminate_ifones_testdata4:
            if False:  # pragma: no cover
                "hello"
        result = eliminate_ifones(eliminate_ifones_testdata4)
        test[len(result) == 0]

        # leave just one branch, numeric
        with q as eliminate_ifones_testdata5:
            if 1:
                "hello"
            else:
                "bye"
        result = eliminate_ifones(eliminate_ifones_testdata5)
        test[len(result) == 1 and ishello(result[0])]

        with q as eliminate_ifones_testdata6:
            if 0:
                "bye"
            else:
                "hello"
        result = eliminate_ifones(eliminate_ifones_testdata6)
        test[len(result) == 1 and ishello(result[0])]

        # leave just one branch, boolean
        with q as eliminate_ifones_testdata7:
            if True:
                "hello"
            else:
                "bye"
        result = eliminate_ifones(eliminate_ifones_testdata7)
        test[len(result) == 1 and ishello(result[0])]

        with q as eliminate_ifones_testdata8:
            if False:
                "bye"
            else:
                "hello"
        result = eliminate_ifones(eliminate_ifones_testdata8)
        test[len(result) == 1 and ishello(result[0])]

    with testset("splice"):
        with q as splice_testdata:
            name["_here_"]
            name["_here_"]
        test[all(stmt.value.id == "_here_" for stmt in splice_testdata)]
        splice(splice_testdata, q[name["replacement"]], "_here_")
        test[all(stmt.value.id == "replacement" for stmt in splice_testdata)]

    with testset("wrapwith"):
        with q as wrapwith_testdata:
            42  # pragma: no cover
        # known fake location information so we can check it copies correctly
        wrapwith_testdata[0].lineno = 9001
        wrapwith_testdata[0].col_offset = 9
        wrapped = wrapwith(q[name["ExampleContextManager"]], wrapwith_testdata)
        test[type(wrapped) is list]
        thewith = wrapped[0]
        test[type(thewith) is With]
        test[thewith.lineno == 9001]
        test[thewith.col_offset == 9]
        test[type(thewith.items[0]) is withitem]
        ctxmanager = thewith.items[0].context_expr
        test[type(ctxmanager) is Name]
        test[ctxmanager.id == "ExampleContextManager"]
        firststmt = thewith.body[0]
        test[type(firststmt) is Expr]
        test[type(firststmt.value) is Num]  # TODO: Python 3.8+: ast.Constant, no ast.Num
        test[firststmt.value.n == 42]  # TODO: Python 3.8+: ast.Constant, no ast.Num

    with testset("ismarker"):
        with q as ismarker_testdata1:
            with ExampleMarker:  # noqa: F821  # pragma: no cover
                ...
        with q as ismarker_testdata2:
            with NotAMarker1, NotAMarker2:  # noqa: F821  # pragma: no cover
                ...
        test[ismarker("ExampleMarker", ismarker_testdata1[0])]
        test[not ismarker("AnotherMarker", ismarker_testdata1[0])]  # right type, different marker
        test[not ismarker("NotAMarker1", ismarker_testdata2[0])]  # a marker must be the only ctxmanager in the `with`
        test[not ismarker("ExampleMarker", q["surprise!"])]  # wrong AST node type

if __name__ == '__main__':  # pragma: no cover
    with session(__file__):
        runtests()
