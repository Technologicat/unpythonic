# -*- coding: utf-8 -*-
"""Nondeterministic evaluation (a tuple comprehension with a multi-expr body)."""

__all__ = ["forall", "insist", "deny"]

from ast import Tuple, arg

from mcpyrate.quotes import macros, q, u, n, a, h  # noqa: F401

from mcpyrate.splicing import splice_expression

from .letdoutil import isenvassign, UnexpandedEnvAssignView
from ..amb import monadify
from ..dynassign import dyn
from ..misc import namelambda

from ..amb import insist, deny  # for re-export only  # noqa: F401

def forall(tree, *, syntax, expander, **kw):
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
    if syntax != "expr":
        raise SyntaxError("forall is an expr macro only")  # pragma: no cover

    # Inside-out macro.
    with dyn.let(_macro_expander=expander):
        return _forall(exprs=tree)

def _forall(exprs):
    if type(exprs) is not Tuple:  # pragma: no cover, let's not test macro expansion errors.
        raise SyntaxError("forall body: expected a sequence of comma-separated expressions")  # pragma: no cover

    # Expand inside-out to easily support lexical scoping.
    exprs = dyn._macro_expander.visit_recursively(exprs)

    itemno = 0
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
        Mv = q[h[monadify](a[v], u[not islast])]
        if not islast:
            lam = q[lambda _: n["_here_"]]
            lam.args.args = [arg(arg=k)]

            nonlocal itemno
            itemno += 1
            label = "item{itemno}" if k == "_ignored" else k
            namedlam = q[h[namelambda](u[f"forall_{label}"])(a[lam])]

            body = q[a[Mv] >> a[namedlam]]  # monadic bind: >>
        else:
            body = Mv
        if tree:
            newtree = splice_expression(body, tree, "_here_")
        else:
            newtree = body
        return build(rest, newtree)
    return q[h[tuple](a[build(exprs.elts, None)])]
