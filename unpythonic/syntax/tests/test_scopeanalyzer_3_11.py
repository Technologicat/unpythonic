# -*- coding: utf-8 -*-
"""Lexical scope analysis tools — try/except* tests.

These tests require Python 3.11+ because the ``except*`` syntax
won't parse on earlier versions.

TODO: Merge into test_scopeanalyzer.py when floor bumps to Python 3.11+.
"""

from ...syntax import macros, test, test_raises, the  # noqa: F401
from ...test.fixtures import session, testset

from mcpyrate.quotes import macros, q  # noqa: F401, F811

from ...syntax.scopeanalyzer import get_names_in_store_context

def runtests():
    with testset("try/except*: get_names_in_store_context"):
        # except* binds names just like except
        with q as exceptstar_simple:
            try:
                pass
            except* ValueError as eg:  # noqa: F841, it's only quoted.
                pass
        test[get_names_in_store_context(exceptstar_simple) == ["eg"]]

        with q as exceptstar_multi:
            try:
                pass
            except* ValueError as eg1:  # noqa: F841, it's only quoted.
                pass
            except* TypeError as eg2:  # noqa: F841, it's only quoted.
                pass
        test[get_names_in_store_context(exceptstar_multi) == ["eg1", "eg2"]]

        # Names bound inside the try body are also collected
        with q as exceptstar_with_assign:
            try:
                x = 42  # noqa: F841, it's only quoted.
            except* ValueError as eg:  # noqa: F841, it's only quoted.
                y = 1  # noqa: F841, it's only quoted.
        names = get_names_in_store_context(exceptstar_with_assign)
        test["x" in the[names]]
        test["y" in the[names]]
        test["eg" in the[names]]

if __name__ == '__main__':  # pragma: no cover
    with session(__file__):
        runtests()
