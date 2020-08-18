# -*- coding: utf-8 -*-
"""Ultralight math notebook.

Auto-print top-level expressions, auto-assign last result as _.
"""

# This is the kind of thing thinking with macros does to your program. ;)

from ast import Expr, Subscript, Name, Call

from macropy.core.quotes import macros, q, ast_literal  # noqa: F401

from .util import isx

def nb(body, args):
    p = args[0] if args else q[print]  # custom print function hook
    newbody = []
    with q as init:
        _ = None
        theprint = ast_literal[p]
    newbody.extend(init)
    for stmt in body:
        if type(stmt) is not Expr or istestmacro(stmt.value):
            newbody.append(stmt)
            continue
        with q as newstmts:
            _ = ast_literal[stmt.value]
            if _ is not None:
                theprint(_)
        newbody.extend(newstmts)
    return newbody

# Integration with the test framework - ignore test[] et al. expressions.
#
# See unpythonic.syntax.test.testutil and unpythonic.test.fixtures.
# TODO: move istestmacro to testutil?
_test_macro_names = ["test", "test_signals", "test_raises", "error", "fail"]
_test_function_names = ["unpythonic_assert",
                        "unpythonic_assert_signals",
                        "unpythonic_assert_raises"]
def istestmacro(tree):
    def isunexpandedtestmacro(tree):
        return (type(tree) is Subscript and
                type(tree.value) is Name and
                tree.value.id in _test_macro_names)
    def isexpandedtestmacro(tree):
        return (type(tree) is Call and
                any(isx(tree.func, fname, accept_attr=False)
                    for fname in _test_function_names))
    return isunexpandedtestmacro(tree) or isexpandedtestmacro(tree)
