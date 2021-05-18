# -*- coding: utf-8 -*-
"""Missing batteries for functools.

Some features modelled after Racket's builtins for handling procedures.
  https://docs.racket-lang.org/reference/procedures.html

Memoize is typical FP (Racket has it in mischief), and flip comes from Haskell.
"""

__all__ = ["memoize", "curry", "iscurried",
           "flip", "rotate",
           "apply", "identity", "const",
           "notf", "andf", "orf",
           "composer1", "composel1", "composer1i", "composel1i",  # single arg
           "composer", "composel", "composeri", "composeli",   # multi-arg
           "composerc", "composelc", "composerci", "composelci",  # multi-arg w/ curry
           "to1st", "to2nd", "tokth", "tolast", "to",
           "withself"]

from functools import wraps, partial as functools_partial
from typing import get_type_hints

from .arity import (arities, _resolve_bindings, tuplify_bindings,
                    UnknownArity)
from .fold import reducel
from .dispatch import (isgeneric, _resolve_multimethod, _format_callable,
                       _get_argument_type_mismatches, _raise_multiple_dispatch_error,
                       _list_multimethods, _extract_self_or_cls)
from .dynassign import dyn, make_dynvar
from .regutil import register_decorator
from .symbol import sym

# we use @passthrough_lazy_args (and handle possible lazy args) to support unpythonic.syntax.lazify.
from .lazyutil import passthrough_lazy_args, islazy, force, force1, maybe_force_args

_success = sym("_success")
_fail = sym("_fail")
@register_decorator(priority=10)
def memoize(f):
    """Decorator: memoize the function f.

    All of the args and kwargs of ``f`` must be hashable.

    Any exceptions raised by ``f`` are also memoized. If the memoized function
    is invoked again with arguments with which ``f`` originally raised an
    exception, *the same exception instance* is raised again.

    **CAUTION**: ``f`` must be pure (no side effects, no internal state
    preserved between invocations) for this to make any sense.
    """
    memo = {}
    @wraps(f)
    def memoized(*args, **kwargs):
        k = tuplify_bindings(_resolve_bindings(f, args, kwargs, _partial=False))
        if k not in memo:
            try:
                result = (_success, maybe_force_args(f, *args, **kwargs))
            except BaseException as err:
                result = (_fail, err)
            memo[k] = result  # should yell separately if k is not a valid key
        kind, value = memo[k]
        if kind is _fail:
            raise value
        return value
    if islazy(f):
        memoized = passthrough_lazy_args(memoized)
    return memoized

#def memoize_simple(f):  # essential idea, without exception handling
#    memo = {}
#    @wraps(f)
#    def memoized(*args, **kwargs):
#        k = tuplify_bindings(resolve_bindings(f, *args, **kwargs))
#        if k not in memo:
#            memo[k] = f(*args, **kwargs)
#        return memo[k]
#    return memoized

