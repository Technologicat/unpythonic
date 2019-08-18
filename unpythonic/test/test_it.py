# -*- coding: utf-8 -*-

from functools import partial
from itertools import tee, count, takewhile
from operator import add, itemgetter
from collections import deque

from ..it import mapr, rmap, zipr, rzip, \
                 map_longest, mapr_longest, rmap_longest, \
                 zip_longest, zipr_longest, rzip_longest, \
                 first, second, nth, last, \
                 scons, tail, butlast, butlastn, \
                 flatmap, \
                 take, drop, split_at, \
                 rev, \
                 uniqify, uniq, \
                 flatten, flatten1, flatten_in, \
                 unpack, \
                 inn, iindex, \
                 window, within

from ..fun import composel, identity
from ..gmemo import imemoize, gmemoize
from ..mathseq import s
from ..misc import Popper

def test():
    def noneadd(a, b):
        if all(x is not None for x in (a, b)):
            return a + b

    # Adding the missing batteries to the algebra of map and zip.
    # Note Python's (and Racket's) map is like Haskell's zipWith, but for n inputs.
    assert tuple(map(add, (1, 2), (3, 4))) == (4, 6)  # builtin
    assert tuple(mapr(add, (1, 2), (3, 4))) == (6, 4)
    assert tuple(rmap(add, (1, 2), (3, 4))) == (6, 4)
    assert tuple(zip((1, 2, 3), (4, 5, 6), (7, 8))) == ((1, 4, 7), (2, 5, 8))  # builtin
    assert tuple(zipr((1, 2, 3), (4, 5, 6), (7, 8))) == ((2, 5, 8), (1, 4, 7))
    assert tuple(rzip((1, 2, 3), (4, 5, 6), (7, 8))) == ((3, 6, 8), (2, 5, 7))
    assert tuple(map_longest(noneadd, (1, 2, 3), (2, 4))) == (3, 6, None)
    assert tuple(mapr_longest(noneadd, (1, 2, 3), (2, 4))) == (None, 6, 3)
    assert tuple(rmap_longest(noneadd, (1, 2, 3), (2, 4))) == (7, 4, None)
    assert tuple(zip_longest((1, 2, 3), (2, 4))) == ((1, 2), (2, 4), (3, None))  # itertools
    assert tuple(zipr_longest((1, 2, 3), (2, 4))) == ((3, None), (2, 4), (1, 2))
    assert tuple(rzip_longest((1, 2, 3), (2, 4))) == ((3, 4), (2, 2), (1, None))

    # Note map and reverse do not commute if inputs have different lengths.
    # map, then reverse; syncs left ends
    assert tuple(mapr(add, (1, 2, 3), (4, 5))) == (7, 5)
    # reverse each, then map; syncs right ends
    assert tuple(rmap(add, (1, 2, 3), (4, 5))) == (8, 6)

    assert first(range(5)) == 0
    assert second(range(5)) == 1
    assert nth(2, range(5)) == 2
    assert last(range(5)) == 4

    assert tuple(scons(0, range(1, 5))) == tuple(range(5))
    assert tuple(tail(scons("foo", range(5)))) == tuple(range(5))

    assert tuple(butlast(range(5))) == (0, 1, 2, 3)
    assert tuple(butlastn(3, range(5))) == (0, 1)

    def msqrt(x):  # multivalued sqrt
        if x == 0.:
            return (0.,)
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
    lzip2 = partial(map, identity)
    rzip2 = lambda *iterables: map(identity, *(rev(s) for s in iterables))
    assert tuple(lzip2((1, 2, 3), (4, 5, 6), (7, 8))) == ((1, 4, 7), (2, 5, 8))
    assert tuple(rzip2((1, 2, 3), (4, 5, 6), (7, 8))) == ((3, 6, 8), (2, 5, 7))

    rzip3 = partial(rmap, identity)
    assert tuple(rzip3((1, 2, 3), (4, 5, 6), (7, 8))) == ((3, 6, 8), (2, 5, 7))

    assert tuple(uniqify((1, 1, 2, 2, 2, 2, 4, 3, 3, 3))) == (1, 2, 4, 3)
    data = (('foo', 1), ('bar', 1), ('foo', 2), ('baz', 2), ('qux', 4), ('foo', 3))
    assert tuple(uniqify(data, key=itemgetter(0))) == (('foo', 1), ('bar', 1), ('baz', 2), ('qux', 4))
    assert tuple(uniqify(data, key=itemgetter(1))) == (('foo', 1), ('foo', 2), ('qux', 4), ('foo', 3))

    assert tuple(uniq((1, 1, 2, 2, 2, 1, 2, 2, 4, 3, 4, 3, 3))) == (1, 2, 1, 2, 4, 3, 4, 3)

    assert tuple(flatten(((1, 2), (3, (4, 5), 6), (7, 8, 9)))) == (1, 2, 3, 4, 5, 6, 7, 8, 9)
    assert tuple(flatten1(((1, 2), (3, (4, 5), 6), (7, 8, 9)))) == (1, 2, 3, (4, 5), 6, 7, 8, 9)

    is_nested = lambda e: all(isinstance(x, (list, tuple)) for x in e)
    assert tuple(flatten((((1, 2), (3, 4)), (5, 6)), is_nested)) == ((1, 2), (3, 4), (5, 6))

    data = (((1, 2), ((3, 4), (5, 6)), 7), ((8, 9), (10, 11)))
    assert tuple(flatten(data, is_nested))    == (((1, 2), ((3, 4), (5, 6)), 7), (8, 9), (10, 11))
    assert tuple(flatten_in(data, is_nested)) == (((1, 2), (3, 4), (5, 6), 7),   (8, 9), (10, 11))

    # lazy unpack from an iterable
    a, b, c, tl = unpack(3, range(5))
    assert a == 0 and b == 1 and c == 2
    assert next(tl) == 3

    # lazy unpack falling off the end of an iterable
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

    # inn: contains-check with automatic termination for monotonic iterables
    evens = imemoize(s(2, 4, ...))
    assert inn(42, evens())
    assert not inn(41, evens())

    @gmemoize
    def primes():
        yield 2
        for n in count(start=3, step=2):
            if not any(n % p == 0 for p in takewhile(lambda x: x*x <= n, primes())):
                yield n
    assert inn(31337, primes())
    assert not inn(1337, primes())

    # iindex: find index of item in iterable (mostly only makes sense for memoized input)
    assert iindex(2, (1, 2, 3)) == 1
    assert iindex(31337, primes()) == 3378
    try:
        iindex(4, (1, 2, 3))
    except ValueError:
        pass  # 4 is not in iterable
    else:
        assert False

    # window: length-n sliding window iterator for general iterables
    lst = list(range(5))
    out = []
    for a, b, c in window(lst, n=3):
        out.append((a, b, c))
    assert lst == list(range(5))
    assert out == [(0, 1, 2), (1, 2, 3), (2, 3, 4)]

    lst = range(5)
    out = []
    for a, b, c in window(lst, n=3):
        out.append((a, b, c))
    assert lst == range(5)
    assert out == [(0, 1, 2), (1, 2, 3), (2, 3, 4)]

    lst = (x for x in range(5))
    out = []
    for a, b, c in window(lst, n=3):
        out.append((a, b, c))
    assert out == [(0, 1, 2), (1, 2, 3), (2, 3, 4)]

    # sneaky integration test: let's window a Popper...
    #
    # This works because window() iter()s the Popper, but the Popper never
    # iter()s the underlying container, so any mutations to the input container
    # performed by the loop body will be seen by the window.
    #
    # (The first n elements, though, are read before the loop body gets control,
    #  because the window needs them to initialize itself.)
    inp = deque(range(3))
    out = []
    for a, b in window(Popper(inp)):
        out.append((a, b))
        if a < 10:
            inp.append(a + 10)
    assert inp == deque([])
    assert out == [(0, 1), (1, 2), (2, 10), (10, 11), (11, 12)]

    # within() - terminate a Cauchy sequence after a tolerance is reached.
    # The condition is `abs(a - b) <= tol` **for the last two yielded items**.
    def g1():
        x = 1.0
        while True:
            yield x
            x /= 2
    assert tuple(within(1/4, g1())) == (1.0, 1/2, 1/4)

    def g2():
        yield 1
        yield 2
        yield 3
        while True:
            yield 4
    assert tuple(within(0, g2())) == (1, 2, 3, 4, 4)

    print("All tests PASSED")

if __name__ == '__main__':
    test()
