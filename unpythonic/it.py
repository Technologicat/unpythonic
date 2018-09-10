#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Missing batteries for itertools.

Racket-like multi-input foldl and foldr based on
  https://docs.racket-lang.org/reference/pairs.html

Take and drop based on Haskell.

Flatten based on Danny Yoo's version:
  http://rightfootin.blogspot.fi/2006/09/more-on-python-flatten.html
"""

__all__ = ["foldl", "foldr", "reducel", "reducer",
           "flatmap", "mapr", "zipr", "uniqify",
           "take", "drop", "split_at",
           "flatten", "flatten1", "flatten_in"]

from itertools import tee, islice
from collections import deque

# require at least one iterable to make this work seamlessly with curry.
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
    # This approach gives us a linear process.
    return foldl(proc, init, reversed(sequence0), *(reversed(s) for s in sequences))

def reducel(proc, iterable, init=None):
    """Foldl for a single iterable.

    Like ``functools.reduce``, but uses ``proc(elt, acc)`` like Racket."""
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

# require at least one iterable to make this work seamlessly with curry.
def flatmap(f, iterable0, *iterables):
    """Map, then concatenate results.

    At least one iterable (``iterable0``) is required. More are optional.

    ``f`` should accept as many arguments as iterables given (each argument
    drawn from one of the iterables), and return an iterable.

    Returns a generator that yields the flatmapped result.

    Example::

        def msqrt(x):  # multivalued sqrt
            if x == 0.:
                return (0.,)
            else:
                s = x**0.5
                return (s, -s)
        assert tuple(flatmap(msqrt, (0, 1, 4, 9))) == \\
               (0., 1., -1., 2., -2., 3., -3.)

        def add_and_tuplify(a, b):
            return (a + b,)
        assert tuple(flatmap(add_and_tuplify, (10, 20, 30), (1, 2, 3))) == \\
               (11, 22, 33)

        def sum_and_diff(a, b):
            return (a + b, a - b)
        assert tuple(flatmap(sum_and_diff, (10, 20, 30), (1, 2, 3))) == \\
               (11, 9, 22, 18, 33, 27)
    """
#    def concat(elt, acc):
#        return tuple(acc) + tuple(elt)
#    return foldl(concat, (), map(f, *lsts))  # eager, bad
    iterables = (iterable0,) + iterables
    for xs in map(f, *iterables):
        for x in xs:
            yield x

def mapr(func, *sequences):
    """Like map, but walk each sequence from the right."""
    return map(func, *(reversed(s) for s in sequences))

def zipr(*sequences):
    """Like zip, but walk each sequence from the right."""
    return zip(*(reversed(s) for s in sequences))

def uniqify(iterable, key=None):
    """Skip duplicates in iterable.

    Returns a generator that yields unique items from iterable, preserving
    their original ordering.

    If ``key`` is provided, the return value of ``key(elt)`` is tested instead
    of ``elt`` itself to determine uniqueness.
    """
    key = key or (lambda x: x)
    it = iter(iterable)
    seen = set()
    for e in it:
        k = key(e)
        if k not in seen:
            seen.add(k)
            yield e

def take(n, iterable):
    """Return a generator that yields the first n items of iterable, then stops.

    Stops earlier if ``iterable`` has fewer than ``n`` items.

    This is essentially ``take`` from ``itertools`` recipes,
    but returns a generator.
    """
    it = iter(iterable)
    it = islice(it, n)
    def gen():
        yield from it
    return gen()

def drop(n, iterable):
    """Skip the first n elements of iterable, then yield the rest.

    If ``n`` is ``None``, consume the iterable until it runs out.

    This is essentially ``consume`` from ``itertools`` recipes,
    but returns a generator.
    """
    it = iter(iterable)
    if n is None:
        deque(it, maxlen=0)
    else:
        next(islice(it, n, n), None)  # advance it to empty slice starting at n
    def gen():
        yield from it
    return gen()

def split_at(n, iterable):
    """Split iterable at position n.

    Returns a pair of generators ``(first_part, second_part)``.

    Examples::

        a, b = split_at(5, range(10))
        assert tuple(a) == tuple(range(5))
        assert tuple(b) == tuple(range(5, 10))

        a, b = map(tuple, split_at(5, range(3)))
        assert a == tuple(range(3))
        assert b == ()
    """
    ia, ib = tee(iter(iterable))
    return take(n, ia), drop(n, ib)

def flatten(iterable, pred=None):
    """Recursively remove nested structure from iterable.

    Process tuples and lists inside the iterable; pass everything else through
    (including any generators stored in the iterable).

    Returns a generator that yields the flattened output.

    ``pred`` is an optional predicate for filtering. It should accept a tuple
    (or list), and return ``True`` if that tuple/list should be flattened.
    When ``pred`` returns False, that tuple/list is passed through as-is.

    E.g. to flatten only those items that contain only tuples::

        is_nested = lambda e: all(isinstance(x, (tuple, list)) for x in e)
        data = (((1, 2), (3, 4)), (5, 6))
        assert tuple(flatten(data, is_nested)) == ((1, 2), (3, 4), (5, 6))
    """
    return _flatten(iterable, pred, recursive=True)

def flatten1(iterable, pred=None):
    """Like flatten, but process outermost level only."""
    return _flatten(iterable, pred, recursive=False)

def _flatten(iterable, pred=None, recursive=True):
    pred = pred or (lambda x: True)
    it = iter(iterable)
    for e in it:
        if isinstance(e, (list, tuple)) and pred(e):
            items = _flatten(e, pred) if recursive else e
            for f in items:
                yield f
        else:
            yield e

def flatten_in(iterable, pred=None):
    """Like flatten, but recurse also into tuples/lists not matching pred.

    This makes also those items get the same flattening applied inside them.

    Example::

        is_nested = lambda e: all(isinstance(x, (tuple, list)) for x in e)
        data = (((1, 2), ((3, 4), (5, 6)), 7), ((8, 9), (10, 11)))
        assert tuple(flatten(data, is_nested))    == \\
               (((1, 2), ((3, 4), (5, 6)), 7), (8, 9), (10, 11))
        assert tuple(flatten_in(data, is_nested)) == \\
               (((1, 2), (3, 4), (5, 6), 7), (8, 9), (10, 11))
    """
    pred = pred or (lambda x: True)
    it = iter(iterable)
    for e in it:
        if isinstance(e, (list, tuple)):
            if pred(e):
                for f in flatten_in(e, pred):
                    yield f
            else:
                t = type(e)
                new_e = t(flatten_in(e, pred))
                yield new_e
        else:
            yield e

def test():
    from operator import add, itemgetter
    from functools import partial

    import unpythonic.fun
    curry = unpythonic.fun.curry
    composer = unpythonic.fun.composer
    composel = unpythonic.fun.composel
    to1st = unpythonic.fun.to1st
    rotate = unpythonic.fun.rotate
    identity = unpythonic.fun.identity

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
        assert False  # one arg too many; cons in the compose chain expects 2 args (acc is one)

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
    assert tuple(flatmap(msqrt, (0, 1, 4, 9))) == (0., 1., -1., 2., -2., 3., -3.)

    def add_and_tuplify(a, b):
        return (a + b,)
    assert tuple(flatmap(add_and_tuplify, (10, 20, 30), (1, 2, 3))) == (11, 22, 33)

    def sum_and_diff(a, b):
        return (a + b, a - b)
    assert tuple(flatmap(sum_and_diff, (10, 20, 30), (1, 2, 3))) == (11, 9, 22, 18, 33, 27)

    assert tuple(take(10, range(100))) == tuple(range(10))
    assert tuple(take(10, range(3))) == tuple(range(3))

    assert tuple(drop(5, range(10))) == tuple(range(5, 10))
    assert tuple(drop(5, range(3))) == ()
    p = composel(partial(drop, 5), partial(take, 5))
    assert tuple(p(range(20))) == tuple(range(5, 10))

    with_same_n = lambda n, fs: (partial(f, n) for f in fs)
#    with_same_n = lambda n, fs: map((lambda f: partial(f, n)), fs)
    p = composel(*with_same_n(5, (drop, take)))
    assert tuple(p(range(20))) == tuple(range(5, 10))

    with_n = lambda *args: (partial(f, n) for n, f in args)
    p = composel(*with_n((5, drop), (10, take)))
    assert tuple(p(range(20))) == tuple(range(5, 15))

    a, b = map(tuple, split_at(5, range(10)))
    assert a == tuple(range(5))
    assert b == tuple(range(5, 10))

    a, b = map(tuple, split_at(5, range(3)))
    assert a == tuple(range(3))
    assert b == ()

    assert tuple(zipr((1, 2, 3), (4, 5, 6), (7, 8))) == ((3, 6, 8), (2, 5, 7))

    @rotate(1)
    def zipper(acc, *rest):   # so that we can use the *args syntax to declare this
        return acc + (rest,)  # even though the input is (e1, ..., en, acc).
#    def zipper(*args):  # straightforward version
#        *rest, acc = args
#        return acc + (tuple(rest),)
    zipl1 = (curry(foldl))(zipper, ())
    zipr1 = (curry(foldr))(zipper, ())
    assert zipl1((1, 2, 3), (4, 5, 6), (7, 8)) == ((1, 4, 7), (2, 5, 8))
    assert zipr1((1, 2, 3), (4, 5, 6), (7, 8)) == ((3, 6, 8), (2, 5, 7))

    # Python's builtin map is not curry-friendly; it accepts arity 1,
    # but actually requires 2. Solution: use partial.
    zipl2 = partial(map, identity)
    zipr2 = lambda *sequences: map(unpythonic.fun.identity, *(reversed(s) for s in sequences))
    assert tuple(zipl2((1, 2, 3), (4, 5, 6), (7, 8))) == ((1, 4, 7), (2, 5, 8))
    assert tuple(zipr2((1, 2, 3), (4, 5, 6), (7, 8))) == ((3, 6, 8), (2, 5, 7))

    zipr3 = partial(mapr, identity)
    assert tuple(zipr3((1, 2, 3), (4, 5, 6), (7, 8))) == ((3, 6, 8), (2, 5, 7))

    assert tuple(uniqify((1, 1, 2, 2, 2, 2, 4, 3, 3, 3))) == (1, 2, 4, 3)
    data = (('foo', 1), ('bar', 1), ('foo', 2), ('baz', 2), ('qux', 4), ('foo', 3))
    assert tuple(uniqify(data, key=itemgetter(0))) == (('foo', 1), ('bar', 1), ('baz', 2), ('qux', 4))
    assert tuple(uniqify(data, key=itemgetter(1))) == (('foo', 1), ('foo', 2), ('qux', 4), ('foo', 3))

    assert tuple(flatten(((1, 2), (3, (4, 5), 6), (7, 8, 9)))) == (1, 2, 3, 4, 5, 6, 7, 8, 9)
    assert tuple(flatten1(((1, 2), (3, (4, 5), 6), (7, 8, 9)))) == (1, 2, 3, (4, 5), 6, 7, 8, 9)

    is_nested = lambda e: all(isinstance(x, (tuple, list)) for x in e)
    assert tuple(flatten((((1, 2), (3, 4)), (5, 6)), is_nested)) == ((1, 2), (3, 4), (5, 6))

    data = (((1, 2), ((3, 4), (5, 6)), 7), ((8, 9), (10, 11)))
    assert tuple(flatten(data, is_nested))    == (((1, 2), ((3, 4), (5, 6)), 7), (8, 9), (10, 11))
    assert tuple(flatten_in(data, is_nested)) == (((1, 2), (3, 4), (5, 6), 7),   (8, 9), (10, 11))

    print("All tests PASSED")

if __name__ == '__main__':
    test()
