# -*- coding: utf-8 -*-
"""Implicitly reference attributes of an object."""

from ast import Name, Assign, Attribute, Load

from macropy.core.quotes import macros, q, u, name, ast_literal
from macropy.core.walkers import Walker

from ..dynassign import dyn
from ..lazyutil import force1

# TODO: suppport Attribute, Subscript in autoref
# TODO: support nested autorefs
# We need something like::
#
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
#
# One possible clean-ish implementation is::
#
#   with autoref(o):
#       x        # --> (lambda _ar271: _ar271[1] if _ar271[0] else x)(_autoref_resolve((o, "x")))
#       x.a      # --> ((lambda _ar271: _ar271[1] if _ar271[0] else x)(_autoref_resolve((o, "x")))).a
#       x[s]     # --> ((lambda _ar271: _ar271[1] if _ar271[0] else x)(_autoref_resolve((o, "x"))))[s]
#       o        # --> o
#       with autoref(p):
#          # the outer autoref just needs to insert its obj to the arglist
#          x     # --> (lambda _ar314: _ar314[1] if _ar314[0] else x)(_autoref_resolve((p, o, "x")))
#          x.a   # --> ((lambda _ar314: _ar314[1] if _ar314[0] else x)(_autoref_resolve((p, o, "x"))).a
#          x[s]  # --> ((lambda _ar314: _ar314[1] if _ar314[0] else x)(_autoref_resolve((p, o, "x")))[s]
#          # these are transformed when the **outer** autoref transforms
#          o     # --> (lambda _ar314: _ar314[1] if _ar314[0] else o)(_autoref_resolve((p, "o")))
#          o.x   # --> ((lambda _ar314: _ar314[1] if _ar314[0] else o)(_autoref_resolve((p, "o")))).x
#          o[s]  # --> ((lambda _ar314: _ar314[1] if _ar314[0] else o)(_autoref_resolve((p, "o"))))[s]
#
# The lambda is needed, because the lexical-variable lookup for ``x`` must occur at the use site,
# and it can only be performed by Python itself. We could modify ``_autoref_resolve`` to take
# ``locals()`` and ``globals()`` as arguments and look also in the ``builtins`` module,
# but that way we get no access to the enclosing scopes (the "E" in LEGB).
#
# Recall the blocks expand from inside out. Here ``_ar*`` are gensyms. A single unique name
# for the parameter of the lambdas would be sufficient, but this is easier to arrange.
#
# In ``_autoref_resolve``, we use a single args parameter to avoid dealing with ``*args``
# when analyzing the Call node, thus avoiding much special-case code for the AST differences
# between Python 3.4 and 3.5+.
#
# In reality, we also capture-and-assign the autoref'd expr into a gensym'd variable (instead of referring
# to ``o`` and ``p`` directly), so that arbitrary expressions can be autoref'd without giving them
# a name in user code.

def _autoref_resolve(args):
    *objs, s = args
    for o in objs:
        if hasattr(o, s):
            return True, force1(getattr(o, s))
    return False, None

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