# Parameter naming is consistent with `functools.partial`.
#
# Note standard behavior of `functools.partial`: `kwargs` do not disappear from the call
# signature even if partially applied. The same kwarg can be sent multiple times, with the
# latest application winning. We must resist the temptation to override that behavior here,
# because there are other places in the stdlib, particularly `inspect._signature_get_partial`
# (as of Python 3.8), that expect the standard semantics.
def partial(func, *args, **kwargs):
    """Wrapper over `functools.partial` that type-checks the arguments against the type annotations on `func`.

    The type annotations may use features from the `typing` stdlib module.
    See `unpythonic.typecheck.isoftype` for details.

    Trying to pass an argument of a type that does not match the corresponding
    parameter's type specification raises `TypeError` immediately.

    Note the check still occurs at run time, but at the use site of `partial`,
    when the partially applied function is constructed. This makes it fail-faster
    than an `isinstance` check inside the function.

    To conveniently make regular calls of the function type-check arguments, too,
    see the decorator `unpythonic.dispatch.typed`.
    """
    # HACK: As of Python 3.8, `typing.get_type_hints` does not know about `functools.partial` objects,
    # HACK: but those objects have `args` and `keywords` attributes, so we can extract what we need.
    # TODO: Remove this hack if `typing.get_type_hints` gets support for `functools.partial` at some point.
    if isinstance(func, functools_partial):
        thecallable = func.func
        collected_args = func.args + args
        collected_kwargs = {**func.keywords, **kwargs}
    else:
        thecallable = func
        collected_args = args
        collected_kwargs = kwargs

    if isgeneric(thecallable):  # multiple dispatch
        # For generic functions, at least one multimethod must match the partial signature
        # for the partial application to be valid.
        if not _resolve_multimethod(thecallable, collected_args, collected_kwargs, _partial=True):
            _raise_multiple_dispatch_error(thecallable, collected_args, collected_kwargs,
                                           candidates=_list_multimethods(thecallable,
                                                                         _extract_self_or_cls(thecallable,
                                                                                              args)),
                                           _partial=True)
    else:  # Not `@generic` or `@typed`; just a function that has type annotations.
        # It's not very unpythonic-ic to provide this since we already have `@typed` for this use case,
        # but it's much more pythonic, if the type-checking `partial` works properly for code that does
        # not opt in to `unpythonic`'s multiple-dispatch subsystem.
        # TODO: There's some repeated error-reporting code in `unpythonic.dispatch`.
        type_signature = get_type_hints(thecallable)
        if type_signature:  # TODO: Python 3.8+: use walrus assignment here
            bound_arguments = _resolve_bindings(func, collected_args, collected_kwargs, _partial=True)
            # TODO: Allow having some parameters without type annotations. Requiring them for all
            # TODO: parameters is a `@generic`-ism (because it uses them for dispatching).
            # TODO: Alternatively, generalize `@generic` to ignore types for arguments whose parameters
            # TODO: have no type annotation. But as said in the comments, that could be a footgun.
            mismatches = _get_argument_type_mismatches(type_signature, bound_arguments)
            if mismatches:
                description = _format_callable(func)
                mismatches_list = [f"{parameter}={repr(value)}, expected {expected_type}"
                                       for parameter, value, expected_type in mismatches]
                mismatches_str = "; ".join(mismatches_list)
                raise TypeError(f"When partially applying {description}:\nParameter binding(s) do not match type specification: {mismatches_str}")

    # `functools.partial` already handles chaining partial applications, so send only the new args/kwargs to it.
    return functools_partial(func, *args, **kwargs)

make_dynvar(curry_context=[])
@passthrough_lazy_args
def _currycall(f, *args, **kwargs):
    """Co-operate with unpythonic.syntax.curry.

    In a ``with autocurry`` block, we need to call `f` also when ``f()`` has
    transformed to ``curry(f)``, but definitions can be curried as usual.

    Hence we provide this separate mode to curry-and-call even if no args.

    This mode no-ops when ``f`` is not inspectable, instead of raising
    an ``unpythonic.arity.UnknownArity`` exception.
    """
    return curry(f, *args, _curry_force_call=True, _curry_allow_uninspectable=True, **kwargs)

