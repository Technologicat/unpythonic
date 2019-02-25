# -*- coding: utf-8 -*-

from itertools import count, takewhile, chain
from collections import Counter

from ..gmemo import gmemoize, imemoize, fimemoize

from ..it import take, drop, last
from ..misc import call, timer

def test():
    total_evaluations = 0
    @gmemoize
    def gen():
        nonlocal total_evaluations
        j = 1
        while True:
            total_evaluations += 1
            yield j
            j += 1
    g1 = gen()
    g2 = gen()
    assert next(g1) == 1
    assert next(g1) == 2
    assert next(g2) == 1
    assert next(g1) == 3
    assert next(g2) == 2
    assert next(g2) == 3
    assert next(g2) == 4
    assert next(g1) == 4
    g3 = gen()
    assert next(g3) == 1
    assert next(g3) == 2
    assert next(g3) == 3
    assert next(g3) == 4
    assert total_evaluations == 4

    total_evaluations = 0
    @gmemoize
    def gen():
        nonlocal total_evaluations
        for j in range(3):
            total_evaluations += 1
            yield j
    g1 = gen()
    g2 = gen()
    assert total_evaluations == 0
    assert tuple(x for x in g1) == (0, 1, 2)
    assert total_evaluations == 3
    assert tuple(x for x in g2) == (0, 1, 2)
    assert total_evaluations == 3

    # exception memoization
    class AllOkJustTesting(Exception): pass
    total_evaluations = 0
    @gmemoize
    def gen():
        nonlocal total_evaluations
        total_evaluations += 1
        yield 1
        total_evaluations += 1
        raise AllOkJustTesting("ha ha only serious")
    g1 = gen()
    assert total_evaluations == 0
    try:
        next(g1)
        assert total_evaluations == 1
        next(g1)
    except AllOkJustTesting as err:
        exc_instance = err
    else:
        assert False  # should have raised at the second next() call
    assert total_evaluations == 2
    g2 = gen()
    next(g2)
    assert total_evaluations == 2
    try:
        next(g2)
    except AllOkJustTesting as err2:
        if err2 is not exc_instance:
            assert False  # should be the same cached exception instance
    else:
        assert False  # should have raised at the second next() call
    assert total_evaluations == 2

    # Memoizing only a part of a sequence.
    #
    # Build a chain of generators, then memoize only the last one:
    #
    evaluations = Counter()
    def orig():
        yield from range(100)
    def evens():
        yield from (x for x in orig() if x % 2 == 0)
    @gmemoize
    def some_evens(n):  # drop n first terms
        evaluations[n] += 1
        yield from drop(n, evens())
    last(some_evens(25))
    last(some_evens(25))
    last(some_evens(20))
    assert all(v == 1 for k, v in evaluations.items())

    # Or use lambda for a more compact presentation:
    se = gmemoize(lambda n: (yield from drop(n, evens())))
    assert last(se(25)) == last(se(25))  # iterating twice!

    # Using fimemoize, we can omit the "yield from" (specifying a regular
    # factory function that makes an iterable, instead of a gfunc):
    se = fimemoize(lambda n: drop(n, evens()))
    assert last(se(25)) == last(se(25))  # iterating twice!

    # In the nonparametric case, we can memoize the iterable directly:
    se = imemoize(drop(25, evens()))
    assert last(se()) == last(se())  # iterating twice!

    # DANGER: WRONG! Now we get a new instance of evens() also for the same n,
    # so each call to se(n) caches separately. (This is why we have fimemoize.)
    se = lambda n: call(imemoize(drop(n, evens())))  # call() invokes the gfunc
    assert last(se(25)) == last(se(25))
    assert last(se(20)) == last(se(20))

    # sieve of Eratosthenes
    def primes():
        yield 2
        for n in count(start=3, step=2):
            if not any(n % p == 0 for p in takewhile(lambda x: x*x <= n, primes())):
                yield n

    @gmemoize  # <-- the only change (beside the function name)
    def mprimes():
        yield 2
        for n in count(start=3, step=2):
            if not any(n % p == 0 for p in takewhile(lambda x: x*x <= n, mprimes())):
                yield n

    @gmemoize  # skip testing 15, 25, 35, ...
    def mprimes2():
        yield 2
        for n in chain([3, 5, 7], (d + k for d in count(10, step=10)
                                         for k in [1, 3, 7, 9])):
            if not any(n % p == 0 for p in takewhile(lambda x: x*x <= n, mprimes2())):
                yield n

    def memo_primes():  # with manually implemented memoization
        memo = []
        def manual_mprimes():
            memo.append(2)
            yield 2
            for n in count(start=3, step=2):
                if not any(n % p == 0 for p in takewhile(lambda x: x*x <= n, memo)):
                    memo.append(n)
                    yield n
        return manual_mprimes()

    assert tuple(take(10, primes())) == (2, 3, 5, 7, 11, 13, 17, 19, 23, 29)
    assert tuple(take(10, mprimes())) == (2, 3, 5, 7, 11, 13, 17, 19, 23, 29)
    assert tuple(take(10, mprimes2())) == (2, 3, 5, 7, 11, 13, 17, 19, 23, 29)
    assert tuple(take(10, memo_primes())) == (2, 3, 5, 7, 11, 13, 17, 19, 23, 29)

    n = 2500
    print("Performance for first {:d} primes:".format(n))
    for g in (primes(), mprimes(), mprimes2(), memo_primes()):
        with timer() as tictoc:
            last(take(n, g))
        print(g, tictoc.dt)

    print("All tests PASSED")

if __name__ == '__main__':
    test()
