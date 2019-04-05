# -*- coding: utf-8 -*-
"""Ultralight math notebook.

Auto-print top-level expressions, auto-assign last result as _.

Also provided is a debug printer, which prints both the expression source code
and its value.
"""

# This is the kind of thing thinking with macros does to your program. ;)

from ast import Expr, Call, Name, Tuple

from macropy.core.quotes import macros, q, u, ast_literal
from macropy.core.hquotes import macros, hq
from macropy.core.walkers import Walker
from macropy.core import unparse

def nb(body, args):
    p = args[0] if args else q[print]  # custom print function hook
    newbody = []
    with q as init:
        _ = None
        theprint = ast_literal[p]
    newbody.extend(init)
    for stmt in body:
        if type(stmt) is not Expr:
            newbody.append(stmt)
            continue
        with q as newstmts:
            _ = ast_literal[stmt.value]
            if _ is not None:
                theprint(_)
        newbody.extend(newstmts)
    return newbody

# -----------------------------------------------------------------------------

def dbgprint(ks, vs, *, sep=", ", **kwargs):
    """Default debug printer for the ``dbg`` macro.

    The default print format looks like::

        x: 2, y: 3, (17 + 23): 40

    Parameters:

        ``ks``: ``tuple``
            expressions as strings

        ``vs``: ``tuple``
            the corresponding values

        ``sep``: ``str``
            separator as in built-in ``print``,
            used between the expression/value pairs.

        ``kwargs``: anything
            passed through to built-in ``print``

    **Implementing a custom debug printer**:

    When implementing a custom print function, it **must** accept two
    positional arguments, ``ks`` and ``vs``.

    It may also accept other arguments (see built-in ``print``), or just
    ``**kwargs`` them through to the built-in ``print``, if you like.

    Other arguments are only needed if the print calls in the ``dbg`` sections
    of your client code use them. (To be flexible, this default debug printer
    supports ``sep`` and passes everything else through.)
    """
    print(sep.join("{}: {}".format(k, v) for k, v in zip(ks, vs)), **kwargs)

def dbg(body, args):
    if args:  # custom print function hook
        # TODO: add support for Attribute to support using a method as a custom print function
        if type(args[0]) is not Name:
            assert False, "Custom debug print function must be specified by a bare name"
        p = args[0]
        pname = p.id  # name of the print function as it appears in the user code
    else:
        p = hq[dbgprint]
        pname = "print"

    @Walker
    def transform(tree, **kw):
        if type(tree) is Call and type(tree.func) is Name and tree.func.id == pname:
            names = [q[u[unparse(node)]] for node in tree.args]  # x --> "x"; (1 + 2) --> "(1 + 2)"; ...
            names = Tuple(elts=names, lineno=tree.lineno, col_offset=tree.col_offset)
            values = Tuple(elts=tree.args, lineno=tree.lineno, col_offset=tree.col_offset)
            tree.args = [names, values]
            tree.func = q[ast_literal[p]]
        return tree

    return [transform.recurse(stmt) for stmt in body]
