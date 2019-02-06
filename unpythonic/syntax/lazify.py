# -*- coding: utf-8 -*-
"""Automatic lazy evaluation of function arguments."""

from copy import copy

from ast import Lambda, FunctionDef, Call, Name, Attribute, \
                Starred, keyword, List, Tuple, Dict, Set, \
                Subscript, Load, Store
from .astcompat import AsyncFunctionDef

from macropy.core.quotes import macros, q, ast_literal
from macropy.core.hquotes import macros, hq
from macropy.core.walkers import Walker

from macropy.quick_lambda import macros, lazy
from macropy.quick_lambda import Lazy

from .util import suggest_decorator_index, sort_lambda_decorators, detect_lambda, \
                  isx, make_isxpred, getname
from .letdoutil import islet, isdo
from ..regutil import register_decorator
from ..collections import mogrify

@register_decorator(priority=95)
def mark_lazy(f):
    """Internal. Helps calling lazy functions from outside a ``with lazify`` block."""
    f._lazy = True
    return f

def lazycall(_func, *thunks, **kwthunks):
    """Internal. Helps calling strict functions from inside a ``with lazify`` block."""
    if hasattr(_func, '_lazy'):
        return _func(*thunks, **kwthunks)
    return _func(*force(thunks), **force(kwthunks))

# -----------------------------------------------------------------------------

# Because force(x) is more explicit than x() and MacroPy itself doesn't define this.
def force1(x):
    """Force a MacroPy lazy[] promise.

    For a promise ``x``, the effect of ``force1(x)`` is the same as ``x()``,
    except that ``force1 `` first checks that ``x`` is a promise.

    If ``x`` is not a promise, it is returned as-is (à la Racket).
    """
    return x() if isinstance(x, Lazy) else x

def force(x):
    """Like force1, but recurse into containers.

    This recurses on any containers with the appropriate ``collections.abc``
    abstract base classes (virtuals ok too). Mutable containers are updated
    in-place, for immutables a new instance is created. For details, see
    ``unpythonic.collections.mogrify``.
    """
    return mogrify(force1, x)  # in-place update to allow lazy functions to have writable list arguments

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

islazy = make_isxpred("lazy")  # unexpanded
isLazy = make_isxpred("Lazy")  # expanded
def lazyrec(tree):
    @Walker
    def transform(tree, *, stop, **kw):
        if type(tree) in (Tuple, List, Set):
            stop()
            tree.elts = [rec(x) for x in tree.elts]
        elif type(tree) is Dict:
            stop()
            tree.values = [rec(x) for x in tree.values]
        elif type(tree) is Call and any(isx(tree.func, ctor) for ctor in _ctorcalls_all):
            stop()
            p, k = _ctor_handling_modes[getname(tree.func)]
            tree = lazify_ctorcall(tree, p, k)
        # TODO: lazy[] seems to expand immediately even though quoted in our atom case?
        elif type(tree) is Subscript and isx(tree.value, islazy):  # unexpanded
            stop()
        elif type(tree) is Call and isx(tree.func, isLazy):  # expanded
            stop()
        else:
            stop()
            tree = hq[lazy[ast_literal[tree]]]
        return tree

    def lazify_ctorcall(tree, positionals="all", keywords="all"):
        newargs = []
        for a in tree.args:
            if type(a) is Starred:  # *args in Python 3.5+
                if is_literal_container(a.value, maps_only=False):
                    a.value = rec(a.value)
                # else do nothing
            elif positionals == "all" or is_literal_container(a, maps_only=False):  # single positional arg
                a = rec(a)
            newargs.append(a)
        tree.args = newargs
        for kw in tree.keywords:
            if kw.arg is None:  # **kwargs in Python 3.5+
                if is_literal_container(kw.value, maps_only=True):
                    kw.value = rec(kw.value)
                # else do nothing
            elif keywords == "all" or is_literal_container(kw.value, maps_only=True):  # single named arg
                kw.value = rec(kw.value)
        # *args and **kwargs in Python 3.4
        if hasattr(tree, "starargs"):
            if tree.starargs is not None and is_literal_container(tree.starargs, maps_only=False):
                tree.starargs = rec(tree.starargs)
        if hasattr(tree, "kwargs"):
            if tree.kwargs is not None and is_literal_container(tree.kwargs, maps_only=True):
                tree.kwargs = rec(tree.kwargs)

    rec = transform.recurse
    return rec(tree)

