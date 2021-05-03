# -*- coding: utf-8 -*-
"""Ultralight math notebook.

Auto-print top-level expressions, auto-assign last result as _.
"""

__all__ = ["nb"]

# This is the kind of thing thinking with macros does to your program. ;)

from ast import Expr

from mcpyrate.quotes import macros, q, u, a, h  # noqa: F401

from mcpyrate import parametricmacro

from .testingtools import istestmacro

@parametricmacro
def nb(tree, *, args, syntax, **kw):
    """[syntax, block] Ultralight math notebook.

    Auto-print top-level expressions, auto-assign last result as _.

    A custom print function can be supplied as an argument.

    Example::

        with nb:
            2 + 3
            42 * _

        from sympy import *
        with nb[pprint]:
            x, y = symbols("x, y")
            x * y
            3 * _
    """
    if syntax != "block":
        raise SyntaxError("nb is a block macro only")
    if syntax == "block" and kw['optional_vars'] is not None:
        raise SyntaxError("nb does not take an asname")

    # Expand outside in. This macro is so simple and orthogonal the
    # ordering doesn't matter. This is cleaner.
    return _nb(body=tree, args=args)

def _nb(body, args):
    p = args[0] if args else q[h[print]]  # custom print function hook
    with q as newbody:  # pragma: no cover, quoted only.
        _ = None
        theprint = a[p]
    for stmt in body:
        # We ignore statements (because no return value), and,
        # test[] and related expressions from our test framework.
        # Those don't return a value either, and play a role
        # similar to the `assert` statement.
        if type(stmt) is not Expr or istestmacro(stmt.value):
            newbody.append(stmt)
            continue
        with q as newstmts:  # pragma: no cover, quoted only.
            _ = a[stmt.value]
            if _ is not None:
                theprint(_)
        newbody.extend(newstmts)
    return newbody
