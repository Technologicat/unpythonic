# -*- coding: utf-8 -*-
"""Lexical scope analysis tools."""

from ...syntax import macros, test, test_raises, warn, the  # noqa: F401
from ...test.fixtures import session, testset

from mcpyrate.quotes import macros, q, n  # noqa: F401, F811

from ast import Name

from ...syntax.scopeanalyzer import (isnewscope,
                                     get_names_in_store_context,
                                     get_names_in_del_context,
                                     get_lexical_variables,
                                     scoped_transform)

def runtests():
    # test data
    with q as getnames_load:
        x  # noqa: F821, it's only quoted.
    with q as getnames_del:
        del x  # noqa: F821
    with q as getnames_store_simple:
        x = 42  # noqa: F841, it's only quoted.

    with testset("isnewscope"):
        test[not isnewscope(q[x])]  # noqa: F821, it's only quoted.
        test[not isnewscope(q[o.x])]  # noqa: F821
        test[not isnewscope(q[d['x']])]  # noqa: F821
        test[isnewscope(q[lambda x: 2 * x])]
        with q as fdef:
            def f():
                pass
        test[isnewscope(fdef[0])]
        with q as afdef:  # Python 3.5+
            async def g():
                pass
        test[isnewscope(afdef[0])]
        with q as cdef:
            class Cat:
                has_four_legs = True
                def sleep():
                    pass
        test[isnewscope(cdef[0])]
        test[not isnewscope(cdef[0].body[0])]  # Cat.has_four_legs
        test[isnewscope(cdef[0].body[1])]  # Cat.sleep
        test[isnewscope(q[[x for x in range(10)]])]  # ListComp
        test[isnewscope(q[{x for x in range(10)}])]  # SetComp
        test[isnewscope(q[(x for x in range(10))])]  # GeneratorExp
        test[isnewscope(q[{x: x**2 for x in range(10)}])]  # DictComp

    with testset("get_names_in_store_context"):
        test[get_names_in_store_context(getnames_load) == []]
        test[get_names_in_store_context(getnames_del) == []]

        # Python has surprisingly many constructs for binding names.
        # https://docs.python.org/3/reference/executionmodel.html#binding-of-names
        # Useful article: http://excess.org/article/2014/04/bar-foo/

        # Assignment
        #
        # At least up to Python 3.7, all assignments produce Name nodes in
        # Store context on their LHS, so we don't need to care what kind of
        # assignment it is.
        test[get_names_in_store_context(getnames_store_simple) == ["x"]]
        with q as getnames_tuple:
            x, y = 1, 2  # noqa: F841
        test[get_names_in_store_context(getnames_tuple) == ["x", "y"]]
        with q as getnames_starredtuple:
            x, y, *rest = range(5)  # noqa: F841
        test[get_names_in_store_context(getnames_starredtuple) == ["x", "y", "rest"]]

        # Function name, async function name, class name
        with q as getnames_func:
            def f1():
                pass
        test[get_names_in_store_context(getnames_func) == ["f1"]]
        with q as getnames_afunc:  # Python 3.5+
            async def f2():
                pass
        test[get_names_in_store_context(getnames_afunc) == ["f2"]]
        with q as getnames_class:
            class Classy:
                pass
        test[get_names_in_store_context(getnames_class) == ["Classy"]]

        # For loop target
        with q as getnames_for_simple:
            for x in range(5):
                pass
        test[get_names_in_store_context(getnames_for_simple) == ["x"]]
        with q as getnames_for_tuple:
            for x, y in zip(range(5), range(5)):
                pass
        test[get_names_in_store_context(getnames_for_tuple) == ["x", "y"]]
        with q as getnames_for_mixed:
            for j, (x, y) in enumerate(zip(range(5), range(5))):
                pass
        test[get_names_in_store_context(getnames_for_mixed) == ["j", "x", "y"]]

        # Async for loop target (Python 3.5+)
        with q as getnames_afor_simple:
            async def g1():
                async for x in range(5):
                    pass
        test[get_names_in_store_context(getnames_afor_simple) == ["g1"]]  # we stop at scope boundaries
        test[get_names_in_store_context(getnames_afor_simple[0].body) == ["x"]]
        with q as getnames_afor_tuple:
            async def g2():
                async for x, y in zip(range(5), range(5)):
                    pass
        test[get_names_in_store_context(getnames_afor_tuple) == ["g2"]]
        test[get_names_in_store_context(getnames_afor_tuple[0].body) == ["x", "y"]]
        with q as getnames_afor_mixed:
            async def g3():
                async for j, (x, y) in enumerate(zip(range(5), range(5))):
                    pass
        test[get_names_in_store_context(getnames_afor_mixed) == ["g3"]]
        test[get_names_in_store_context(getnames_afor_mixed[0].body) == ["j", "x", "y"]]

        # Import statement
        with q as getnames_import:
            import mymod  # noqa: F401
            import yourmod as renamedmod  # noqa: F401
            from othermod import original as renamed, other  # noqa: F401
        test[get_names_in_store_context(getnames_import) == ["mymod", "renamedmod", "renamed", "other"]]

        # Except clause target in try statement
        with q as getnames_try:
            try:
                pass
            except Exception as err:  # noqa: F841
                pass
            except KeyboardInterrupt as kbi:  # noqa: F841
                pass
        test[get_names_in_store_context(getnames_try) == ["err", "kbi"]]

        # With statement target
        with q as getnames_with:
            with Manager() as boss:  # noqa: F821, F841
                pass
        test[get_names_in_store_context(getnames_with) == ["boss"]]

        # Async with statement target (Python 3.5+)
        with q as getnames_awith:
            async def g4():
                async with Manager() as boss:  # noqa: F821, F841
                    pass
        test[get_names_in_store_context(getnames_awith) == ["g4"]]
        test[get_names_in_store_context(getnames_awith[0].body) == ["boss"]]

    with testset("get_names_in_del_context"):
        test[get_names_in_del_context(getnames_load) == []]
        test[get_names_in_del_context(getnames_store_simple) == []]

        test[get_names_in_del_context(getnames_del) == ["x"]]

        # Intended for static analysis of lexical variables.
        # We ignore `del o.x` and `del d['x']`, because these
        # don't delete the lexical variables `o` and `d`.
        with q as getnames_del_attrib:
            del o.x  # noqa: F821, F841
        test[get_names_in_del_context(getnames_del_attrib) == []]

        with q as getnames_del_subscript:
            del d["x"]  # noqa: F821, F841
        test[get_names_in_del_context(getnames_del_subscript) == []]

        with q as getnames_del_scope_boundary:
            del x  # noqa: F821
            def f3():
                del y  # noqa: F821
        test[get_names_in_del_context(getnames_del_scope_boundary) == ["x"]]
        test[get_names_in_del_context(getnames_del_scope_boundary[1].body) == ["y"]]

    with testset("get_lexical_variables"):
        with q as getlexvars_fdef:
            y = 21
            def myfunc(x, *args, kwonlyarg, **kwargs):
                nonlocal y  # not really needed here, except for exercising the analyzer.
                global g
                def inner(blah):
                    abc = 123  # noqa: F841
                z = 2 * y  # noqa: F841
        test_raises[TypeError, get_lexical_variables(getlexvars_fdef[0])]  # wrong AST node type
        test[get_lexical_variables(getlexvars_fdef[1]) == (["myfunc",
                                                            "x", "kwonlyarg", "args", "kwargs",
                                                            "inner",
                                                            "z"],
                                                           ["y", "g"])]

        # If we disable `collect_locals`, then `inner` and `z` should not be collected.
        test[get_lexical_variables(getlexvars_fdef[1], collect_locals=False) == (["myfunc",
                                                                                  "x", "kwonlyarg",
                                                                                  "args", "kwargs"],
                                                                                 ["y", "g"])]

        with q as getlexvars_classdef:
            class WorldClassy(Classy):
                pass
        test[get_lexical_variables(getlexvars_classdef[0]) == (["WorldClassy", "Classy"],
                                                               [])]

        with q as getlexvars_listcomp_simple:
            [x for x in range(5)]  # note this goes into an ast.Expr
        test[get_lexical_variables(getlexvars_listcomp_simple[0].value) == (["x"],
                                                                            [])]
        with q as getlexvars_listcomp_tuple_in_expr:
            [(x, y) for x in range(5) for y in range(x)]
        test[get_lexical_variables(getlexvars_listcomp_tuple_in_expr[0].value) == (["x", "y"],
                                                                                   [])]
        with q as getlexvars_listcomp_tuple_in_target:
            [(x, y) for x, y in zip(range(5), range(5))]
        test[get_lexical_variables(getlexvars_listcomp_tuple_in_target[0].value) == (["x", "y"],
                                                                                     [])]

    with testset("scoped_transform"):
        def istestlocation(tree):  # mark where to apply the test[] in the walking process
            return type(tree) is Name and tree.id == "_apply_test_here_"
        def make_checker(expected_names):
            def check(tree, actual_names):
                if istestlocation(tree):
                    # We use multiple the[] to capture both sides
                    # for inspection if the test fails.
                    test[the[actual_names] == the[expected_names]]
                return tree
            return check

        with q as scoped_onefunc:
            def f(x):  # noqa: F811
                n["_apply_test_here_"]
        scoped_transform(scoped_onefunc, callback=make_checker(["f", "x"]))

        with q as scoped_nestedfunc1:
            def f(x):  # noqa: F811
                n["_apply_test_here_"]
                def g(y):
                    pass
        scoped_transform(scoped_nestedfunc1, callback=make_checker(["f", "x"]))

        with q as scoped_nestedfunc2:
            def f(x):  # noqa: F811
                def g(y):
                    n["_apply_test_here_"]
        scoped_transform(scoped_nestedfunc2, callback=make_checker(["f", "x", "g", "y"]))

        with q as scoped_classdef:
            class WorldClassy(Classy):  # noqa: F811
                n["_apply_test_here_"]
        scoped_transform(scoped_classdef, callback=make_checker(["WorldClassy", "Classy"]))

        with q as scoped_localvar1:
            def f():  # noqa: F811
                x = 42  # noqa: F841
                n["_apply_test_here_"]
        scoped_transform(scoped_localvar1, callback=make_checker(["f", "x"]))

        # TODO: In 0.15.x, fully lexical scope analysis; update this test at that time.
        with q as scoped_localvar2:
            def f():  # noqa: F811
                n["_apply_test_here_"]
                x = 42  # noqa: F841
        scoped_transform(scoped_localvar2, callback=make_checker(["f"]))  # x not yet created

        # TODO: In 0.15.x, fully lexical scope analysis; update this test at that time.
        with q as scoped_localvar3:
            def f():  # noqa: F811
                x = 42  # noqa: F841
                del x
                n["_apply_test_here_"]
        scoped_transform(scoped_localvar3, callback=make_checker(["f"]))  # x already deleted

if __name__ == '__main__':  # pragma: no cover
    with session(__file__):
        runtests()