@register_decorator(priority=8)
@passthrough_lazy_args
def curry(f, *args, _curry_force_call=False, _curry_allow_uninspectable=False, **kwargs):
    """Decorator: curry the function f.

    Essentially, the resulting function automatically chains partial application
    until all parameters of ``f`` are bound, at which point ``f`` is called.

    For a callable to be curryable, its signature must be inspectable by the stdlib
    function `inspect.signature`. In some versions of Python, inspection may fail
    for builtin functions or methods such as ``print``, ``range``, ``operator.add``,
    or ``list.append``.

    **CAUTION**: Up to v0.14.3, we looked at positional arity only, and there were
    workarounds in place for some of the most common builtins. As of v0.15.0, we
    compute argument bindings like Python itself does. Hence we use a different
    algorithm, and thus a *different subset* of builtins may have become uninspectable.

    When inspection fails, we raise ``unpythonic.arity.UnknownArity``.

    **Examples**::

        @curry
        def add3(a, b, c):
            return a + b + c
        assert add3(1)(2)(3) == 6

        # actually uses partial application so these work, too
        assert add3(1, 2)(3) == 6
        assert add3(1)(2, 3) == 6
        assert add3(1, 2, 3) == 6

        @curry
        def lispyadd(*args):
            return sum(args)
        assert lispyadd() == 0  # no args is a valid arity here

        @curry
        def foo(a, b, *, c, d):
            return a, b, c, d
        assert foo(5, c=23)(17, d=42) == (5, 17, 23, 42)

    **Passthrough**:

    If too many args are given, any extra ones are passed through on the right.
    If an intermediate result is callable, it is invoked on the remaining
    positional args::

        map_one = lambda f: (curry(foldr))(composer(cons, to1st(f)), nil)
        assert curry(map_one)(double, ll(1, 2, 3)) == ll(2, 4, 6)

    In the above example, ``map_one`` has arity 1, so the arg ``ll(1, 2, 3)``
    is extra. The result of ``map_one`` is a callable, so it is then
    invoked on this tuple.

    For simplicity, in passthrough, all kwargs are consumed in the first step
    for which too many positional args were supplied.

    By default, if any passed-through positional args are still remaining when
    the currently top-level curry context exits, ``curry`` raises ``TypeError``,
    because such usage often indicates a bug.

    This behavior can be locally modified by setting the dynvar
    ``curry_context``, which is a list representing the stack of
    currently active curry contexts. A context is any object,
    a human-readable label is fine::

        with dyn.let(curry_context=["whatever"]):
            curry(double, 2, "foo") == (4, "foo")

    Because it is a dynvar, it affects all ``curry`` calls in its dynamic extent,
    including ones inside library functions such as ``composerc`` or ``pipec``.

    **Curry itself is curried**:

    When invoked as a regular function (not decorator), curry itself is curried.
    If any arguments are provided beside ``f``, then they are the first step.
    This helps eliminate many parentheses::

        map_one = lambda f: curry(foldr, composer(cons, to1st(f)), nil)

    This comboes with passthrough::

        mymap = lambda f: curry(foldr, composerc(cons, f), nil)
        add = lambda x, y: x + y
        assert curry(mymap, add, ll(1, 2, 3), ll(4, 5, 6)) == ll(5, 7, 9)

        from functools import partial
        from unpythonic import curry, composel, drop, take

        with_n = lambda *args: (partial(f, n) for n, f in args)
        clip = lambda n1, n2: composel(*with_n((n1, drop), (n2, take)))
        assert tuple(curry(clip, 5, 10, range(20))) == tuple(range(5, 15))

    **Kwargs support**:

    As of v0.15.0, `curry` supports passing arguments by name at any step during the currying.

    We collect both `args` and `kwargs` across all steps, and bind arguments to function
    parameters the same way Python itself does, so it shouldn't matter whether the function
    parameters end up bound by position or name. When all parameters have a binding, the call
    triggers.

    That means, for example, that this now works as expected::

        @curry
        def f(x, y):
            return x, y

        assert f(y=2)(x=1) == (1, 2)

    However, it is possible that the algorithm isn't perfect, so there may be small semantic
    differences to regular one-step function calls. If you find any, please file an issue,
    so these can at the very least be documented; and if doable with reasonable effort,
    preferably fixed.

    It is still an error if named arguments are left over when the top-level curry context
    is reached. Treating this case would require generalizing return values so that functions
    could return named outputs. See:
        https://github.com/Technologicat/unpythonic/issues/32
    """
    f = force(f)  # lazify support: we need the value of f
    # trivial case first: interaction with call_ec and other replace-def-with-value decorators
    if not callable(f):
        return f
    # trivial case first: prevent stacking curried wrappers
    if iscurried(f):
        if args or kwargs or _curry_force_call:
            return maybe_force_args(f, *args, **kwargs)
        return f

    def fallback():  # what to do if inspection fails
        if not _curry_allow_uninspectable:  # usual behavior
            raise
        # co-operate with unpythonic.syntax.autocurry; don't crash on builtins
        if args or kwargs or _curry_force_call:
            return maybe_force_args(f, *args, **kwargs)
        return f

    try:
        min_arity, max_arity = arities(f)
    except UnknownArity:  # likely a builtin
        return fallback()

    @wraps(f)
    def curried(*args, **kwargs):
        outerctx = dyn.curry_context
        with dyn.let(curry_context=(outerctx + [f])):
            # In order to decide what to do when the curried function is called, we first compute the
            # parameter bindings.
            #
            # All of `f`'s parameters should be bound (whether by position or by name) before calling `f`.
            #
            # `functools.partial()` doesn't remove an already-set kwarg from the signature (as seen by
            # `inspect.signature`, used by `unpythonic.arity.arities`), but `functools.partial` objects
            # have a `keywords` attribute, which contains what we want.
            #
            # To support kwargs properly, we must compute argument bindings anyway, so we also use the
            # `func` and `args` attributes. This allows us to compute the bindings against the original
            # function.
            if isinstance(f, functools_partial):
                function = f.func
                collected_args = f.args + args
                collected_kwargs = {**f.keywords, **kwargs}
            else:
                function = f
                collected_args = args
                collected_kwargs = kwargs

            # The `type_signature` is used for `@generic` and `@typed` functions.
            def match_arguments(thecallable, type_signature=None):
                try:
                    bound_arguments = _resolve_bindings(thecallable, collected_args,
                                                        collected_kwargs, _partial=False)
                except TypeError as err:
                    # TODO: Searching the error message for a particular text snippet is a big HACK,
                    # TODO: but we need to know *why* the arguments could not be bound.
                    msg = err.args[0]
                    if "too many" in msg:  # too many positional args supplied
                        return "too many args"
                    elif "unexpected" in msg:  # unexpected named arg supplied
                        return "unexpected kwarg"
                    elif "missing" in msg:  # at least one parameter not bound
                        return "unbound parameter"
                    elif "multiple values" in msg:  # attempted to bind a parameter to more than one value
                        # This is a `TypeError` for regular calls, too, so let it propagate.
                        raise
                    else:  # we should have accounted for all cases  # pragma: no cover
                        raise NotImplementedError from err
                else:
                    # The parameter types in the call signature affect multiple-dispatching,
                    # so we must type-check, too.
                    if not type_signature or not _get_argument_type_mismatches(type_signature, bound_arguments):
                        return "ok"
                    return "argument type mismatch"
                return bound_arguments  # error code

            # `@generic` functions have several call signatures, so we must aggregate the results
            # in some sensible way to decide what to do. For non-generics, there's just one call signature.
            try:
                if not isgeneric(function):
                    status = match_arguments(function)
                else:
                    results = set()
                    # We can't use the public `list_methods` here, because on OOP methods,
                    # decorators live on the unbound method (raw function). Thus we must
                    # extract `self`/`cls` from the arguments of the call (for linked
                    # dispatcher lookup in the MRO).
                    multimethods = _list_multimethods(function,
                                                      _extract_self_or_cls(function,
                                                                           collected_args))
                    for thecallable, type_signature in multimethods:
                        result = match_arguments(thecallable, type_signature)
                        results.add(result)
                        if result == "ok":
                            break
                    # Any multimethod that can bind all collected args and kwargs (without type errors)
                    # is a match; prefer that first.
                    if "ok" in results:
                        status = "ok"
                    # No match. Figure out if we have too few or too many args/kwargs.
                    # If at least one multimethod can accept more args or kwargs, prefer that next.
                    elif "unbound parameter" in results:
                        status = "unbound parameter"
                    # Then prefer the case with too many positionals (and hope there aren't unexpected kwargs, too).
                    elif "too many args" in results:
                        status = "too many args"
                    elif "unexpected kwarg" in results or "argument type mismatch" in results:
                        _raise_multiple_dispatch_error(function, collected_args, collected_kwargs,
                                                       candidates=multimethods, _partial=True)
                    else:  # all cases should be accounted for  # pragma: no cover
                        assert False
            except ValueError as err:  # inspect.Signature.bind(), via our _resolve_bindings()
                msg = err.args[0]
                if "no signature found" in msg:
                    return fallback()
                raise

            if status == "unbound parameter":  # at least one parameter not bound yet; wait for more args/kwargs
                # Fail-fast: use our `partial` wrapper to type-check the partial call signature
                # when we build the curried function. It delegates to `functools.partial` if the
                # type check passes, and else raises a `TypeError` immediately.
                p = partial(f, *args, **kwargs)
                if islazy(f):
                    p = passthrough_lazy_args(p)
                return curry(p)

            # Too many positional args; passthrough on right, like https://github.com/Technologicat/spicy
            elif status == "too many args":
                # TODO: The uniform thing to do would be to pass on any arguments that weren't
                # TODO: bound to any parameter, regardless if they were passed positionally or by name.
                now_args, later_args = args[:max_arity], args[max_arity:]
                now_result = maybe_force_args(f, *now_args, **kwargs)  # use up all kwargs now
                now_result = force(now_result) if not isinstance(now_result, tuple) else force1(now_result)
                if callable(now_result):
                    # curry it now, to sustain the chain in case we have
                    # too many (or too few) args for it.
                    if not iscurried(now_result):
                        now_result = curry(now_result)
                    return now_result(*later_args)
                if not outerctx:
                    raise TypeError(f"Top-level curry context exited with {len(later_args)} arg(s) remaining: {later_args}")
                # pass through to the curried procedure waiting in outerctx
                # (e.g. in a curried compose chain)
                if isinstance(now_result, tuple):
                    return now_result + later_args
                return (now_result,) + later_args

            # Unexpected kwarg, could not be bound to any parameter
            elif status == "unexpected kwarg":
                # TODO: report the unexpected kwarg(s)
                raise NotImplementedError("curry: cannot pass-through unexpected named args")

            # All parameters bound to some arg or kwarg
            assert status == "ok", status
            return maybe_force_args(f, *args, **kwargs)
    if islazy(f):
        curried = passthrough_lazy_args(curried)
    curried._is_curried_function = True  # stash for detection
    # curry itself is curried: if we get args, they're the first step
    if args or kwargs or _curry_force_call:
        return maybe_force_args(curried, *args, **kwargs)
    return curried

