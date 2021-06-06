# -*- coding: utf-8 -*-
"""Implicitly reference attributes of an object."""

__all__ = ["autoref"]

from ast import (Name, Load, Call, Lambda, arg,
                 Attribute, Subscript, Store, Del)

from mcpyrate.quotes import macros, q, u, n, a, h  # noqa: F401

from mcpyrate import gensym, parametricmacro
from mcpyrate.astfixers import fix_ctx
from mcpyrate.quotes import is_captured_value
from mcpyrate.walkers import ASTTransformer

from .astcompat import getconstant
from .nameutil import isx
from .util import ExpandedAutorefMarker
from .letdoutil import isdo, islet, ExpandedDoView, ExpandedLetView
from .testingtools import _test_function_names

from ..dynassign import dyn
from ..lazyutil import force1, passthrough_lazy_args

# with autoref[o]:
# with autoref[scipy.loadmat("mydata.mat")]:       # evaluate once, assign to a gensym
# with autoref[scipy.loadmat("mydata.mat")] as o:  # evaluate once, assign to given name
#
# We need something like::
#
#   with autoref[o]:
#       x        # --> (o.x if hasattr(o, "x") else x)
#       x.a      # --> (o.x.a if hasattr(o, "x") else x.a)
#       x[s]     # --> (o.x[s] if hasattr(o, "x") else x[s])
#       o        # --> o
#       with autoref[p]:
#          x     # --> (p.x if hasattr(p, "x") else (o.x if hasattr(o, "x") else x))
#          x.a   # --> (p.x.a if hasattr(p, "x") else (o.x.a if hasattr(o, "x") else x.a))
#          x[s]  # --> (p.x[s] if hasattr(p, "x") else (o.x[s] if hasattr(o, "x") else x[s]))
#          o     # --> (p.o if hasattr(p, "o") else o)
#          o.x   # --> (p.o.x if hasattr(p, "o") else o.x)
#          o[s]  # --> (p.o[s] if hasattr(p, "o") else o[s])
#
# One possible clean-ish implementation is::
#
#   $ASTMarker<ExpandedAutorefMarker>:
#       varname: 'o'
#       body:
#           x        # --> (lambda _ar271: _ar271[1] if _ar271[0] else x)(_autoref_resolve((o, "x")))
#           x.a      # --> ((lambda _ar271: _ar271[1] if _ar271[0] else x)(_autoref_resolve((o, "x")))).a
#           x[s]     # --> ((lambda _ar271: _ar271[1] if _ar271[0] else x)(_autoref_resolve((o, "x"))))[s]
#           o        # --> o   (can only occur if an as-part is supplied)
#           $ASTMarker<ExpandedAutorefMarker>:
#               varname: 'p'
#               body:
#                   x     # --> (lambda _ar314: _ar314[1] if _ar314[0] else x)(_autoref_resolve((p, o, "x")))
#                   x.a   # --> ((lambda _ar314: _ar314[1] if _ar314[0] else x)(_autoref_resolve((p, o, "x"))).a
#                   x[s]  # --> ((lambda _ar314: _ar314[1] if _ar314[0] else x)(_autoref_resolve((p, o, "x")))[s]
#                   # when the inner autoref expands, it doesn't know about the outer one, so we will get this:
#                   o     # --> (lambda _ar314: _ar314[1] if _ar314[0] else o)(_autoref_resolve((p, "o")))
#                   o.x   # --> ((lambda _ar314: _ar314[1] if _ar314[0] else o)(_autoref_resolve((p, "o")))).x
#                   o[s]  # --> ((lambda _ar314: _ar314[1] if _ar314[0] else o)(_autoref_resolve((p, "o"))))[s]
#                   # the outer autoref needs the marker to know to skip this (instead of looking up o.p):
#                   p     # --> p
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
# when analyzing the Call node. This used to be to avoid much special-case code for the
# AST differences between Python 3.4 and 3.5+. Now this doesn't matter any more, but
# there's no reason to change the design, either.
#
# In reality, we also capture-and-assign the autoref'd expr into a gensym'd variable (instead of referring
# to ``o`` and ``p`` directly), so that arbitrary expressions can be autoref'd without giving them
# a name in user code.

