# -*- coding: utf-8 -*-
"""Ultralight math notebook.

Auto-print top-level expressions, auto-assign last result as _.
"""

# This is the kind of thing thinking with macros does to your program. ;)

from ast import Expr

from macropy.core.quotes import macros, q, ast_literal  # noqa: F401

from .testingtools import istestmacro

def nb(body, args):
    p = args[0] if args else q[print]  # custom print function hook
    newbody = []
    with q as init:  # pragma: no cover, quoted only.
        _ = None
        theprint = ast_literal[p]
    newbody.extend(init)
    for stmt in body:
        # We ignore statements (because no return value), and,
        # test[] and related expressions from our test framework.
        # Those don't return a value either, and play a role
        # similar to the `assert` statement.
        if type(stmt) is not Expr or istestmacro(stmt.value):
            newbody.append(stmt)
            continue
        with q as newstmts:  # pragma: no cover, quoted only.
            _ = ast_literal[stmt.value]
            if _ is not None:
                theprint(_)
        newbody.extend(newstmts)
    return newbody
