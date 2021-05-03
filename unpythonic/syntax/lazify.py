# -*- coding: utf-8 -*-
"""Automatic lazy evaluation of function arguments."""

__all__ = ["lazy", "lazyrec", "lazify"]

from ast import (Lambda, FunctionDef, AsyncFunctionDef, Call, Name, Attribute,
                 Starred, keyword, List, Tuple, Dict, Set, Subscript, Load)
from functools import partial

from mcpyrate.quotes import macros, q, a, h  # noqa: F401

from mcpyrate.astfixers import fix_ctx
from mcpyrate.quotes import capture_as_macro, is_captured_value
from mcpyrate.walkers import ASTTransformer

from .util import (suggest_decorator_index, sort_lambda_decorators, detect_lambda,
                   isx, getname, is_decorator, wrapwith)
from .letdoutil import islet, isdo, ExpandedLetView
from .nameutil import is_unexpanded_expr_macro
from ..lazyutil import Lazy, passthrough_lazy_args, force, force1, maybe_force_args
from ..dynassign import dyn

# -----------------------------------------------------------------------------

# The `lazy` macro comes from `demo/promise.py` in `mcpyrate`.
def lazy(tree, *, syntax, **kw):
    """[syntax, expr] Delay an expression (lazy evaluation).

    This macro injects a lambda to delay evaluation, and encapsulates
    the result into a *promise* (an `unpythonic.lazyutil.Lazy` object).

    In Racket, this operation is known as `delay`.
    """
    if syntax != "expr":
        raise SyntaxError("lazy is an expr macro only")

    # Expand outside in. Ordering shouldn't matter here.
    return _lazy(tree)

def lazyrec(tree, *, syntax, **kw):
    """[syntax, expr] Delay items in a container literal, recursively.

    Essentially, this distributes ``lazy[]`` into the items inside a literal
    ``list``, ``tuple``, ``set``, ``frozenset``, ``unpythonic.collections.box``
    or ``unpythonic.llist.cons``, and into the values of a literal ``dict`` or
    ``unpythonic.collections.frozendict``.

    Because this is a macro and must work by names only, only this fixed set of
    container types is supported.

    The container itself is not lazified, only the items inside it are, to keep
    the lazification from interfering with unpacking. This allows things such as
    ``f(*lazyrec[(1*2*3, 4*5*6)])`` to work as expected.

    See also ``lazy[]`` (the effect on each item) and ``unpythonic.syntax.force``
    (the inverse of ``lazyrec[]``).

    For an atom, ``lazyrec[]`` has the same effect as ``lazy[]``::

        lazyrec[dostuff()] --> lazy[dostuff()]

    For a container literal, ``lazyrec[]`` descends into it::

        lazyrec[(2*21, 1/0)] --> (lazy[2*21], lazy[1/0])
        lazyrec[{'a': 2*21, 'b': 1/0}] --> {'a': lazy[2*21], 'b': lazy[1/0]}

    Constructor call syntax for container literals is also supported::

        lazyrec[list(2*21, 1/0)] --> [lazy[2*21], lazy[1/0]]

    Nested container literals (with any combination of known types) are
    processed recursively, for example::

        lazyrec[((2*21, 1/0), (1+2+3, 4+5+6))] --> ((lazy[2*21], lazy[1/0]),
                                                    (lazy[1+2+3], lazy[4+5+6]))
    """
    if syntax != "expr":
        raise SyntaxError("lazyrec is an expr macro only")

    # Expand outside in. Ordering shouldn't matter here.
    return _lazyrec(tree)

