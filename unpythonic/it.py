#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Missing batteries for itertools.

Racket-like multi-input ``foldl`` and ``foldr`` based on
  https://docs.racket-lang.org/reference/pairs.html

``scanl`  and ``scanr`` inspired by ``itertools.accumulate``, Haskell,
and (stream-scan) in SRFI-41.
  https://srfi.schemers.org/srfi-41/srfi-41.html

``flatten`` based on Danny Yoo's version:
  http://rightfootin.blogspot.fi/2006/09/more-on-python-flatten.html
"""

__all__ = ["map_longest", "mapr", "zipr", "mapr_longest", "zipr_longest",
           "flatmap", "uniqify", "uniq",
           "take", "drop", "split_at", "unpack",
           "tail", "first", "second", "nth", "last", "scons",
           "flatten", "flatten1", "flatten_in",
           "iterate", "iterate1"]

from operator import itemgetter
from functools import partial
from itertools import tee, islice, zip_longest, starmap, chain, filterfalse, groupby
from collections import deque

# When completing an existing set of functions (map, zip, zip_longest),
# consistency wins over curry-friendliness.
def map_longest(func, *iterables, fillvalue=None):
    """Like map, but terminate on the longest input.

    In the input to ``func``, missing elements (after end of shorter inputs)
    are replaced by ``fillvalue``, which defaults to ``None``.
    """
    return starmap(func, zip_longest(*iterables, fillvalue=fillvalue))

def mapr(func, *sequences):
    """Like map, but walk each sequence from the right."""
    return map(func, *(reversed(s) for s in sequences))

def zipr(*sequences):
    """Like zip, but walk each sequence from the right."""
    return zip(*(reversed(s) for s in sequences))

def mapr_longest(func, *sequences, fillvalue=None):
    """Like map_longest, but walk each sequence from the right."""
    return map_longest(func, *(reversed(s) for s in sequences), fillvalue=fillvalue)

def zipr_longest(*sequences, fillvalue=None):
    """Like itertools.zip_longest, but walk each sequence from the right."""
    return zip_longest(*(reversed(s) for s in sequences), fillvalue=fillvalue)

def flatmap(f, iterable0, *iterables):
    """Map, then concatenate results.

    At least one iterable (``iterable0``) is required. More are optional.

    ``f`` should accept as many arguments as iterables given (each argument
    drawn from one of the iterables), and return an iterable.

    Returns an iterator that yields the flatmapped result.

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
    return chain.from_iterable(map(f, iterable0, *iterables))
#    for xs in map(f, iterable0, *iterables):
#        yield from xs

def uniqify(iterable, *, key=None):
    """Skip duplicates in iterable.

    Returns a generator that yields unique items from iterable, preserving
    their original ordering.

    If ``key`` is provided, the return value of ``key(elt)`` is tested instead
    of ``elt`` itself to determine uniqueness.

    This is ``unique_everseen`` from ``itertools`` recipes.
    """
    it = iter(iterable)
    seen = set()
    seen_add = seen.add
    if key is None:
        for e in filterfalse(seen.__contains__, it):
            seen_add(e)
            yield e
    else:
        for e in it:
            k = key(e)
            if k not in seen:
                seen_add(k)
                yield e

def uniq(iterable, *, key=None):
    """Like uniqify, but for consecutive duplicates only.

    Named after the *nix utility.

    This is ``unique_justseen`` from ``itertools`` recipes.
    """
    # the outer map retrieves the item from the subiterator in (key, subiterator).
    return map(next, map(itemgetter(1), groupby(iterable, key)))

def take(n, iterable):
    """Return an iterator that yields the first n items of iterable, then stops.

    Stops earlier if ``iterable`` has fewer than ``n`` items.

    This is ``take`` from ``itertools`` recipes.
    """
    if not isinstance(n, int):
        raise TypeError("expected integer n, got {} with value {}".format(type(n), n))
    if n < 0:
        raise ValueError("expected n >= 0, got {}".format(n))
    return islice(iter(iterable), n)

def drop(n, iterable):
    """Skip the first n elements of iterable, then yield the rest.

    If ``n`` is ``None``, consume the iterable until it runs out.

    This is ``consume`` from ``itertools`` recipes.
    """
    if not isinstance(n, int):
        raise TypeError("expected integer n, got {} with value {}".format(type(n), n))
    if n < 0:
        raise ValueError("expected n >= 0, got {}".format(n))
    it = iter(iterable)
    if n is None:
        deque(it, maxlen=0)
    else:
        next(islice(it, n, n), None)  # advance it to empty slice starting at n
    return it

def split_at(n, iterable):
    """Split iterable at position n.

    Returns a pair of iterators ``(first_part, second_part)``.

    Based on ``itertools.tee``, ``take`` and ``drop``.

    Examples::

        a, b = split_at(5, range(10))
        assert tuple(a) == tuple(range(5))
        assert tuple(b) == tuple(range(5, 10))

        a, b = map(tuple, split_at(5, range(3)))
        assert a == tuple(range(3))
        assert b == ()
    """
    if not isinstance(n, int):
        raise TypeError("expected integer n, got {} with value {}".format(type(n), n))
    if n < 0:
        raise ValueError("expected n >= 0, got {}".format(n))
    ia, ib = tee(iter(iterable))
    return take(n, ia), drop(n, ib)

def unpack(n, iterable, *, k=None, fillvalue=None):
    """From iterable, return the first n elements, and the kth tail.

    This is a lazy generalization of sequence unpacking that works also for
    infinite iterables.

    Default ``k=None`` means ``k = n``, i.e. return the tail that begins
    right after the extracted items. Other values are occasionally useful,
    e.g. to peek into the tail, while not permanently extracting an item.

    The return value is a tuple containing the ``n`` first elements, and as its
    last item, an iterator representing the tail of the iterable from item ``k``
    onwards.

    If there are fewer than ``n`` items in the iterable, the missing items
    are returned as ``fillvalue``. The tail is then a generator that just
    raises ``StopIteration``.

    If ``k < n`` (tail overlaps with the extracted items), the tail
    is formed by calling ``itertools.tee`` at the appropriate point
    during the extraction. (Plan the client code accordingly; see the
    caution in `itertools.tee`. Essentially, the original iterator should
    no longer be used after it has been tee'd; only use the tee'd copy.)

    If ``k == n`` (tail begins right after the extracted items), the tail
    is the original iterator at the end of the extraction.

    If ``k > n`` (skip some items after the first n), then after extraction,
    the tail is formed by fast-forwarding the iterator using ``drop``.
    """
    if not isinstance(n, int):
        raise TypeError("expected integer n, got {} with value {}".format(type(n), n))
    if n < 0:
        raise ValueError("expected n >= 0, got {}".format(n))
    k = k if k is not None else n  # not "k or n", since k = 0 is valid
    if not isinstance(k, int):
        raise TypeError("expected integer k, got {} with value {}".format(type(k), k))
    if k < 0:
        raise ValueError("expected k >= 0, got {}".format(k))
    out = []
    tl = None
    it = iter(iterable)
    for j in range(n):
        try:
            if j == k:  # tail is desired to overlap with the extracted items
                it, tl = tee(it)
            out.append(next(it))
        except StopIteration:  # fewer than n items
            out += [fillvalue] * (n - len(out))
            def empty_sequence():
                yield from ()
            tl = empty_sequence()
            break
    if not tl:  # avoid replacing empty_sequence()
        if k == n:
            tl = it
        elif k > n:
            tl = drop(k - n, it)
    out.append(tl)
    return tuple(out)

def tail(iterable):
    """Return an iterator pointing to the tail of iterable.

    Same as ```drop(1, iterable)```.
    """
    return drop(1, iterable)

def first(iterable, *, default=None):
    """Like nth, but return the first item."""
    return nth(0, iterable, default=default)

def second(iterable, *, default=None):
    """Like nth, but return the second item."""
    return nth(1, iterable, default=default)

def nth(n, iterable, *, default=None):
    """Return the item at position n from an iterable.

    The ``default`` is returned if there are fewer than ``n + 1`` items.
    """
    if not isinstance(n, int):
        raise TypeError("expected integer n, got {} with value {}".format(type(n), n))
    if n < 0:
        raise ValueError("expected n >= 0, got {}".format(n))
    it = drop(n - 1, iterable) if n else iter(iterable)
    try:
        return next(it)
    except StopIteration:
        return default

def last(iterable, *, default=None):
    """Return the last item from an iterable.

    We consume the iterable until it runs out of items, then return the
    last item seen.

    The default value is returned if the iterable contained no items.

    **Caution**: Will not terminate for infinite inputs.
    """
    d = deque(iterable, maxlen=1)  # C speed
    return d.pop() if d else default

def scons(x, iterable):
    """Prepend one element to the start of an iterable, return new iterable.

    Same as ``itertools.chain((x,), iterable)``. The point is sometimes it is
    convenient to be able to stuff one item in front of an existing iterator.
    If ``iterable`` is a generator, this is somewhat like (stream-cons) in Racket.

    If you need to prepend several values, just use ``itertools.chain``.
    """
    return chain((x,), iterable)

def flatten(iterable, pred=None):
    """Recursively remove nested structure from iterable.

    Process tuples and lists inside the iterable; pass everything else through
    (including any iterators stored in the iterable).

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
    if pred:
        return _flatten(iterable, pred, recursive=False)
    else:
        return chain.from_iterable(iterable)  # itertools recipes: fast, no pred

def _flatten(iterable, pred=None, recursive=True):
    pred = pred or (lambda x: True)  # unpythonic.fun.const(True), but dependency loop
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
                yield t(flatten_in(e, pred))
        else:
            yield e

def iterate1(f, x):
    """Return an infinite generator yielding x, f(x), f(f(x)), ..."""
    while True:
        yield x
        x = f(x)

def iterate(f, *args):
    """Multiple-argument version of iterate1.

    The function ``f`` should return a tuple or list of as many elements as it
    takes positional arguments; this will be unpacked to the argument list in
    the next call.

    Or in other words, yield args, f(*args), f(*f(*args)), ...
    """
    while True:
        yield args
        args = f(*args)

def test():
    from operator import add
    from unpythonic.fun import composel, identity

    def noneadd(a, b):
        if all(x is not None for x in (a, b)):
            return a + b

    # Adding the missing batteries to the algebra of map and zip.
    # Note Python's (and Racket's) map is like Haskell's zipWith, but for n inputs.
    assert tuple(map(add, (1, 2), (3, 4))) == (4, 6)  # builtin
    assert tuple(mapr(add, (1, 2), (3, 4))) == (6, 4)
    assert tuple(zip((1, 2, 3), (4, 5, 6), (7, 8))) == ((1, 4, 7), (2, 5, 8))  # builtin
    assert tuple(zipr((1, 2, 3), (4, 5, 6), (7, 8))) == ((3, 6, 8), (2, 5, 7))
    assert tuple(map_longest(noneadd, (1, 2, 3), (2, 4))) == (3, 6, None)
    assert tuple(mapr_longest(noneadd, (1, 2, 3), (2, 4))) == (7, 4, None)
    assert tuple(zip_longest((1, 2, 3), (2, 4))) == ((1, 2), (2, 4), (3, None))  # itertools
    assert tuple(zipr_longest((1, 2, 3), (2, 4))) == ((3, 4), (2, 2), (1, None))

    assert tuple(scons(0, range(1, 5))) == tuple(range(5))
    assert tuple(tail(scons("foo", range(5)))) == tuple(range(5))

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

    drop5take5 = composel(partial(drop, 5), partial(take, 5))
    assert tuple(drop5take5(range(20))) == tuple(range(5, 10))

    with_same_n = lambda n, fs: (partial(f, n) for f in fs)
#    with_same_n = lambda n, fs: map((lambda f: partial(f, n)), fs)
    drop5take5 = composel(*with_same_n(5, (drop, take)))
    assert tuple(drop5take5(range(20))) == tuple(range(5, 10))

    with_n = lambda *args: (partial(f, n) for n, f in args)
    drop5take10 = composel(*with_n((5, drop), (10, take)))
    assert tuple(drop5take10(range(20))) == tuple(range(5, 15))

    a, b = map(tuple, split_at(5, range(10)))
    assert a == tuple(range(5))
    assert b == tuple(range(5, 10))

    a, b = map(tuple, split_at(5, range(3)))
    assert a == tuple(range(3))
    assert b == ()

    # Python's builtin map is not curry-friendly; it accepts arity 1,
    # but actually requires 2. Solution: use partial instead of curry.
    zipl2 = partial(map, identity)
    zipr2 = lambda *sequences: map(identity, *(reversed(s) for s in sequences))
    assert tuple(zipl2((1, 2, 3), (4, 5, 6), (7, 8))) == ((1, 4, 7), (2, 5, 8))
    assert tuple(zipr2((1, 2, 3), (4, 5, 6), (7, 8))) == ((3, 6, 8), (2, 5, 7))

    zipr3 = partial(mapr, identity)
    assert tuple(zipr3((1, 2, 3), (4, 5, 6), (7, 8))) == ((3, 6, 8), (2, 5, 7))

    assert tuple(uniqify((1, 1, 2, 2, 2, 2, 4, 3, 3, 3))) == (1, 2, 4, 3)
    data = (('foo', 1), ('bar', 1), ('foo', 2), ('baz', 2), ('qux', 4), ('foo', 3))
    assert tuple(uniqify(data, key=itemgetter(0))) == (('foo', 1), ('bar', 1), ('baz', 2), ('qux', 4))
    assert tuple(uniqify(data, key=itemgetter(1))) == (('foo', 1), ('foo', 2), ('qux', 4), ('foo', 3))

    assert tuple(uniq((1, 1, 2, 2, 2, 1, 2, 2, 4, 3, 4, 3, 3))) == (1, 2, 1, 2, 4, 3, 4, 3)

    assert tuple(flatten(((1, 2), (3, (4, 5), 6), (7, 8, 9)))) == (1, 2, 3, 4, 5, 6, 7, 8, 9)
    assert tuple(flatten1(((1, 2), (3, (4, 5), 6), (7, 8, 9)))) == (1, 2, 3, (4, 5), 6, 7, 8, 9)

    is_nested = lambda e: all(isinstance(x, (tuple, list)) for x in e)
    assert tuple(flatten((((1, 2), (3, 4)), (5, 6)), is_nested)) == ((1, 2), (3, 4), (5, 6))

    data = (((1, 2), ((3, 4), (5, 6)), 7), ((8, 9), (10, 11)))
    assert tuple(flatten(data, is_nested))    == (((1, 2), ((3, 4), (5, 6)), 7), (8, 9), (10, 11))
    assert tuple(flatten_in(data, is_nested)) == (((1, 2), (3, 4), (5, 6), 7),   (8, 9), (10, 11))

    # lazy unpack from a sequence
    a, b, c, tl = unpack(3, range(5))
    assert a == 0 and b == 1 and c == 2
    assert next(tl) == 3

    # lazy unpack falling off the end of a sequence
    a, b, c, tl = unpack(3, range(2))
    assert a == 0 and b == 1 and c is None
    try:
        next(tl)
    except StopIteration:
        pass
    else:
        assert False  # the tail should be empty

    # unpacking of generators - careful!
    def mygen():
        for x in range(10, 16):
            yield x
    def dostuff(s):
        a, b, tl = unpack(2, s, k=0)  # peek two, set tl to 0th tail (the original s)
        return tl
    g = mygen()
    dostuff(g)  # gotcha: advances g!
    assert next(g) == 12

    # workaround 1: tee off a copy with itertools.tee:
    g = mygen()
    g, h = tee(g)
    dostuff(g)  # advances g, but not h
    assert next(h) == 10

    # workaround 2: use the implicit tee in unpack:
    g = mygen()
    g = dostuff(g)  # advances g, but then overwrites name g with the returned tail
    assert next(g) == 10

    print("All tests PASSED")

if __name__ == '__main__':
    test()
