#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Write Python like Lisp: the first item is the operator.

Example::

    with prefix:
        (print, "hello world")
        t = (q, 1, 2, 3)
        (print, t)

``q`` is the quote operator.

Current limitations:

  - no kwarg support
  - no quasiquotes or unquotes
"""

from macropy.core.macros import Macros
from macropy.core.walkers import Walker
from macropy.core.quotes import macros, q, ast_literal

from ast import Tuple, Name

macros = Macros()

@macros.block
def prefix(tree, **kw):
    @Walker
    def transform(tree, *, in_quote, set_ctx, **kw):
        if in_quote or type(tree) is not Tuple:
            return tree
        first, *rest = tree.elts
        if type(first) is Name and first.id == "q":
            set_ctx(in_quote=True)
            return q[(ast_literal[rest],)]
        # (f, a1, ..., an) --> f(a1, ..., an)
        return q[ast_literal[first](ast_literal[rest])]
    return transform.recurse(tree, in_quote=False)