def lazify(tree, *, syntax, expander, **kw):
    """[syntax, block] Call-by-need for Python.

    In a ``with lazify`` block, function arguments are evaluated only when
    actually used, at most once each, and in the order in which they are
    actually used. Promises are automatically forced on access.

    Automatic lazification applies to arguments in function calls and to
    let-bindings, since they play a similar role. **No other binding forms
    are auto-lazified.**

    Automatic lazification uses the ``lazyrec[]`` macro, which recurses into
    certain types of container literals, so that the lazification will not
    interfere with unpacking. See its docstring for details.

    Comboing with other block macros in ``unpythonic.syntax`` is supported,
    including ``curry`` and ``continuations``.

    Silly contrived example::

        with lazify:
            def my_if(p, a, b):
                if p:
                    return a  # b never evaluated in this code path...
                else:
                    return b  # a never evaluated in this code path...

            # ...hence the divisions by zero here are never performed.
            assert my_if(True, 23, 1/0) == 23
            assert my_if(False, 1/0, 42) == 42

    Note ``my_if`` is a run-of-the-mill runtime function, not a macro. Only the
    ``with lazify`` is imbued with any magic.

    Like ``with continuations``, no state or context is associated with a
    ``with lazify`` block, so lazy functions defined in one block may call
    those defined in another. Calls between lazy and strict code are also
    supported (in both directions), without requiring any extra effort.

    Evaluation of each lazified argument is guaranteed to occur at most once;
    the value is cached. Order of evaluation of lazy arguments is determined
    by the (dynamic) order in which the lazy code actually uses them.

    Essentially, the above code expands into::

        from unpythonic.syntax import macros, lazy
        from unpythonic.syntax import force

        def my_if(p, a, b):
            if force(p):
                return force(a)
            else:
                return force(b)
        assert my_if(lazy[True], lazy[23], lazy[1/0]) == 23
        assert my_if(lazy[False], lazy[1/0], lazy[42]) == 42

    plus some clerical details to allow lazy and strict code to be mixed.

    Just passing through a lazy argument to another lazy function will
    not trigger evaluation, even when it appears in a computation inlined
    to the argument list::

        with lazify:
            def g(a, b):
                return a
            def f(a, b):
                return g(2*a, 3*b)
            assert f(21, 1/0) == 42

    The division by zero is never performed, because the value of ``b`` is
    not needed to compute the result (worded less magically, that promise is
    never forced in the code path that produces the result). Essentially,
    the above code expands into::

        from unpythonic.syntax import macros, lazy
        from unpythonic.syntax import force

        def g(a, b):
            return force(a)
        def f(a, b):
            return g(lazy[2*force(a)], lazy[3*force(b)])
        assert f(lazy[21], lazy[1/0]) == 42

    This relies on the magic of closures to capture f's ``a`` and ``b`` into
    the promises.

    But be careful; **assignments are not auto-lazified**, so the following does
    **not** work::

        with lazify:
            def g(a, b):
                return a
            def f(a, b):
                c = 3*b  # not in an arglist, b gets evaluated!
                return g(2*a, c)
            assert f(21, 1/0) == 42

    To avoid that, explicitly wrap the computation into a ``lazy[]``. For why
    assignment RHSs are not auto-lazified, see the section on pitfalls below.

    In calls, bare references (name, subscript, attribute) are detected and for
    them, re-thunking is skipped. For example::

        def g(a):
            return a
        def f(a):
            return g(a)
        assert f(42) == 42

    expands into::

        def g(a):
            return force(a)
        def f(a):
            return g(a)  # <-- no lazy[force(a)] since "a" is just a name
        assert f(lazy[42]) == 42

    When resolving references, subscripts and attributes are forced just enough
    to obtain the containing object from a promise, if any; for example, the
    elements of a list ``lst`` will not be evaluated just because the user code
    happens to use ``lst.append(...)``; this only forces the object ``lst``
    itself.

    A ``lst`` appearing by itself evaluates the whole list. Similarly, ``lst[0]``
    by itself evaluates only the first element, and ``lst[:-1]`` by itself
    evaluates all but the last element. The index expression in a subscript is
    fully forced, because its value is needed to determine which elements of the
    subscripted container are to be accessed.

    **Mixing lazy and strict code**

    Lazy code is allowed to call strict functions and vice versa, without
    requiring any additional effort.

    Keep in mind what this implies: when calling a strict function, any arguments
    given to it will be evaluated!

    In the other direction, when calling a lazy function from strict code, the
    arguments are evaluated by the caller before the lazy code gets control.
    The lazy code gets just the evaluated values.

    If you have, in strict code, an argument expression you want to pass lazily,
    use syntax like ``f(lazy[...], ...)``. If you accidentally do this in lazy
    code, it shouldn't break anything; ``with lazify`` detects any argument
    expressions that are already promises, and just passes them through.

    **Forcing promises manually**

    This is mainly useful if you ``lazy[]`` or ``lazyrec[]`` something explicitly,
    and want to compute its value outside a ``with lazify`` block.

    We provide the functions ``force1`` and ``force``.

    Using ``force1``, if ``x`` is a ``lazy[]`` promise, it will be forced,
    and the resulting value is returned. If ``x`` is not a promise,
    ``x`` itself is returned, à la Racket.

    The function ``force``, in addition, descends into containers (recursively).
    When an atom ``x`` (i.e. anything that is not a container) is encountered,
    it is processed using ``force1``.

    Mutable containers are updated in-place; for immutables, a new instance is
    created. Any container with a compatible ``collections.abc`` is supported.
    (See ``unpythonic.collections.mogrify`` for details.) In addition, as
    special cases ``unpythonic.collections.box`` and ``unpythonic.llist.cons``
    are supported.

    **Tips, tricks and pitfalls**

    You can mix and match bare data values and promises, since ``force(x)``
    evaluates to ``x`` when ``x`` is not a promise.

    So this is just fine::

        with lazify:
            def f(x):
                x = 2*21  # assign a bare data value
                print(x)  # the implicit force(x) evaluates to x
            f(17)

    If you want to manually introduce a promise, use ``lazy[]``::

        from unpythonic.syntax import macros, lazify, lazy

        with lazify:
            def f(x):
                x = lazy[2*21]  # assign a promise
                print(x)        # the implicit force(x) evaluates the promise
            f(17)

    If you have a container literal and want to lazify it recursively in a
    position that does not auto-lazify, use ``lazyrec[]`` (see its docstring
    for details)::

        from unpythonic.syntax import macros, lazify, lazyrec

        with lazify:
            def f(x):
                return x[:-1]
            lst = lazyrec[[1, 2, 3/0]]
            assert f(lst) == [1, 2]

    For non-literal containers, use ``lazy[]`` for each item as appropriate::

        def f(lst):
            lst.append(lazy["I'm lazy"])
            lst.append(lazy["Don't call me lazy, I'm just evaluated later!"])

    Keep in mind, though, that ``lazy[]`` will introduce a lambda, so there's
    the usual pitfall::

        from unpythonic.syntax import macros, lazify, lazy

        with lazify:
            lst = []
            for x in range(3):       # DANGER: only one "x", mutated imperatively
                lst.append(lazy[x])  # all these closures capture the same "x"
            print(lst[0])  # 2
            print(lst[1])  # 2
            print(lst[2])  # 2

    So to capture the value instead of the name, use the usual workaround,
    the wrapper lambda (here written more readably as a let, which it really is)::

        from unpythonic.syntax import macros, lazify, lazy, let

        with lazify:
            lst = []
            for x in range(3):
                lst.append(let[(y, x) in lazy[y]])
            print(lst[0])  # 0
            print(lst[1])  # 1
            print(lst[2])  # 2

    Be careful not to ``lazy[]`` or ``lazyrec[]`` too much::

        with lazify:
            a = 10
            a = lazy[2*a]  # 20, right?
            print(a)       # crash!

    Why does this example crash? The expanded code is::

        with lazify:
            a = 10
            a = lazy[2*force(a)]
            print(force(a))

    The ``lazy[]`` sets up a promise, which will force ``a`` *at the time when
    the containing promise is forced*, but at that time the name ``a`` points
    to a promise, which will force...

    The fundamental issue is that ``a = 2*a`` is an imperative update; if you
    need to do that, just let Python evaluate the RHS normally (i.e. use the
    value the name ``a`` points to *at the time when the RHS runs*).

    Assigning a lazy value to a new name evaluates it, because any read access
    triggers evaluation::

        with lazify:
            def g(x):
                y = x       # the "x" on the RHS triggers the implicit force
                print(y)    # bare data value
            f(2*21)

    Inspired by Haskell, Racket's (delay) and (force), and lazy/racket.

    **Combos**

    Introducing the *HasThon* programming language (it has 100% more Thon than
    popular brands)::

        with autocurry, lazify:  # or continuations, autocurry, lazify if you want those
            def add2first(a, b, c):
                return a + b
            assert add2first(2)(3)(1/0) == 5

            def f(a, b):
                return a
            assert let[((c, 42),
                        (d, 1/0)) in f(c)(d)] == 42
            assert letrec[((c, 42),
                           (d, 1/0),
                           (e, 2*c)) in f(e)(d)] == 84

            assert letrec[((c, 42),
                           (d, 1/0),
                           (e, 2*c)) in [local[x << f(e)(d)],
                                         x/4]] == 21

    Works also with continuations. Rules:

      - Also continuations are transformed into lazy functions.

      - ``cc`` built by chain_conts is treated as lazy, **itself**; then it's
        up to the continuations chained by it to decide whether to force their
        arguments.

      - The default continuation ``identity`` is strict, so that return values
        from a continuation-enabled computation will be forced.

    Example::

        with continuations, lazify:
            k = None
            def setk(*args, cc):
                nonlocal k
                k = cc
                return args[0]
            def doit():
                lst = ['the call returned']
                *more, = call_cc[setk('A', 1/0)]
                return lst + [more[0]]
            assert doit() == ['the call returned', 'A']
            assert k('again') == ['the call returned', 'again']
            assert k('thrice', 1/0) == ['the call returned', 'thrice']

    For a version with comments, see ``unpythonic/syntax/test/test_lazify.py``.

    **CAUTION**: Call-by-need is a low-level language feature that is difficult
    to bolt on after the fact. Some things might not work.

    **CAUTION**: The functions in ``unpythonic.fun`` are lazify-aware (so that
    e.g. curry and compose work with lazy functions), as are ``call`` and
    ``callwith`` in ``unpythonic.misc``, but the rest of ``unpythonic`` is not.

    **CAUTION**: Argument passing by function call, and let-bindings are
    currently the only binding constructs to which auto-lazification is applied.
    """
    if syntax != "block":
        raise SyntaxError("lazify is a block macro only")
    if syntax == "block" and kw['optional_vars'] is not None:
        raise SyntaxError("lazify does not take an asname")

    # Two-pass macro.
    with dyn.let(_macro_expander=expander):
        return _lazify(body=tree)

