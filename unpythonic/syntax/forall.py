# -*- coding: utf-8 -*-
"""Nondeterministic evaluation (a tuple comprehension with multi-expr body)."""

from ast import Tuple, Name, arg

from macropy.core.quotes import macros, q, u, ast_literal, name
from macropy.core.hquotes import macros, hq
from macropy.core.walkers import Walker

from unpythonic.syntax.letdo import isenvassign, envassign_name, envassign_value
from unpythonic.amb import monadify
from unpythonic.amb import insist, deny  # for re-export only

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
    if type(exprs) is not Tuple:
        assert False, "forall body: expected a sequence of comma-separated expressions"
    def build(lines, tree):
        if not lines:
            return tree
        line, *rest = lines
        if isenvassign(line):
            k, v = envassign_name(line), envassign_value(line)
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
            @Walker
            def splice(tree, *, stop, **kw):
                if type(tree) is Name and tree.id == "_here_":
                    stop()
                    return body
                return tree
            newtree = splice.recurse(tree)
        else:
            newtree = body
        return build(rest, newtree)
    return hq[tuple(ast_literal[build(exprs.elts, None)])]
