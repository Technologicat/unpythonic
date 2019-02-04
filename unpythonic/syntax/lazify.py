# -*- coding: utf-8 -*-
"""Automatic lazy evaluation of function arguments."""

from functools import wraps

from ast import Lambda, FunctionDef, Call, Name, \
                Starred, keyword, List, Tuple, Dict, Set, \
                Subscript, Load
from .astcompat import AsyncFunctionDef

from macropy.core.quotes import macros, q, ast_literal, name
from macropy.core.hquotes import macros, hq
from macropy.core.walkers import Walker

from macropy.quick_lambda import macros, lazy
from macropy.quick_lambda import Lazy

from .util import suggest_decorator_index, sort_lambda_decorators, detect_lambda, isx
from .letdo import let
from .letdoutil import islet, isdo
from ..regutil import register_decorator
from ..it import uniqify
from ..dynassign import dyn
from ..fup import frozendict

@register_decorator(priority=95)
def mark_lazy(f):
    """Internal. Helps calling lazy functions from outside a ``with lazify`` block."""
    @wraps(f)
    def lazified(*args, **kwargs):
        return f(*wrap(args), **wrap(kwargs))
    lazified._lazy = True
    lazified._entrypoint = f
    return lazified

def lazycall(_func, *thunks, **kwthunks):
    """Internal. Helps calling strict functions from inside a ``with lazify`` block."""
    if hasattr(_func, '_lazy'):
        return _func._entrypoint(*thunks, **kwthunks)  # skip the lazified() wrapper
    return _func(*force(thunks), **force(kwthunks))

# syntax transformer: lazify elements in container literals, recursively
def lazyrec(tree):
    @Walker
    def transform(tree, *, stop, **kw):
        if type(tree) in (Tuple, List, Set):
            stop()
            tree.elts = [transform.recurse(x) for x in tree.elts]
        elif type(tree) is Dict:
            stop()
            tree.values = [transform.recurse(x) for x in tree.values]
        elif type(tree) is Call and isx(tree.func, "frozenset") and \
             len(tree.args) == 1 and type(tree.args[0]) is Set:
            stop()
            tree.args[0] = transform.recurse(tree.args[0])
        elif type(tree) is Call and isx(tree.func, "frozendict") and \
             len(tree.args) == 1 and type(tree.args[0]) is Dict:
            stop()
            tree.args[0] = transform.recurse(tree.args[0])
        # TODO: this might not catch what we want; lazy[] seems to expand immediately even though quoted here.
        elif type(tree) is Subscript and isx(tree.value, 'lazy'):
            stop()
        else:
            stop()
            tree = hq[lazy[ast_literal[tree]]]
        return tree
    return transform.recurse(tree)

# Because force(x) is more explicit than x() and MacroPy itself doesn't define this.
def force(x):
    """Force a MacroPy lazy[] promise.

    For a promise ``x``, the effect of ``force(x)`` is the same as ``x()``,
    except that ``force `` first checks that ``x`` is a promise.

    If ``x`` is not a promise, it is returned as-is (à la Racket).

    This recurses into ``list``, ``tuple``, ``dict``, ``set``, ``frozenset``,
    and ``unpythonic.fup.frozendict``.
    """
    return _f(x, iflazyatom=lambda x: x(), otherwise=lambda x: x)

def wrap(x):
    """Wrap an already evaluated data value into a MacroPy lazy[] promise.

    If ``x`` is already a promise, it is returned as-is.

    This recurses into ``list``, ``tuple``, ``dict``, ``set``, ``frozenset``,
    and ``unpythonic.fup.frozendict``.
    """
    # The otherwise case wraps the already evaluated x into a promise.
    return _f(x, iflazyatom=lambda x: x, otherwise=lambda x: lazy[x])

def _f(x, iflazyatom, otherwise):  # common skeleton for force/wrap
    def doit(x):
        if isinstance(x, tuple):
            return tuple(doit(elt) for elt in x)
        elif isinstance(x, list):
            return [doit(elt) for elt in x]
        elif isinstance(x, set):
            return {doit(elt) for elt in x}
        elif isinstance(x, frozenset):
            return frozenset({doit(elt) for elt in x})
        elif isinstance(x, dict):
            return {k: doit(v) for k, v in x.items()}
        elif isinstance(x, frozendict):
            return frozendict({k: doit(v) for k, v in x.items()})
        elif isinstance(x, Lazy):
            return iflazyatom(x)
        return otherwise(x)
    return doit(x)

# TODO: support curry, call, callwith (may need changes to their implementations, too)

