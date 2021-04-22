# -*- coding: utf-8 -*-
"""Automatic currying. Transforms both function definitions and calls."""

from ast import Call, Lambda, FunctionDef, AsyncFunctionDef

from mcpyrate.quotes import macros, q, a, h  # noqa: F401

from mcpyrate.walkers import ASTTransformer

from .util import (suggest_decorator_index, isx, make_isxpred, has_curry,
                   sort_lambda_decorators)

# CAUTION: unpythonic.syntax.lambdatools.namedlambda depends on the exact names
# "curryf" and "currycall" to detect an auto-curried expression with a final lambda.
from ..fun import curry as curryf, _currycall as currycall

_iscurry = make_isxpred("curry")

def curry(block_body):
    class AutoCurryTransformer(ASTTransformer):
        def transform(self, tree):
            hascurry = self.state.hascurry
            if type(tree) is Call and not isx(tree.func, "AutorefMarker"):
                if has_curry(tree):  # detect decorated lambda with manual curry
                    # the lambda inside the curry(...) is the next Lambda node we will descend into.
                    self.generic_withstate(tree, hascurry=True)
                if not isx(tree.func, _iscurry):
                    tree.args = [tree.func] + tree.args
                    tree.func = q[h[currycall]]
            elif type(tree) in (FunctionDef, AsyncFunctionDef):
                if not any(isx(item, _iscurry) for item in tree.decorator_list):  # no manual curry already
                    k = suggest_decorator_index("curry", tree.decorator_list)
                    if k is not None:
                        tree.decorator_list.insert(k, q[h[curryf]])
                    else:  # couldn't determine insert position; just plonk it at the end and hope for the best
                        tree.decorator_list.append(q[h[curryf]])
            elif type(tree) is Lambda:
                if not hascurry:
                    tree = q[h[curryf](a[tree])]  # plonk it as innermost, we'll sort them later
                    # don't recurse on the lambda we just moved, but recurse inside it.
                    self.withstate(tree.args[0].body, hascurry=False)
                    tree.args[0].body = self.visit(tree.args[0].body)
                    return tree
            return self.generic_visit(tree)
    newbody = AutoCurryTransformer(hascurry=False).visit(block_body)
    return sort_lambda_decorators(newbody)