def is_literal_container(tree, maps_only=False):
    """Test whether tree is a container literal understood by lazyrec[]."""
    if not maps_only:
        if type(tree) in (List, Tuple, Set): return True
        if type(tree) is Call and any(isx(tree.func, s) for s in _ctorcalls_seq): return True
    if type(tree) is Dict: return True
    if type(tree) is Call and any(isx(tree.func, s) for s in _ctorcalls_map): return True
    return False

# -----------------------------------------------------------------------------

# TODO: support curry, call, callwith (may need changes to their implementations, too)

# TODO: other binding constructs?
#   - keep in mind that force(x) == x if x is a non-promise atom, so a wrapper is not needed
#   - not "with", eager init is the whole point of a context manager
#   - not "for", it's a rapidly changing loop counter
# full list: see unpythonic.syntax.scoping.get_names_in_store_context (and the link therein)

def lazify(body):
    # first pass, outside-in
    userlambdas = detect_lambda.collect(body)
    body = yield body

    # second pass, inside-out
    @Walker
    def transform(tree, *, stop, **kw):
        if type(tree) in (FunctionDef, AsyncFunctionDef, Lambda):
            if type(tree) is Lambda and id(tree) not in userlambdas:
                pass  # ignore macro-introduced lambdas
            else:
                stop()
                tree.decorator_list = rec(tree.decorator_list)

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

                tree.body = rec(tree.body)

