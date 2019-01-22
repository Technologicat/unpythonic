# -*- coding: utf-8 -*-
"""Automatic lazy evaluation of function arguments."""

from functools import wraps

from ast import Lambda, FunctionDef, Call, Name, \
                Starred, keyword, List, Tuple, Dict, \
                Subscript, Index, Slice, Load
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

def forcestarargs(x):
    """Internal helper for the lazify macro.

    Forces all items of an ``*args`` object.
    """
    return tuple(elt() for elt in x)

def forcekwargs(x):
    """Internal helper for the lazify macro.

    Forces all items of a ``**kwargs`` object.
    """
    return {k: v() for k, v in x.items()}

def dataseq(x):
    """Internal helper for the lazify macro.

    Counterpart of ``forcestarargs``; makes an already evaluated iterable
    containing data appear as if each item was lazy. (I.e., for each item,
    a call is needed to extract the value.)
    """
    lz = lambda x: lazy[x]  # capture the *value*, not the binding "elt"
    return tuple(lz(elt) for elt in x)

def datadic(x):
    """Internal helper for the lazify macro.

    Counterpart of ``forcekwargs``; makes an already evaluated dictionary
    containing data appear as if each item was lazy. (I.e., for each item,
    a call is needed to extract the value.)
    """
    lz = lambda x: lazy[x]
    return {k: lz(v) for k, v in x.items()}

# TODO: support curry, call, callwith (may need changes to their implementations, too)
# TODO: detect and handle overwrites of formals (new value should be lazified, too)

