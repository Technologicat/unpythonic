# -*- coding: utf-8 -*-
"""Ultralight math notebook.

Auto-print top-level expressions, auto-assign last result as _."""

# This is the kind of thing thinking with macros does to your program. ;)

from ast import Expr, Call, Name

from macropy.core.quotes import macros, q, u, ast_literal
from macropy.core.walkers import Walker

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

# with dbg:
#     x = 3
#     print(x)   # --> "x: <value>"
#
# with dbg(prt):
#     x = 3
#     prt(x)     # --> prt(name, value)
#
def dbg(body, args):
    p = args[0] if args else q[print]  # custom print function hook
    if type(p) is not Name:
        assert False, "The print function can only be specified by a bare name"
    theid = p.id

    @Walker
    def transform(tree, *, stop, **kw):
        if type(tree) is Call and type(tree.func) is Name and tree.func.id == theid and \
           len(tree.args) == 1 and type(tree.args[0]) is Name:
            varname = q[u[tree.args[0].id]]
            tree.args.insert(0, varname)
        return tree

    return [transform.recurse(stmt) for stmt in body]
