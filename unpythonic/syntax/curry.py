# -*- coding: utf-8 -*-
"""Automatic currying. Transforms both function definitions and calls."""

from ast import Call, Lambda, FunctionDef, With, withitem
from .astcompat import AsyncFunctionDef

from macropy.core.quotes import macros, ast_literal
from macropy.core.hquotes import macros, hq
from macropy.core.walkers import Walker

from .util import suggest_decorator_index

from ..dynassign import dyn

# CAUTION: unpythonic.syntax.lambdatools.namedlambda depends on the exact names
# "curryf" and "currycall" to detect an auto-curried expression with a final lambda.
from ..fun import curry as curryf, _currycall as currycall

def curry(block_body):
    @Walker
    def transform_call(tree, *, stop, **kw):  # technically a node containing the current subtree
        if type(tree) is Call:
            tree.args = [tree.func] + tree.args
            tree.func = hq[currycall]
        elif type(tree) in (FunctionDef, AsyncFunctionDef):
            # TODO: detect there's no curry already.
            k = suggest_decorator_index("curry", tree.decorator_list)
            if k is not None:
                tree.decorator_list.insert(k, hq[curryf])
            else:  # couldn't determine insert position; just plonk it at the end and hope for the best
                tree.decorator_list.append(hq[curryf])
        elif type(tree) is Lambda:
            # This inserts curry() as the innermost "decorator", and the curry
            # macro is meant to run last (after e.g. tco), so we're fine.
            # TODO: detect there's no curry already.
            tree = hq[curryf(ast_literal[tree])]
            # don't recurse on the lambda we just moved, but recurse inside it.
            stop()
            tree.args[0].body = transform_call.recurse(tree.args[0].body)
        return tree
    block_body = transform_call.recurse(block_body)
    # Wrap the body in "with dyn.let(_curry_allow_uninspectable=True):"
    # to avoid crash with uninspectable builtins
    item = hq[dyn.let(_curry_allow_uninspectable=True)]
    wrapped = With(items=[withitem(context_expr=item, optional_vars=None)],
                   body=block_body)
    return [wrapped]  # block macro: got a list, must return a list.