def lazify(body):
    # first pass, outside-in
    userlambdas = detect_lambda.collect(body)
    body = yield body

    # second pass, inside-out
    @Walker
    def transform(tree, *, formals, varargs, kwargs, stop, **kw):
        def rec(tree):  # boilerplate eliminator for recursion in current scope
            return transform.recurse(tree,
                                     varargs=varargs,
                                     kwargs=kwargs,
                                     formals=formals)

        # transform function definitions
        if type(tree) in (FunctionDef, AsyncFunctionDef, Lambda):
            if type(tree) is Lambda and id(tree) not in userlambdas:
                pass  # ignore macro-introduced lambdas
            else:
                stop()

                # transform decorators using previous scope
                tree.decorator_list = rec(tree.decorator_list)

                # gather the names of formal parameters
                a = tree.args
                newformals = formals.copy()
                for s in (a.args, a.kwonlyargs):
                    newformals += [x.arg for x in s if x is not None]
                newformals = list(uniqify(newformals))

                if a.vararg is not None:
                    newvarargs = varargs.copy()
                    newvarargs.append(a.vararg.arg)
                    newvarargs = list(uniqify(newvarargs))
                else:
                    newvarargs = varargs

                if a.kwarg is not None:
                    newkwargs = kwargs.copy()
                    newkwargs.append(a.kwarg.arg)
                    newkwargs = list(uniqify(newkwargs))
                else:
                    newkwargs = kwargs

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

                # transform body using **the new inner scope**
                tree.body = transform.recurse(tree.body,
                                              varargs=newvarargs,
                                              kwargs=newkwargs,
                                              formals=newformals)

        # force the accessed part of *args or **kwargs (at the receiving end)
        elif type(tree) is Subscript and type(tree.ctx) is Load:
            if type(tree.value) is Name:
                # force now only those items that are actually used here
                if tree.value.id in varargs:
                    stop()
                    tree.slice = rec(tree.slice)
                    if type(tree.slice) is Index:
                        tree = q[ast_literal[tree]()]
                    elif type(tree.slice) is Slice:
                        tree = hq[forcestarargs(ast_literal[tree])]
                    else:
                        assert False, "lazify: expected Index or Slice in subscripting a formal *args"
                elif tree.value.id in kwargs:
                    stop()
                    tree.slice = rec(tree.slice)
                    if type(tree.slice) is Index:
                        tree = q[ast_literal[tree]()]
                    else:
                        assert False, "lazify: expected Index in subscripting a formal **kwargs"

        # force formal parameters, including any uses of the whole *args or **kwargs
        elif type(tree) is Name and type(tree.ctx) is Load:
            stop()  # must not recurse even when a Name changes into a Call.
            if tree.id in formals:
                tree = q[ast_literal[tree]()]  # force the promise
            elif tree.id in varargs:
                tree = hq[forcestarargs(ast_literal[tree])]
            elif tree.id in kwargs:
                tree = hq[forcekwargs(ast_literal[tree])]

        # transform calls
        #
        # Delay evaluation of the args, but only if the call target is
        # a lazy function (i.e. expects delayed args).
        #
        # We need this runtime detection to support calls to strict
        # (regular Python) functions from within the "with lazify" block.
        elif type(tree) is Call:
            if isdo(tree) or islet(tree):
                pass  # known to be strict, no need to introduce lazy[]
            else:
                stop()
                gen_sym = dyn.gen_sym

                # Evaluate the operator (.func of the Call node) just once.
                thefunc = tree.func
                thefunc = rec(thefunc)  # recurse into the operator
                fname = gen_sym("f")
                letbindings = [q[(name[fname], ast_literal[thefunc])]]

                # Delay the args (first, recurse into them).

                def transform_starred(tree):  # transform a "*t" item in a call
                    tree = rec(tree)
                    # literal list or tuple containing computations that should be evaluated lazily
                    if type(tree) in (List, Tuple):
                        tree.elts = [hq[lazy[ast_literal[x]]] for x in tree.elts]
                    else:  # something else - assume an iterable
                        tree = hq[dataseq(ast_literal[tree])]
                    return tree

                def transform_dstarred(tree):  # transform a "**d" item in a call
                    tree = rec(tree)
                    # literal dictionary where the values contain computations that should be evaluated lazily
                    if type(tree) is Dict:
                        tree.values = [hq[lazy[ast_literal[x]]] for x in tree.values]
                    else: # something else - assume a mapping
                        tree = hq[datadic(ast_literal[tree])]
                    return tree

                anames = []
                for x in tree.args:
                    if type(x) is Starred:  # Python 3.5+
                        raise NotImplementedError("lazify: sorry, passing *args in a call currently not supported for Python 3.5+")
                        v = transform_starred(x.value)
                        # TODO: finish *args support, mirroring the Python 3.4 implementation below
                    else:
                        v = rec(x)
                        v = hq[lazy[ast_literal[v]]]
                    localname = gen_sym("a")
                    letbindings.append(q[(name[localname], ast_literal[v])])
                    anames.append(localname)

                kwmap = []
                for x in tree.keywords:
                    if x.arg is None:
                        raise NotImplementedError("lazify: sorry, passing **kwargs in a call currently not supported for Python 3.5+")
                        v = transform_dstarred(x.value)
                        # TODO: finish **kwargs support, mirroring the Python 3.4 implementation below
                    else:
                        v = rec(x.value)
                        v = hq[lazy[ast_literal[v]]]
                        localname = gen_sym("kw")
                        letbindings.append(q[(name[localname], ast_literal[v])])
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

                # Python 3.4 starargs/kwargs handling
                #
                # Note this pertains to the presence of *args and **kwargs
                # arguments **in a call**. The receiving end is handled by
                # the function definition transformer.
                if hasattr(tree, "starargs"):
                    if tree.starargs is not None:
                        saname = gen_sym("sa")
                        letbindings.append(q[(name[saname], ast_literal[transform_starred(tree.starargs)])])
                        lazycall.starargs = q[name[saname]]
                        strictcall.starargs = hq[forcestarargs(name[saname])]
                    else:
                        lazycall.starargs = strictcall.starargs = None
                if hasattr(tree, "kwargs"):
                    if tree.kwargs is not None:
                        kwaname = gen_sym("kwa")
                        letbindings.append(q[(name[kwaname], ast_literal[transform_dstarred(tree.kwargs)])])
                        lazycall.kwargs = q[name[kwaname]]
                        strictcall.kwargs = hq[forcekwargs(name[kwaname])]
                    else:
                        lazycall.kwargs = strictcall.kwargs = None

                letbody = q[ast_literal[lazycall] if hasattr(name[fname], "_lazy") else ast_literal[strictcall]]
                tree = let(letbindings, letbody)

        return tree
    newbody = []
    for stmt in body:
        newbody.append(transform.recurse(stmt, varargs=[], kwargs=[], formals=[]))
    return newbody
