# -*- coding: utf-8 -*-

from ..syntax import macros, test, test_raises, fail  # noqa: F401
from .fixtures import testset

from itertools import count, takewhile, chain
from collections import Counter

from ..gmemo import gmemoize, imemoize, fimemoize

from ..it import take, drop, last
from ..fold import prod
from ..misc import call, timer

def runtests():
    with testset("unpythonic.gmemo"):
        with testset("multiple instances, interleaved"):
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
            test[next(g1) == 1]
            test[next(g1) == 2]
            test[next(g2) == 1]
            test[next(g1) == 3]
            test[next(g2) == 2]
            test[next(g2) == 3]
            test[next(g2) == 4]
            test[next(g1) == 4]
            g3 = gen()
            test[next(g3) == 1]
            test[next(g3) == 2]
            test[next(g3) == 3]
            test[next(g3) == 4]
            test[total_evaluations == 4]

        with testset("multiple instances, exhaust one first"):
            total_evaluations = 0
            @gmemoize
            def gen():
                nonlocal total_evaluations
                for j in range(3):
                    total_evaluations += 1
                    yield j
            g1 = gen()
            g2 = gen()
            test[total_evaluations == 0]
            test[tuple(x for x in g1) == (0, 1, 2)]
            test[total_evaluations == 3]
            test[tuple(x for x in g2) == (0, 1, 2)]
            test[total_evaluations == 3]

        with testset("@gmemoize caches exceptions"):
            class AllOkJustTesting(Exception):
                pass
            total_evaluations = 0
            @gmemoize
            def gen():
                nonlocal total_evaluations
                total_evaluations += 1
                yield 1
                total_evaluations += 1
                raise AllOkJustTesting("ha ha only serious")

            g1 = gen()
            test[total_evaluations == 0]
            try:
                next(g1)
                test[total_evaluations == 1]
                next(g1)
            except AllOkJustTesting as err:
                exc_instance = err
            else:
                fail["Should have raised at the second next() call."]
            test[total_evaluations == 2]

            g2 = gen()
            next(g2)
            test[total_evaluations == 2]  # still just two, it's memoized
            try:
                next(g2)
            except AllOkJustTesting as err2:
                test[err2 is exc_instance, "should be the same cached exception instance"]
            else:
                fail["Should have raised at the second next() call."]
            test[total_evaluations == 2]

        with testset("memoizing a sequence partially"):
            # To do this, build a chain of generators, then memoize only the last one:
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
            test[all(v == 1 for k, v in evaluations.items())]

            # Or use lambda for a more compact presentation:
            se = gmemoize(lambda n: (yield from drop(n, evens())))
            test[last(se(25)) == last(se(25))]  # iterating twice!

            # Using fimemoize, we can omit the "yield from" (specifying a regular
            # factory function that makes an iterable, instead of a gfunc):
            se = fimemoize(lambda n: drop(n, evens()))
            test[last(se(25)) == last(se(25))]  # iterating twice!

            # In the nonparametric case, we can memoize the iterable directly:
            se = imemoize(drop(25, evens()))
            test[last(se()) == last(se())]  # iterating twice!

            # DANGER: WRONG! Now we get a new instance of evens() also for the same n,
            # so each call to se(n) caches separately. (This is why we have fimemoize.)
            se = lambda n: call(imemoize(drop(n, evens())))  # call() invokes the gfunc
            test[last(se(25)) == last(se(25))]
            test[last(se(20)) == last(se(20))]

        with testset("FP sieve of Eratosthenes"):
            def primes():  # no memoization, recomputes unnecessarily, very slow
                yield 2
                for n in count(start=3, step=2):
                    if not any(n % p == 0 for p in takewhile(lambda x: x * x <= n, primes())):
                        yield n

            @gmemoize  # <-- the only change (beside the function name)
            def mprimes():  # external memo for users, re-use it internally - simplest code
                yield 2
                for n in count(start=3, step=2):
                    if not any(n % p == 0 for p in takewhile(lambda x: x * x <= n, mprimes())):
                        yield n

            def memo_primes():  # manual internal memo only - fastest, no caching for users
                memo = []
                def manual_mprimes():
                    memo.append(2)
                    yield 2
                    for n in count(start=3, step=2):
                        if not any(n % p == 0 for p in takewhile(lambda x: x * x <= n, memo)):
                            memo.append(n)
                            yield n
                return manual_mprimes()

            # external memo for users, separate manual internal memo
            # doubles memory usage due to exactly one internal memo; almost as fast as memo_primes
            # since the tight inner loop skips the very general gmemoize machinery
            #
            # This version wins in speed for moderate n (1e5) on typical architectures where
            # the memory bus is a bottleneck, since the rule for generating new candidates is
            # simple arithmetic. Contrast memo_primes3, which needs to keep a table that gets
            # larger as n grows (so memory transfers dominate for large n). That strategy
            # seems faster for n ~ 1e3, though.
            @gmemoize
            def memo_primes2():
                memo = []
                def manual_mprimes2():
                    memo.append(2)
                    yield 2
                    for n in count(start=3, step=2):
                        if not any(n % p == 0 for p in takewhile(lambda x: x * x <= n, memo)):
                            memo.append(n)
                            yield n
                return manual_mprimes2()

            # small refinement: skip testing 15, 25, 35, ...
            # - we know that in base-10, for any prime > 10 the last digit must be 1, 3, 7 or 9;
            #   if it is 0, 2 or 5, the number is divisible by at least one factor of 10 (namely 2 or 5)
            # - n < 10 must be checked separately; the primes are 2, 3, 5, 7
            #   (note the factors of 10 are there, plus some unrelated primes)
            @gmemoize
            def mprimes2():
                yield 2
                for n in chain([3, 5, 7], (d + k for d in count(10, step=10)
                                                 for k in [1, 3, 7, 9])):
                    if not any(n % p == 0 for p in takewhile(lambda x: x * x <= n, mprimes2())):
                        yield n

            # generalization: let's not be limited by base-10
            # base-b representation, switch b when appropriate:
            #   n = k*b + m
            #   b = 2*3, 2*3*5, 2*3*5*7, ...
            # k: integer,  1, 2, ..., {next factor to account for in b} - 1
            #    so e.g. when b=6, we check from 6 to 29; when b=30, from 30 to 209, ...
            # m: last digit in base-b representation of n, note m < b
            #    for a number represented in base-b to be prime, m must not be divisible by any factor of b
            # Only the numbers up to b must be checked separately (and already have when we reach the next b).
            #
            # For the first 5e4 primes, about 20% of the integers within each range are candidates.
            # If you want the details, add this just before "for n in ns:":
            #    print(b, ns[-1]**(1/2), len(ns), (nextp-1)*b, len(ns)/((nextp-1)*b))
            @gmemoize
            def mprimes3():
                # minimal init takes three terms; b = 2*3 = 6 > 5, so no overlap in output of init and general loop
                # (and this init yields all primes up to b = 6)
                yield from (2, 3, 5)
                theprimes = mprimes3()
                ps = list(take(2, theprimes))  # factors of b; b is chosen s.t. each factor is a different prime
                p, b, np = ps[-1], prod(ps), len(ps)
                lastdigits = [1, 3, 5]  # last digits in base-6 that are not divisible by 2

                while True:
                    nextp = next(theprimes)
                    lastdigits = [n for n in lastdigits if not n % p == 0]
                    ns = [k * b + m for k in range(1, nextp)
                                    for m in lastdigits]
                    # in ns, we have already eliminated the first np primes as possible factors, so skip checking them
                    for n in ns:
                        if not any(n % p == 0 for p in takewhile(lambda x: x * x <= n, drop(np, mprimes3()))):
                            yield n
                    ps.append(nextp)
                    b *= nextp
                    p = nextp
                    np += 1
                    lastdigits = lastdigits + ns
            test[tuple(take(500, mprimes3())) == tuple(take(500, mprimes2()))]

            @gmemoize
            def memo_primes3():
                memo = []
                def manual_mprimes3():
                    for p in (2, 3, 5):
                        memo.append(p)
                        yield p
                    p, b, np = 3, 6, 2
                    lastdigits = [1, 3, 5]

                    while True:
                        nextp = memo[np]
                        lastdigits = [n for n in lastdigits if not n % p == 0]
                        ns = [k * b + m for k in range(1, nextp)
                                        for m in lastdigits]
                        for n in ns:
                            if not any(n % p == 0 for p in takewhile(lambda x: x * x <= n, drop(np, memo))):
                                memo.append(n)
                                yield n
                        b *= nextp
                        p = nextp
                        np += 1
                        lastdigits += ns
                return manual_mprimes3()
            test[tuple(take(500, memo_primes3())) == tuple(take(500, mprimes2()))]

            @gmemoize
            def memo_primes4():
                memo = []
                def manual_mprimes4():
                    for p in (2, 3, 5):
                        memo.append(p)
                        yield p
                    p, b, np = 3, 6, 2
                    lastdigits = [1, 3, 5]
                    maxnp = 5  # --> b = 2*3*5*7*11 = 2310; optimal setting depends on CPU cache size

                    while True:
                        nextp = memo[np]
                        lastdigits = [n for n in lastdigits if not n % p == 0]
                        ns = [k * b + m for k in range(1, nextp)
                                        for m in lastdigits]
                        for n in ns:
                            if not any(n % p == 0 for p in takewhile(lambda x: x * x <= n, drop(np, memo))):
                                memo.append(n)
                                yield n
                        if np == maxnp:  # avoid table becoming too big (leading to memory bus dominated run time)
                            break
                        b *= nextp
                        p = nextp
                        np += 1
                        lastdigits += ns
                    # once maximum b reached, stay at that b, using the final table of lastdigits
                    for kb in count(nextp * b, step=b):
                        for n in (kb + m for m in lastdigits):
                            if not any(n % p == 0 for p in takewhile(lambda x: x * x <= n, drop(np, memo))):
                                memo.append(n)
                                yield n
                return manual_mprimes4()
            test[tuple(take(500, memo_primes4())) == tuple(take(500, mprimes2()))]

            test[tuple(take(10, primes())) == (2, 3, 5, 7, 11, 13, 17, 19, 23, 29)]
            test[tuple(take(10, mprimes())) == (2, 3, 5, 7, 11, 13, 17, 19, 23, 29)]
            test[tuple(take(10, memo_primes())) == (2, 3, 5, 7, 11, 13, 17, 19, 23, 29)]
            test[tuple(take(10, mprimes2())) == (2, 3, 5, 7, 11, 13, 17, 19, 23, 29)]
            test[tuple(take(10, memo_primes2())) == (2, 3, 5, 7, 11, 13, 17, 19, 23, 29)]
            test[tuple(take(10, mprimes3())) == (2, 3, 5, 7, 11, 13, 17, 19, 23, 29)]
            test[tuple(take(10, memo_primes3())) == (2, 3, 5, 7, 11, 13, 17, 19, 23, 29)]

        # TODO: need some kind of benchmarking tools to do this properly.
        with testset("performance benchmark"):
            n = 2500
            print("Performance for first {:d} primes:".format(n))
            for g in (mprimes(), memo_primes(), mprimes2(), memo_primes2(), mprimes3(), memo_primes3(), memo_primes4()):
                with timer() as tictoc:
                    last(take(n, g))
                print(g, tictoc.dt)

if __name__ == '__main__':
    runtests()
