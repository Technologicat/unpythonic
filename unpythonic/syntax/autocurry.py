# -*- coding: utf-8 -*-
"""Automatic currying. Transforms both function definitions and calls."""

__all__ = ["autocurry"]

from ast import Call, Lambda, FunctionDef, AsyncFunctionDef

from mcpyrate.quotes import macros, q, a, h  # noqa: F401

from mcpyrate.quotes import is_captured_value
from mcpyrate.walkers import ASTTransformer

from .util import (suggest_decorator_index, isx, has_curry, sort_lambda_decorators)

# CAUTION: unpythonic.syntax.lambdatools.namedlambda depends on the exact names
# "curryf" and "currycall" to detect an auto-curried expression with a final lambda.
from ..fun import curry as curryf, _currycall as currycall


def autocurry(tree, *, syntax, expander, **kw):  # technically a list of trees, the body of the with block
    """[syntax, block] Automatic currying.

    Usage::

        from unpythonic.syntax import macros, autocurry

        with autocurry:
            ...

    All **function calls** and **function definitions** (``def``, ``lambda``)
    *lexically* inside the ``with autocurry`` block are automatically curried.

    **CAUTION**: Some builtins are uninspectable or may report their arities
    incorrectly; in those cases, ``curry`` may fail, occasionally in mysterious
    ways.

    The function ``unpythonic.arity.arities``, which ``unpythonic.fun.curry``
    internally uses, has a workaround for the inspectability problems of all
    builtins in the top-level namespace (as of Python 3.7), but e.g. methods
    of builtin types are not handled.

    Lexically inside a ``with autocurry`` block, the auto-curried function calls
    will skip the curry if the function is uninspectable, instead of raising
    ``TypeError`` as usual.

    Example::

        from unpythonic.syntax import macros, autocurry
        from unpythonic import foldr, composerc as compose, cons, nil, ll

        with autocurry:
            def add3(a, b, c):
                return a + b + c
            assert add3(1)(2)(3) == 6
            assert add3(1, 2)(3) == 6
            assert add3(1)(2, 3) == 6
            assert add3(1, 2, 3) == 6

            mymap = lambda f: foldr(compose(cons, f), nil)
            double = lambda x: 2 * x
            assert mymap(double, ll(1, 2, 3)) == ll(2, 4, 6)

        # The definition was auto-curried, so this works here too.
        assert add3(1)(2)(3) == 6
    """
    if syntax != "block":
        raise SyntaxError("autocurry is a block macro only")
    if syntax == "block" and kw['optional_vars'] is not None:
        raise SyntaxError("autocurry does not take an asname")

    tree = expander.visit(tree)

    return _autocurry(block_body=tree)


_iscurry = lambda name: name in ("curry", "currycall")

def _autocurry(block_body):
    class AutoCurryTransformer(ASTTransformer):
        def transform(self, tree):
            # Ignore hygienically captured values, and don't recurse in them.
            # In `mcpyrate`, they are represented by Call nodes that match
            # `mcpyrate.quotes.is_captured_value`.
            if is_captured_value(tree):
                return tree

            hascurry = self.state.hascurry
            if type(tree) is Call and not isx(tree.func, "ExpandedAutorefMarker"):
                if has_curry(tree):  # detect decorated lambda with manual curry
                    # the lambda inside the curry(...) is the next Lambda node we will descend into.
                    hascurry = True
                if not isx(tree.func, _iscurry):
                    tree.args = [tree.func] + tree.args
                    tree.func = q[h[currycall]]
                if hascurry:  # this must be done after the edit because the edit changes the children
                    self.generic_withstate(tree, hascurry=True)

            elif type(tree) in (FunctionDef, AsyncFunctionDef):
                if not any(isx(item, _iscurry) for item in tree.decorator_list):  # no manual curry already
                    k = suggest_decorator_index("curry", tree.decorator_list)
                    if k is not None:
                        tree.decorator_list.insert(k, q[h[curryf]])
                    else:  # couldn't determine insert position; just plonk it at the end and hope for the best
                        tree.decorator_list.append(q[h[curryf]])

            elif type(tree) is Lambda:
                if not hascurry:
                    thelambda = tree
                    tree = q[h[curryf](a[thelambda])]  # plonk it as innermost, we'll sort them later
                    # don't recurse on the lambda we just moved, but recurse inside it.
                    self.withstate(thelambda.body, hascurry=False)
                    thelambda.body = self.visit(thelambda.body)
                    return tree

            return self.generic_visit(tree)

    newbody = AutoCurryTransformer(hascurry=False).visit(block_body)
    return sort_lambda_decorators(newbody)
