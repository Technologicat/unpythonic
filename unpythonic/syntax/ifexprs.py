# -*- coding: utf-8 -*-
"""Anaphoric if."""

from ast import Tuple

from mcpyrate.quotes import macros, q, a  # noqa: F811, F401

from .letdo import implicit_do, let

# TODO: `mcpyrate` has a rudimentary capability like Racket's "syntax-parameterize".
# TODO: Make `it` a name macro that errors out unless it appears inside an `aif`.
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
    bindings = [q[(it, a[test])]]
    body = q[a[then] if it else a[otherwise]]
    return let(bindings, body)

def cond(tree):
    if type(tree) is not Tuple:
        raise SyntaxError("Expected cond[test1, then1, test2, then2, ..., otherwise]")  # pragma: no cover
    def build(elts):
        if len(elts) == 1:  # final "otherwise" branch
            return implicit_do(elts[0])
        if not elts:
            raise SyntaxError("Expected cond[test1, then1, test2, then2, ..., otherwise]")  # pragma: no cover
        test, then, *more = elts
        test = implicit_do(test)
        then = implicit_do(then)
        return q[a[then] if a[test] else a[build(more)]]
    return build(tree.elts)