@parametricmacro
def autoref(tree, *, args, syntax, expander, **kw):
    """Implicitly reference attributes of an object.

    Example::

        e = env(a=1, b=2)
        c = 3
        with autoref[e]:
            a
            b
            c

    The macro argument of `with autoref[...]` is an arbitrary expression that,
    at run time, evaluates to the object instance to be autoreferenced.

    At the beginning of the block, the expression given as the macro argument
    is implicitly assigned to a gensymmed variable, and then always used from
    there, to ensure that the expression is evaluated only once. If you want to
    explicitly name the variable instead of allowing `autoref` to gensym it,
    use `with autoref[...] as ...`::

        with autoref[e] as the_e:
            a
            b
            c

    (Explicit naming can be useful for debugging.)

    The transformation is applied in ``Load`` context only. ``Store`` and ``Del``
    are not redirected.

    Useful e.g. with the ``.mat`` file loader of SciPy.

    **CAUTION**: `autoref` is essentially the `with` construct of JavaScript
    (which is completely different from Python's meaning of `with`), which is
    nowadays deprecated. See:

        https://www.ecma-international.org/ecma-262/6.0/#sec-with-statement
        https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Statements/with
        https://2ality.com/2011/06/with-statement.html

    **CAUTION**: The auto-reference `with` construct was deprecated in JavaScript
    **for security reasons**. Since the autoref'd object **will hijack all name
    lookups**, use `with autoref` only with an object you trust!

    **CAUTION**: `with autoref` also complicates static code analysis or makes it
    outright infeasible, for the same reason. It is impossible to statically know
    whether something that looks like a bare name in the source code is actually
    a true bare name, or a reference to an attribute of the autoref'd object.
    That status can also change at any time, since the lookup is dynamic, and
    attributes can be added and removed dynamically.
    """
    if syntax != "block":
        raise SyntaxError("autoref is a block macro only")  # pragma: no cover
    if not args:
        raise SyntaxError("autoref requires an argument, the object to be auto-referenced")  # pragma: no cover

    target = kw.get("optional_vars", None)
    if target and type(target) is not Name:  # tuples not accepted
        raise SyntaxError("with autoref[...] as ... takes at most one name in the as-part")  # pragma: no cover

    with dyn.let(_macro_expander=expander):
        return _autoref(block_body=tree, args=args, asname=target)

# --------------------------------------------------------------------------------

@passthrough_lazy_args
def _autoref_resolve(args):
    *objs, s = [force1(x) for x in args]
    for o in objs:
        if hasattr(o, s):
            return True, force1(getattr(o, s))
    return False, None

