#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Anaphoric if for Python.

Usage::

    aif[test, then, otherwise]

Magic identifier ``it`` refers to the test result.
"""

from macropy.core.macros import Macros
from macropy.core.quotes import macros, ast_literal
from macropy.core.hquotes import macros, hq

from letm import macros, let

macros = Macros()

@macros.expr
def aif(tree, **kw):
    test, then, otherwise = tree.elts
    return hq[let((it, ast_literal[test]),)[
                ast_literal[then] if it else ast_literal[otherwise]]]
