#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""let as a macro for Python, like in Lisps.

No need for ``lambda e: ...``, and proper lexical scoping in letseq."""

from macropy.core.macros import Macros
from macropy.core.walkers import Walker
from macropy.core.quotes import macros, q, u, ast_literal, name
from macropy.core.hquotes import macros, hq

from ast import arg, Name, Attribute, Load, BinOp, LShift, keyword, Call

from unpythonic.lispylet import letrec as letrecf
from unpythonic.seq import do as dof, assign as assignf

## highly useful debug tools:
#from macropy.core import unparse  # AST --> source code
## https://bitbucket.org/takluyver/greentreesnakes/src/default/astpp.py
#from astpp import dump  # show AST

macros = Macros()

# Macros can only take positional args (as of MacroPy3 v1.1), so we use
# the  lispylet syntax (but without quotes around the variable names).
#   let((x, 1), (y, 2))[print(x, y)]
#   --> (lambda x, y: print(x, y))(1, 2)
@macros.expr
def let(tree, args, **kw):
    # Each arg is a tuple of (ast.Name, some_value) representing a binding.
    names  = [k.id for k, _ in (a.elts for a in args)]
    values = [v for _, v in (a.elts for a in args)]
    lam = q[lambda: ast_literal[tree]]  # we can inject args later...
    # ...like this. lam.args is an ast.arguments instance; its .args is a list
    # of positional arg names, as strings wrapped into ast.arg objects.
    lam.args.args = [arg(arg=x) for x in names]
#    return Call(func=lam, args=values, keywords=[])
    return q[ast_literal[lam](ast_literal[values])]  # same thing, with quasiquote

# Like Scheme/Racket let*. Expands to nested let expressions.
@macros.expr
def letseq(tree, args, **kw):
    if not args:
        return tree
    first, *rest = args
    return let(letseq(tree, rest), [first])

# letrec and seq.do

# insert the "lambda e: ..." to feed in the environment
def _envwrap(astnode, envname):
    lam = q[lambda: ast_literal[astnode]]
    lam.args.args = [arg(arg=envname)]
    return lam

# bare name x -> e.x for x in names bound in this environment
@Walker
def _transform_name(tree, *, names, envname, stop, **kw):
    if type(tree) is Attribute:  # do not recurse into attributes
        stop()
    elif type(tree) is Name and tree.id in names:
        return Attribute(value=hq[name[envname]], attr=tree.id, ctx=Load())
    return tree

def _isassign(tree):  # detect custom syntax to assign variables in an environment
    return type(tree) is BinOp and type(tree.op) is LShift and type(tree.left) is Name

# Sugar around unpythonic.lispylet.letrec. We take this approach because
# letrec needs assignment (must create placeholder bindings, then update
# them with the real value)... but in Python, assignment is a statement.
#
#  - remove the need for quotes around the variable names
#  - automatically wrap each RHS and the body in a lambda e: ...
#  - if x is defined in bindings, expand any bare x in body
#    (and in bindings) into e.x
@macros.expr
def letrec(tree, args, gen_sym, **kw):
    names = [k.id for k, _ in (a.elts for a in args)]
    values = [v for _, v in (a.elts for a in args)]

    # Respect lexical scoping by naming the environments uniquely, so that
    # names from other lexically surrounding letrec expressions remain visible.
    e = gen_sym("e")
    envset = Attribute(value=hq[name[e]], attr="set", ctx=Load())

    # transform binding RHSs and the body:

    # x << val --> e.set('x', val)
    @Walker
    def assignment_walker(tree, **kw):
        if not _isassign(tree):
            return tree
        varname = tree.left.id
        if varname not in names:  # each letrec handles only its own varnames
            return tree
        value = tree.right
        return q[ast_literal[envset](u[varname], ast_literal[value])]
    values = [assignment_walker.recurse(v) for v in values]
    assignment_walker.recurse(tree)

    # x -> e.x for x in names
    values = [_transform_name.recurse(v, names=names, envname=e) for v in values]
    tree = _transform_name.recurse(tree, names=names, envname=e)

    # insert the "lambda e: ..."
    values = [_envwrap(v, envname=e) for v in values]
    tree = _envwrap(tree, envname=e)

    # build the call to unpythonic.lispylet.letrec.
    #
    # CAREFUL - the elts arg of ast.Tuple MUST be a list, NOT a tuple.
    # Using a tuple triggers a mysterious-looking error about an invalid
    # AST node.
#    binding_pairs = [Tuple(elts=[Str(s=k), v], ctx=Load())
#                       for k, v in zip(names, values)]  # name as str
#    binding_pairs = Tuple(elts=binding_pairs, ctx=Load())
#    return Call(func=hq[letrecf], args=[binding_pairs, tree], keywords=[])

    # maybe more readable with quasiquotes?
    # binding_pairs produces n items as a list...
    binding_pairs = [q[(u[k], ast_literal[v])] for k, v in zip(names, values)]
    # ...so here we must place ast_literal into a tuple context, so that
    # when it unpacks the values, the end result is a tuple.
    return hq[letrecf((ast_literal[binding_pairs],), ast_literal[tree])]

# Implementation is very similar to letrec, so implemented here.
@macros.expr
def do(tree, gen_sym, **kw):
    e = gen_sym("e")
    outlines = []
    names = []
    for line in tree.elts:
        # assignment syntax, e.g. "x << 1"
        if _isassign(line):
            k = line.left.id
            names.append(k)
            # as of MacroPy 1.1.0, no unquote operator to make kwargs,
            # so we have to do this manually (since unpythonic uses the
            # kwarg syntax for assignments in a do()):
            kw = keyword(arg=k, value=line.right)
            outlines.append(Call(func=hq[assignf], args=[], keywords=[kw]))
        else:  # x -> e.x for x in names; insert the "lambda e: ..."
            line = _transform_name.recurse(line, names=names, envname=e)
            outlines.append(_envwrap(line, envname=e))
    return hq[dof(ast_literal[outlines])]
