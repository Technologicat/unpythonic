# -*- coding: utf-8 -*-
"""Implicitly reference attributes of an object."""

from ast import (Name, Assign, Load, Call, Lambda, With, Str, arg,
                 Attribute, Subscript, Store, Del)

from macropy.core.quotes import macros, q, u, name, ast_literal
from macropy.core.hquotes import macros, hq  # noqa: F811, F401
from macropy.core.walkers import Walker

from .util import wrapwith, AutorefMarker
from .letdoutil import isdo, islet, ExpandedDoView, ExpandedLetView

from ..dynassign import dyn
from ..lazyutil import force1, passthrough_lazy_args

# with autoref(o):
# with autoref(scipy.loadmat("mydata.mat")):       # evaluate once, assign to a gensym
# with autoref(scipy.loadmat("mydata.mat")) as o:  # evaluate once, assign to given name
#
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
#   with AutorefMarker("o"):  # no-op at runtime
#       x        # --> (lambda _ar271: _ar271[1] if _ar271[0] else x)(_autoref_resolve((o, "x")))
#       x.a      # --> ((lambda _ar271: _ar271[1] if _ar271[0] else x)(_autoref_resolve((o, "x")))).a
#       x[s]     # --> ((lambda _ar271: _ar271[1] if _ar271[0] else x)(_autoref_resolve((o, "x"))))[s]
#       o        # --> o   (can only occur if an asname is supplied)
#       with AutorefMarker("p"):
#          x     # --> (lambda _ar314: _ar314[1] if _ar314[0] else x)(_autoref_resolve((p, o, "x")))
#          x.a   # --> ((lambda _ar314: _ar314[1] if _ar314[0] else x)(_autoref_resolve((p, o, "x"))).a
#          x[s]  # --> ((lambda _ar314: _ar314[1] if _ar314[0] else x)(_autoref_resolve((p, o, "x")))[s]
#          # when the inner autoref expands, it doesn't know about the outer one, so we will get this:
#          o     # --> (lambda _ar314: _ar314[1] if _ar314[0] else o)(_autoref_resolve((p, "o")))
#          o.x   # --> ((lambda _ar314: _ar314[1] if _ar314[0] else o)(_autoref_resolve((p, "o")))).x
#          o[s]  # --> ((lambda _ar314: _ar314[1] if _ar314[0] else o)(_autoref_resolve((p, "o"))))[s]
#          # the outer autoref needs the marker to know to skip this (instead of looking up o.p):
#          p     # --> p
#
# The lambda is needed, because the lexical-variable lookup for ``x`` must occur at the use site,
# and it can only be performed by Python itself. We could modify ``_autoref_resolve`` to take
# ``locals()`` and ``globals()`` as arguments and look also in the ``builtins`` module,
# but that way we get no access to the enclosing scopes (the "E" in LEGB).
#
# Recall the blocks expand from inside out.
#
# We must leave an AST marker in place of the each autoref block, so that any outer autoref block (when it expands)
# understands that within that block, any read access to the name "p" is to be left alone.
#
# In ``_autoref_resolve``, we use a single args parameter to avoid dealing with ``*args``
# when analyzing the Call node, thus avoiding much special-case code for the AST differences
# between Python 3.4 and 3.5+.
#
# In reality, we also capture-and-assign the autoref'd expr into a gensym'd variable (instead of referring
# to ``o`` and ``p`` directly), so that arbitrary expressions can be autoref'd without giving them
# a name in user code.

@passthrough_lazy_args
def _autoref_resolve(args):
    *objs, s = [force1(x) for x in args]
    for o in objs:
        if hasattr(o, s):
            return True, force1(getattr(o, s))
    return False, None

