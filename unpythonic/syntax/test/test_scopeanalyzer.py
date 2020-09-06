# -*- coding: utf-8 -*-
"""Lexical scope analysis tools."""

from ...syntax import macros, test, warn  # noqa: F401
from ...test.fixtures import session, testset

from macropy.core.quotes import macros, q  # noqa: F811, F401
# from macropy.core.hquotes import macros, hq  # noqa: F811, F401

from ...syntax.scopeanalyzer import (isnewscope,
                                     get_names_in_store_context,
                                     get_names_in_del_context,
                                     get_lexical_variables,
                                     scoped_walker)

def runtests():
    # test data
    with q as getnames_load:
        x  # noqa: F821, it's only quoted.  # pragma: no cover
    with q as getnames_del:
        del x  # noqa: F821  # pragma: no cover
    with q as getnames_store_simple:
        x = 42  # noqa: F841, it's only quoted.  # pragma: no cover

    with testset("isnewscope"):
        test[not isnewscope(q[x])]  # noqa: F821, it's only quoted.
        test[not isnewscope(q[o.x])]  # noqa: F821
        test[not isnewscope(q[d['x']])]  # noqa: F821
        test[isnewscope(q[lambda x: 2 * x])]
        with q as fdef:
            def f():  # pragma: no cover
                pass
        test[isnewscope(fdef[0])]
        with q as afdef:
            async def g():  # pragma: no cover
                pass
        test[isnewscope(afdef[0])]
        with q as cdef:
            class Cat:  # pragma: no cover
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
        test[get_names_in_store_context.collect(getnames_load) == []]
        test[get_names_in_store_context.collect(getnames_del) == []]

        # Python has surprisingly many constructs for binding names.
        # https://docs.python.org/3/reference/executionmodel.html#binding-of-names
        # Useful article: http://excess.org/article/2014/04/bar-foo/

        # Assignment
        #
        # At least up to Python 3.7, all assignments produce Name nodes in
        # Store context on their LHS, so we don't need to care what kind of
        # assignment it is.
        test[get_names_in_store_context.collect(getnames_store_simple) == ["x"]]
        with q as getnames_tuple:
            x, y = 1, 2  # noqa: F841  # pragma: no cover
        test[get_names_in_store_context.collect(getnames_tuple) == ["x", "y"]]
        with q as getnames_starredtuple:
            x, y, *rest = range(5)  # noqa: F841  # pragma: no cover
        test[get_names_in_store_context.collect(getnames_starredtuple) == ["x", "y", "rest"]]

        # Function name, async function name, class name
        with q as getnames_func:
            def f1():  # pragma: no cover
                pass
        test[get_names_in_store_context.collect(getnames_func) == ["f1"]]
        with q as getnames_afunc:
            async def f2():  # pragma: no cover
                pass
        test[get_names_in_store_context.collect(getnames_afunc) == ["f2"]]
        with q as getnames_class:
            class Classy:  # pragma: no cover
                pass
        test[get_names_in_store_context.collect(getnames_class) == ["Classy"]]

        # For loop target
        with q as getnames_for_simple:
            for x in range(5):  # pragma: no cover
                pass
        test[get_names_in_store_context.collect(getnames_for_simple) == ["x"]]
        with q as getnames_for_tuple:
            for x, y in zip(range(5), range(5)):  # pragma: no cover
                pass
        test[get_names_in_store_context.collect(getnames_for_tuple) == ["x", "y"]]
        with q as getnames_for_mixed:
            for j, (x, y) in enumerate(zip(range(5), range(5))):  # pragma: no cover
                pass
        test[get_names_in_store_context.collect(getnames_for_mixed) == ["j", "x", "y"]]

        # Async for loop target
        with q as getnames_afor_simple:
            async def g1():  # pragma: no cover
                async for x in range(5):
                    pass
        test[get_names_in_store_context.collect(getnames_afor_simple) == ["g1"]]  # we stop at scope boundaries
        test[get_names_in_store_context.collect(getnames_afor_simple[0].body) == ["x"]]
        with q as getnames_afor_tuple:
            async def g2():  # pragma: no cover
                async for x, y in zip(range(5), range(5)):
                    pass
        test[get_names_in_store_context.collect(getnames_afor_tuple) == ["g2"]]
        test[get_names_in_store_context.collect(getnames_afor_tuple[0].body) == ["x", "y"]]
        with q as getnames_afor_mixed:
            async def g3():  # pragma: no cover
                async for j, (x, y) in enumerate(zip(range(5), range(5))):
                    pass
        test[get_names_in_store_context.collect(getnames_afor_mixed) == ["g3"]]
        test[get_names_in_store_context.collect(getnames_afor_mixed[0].body) == ["j", "x", "y"]]

        # Import statement
        with q as getnames_import:
            import mymod  # noqa: F401  # pragma: no cover
            import yourmod as renamedmod  # noqa: F401  # pragma: no cover
            from othermod import original as renamed, other  # noqa: F401  # pragma: no cover
        test[get_names_in_store_context.collect(getnames_import) == ["mymod", "renamedmod", "renamed", "other"]]

        # Except clause target in try statement
        with q as getnames_try:
            try:  # pragma: no cover
                pass
            except Exception as err:  # noqa: F841
                pass
            except KeyboardInterrupt as kbi:  # noqa: F841
                pass
        test[get_names_in_store_context.collect(getnames_try) == ["err", "kbi"]]

        # With (and async with) statement target
        with q as getnames_with:
            with Manager() as boss:  # noqa: F821, F841  # pragma: no cover
                pass
        test[get_names_in_store_context.collect(getnames_with) == ["boss"]]
        with q as getnames_awith:
            async def g4():  # pragma: no cover
                async with Manager() as boss:  # noqa: F821, F841
                    pass
        test[get_names_in_store_context.collect(getnames_awith) == ["g4"]]
        test[get_names_in_store_context.collect(getnames_awith[0].body) == ["boss"]]

    with testset("get_names_in_del_context"):
        test[get_names_in_del_context.collect(getnames_load) == []]
        test[get_names_in_del_context.collect(getnames_store_simple) == []]

        test[get_names_in_del_context.collect(getnames_del) == ["x"]]

        # Intended for static analysis of lexical variables.
        # We ignore `del o.x` and `del d['x']`, because these
        # don't delete the lexical variables `o` and `d`.
        with q as getnames_del_attrib:
            del o.x  # noqa: F821, F841  # pragma: no cover
        test[get_names_in_del_context.collect(getnames_del_attrib) == []]

        with q as getnames_del_subscript:
            del d["x"]  # noqa: F821, F841  # pragma: no cover
        test[get_names_in_del_context.collect(getnames_del_subscript) == []]

    with testset("get_lexical_variables"):
        warn["TODO: This testset not implemented yet."]

    with testset("scoped_walker"):
        warn["TODO: This testset not implemented yet."]

if __name__ == '__main__':  # pragma: no cover
    with session(__file__):
        runtests()