def iscurried(f):
    """Return whether f is a curried function."""
    return hasattr(f, "_is_curried_function")

#def curry_simple(f):  # essential idea, without the extra features
#    min_arity, _ = arities(f)
#    @wraps(f)
#    def curried(*args, **kwargs):
#        if len(args) < min_arity:
#            return curry(partial(f, *args, **kwargs))
#        return f(*args, **kwargs)
#    return curried

def flip(f):
    """Decorator: flip (reverse) the positional arguments of f."""
    @ wraps(f)
    def flipped(*args, **kwargs):
        return maybe_force_args(f, *reversed(args), **kwargs)
    if islazy(f):
        flipped = passthrough_lazy_args(flipped)
    return flipped

def rotate(k):
    """Decorator (factory): cycle positional arg slots of f to the right by k places.

    Negative values cycle to the left.

    Note this (conceptually) shifts the slots, not the incoming argument values.

    **Examples**::

        # (a, b, c) -> (b, c, a), so b=1, c=2, a=3 in return (a, b, c)
        assert (rotate(-1)(identity))(1, 2, 3) == (3, 1, 2)

        # (a, b, c) -> (c, a, b), so c=1, a=2, b=3 in return (a, b, c)
        assert (rotate(1)(identity))(1, 2, 3) == (2, 3, 1)
    """
    def rotate_k(f):
        @ wraps(f)
        def rotated(*args, **kwargs):
            n = len(args)
            if not n:
                raise TypeError("Expected at least one argument")
            if not -n < k < n:  # standard semantics for negative indices
                raise IndexError(f"Should have -n < k < n, but n = len(args) = {n}, and k = {k}")
            j = -k % n
            rargs = args[-j:] + args[:-j]
            return maybe_force_args(f, *rargs, **kwargs)
        if islazy(f):
            rotated = passthrough_lazy_args(rotated)
        return rotated
    return rotate_k

