#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""let as a macro for Python, like in Lisps.

No need for ``lambda e: ...``, and proper lexical scoping in letseq."""

from macropy.core.macros import Macros

from ast import Lambda, Call, arguments, arg

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
    argnodes = [arg(arg=s, annotation=None) for s in names]
    argspec = arguments(args=argnodes, vararg=None, kwonlyargs=[],
                        kwarg=None, defaults=[], kw_defaults=[])
    return Call(func=Lambda(args=argspec, body=tree),
                args=values, keywords=[])

# Like Scheme/Racket let*. Expands to nested let expressions.
@macros.expr
def letseq(tree, args, **kw):
    if not args:
        return tree
    first, *rest = args
    return let(letseq(tree, rest), [first])
