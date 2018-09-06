#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Missing batteries for functools.

Some features modelled after Racket's builtins for handling procedures.
  https://docs.racket-lang.org/reference/procedures.html

Memoize is typical FP (Racket has it in mischief), and flip comes from Haskell.
"""

__all__ = ["memoize", "curry",
           "flip", "rotate",
           "apply", "identity", "const", "negate", "conjoin", "disjoin",
           "composer1", "composel1", "composer", "composel",
           "to1st", "to2nd", "tokth", "tolast", "to"]

from functools import wraps, partial
from operator import itemgetter

from unpythonic.arity import arities
import unpythonic.it

def memoize(f):
    """Decorator: memoize the function f.

    All of the args and kwargs of ``f`` must be hashable.

    Any exceptions raised by ``f`` are also memoized. If the memoized function
    is invoked again with arguments with which ``f`` originally raised an
    exception, *the same exception instance* is raised again.

    **CAUTION**: ``f`` must be pure (no side effects, no internal state
    preserved between invocations) for this to make any sense.
    """
    success, fail = [object() for _ in range(2)]  # sentinels
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
        sentinel, value = memo[k]
        if sentinel is fail:
            raise value
        else:
            return value
    return memoized

def curry(f):
    """Decorator: curry the function f.

    Essentially, the resulting function automatically chains partial application
    until the minimum positional arity of ``f`` is satisfied, at which point
    ``f``is called.

    Also more kwargs can be passed at each step, but they do not affect the
    decision when the function is called.

    Examples::

        @curry
        def add3(a, b, c):
            return a + b + c
        assert add3(1)(2)(3) == 6

        @curry
        def lispyadd(*args):
            return sum(args)
        assert lispyadd() == 0  # no args is a valid arity here

        @curry
        def foo(a, b, *, c, d):
            return a, b, c, d
        assert foo(5, c=23)(17, d=42) == (5, 17, 23, 42)
    """
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
            if hasattr(now_result, "_is_curried_function"):
                return now_result(*later_args)
            elif isinstance(now_result, (tuple, list)):
                return tuple(now_result) + later_args
            else:
                return (now_result,) + later_args
        return f(*args, **kwargs)
    curried._is_curried_function = True  # stash for easy detection
    return curried

#def curry_simple(f):  # without the passthrough capability, this is sufficient
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

    Accepts any positional arguments, and returns them as a tuple.

    Example::

        assert identity(1, 2, 3) == (1, 2, 3)
    """
    return args

def const(*args):
    """Constant function.

    Returns a function that accepts any arguments (also kwargs)
    and returns the args given here, as a tuple.

    Example::

        c = const(1, 2, 3)
        assert c(42, "foo") == (1, 2, 3)
        assert c("anything") == (1, 2, 3)
    """
    def constant(*a, **kw):
        return args
    return constant

def negate(f):
    """Return a function that returns the logical not of the result of f.

    Examples::

        assert negate(lambda x: 2*x)(3) is False
        assert negate(lambda x: 2*x)(0) is True
    """
    @wraps(f)
    def negated(*args, **kwargs):
        return not f(*args, **kwargs)
    return negated

def conjoin(*fs):
    """Return a function that conjoins calls to fs with "and".

    Each function in ``fs`` is called with the same ``args`` and ``kwargs``,
    provided when the conjoined function is called.

    Evaluation short-circuits at the first falsey term, if any, returning ``False``.
    If all terms are truthy, the final return value (from the last function in
    ``fs``) is returned.

    Examples::

        assert conjoin(lambda x: isinstance(x, int), lambda x: x % 2 == 0)(42) is True
        assert conjoin(lambda x: isinstance(x, int), lambda x: x % 2 == 0)(43) is False
    """
    def conjoined(*args, **kwargs):
        b = True
        for f in fs:
            b = b and f(*args, **kwargs)
            if not b:
                return False
        return b
    return conjoined

