# -*- coding: utf-8 -*-

from ..syntax import macros, test, test_raises, the  # noqa: F401
from ..test.fixtures import session, testset

from functools import partial
from itertools import tee, count, takewhile
from operator import add, itemgetter
from collections import deque
from math import cos, sqrt

from ..it import (map, mapr, rmap, zipr, rzip,
                  map_longest, mapr_longest, rmap_longest,
                  zip_longest, zipr_longest, rzip_longest,
                  first, second, nth, last, lastn,
                  scons, pad, tail, butlast, butlastn,
                  flatmap,
                  take, drop, split_at,
                  unpack,
                  rev,
                  uniqify, uniq,
                  flatten, flatten1, flatten_in,
                  iterate1, iterate,
                  partition,
                  partition_int,
                  inn, iindex, find,
                  window, chunked,
                  within, fixpoint,
                  interleave,
                  subset, powerset,
                  allsame)

from ..fun import composel, identity, curry
from ..gmemo import imemoize, gmemoize
from ..mathseq import s
from ..misc import Popper, ulp

def runtests():
    with testset("mapping and zipping"):
        def noneadd(a, b):
            if all(x is not None for x in (a, b)):
                return a + b

        # Our map is a thin wrapper that makes it mandatory to provide at least one iterable,
        # so we can easily curry it with just the function to be applied.
        oneplus = lambda x: 1 + x  # noqa: E731
        add_one = curry(map, oneplus)
        test[tuple(add_one(range(5))) == tuple(range(1, 6))]

        # Adding the missing batteries to the algebra of map and zip.
        # Note Python's (and Racket's) map is like Haskell's zipWith, but for n inputs.
        test[tuple(map(add, (1, 2), (3, 4))) == (4, 6)]  # builtin (or ours, doesn't matter)
        test[tuple(mapr(add, (1, 2), (3, 4))) == (6, 4)]
        test[tuple(rmap(add, (1, 2), (3, 4))) == (6, 4)]
        test[tuple(zip((1, 2, 3), (4, 5, 6), (7, 8))) == ((1, 4, 7), (2, 5, 8))]  # builtin
        test[tuple(zipr((1, 2, 3), (4, 5, 6), (7, 8))) == ((2, 5, 8), (1, 4, 7))]
        test[tuple(rzip((1, 2, 3), (4, 5, 6), (7, 8))) == ((3, 6, 8), (2, 5, 7))]
        test[tuple(map_longest(noneadd, (1, 2, 3), (2, 4))) == (3, 6, None)]
        test[tuple(mapr_longest(noneadd, (1, 2, 3), (2, 4))) == (None, 6, 3)]
        test[tuple(rmap_longest(noneadd, (1, 2, 3), (2, 4))) == (7, 4, None)]
        test[tuple(zip_longest((1, 2, 3), (2, 4))) == ((1, 2), (2, 4), (3, None))]  # itertools
        test[tuple(zipr_longest((1, 2, 3), (2, 4))) == ((3, None), (2, 4), (1, 2))]
        test[tuple(rzip_longest((1, 2, 3), (2, 4))) == ((3, 4), (2, 2), (1, None))]

        # Note map and reverse do not commute if inputs have different lengths.
        # map, then reverse; syncs left ends
        test[tuple(mapr(add, (1, 2, 3), (4, 5))) == (7, 5)]
        # reverse each, then map; syncs right ends
        test[tuple(rmap(add, (1, 2, 3), (4, 5))) == (8, 6)]

        # Python's builtin map is not curry-friendly; it accepts arity 1,
        # but actually requires 2. Solution: use partial instead of curry.
        lzip2 = partial(map, identity)
        rzip2 = lambda *iterables: map(identity, *(rev(s) for s in iterables))
        test[tuple(lzip2((1, 2, 3), (4, 5, 6), (7, 8))) == ((1, 4, 7), (2, 5, 8))]
        test[tuple(rzip2((1, 2, 3), (4, 5, 6), (7, 8))) == ((3, 6, 8), (2, 5, 7))]

        rzip3 = partial(rmap, identity)
        test[tuple(rzip3((1, 2, 3), (4, 5, 6), (7, 8))) == ((3, 6, 8), (2, 5, 7))]

    with testset("first, second, nth, last"):
        test[first(range(5)) == 0]
        test[second(range(5)) == 1]
        test[nth(2, range(5)) == 2]
        test[last(range(5)) == 4]

        test_raises[TypeError, nth("not a number", range(5))]
        test_raises[ValueError, nth(-3, range(5))]
        test[nth(10, range(5)) is None]  # default

    with testset("scons (stream-cons)"):
        test[tuple(scons(0, range(1, 5))) == tuple(range(5))]
        test[tuple(tail(scons("foo", range(5)))) == tuple(range(5))]

    with testset("flattening"):
        test[tuple(flatten(((1, 2), (3, (4, 5), 6), (7, 8, 9)))) == (1, 2, 3, 4, 5, 6, 7, 8, 9)]
        test[tuple(flatten1(((1, 2), (3, (4, 5), 6), (7, 8, 9)))) == (1, 2, 3, (4, 5), 6, 7, 8, 9)]

        test[tuple(flatten1(((1, 2), (3, (4, 5), 6), (7, 8, 9)),
                            lambda tup: len(tup) < 3)) == (1, 2, (3, (4, 5), 6), (7, 8, 9))]

        is_nested = lambda e: all(isinstance(x, (list, tuple)) for x in e)
        test[tuple(flatten((((1, 2), (3, 4)), (5, 6)), is_nested)) == ((1, 2), (3, 4), (5, 6))]

        data = (((1, 2), ((3, 4), (5, 6)), 7), ((8, 9), (10, 11)))
        test[tuple(flatten(data, is_nested)) == (((1, 2), ((3, 4), (5, 6)), 7), (8, 9), (10, 11))]
        test[tuple(flatten_in(data, is_nested)) == (((1, 2), (3, 4), (5, 6), 7), (8, 9), (10, 11))]

        def msqrt(x):  # multivalued sqrt
            if x == 0.:
                return (0.,)
            s = x**0.5
            return (s, -s)
        test[tuple(flatmap(msqrt, (0, 1, 4, 9))) == (0., 1., -1., 2., -2., 3., -3.)]

        def add_and_tuplify(a, b):
            return (a + b,)
        test[tuple(flatmap(add_and_tuplify, (10, 20, 30), (1, 2, 3))) == (11, 22, 33)]

        def sum_and_diff(a, b):
            return (a + b, a - b)
        test[tuple(flatmap(sum_and_diff, (10, 20, 30), (1, 2, 3))) == (11, 9, 22, 18, 33, 27)]

    with testset("take, drop, lastn, butlastn, butlast"):
        test[tuple(take(10, range(100))) == tuple(range(10))]
        test[tuple(take(10, range(3))) == tuple(range(3))]

        test[tuple(drop(5, range(10))) == tuple(range(5, 10))]
        test[tuple(drop(5, range(3))) == ()]

        test[tuple(lastn(3, range(5))) == (2, 3, 4)]
        test[tuple(lastn(3, range(2))) == (0, 1)]
        test[tuple(lastn(3, ())) == ()]

        test[tuple(butlast(range(5))) == (0, 1, 2, 3)]
        test[tuple(butlastn(3, range(5))) == (0, 1)]

        test[tuple(butlastn(5, range(5))) == ()]
        test[tuple(butlastn(10, range(5))) == ()]

        drop5take5 = composel(partial(drop, 5), partial(take, 5))
        test[tuple(drop5take5(range(20))) == tuple(range(5, 10))]

        with_same_n = lambda n, fs: (partial(f, n) for f in fs)
        # with_same_n = lambda n, fs: map((lambda f: partial(f, n)), fs)
        drop5take5 = composel(*with_same_n(5, (drop, take)))
        test[tuple(drop5take5(range(20))) == tuple(range(5, 10))]

        with_n = lambda *args: (partial(f, n) for n, f in args)
        drop5take10 = composel(*with_n((5, drop), (10, take)))
        test[tuple(drop5take10(range(20))) == tuple(range(5, 15))]

        # drop with n=None means to consume until the iterable runs out.
        test[tuple(drop(None, range(10))) == ()]

        test_raises[TypeError, take("not a number", range(5))]
        test_raises[ValueError, take(-3, range(5))]
        test_raises[TypeError, drop("not a number", range(5))]
        test_raises[ValueError, drop(-3, range(5))]

    with testset("split_at"):
        a, b = map(tuple, split_at(5, range(10)))
        test[a == tuple(range(5))]
        test[b == tuple(range(5, 10))]

        a, b = map(tuple, split_at(5, range(3)))
        test[a == tuple(range(3))]
        test[b == ()]

        test_raises[TypeError, split_at("not a number", range(10))]
        test_raises[ValueError, split_at(-3, range(10))]

    with testset("uniqify, uniq"):
        test[tuple(uniqify((1, 1, 2, 2, 2, 2, 4, 3, 3, 3))) == (1, 2, 4, 3)]
        data = (('foo', 1), ('bar', 1), ('foo', 2), ('baz', 2), ('qux', 4), ('foo', 3))
        test[tuple(uniqify(data, key=itemgetter(0))) == (('foo', 1), ('bar', 1), ('baz', 2), ('qux', 4))]
        test[tuple(uniqify(data, key=itemgetter(1))) == (('foo', 1), ('foo', 2), ('qux', 4), ('foo', 3))]

        test[tuple(uniq((1, 1, 2, 2, 2, 1, 2, 2, 4, 3, 4, 3, 3))) == (1, 2, 1, 2, 4, 3, 4, 3)]

    with testset("unpack (lazily)"):
        a, b, c, tl = unpack(3, range(5))
        test[the[a] == 0 and the[b] == 1 and the[c] == 2]
        test[next(tl) == 3]

        # lazy unpack falling off the end of an iterable
        a, b, c, tl = unpack(3, range(2))
        test[the[a] == 0 and the[b] == 1 and the[c] is None]
        test_raises[StopIteration, next(tl)]  # the tail should be empty

        # unpacking of generators - careful!
        def ten_through_fifteen():
            for x in range(10, 16):
                yield x
        def peektwo(s):
            a, b, tl = unpack(2, s, k=0)  # peek two, set tl to 0th tail (the original s)
            # ...do something with a and b...
            return tl
        g = ten_through_fifteen()
        peektwo(g)  # gotcha: g itself advances!
        test[next(g) == 12]

        # workaround 1: tee off a copy manually with `itertools.tee`:
        g = ten_through_fifteen()
        g, h = tee(g)
        peektwo(g)  # g advances, but h doesn't
        test[next(h) == 10]

        # workaround 2: use the implicit tee in unpack:
        g = ten_through_fifteen()
        g = peektwo(g)  # the original g advances, but we then overwrite the name g with the tail returned by peektwo
        test[next(g) == 10]

        test_raises[TypeError, unpack("not a number", range(5))]
        test_raises[ValueError, unpack(-3, range(5))]
        test_raises[TypeError, unpack(3, range(5), k="not a number")]
        test_raises[ValueError, unpack(3, range(5), k=-3)]

        # fast-forward when k > n
        a, b, tl = unpack(2, range(5), k=3)
        test[the[a] == 0 and the[b] == 1]
        test[next(tl) == 3]

    # inn: contains-check with automatic termination for monotonic divergent iterables
    with testset("inn"):
        evens = imemoize(s(2, 4, ...))
        test[inn(42, evens())]
        test[not inn(41, evens())]

        @gmemoize
        def primes():
            yield 2
            for n in count(start=3, step=2):
                if not any(n % p == 0 for p in takewhile(lambda x: x * x <= n, primes())):
                    yield n
        test[inn(31337, primes())]
        test[not inn(1337, primes())]

        # corner cases
        test[not inn(10, ())]  # empty input
        test[inn(10, (10,))]  # match at first element
        test[not inn(11, (10,))]  # fail after one element
        test[not inn(11, (10, 10, 10))]  # fail after elements equal to the first one
        test[inn(11, (10, 10, 10, 11))]  # match at first element differing from the first one

    # iindex: find index of item in iterable (mostly only makes sense for memoized input)
    with testset("iindex"):
        test[iindex(2, (1, 2, 3)) == 1]
        test[iindex(31337, primes()) == 3378]
        test_raises[ValueError, iindex(4, (1, 2, 3))]  # 4 is not in the iterable being tested

    # find: return first matching element from an iterable
    # Convenience function; if you need them all, just filter or use a comprehension.
    with testset("find"):
        lst = list(range(5))
        test[find(lambda x: x >= 3, lst) == 3]
        test[find(lambda x: x >= 3 and x % 2 == 0, lst) == 4]
        test[find(lambda x: x == 10, lst) is None]
        test[find(lambda x: x == 10, lst, default=42) == 42]

        # a consumable iterable is consumed, as usual
        gen = (x for x in range(5))
        test[find(lambda x: x >= 3, gen) == 3]
        test[find(lambda x: x >= 3, gen) == 4]
        test[find(lambda x: x >= 3, gen) is None]

    # pad: extend an iterable with a fillvalue
    with testset("pad"):
        test[tuple(pad(5, None, range(3))) == (0, 1, 2, None, None)]
        test[tuple(pad(5, None, ())) == (None, None, None, None, None)]
        test[tuple(pad(5, None, range(6))) == tuple(range(6))]

    # window: length-n sliding window iterator for general iterables
    with testset("window"):
        lst = list(range(5))
        out = []
        for a, b, c in window(lst, n=3):
            out.append((a, b, c))
        test[lst == list(range(5))]
        test[out == [(0, 1, 2), (1, 2, 3), (2, 3, 4)]]

        lst = range(5)
        out = []
        for a, b, c in window(lst, n=3):
            out.append((a, b, c))
        test[lst == range(5)]
        test[out == [(0, 1, 2), (1, 2, 3), (2, 3, 4)]]

        lst = (x for x in range(5))
        out = []
        for a, b, c in window(lst, n=3):
            out.append((a, b, c))
        test[out == [(0, 1, 2), (1, 2, 3), (2, 3, 4)]]

        test_raises[ValueError, window(range(5), n=1)]
        test[tuple(window(range(5), n=10)) == ()]

    with testset("window integration with Popper"):
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
        test[inp == deque([])]
        test[out == [(0, 1), (1, 2), (2, 10), (10, 11), (11, 12)]]

    # chunked() - split an iterable into constant-length chunks.
    with testset("chunked"):
        chunks = chunked(3, range(9))
        test[[tuple(chunk) for chunk in chunks] == [(0, 1, 2), (3, 4, 5), (6, 7, 8)]]
        chunks = chunked(3, range(7))
        test[[tuple(chunk) for chunk in chunks] == [(0, 1, 2), (3, 4, 5), (6,)]]

        test_raises[ValueError, chunked(1, range(5))]

    # Interleave iterables.
    with testset("interleave"):
        test[tuple(interleave((1, 2, 3), (4, 5, 6))) == (1, 4, 2, 5, 3, 6)]

        # It round-robins until the shortest input runs out.
        a = ('a', 'b', 'c')
        b = ('+', '*')
        test[tuple(interleave(a, b)) == ('a', '+', 'b', '*', 'c')]

    with testset("subset"):
        test[subset([1, 2, 3], [1, 2, 3, 4, 5])]
        test[subset({"cat"}, {"cat", "lynx"})]

    # Power set (set of all subsets) of an iterable.
    with testset("powerset"):
        test[tuple(powerset(range(3))) == ((0,), (1,), (0, 1), (2,), (0, 2), (1, 2), (0, 1, 2))]
        r = tuple(range(5))
        test[all(subset(tuple(s), r) for s in powerset(r))]
        S = {"cat", "lynx", "lion", "tiger"}  # unordered
        test[all(subset(tuple(s), S) for s in powerset(S))]

    # repeated function application
    with testset("iterate1, iterate"):
        test[last(take(100, iterate1(cos, 1.0))) == 0.7390851332151607]

        # Multi-arg version (n in, n out). May as well demonstrate that
        # it doesn't matter where you start, the fixed point of cosine
        # remains the same.
        def cos3(a, b, c):
            return cos(a), cos(b), cos(c)
        fp = 0.7390851332151607
        test[the[last(take(100, iterate(cos3, 1.0, 2.0, 3.0)))] == (the[fp], fp, fp)]

    # within() - terminate a Cauchy sequence after a tolerance is reached.
    # The condition is `abs(a - b) <= tol` **for the last two yielded items**.
    with testset("within (Cauchy sequences)"):
        def g1():
            x = 1.0
            while True:
                yield x
                x /= 2
        test[tuple(within(1 / 4, g1())) == (1.0, 1 / 2, 1 / 4)]

        def g2():
            yield 1
            yield 2
            yield 3
            while True:
                yield 4
        test[tuple(within(0, g2())) == (1, 2, 3, 4, 4)]

    # Arithmetic fixed points.
    with testset("fixpoint (arithmetic fixed points)"):
        c = fixpoint(cos, x0=1)
        test[the[c] == the[cos(c)]]  # 0.7390851332151607

        # Actually "Newton's" algorithm for the square root was already known to the
        # ancient Babylonians, ca. 2000 BCE. (Carl Boyer: History of mathematics)
        def sqrt_newton(n):
            def sqrt_iter(x):  # has an attractive fixed point at sqrt(n)
                return (x + n / x) / 2
            return fixpoint(sqrt_iter, x0=n / 2)
        # different algorithm, so not necessarily equal down to the last bit
        # (caused by the fixpoint update becoming smaller than the ulp, so it
        #  stops there, even if the limit is still one ulp away).
        test[abs(the[sqrt_newton(2)] - the[sqrt(2)]) <= the[ulp(1.414)]]

    # partition: split an iterable according to a predicate
    with testset("partition"):
        iseven = lambda item: item % 2 == 0
        test[[tuple(it) for it in partition(iseven, range(10))] == [(1, 3, 5, 7, 9), (0, 2, 4, 6, 8)]]

    # partition_int: split a small positive integer, in all possible ways, into smaller integers that sum to it
    with testset("partition_int"):
        test[tuple(partition_int(4)) == ((4,), (3, 1), (2, 2), (2, 1, 1), (1, 3), (1, 2, 1), (1, 1, 2), (1, 1, 1, 1))]
        test[tuple(partition_int(5, lower=2)) == ((5,), (3, 2), (2, 3))]
        test[tuple(partition_int(5, lower=2, upper=3)) == ((3, 2), (2, 3))]
        test[tuple(partition_int(10, lower=3, upper=5)) == ((5, 5), (4, 3, 3), (3, 4, 3), (3, 3, 4))]
        test[all(sum(terms) == 10 for terms in partition_int(10))]
        test[all(sum(terms) == 10 for terms in partition_int(10, lower=3))]
        test[all(sum(terms) == 10 for terms in partition_int(10, lower=3, upper=5))]

        test_raises[TypeError, partition_int("not a number")]
        test_raises[TypeError, partition_int(4, lower="not a number")]
        test_raises[TypeError, partition_int(4, upper="not a number")]
        test_raises[ValueError, partition_int(-3)]
        test_raises[ValueError, partition_int(4, lower=-1)]
        test_raises[ValueError, partition_int(4, lower=5)]
        test_raises[ValueError, partition_int(4, upper=-1)]
        test_raises[ValueError, partition_int(4, upper=5)]
        test_raises[ValueError, partition_int(4, lower=3, upper=2)]

    with testset("allsame"):
        test[allsame(())]
        test[allsame((1,))]
        test[allsame((8, 8, 8, 8, 8))]
        test[not allsame((1, 2, 3))]

if __name__ == '__main__':  # pragma: no cover
    with session(__file__):
        runtests()
