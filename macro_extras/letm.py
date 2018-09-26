#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""let as a macro for Python, like in Lisps.

Proper lexical scoping, and no need for ``lambda e: ...``.

Macros can only take positional args (as of MacroPy3 v1.1), so we use
the lispylet syntax (but without quotes around the variable names)::

    let((x, 1),
        (y, 2))[
          print(x, y)]

Note the ``[...]``; ``let`` is an ``expr`` macro.
"""

from macropy.core.macros import Macros
from macropy.core.walkers import Walker
from macropy.core.quotes import macros, q, u, ast_literal, name
from macropy.core.hquotes import macros, hq

from ast import arg, Name, Attribute, Load, BinOp, LShift, keyword, Call
from functools import partial

from unpythonic.it import uniqify

# functions that do the work
from unpythonic.lispylet import letrec as letrecf, let as letf
from unpythonic.seq import do as dof, assign as assignf

## highly useful debug tools:
#from macropy.core import unparse  # AST --> source code
## https://bitbucket.org/takluyver/greentreesnakes/src/default/astpp.py
#from astpp import dump  # AST --> human-readable repr

macros = Macros()

# This simple classical lambda-based version works, but does not support assignment,
# so it can't be used for things like let-over-lambda, or indeed letrec.
# But it's simple, and creates real lexical variables.

#  simple_let((x, 1), (y, 2))[print(x, y)]
#  --> (lambda x, y: print(x, y))(1, 2)
@macros.expr
def simple_let(tree, args, **kw):  # args; ast.Tuple: (k1, v1), (k2, v2), ..., (kn, vn)
    names  = [k.id for k, _ in (a.elts for a in args)]
    values = [v for _, v in (a.elts for a in args)]
    lam = q[lambda: ast_literal[tree]]
    lam.args.args = [arg(arg=x) for x in names]  # inject args
    return q[ast_literal[lam](ast_literal[values])]

# Like Scheme/Racket let*. Expands to nested let expressions.
@macros.expr
def simple_letseq(tree, args, **kw):
    if not args:
        return tree
    first, *rest = args
    return simple_let(simple_letseq(tree, rest), [first])

# Sugar around unpythonic.lispylet. We take this approach because letrec
# needs assignment (must create placeholder bindings, then update them
# with the real value)... but in Python, assignment is a statement.
#
# As a bonus, we get assignment for let and letseq, too.
# (Now that we have a separate macro expansion pass, we can provide a letseq.)
#
#  - no quotes around variable names in bindings
#  - automatically wrap each RHS and the body in a lambda e: ...
#  - for all x in bindings, transform x --> e.x
#  - respect lexical scoping by naming the environments uniquely
def _t(subtree, envname, varnames, setter):
    subtree = _assignment_walker.recurse(subtree, names=varnames, setter=setter)  # x << val --> e.set('x', val)
    subtree = _transform_name.recurse(subtree, names=varnames, envname=envname)  # x --> e.x
    return _envwrap(subtree, envname=envname)  # ... -> lambda e: ...

def _transform_let(bindings, body, mode, envname, varnames, setter):
    t = partial(_t, envname=envname, varnames=varnames, setter=setter)
    if mode == "letrec":
        bindings = [t(b) for b in bindings]
    body = t(body)
    return bindings, body

def _let(tree, args, mode, gen_sym):  # args; ast.Tuple: (k1, v1), (k2, v2), ..., (kn, vn)
    names, values = zip(*[a.elts for a in args])  # --> (k1, ..., kn), (v1, ..., vn)
    names = [k.id for k in names]

    e = gen_sym("e")
    envset = Attribute(value=hq[name[e]], attr="set", ctx=Load())
    values, tree = _transform_let(values, tree, mode, e, names, envset)

    binding_pairs = [q[(u[k], ast_literal[v])] for k, v in zip(names, values)]
    func = letf if mode == "let" else letrecf
    return hq[func((ast_literal[binding_pairs],), ast_literal[tree])]  # splice into tuple context

@macros.expr
def let(tree, args, gen_sym, **kw):
    return _let(tree, args, "let", gen_sym)

# Like Scheme/Racket let*. Expands to nested let expressions.
@macros.expr
def letseq(tree, args, gen_sym, **kw):
    if not args:
        return tree
    first, *rest = args
    return let(letseq(tree, rest, gen_sym), [first], gen_sym)

@macros.expr
def letrec(tree, args, gen_sym, **kw):
    return _let(tree, args, "letrec", gen_sym)

@macros.expr
def do(tree, gen_sym, **kw):
    e = gen_sym("e")
    # must use env.__setattr__ to define new names; env.set only rebinds.
    envset = Attribute(value=hq[name[e]], attr="__setattr__", ctx=Load())

    @Walker
    def _find_assignments(tree, collect, **kw):
        if _isassign(tree):
            collect(tree.left.id)
        return tree
    names = list(uniqify(_find_assignments.collect(tree)))

    lines = [_t(line, e, names, envset) for line in tree.elts]
    return hq[dof(ast_literal[lines])]

def _isassign(tree):  # detect "x << 42" syntax to assign variables in an environment
    return type(tree) is BinOp and type(tree.op) is LShift and type(tree.left) is Name

# x << val --> e.set('x', val)  (for names bound in this environment)
@Walker
def _assignment_walker(tree, *, names, setter, **kw):
    if not _isassign(tree):
        return tree
    varname = tree.left.id
    if varname not in names:  # each let handles only its own varnames
        return tree
    value = tree.right
    return q[ast_literal[setter](u[varname], ast_literal[value])]

# # ... -> lambda e: ...
def _envwrap(tree, envname):
    lam = q[lambda: ast_literal[tree]]
    lam.args.args = [arg(arg=envname)]
    return lam

# x --> e.x  (for names bound in this environment)
@Walker
def _transform_name(tree, *, names, envname, stop, **kw):
    if type(tree) is Attribute:
        stop()
    elif type(tree) is Name and tree.id in names:
        return Attribute(value=hq[name[envname]], attr=tree.id, ctx=Load())
    return tree
