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

# TODO: figure out later what we need to change to use the same let implementation
# as elsewhere. Currently complains that "it" is not defined at the call site,
# although the "let" here should pick it up and transform to "e.it" - shouldn't
# matter that part of the code in the body comes from the call site.
# Maybe something to do with macro expansion order? Or maybe need to quasiquote
# the construction here differently? Or use let as a syntax transformer function,
# instead of invoking it as a macro?
from letm import macros, simple_let

macros = Macros()

@macros.expr
def aif(tree, **kw):
    test, then, otherwise = tree.elts
    return hq[simple_let((it, ast_literal[test]),)[
                         ast_literal[then] if it else ast_literal[otherwise]]]
