#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Utilities for working with functions."""

__all__ = ["memoize", "curry", "flip",
           "composer", "composel",
           "composer1", "composel1",
           "foldl", "foldr"]

from functools import wraps, partial, reduce as foldl
from operator import itemgetter

from unpythonic.arity import arities

def memoize(f):
    """Decorator: memoize the function f.

    All of the args and kwargs of ``f`` must be hashable.

    **CAUTION**: ``f`` must be pure (no side effects, no internal state
    preserved between invocations) for this to make sense.
    """
    memo = {}
    @wraps(f)
    def memoized(*args, **kwargs):
        k = (args, tuple(sorted(kwargs.items(), key=itemgetter(0))))
        if k not in memo:
            memo[k] = f(*args, **kwargs)
        return memo[k]
    return memoized

def curry(f):
    """Decorator: curry the function f.

    Essentially, the resulting function automatically chains
    partial application until the minimum arity of ``f`` is satisfied.

    Example::

        @curry
        def add3(a, b, c):
            return a + b + c
        assert add3(1)(2)(3) == 6
    """
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

def foldr(function, sequence, initial=None):
    """Right fold.

    Same semantics as ``functools.reduce``.
    """
    return foldl(function, reversed(sequence), initial)

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
    def compose_pair(f, g):
        def composed(*args):
            a = g(*args)
            try:
                return f(*a)
            except TypeError:  # not unpackable, treat as a single value
                return f(a)
        return composed
    return foldl(compose_pair, fs)  # op(acc, elt)

def composer1(*fs):
    """Like composer, but limited to one-argument functions. Faster."""
    def compose1_pair(f, g):
        return lambda x: f(g(x))
    return foldl(compose1_pair, fs)  # op(acc, elt)

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

def composel1(*fs):
    """Like composel, but limited to one-argument functions. Faster."""
    return composer1(*reversed(fs))

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

    @curry
    def add3(a, b, c):
        return a + b + c
    assert add3(1)(2)(3) == 6
    # it actually uses partial application so these work, too
    assert add3(1, 2)(3) == 6
    assert add3(1)(2, 3) == 6
    assert add3(1, 2, 3) == 6

    # test that currying a thunk is essentially a no-op
    evaluations = 0
    @curry
    def t():
        nonlocal evaluations
        evaluations += 1
    t()
    assert evaluations == 1  # t has no args, so it should have been invoked

    # test flip
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

    # TODO: test also composer, composel

    print("All tests PASSED")

    def app1(f, a, b):
        return (f(a), b)
    def app2(f, a, b):
        return (a, f(b))
    def mymap(f, iterable):
        proc = lambda acc, elt: snoc(*app2(f, acc, elt))
        return foldr(proc, iterable, nil)
    print(mymap(double, (1, 2, 3)))

if __name__ == '__main__':
    test()
