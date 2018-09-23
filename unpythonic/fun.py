#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Missing batteries for functools.

Some features modelled after Racket's builtins for handling procedures.
  https://docs.racket-lang.org/reference/procedures.html

Memoize is typical FP (Racket has it in mischief), and flip comes from Haskell.
"""

__all__ = ["memoize", "curry", "iscurried",
           "flip", "rotate",
           "apply", "identity", "const", "notf", "andf", "orf",
           "composer1", "composel1", "composer1i", "composel1i",  # single arg
           "composer",  "composel",  "composeri",  "composeli",   # multi-arg
           "composerc", "composelc", "composerci", "composelci",  # multi-arg w/ curry
           "to1st", "to2nd", "tokth", "tolast", "to"]

from functools import wraps, partial
from operator import itemgetter

from unpythonic.arity import arities
from unpythonic.fold import reducel

def memoize(f):
    """Decorator: memoize the function f.

    All of the args and kwargs of ``f`` must be hashable.

    Any exceptions raised by ``f`` are also memoized. If the memoized function
    is invoked again with arguments with which ``f`` originally raised an
    exception, *the same exception instance* is raised again.

    **CAUTION**: ``f`` must be pure (no side effects, no internal state
    preserved between invocations) for this to make any sense.
    """
    success, fail = [object() for _ in range(2)]
    memo = {}
    @wraps(f)
    def memoized(*args, **kwargs):
        k = (args, tuple(sorted(kwargs.items(), key=itemgetter(0))))
        if k not in memo:
            try:
                result = (success, f(*args, **kwargs))
            except BaseException as err:
                result = (fail, err)
            memo[k] = result  # should yell separately if k is not a valid key
        kind, value = memo[k]
        if kind is fail:
            raise value
        return value
    return memoized

#def memoize_simple(f):  # essential idea, without exception handling
#    memo = {}
#    @wraps(f)
#    def memoized(*args, **kwargs):
#        k = (args, tuple(sorted(kwargs.items(), key=itemgetter(0))))
#        if k not in memo:
#            memo[k] = f(*args, **kwargs)
#        return memo[k]
#    return memoized

def curry(f, *args, **kwargs):
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

    If too many args are given, any extra ones are passed through on the right::

        double = lambda x: 2 * x
        assert curry(double)(2, "foo") == (4, "foo")

    In passthrough, if an intermediate result is callable it is invoked
    on the remaining positional args::

        map_one = lambda f: (curry(foldr))(composer(cons, to1st(f)), nil)
        assert curry(map_one)(double, ll(1, 2, 3)) == ll(2, 4, 6)

    In the above example, ``map_one`` has arity 1, so the arg ``ll(1, 2, 3)``
    is extra. The result of ``map_one`` is a callable, so it is then
    invoked on this tuple.

    For simplicity, in passthrough, all kwargs are consumed in the first step
    for which too many positional args were supplied.

    **Curry itself is curried**:

    When invoked as a regular function (not decorator), curry itself is curried.
    If any arguments are provided beside ``f``, then they are the first step.
    This helps eliminate many parentheses::

        map_one = lambda f: curry(foldr, composer(cons, to1st(f)), nil)

    This comboes with passthrough::

        assert curry(double, 2, "foo") == (4, "foo")

        mymap = lambda f: curry(foldr, composerc(cons, f), nil)
        add = lambda x, y: x + y
        assert curry(mymap, add, ll(1, 2, 3), ll(4, 5, 6)) == ll(5, 7, 9)

        from functools import partial
        from unpythonic import curry, composel, drop, take

        with_n = lambda *args: (partial(f, n) for n, f in args)
        look = lambda n1, n2: composel(*with_n((n1, drop), (n2, take)))
        assert tuple(curry(look, 5, 10, range(20))) == tuple(range(5, 15))
    """
    # trivial case first: prevent stacking curried wrappers
    if iscurried(f):
        if args or kwargs:
            return f(*args, **kwargs)
        return f
    # TODO: improve: all required name-only args should be present before calling f.
    # Difficult, partial() doesn't remove an already-set kwarg from the signature.
    min_arity, max_arity = arities(f)
    @wraps(f)
    def curried(*args, **kwargs):
        if len(args) < min_arity:
            return curry(partial(f, *args, **kwargs))
        # passthrough on right, like https://github.com/Technologicat/spicy
        if len(args) > max_arity:
            now_args, later_args = args[:max_arity], args[max_arity:]
            now_result = f(*now_args, **kwargs)  # use up all kwargs now
            if callable(now_result):
                # curry it now, to sustain the chain in case we have
                # too many (or too few) args for it.
                if not iscurried(now_result):
                    now_result = curry(now_result)
                return now_result(*later_args)
            if isinstance(now_result, (tuple, list)):
                return tuple(now_result) + later_args
            return (now_result,) + later_args
        return f(*args, **kwargs)
    curried._is_curried_function = True  # stash for detection
    # curry itself is curried: if we get args, they're the first step
    if args or kwargs:
        return curried(*args, **kwargs)
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
        return f(*reversed(args), **kwargs)
    return flipped