def disjoin(*fs):
    """Return a function that disjoins calls to fs with "or".

    Each function in ``fs`` is called with the same ``args`` and ``kwargs``,
    provided when the disjoined function is called.

    Evaluation short-circuits at the first truthy term, if any, and it is returned.
    If all terms are falsey, the return value is False.

    Examples::

        isstr  = lambda s: isinstance(s, str)
        iseven = lambda x: isinstance(x, int) and x % 2 == 0
        assert disjoin(isstr, iseven)(42) is True
        assert disjoin(isstr, iseven)("foo") is True
        assert disjoin(isstr, iseven)(None) is False  # neither condition holds
    """
    def disjoined(*args, **kwargs):
        b = False
        for f in fs:
            b = b or f(*args, **kwargs)
            if b:
                return b
        return False
    return disjoined

def composer1(*fs):
    """Like composer, but limited to one-argument functions. Faster.

    Example::

        double = lambda x: 2*x
        inc    = lambda x: x+1
        inc_then_double = composer1(double, inc)
        assert inc_then_double(3) == 8
    """
    def compose1_two(f, g):
        return lambda x: f(g(x))
    return unpythonic.it.reducer(compose1_two, fs)  # op(elt, acc)

def composel1(*fs):
    """Like composel, but limited to one-argument functions. Faster.

    Example::

        double = lambda x: 2*x
        inc    = lambda x: x+1
        double_then_inc = composel(double, inc)
        assert double_then_inc(3) == 7
    """
    return composer1(*reversed(fs))

def composer(*fs):
    """Compose functions accepting only positional args. Right to left.

    This mirrors the standard mathematical convention (f ∘ g)(x) ≡ f(g(x)).

    The output from each function is unpacked to the argument list of
    the next one. If the duck test fails, the output is assumed to be
    a single value, and is fed in to the next function as-is.
    """
    def unpack_ctx(*args): pass  # just a context where we can use * to unpack
    def compose_two(f, g):
        def composed(*args):
            a = g(*args)
            try:
                unpack_ctx(*a)
            except TypeError:
                return f(a)
            else:
                return f(*a)
        return composed
    return unpythonic.it.reducer(compose_two, fs)  # op(elt, acc)

def composel(*fs):
    """Like composer, but from left to right.

    The sequence ``fs`` is applied in the order given; no need
    to read the source code backwards.
    """
    return composer(*reversed(fs))

# Helpers for multi-arg compose chains
def tokth(k, f):
    """Return a function to apply f to args[k], pass the rest through.

    Negative indices also supported.

    Especially useful in multi-arg compose chains. See ``test()`` for examples.
    """
    def applicator(*args):
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
    return applicator

def to1st(f):
    """Return a function to apply f to first item in args, pass the rest through.

    Example::

        nil = ()
        def cons(x, l):  # elt, acc
            return (x,) + l
        def mymap_one(f, sequence):
            f_then_cons = composer(cons, to1st(f))  # args: elt, acc
            return foldr(f_then_cons, nil, sequence)
        double = lambda x: 2*x
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
    return composel(*(tokth(k, f) for k, f in specs))

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

    # Outer gets effectively applied first, because of the order in which
    # the decorators get their hands on the incoming, user-given arguments.
    assert flip(rotate(1)(identity))(1, 2, 3) == (1, 3, 2)

    def hello(*args):
        return args
    assert apply(hello, (1, 2, 3)) == (1, 2, 3)
    assert apply(hello, 1, (2, 3, 4)) == (1, 2, 3, 4)
    assert apply(hello, 1, 2, (3, 4, 5)) == (1, 2, 3, 4, 5)
    assert apply(hello, 1, 2, [3, 4, 5]) == (1, 2, 3, 4, 5)

    assert const(1, 2, 3)(42, "foo") == (1, 2, 3)
    assert negate(lambda x: 2*x)(3) is False
    assert negate(lambda x: 2*x)(0) is True
    assert conjoin(lambda x: isinstance(x, int), lambda x: x % 2 == 0)(42) is True
    assert conjoin(lambda x: isinstance(x, int), lambda x: x % 2 == 0)(43) is False
    isstr  = lambda s: isinstance(s, str)
    iseven = lambda x: isinstance(x, int) and x % 2 == 0
    assert disjoin(isstr, iseven)(42) is True
    assert disjoin(isstr, iseven)("foo") is True
    assert disjoin(isstr, iseven)(None) is False  # neither condition holds

    print("All tests PASSED")

if __name__ == '__main__':
    test()