@ passthrough_lazy_args
def apply(f, arg0, *more, **kwargs):
    """Scheme/Racket-like apply.

    Not really needed since Python has *, but included for completeness.
    Useful if using the ``prefix`` macro from ``unpythonic.syntax``.

    ``f`` is a function.

    ``arg0``, if alone, is the list to unpack.

    Otherwise the last item of ``more`` is the list to unpack. Any earlier
    arguments (starting from ``arg0``) are concatenated at the front.

    The ``**kwargs`` are passed to `f`, allowing to pass also named arguments.
    """
    f = force(f)
    if not more:
        args, lst = (), tuple(arg0)
    else:
        args = (arg0,) + more[:-1]
        lst = tuple(more[-1])
    return maybe_force_args(f, *(args + lst), **kwargs)

# Not marking this as lazy-aware works better with continuations (since this
# is the default cont, and return values should be values, not lazy[])
def identity(*args):
    """Identity function.

    Accepts any positional arguments, and returns them.

    Packs into a tuple if there is more than one.

    Example::

        assert identity(1, 2, 3) == (1, 2, 3)
        assert identity(42) == 42
        assert identity() is None
    """
    if not args:
        return None
    return args if len(args) > 1 else args[0]

# In lazify, return values are always just values, so we have to force args
# to compute the return value; as a shortcut, just don't mark this as lazy.
def const(*args):
    """Constant function.

    Returns a function that accepts any arguments (also kwargs)
    and returns the args given here (packed into a tuple if more than one).

    Example::

        c = const(1, 2, 3)
        assert c(42, "foo") == (1, 2, 3)
        assert c("anything") == (1, 2, 3)
        assert c() == (1, 2, 3)

        c = const(42)
        assert c("anything") == 42

        c = const()
        assert c("anything") is None
    """
    if not args:
        ret = None
    else:
        ret = args if len(args) > 1 else args[0]
    def constant(*a, **kw):
        return ret
    return constant

