#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Simple classical lambda-based let.

It works, but does not support assignment, so it can't be used for things like
let-over-lambda, or indeed letrec.  But it's simple, and creates real lexical
variables.

These are here mainly for documentation purposes; the other macros are designed
to work together with the regular "let", "letseq", "letrec", not these ones.
"""

# Unlike the other submodules, this module contains the macro interface;
# these macros are not part of the top-level ``unpythonic.syntax`` interface.

from macropy.core.macros import Macros
from macropy.core.quotes import macros, q, ast_literal

from ast import arg

macros = Macros()

@macros.expr
def simple_let(tree, args, **kw):  # args; ast.Tuple: (k1, v1), (k2, v2), ..., (kn, vn)
    """[syntax, expr] Introduce local bindings, as real lexical variables.

    Usage::

        simple_let(bindings)[body]

    where ``bindings`` is a comma-separated sequence of pairs ``(name, value)``
    and ``body`` is an expression. The names bound by ``simple_let`` are local;
    they are available in ``body``, and do not exist outside ``body``.

    Each ``name`` in the same ``simple_let`` must be unique.

    Example::

        from unpythonic.syntax import macros, simple_let

        simple_let((x, 40))[print(x+2)]

    ``simple_let`` expands into a ``lambda``::

        simple_let((x, 1), (y, 2))[print(x, y)]
        # --> (lambda x, y: print(x, y))(1, 2)
    """
    names  = [k.id for k, _ in (a.elts for a in args)]
    if len(set(names)) < len(names):
        assert False, "binding names must be unique in the same simple_let"
    values = [v for _, v in (a.elts for a in args)]
    lam = q[lambda: ast_literal[tree]]
    lam.args.args = [arg(arg=x) for x in names]  # inject args
    return q[ast_literal[lam](ast_literal[values])]

@macros.expr
def simple_letseq(tree, args, **kw):
    """[syntax, expr] Let with sequential binding (like Scheme/Racket let*).

    Like ``simple_let``, but bindings take effect sequentially. Later bindings
    shadow earlier ones if the same name is used multiple times.

    Expands to nested ``simple_let`` expressions.
    """
    if not args:
        return tree
    first, *rest = args
    return simple_let.transform(simple_letseq.transform(tree, *rest), first)
