# -*- coding: utf-8 -*-
"""Anaphoric if."""

from ast import copy_location, Tuple

from macropy.core.quotes import macros, q, ast_literal
from macropy.core.hquotes import macros, hq

from unpythonic.syntax.letdo import implicit_do, let

# TODO: currently no "syntax-parameterize" in MacroPy. Would be convenient to
# create a macro that expands to an error by default, and then override it
# inside an aif.
#
# We could just leave "it" undefined by default, but IDEs are happier if the
# name exists, and this also gives us a chance to provide a docstring.
class it:
    """[syntax] The result of the test in an aif.

    Only meaningful inside the ``then`` and ``otherwise`` branches of an aif.
    """
    def __repr__(self):  # in case one of these ends up somewhere at runtime
        return "<aif it>"
it = it()

def aif(tree, gen_sym):
    test, then, otherwise = [implicit_do(x, gen_sym) for x in tree.elts]
    bindings = [q[(it, ast_literal[test])]]
    body = q[ast_literal[then] if it else ast_literal[otherwise]]
    return let(bindings, body, gen_sym)

def cond(tree, gen_sym):
    if type(tree) is not Tuple:
        assert False, "Expected cond[test1, then1, test2, then2, ..., otherwise]"
    def build(elts):
        if len(elts) == 1:  # final "otherwise" branch
            return implicit_do(elts[0], gen_sym)
        if not elts:
            assert False, "Expected cond[test1, then1, test2, then2, ..., otherwise]"
        test, then, *more = elts
        test = implicit_do(test, gen_sym)
        then = implicit_do(then, gen_sym)
        return hq[ast_literal[then] if ast_literal[test] else ast_literal[build(more)]]
    return build(tree.elts)