def notf(f):  # Racket: negate
    """Return a function that returns the logical not of the result of f.

    Examples::

        assert notf(lambda x: 2*x)(3) is False
        assert notf(lambda x: 2*x)(0) is True
    """
    def negated(*args, **kwargs):
        return not maybe_force_args(f, *args, **kwargs)
    if islazy(f):
        negated = passthrough_lazy_args(negated)
    return negated

def andf(*fs):  # Racket: conjoin
    """Return a function that conjoins calls to fs with "and".

    Each function in ``fs`` is called with the same ``args`` and ``kwargs``,
    provided when the conjoined function is called.

    Evaluation short-circuits at the first falsey term, if any, returning ``False``.
    If all terms are truthy, the final return value (from the last function in
    ``fs``) is returned.

    Examples::

        assert andf(lambda x: isinstance(x, int), lambda x: x % 2 == 0)(42) is True
        assert andf(lambda x: isinstance(x, int), lambda x: x % 2 == 0)(43) is False
    """
    def conjoined(*args, **kwargs):
        b = True
        for f in fs:
            b = b and maybe_force_args(f, *args, **kwargs)
            if not b:
                return False
        return b
    if all(islazy(f) for f in fs):
        conjoined = passthrough_lazy_args(conjoined)
    return conjoined

def orf(*fs):  # Racket: disjoin
    """Return a function that disjoins calls to fs with "or".

    Each function in ``fs`` is called with the same ``args`` and ``kwargs``,
    provided when the disjoined function is called.

    Evaluation short-circuits at the first truthy term, if any, and it is returned.
    If all terms are falsey, the return value is False.

    Examples::

        isstr  = lambda s: isinstance(s, str)
        iseven = lambda x: isinstance(x, int) and x % 2 == 0
        assert orf(isstr, iseven)(42) is True
        assert orf(isstr, iseven)("foo") is True
        assert orf(isstr, iseven)(None) is False  # neither condition holds
    """
    def disjoined(*args, **kwargs):
        b = False
        for f in fs:
            b = b or maybe_force_args(f, *args, **kwargs)
            if b:
                return b
        return False
    if all(islazy(f) for f in fs):
        disjoined = passthrough_lazy_args(disjoined)
    return disjoined

