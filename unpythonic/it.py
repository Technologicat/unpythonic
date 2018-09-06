#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Missing batteries for itertools.

Racket-like multi-input foldl and foldr based on
  https://docs.racket-lang.org/reference/pairs.html
"""

__all__ = ["foldl", "foldr", "reducel", "reducer",
           "flatmap", "take"]

# minimum arity of 3 allows using this with curry.
def foldl(proc, init, iterable0, *iterables):
    """Racket-like foldl that supports multiple input iterables.

    At least one iterable (``iterable0``) is required. More are optional.

    Terminates when the shortest input runs out.

    Initial value is mandatory; there is no sane default for the case with
    multiple inputs.

    Note order: ``proc(elt, acc)``, which is the opposite order of arguments
    compared to ``functools.reduce``. General case ``proc(e1, ..., en, acc)``.
    """
    iterables = (iterable0,) + iterables
    def heads(its):
        hs = []
        for it in its:
            try:
                h = next(it)
            except StopIteration:  # shortest sequence ran out
                return StopIteration
            hs.append(h)
        return tuple(hs)
    iters = tuple(iter(x) for x in iterables)
    acc = init
    while True:
        hs = heads(iters)
        if hs is StopIteration:
            return acc
        acc = proc(*(hs + (acc,)))

def foldr(proc, init, sequence0, *sequences):
    """Like foldl, but fold from the right (walk each sequence backwards)."""
    return foldl(proc, init, reversed(sequence0), *(reversed(s) for s in sequences))

def reducel(proc, iterable, init=None):
    """Foldl for a single iterable.

    Like functools.reduce, but uses ``proc(elt, acc)`` like Racket."""
    it = iter(iterable)
    if not init:
        try:
            init = next(it)
        except StopIteration:
            return None  # empty input sequence
    return foldl(proc, init, it)

def reducer(proc, sequence, init=None):
    """Like reducel, but fold from the right (walk backwards)."""
    return reducel(proc, reversed(sequence), init)

def flatmap(f, *lsts):
    """Map, then concatenate results.

    ``f`` should accept ``len(lsts)`` arguments (each drawn from one of
    the ``lsts``), and return a list or tuple.

    Example::

        def msqrt(x):  # multivalued sqrt
            if x == 0.:
                return (0.,)
            else:
                s = x**0.5
                return (s, -s)
        assert flatmap(msqrt, (0, 1, 4, 9)) == (0., 1., -1., 2., -2., 3., -3.)

        def add_and_tuplify(a, b):
            return (a + b,)
        assert flatmap(add_and_tuplify, (10, 20, 30), (1, 2, 3)) == (11, 22, 33)

        def sum_and_diff(a, b):
            return (a + b, a - b)
        assert flatmap(sum_and_diff, (10, 20, 30), (1, 2, 3)) == (11, 9, 22, 18, 33, 27)
    """
    def concat(elt, acc):
        return tuple(acc) + tuple(elt)
    return foldl(concat, (), map(f, *lsts))

def take(iterable, n):
    """Return a generator that yields the first n items of iterable, then stops.

    Stops earlier if ``iterable`` has fewer than ``n`` items.
    """
    return map(lambda x, _: x, iter(iterable), range(n))
#    return (x for x, _ in zip(iter(iterable), range(n)))

def test():
    from operator import add
    from functools import partial

    import unpythonic.fun
    curry = unpythonic.fun.curry
    composer = unpythonic.fun.composer
    composel = unpythonic.fun.composel
    to1st = unpythonic.fun.to1st
    rotate = unpythonic.fun.rotate

    # just a testing hack; for a "real" cons, see unpythonic.llist.cons
    nil = ()
    def cons(x, l):  # elt, acc
        return (x,) + l
    assert foldl(cons, nil, (1, 2, 3)) == (3, 2, 1)
    assert foldr(cons, nil, (1, 2, 3)) == (1, 2, 3)

    assert reducel(add, (1, 2, 3)) == 6
    assert reducer(add, (1, 2, 3)) == 6

    def foo(a, b, acc):
        return acc + ((a, b),)
    assert foldl(foo, (), (1, 2, 3), (4, 5)) == ((1, 4), (2, 5))
    assert foldr(foo, (), (1, 2, 3), (4, 5)) == ((3, 5), (2, 4))

    def mymap_one(f, sequence):
        f_then_cons = composer(cons, to1st(f))  # args: elt, acc
        return foldr(f_then_cons, nil, sequence)
    double = lambda x: 2 * x
    assert mymap_one(double, (1, 2, 3)) == (2, 4, 6)
    def mymap_one2(f, sequence):
        f_then_cons = composel(to1st(f), cons)  # args: elt, acc
        return foldr(f_then_cons, nil, sequence)
    assert mymap_one2(double, (1, 2, 3)) == (2, 4, 6)

    # point-free-ish style
    mymap_one3 = lambda f: partial(foldr, composer(cons, to1st(f)), nil)
    doubler = mymap_one3(double)
    assert doubler((1, 2, 3)) == (2, 4, 6)

    try:
        doubler((1, 2, 3), (4, 5, 6))
    except TypeError:
        pass
    else:
        assert False  # one arg too many; cons in the compose chain expects 2 args

    # minimum arity of fold functions is 3, to allow use with curry:
    mymap_one4 = lambda f: (curry(foldr))(composer(cons, to1st(f)), nil)
    doubler = mymap_one4(double)
    assert doubler((1, 2, 3)) == (2, 4, 6)

    # curry supports passing through on the right any args over the max arity.
    assert curry(double)(2, "foo") == (4, "foo")   # arity of double is 1

    # In passthrough, if an intermediate result is a curried function,
    # it is invoked on the remaining positional args:
    assert curry(mymap_one4)(double, (1, 2, 3)) == (2, 4, 6)

    reverse_one = curry(foldl)(cons, nil)
    assert reverse_one((1, 2, 3)) == (3, 2, 1)

    append_two = lambda a, b: foldr(cons, b, a)
    assert append_two((1, 2, 3), (4, 5, 6)) == (1, 2, 3, 4, 5, 6)

    append_many = lambda *lsts: foldr(append_two, nil, lsts)
    assert append_many((1, 2), (3, 4), (5, 6)) == (1, 2, 3, 4, 5, 6)

    def msqrt(x):  # multivalued sqrt
        if x == 0.:
            return (0.,)
        else:
            s = x**0.5
            return (s, -s)
    assert flatmap(msqrt, (0, 1, 4, 9)) == (0., 1., -1., 2., -2., 3., -3.)

    def add_and_tuplify(a, b):
        return (a + b,)
    assert flatmap(add_and_tuplify, (10, 20, 30), (1, 2, 3)) == (11, 22, 33)

    def sum_and_diff(a, b):
        return (a + b, a - b)
    assert flatmap(sum_and_diff, (10, 20, 30), (1, 2, 3)) == (11, 9, 22, 18, 33, 27)

    assert tuple(take(range(100), 10)) == tuple(range(10))
    assert tuple(take(range(3), 10)) == tuple(range(3))

    @rotate(1)
    def zipper(acc, *rest):   # so that we can use the *args syntax to declare this
        return acc + (rest,)  # even though the input is (e1, ..., en, acc).
#    def zipper(*args):  # straightforward version
#        *rest, acc = args
#        return acc + (tuple(rest),)
    zipl = (curry(foldl))(zipper, ())
    zipr = (curry(foldr))(zipper, ())
    assert zipl((1, 2, 3), (4, 5, 6), (7, 8)) == ((1, 4, 7), (2, 5, 8))
    assert zipr((1, 2, 3), (4, 5, 6), (7, 8)) == ((3, 6, 8), (2, 5, 7))

    print("All tests PASSED")

if __name__ == '__main__':
    test()
