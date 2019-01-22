# -*- coding: utf-8 -*-
"""Automatic lazy evaluation of function arguments."""

from functools import wraps
from copy import deepcopy

from ast import Lambda, FunctionDef, Call, Name, Starred
from .astcompat import AsyncFunctionDef

from macropy.core.quotes import macros, q, ast_literal, name
from macropy.core.hquotes import macros, hq
from macropy.core.walkers import Walker

from macropy.quick_lambda import macros, lazy
from macropy.quick_lambda import Lazy

from .util import suggest_decorator_index, sort_lambda_decorators, detect_lambda
from .letdo import let
from .letdoutil import islet, isdo
from ..regutil import register_decorator
from ..it import uniqify

from macropy.core import unparse

@register_decorator(priority=95)
def mark_lazy(f):
    """Internal helper decorator for the lazify macro."""
    @wraps(f)
    def lazified(*args, **kwargs):
        # support calls coming in from outside of the "with lazify" block,
        # by wrapping already evaluated args.
        newargs = [(x if isinstance(x, Lazy) else lazy[x]) for x in args]
        newkwas = {k: (v if isinstance(v, Lazy) else lazy[v]) for k, v in kwargs.items()}
        return f(*newargs, **newkwas)
    lazified._lazy = True  # stash for call logic
    return lazified

# TODO: support curry, call, callwith (may need changes to their implementations, too)

def lazify(body):
    # first pass, outside-in
    userlambdas = detect_lambda.collect(body)
    body = yield body

    # second pass, inside-out
    @Walker
    def transform(tree, *, formals, stop, **kw):
        if type(tree) in (FunctionDef, AsyncFunctionDef, Lambda):
            if type(tree) is Lambda and id(tree) not in userlambdas:
                pass  # ignore macro-introduced lambdas
            else:
                stop()
                tree.decorator_list = transform.recurse(tree.decorator_list, formals=formals)  # previous scope
                a = tree.args
                newformals = formals.copy()
                for s in (a.args, a.kwonlyargs, [a.vararg], [a.kwarg]):
                    newformals += [x.arg for x in s if x is not None]
                newformals = list(uniqify(newformals))

                # mark this definition as lazy, and insert the interface wrapper
                if type(tree) is Lambda:
                    tree = hq[mark_lazy(ast_literal[tree])]
                    tree = sort_lambda_decorators(tree)
                else:
                    k = suggest_decorator_index("mark_lazy", tree.decorator_list)
                    if k is not None:
                        tree.decorator_list.insert(k, hq[mark_lazy])
                    else:
                        tree.decorator_list.append(hq[mark_lazy])

                tree.body = transform.recurse(tree.body, formals=newformals)  # the inner scope

        elif type(tree) is Name:
            if tree.id in formals:
                stop()  # Name changes into a Call, must not recurse there.
                tree = q[ast_literal[tree]()]  # force the promise

        elif type(tree) is Call:
            if isdo(tree) or islet(tree):
                pass  # known to be strict, no need to introduce lazy[]
            else:
                stop()

                # Delay evaluation of the args, but only if the call target is
                # a lazy function (i.e. expects delayed args).
                #
                # We need this runtime detection to support calls to strict
                # (regular Python) functions from within the "with lazify" block.
                #
                # Also, evaluate the operator (.func of the Call node) just once.
                # TODO: mention the arg ASTs just once, and recurse into them
                # TODO: recurse into the operator
                thefunc = tree.func
                letbindings = [q[(name["_thefunc"], ast_literal[thefunc])]]
                tree.func = q[name["_thefunc"]]
                lazytree = deepcopy(tree)

                newargs = []
                for x in lazytree.args:
                    if type(x) is Starred:  # Python 3.5+
                        x.value = hq[lazy[ast_literal[x.value]]]
                    else:
                        x = hq[lazy[ast_literal[x]]]
                    newargs.append(x)
                lazytree.args = newargs

                newkeywords = []
                for x in lazytree.keywords:
                    x.value = hq[lazy[ast_literal[x.value]]]
                    newkeywords.append(x)
                lazytree.keywords = newkeywords

                # Python 3.4
                if hasattr(lazytree, "starargs") and lazytree.starargs is not None:
                    lazytree.starargs = hq[lazy[ast_literal[lazytree.starargs]]]
                if hasattr(lazytree, "kwargs") and lazytree.kwargs is not None:
                    lazytree.kwargs = hq[lazy[ast_literal[lazytree.kwargs]]]

                letbody = q[ast_literal[lazytree] if hasattr(name["_thefunc"], "_lazy") else ast_literal[tree]]
                tree = let(letbindings, letbody)

        return tree
    newbody = []
    for stmt in body:
        newbody.append(transform.recurse(stmt, formals=[]))
    return newbody
