# -*- coding: utf-8 -*-
"""Pytkell: Because it's good to have a kell.

Powered by `mcpyrate` and `unpythonic`.
"""

__all__ = ["Pytkell"]

__version__ = '2.0.0'

from mcpyrate.quotes import macros, q  # noqa: F401

from mcpyrate.dialects import Dialect
from mcpyrate.splicing import splice_dialect

class Pytkell(Dialect):
    def transform_ast(self, tree):  # tree is an ast.Module
        with q as template:
            __lang__ = "Pytkell"  # noqa: F841, just provide it to user code.
            from unpythonic.syntax import (macros, lazy, lazyrec, lazify, autocurry,  # noqa: F401, F811
                                           where,
                                           let, letseq, letrec,
                                           dlet, dletseq, dletrec,
                                           blet, bletseq, bletrec,
                                           local, delete, do, do0,
                                           cond, forall)
            # Auxiliary syntax elements for the macros.
            from unpythonic.syntax import insist, deny  # noqa: F401
            # Functions that have a haskelly feel to them.
            from unpythonic import (foldl, foldr, scanl, scanr,  # noqa: F401
                                    s, imathify, gmathify, frozendict,
                                    memoize, fupdate, fup,
                                    gmemoize, imemoize, fimemoize,
                                    islice, take, drop, split_at, first, second, nth, last,
                                    flip, rotate)
            from unpythonic import composerc as compose  # compose from Right, Currying (Haskell's . operator)  # noqa: F401
            # This is a bit lispy, but we're not going out of our way to provide
            # a haskelly surface syntax for these.
            from unpythonic import cons, car, cdr, ll, llist, nil  # noqa: F401
            with lazify, autocurry:
                __paste_here__  # noqa: F821, just a splicing marker.

        # Beginning with 3.6.0, `mcpyrate` makes available the source location info
        # of the dialect-import that imported this dialect.
        if hasattr(self, "lineno"):  # mcpyrate 3.6.0+
            tree.body = splice_dialect(tree.body, template, "__paste_here__",
                                       lineno=self.lineno, col_offset=self.col_offset)
        else:
            tree.body = splice_dialect(tree.body, template, "__paste_here__")

        return tree
