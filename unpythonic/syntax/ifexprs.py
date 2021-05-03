# -*- coding: utf-8 -*-
"""Anaphoric if."""

__all__ = ["aif", "it",
           "cond"]

from ast import Tuple

from mcpyrate.quotes import macros, q, n, a, h  # noqa: F811, F401
from .letdo import macros, let  # noqa: F811, F401

from mcpyrate import namemacro
from mcpyrate.expander import MacroExpander
from mcpyrate.utils import extract_bindings, NestingLevelTracker

from .letdo import _implicit_do

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

    # Detect the name(s) of `it` at the use site (this accounts for as-imports)
    # TODO: We don't know which binding this particular use site uses.
    # TODO: For now, we hack this by making `it` always rename itself to literal `it`.
    macro_bindings = extract_bindings(expander.bindings, it)
    if not macro_bindings:
        raise SyntaxError("The use site of `aif` must macro-import `it`, too.")

    # Expand outside-in, but the implicit do[] needs the expander.
    with dyn.let(_macro_expander=expander):
        return _aif(tree, macro_bindings)

_aif_level = NestingLevelTracker()

def _aif(tree, bindings_of_it):
    # expand any `it` inside the `aif` (thus confirming those uses are valid)
    def expand_it(tree):
        return MacroExpander(bindings_of_it, dyn._macro_expander.filename).visit(tree)

    # careful here: `it` is only valid in the `then` and `otherwise` parts.
    test, then, otherwise = tree.elts
    test = _implicit_do(test)
    with _aif_level.changed_by(+1):
        # TODO: We don't know which binding this particular use site uses.
        # TODO: For now, we hack this by making `it` always rename itself to literal `it`.
        name_of_it = list(bindings_of_it.keys())[0]
        expanded_it = expand_it(q[n[name_of_it]])

        then = _implicit_do(expand_it(then))
        otherwise = _implicit_do(expand_it(otherwise))

    let_bindings = q[(a[expanded_it], a[test])]
    let_body = q[a[then] if a[expanded_it] else a[otherwise]]
    # We use a hygienic macro reference to `let[]` in the output,
    # so that the expander can expand it later.
    return q[h[let][a[let_bindings]][a[let_body]]]

@namemacro
def it(tree, *, syntax, **kw):
    """[syntax, name] The `it` of an anaphoric if.

    Inside an `aif` body, evaluates to the value of the test result.
    Anywhere else, is considered a syntax error.

    **CAUTION**: Currently cannot be as-imported; must be imported
    without renaming.
    """
    if syntax != "name":
        raise SyntaxError("`it` is a name macro only")
    if _aif_level.value < 1:
        raise SyntaxError("`it` may only appear in the 'then' and 'otherwise' parts of an `aif[...]`")
    return q[it]  # always rename to literal `it`

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
            return _implicit_do(elts[0])
        if not elts:
            raise SyntaxError("Expected cond[test1, then1, test2, then2, ..., otherwise]")  # pragma: no cover
        test, then, *more = elts
        test = _implicit_do(test)
        then = _implicit_do(then)
        return q[a[then] if a[test] else a[build(more)]]
    return build(tree.elts)