# -----------------------------------------------------------------------------

# lazy: syntax transformer, lazify a single expression
def _lazy(tree):
    return q[h[Lazy](lambda: a[tree])]

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

_unexpanded_lazy_name = "lazy"
_expanded_lazy_name = "Lazy"
_our_lazy = capture_as_macro(lazy)
def _lazyrec(tree):
    is_unexpanded_lazy = partial(is_unexpanded_expr_macro, lazy, dyn._macro_expander)

    # This helper doesn't need to recurse, so we don't need `ASTTransformer` here.
    def transform(tree):
        if type(tree) in (Tuple, List, Set):
            tree.elts = [rec(x) for x in tree.elts]
        elif type(tree) is Dict:
            tree.values = [rec(x) for x in tree.values]
        elif type(tree) is Call and any(isx(tree.func, ctor) for ctor in _ctorcalls_all):
            p, k = _ctor_handling_modes[getname(tree.func)]
            lazify_ctorcall(tree, p, k)
        elif is_unexpanded_lazy(tree):
            pass
        elif type(tree) is Call and isx(tree.func, _expanded_lazy_name):
            pass
        else:
            # `mcpyrate` supports hygienic macro capture, so we can just splice
            # hygienic `lazy` invocations here.
            tree = q[a[_our_lazy][a[tree]]]
        return tree

    def lazify_ctorcall(tree, positionals="all", keywords="all"):
        if getname(tree.func) in _ctorcalls_that_take_exactly_one_positional_arg and len(tree.args) > 1:
            raise SyntaxError(f"lazyrec[]: while analyzing constructor call `{getname(tree.func)}`: there should be exactly one argument, but {len(tree.args)} were given.")  # pragma: no cover

        newargs = []
        for arg in tree.args:
            if type(arg) is Starred:  # *args in Python 3.5+
                if _is_literal_container(arg.value, maps_only=False):
                    arg.value = rec(arg.value)
                # else do nothing
            elif positionals == "all" or _is_literal_container(arg, maps_only=False):  # single positional arg
                arg = rec(arg)
            newargs.append(arg)
        tree.args = newargs
        for kw in tree.keywords:
            if kw.arg is None:  # **kwargs in Python 3.5+
                if _is_literal_container(kw.value, maps_only=True):
                    kw.value = rec(kw.value)
                # else do nothing
            elif keywords == "all" or _is_literal_container(kw.value, maps_only=True):  # single named arg
                kw.value = rec(kw.value)

    rec = transform
    return rec(tree)

