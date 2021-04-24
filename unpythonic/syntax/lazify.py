# -*- coding: utf-8 -*-
"""Automatic lazy evaluation of function arguments."""

from ast import (Lambda, FunctionDef, AsyncFunctionDef, Call, Name, Attribute,
                 Starred, keyword, List, Tuple, Dict, Set, Subscript, Load)

from mcpyrate.quotes import macros, q, a, h  # noqa: F401

from mcpyrate.walkers import ASTTransformer

from .util import (suggest_decorator_index, sort_lambda_decorators, detect_lambda,
                   isx, make_isxpred, getname, is_decorator, wrapwith)
from .letdoutil import islet, isdo, ExpandedLetView
from ..lazyutil import Lazy, passthrough_lazy_args, force, force1, maybe_force_args
from ..dynassign import dyn

# -----------------------------------------------------------------------------

# lazy: syntax transformer, lazify a single expression
def lazy(tree):
    return q[Lazy(lambda: a[tree])]

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
_ctorcalls_seq = ("list", "tuple", "set", "frozenset", "box", "ThreadLocalBox", "Some", "cons", "llist", "ll")
# when to lazify individual (positional, keyword) args.
_ctor_handling_modes = {  # constructors that take iterable(s) as positional args.
                        "dict": ("literal_only", "all"),
                        "frozendict": ("literal_only", "all"),  # same ctor API as dict
                        "list": ("literal_only", "all"),  # doesn't take kws, "all" is ok
                        "tuple": ("literal_only", "all"),
                        "set": ("literal_only", "all"),
                        "frozenset": ("literal_only", "all"),
                        "llist": ("literal_only", "all"),
                        # constructors that take individual items as separate positional args.
                        "box": ("all", "all"),
                        "ThreadLocalBox": ("all", "all"),
                        "Some": ("all", "all"),
                        "cons": ("all", "all"),
                        "ll": ("all", "all")}
_ctorcalls_all = _ctorcalls_map + _ctorcalls_seq

# Usability: warn about incorrect use to prevent mysterious errors whose cause is hard to find.
#
# Constructors for which the positional mode is "literal_only" are susceptible
# to a particular variety of human error.
#
# Without the check in `lazify_ctorcall`, the invocation `lazyrec[tuple(1/0, 2/0)]`
# will crash due to a `ZeroDivisionError`. The lazifier skips the arguments, because
# the `tuple()` call is wrong; it should be `lazyrec[tuple((1/0, 2/0))]`.
# Note the outer parentheses; `tuple` takes an iterable as **its only argument**.
#
# `frozendict` is not in this list, because it has the functional-update initialization
# variant `frozendict(mapping1, mapping2, ...)`.
_ctorcalls_that_take_exactly_one_positional_arg = {"tuple", "list", "set", "dict", "frozenset", "llist"}

islazy = make_isxpred("lazy")  # unexpanded
isLazy = make_isxpred("Lazy")  # expanded
def lazyrec(tree):
    # This helper doesn't need to recurse, so we don't need `ASTTransformer` here.
    def transform(tree):
        if type(tree) in (Tuple, List, Set):
            tree.elts = [rec(x) for x in tree.elts]
        elif type(tree) is Dict:
            tree.values = [rec(x) for x in tree.values]
        elif type(tree) is Call and any(isx(tree.func, ctor) for ctor in _ctorcalls_all):
            p, k = _ctor_handling_modes[getname(tree.func)]
            tree = lazify_ctorcall(tree, p, k)
        elif type(tree) is Subscript and isx(tree.value, islazy):  # unexpanded
            pass
        elif type(tree) is Call and isx(tree.func, isLazy):  # expanded
            pass
        else:
            # mcpyrate supports hygienic macro capture, so we can just splice unexpanded
            # (but hygienically unquoted) `lazy` invocations here.
            tree = q[h[lazy][a[tree]]]
        return tree

    def lazify_ctorcall(tree, positionals="all", keywords="all"):
        if getname(tree.func) in _ctorcalls_that_take_exactly_one_positional_arg and len(tree.args) > 1:
            raise SyntaxError(f"lazyrec[]: while analyzing constructor call `{getname(tree.func)}`: there should be exactly one argument, but {len(tree.args)} were given.")  # pragma: no cover

        newargs = []
        for arg in tree.args:
            if type(arg) is Starred:  # *args in Python 3.5+
                if is_literal_container(arg.value, maps_only=False):
                    arg.value = rec(arg.value)
                # else do nothing
            elif positionals == "all" or is_literal_container(arg, maps_only=False):  # single positional arg
                arg = rec(arg)
            newargs.append(arg)
        tree.args = newargs
        for kw in tree.keywords:
            if kw.arg is None:  # **kwargs in Python 3.5+
                if is_literal_container(kw.value, maps_only=True):
                    kw.value = rec(kw.value)
                # else do nothing
            elif keywords == "all" or is_literal_container(kw.value, maps_only=True):  # single named arg
                kw.value = rec(kw.value)

    rec = transform
    return rec(tree)

