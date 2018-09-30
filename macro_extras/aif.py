#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Anaphoric if for Python.

Usage::

    aif[test, then, otherwise]

Magic identifier ``it`` refers to the test result.
"""

from macropy.core.macros import Macros
from macropy.core.quotes import macros, ast_literal, q
from macropy.core.hquotes import macros, hq

# TODO: figure out later what we need to change to use the same let implementation
# as elsewhere. Currently complains that "it" is not defined at the call site,
# although the "let" here should pick it up and transform to "e.it" - shouldn't
# matter that part of the code in the body comes from the call site.
# Maybe something to do with macro expansion order? Or maybe need to quasiquote
# the construction here differently? Or use let as a syntax transformer function,
# instead of invoking it as a macro?
from letm import macros, simple_let
#from letm import _let

macros = Macros()

class it:
    """[syntax] The result of the test in an aif.

    Only meaningful inside the then and otherwise branches of an aif."""
    def __repr__(self):  # in case one of these ends up somewhere at runtime
        return "<aif it>"
it = it()

@macros.expr
def aif(tree, gen_sym, **kw):
    test, then, otherwise = tree.elts
    return hq[simple_let((it, ast_literal[test]),)[
                         ast_literal[then] if it else ast_literal[otherwise]]]
#    # this works for using the same let as elsewhere.
#    ltree = q[ast_literal[then] if it else ast_literal[otherwise]]
#    bindings = [q[(it, ast_literal[test])]]
#    return _let(ltree, bindings, "let", gen_sym)
