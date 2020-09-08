# -*- coding: utf-8 -*-
"""Simple classical lambda-based let.

It works, but does not support assignment, so it can't be used for things like
let-over-lambda, or indeed letrec.  But it's simple, and creates real lexical
variables.

These are here mainly for documentation purposes; the other macros are designed
to work together with the regular ``let``, ``letseq``, ``letrec`` from the module
``unpythonic.syntax``, not the ones defined here.
"""

# Unlike the other submodules, this module contains the macro interface;
# these macros are not part of the top-level ``unpythonic.syntax`` interface.

from macropy.core.macros import Macros
from macropy.core.quotes import macros, q, ast_literal

from ast import arg

macros = Macros()  # noqa: F811

# Syntax transformers
def _let(tree, args):
    names = [k.id for k, _ in (a.elts for a in args)]
    if len(set(names)) < len(names):
        assert False, "binding names must be unique in the same let"  # pragma: no cover
    values = [v for _, v in (a.elts for a in args)]
    lam = q[lambda: ast_literal[tree]]
    lam.args.args = [arg(arg=x) for x in names]  # inject args
    return q[ast_literal[lam](ast_literal[values])]

def _letseq(tree, args):
    if not args:
        return tree
    first, *rest = args
    return _let(_letseq(tree, rest), (first,))

# Macro interface
@macros.expr
def let(tree, args, **kw):  # args: `tuple`, each element `ast.Tuple`: (k1, v1), (k2, v2), ..., (kn, vn)
    """[syntax, expr] Introduce local bindings, as real lexical variables.

    See also ``unpythonic.syntax.let``, which uses an ``env`` to allow assignments.

    Usage::

        let(bindings)[body]

    where ``bindings`` is a comma-separated sequence of pairs ``(name, value)``
    and ``body`` is an expression. The names bound by ``let`` are local;
    they are available in ``body``, and do not exist outside ``body``.

    Each ``name`` in the same ``let`` must be unique.

    Example::

        from unpythonic.syntax.simplelet import macros, let

        let((x, 40))[print(x+2)]

    ``let`` expands into a ``lambda``::

        let((x, 1), (y, 2))[print(x, y)]
        # --> (lambda x, y: print(x, y))(1, 2)
    """
    return _let(tree, args)

@macros.expr
def letseq(tree, args, **kw):
    """[syntax, expr] Let with sequential binding (like Scheme/Racket let*).

    Like ``let``, but bindings take effect sequentially. Later bindings
    shadow earlier ones if the same name is used multiple times.

    Expands to nested ``let`` expressions.

    Real lexical variables. See also ``unpythonic.syntax.letseq``, which uses
    an ``env`` to allow assignments.
    """
    return _letseq(tree, args)
