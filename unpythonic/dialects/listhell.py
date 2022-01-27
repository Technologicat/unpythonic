# -*- coding: utf-8 -*-
"""Listhell: It's not Lisp, it's not Python, it's not Haskell.

Powered by `mcpyrate` and `unpythonic`.
"""

__all__ = ["Listhell"]

__version__ = '2.0.0'

from mcpyrate.quotes import macros, q  # noqa: F401

from mcpyrate.dialects import Dialect
from mcpyrate.splicing import splice_dialect

class Listhell(Dialect):
    def transform_ast(self, tree):  # tree is an ast.Module
        with q as template:
            __lang__ = "Listhell"  # noqa: F841, just provide it to user code.
            from unpythonic.syntax import macros, prefix, q, u, kw, autocurry  # noqa: F401, F811
            # Auxiliary syntax elements for the macros
            from unpythonic import apply  # noqa: F401
            from unpythonic import composerc as compose  # compose from Right, Currying  # noqa: F401
            with prefix, autocurry:
                __paste_here__  # noqa: F821, just a splicing marker.

        # Beginning with 3.6.0, `mcpyrate` makes available the source location info
        # of the dialect-import that imported this dialect.
        if hasattr(self, "lineno"):  # mcpyrate 3.6.0+
            tree.body = splice_dialect(tree.body, template, "__paste_here__",
                                       lineno=self.lineno, col_offset=self.col_offset)
        else:
            tree.body = splice_dialect(tree.body, template, "__paste_here__")

        return tree
