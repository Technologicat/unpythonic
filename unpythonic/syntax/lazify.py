# -*- coding: utf-8 -*-
"""Automatic lazy evaluation of function arguments."""

from functools import wraps

from ast import Lambda, FunctionDef, Call, Name, Starred, keyword
from .astcompat import AsyncFunctionDef

from macropy.core.quotes import macros, q, u, ast_literal, name
from macropy.core.hquotes import macros, hq
from macropy.core.walkers import Walker

from macropy.quick_lambda import macros, lazy
from macropy.quick_lambda import Lazy

from .util import suggest_decorator_index, sort_lambda_decorators, detect_lambda
from .letdo import let
from .letdoutil import islet, isdo
from ..regutil import register_decorator
from ..it import uniqify
from ..dynassign import dyn

@register_decorator(priority=95)
def mark_lazy(f):
    """Internal helper decorator for the lazify macro.

    Marks a function as lazy, and adds a wrapper that allows it to be called
    with strict (already evaluated) arguments, which occurs if called from
    outside any ``with lazify`` block.
    """
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
    def transform(tree, *, formals, varargs, stop, **kw):
        if type(tree) in (FunctionDef, AsyncFunctionDef, Lambda):
            if type(tree) is Lambda and id(tree) not in userlambdas:
                pass  # ignore macro-introduced lambdas
            else:
                stop()

                # previous scope
                tree.decorator_list = transform.recurse(tree.decorator_list, varargs=varargs, formals=formals)

                a = tree.args
                newformals = formals.copy()
                for s in (a.args, a.kwonlyargs, [a.kwarg]):
                    newformals += [x.arg for x in s if x is not None]
                newformals = list(uniqify(newformals))

                if a.vararg is not None:
                    newvarargs = varargs.copy()
                    newvarargs.append(a.vararg.arg)
                    newvarargs = list(uniqify(newvarargs))
                else:
                    newvarargs = varargs

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

                # the inner scope
                tree.body = transform.recurse(tree.body, varargs=newvarargs, formals=newformals)

        elif type(tree) is Name:
            stop()  # must not recurse even when a Name changes into a Call.
            if tree.id in formals:
                tree = q[ast_literal[tree]()]  # force the promise
            elif tree.id in varargs:
                # evaluate each element in *args
                tree = q[tuple(x() for x in ast_literal[tree])]

        elif type(tree) is Call:
            if isdo(tree) or islet(tree):
                pass  # known to be strict, no need to introduce lazy[]
            else:
                stop()
                gen_sym = dyn.gen_sym

                # Delay evaluation of the args, but only if the call target is
                # a lazy function (i.e. expects delayed args).
                #
                # We need this runtime detection to support calls to strict
                # (regular Python) functions from within the "with lazify" block.

                # Evaluate the operator (.func of the Call node) just once.
                thefunc = tree.func
                thefunc = transform.recurse(thefunc, varargs=varargs, formals=formals)  # recurse into the operator
                fname = gen_sym("f")
                letbindings = [q[(name[fname], ast_literal[thefunc])]]

                # Delay the args (first, recurse into them).
                anames = []
                for x in tree.args:
                    if type(x) is Starred:  # Python 3.5+
                        x.value = transform.recurse(x.value, varargs=varargs, formals=formals)
                        x.value = hq[lazy[ast_literal[x.value]]]
                    else:
                        x = transform.recurse(x, varargs=varargs, formals=formals)
                        x = hq[lazy[ast_literal[x]]]
                    localname = gen_sym("a")
                    letbindings.append(q[(name[localname], ast_literal[x])])
                    anames.append(localname)

                kwmap = []
                for x in tree.keywords:
                    x.value = transform.recurse(x.value, varargs=varargs, formals=formals)
                    x.value = hq[lazy[ast_literal[x.value]]]
                    localname = gen_sym("kw")
                    letbindings.append(q[(name[localname], ast_literal[x.value])])
                    kwmap.append((x.arg, localname))

                # Construct the calls.
                ln, co = tree.lineno, tree.col_offset
                lazycall = Call(func=q[name[fname]],
                                args=[q[name[x]] for x in anames],
                                keywords=[keyword(arg=k, value=q[name[x]]) for k, x in kwmap],
                                lineno=ln, col_offset=co)
                strictcall = Call(func=q[name[fname]],
                                  args=[q[name[x]()] for x in anames],
                                  keywords=[keyword(arg=k, value=q[name[x]()]) for k, x in kwmap],
                                  lineno=ln, col_offset=co)

                # Python 3.4
                if hasattr(tree, "starargs"):
                    if tree.starargs is not None:
                        saname = gen_sym("sa")
                        tree.starargs = transform.recurse(tree.starargs, varargs=varargs, formals=formals)
                        letbindings.append(q[(name[saname], ast_literal[tree.starargs])])
                        lazycall.starargs = q[name[saname]]
                        strictcall.starargs = q[name[saname]()]
                    else:
                        lazycall.starargs = strictcall.starargs = None
                if hasattr(tree, "kwargs"):
                    if tree.kwargs is not None:
                        kwaname = gen_sym("kwa")
                        tree.kwargs = transform.recurse(tree.kwargs, varargs=varargs, formals=formals)
                        letbindings.append(q[(name[kwaname], ast_literal[tree.kwargs])])
                        lazycall.kwargs = q[name[kwaname]]
                        strictcall.kwargs = q[name[kwaname]()]
                    else:
                        lazycall.kwargs = strictcall.kwargs = None

                letbody = q[ast_literal[lazycall] if hasattr(name[fname], "_lazy") else ast_literal[strictcall]]
                tree = let(letbindings, letbody)

        return tree
    newbody = []
    for stmt in body:
        newbody.append(transform.recurse(stmt, varargs=[], formals=[]))
    return newbody
