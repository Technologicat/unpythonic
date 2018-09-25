#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Lispy cond for Python (no implicit begin, though).

This allows human-readable multi-branch conditionals in a lambda.

Usage::

    cond[test1, then1,
         test2, then2,
         ...
         otherwise]
"""

from macropy.core.macros import Macros
from macropy.core.quotes import macros, ast_literal
from macropy.core.hquotes import macros, hq

#from macropy.core import unparse
#from astpp import dump

macros = Macros()

@macros.expr
def cond(tree, **kw):
    return _cond(tree.elts)

def _cond(elts):
    if len(elts) == 1:  # final "otherwise" branch
        return elts[0]
    if not elts:
        assert False, "Expected cond[test1, then1, test2, then2, ..., otherwise]"
    test, then, *more = elts
    return hq[ast_literal[then] if ast_literal[test] else ast_literal[_cond(more)]]