def _make_compose1(direction):  # "left", "right"
    def compose1_two(f, g):
        # return lambda x: f(g(x))
        return lambda x: maybe_force_args(f, maybe_force_args(g, x))
    if direction == "right":
        compose1_two = flip(compose1_two)
    def compose1(fs):
        # direction == "left" (leftmost is innermost):
        #   input: a b c
        #   elt = b -> f, acc = a(x) -> g --> b(a(x))
        #   elt = c -> f, acc = b(a(x)) -> g --> c(b(a(x)))
        # direction == "right" (rightmost is innermost):
        #   input: a b c
        #   elt = b -> g, acc = a(x) -> f --> a(b(x))
        #   elt = c -> g, acc = a(b(x)) -> f --> a(b(c(x)))
        # Using reducel is particularly nice here:
        #  - if fs is empty, we output None
        #  - if fs contains only one item, we output it as-is
        composed = reducel(compose1_two, fs)  # op(elt, acc)
        if all(islazy(f) for f in fs):
            composed = passthrough_lazy_args(composed)
        return composed
    return compose1

_compose1_left = _make_compose1("left")
_compose1_right = _make_compose1("right")

def composer1(*fs):
    """Like composer, but limited to one-argument functions. Faster.

    Example::

        double = lambda x: 2*x
        inc    = lambda x: x+1
        inc_then_double = composer1(double, inc)
        assert inc_then_double(3) == 8
    """
    return composer1i(fs)

def composel1(*fs):
    """Like composel, but limited to one-argument functions. Faster.

    Example::

        double = lambda x: 2*x
        inc    = lambda x: x+1
        double_then_inc = composel1(double, inc)
        assert double_then_inc(3) == 7
    """
    return composel1i(fs)

def composer1i(iterable):  # this is just to insert a docstring
    """Like composer1, but read the functions from an iterable."""
    return _compose1_right(iterable)

def composel1i(iterable):
    """Like composel1, but read the functions from an iterable."""
    return _compose1_left(iterable)

def _make_compose(direction):  # "left", "right"
    def compose_two(f, g):
        def composed(*args):
            bindings = {}
            if iscurried(f):
                # co-operate with curry: provide a top-level curry context
                # to allow passthrough from the function that is applied first
                # to the function that is applied second.
                bindings = {"curry_context": dyn.curry_context + [composed]}
            with dyn.let(**bindings):
                a = maybe_force_args(g, *args)
            # we could duck-test, but this is more predictable for the user
            # (consider chaining functions that manipulate a generator), and
            # tuple specifically is the pythonic multiple-return-values thing.
            if isinstance(a, tuple):
                return maybe_force_args(f, *a)
            return maybe_force_args(f, a)
        return composed
    if direction == "right":
        compose_two = flip(compose_two)
    def compose(fs):
        composed = reducel(compose_two, fs)  # op(elt, acc)
        if all(islazy(f) for f in fs):
            composed = passthrough_lazy_args(composed)
        return composed
    return compose

_compose_left = _make_compose("left")
_compose_right = _make_compose("right")

def composer(*fs):
    """Compose functions accepting only positional args. Right to left.

    This mirrors the standard mathematical convention (f ∘ g)(x) ≡ f(g(x)).

    At each step, if the output from a function is a tuple,
    it is unpacked to the argument list of the next function. Otherwise,
    we assume the output is intended to be fed to the next function as-is.

    Especially, generators, namedtuples and any custom classes will **not** be
    unpacked, regardless of whether or not they support the iterator protocol.
    """
    return composeri(fs)

def composel(*fs):
    """Like composer, but from left to right.

    The functions ``fs`` are applied in the order given; no need
    to read the source code backwards.
    """
    return composeli(fs)

def composeri(iterable):
    """Like composer, but read the functions from an iterable."""
    return _compose_right(iterable)

def composeli(iterable):
    """Like composel, but read the functions from an iterable."""
    return _compose_left(iterable)