def rotate(k):
    """Decorator (factory): cycle positional args of f to the right by k places.

    Negative values cycle to the left.

    Note this shifts the incoming argument values, not the formal parameter list!

    **Examples**::

        assert (rotate(1)(identity))(1, 2, 3) == (3, 1, 2)
        assert (rotate(-1)(identity))(1, 2, 3) == (2, 3, 1)
    """
    def rotate_k(f):
        @wraps(f)
        def rotated(*args, **kwargs):
            n = len(args)
            if not n:
                raise TypeError("Expected at least one argument")
            j = k % n  # handle also negative values
            rargs = args[-j:] + args[:-j]
            return f(*rargs, **kwargs)
        return rotated
    return rotate_k

def apply(f, arg0, *more):
    """Scheme/Racket-like apply.

    Not really needed since Python has *, but included for completeness.

    ``f`` is a function.

    ``arg0``, if alone, is the list to unpack.

    Otherwise the last item of ``more`` is the list to unpack. Any earlier
    arguments (starting from ``arg0``) are concatenated at the front.
    """
    if not more:
        args, lst = (), arg0
    else:
        args = (arg0,) + more[:-1]
        lst = tuple(more[-1])
    return f(*(args + lst))

def identity(*args):
    """Identity function.

    Accepts any positional arguments, and returns them.

    Packs into a tuple if there is more than one.

    Example::

        assert identity(1, 2, 3) == (1, 2, 3)
        assert identity(42) == 42
    """
    return args if len(args) > 1 else args[0]

def const(*args):
    """Constant function.

    Returns a function that accepts any arguments (also kwargs)
    and returns the args given here (packed into a tuple if more than one).

    Example::

        c = const(1, 2, 3)
        assert c(42, "foo") == (1, 2, 3)
        assert c("anything") == (1, 2, 3)
    """
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
        return not f(*args, **kwargs)
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
            b = b and f(*args, **kwargs)
            if not b:
                return False
        return b
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
            b = b or f(*args, **kwargs)
            if b:
                return b
        return False
    return disjoined

def _make_compose1(direction):  # "left", "right"
    def compose1_two(f, g):
        return lambda x: f(g(x))
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
        return reducel(compose1_two, fs)  # op(elt, acc)
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
            a = g(*args)
            # we could duck-test but this is more predictable for the user
            # (consider chaining functions that manipulate a generator).
            if isinstance(a, (list, tuple)):
                return f(*a)
            return f(a)
        return composed
    if direction == "right":
        compose_two = flip(compose_two)
    def compose(fs):
        return reducel(compose_two, fs)  # op(elt, acc)
    return compose

_compose_left = _make_compose("left")
_compose_right = _make_compose("right")

def composer(*fs):
    """Compose functions accepting only positional args. Right to left.

    This mirrors the standard mathematical convention (f ∘ g)(x) ≡ f(g(x)).

    At each step, if the output from a function is a list or a tuple,
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

    Especially useful in multi-arg compose chains. See ``test()`` for examples.
    """
    def apply_f_to_kth_arg(*args):
        n = len(args)
        if not n:
            raise TypeError("Expected at least one argument")
        j = k % n  # handle also negative values
        m = j + 1
        if n < m:
            raise TypeError("Expected at least {:d} arguments, got {:d}".format(m, n))
        out = list(args[:j])
        out.append(f(args[j]))  # mth argument
        if n > m:
            out.extend(args[m:])
        return tuple(out)
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

