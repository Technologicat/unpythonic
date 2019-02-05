# -*- coding: utf-8 -*-
"""Automatic lazy evaluation of function arguments."""

from functools import wraps

from ast import Lambda, FunctionDef, Call, Name, \
                Starred, keyword, List, Tuple, Dict, Set, \
                Subscript, Load
from .astcompat import AsyncFunctionDef

from macropy.core.quotes import macros, q, ast_literal
from macropy.core.hquotes import macros, hq
from macropy.core.walkers import Walker

from macropy.quick_lambda import macros, lazy
from macropy.quick_lambda import Lazy

from .util import suggest_decorator_index, sort_lambda_decorators, detect_lambda, isx, getname
from .letdoutil import islet, isdo
from ..regutil import register_decorator
from ..it import uniqify
from ..collections import mogrify

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

# -----------------------------------------------------------------------------

# lazyrec: syntax transformer, recursively lazify elements in container literals
#
# **CAUTION**: There are some containers whose constructors appear as a Call node,
# and also ``list``, ``tuple`` and ``set`` can be created via explicit calls.
#
# To treat these cases correctly, we must know which arguments to the
# constructors refer to other containers (to be unpacked into the new one)
# and which refer to atoms (to be added as individual items).
#
# Args that represent atoms should be lazified, so that they enter the container
# as lazy items.
#
# For args that represent containers:
#
#   - Args that opaquely refer to an existing container should not be lazified,
#     to avoid interfering with their unpacking.
#
#   - Args where the value is a literal container should be lazified by descending
#     into it, to lazify its items.
#
# For example::
#
#     s = {1, 2, 3}
#     fs = frozenset(s)          # opaque container argument, do nothing
#     fs = frozenset({1, 2, 3})  # literal container argument, descend
#
#     d1 = {'a': 'foo', 'b': 'bar'}
#     d2 = {'c': 'baz'}
#     fd = frozendict(d1, d2, d='qux')  # d1, d2 opaque containers; any kws are atoms
#     fd = frozendict({1: 2, 3: 4}, d2, d='qux')  # literal container, opaque container, atom
#
# In any case, *args and **kwargs are lazified only if literal containers;
# whatever they are, the result must be unpackable to perform the function call.
_ctorcalls_map = ("frozendict", "dict")
_ctorcalls_seq = ("list", "tuple", "set", "frozenset", "box", "cons", "llist", "ll")
# when to lazify individual (positional, keyword) args.
_ctor_handling_modes = {  # constructors that take iterable(s) as positional args.
                        "dict": ("literal_only", "all"),
                        "frozendict": ("literal_only", "all"), # same ctor API as dict
                        "list": ("literal_only", "all"),  # doesn't take kws, "all" is ok
                        "tuple": ("literal_only", "all"),
                        "set": ("literal_only", "all"),
                        "frozenset": ("literal_only", "all"),
                        "llist": ("literal_only", "all"),
                        # constructors that take individual items.
                        "box": ("all", "all"),
                        "cons": ("all", "all"),
                        "ll": ("all", "all")}
_ctorcalls_all = _ctorcalls_map + _ctorcalls_seq
def lazyrec(tree):
    def lazify_ctorcall(tree, positionals="all", keywords="all"):
        newargs = []
        for a in tree.args:
            if type(a) is Starred:  # *args in Python 3.5+
                if is_literal_container(a.value, maps_only=False):
                    a.value = transform.recurse(a.value)
                # else do nothing
            elif positionals == "all" or is_literal_container(a, maps_only=False):  # single positional arg
                a = transform.recurse(a)
            newargs.append(a)
        tree.args = newargs
        for kw in tree.keywords:
            if kw.arg is None:  # **kwargs in Python 3.5+
                if is_literal_container(kw.value, maps_only=True):
                    kw.value = transform.recurse(kw.value)
                # else do nothing
            elif keywords == "all" or is_literal_container(kw.value, maps_only=True):  # single named arg
                kw.value = transform.recurse(kw.value)
        # *args and **kwargs in Python 3.4
        if hasattr(tree, "starargs"):
            if tree.starargs is not None and is_literal_container(tree.starargs, maps_only=False):
                tree.starargs = transform.recurse(tree.starargs)
        if hasattr(tree, "kwargs"):
            if tree.kwargs is not None and is_literal_container(tree.kwargs, maps_only=True):
                tree.kwargs = transform.recurse(tree.kwargs)

    @Walker
    def transform(tree, *, stop, **kw):
        if type(tree) in (Tuple, List, Set):
            stop()
            tree.elts = [transform.recurse(x) for x in tree.elts]
        elif type(tree) is Dict:
            stop()
            tree.values = [transform.recurse(x) for x in tree.values]
        elif type(tree) is Call and any(isx(tree.func, ctor) for ctor in _ctorcalls_all):
            stop()
            p, k = _ctor_handling_modes[getname(tree.func)]
            tree = lazify_ctorcall(tree, p, k)
        # TODO: this might not catch what we want; lazy[] seems to expand immediately even though quoted here.
        elif type(tree) is Subscript and isx(tree.value, 'lazy'):
            stop()
        else:
            stop()
            tree = hq[lazy[ast_literal[tree]]]
        return tree
    return transform.recurse(tree)

