# -*- coding: utf-8 -*-
"""Lispython: The love child of Python and Scheme.

Powered by `mcpyrate` and `unpythonic`.
"""

__all__ = ["Lispython", "Lispy"]

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
                                           multilambda, quicklambda, namedlambda, fn,
                                           where,
                                           let, letseq, letrec,
                                           dlet, dletseq, dletrec,
                                           blet, bletseq, bletrec,
                                           local, delete, do, do0,
                                           let_syntax, abbrev, block, expr,
                                           cond)
            from unpythonic import cons, car, cdr, ll, llist, nil, prod, dyn, Values  # noqa: F401, F811
            with autoreturn, quicklambda, multilambda, namedlambda, tco:
                __paste_here__  # noqa: F821, just a splicing marker.

        # Beginning with 3.6.0, `mcpyrate` makes available the source location info
        # of the dialect-import that imported this dialect.
        if hasattr(self, "lineno"):  # mcpyrate 3.6.0+
            tree.body = splice_dialect(tree.body, template, "__paste_here__",
                                       lineno=self.lineno, col_offset=self.col_offset)
        else:
            tree.body = splice_dialect(tree.body, template, "__paste_here__")

        return tree


class Lispy(Dialect):
    """**Pythonistas rejoice!**

    O language like Lisp, like Python!
    Semantic changes sensibly carry,
    Python's primary virtue vindicate.
    Ire me not with implicit imports,
    Let my IDE label mistakes.
    """

    def transform_ast(self, tree):  # tree is an ast.Module
        with q as template:
            __lang__ = "Lispy"  # noqa: F841, just provide it to user code.
            from unpythonic.syntax import (macros, tco, autoreturn,  # noqa: F401, F811
                                           multilambda, quicklambda, namedlambda)
            # The important point is none of these expect the user code to look like
            # anything but regular Python, so IDEs won't yell about undefined names;
            # just the semantics are slightly different.
            #
            # Even if the user code uses `fn[]` (to make `quicklambda` actually do anything),
            # that macro must be explicitly imported. It works, because `splice_dialect`
            # hoists macro-imports from the top level of the user code into the top level
            # of the template.
            with autoreturn, quicklambda, multilambda, namedlambda, tco:
                __paste_here__  # noqa: F821, just a splicing marker.

        # Beginning with 3.6.0, `mcpyrate` makes available the source location info
        # of the dialect-import that imported this dialect.
        if hasattr(self, "lineno"):  # mcpyrate 3.6.0+
            tree.body = splice_dialect(tree.body, template, "__paste_here__",
                                       lineno=self.lineno, col_offset=self.col_offset)
        else:
            tree.body = splice_dialect(tree.body, template, "__paste_here__")

        return tree