def _autoref(block_body, args, asname):
    # first pass, outside-in
    if len(args) != 1:
        raise SyntaxError("expected exactly one argument, the expr to implicitly reference")  # pragma: no cover
    if not block_body:
        raise SyntaxError("expected at least one statement inside the 'with autoref' block")  # pragma: no cover

    block_body = dyn._macro_expander.visit_recursively(block_body)

    # second pass, inside-out

    # `autoref`'s analyzer needs the `ctx` attributes in `tree` to be filled in correctly.
    block_body = fix_ctx(block_body, copy_seen_nodes=False)  # TODO: or maybe copy seen nodes?

    o = asname.id if asname else gensym("_o")  # Python itself guarantees asname to be a bare Name.

    # (lambda _ar314: _ar314[1] if _ar314[0] else x)(_autoref_resolve((p, o, "x")))
    def isautoreference(tree):
        return (type(tree) is Call and
                len(tree.args) == 1 and type(tree.args[0]) is Call and
                isx(tree.args[0].func, "_autoref_resolve") and
                type(tree.func) is Lambda and len(tree.func.args.args) == 1 and
                tree.func.args.args[0].arg.startswith("_ar"))
    def get_resolver_list(tree):  # (p, o, "x")
        return tree.args[0].args[0].elts
    def add_to_resolver_list(tree, objnode):
        lst = get_resolver_list(tree)
        lst.insert(-1, objnode)

    # x --> the autoref code above.
    def makeautoreference(tree):
        # We don't need to care about `Done` markers from expanded `@namemacro`s
        # because the transformer that calls this function recurses into them.
        assert type(tree) is Name and (type(tree.ctx) is Load or not tree.ctx)
        newtree = q[(lambda __ar_: __ar_[1] if __ar_[0] else a[tree])(h[_autoref_resolve]((n[o], u[tree.id])))]
        our_lambda_argname = gensym("_ar")

        # TODO: could we use `mcpyrate.utils.rename` here?
        class PlaceholderRenamer(ASTTransformer):
            def transform(self, tree):
                if is_captured_value(tree):
                    return tree  # don't recurse!
                if type(tree) is Name and tree.id == "__ar_":
                    tree.id = our_lambda_argname
                elif type(tree) is arg and tree.arg == "__ar_":
                    tree.arg = our_lambda_argname
                return self.generic_visit(tree)
        return PlaceholderRenamer().visit(newtree)

    class AutorefTransformer(ASTTransformer):
        def transform(self, tree):
            if is_captured_value(tree):
                return tree  # don't recurse!

            referents = self.state.referents
            if type(tree) in (Attribute, Subscript, Name) and type(tree.ctx) in (Store, Del):
                return tree
            # skip autoref lookup for let/do envs
            elif islet(tree):
                view = ExpandedLetView(tree)
                self.generic_withstate(tree, referents=referents + [view.body.args.args[0].arg])  # lambda e14: ...
            elif isdo(tree):
                view = ExpandedDoView(tree)
                self.generic_withstate(tree, referents=referents + [view.body[0].args.args[0].arg])  # lambda e14: ...
            elif isinstance(tree, ExpandedAutorefMarker):
                self.generic_withstate(tree, referents=referents + [tree.varname])
            elif isautoreference(tree):  # generated by an inner already expanded autoref block
                thename = getconstant(get_resolver_list(tree)[-1])
                if thename in referents:
                    # This case is tricky to trigger, so let's document it here. This code:
                    #
                    # with autoref[e]:
                    #     with autoref[e2]:
                    #         e
                    #
                    # expands to:
                    #
                    # $ASTMarker<ExpandedAutorefMarker>:
                    #     varname: '_o5'
                    #     body:
                    #         _o5 = e
                    #         $ASTMarker<ExpandedAutorefMarker>:
                    #             varname: '_o4'
                    #             body:
                    #                 _o4 = (lambda _ar13: (_ar13[1] if _ar13[0] else e2))(_autoref_resolve((_o5, 'e2')))
                    #                 (lambda _ar9: (_ar9[1] if _ar9[0] else e))(_autoref_resolve((_o4, _o5, 'e')))
                    #
                    # so there's no "e" as referent; the actual referent has a gensymmed name.
                    # Inside the body of the inner autoref, looking up "e" in e2 before falling
                    # back to the outer "e" is exactly what `autoref` is expected to do.
                    #
                    # Where is this used, then? The named variant `with autoref[...] as ...`:
                    #
                    # with step_expansion:
                    #     with autoref[e] as outer:
                    #         with autoref[e2] as inner:
                    #             outer
                    #
                    # expands to:
                    #
                    # $ASTMarker<ExpandedAutorefMarker>:
                    #     varname: 'outer'
                    #     body:
                    #         outer = e
                    #         $ASTMarker<ExpandedAutorefMarker>:
                    #             varname: 'inner'
                    #             body:
                    #                 inner = (lambda _ar17: (_ar17[1] if _ar17[0] else e2))(_autoref_resolve((outer, 'e2')))
                    #                 outer  # <-- !!!
                    #
                    # Now this case is triggered; we get a bare `outer` inside the inner body.
                    # TODO: Whether this wart is a good idea is another question...

                    # remove autoref lookup for an outer referent, inserted early by an inner autoref block
                    # (that doesn't know that any outer block exists)
                    tree = q[n[thename]]  # (lambda ...)(_autoref_resolve((p, "o"))) --> o
                else:
                    add_to_resolver_list(tree, q[n[o]])  # _autoref_resolve((p, "x")) --> _autoref_resolve((p, o, "x"))
                return tree
            elif isinstance(tree, ExpandedAutorefMarker):  # nested autorefs
                return tree
            elif type(tree) is Name and (type(tree.ctx) is Load or not tree.ctx) and tree.id not in referents:
                tree = makeautoreference(tree)
                return tree
            # Attribute works as-is, because a.b.c --> Attribute(Attribute(a, "b"), "c"), so Name "a" gets transformed.
            # Subscript similarly, a[1][2] --> Subscript(Subscript(a, 1), 2), so Name "a" gets transformed.
            return self.generic_visit(tree)

    # Skip (by name) some common references inserted by other macros.
    #
    # This part runs in the inside-out pass, so any outside-in macro invocations,
    # as well as any inside-out macro invocations inside the `with autoref`
    # block, have already expanded by the time we run our transformer.
    always_skip = ['letter', 'dof',  # let/do subsystem
                   'namelambda',  # lambdatools subsystem
                   'curry', 'curryf' 'currycall',  # autocurry subsystem
                   'lazy', 'lazyrec', 'maybe_force_args',  # lazify subsystem
                   # the test framework subsystem
                   'callsite_filename', 'returns_normally'] + _test_function_names
    with q as newbody:
        n[o] = a[args[0]]
    for stmt in block_body:
        newbody.append(AutorefTransformer(referents=always_skip + [o]).visit(stmt))

    return ExpandedAutorefMarker(body=newbody, varname=o)