def is_literal_container(tree, maps_only=False):
    """Test whether tree is a container literal understood by lazyrec[]."""
    if not maps_only:
        if type(tree) in (List, Tuple, Set):
            return True
        # Not reached in case of `lazyrec`, because `lazify_ctorcall` recurses
        # into the the arg using `transform`. Which in turn uses `lazify_ctorcall`,
        # which (beside the constructor name) looks only at the args.
        if type(tree) is Call and any(isx(tree.func, s) for s in _ctorcalls_seq):
            return True
    if type(tree) is Dict:
        return True
    # Not reached in case of `lazyrec`, similarly as above.
    if type(tree) is Call and any(isx(tree.func, s) for s in _ctorcalls_map):
        return True
    return False

# -----------------------------------------------------------------------------

# Note we do **not** lazify the RHS of assignments. This is one place where
# explicit is better than implicit; with auto-lazification of assignment RHSs
# it is too easy to accidentally set up an infinite recursion.
#
# This is ok:
#   force1(lst)[0] = (10 * (force1(lst()[0]) if isinstance(lst, Lazy1) else force1(lst[0])))
#
# but this blows up (by infinite recursion) later when we eventually force lst[0]:
#   force1(lst)[0] = Lazy1(lambda: (10 * (force1(lst()[0]) if isinstance(lst, Lazy1) else force1(lst[0]))))
#
# We **could** solve this by forcing and capturing the current value before assigning,
# instead of allowing the RHS to refer to a lazy list element. But on the other hand,
# that's a **use** of the current value, so we may as well do nothing, causing
# the RHS to be evaluated, without the need to have any extra code here. :)

# TODO: other binding constructs?
#   - keep in mind that force(x) == x if x is a non-promise atom, so a wrapper is not needed
#   - don't lazify "with", eager init is the whole point of a context manager
#   - don't lazify "for", the loop counter changes value imperatively (and usually rather rapidly)
# full list: see unpythonic.syntax.scopeanalyzer.get_names_in_store_context (and the link therein)