def _is_literal_container(tree, maps_only=False):
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

def _lazify(body):
    # first pass, outside-in
    userlambdas = detect_lambda(body)

    # Expand any inner macro invocations. Particularly, this expands away any `lazyrec[]` and `lazy[]`
    # so they become easier to work with. We also know that after this, any `Subscript` is really a
    # subscripting operation and not a macro invocation.
    body = dyn._macro_expander.visit(body)

    # `lazify`'s analyzer needs the `ctx` attributes in `tree` to be filled in correctly.
    body = fix_ctx(body, copy_seen_nodes=False)  # TODO: or maybe copy seen nodes?

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

            # Hygienic captures must be treated separately:
            if is_captured_value(tree):
                if forcing_mode in ("full", "flat"):
                    return q[h[force](a[tree])]
                # else forcing_mode == "off"
                return tree

            elif type(tree) in (FunctionDef, AsyncFunctionDef, Lambda):
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
                # We don't need to expand in the output of `_lazyrec`,
                # because we don't recurse further into the args of the call,
                # so the `lazify` transformer never sees the confusing `Subscript`
                # instances that are actually macro invocations for `lazy[]`.
                def transform_arg(tree):
                    # add any needed force() invocations inside the tree,
                    # but leave the top level of simple references untouched.
                    isref = type(tree) in (Name, Attribute, Subscript)
                    self.withstate(tree, forcing_mode=("off" if isref else "full"))
                    tree = self.visit(tree)
                    if not isref:  # (re-)thunkify expr; a reference can be passed as-is.
                        tree = _lazyrec(tree)
                    return tree

                def transform_starred(tree, dstarred=False):
                    isref = type(tree) in (Name, Attribute, Subscript)
                    self.withstate(tree, forcing_mode=("off" if isref else "full"))
                    tree = self.visit(tree)
                    # lazify items if we have a literal container
                    # we must avoid lazifying any other exprs, since a Lazy cannot be unpacked.
                    if _is_literal_container(tree, maps_only=dstarred):
                        tree = _lazyrec(tree)
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
                      any(isx(tree.func, s) for s in _ctorcalls_all) or isx(tree.func, _expanded_lazy_name) or
                      any(isx(tree.func, s) for s in ("_autoref_resolve", "ExpandedAutorefMarker"))):
                    # here we know the operator (.func) to be one of specific names;
                    # don't transform it to avoid confusing lazyrec[] (important if this
                    # is an inner call in the arglist of an outer, lazy call, since it
                    # must see any container constructor calls that appear in the args)
                    #
                    # TODO: correct forcing mode for recursion? We shouldn't need to forcibly use "full",
                    # since maybe_force_args() already fully forces any remaining promises
                    # in the args when calling a strict function.
                    tree.args = self.visit(tree.args)
                    tree.keywords = self.visit(tree.keywords)
                    return tree

                else:
                    thefunc = self.visit(tree.func)

                    adata = []
                    for x in tree.args:
                        if type(x) is Starred:  # *args in Python 3.5+
                            v = transform_starred(x.value)
                            v = Starred(value=q[a[v]])
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
                                  keywords=[keyword(arg=k, value=q[a[x]]) for k, x in kwdata])
                    tree = mycall
                    return tree

            # NOTE: We must expand all inner macro invocations before we hit this, or we'll produce nonsense.
            # Hence it is easiest to have `lazify` expand inside-out.
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
                    body=newbody)

# -----------------------------------------------------------------------------
