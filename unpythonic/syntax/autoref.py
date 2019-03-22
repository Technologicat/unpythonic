# -*- coding: utf-8 -*-
"""Implicitly reference attributes of an object."""

from ast import Name, Assign, Attribute, Load

from macropy.core.quotes import macros, q, u, name, ast_literal
from macropy.core.walkers import Walker

from ..dynassign import dyn

# TODO: suppport Attribute, Subscript in autoref
# TODO: support nested autorefs
# Consider:
#   with autoref(o):
#       x        # --> (o.x if hasattr(o, "x") else x)
#       x.a      # --> (o.x.a if hasattr(o, "x") else x.a)
#       x[s]     # --> (o.x[s] if hasattr(o, "x") else x[s])
#       o        # --> o
#       with autoref(p):
#          x     # --> (p.x if hasattr(p, "x") else (o.x if hasattr(o, "x") else x))
#          x.a   # --> (p.x.a if hasattr(p, "x") else (o.x.a if hasattr(o, "x") else x.a))
#          x[s]  # --> (p.x[s] if hasattr(p, "x") else (o.x[s] if hasattr(o, "x") else x[s]))
#          o     # --> (p.o if hasattr(p, "o") else o)
#          o.x   # --> (p.o.x if hasattr(p, "o") else o.x)
#          o[s]  # --> (p.o[s] if hasattr(p, "o") else o[s])

def autoref(block_body, args):
    assert len(args) == 1, "expected exactly one argument, the object to implicitly reference"
    assert block_body, "expected at least one statement in the 'with autoref' block"

    # assign the implicit object to a temporary name, to resolve a computed reference only once
    gen_sym = dyn.gen_sym
    ref = gen_sym("r")

    @Walker
    def transform(tree, *, stop, **kw):
        if not (type(tree) is Name and type(tree.ctx) is Load):
            return tree
        stop()
        x = tree.id
        theattr = Attribute(value=q[name[ref]], attr=x)
        newtree = q[ast_literal[theattr] if hasattr(name[ref], u[x]) else ast_literal[tree]]
        return newtree

    newbody = [Assign(targets=[q[name[ref]]], value=args[0])]
    for stmt in block_body:
        newbody.append(transform.recurse(stmt))

    return newbody