def is_literal_container(tree, maps_only=False):  # containers understood by lazyrec[]
    """Test whether tree is a container literal understood by lazyrec[]."""
    if not maps_only:
        if type(tree) in (List, Tuple, Set): return True
        if type(tree) is Call and any(isx(tree.func, s) for s in _ctorcalls_seq): return True
    if type(tree) is Dict: return True
    if type(tree) is Call and any(isx(tree.func, s) for s in _ctorcalls_map): return True
    return False

# -----------------------------------------------------------------------------

# Because force(x) is more explicit than x() and MacroPy itself doesn't define this.
def force(x):
    """Force a MacroPy lazy[] promise.

    For a promise ``x``, the effect of ``force(x)`` is the same as ``x()``,
    except that ``force `` first checks that ``x`` is a promise.

    If ``x`` is not a promise, it is returned as-is (à la Racket).

    This recurses on any containers with the appropriate ``collections.abc``
    abstract base classes (virtuals ok too). Mutable containers are updated
    in-place, for immutables a new instance is created. For details, see
    ``unpythonic.collections.mogrify``.
    """
    f = lambda elt: elt() if isinstance(elt, Lazy) else elt
    return mogrify(f, x)  # in-place update to allow lazy functions to have writable list arguments

def wrap(x):
    """Wrap an already evaluated data value into a MacroPy lazy[] promise.

    If ``x`` is already a promise, it is returned as-is.

    This recurses on any containers with the appropriate ``collections.abc``
    abstract base classes (virtuals ok too). Mutable containers are updated
    in-place, for immutables a new instance is created. For details, see
    ``unpythonic.collections.mogrify``.
    """
    # the else wraps the already evaluated elt into a promise
    f = lambda elt: elt if isinstance(elt, Lazy) else lazy[elt]
    return mogrify(f, x)

# -----------------------------------------------------------------------------

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
            if isdo(tree) or islet(tree) or isx(tree.func, "namelambda"):
                pass  # known to be strict, no need to introduce lazy[] (just let the transformer recurse)
            else:
                stop()
                ln, co = tree.lineno, tree.col_offset

                # Evaluate the operator (.func of the Call node).
                thefunc = tree.func
                thefunc = rec(thefunc)  # recurse into the operator

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
                        if is_literal_container(tree, maps_only=dstarred):
                            tree = lazyrec(tree)
                    return tree

                # TODO: test *args support in Python 3.5+ (this **should** work according to the AST specs)
                adata = []
                for x in tree.args:
                    if type(x) is Starred:  # *seq in Python 3.5+
                        v = transform_starred(x.value)
                        v = Starred(value=q[ast_literal[v]], lineno=ln, col_offset=co)
                    else:
                        v = transform_arg(x)
                    adata.append(v)

                # TODO: test **kwargs support in Python 3.5+ (this **should** work according to the AST specs)
                kwdata = []
                for x in tree.keywords:
                    if x.arg is None:  # **dic in Python 3.5+
                        v = transform_starred(x.value, dstarred=True)
                    else:
                        v = transform_arg(x.value)
                    kwdata.append((x.arg, v))

                # Construct the call
                mycall = Call(func=hq[lazycall],
                              args=[q[ast_literal[thefunc]]] + [q[ast_literal[x]] for x in adata],
                              keywords=[keyword(arg=k, value=q[ast_literal[x]]) for k, x in kwdata],
                              lineno=ln, col_offset=co)

                # Python 3.4 starargs/kwargs handling
                #
                # Note this pertains to the presence of *args and **kwargs
                # arguments **in a call**. The receiving end is handled by
                # the function definition transformer.
                if hasattr(tree, "starargs"):
                    if tree.starargs is not None:
                        mycall.starargs = transform_starred(tree.starargs)
                    else:
                        mycall.starargs = None
                if hasattr(tree, "kwargs"):
                    if tree.kwargs is not None:
                        mycall.kwargs = transform_starred(tree.kwargs, dstarred=True)
                    else:
                        mycall.kwargs = None

                tree = mycall

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

# -----------------------------------------------------------------------------
