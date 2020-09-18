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

from functools import wraps, partial

from .arity import arities, resolve_bindings, tuplify_bindings, UnknownArity
from .fold import reducel
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
        k = tuplify_bindings(resolve_bindings(f, *args, **kwargs))
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

make_dynvar(curry_context=[])
@passthrough_lazy_args
def _currycall(f, *args, **kwargs):
    """Co-operate with unpythonic.syntax.curry.

    In a ``with curry`` block, need to call also when ``f()`` has transformed
    to ``curry(f)``, but definitions can be curried as usual.

    Hence we provide this separate mode to curry-and-call even if no args.

    This mode also no-ops when ``f`` is not inspectable, instead of raising
    an ``unpythonic.arity.UnknownArity`` exception.
    """
    return curry(f, *args, _curry_force_call=True, _curry_allow_uninspectable=True, **kwargs)

@register_decorator(priority=8)
@passthrough_lazy_args
def curry(f, *args, _curry_force_call=False, _curry_allow_uninspectable=False, **kwargs):
    """Decorator: curry the function f.

    Essentially, the resulting function automatically chains partial application
    until the minimum positional arity of ``f`` is satisfied, at which point
    ``f``is called.

    Also more kwargs can be passed at each step, but they do not affect the
    decision when the function is called.

    For a callable to be curryable, it must be possible to inpect its signature
    to determine its minimum and maximum positional arities; builtin functions
    such as ``operator.add`` won't work. In such cases ``UnknownArity`` will
    be raised.

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

    **CAUTION**: BUG: `curry` may fail to actually call the function even after
    sufficient arguments have been collected, if some of the positional-or-keyword
    arguments of the function being curried are passed by name (in the first call).
    It seems those arguments don't reduce the expected remaining positional arity,
    although they should. See issue #61:
        https://github.com/Technologicat/unpythonic/issues/61

    **Workaround**: if possible, at the definition site for your function, declare
    any arguments you plan to pass by name as keyword-only; then they won't affect
    the positional arity.
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
    # TODO: improve: all required name-only args should be present before calling f.
    # Difficult, partial() doesn't remove an already-set kwarg from the signature.
    try:
        min_arity, max_arity = arities(f)
    except UnknownArity:  # likely a builtin
        if not _curry_allow_uninspectable:  # usual behavior
            raise
        # co-operate with unpythonic.syntax.curry; don't crash on builtins
        if args or kwargs or _curry_force_call:
            return maybe_force_args(f, *args, **kwargs)
        return f
    @wraps(f)
    def curried(*args, **kwargs):
        outerctx = dyn.curry_context
        with dyn.let(curry_context=(outerctx + [f])):
            if len(args) < min_arity:
                p = partial(f, *args, **kwargs)
                if islazy(f):
                    p = passthrough_lazy_args(p)
                return curry(p)
            # passthrough on right, like https://github.com/Technologicat/spicy
            if len(args) > max_arity:
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
                    raise TypeError("Top-level curry context exited with {:d} arg(s) remaining: {}".format(len(later_args),
                                                                                                           later_args))
                # pass through to the curried procedure waiting in outerctx
                # (e.g. in a curried compose chain)
                if isinstance(now_result, tuple):
                    return now_result + later_args
                return (now_result,) + later_args
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
    @wraps(f)
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
        @wraps(f)
        def rotated(*args, **kwargs):
            n = len(args)
            if not n:
                raise TypeError("Expected at least one argument")
            if not -n < k < n:  # standard semantics for negative indices
                raise IndexError("Should have -n < k < n, but n = len(args) = {}, and k = {}".format(n, k))
            j = -k % n
            rargs = args[-j:] + args[:-j]
            return maybe_force_args(f, *rargs, **kwargs)
        if islazy(f):
            rotated = passthrough_lazy_args(rotated)
        return rotated
    return rotate_k

@passthrough_lazy_args
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
            raise IndexError("Should have -n < k < n, but n = len(args) = {}, and k = {}".format(n, k))
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

@register_decorator(priority=80)
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
    @wraps(f)
    def fwithself(*args, **kwargs):
        #return f(fwithself, *args, **kwargs)
        return maybe_force_args(f, fwithself, *args, **kwargs)  # support unpythonic.syntax.lazify
    if islazy(f):
        fwithself = passthrough_lazy_args(fwithself)
    return fwithself
