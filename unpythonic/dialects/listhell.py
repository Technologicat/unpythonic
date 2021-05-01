# -*- coding: utf-8 -*-
"""Listhell: it's not Lisp, it's not Python, it's not Haskell.

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
            from unpythonic.syntax import macros, prefix, autocurry  # noqa: F401, F811
            # auxiliary syntax elements for the macros
            from unpythonic.syntax import q, u, kw  # noqa: F401
            from unpythonic import apply  # noqa: F401
            from unpythonic import composerc as compose  # compose from Right, Currying  # noqa: F401
            with prefix, autocurry:
                __paste_here__  # noqa: F821, just a splicing marker.
        tree.body = splice_dialect(tree.body, template, "__paste_here__")
        return tree
