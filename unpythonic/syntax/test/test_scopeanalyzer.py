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
        warn["TODO: This testset not implemented yet."]

    with testset("get_names_in_del_context"):
        warn["TODO: This testset not implemented yet."]

    with testset("get_lexical_variables"):
        warn["TODO: This testset not implemented yet."]

    with testset("scoped_walker"):
        warn["TODO: This testset not implemented yet."]

if __name__ == '__main__':  # pragma: no cover
    with session(__file__):
        runtests()
