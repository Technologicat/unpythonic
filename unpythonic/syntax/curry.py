# -*- coding: utf-8 -*-
"""Automatic currying. Transforms both function definitions and calls."""

from ast import Call, Lambda, FunctionDef, Name
from .astcompat import AsyncFunctionDef

from macropy.core.quotes import macros, ast_literal
from macropy.core.hquotes import macros, hq  # noqa: F811, F401
from macropy.core.walkers import Walker

from .util import (suggest_decorator_index, isx, make_isxpred, has_curry,
                   sort_lambda_decorators)

# CAUTION: unpythonic.syntax.lambdatools.namedlambda depends on the exact names
# "curryf" and "currycall" to detect an auto-curried expression with a final lambda.
from ..fun import curry as curryf, _currycall as currycall

_iscurry = make_isxpred("curry")

def curry(block_body):
    @Walker
    def transform(tree, *, hascurry, set_ctx, stop, **kw):
        if type(tree) is Call and not (type(tree.func) is Name and tree.func.id == "AutorefMarker"):
            if has_curry(tree):  # detect decorated lambda with manual curry
                set_ctx(hascurry=True)  # the lambda inside the curry(...) is the next Lambda node we will descend into.
            if not isx(tree.func, _iscurry):
                tree.args = [tree.func] + tree.args
                tree.func = hq[currycall]
        elif type(tree) in (FunctionDef, AsyncFunctionDef):
            if not any(isx(item, _iscurry) for item in tree.decorator_list):  # no manual curry already
                k = suggest_decorator_index("curry", tree.decorator_list)
                if k is not None:
                    tree.decorator_list.insert(k, hq[curryf])
                else:  # couldn't determine insert position; just plonk it at the end and hope for the best
                    tree.decorator_list.append(hq[curryf])
        elif type(tree) is Lambda:
            if not hascurry:
                tree = hq[curryf(ast_literal[tree])]  # plonk it as innermost, we'll sort them later
                # don't recurse on the lambda we just moved, but recurse inside it.
                stop()
                tree.args[0].body = transform.recurse(tree.args[0].body, hascurry=False)
        return tree
    newbody = transform.recurse(block_body, hascurry=False)
    return sort_lambda_decorators(newbody)
