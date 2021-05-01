# -*- coding: utf-8 -*-
"""Anaphoric if."""

__all__ = ["aif", "it",
           "cond"]

from ast import Tuple

from mcpyrate.quotes import macros, q, a  # noqa: F811, F401

from .letdo import implicit_do, _let

from ..dynassign import dyn

# --------------------------------------------------------------------------------

def aif(tree, *, syntax, expander, **kw):
    """[syntax, expr] Anaphoric if.

    Usage::

        aif[test, then, otherwise]

        aif[[pre, ..., test],
            [post_true, ..., then],        # "then" branch
            [post_false, ..., otherwise]]  # "otherwise" branch

    Inside the ``then`` and ``otherwise`` branches, the magic identifier ``it``
    (which is always named literally ``it``) refers to the value of ``test``.

    This expands into a ``let`` and an expression-form ``if``.

    Each part may consist of multiple expressions by using brackets around it;
    those brackets create a `do` environment (see `unpythonic.syntax.do`).

    To represent a single expression that is a literal list, use extra
    brackets: ``[[1, 2, 3]]``.
    """
    if syntax != "expr":
        raise SyntaxError("aif is an expr macro only")

    # Expand outside-in, but the implicit do[] needs the expander.
    with dyn.let(_macro_expander=expander):
        return _aif(tree)

def _aif(tree):
    test, then, otherwise = [implicit_do(x) for x in tree.elts]
    bindings = [q[(it, a[test])]]
    body = q[a[then] if it else a[otherwise]]
    # TODO: we should use a hygienically captured macro here.
    return _let(bindings, body)

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

# --------------------------------------------------------------------------------

def cond(tree, *, syntax, expander, **kw):
    """[syntax, expr] Lispy cond; like "a if p else b", but has "elif".

    Usage::

        cond[test1, then1,
             test2, then2,
             ...
             otherwise]

        cond[[pre1, ..., test1], [post1, ..., then1],
             [pre2, ..., test2], [post2, ..., then2],
             ...
             [postn, ..., otherwise]]

    This allows human-readable multi-branch conditionals in an expression position.

    Each part may consist of multiple expressions by using brackets around it;
    those brackets create a `do` environment (see `unpythonic.syntax.do`).

    To represent a single expression that is a literal list, use extra
    brackets: ``[[1, 2, 3]]``.
    """
    if syntax != "expr":
        raise SyntaxError("cond is an expr macro only")

    # Expand outside-in, but the implicit do[] needs the expander.
    with dyn.let(_macro_expander=expander):
        return _cond(tree)

def _cond(tree):
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