#        # This is one place where explicit is better than implicit; with
#        # auto-lazification of assignments it is too easy to accidentally set up
#        # an infinite loop.
#        # This is ok:
#        #   force1(lst)[0] = (10 * (force1(lst()[0]) if isinstance(lst, Lazy1) else force1(lst[0])))
#        # but this blows up later when we eventually force lst[0]:
#        #   force1(lst)[0] = Lazy1(lambda: (10 * (force1(lst()[0]) if isinstance(lst, Lazy1) else force1(lst[0]))))
#        # TODO: solve this by forcing and capturing the current value before assigning,
#        # TODO: instead of allowing the promise to refer to a list element.
#        # TODO: OTOH, that's a **use** of the current value, so we may as well do nothing,
#        # TODO: causing the RHS to be evaluated.
#        elif type(tree) is Assign:  # lazify RHS
#            stop()
#            tree.targets = rec(tree.targets)
#            tree.value = rec(tree.value)          # add any needed force() invocations inside the tree
#            if type(tree) is not Name:
#                tree.value = lazyrec(tree.value)  # (re-)thunkify
#
#        elif type(tree) is AnnAssign:  # TODO: test in Python 3.6+
#            stop()
#            if tree.value is not None:
#                tree.target = rec(tree.target)
#                tree.value = rec(tree.value)
#                if type(tree) is not Name:
#                    tree.value = lazyrec(tree.value)
#
#        elif type(tree) is AugAssign:
#            stop()
#            tree.target = rec(tree.target)
#            tree.value = rec(tree.value)
#            if type(tree) is not Name:
#                tree.value = lazyrec(tree.value)

        elif type(tree) is Call:
            # For some important functions known to be strict, just recurse
            # namelambda() is used by let[] and do[]
            # Lazy() is a strict function, takes a lambda, constructs a Lazy object
            if isdo(tree) or islet(tree) or isx(tree.func, "namelambda") or \
               any(isx(tree.func, s) for s in _ctorcalls_all) or isx(tree.func, isLazy):
                # here we know the operator (.func) to be one of specific names;
                # don't transform it to avoid confusing lazyrec[] (important if this
                # is an inner call in the arglist of an outer, lazy call, since it
                # must see any container constructor calls that appear in the args)
                stop()
                tree.args = rec(tree.args)
                tree.keywords = rec(tree.keywords)
                if hasattr(tree, "starargs"): tree.starargs = rec(tree.starargs)  # Python 3.4
                if hasattr(tree, "kwargs"): tree.kwargs = rec(tree.kwargs)  # Python 3.4
            else:
                stop()
                ln, co = tree.lineno, tree.col_offset
                thefunc = rec(tree.func)

                def transform_arg(tree):
                    if type(tree) is not Name:
                        tree = rec(tree)      # add any needed force() invocations inside the tree
                        tree = lazyrec(tree)  # (re-)thunkify
                    return tree

                def transform_starred(tree, dstarred=False):
                    if type(tree) is not Name:
                        tree = rec(tree)
                        # lazify items if we have a literal container
                        # we must avoid lazifying any other exprs, since a Lazy cannot be unpacked.
                        if is_literal_container(tree, maps_only=dstarred):
                            tree = lazyrec(tree)
                    return tree

                # TODO: test *args support in Python 3.5+ (this **should** work according to the AST specs)
                adata = []
                for x in tree.args:
                    if type(x) is Starred:  # *args in Python 3.5+
                        v = transform_starred(x.value)
                        v = Starred(value=q[ast_literal[v]], lineno=ln, col_offset=co)
                    else:
                        v = transform_arg(x)
                    adata.append(v)

                # TODO: test **kwargs support in Python 3.5+ (this **should** work according to the AST specs)
                kwdata = []
                for x in tree.keywords:
                    if x.arg is None:  # **kwargs in Python 3.5+
                        v = transform_starred(x.value, dstarred=True)
                    else:
                        v = transform_arg(x.value)
                    kwdata.append((x.arg, v))

                # Construct the call
                mycall = Call(func=hq[lazycall],
                              args=[q[ast_literal[thefunc]]] + [q[ast_literal[x]] for x in adata],
                              keywords=[keyword(arg=k, value=q[ast_literal[x]]) for k, x in kwdata],
                              lineno=ln, col_offset=co)

                if hasattr(tree, "starargs"):  # *args in Python 3.4
                    if tree.starargs is not None:
                        mycall.starargs = transform_starred(tree.starargs)
                    else:
                        mycall.starargs = None
                if hasattr(tree, "kwargs"):  # **kwargs in Python 3.4
                    if tree.kwargs is not None:
                        mycall.kwargs = transform_starred(tree.kwargs, dstarred=True)
                    else:
                        mycall.kwargs = None

                tree = mycall

        elif type(tree) is Subscript:  # force only accessed part of obj[...]
            if type(tree.value) is Name:
                stop()
                tree.slice = rec(tree.slice)
                # shallow-force top-level promise to get the actual container without evaluating its items.
                tree.value = hq[force1(ast_literal[tree.value])]
                if type(tree.ctx) is Load:
                    tree = hq[force(ast_literal[tree])]

        elif type(tree) is Attribute:
            stop()
            # a.b.c --> force(force(force(a).b).c)  (Load)
            #       -->       force(force(a).b).c   (Store)
            # attr="c", value=a.b
            # attr="b", value=a
            # Note in case of assignment to a compound, only the outermost
            # Attribute is in Store context.
            tree.value = rec(tree.value)
            if type(tree.ctx) is Load:
                tree = hq[force(ast_literal[tree])]

        elif type(tree) is Name and type(tree.ctx) is Load:
            stop()  # must not recurse when a Name changes into a Call.
            tree = hq[force(ast_literal[tree])]

        return tree

    rec = transform.recurse
    newbody = []
    for stmt in body:
        newbody.append(rec(stmt))
    return newbody

# -----------------------------------------------------------------------------