# TODO: collect localvars (if not already in formals) from assignments, lazify RHS
# TODO: other binding constructs? Maybe "with": wrap(ctxmgr(...)) to eagerly init, but return a dummy promise
# full list: see unpythonic.syntax.scoping.get_names_in_store_context (and the link therein)

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
                newvarargs = list(uniqify(varargs + [a.vararg.arg])) if a.vararg is not None else varargs
                newkwargs = list(uniqify(kwargs + [a.kwarg.arg])) if a.kwarg is not None else kwargs

                # mark this definition as lazy, and insert the interface wrapper
                # to allow also strict code to call this function
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

        elif type(tree) is Call:
            if isdo(tree) or islet(tree):
                pass  # known to be strict, no need to introduce lazy[] (just let the transformer recurse)
            else:
                stop()
                gen_sym = dyn.gen_sym
                ln, co = tree.lineno, tree.col_offset

                # Evaluate the operator (.func of the Call node) just once.
                thefunc = tree.func
                thefunc = rec(thefunc)  # recurse into the operator
                fname = gen_sym("f")
                letbindings = [q[(name[fname], ast_literal[thefunc])]]

                # Delay the args (first, recurse into them).

                def transform_arg(tree):
                    if type(tree) is Name and tree.id in formals:
                        pass  # optimized passthrough for arg -> arg (both positional and named)
                    else:
                        tree = rec(tree)  # add any needed force() invocations inside the tree
                        tree = hq[lazy[ast_literal[tree]]]  # thunkify *the whole tree*
                    return tree

                def transform_starred(tree, dstarred=False):
                    optimizable_names = kwargs if dstarred else varargs
                    if type(tree) is Name and tree.id in optimizable_names:
                        pass  # optimized passthrough for *args -> *args, **kwargs -> **kwargs
                    else:
                        tree = rec(tree)
                        # lazify items if we have a literal container
                        # we must avoid lazifying any other exprs, since a Lazy cannot be unpacked.
                        if is_unpackable_literal(tree, dictsonly=dstarred):
                            tree = lazyrec(tree)
                    return tree

                def is_unpackable_literal(tree, dictsonly=False):  # containers understood by lazyrec[]
                    if not dictsonly:
                        if type(tree) in (List, Tuple, Set): return True
                        if type(tree) is Call and isx(tree.func, 'frozenset'): return True
                    if type(tree) is Dict: return True
                    if type(tree) is Call and isx(tree.func, 'frozendict'): return True
                    return False

                # TODO: test *args support in Python 3.5+ (this **should** work according to the AST specs)
                adata = []
                for x in tree.args:
                    localname = gen_sym("a")
                    if type(x) is Starred:  # *seq in Python 3.5+
                        v = transform_starred(x.value)
                        a = Starred(value=q[name[localname]], lineno=ln, col_offset=co)
                    else:
                        v = transform_arg(x)
                        a = q[name[localname]]
                    adata.append(a)
                    letbindings.append(q[(name[localname], ast_literal[v])])

                # TODO: test **kwargs support in Python 3.5+ (this **should** work according to the AST specs)
                kwdata = []
                for x in tree.keywords:
                    localname = gen_sym("kw")
                    if x.arg is None:  # **dic in Python 3.5+
                        v = transform_starred(x.value, dstarred=True)
                    else:
                        v = transform_arg(x.value)
                    a = q[name[localname]]
                    kwdata.append((x.arg, a))
                    letbindings.append(q[(name[localname], ast_literal[v])])

                # Construct the call
                mycall = Call(func=hq[lazycall],
                              args=[q[name[fname]]] + [q[ast_literal[x]] for x in adata],
                              keywords=[keyword(arg=k, value=q[ast_literal[x]]) for k, x in kwdata],
                              lineno=ln, col_offset=co)

                # Python 3.4 starargs/kwargs handling
                #
                # Note this pertains to the presence of *args and **kwargs
                # arguments **in a call**. The receiving end is handled by
                # the function definition transformer.
                if hasattr(tree, "starargs"):
                    if tree.starargs is not None:
                        saname = gen_sym("sa")
                        v = transform_starred(tree.starargs)
                        letbindings.append(q[(name[saname], ast_literal[v])])
                        mycall.starargs = q[name[saname]]
                    else:
                        mycall.starargs = None
                if hasattr(tree, "kwargs"):
                    if tree.kwargs is not None:
                        kwaname = gen_sym("kwa")
                        v = transform_starred(tree.kwargs, dstarred=True)
                        letbindings.append(q[(name[kwaname], ast_literal[v])])
                        mycall.kwargs = q[name[kwaname]]
                    else:
                        mycall.kwargs = None

                letbody = mycall
                tree = let(letbindings, letbody)

        # force the accessed part of *args or **kwargs (at the receiving end)
        elif type(tree) is Subscript and type(tree.ctx) is Load:
            if type(tree.value) is Name and tree.value.id in varargs + kwargs:
                stop()
                tree.slice = rec(tree.slice)
                tree = hq[force(ast_literal[tree])]

        # force formal parameters, including any uses of the whole *args or **kwargs
        elif type(tree) is Name and type(tree.ctx) is Load:
            stop()  # must not recurse even when a Name changes into a Call.
            if tree.id in formals + varargs + kwargs:
                tree = hq[force(ast_literal[tree])]

        return tree
    newbody = []
    for stmt in body:
        newbody.append(transform.recurse(stmt, varargs=[], kwargs=[], formals=[]))
    return newbody