def lazify(body):
    # first pass, outside-in
    userlambdas = detect_lambda(body)

    body = dyn._macro_expander.visit(body)

    # second pass, inside-out
    class LazifyTransformer(ASTTransformer):
        def transform(self, tree):
            forcing_mode = self.state.forcing_mode

            # Forcing references (Name, Attribute, Subscript):
            #   x -> f(x)
            #   a.x -> f(force1(a).x)
            #   a.b.x -> f(force1(force1(a).b).x)
            #   a[j] -> f((force1(a))[force(j)])
            #   a[j][k] -> f(force1(force1(a)[force(j)])[force(k)])
            #
            # where f is force, force1 or identity (optimized away) depending on
            # where the term appears; j and k may be indices or slices.
            #
            # Whenever not in Load context, f is identity.
            #
            # The idea is to apply just the right level of forcing to be able to
            # resolve the reference, and then decide what to do with the resolved
            # reference based on where it appears.
            #
            # For example, when subscripting a list, force1 it to unwrap it from
            # a promise if it happens to be inside one, but don't force its elements
            # just for the sake of resolving the reference. Then, apply f to the
            # whole subscript term (forcing the accessed slice of the list, if necessary).
            def f(tree):
                if type(tree.ctx) is Load:
                    if forcing_mode == "full":
                        return q[h[force](a[tree])]
                    elif forcing_mode == "flat":
                        return q[h[force1](a[tree])]
                    # else forcing_mode == "off"
                return tree

            if type(tree) in (FunctionDef, AsyncFunctionDef, Lambda):
                if type(tree) is Lambda and id(tree) not in userlambdas:
                    return self.generic_visit(tree)  # ignore macro-introduced lambdas (but recurse inside them)
                else:
                    # mark this definition as lazy, and insert the interface wrapper
                    # to allow also strict code to call this function
                    if type(tree) is Lambda:
                        lam = tree
                        tree = q[h[passthrough_lazy_args](a[tree])]
                        # TODO: This doesn't really do anything; we don't here see the chain
                        # TODO: of Call nodes (decorators) that surround the Lambda node.
                        tree = sort_lambda_decorators(tree)
                        lam.body = self.visit(lam.body)
                    else:
                        k = suggest_decorator_index("passthrough_lazy_args", tree.decorator_list)
                        # Force the decorators only after `suggest_decorator_index`
                        # has suggested us where to put ours.
                        # TODO: could make `suggest_decorator_index` ignore a `force()` wrapper.
                        tree.decorator_list = self.visit(tree.decorator_list)
                        if k is not None:
                            tree.decorator_list.insert(k, q[h[passthrough_lazy_args]])
                        else:
                            # passthrough_lazy_args should generally be as innermost as possible
                            # (so that e.g. the curry decorator will see the function as lazy)
                            tree.decorator_list.append(q[h[passthrough_lazy_args]])
                        tree.body = self.visit(tree.body)
                    return tree

            elif type(tree) is Call:
                def transform_arg(tree):
                    # add any needed force() invocations inside the tree,
                    # but leave the top level of simple references untouched.
                    isref = type(tree) in (Name, Attribute, Subscript)
                    self.withstate(tree, forcing_mode=("off" if isref else "full"))
                    tree = self.visit(tree)
                    if not isref:  # (re-)thunkify expr; a reference can be passed as-is.
                        tree = lazyrec(tree)
                    return tree

                def transform_starred(tree, dstarred=False):
                    isref = type(tree) in (Name, Attribute, Subscript)
                    self.withstate(tree, forcing_mode=("off" if isref else "full"))
                    tree = self.visit(tree)
                    # lazify items if we have a literal container
                    # we must avoid lazifying any other exprs, since a Lazy cannot be unpacked.
                    if is_literal_container(tree, maps_only=dstarred):
                        tree = lazyrec(tree)
                    return tree

                # let bindings have a role similar to function arguments, so auto-lazify there
                # (LHSs are always new names, so no infinite loop trap for the unwary)
                if islet(tree):
                    view = ExpandedLetView(tree)
                    if view.mode == "let":
                        for b in view.bindings.elts:  # b = (name, value)
                            b.elts[1] = transform_arg(b.elts[1])
                    else:  # view.mode == "letrec":
                        for b in view.bindings.elts:  # b = (name, (lambda e: ...))
                            thelambda = b.elts[1]
                            thelambda.body = transform_arg(thelambda.body)
                    if view.body:  # let decorators have no body inside the Call node
                        thelambda = view.body
                        thelambda.body = self.visit(thelambda.body)
                    return tree

                # namelambda() is used by let[] and do[]
                # Lazy() is a strict function, takes a lambda, constructs a Lazy object
                # _autoref_resolve doesn't need any special handling
                elif (isdo(tree) or is_decorator(tree.func, "namelambda") or
                      any(isx(tree.func, s) for s in _ctorcalls_all) or isx(tree.func, isLazy) or
                      any(isx(tree.func, s) for s in ("_autoref_resolve", "AutorefMarker"))):
                    # here we know the operator (.func) to be one of specific names;
                    # don't transform it to avoid confusing lazyrec[] (important if this
                    # is an inner call in the arglist of an outer, lazy call, since it
                    # must see any container constructor calls that appear in the args)
                    #
                    # TODO: correct forcing mode for `rec`? We shouldn't need to forcibly use "full",
                    # since maybe_force_args() already fully forces any remaining promises
                    # in the args when calling a strict function.
                    tree.args = self.visit(tree.args)
                    tree.keywords = self.visit(tree.keywords)
                    return tree

                else:
                    ln, co = tree.lineno, tree.col_offset
                    thefunc = self.visit(tree.func)

                    adata = []
                    for x in tree.args:
                        if type(x) is Starred:  # *args in Python 3.5+
                            v = transform_starred(x.value)
                            v = Starred(value=q[a[v]], lineno=ln, col_offset=co)
                        else:
                            v = transform_arg(x)
                        adata.append(v)

                    kwdata = []
                    for x in tree.keywords:
                        if x.arg is None:  # **kwargs in Python 3.5+
                            v = transform_starred(x.value, dstarred=True)
                        else:
                            v = transform_arg(x.value)
                        kwdata.append((x.arg, v))

                    # Construct the call
                    mycall = Call(func=q[h[maybe_force_args]],
                                  args=[q[a[thefunc]]] + [q[a[x]] for x in adata],
                                  keywords=[keyword(arg=k, value=q[a[x]]) for k, x in kwdata],
                                  lineno=ln, col_offset=co)
                    tree = mycall
                    return tree

            elif type(tree) is Subscript:  # force only accessed part of obj[...]
                self.withstate(tree.slice, forcing_mode="full")
                tree.slice = self.visit(tree.slice)
                # resolve reference to the actual container without forcing its items.
                self.withstate(tree.value, forcing_mode="flat")
                tree.value = self.visit(tree.value)
                tree = f(tree)
                return tree

            elif type(tree) is Attribute:
                #   a.b.c --> f(force1(force1(a).b).c)  (Load)
                #         -->   force1(force1(a).b).c   (Store)
                #   attr="c", value=a.b
                #   attr="b", value=a
                # Note in case of assignment to a compound, only the outermost
                # Attribute is in Store context.
                #
                # Recurse in flat mode. Consider lst = [[1, 2], 3]
                #   lst[0] --> f(force1(lst)[0]), but
                #   lst[0].append --> force1(force1(force1(lst)[0]).append)
                # Hence, looking up an attribute should only force **the object**
                # so that we can perform the attribute lookup on it, whereas
                # looking up values should finally f() the whole slice.
                # (In the above examples, we have omitted f() when it is identity;
                #  in reality there is always an f() around the whole expr.)
                self.withstate(tree.value, forcing_mode="flat")
                tree.value = self.visit(tree.value)
                tree = f(tree)
                return tree

            elif type(tree) is Name and type(tree.ctx) is Load:
                tree = f(tree)
                # must not recurse when a Name changes into a Call.
                return tree

            return self.generic_visit(tree)

    newbody = []
    for stmt in body:
        newbody.append(LazifyTransformer(forcing_mode="full").visit(stmt))

    # Pay-as-you-go: to avoid a drastic performance hit (~10x) in trampolines
    # built by unpythonic.tco.trampolined for regular strict code, a special mode
    # must be enabled to build lazify-aware trampolines.
    #
    # The idea is that the mode is enabled while any function definitions in the
    # "with lazify" block run, so they get a lazify-aware trampoline.
    # This should be determined lexically, but that's complicated to do API-wise,
    # so we currently enable the mode for the dynamic extent of the "with lazify".
    # Usually this is close enough; the main case where this can behave
    # unexpectedly is::
    #
    #     @trampolined  # strict trampoline
    #     def g():
    #         ...
    #
    #     def make_f():
    #         @trampolined  # which kind of trampoline is this?
    #         def f():
    #             ...
    #         return f
    #
    #     f1 = make_f()  # f1 gets the strict trampoline
    #
    #     with lazify:
    #         @trampolined  # lazify-aware trampoline
    #         def h():
    #             ...
    #
    #         f2 = make_f()  # f2 gets the lazify-aware trampoline
    #
    # TCO chains with an arbitrary mix of lazy and strict functions should work
    # as long as the first function in the chain has a lazify-aware trampoline,
    # because the chain runs under the trampoline of the first function.
    #
    # Tail-calling from a strict function into a lazy function should work, because
    # all arguments are evaluated at the strict side before the call is made.
    #
    # But tail-calling strict -> lazy -> strict will fail in some cases.
    # The second strict callee may get promises instead of values, because the
    # strict trampoline does not have the maybe_force_args (that usually forces the args
    # when lazy code calls into strict code).
    return wrapwith(item=q[h[dyn.let](_build_lazy_trampoline=True)],
                    body=newbody,
                    locref=body[0])

# -----------------------------------------------------------------------------
