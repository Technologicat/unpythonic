# -*- coding: utf-8 -*-
"""Nondeterministic evaluation (a tuple comprehension with a multi-expr body)."""

from ast import Tuple, arg

from macropy.core.quotes import macros, q, u, ast_literal, name
from macropy.core.hquotes import macros, hq  # noqa: F811, F401

from .util import splice
from .letdoutil import isenvassign, UnexpandedEnvAssignView
from ..amb import monadify
from ..amb import insist, deny  # for re-export only  # noqa: F401

def forall(exprs):
    """[syntax, expr] Nondeterministic evaluation.

    Fully based on AST transformation, with real lexical variables.
    Like Haskell's do-notation, but here specialized for the List monad.

    Example::

        # pythagorean triples
        pt = forall[z << range(1, 21),   # hypotenuse
                    x << range(1, z+1),  # shorter leg
                    y << range(x, z+1),  # longer leg
                    insist(x*x + y*y == z*z),
                    (x, y, z)]
        assert tuple(sorted(pt)) == ((3, 4, 5), (5, 12, 13), (6, 8, 10),
                                     (8, 15, 17), (9, 12, 15), (12, 16, 20))
    """
    if type(exprs) is not Tuple:  # pragma: no cover, let's not test macro expansion errors.
        assert False, "forall body: expected a sequence of comma-separated expressions"
    def build(lines, tree):
        if not lines:
            return tree
        line, *rest = lines
        if isenvassign(line):  # no need for "let"; we just borrow a very small part of its syntax machinery.
            view = UnexpandedEnvAssignView(line)
            k, v = view.name, view.value
        else:
            k, v = "_ignored", line
        islast = not rest
        # don't unpack on last line to allow easily returning a tuple as a result item
        Mv = hq[monadify(ast_literal[v], u[not islast])]
        if not islast:
            body = q[ast_literal[Mv] >> (lambda: name["_here_"])]  # monadic bind: >>
            body.right.args.args = [arg(arg=k)]
        else:
            body = Mv
        if tree:
            newtree = splice(tree, body, "_here_")
        else:
            newtree = body
        return build(rest, newtree)
    return hq[tuple(ast_literal[build(exprs.elts, None)])]
