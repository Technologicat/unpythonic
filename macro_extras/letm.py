#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""let as a macro for Python, like in Lisps.

No need for ``lambda e: ...``, and proper lexical scoping in letseq."""

from macropy.core.macros import Macros
from macropy.core.walkers import Walker
from macropy.core.quotes import macros, q, ast_literal, name
from macropy.core.hquotes import macros, hq

from ast import Call, arg, Name, Attribute, Load, Tuple, Str

from unpythonic.lispylet import letrec as letrecf

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
    return Call(func=lam, args=values, keywords=[])

# Like Scheme/Racket let*. Expands to nested let expressions.
@macros.expr
def letseq(tree, args, **kw):
    if not args:
        return tree
    first, *rest = args
    return let(letseq(tree, rest), [first])

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
    e = gen_sym()

    # x -> e.x for x in names
    @Walker
    def transform_name(tree, *, stop, **kw):
        if type(tree) is Attribute:  # do not recurse into attributes
            stop()
        elif type(tree) is Name and tree.id in names:
            return Attribute(value=hq[name[e]], attr=tree.id, ctx=Load())
        return tree
    values = [transform_name.recurse(v) for v in values]  # binding RHSs
    tree = transform_name.recurse(tree)                   # letrec body

    # insert the "lambda e: ..." to binding RHSs and the body
    def envwrap(astnode):
        lam = q[lambda: ast_literal[astnode]]
        lam.args.args = [arg(arg=e)]
        return lam
    values = [envwrap(v) for v in values]
    tree = envwrap(tree)

    # build the call to unpythonic.lispylet.letrec.
    #
    # CAREFUL - the elts arg of ast.Tuple MUST be a list, NOT a tuple.
    # Using a tuple triggers a mysterious-looking error about an invalid
    # AST node.
    binding_pairs = [Tuple(elts=[Str(s=k), v], ctx=Load())
                       for k, v in zip(names, values)]  # name as str
    binding_pairs = Tuple(elts=binding_pairs, ctx=Load())
    return Call(func=hq[letrecf], args=[binding_pairs, tree], keywords=[])
