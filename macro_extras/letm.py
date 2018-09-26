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

# functions that do the work
from unpythonic.lispylet import letrec as letrecf, let as letf
from unpythonic.seq import do as dof, assign as assignf

## highly useful debug tools:
#from macropy.core import unparse  # AST --> source code
## https://bitbucket.org/takluyver/greentreesnakes/src/default/astpp.py
#from astpp import dump  # show AST

macros = Macros()

# This simple classical lambda-based version works, but does not support assignment,
# so it can't be used for things like let-over-lambda, or indeed letrec.
#
# But it's simple, and creates real lexical variables, which is sometimes useful
# (such as in the "aif" macro).

#  simple_let((x, 1), (y, 2))[print(x, y)]
#  --> (lambda x, y: print(x, y))(1, 2)
@macros.expr
def simple_let(tree, args, **kw):
    # Each arg is a tuple of (ast.Name, some_value) representing a binding.
    names  = [k.id for k, _ in (a.elts for a in args)]
    values = [v for _, v in (a.elts for a in args)]
    lam = q[lambda: ast_literal[tree]]  # we can inject args later...
    # ...like this. lam.args is an ast.arguments instance; its .args is a list
    # of positional arg names, as strings wrapped into ast.arg objects.
    lam.args.args = [arg(arg=x) for x in names]
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
#  - remove the need for quotes around the variable names
#  - automatically wrap each RHS and the body in a lambda e: ...
#  - if x is defined in bindings, expand any bare x in body
#    (and in bindings) into e.x
#  - respect lexical scoping by naming the environments uniquely, so that
#    names from other lexically surrounding letrec expressions remain visible.

def _transform_let(bindings, body, mode, envname, varnames, setter):
    def t1(subtree):  # x << val --> e.set('x', val)
        return _assignment_walker.recurse(subtree, names=varnames, setter=setter)
    def t2(subtree):  # x --> e.x, and insert the "lambda e: ..."
        subtree = _transform_name.recurse(subtree, names=varnames, envname=envname)
        subtree = _envwrap(subtree, envname=envname)
        return subtree
    if mode == "let":
        bindings = [t1(b) for b in bindings]
    elif mode == "letrec":
        bindings = [t2(t1(b)) for b in bindings]
    else:
        assert False, "unknown mode {}".format(mode)
    body = t2(t1(body))
    return bindings, body

def _let(tree, args, mode, gen_sym):
#    names = [k.id for k, _ in (a.elts for a in args)]
#    values = [v for _, v in (a.elts for a in args)]
    # (k1, v1), ... (kn, vn) --> (k1, ..., kn), (v1, ..., vn)
    names, values = zip(*[a.elts for a in args])
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

# insert the "lambda e: ..." to feed in the environment
def _envwrap(tree, envname):
    lam = q[lambda: ast_literal[tree]]
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


# What we need to macro-wrap seq.do is similar to letrec, so implemented here.
@macros.expr
def do(tree, gen_sym, **kw):
    e = gen_sym("e")
    outlines = []
    names = []
    for line in tree.elts:
        # assignment syntax, e.g. "x << 1"
        # TODO: for now, seq.do only supports this at the top level (whole "line").
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