def test():
    from collections import Counter
    evaluations = Counter()
    @memoize
    def f(x):
        evaluations[x] += 1
        return x**2
    f(3)
    f(3)
    f(4)
    f(3)
    assert all(n == 1 for n in evaluations.values())

    # "memoize lambda": classic evaluate-at-most-once thunk
    thunk = memoize(lambda: print("hi from thunk"))
    thunk()
    thunk()

    evaluations = 0
    @memoize
    def t():
        nonlocal evaluations
        evaluations += 1
    t()
    t()
    assert evaluations == 1

    # exception storage in memoize
    class AllOkJustTesting(Exception):
        pass
    evaluations = 0
    @memoize
    def t():
        nonlocal evaluations
        evaluations += 1
        raise AllOkJustTesting()
    olderr = None
    for _ in range(3):
        try:
            t()
        except AllOkJustTesting as err:
            if olderr is not None and err is not olderr:
                assert False  # exception instance memoized, should be same every time
            olderr = err
        else:
            assert False  # memoize should not block raise
    assert evaluations == 1

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

    # currying a thunk is essentially a no-op
    evaluations = 0
    @curry
    def t():
        nonlocal evaluations
        evaluations += 1
    t()
    assert evaluations == 1  # t has no args, so it should have been invoked

    add = lambda x, y: x + y
    a = curry(add)
    assert curry(a) is a  # curry wrappers should not stack

    # flip
    def f(a, b):
        return (a, b)
    assert f(1, 2) == (1, 2)
    assert (flip(f))(1, 2) == (2, 1)
    assert (flip(f))(1, b=2) == (1, 2)  # b -> kwargs

    double = lambda x: 2*x
    inc    = lambda x: x+1
    inc_then_double = composer1(double, inc)
    double_then_inc = composel1(double, inc)
    assert inc_then_double(3) == 8
    assert double_then_inc(3) == 7

    inc2_then_double = composer1(double, inc, inc)
    double_then_inc2 = composel1(double, inc, inc)
    assert inc2_then_double(3) == 10
    assert double_then_inc2(3) == 8

    inc_then_double = composer(double, inc)
    double_then_inc = composel(double, inc)
    assert inc_then_double(3) == 8
    assert double_then_inc(3) == 7

    inc2_then_double = composer(double, inc, inc)
    double_then_inc2 = composel(double, inc, inc)
    assert inc2_then_double(3) == 10
    assert double_then_inc2(3) == 8

    assert to1st(double)(1, 2, 3)  == (2, 2, 3)
    assert to2nd(double)(1, 2, 3)  == (1, 4, 3)
    assert tolast(double)(1, 2, 3) == (1, 2, 6)

    processor = to((0, double),
                   (-1, inc),
                   (1, composer(double, double)),
                   (0, inc))
    assert processor(1, 2, 3) == (3, 8, 4)

    assert identity(1, 2, 3) == (1, 2, 3)
    assert (rotate(1)(identity))(1, 2, 3) == (3, 1, 2)
    assert (rotate(-1)(identity))(1, 2, 3) == (2, 3, 1)

    # The inner decorator is applied first to the decorated function, as usual.
    #
    # But here the outer one effectively takes effect first, because of the
    # order in which the decorators get their hands on the incoming arguments.
    #
    # So this first flips, then rotates the given arguments:
    assert flip(rotate(1)(identity))(1, 2, 3) == (1, 3, 2)

    def hello(*args):
        return args
    assert apply(hello, (1, 2, 3)) == (1, 2, 3)
    assert apply(hello, 1, (2, 3, 4)) == (1, 2, 3, 4)
    assert apply(hello, 1, 2, (3, 4, 5)) == (1, 2, 3, 4, 5)
    assert apply(hello, 1, 2, [3, 4, 5]) == (1, 2, 3, 4, 5)

    assert const(1, 2, 3)(42, "foo") == (1, 2, 3)
    assert notf(lambda x: 2*x)(3) is False
    assert notf(lambda x: 2*x)(0) is True
    isint  = lambda x: isinstance(x, int)
    iseven = lambda x: x % 2 == 0
    isstr  = lambda s: isinstance(s, str)
    assert andf(isint, iseven)(42) is True
    assert andf(isint, iseven)(43) is False
    pred = orf(isstr, andf(isint, iseven))
    assert pred(42) is True
    assert pred("foo") is True
    assert pred(None) is False  # neither condition holds

    print("All tests PASSED")

if __name__ == '__main__':
    test()
