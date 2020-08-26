# -*- coding: utf-8 -*-
"""Anaphoric if."""

from ast import Tuple

from macropy.core.quotes import macros, q, ast_literal
from macropy.core.hquotes import macros, hq  # noqa: F811, F401

from .letdo import implicit_do, let

# TODO: currently no "syntax-parameterize" (see Racket) in MacroPy. Would be
# convenient to create a macro that expands to an error by default, and then
# override it inside an aif.
#
# We could just leave "it" undefined by default, but IDEs are happier if the
# name exists, and this also gives us a chance to provide a docstring.
class it:
    """[syntax] The result of the test in an aif.

    Only meaningful inside the ``then`` and ``otherwise`` branches of an aif.
    """
    def __repr__(self):  # pragma: no cover, we have a repr just in case one of these ends up somewhere at runtime.
        return "<aif it>"
it = it()

def aif(tree):
    test, then, otherwise = [implicit_do(x) for x in tree.elts]
    bindings = [q[(it, ast_literal[test])]]
    body = q[ast_literal[then] if it else ast_literal[otherwise]]
    return let(bindings, body)

def cond(tree):
    if type(tree) is not Tuple:
        assert False, "Expected cond[test1, then1, test2, then2, ..., otherwise]"  # pragma: no cover
    def build(elts):
        if len(elts) == 1:  # final "otherwise" branch
            return implicit_do(elts[0])
        if not elts:
            assert False, "Expected cond[test1, then1, test2, then2, ..., otherwise]"  # pragma: no cover
        test, then, *more = elts
        test = implicit_do(test)
        then = implicit_do(then)
        return hq[ast_literal[then] if ast_literal[test] else ast_literal[build(more)]]
    return build(tree.elts)