def autoref(block_body, args, asname):
    assert len(args) == 1, "expected exactly one argument, the expr to implicitly reference"
    assert block_body, "expected at least one statement inside the 'with autoref' block"

    gen_sym = dyn.gen_sym
    o = asname.id if asname else gen_sym("_o")  # Python itself guarantees asname to be a bare Name.

    # with AutorefMarker("_o42"):
    def isexpandedautorefblock(tree):
        if not (type(tree) is With and len(tree.items) == 1):
            return False
        ctxmanager = tree.items[0].context_expr
        return (type(ctxmanager) is Call and
                type(ctxmanager.func) is Name and ctxmanager.func.id == "AutorefMarker" and
                len(ctxmanager.args) == 1 and type(ctxmanager.args[0]) is Str)
    def getreferent(tree):
        return tree.items[0].context_expr.args[0].s

    # (lambda _ar314: _ar314[1] if _ar314[0] else x)(_autoref_resolve((p, o, "x")))
    def isautoreference(tree):
        return (type(tree) is Call and
                len(tree.args) == 1 and type(tree.args[0]) is Call and
                type(tree.args[0].func) is Name and tree.args[0].func.id == "_autoref_resolve" and
                type(tree.func) is Lambda and len(tree.func.args.args) == 1 and
                tree.func.args.args[0].arg.startswith("_ar"))
    def get_resolver_list(tree):  # (p, o, "x")
        return tree.args[0].args[0].elts
    def add_to_resolver_list(tree, objnode):
        lst = get_resolver_list(tree)
        lst.insert(-1, objnode)

    # x --> the autoref code above.
    def makeautoreference(tree):
        assert type(tree) is Name and (type(tree.ctx) is Load or not tree.ctx)
        newtree = hq[(lambda __ar_: __ar_[1] if __ar_[0] else ast_literal[tree])(_autoref_resolve((name[o], u[tree.id])))]
        our_lambda_argname = gen_sym("_ar")
        @Walker
        def renametmp(tree, **kw):
            if type(tree) is Name and tree.id == "__ar_":
                tree.id = our_lambda_argname
            elif type(tree) is arg and tree.arg == "__ar_":
                tree.arg = our_lambda_argname
            return tree
        return renametmp.recurse(newtree)

    @Walker
    def transform(tree, *, referents, set_ctx, stop, **kw):
        if type(tree) in (Attribute, Subscript, Name) and type(tree.ctx) in (Store, Del):
            stop()
        # skip autoref lookup for let/do envs
        elif islet(tree):
            view = ExpandedLetView(tree)
            set_ctx(referents=referents + [view.body.args.args[0].arg])  # lambda e14: ...
        elif isdo(tree):
            view = ExpandedDoView(tree)
            set_ctx(referents=referents + [view.body[0].args.args[0].arg])  # lambda e14: ...
        elif isexpandedautorefblock(tree):
            set_ctx(referents=referents + [getreferent(tree)])
        elif isautoreference(tree):  # generated by an inner already expanded autoref block
            stop()
            thename = get_resolver_list(tree)[-1].s  # TODO: Python 3.8: ast.Constant, no ast.Str
            if thename in referents:
                # This case is tricky to trigger, so let's document it here. This code:
                #
                # with autoref(e):
                #     with autoref(e2):
                #         e
                #
                # expands to:
                #
                # with AutorefMarker('_o5'):
                #     _o5 = e
                #     with AutorefMarker('_o4'):
                #         _o4 = (lambda _ar13: (_ar13[1] if _ar13[0] else e2))(_autoref_resolve((_o5, 'e2')))
                #         (lambda _ar9: (_ar9[1] if _ar9[0] else e))(_autoref_resolve((_o4, _o5, 'e')))
                #
                # so there's no "e" as referent; the actual referent has a gensymmed name.
                # Inside the body of the inner autoref, looking up "e" in e2 before falling
                # back to the outer "e" is exactly what `autoref` is expected to do.
                #
                # Where is this used, then? The named variant `with autoref(...) as ...`:
                #
                # with show_expanded:
                #     with autoref(e) as outer:
                #         with autoref(e2) as inner:
                #             outer
                #
                # expands to:
                #
                # with AutorefMarker('outer'):
                #     outer = e
                #     with AutorefMarker('inner'):
                #         inner = (lambda _ar17: (_ar17[1] if _ar17[0] else e2))(_autoref_resolve((outer, 'e2')))
                #         outer  # <-- !!!
                #
                # Now this case is triggered; we get a bare `outer` inside the inner body.
                # TODO: Whether this wart is a good idea is another question...

                # remove autoref lookup for an outer referent, inserted early by an inner autoref block
                # (that doesn't know that any outer block exists)
                tree = q[name[thename]]  # (lambda ...)(_autoref_resolve((p, "o"))) --> o
            else:
                add_to_resolver_list(tree, q[name[o]])  # _autoref_resolve((p, "x")) --> _autoref_resolve((p, o, "x"))
        elif type(tree) is Call and type(tree.func) is Name and tree.func.id == "AutorefMarker":  # nested autorefs
            stop()
        elif type(tree) is Name and (type(tree.ctx) is Load or not tree.ctx) and tree.id not in referents:
            stop()
            tree = makeautoreference(tree)
        # Attribute works as-is, because a.b.c --> Attribute(Attribute(a, "b"), "c"), so Name "a" gets transformed.
        # Subscript similarly, a[1][2] --> Subscript(Subscript(a, 1), 2), so Name "a" gets transformed.
        return tree

    # Skip (by name) some common references inserted by other macros.
    #
    # We are a second-pass macro (inside out), so any first-pass macro invocations,
    # as well as any second-pass macro invocations inside the `with autoref` block,
    # have already expanded by the time we run our transformer.
    always_skip = ['letter', 'dof', 'namelambda', 'curry', 'currycall', 'lazy', 'lazyrec', 'maybe_force_args',
                   # test framework stuff
                   'unpythonic_assert', 'unpythonic_assert_signals', 'unpythonic_assert_raises',
                   'callsite_filename', 'returns_normally']
    newbody = [Assign(targets=[q[name[o]]], value=args[0])]
    for stmt in block_body:
        newbody.append(transform.recurse(stmt, referents=always_skip + [o]))

    return wrapwith(item=hq[AutorefMarker(u[o])],
                    body=newbody,
                    locref=block_body[0])
