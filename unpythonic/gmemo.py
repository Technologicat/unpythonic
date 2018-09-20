#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Memoization of generators."""

__all__ = ["gmemoize"]

from operator import itemgetter
from functools import wraps
from threading import RLock

def gmemoize(gfunc):
    """Decorator: produce memoized generator instances.

      - Decorate the generator function (i.e. generator definition) with this.

      - All values yielded from the generator are stored indefinitely.

        For infinite sequences, use this only if you can guarantee only a
        reasonable number of terms will ever be evaluated (w.r.t. available RAM).

      - Any exceptions raised by the generator (except StopIteration)
        are also memoized, like in ``memoize``.

      - If the gfunc takes arguments, they must be hashable. A separate memoized
        sequence is created for each unique set of arguments seen.

      - For simplicity, the generator itself may use ``yield`` for output only;
        ``send`` is not supported.

      - Thread-safe. Calls to ``next`` on the memoized generator from different
        threads are serialized via a lock. Each memoized sequence has its own
        lock. This uses ``threading.RLock``, so re-entering from the same
        thread (e.g. in recursively defined sequences) is fine.

      - Typically, this should be the outermost decorator if several are used
        on the same gfunc.

    Usage::

        @gmemoize
        def mygen():
            yield 1
            yield 2
            yield 3
    """
    memos = {}
    @wraps(gfunc)
    def gmemoized(*args, **kwargs):
        k = (args, tuple(sorted(kwargs.items(), key=itemgetter(0))))
        if k not in memos:
            # underlying generator instance, memo instance, lock instance
            memos[k] = (gfunc(*args, **kwargs), [], RLock())
        return _MemoizedGenerator(*memos[k])
    return gmemoized

_success, _fail = [object() for _ in range(2)]  # sentinels (globals, saves indirect via self)
class _MemoizedGenerator:
    """Wrapper that manages one memoized sequence. Co-operates with gmemoize."""
    def __init__(self, g, memo, lock):
        self.memo = memo  # each instance for the same g gets the same memo
        self.g = g
        self.j = 0  # current position in memo
        self.lock = lock
    def __repr__(self):
        return "<_MemoizedGenerator object {} at 0x{:x}>".format(self.g.__name__, id(self))
    def __iter__(self):
        return self
    def __next__(self):
        j = self.j
        memo = self.memo
        with self.lock:
            if j < len(memo):
                result = memo[j]
            else:
                try:
                    result = (_success, next(self.g))
                except BaseException as err:  # StopIteration propagates, not a BaseException
                    result = (_fail, err)
                memo.append(result)
            sentinel, value = result
            self.j += 1
            if sentinel is _success:
                return value
            else:
                raise value

def test():
    from time import time
    from itertools import count, takewhile
    from unpythonic.it import take, last

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

    # sieve of Eratosthenes
    def primes():
        yield 2
        for f in count(start=1):
            n = 2*f + 1
            if not any(p != n and n % p == 0 for p in takewhile(lambda x: x*x <= n, primes())):
                yield n

    @gmemoize  # <-- only change
    def mprimes():
        yield 2
        for f in count(start=1):
            n = 2*f + 1
            if not any(p != n and n % p == 0 for p in takewhile(lambda x: x*x <= n, mprimes())):
                yield n

    def memo_primes():  # with manually implemented memoization
        memo = []
        def manual_mprimes():
            memo.append(2)
            yield 2
            for f in count(start=1):
                n = 2*f + 1
                if not any(p != n and n % p == 0 for p in takewhile(lambda x: x*x <= n, memo)):
                    memo.append(n)
                    yield n
        return manual_mprimes()

    assert tuple(take(10, primes())) == (2, 3, 5, 7, 11, 13, 17, 19, 23, 29)
    assert tuple(take(10, mprimes())) == (2, 3, 5, 7, 11, 13, 17, 19, 23, 29)
    assert tuple(take(10, memo_primes())) == (2, 3, 5, 7, 11, 13, 17, 19, 23, 29)

    n = 2500
    print("Performance for first {:d} primes:".format(n))
    for g in (primes(), mprimes(), memo_primes()):
        t0 = time()
        last(take(n, g))
        dt = time() - t0
        print(g, dt)

    print("All tests PASSED")

if __name__ == '__main__':
    test()