def composerc(*fs):
    """Like composer, but curry each function before composing.

    With the passthrough in ``curry``, this allows very compact code::

        mymap = lambda f: curry(foldr, composerc(cons, f), nil)
        assert curry(mymap, double, ll(1, 2, 3)) == ll(2, 4, 6)

        add = lambda x, y: x + y
        assert curry(mymap, add, ll(1, 2, 3), ll(4, 5, 6)) == ll(5, 7, 9)
    """
    return composerci(fs)

def composelc(*fs):
    """Like composel, but curry each function before composing."""
    return composelci(fs)

def composerci(iterable):
    """Like composerc, but read the functions from an iterable."""
    return composeri(map(curry, iterable))

def composelci(iterable):
    """Like composelc, but read the functions from an iterable."""
    return composeli(map(curry, iterable))

# Helpers to insert one-in-one-out functions into multi-arg compose chains
def tokth(k, f):
    """Return a function to apply f to args[k], pass the rest through.

    Negative indices also supported.

    Especially useful in multi-arg compose chains.
    See ``unpythonic.test.test_fun`` for examples.
    """
    def apply_f_to_kth_arg(*args):
        n = len(args)
        if not n:
            raise TypeError("Expected at least one argument")
        if not -n < k < n:  # standard semantics for negative indices
            raise IndexError(f"Should have -n < k < n, but n = len(args) = {n}, and k = {k}")
        j = k % n  # --> j ∈ {0, 1, ..., n - 1}, even if k < 0
        m = j + 1  # --> m ∈ {1, 2, ..., n}
        out = list(args[:j])
        out.append(maybe_force_args(f, args[j]))  # mth argument
        if n > m:
            out.extend(args[m:])
        return tuple(out)
    if islazy(f):
        apply_f_to_kth_arg = passthrough_lazy_args(apply_f_to_kth_arg)
    return apply_f_to_kth_arg

def to1st(f):
    """Return a function to apply f to first item in args, pass the rest through.

    Example::

        def mymap_one(f, sequence):
            f_then_cons = composer(cons, to1st(f))  # args: elt, acc
            return foldr(f_then_cons, nil, sequence)
        double = lambda x: 2 * x
        assert mymap_one(double, (1, 2, 3)) == (2, 4, 6)
    """
    return tokth(0, f)  # this is just a partial() but we want to provide a docstring.

def to2nd(f):
    """Return a function to apply f to second item in args, pass the rest through."""
    return tokth(1, f)

def tolast(f):
    """Return a function to apply f to last item in args, pass the rest through."""
    return tokth(-1, f)

def to(*specs):
    """Return a function to apply f1, ..., fn to items in args, pass the rest through.

    The specs are processed sequentially in the given order (allowing also
    multiple updates to the same item).

    Parameters:
        specs: tuple of `(k, f)`, where:
            k: int
              index (also negative supported)
            f: function
              One-argument function to apply to `args[k]`.

    Returns:
        Function to (functionally) update args with the specs applied.
    """
    return composeli(tokth(k, f) for k, f in specs)

@ register_decorator(priority=80)
def withself(f):
    """Decorator. Allow a lambda to refer to itself.

    This is essentially the Y combinator trick packaged as a decorator.

    The reference to the lambda itself (the ``self`` argument) is passed as the
    first positional argument. It is declared explicitly, but passed implicitly,
    just like the ``self`` argument of a method.

    Note there is no point using this with named functions, because they can
    already refer to themselves via the name.

    Example::

        fact = withself(lambda self, n: n * self(n - 1) if n > 1 else 1)
        assert fact(5) == 120

    To TCO it, too::

        fact = trampolined(withself(lambda self, n, acc=1:
                             acc if n == 0 else jump(self, n - 1, n * acc)))
        assert fact(5) == 120
        fact(5000)  # no crash
    """
    @ wraps(f)
    def fwithself(*args, **kwargs):
        #return f(fwithself, *args, **kwargs)
        return maybe_force_args(f, fwithself, *args, **kwargs)  # support unpythonic.syntax.lazify
    if islazy(f):
        fwithself = passthrough_lazy_args(fwithself)
    return fwithself
