#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Missing batteries for functools."""

__all__ = ["memoize", "curry", "flip",
           "composer1", "composel1",
           "composer", "composel", "app1st", "app2nd", "appkth", "applast", "appto",
           "foldl", "foldr"]

from functools import wraps, partial, reduce as foldl
from operator import itemgetter

from unpythonic.arity import arities

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
    min_arity, _ = arities(f)
    @wraps(f)
    def curried(*args, **kwargs):
        if len(args) < min_arity:
            return curry(partial(f, *args, **kwargs))
        return f(*args, **kwargs)
    return curried

def flip(f):
    """Decorator: flip (reverse) the positional arguments of f."""
    @wraps(f)
    def flipped(*args, **kwargs):
        return f(*reversed(args), **kwargs)
    return flipped

def composer1(*fs):
    """Like composer, but limited to one-argument functions. Faster."""
    def compose1_pair(f, g):
        return lambda x: f(g(x))
    return foldl(compose1_pair, fs)  # op(acc, elt)

def composel1(*fs):
    """Like composel, but limited to one-argument functions. Faster."""
    return composer1(*reversed(fs))

def composer(*fs):
    """Compose functions accepting only positional args. Right to left.

    This mirrors the standard mathematical convention (f ∘ g)(x) ≡ f(g(x)).

    The output from the previous function is unpacked to the argument list
    of the next one. If the duck test fails, the output is assumed to be
    a single value, and is fed in to the next function as-is.

    Example::

        double = lambda x: 2*x
        inc    = lambda x: x+1
        inc_then_double = composer(double, inc)
        assert inc_then_double(3) == 8
    """
    def test_unpack(*args):
        pass
    def compose_pair(f, g):
        def composed(*args):
            a = g(*args)
            try:
                test_unpack(*a)
            except TypeError:  # not unpackable, treat as a single value
                return f(a)
            else:
                return f(*a)
        return composed
    return foldl(compose_pair, fs)  # op(acc, elt)

def composel(*fs):
    """Like composer, but from left to right.

    The sequence ``fs`` is applied in the order given; no need
    to read the source code backwards.

    Example::

        double = lambda x: 2*x
        inc    = lambda x: x+1
        double_then_inc = composel(double, inc)
        assert double_then_inc(3) == 7
    """
    return composer(*reversed(fs))

# Helpers for multi-arg compose chains
def appkth(f, k, *args):
    """Apply f to kth item in args, pass the rest through.

    Negative indices also supported.

    Especially useful in multi-arg compose chains as `partial(appk, f, k)`.
    """
    if k < 0:
        k = k % len(args)
    out = list(args[:k])
    out.append(f(args[k]))
    if len(args) > k + 1:
        out.extend(args[k+1:])
    return tuple(out)

def app1st(f, *args):
    """Apply f to first item in args, pass the rest through."""
    return appkth(f, 0, *args)

def app2nd(f, *args):
    """Apply f to second item in args, pass the rest through.

    Example::

        nil = ()
        def cons(x, l):  # elt, acc
            return (x,) + l
        snoc = flip(cons)  # acc, elt like reduce wants
        def mymap(f, sequence):
            f_then_cons = composer(snoc, partial(app2nd, f))  # args: acc, elt
            return foldr(f_then_cons, sequence, nil)
        double = lambda x: 2*x
        assert mymap(double, (1, 2, 3)) == (2, 4, 6)
    """
    return appkth(f, 1, *args)

def applast(f, *args):
    """Apply f to last item in args, pass the rest through."""
    return appkth(f, -1, *args)

def appto(spec, *args):
    """Apply f1, ..., fn to items in args, pass the rest through.

    The spec is processed sequentially in the given order (allowing also
    multiple updates to the same item).

    Parameters:
        spec: tuple of `(f, k)`, where:
            f: function
              One-argument function to apply to `args[k]`.
            k: int
              index (also negative supported)

    Returns:
        (functionally) updated args with the spec applied.
    """
    vs = args
    for f, k in spec:
        vs = appkth(f, k, *vs)
    return vs

def foldr(function, sequence, initial=None):
    """Right fold.

    Same semantics as ``functools.reduce``.
    """
    return foldl(function, reversed(sequence), initial)

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

    nil = ()
    def cons(x, l):  # elt, acc
        return (x,) + l
    snoc = flip(cons)  # acc, elt like reduce wants
    assert foldl(snoc, (1, 2, 3), nil) == (3, 2, 1)
    assert foldr(snoc, (1, 2, 3), nil) == (1, 2, 3)

    double = lambda x: 2*x
    inc    = lambda x: x+1
    inc_then_double = composer1(double, inc)
    double_then_inc = composel1(double, inc)
    assert inc_then_double(3) == 8
    assert double_then_inc(3) == 7

    def mymap(f, sequence):
        f_then_cons = composer(snoc, partial(app2nd, f))  # args: acc, elt
        return foldr(f_then_cons, sequence, nil)
    assert mymap(double, (1, 2, 3)) == (2, 4, 6)
    def mymap2(f, sequence):
        f_then_cons = composel(partial(app2nd, f), snoc)  # args: acc, elt
        return foldr(f_then_cons, sequence, nil)
    assert mymap2(double, (1, 2, 3)) == (2, 4, 6)

    processor = partial(appto, ((double, 0),
                                (inc, -1),
                                (composer(double, double), 1),
                                (inc, 0)))
    assert processor(1, 2, 3) == (3, 8, 4)

    print("All tests PASSED")

if __name__ == '__main__':
    test()
