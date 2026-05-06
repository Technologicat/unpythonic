# -*- coding: utf-8 -*-
"""Tests for `@multishot`, `myield`, and `MultishotIterator`."""

import copy

from ...syntax import macros, test, test_raises  # noqa: F401, F811
from ...test.fixtures import session, testset

from ...syntax import macros, continuations, multishot, myield  # noqa: F401, F811
from ...syntax import MultishotIterator  # runtime import (not a macro)


def runtests():
    with testset("@multishot: four `myield` forms"):
        with continuations:
            @multishot
            def f():
                myield
                myield[42]
                k = myield
                test[k == 23]
                k = myield[42]
                test[k == 17]

            k0 = f()              # instantiate (returns the initial continuation)
            k1 = k0()             # run up to the explicit bare `myield`
            k2, x2 = k1()         # to `myield[42]`
            test[x2 == 42]
            k3 = k2()             # to `k = myield`
            k4, x4 = k3(23)       # send 23, run to `k = myield[42]`
            test[x4 == 42]
            test_raises[StopIteration, k4(17)]  # send 17, fall off the end

    with testset("@multishot: basic linear consumption"):
        with continuations:
            @multishot
            def g():
                myield[1]
                myield[2]
                myield[3]

            try:
                out = []
                k = g()
                while True:
                    k, x = k()
                    out.append(x)
            except StopIteration:
                pass
            test[out == [1, 2, 3]]

    with testset("@multishot: re-invoke an earlier continuation (multi-shot)"):
        with continuations:
            @multishot
            def g():
                myield[1]
                myield[2]
                myield[3]

            k0 = g()
            k1, x1 = k0()
            k2, x2 = k1()
            k3, x3 = k2()
            k, x = k1()  # multi-shot: rewind to k1
            test[x1 == 1]
            test[x2 == x == 2]
            test[x3 == 3]
            test[k.func.__qualname__ == k2.func.__qualname__]  # same bookmarked position
            test[k.func is not k2.func]                        # but different closure instance
            test_raises[StopIteration, k3()]

    with testset("@multishot: `return value` raises StopIteration(value)"):
        with continuations:
            @multishot
            def h():
                myield[1]
                return 42

            mi = MultishotIterator(h())
            test[next(mi) == 1]
            try:
                next(mi)
            except StopIteration as e:
                test[e.value == 42]
            else:
                test[False]  # should have raised

    with testset("MultishotIterator: linear iteration"):
        with continuations:
            @multishot
            def g():
                myield[1]
                myield[2]
                myield[3]

            test[[x for x in MultishotIterator(g())] == [1, 2, 3]]

    with testset("MultishotIterator: send"):
        with continuations:
            @multishot
            def f():
                k = myield[10]
                test[k == 99]
                k = myield[20]
                test[k == 100]

            mi = MultishotIterator(f())
            test[next(mi) == 10]
            test[mi.send(99) == 20]
            test_raises[StopIteration, mi.send(100)]

    with testset("MultishotIterator: close"):
        with continuations:
            @multishot
            def g():
                myield[1]
                myield[2]
                myield[3]

            mi = MultishotIterator(g())
            test[next(mi) == 1]
            mi.close()
            test_raises[StopIteration, next(mi)]
            # close is idempotent
            mi.close()

    with testset("MultishotIterator: throw re-enters the continuation"):
        with continuations:
            @multishot
            def g():
                myield[1]
                myield[2]

            mi = MultishotIterator(g())
            test[next(mi) == 1]
            test_raises[ValueError, mi.throw(ValueError("boom"))]

    with testset("MultishotIterator: copy.copy forks the iterator (HEADLINE)"):
        with continuations:
            @multishot
            def g():
                myield[1]
                myield[2]
                myield[3]
                myield[4]

            # Real generators raise TypeError on copy.copy. Multi-shots fork.
            mi = MultishotIterator(g())
            test[next(mi) == 1]    # advance original to position 1

            fork = copy.copy(mi)   # snapshot at "after yielding 1"
            test[next(mi) == 2]    # original advances independently...
            test[next(mi) == 3]
            test[next(fork) == 2]  # ...and so does the fork, from its own snapshot
            test[next(fork) == 3]
            test[next(fork) == 4]
            test_raises[StopIteration, next(fork)]

            # Original is unaffected by fork's exhaustion
            test[next(mi) == 4]
            test_raises[StopIteration, next(mi)]

    with testset("MultishotIterator: copy.deepcopy raises TypeError"):
        with continuations:
            @multishot
            def g():
                myield[1]

            mi = MultishotIterator(g())
            test_raises[TypeError, copy.deepcopy(mi)]

    with testset("MultishotIterator: gi_running is always False"):
        with continuations:
            @multishot
            def g():
                myield[1]
                myield[2]

            mi = MultishotIterator(g())
            test[mi.gi_running is False]
            next(mi)
            test[mi.gi_running is False]
            next(mi)
            test[mi.gi_running is False]

    with testset("MultishotIterator: gi_frame is always None"):
        with continuations:
            @multishot
            def g():
                myield[1]
                myield[2]

            mi = MultishotIterator(g())
            test[mi.gi_frame is None]
            next(mi)
            test[mi.gi_frame is None]
            mi.close()
            test[mi.gi_frame is None]

    with testset("MultishotIterator: gi_code is the liveness signal"):
        with continuations:
            @multishot
            def g():
                myield[1]
                myield[2]

            mi = MultishotIterator(g())
            # While live, gi_code matches the underlying continuation's __code__.
            k = mi.k
            expected_code = k.func.__code__ if hasattr(k, "func") else k.__code__
            test[mi.gi_code is expected_code]

            next(mi)
            # Still live; gi_code reflects the new continuation.
            k = mi.k
            expected_code = k.func.__code__ if hasattr(k, "func") else k.__code__
            test[mi.gi_code is expected_code]

            mi.close()
            # After close, gi_code is None — this is the liveness signal.
            test[mi.gi_code is None]

    with testset("MultishotIterator: gi_yieldfrom is None (no myield_from yet)"):
        with continuations:
            @multishot
            def g():
                myield[1]

            mi = MultishotIterator(g())
            test[mi.gi_yieldfrom is None]
            next(mi)
            test[mi.gi_yieldfrom is None]


if __name__ == '__main__':  # pragma: no cover
    with session(__file__):
        runtests()
