#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Memoization of generators.

Memoize generator functions (generator definitions), iterators,
or iterators created by factory functions."""

__all__ = ["gmemoize", "imemoize", "fimemoize"]

from operator import itemgetter
from functools import wraps
from threading import RLock

def gmemoize(gfunc):
    """Decorator: produce memoized generator instances.

    Similar to ``itertools.tee``, but the whole sequence is kept in memory
    indefinitely, so more instances of the memoized generator can be created
    at any time (instead of having to specify how many copies at ``tee`` time).

    Decorate the **generator function** (i.e. generator definition) with this.

      - If the gfunc takes arguments, they must be hashable. A separate memoized
        sequence is created for each unique set of argument values seen.

      - For simplicity, the generator itself may use ``yield`` for output only;
        ``send`` is not supported.

      - Any exceptions raised by the generator (except StopIteration) are also
        memoized, like in ``memoize``.

      - Thread-safe. Calls to ``next`` on the memoized generator from different
        threads are serialized via a lock. Each memoized sequence has its own
        lock. This uses ``threading.RLock``, so re-entering from the same
        thread (e.g. in recursively defined sequences) is fine.

      - For infinite sequences, use this only if you can guarantee only a
        reasonable number of terms will ever be evaluated (w.r.t. available RAM).

      - Typically, this should be the outermost decorator if several are used
        on the same gfunc.

    Usage::

        evals = 0

        @gmemoize
        def one_two_three():
            global evals
            for j in range(3):
                evals += 1
                yield j

        g1 = one_two_three()
        assert tuple(x for x in g1) == (0, 1, 2)
        g2 = one_two_three()
        assert tuple(x for x in g2) == (0, 1, 2)
        assert evals == 3

    It doesn't matter when the generator instances are created, or when which
    of them is advanced. All instances created with the same arguments (here none)
    to the gfunc share the same memoized sequence.

    **Recipe**: *Memoizing only a part of a sequence*.

    Build a chain of generators, then memoize only the last one::

        def orig():
            yield from range(100)
        def evens():
            yield from (x for x in orig() if x % 2 == 0)
        evaluations = collections.Counter()
        @gmemoize
        def some_evens(n):  # drop n first terms
            evaluations[n] += 1
            yield from drop(n, evens())
        last(some_evens(25))
        last(some_evens(25))
        last(some_evens(20))
        assert all(v == 1 for k, v in evaluations.items())

    Or with ``lambda`` for a more compact presentation::

        orig = lambda: (yield from range(100))
        evens = lambda: (yield from (x for x in orig() if x % 2 == 0))
        some_evens = gmemoize(lambda n: (yield from drop(n, evens())))
        last(some_evens(25))
        last(some_evens(25))

    See also ``imemoize``, ``fimemoize``.
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

_success, _fail = [object() for _ in range(2)]  # global saves indirect via self
class _MemoizedGenerator:
    """Wrapper that manages one memoized sequence. Co-operates with gmemoize."""
    def __init__(self, g, memo, lock):
        self.g = g
        self.memo = memo  # each instance for the same g gets the same memo
        self.lock = lock
        self.j = 0  # current position in memo
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
            kind, value = result
            self.j += 1
            if kind is _fail:
                raise value
            return value

def imemoize(iterable):
    """Memoize an iterable.

    Return a gfunc with no parameters which, when called, returns a generator
    that yields items from the memoized iterable. The original iterable is
    used to retrieve more terms when needed.

    ``imemoize`` essentially makes the iterable restartable (arbitrarily "tee-able"),
    at the cost of keeping the whole history in memory.

    Unlike ``itertools.tee``, there is no need to specify how many copies
    are needed at ``tee`` time; a new copy can be created at any time,
    by calling the returned gfunc.

    Like ``itertools.tee``, after memoizing, the original iterator should not
    be used. The danger is that if something outside the memoization mechanism
    advances it, some values will be lost before they reach the memo.

    Example::

        evens = (x for x in range(100) if x % 2 == 0)
        some_evens = imemoize(drop(25, evens))
        assert last(some_evens()) == last(some_evens())  # iterating twice!

    In the example, whenever ``some_evens`` is called, it returns a new
    memoized generator instance that yields items from the memoized iterable.

    If you need to take arguments to create the iterable, see ``fimemoize``.
    """
    # The lambda is the gfunc; decorate it with gmemoize and return that.
    return gmemoize(lambda: (yield from iterable))

def fimemoize(ifactory):
    """Like imemoize, but for cases where creating the iterable needs arguments.

    ``ifactory`` is a function, which takes any number of positional or keyword
    arguments, and returns an iterable.

    This is similar to ``gmemoize``, but for a regular function that returns
    an iterable (instead of for a gfunc).

    This works by defining a gfunc based on ``ifactory``, and gmemoizing that.
    Hence arguments of ``ifactory`` must be hashable, and each unique set of
    argument values produces its own memoized sequence.

    The return value is a gfunc, which takes the same arguments as ``ifactory``.

    Example::

        def evens():
            yield from (x for x in range(100) if x % 2 == 0)
        @fimemoize
        def some_evens(n):  # regular function!
            return drop(n, evens())
        assert last(some_evens(25)) == last(some_evens(25))

    Compare to::

        def evens():
            yield from (x for x in range(100) if x % 2 == 0)
        @gmemoize
        def some_evens(n):  # gfunc!
            yield from drop(n, evens())
        assert last(some_evens(25)) == last(some_evens(25))

    Using lambda, the original example is equivalent to::

        evens = lambda: (yield from (x for x in range(100) if x % 2 == 0))
        some_evens = fimemoize(lambda n: drop(n, evens()))
        assert last(some_evens(25)) == last(some_evens(25))
    """
    @wraps(ifactory)
    def gfunc(*args, **kwargs):
        yield from ifactory(*args, **kwargs)
    return gmemoize(gfunc)
    # return gmemoize(lambda *a, **kw: (yield from ifactory(*a, **kw)))

def test():
    from time import time
    from itertools import count, takewhile
    from collections import Counter
    from unpythonic.it import take, drop, last
    from unpythonic.misc import call

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
            if not any(p != n and n % p == 0 for p in takewhile(lambda x: x*x <= n, primes())):
                yield n

    @gmemoize  # <-- the only change (beside the function name)
    def mprimes():
        yield 2
        for n in count(start=3, step=2):
            if not any(p != n and n % p == 0 for p in takewhile(lambda x: x*x <= n, mprimes())):
                yield n

    def memo_primes():  # with manually implemented memoization
        memo = []
        def manual_mprimes():
            memo.append(2)
            yield 2
            for n in count(start=3, step=2):
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
