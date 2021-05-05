# -*- coding: utf-8 -*-
"""Lispython: The love child of Python and Scheme.

Powered by `mcpyrate` and `unpythonic`.
"""

__all__ = ["Lispython"]

__version__ = '2.0.0'

from mcpyrate.quotes import macros, q  # noqa: F401

from mcpyrate.dialects import Dialect
from mcpyrate.splicing import splice_dialect

class Lispython(Dialect):
    """**Schemers rejoice!**

    Multiple musings mix in a lambda,
    Lament no longer the lack of let.
    Languish no longer labelless, lambda,
    Linked lists cons and fold.
    Tail-call into recursion divine,
    The final value always provide.
    """

    def transform_ast(self, tree):  # tree is an ast.Module
        with q as template:
            __lang__ = "Lispython"  # noqa: F841, just provide it to user code.
            from unpythonic.syntax import (macros, tco, autoreturn,  # noqa: F401, F811
                                           multilambda, quicklambda, namedlambda, f,
                                           let, letseq, letrec,
                                           dlet, dletseq, dletrec,
                                           blet, bletseq, bletrec,
                                           local, delete, do, do0,
                                           let_syntax, abbrev,
                                           cond)
            # Auxiliary syntax elements for the macros.
            from unpythonic.syntax import where, block, expr  # noqa: F401, F811
            from unpythonic import cons, car, cdr, ll, llist, nil, prod, dyn  # noqa: F401, F811
            with autoreturn, quicklambda, multilambda, tco, namedlambda:
                __paste_here__  # noqa: F821, just a splicing marker.
        tree.body = splice_dialect(tree.body, template, "__paste_here__")
        return tree
