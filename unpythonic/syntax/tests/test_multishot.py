# -*- coding: utf-8 -*-
"""Tests for `@multishot`, `myield`, and `MultishotIterator`."""

import copy

from ...syntax import macros, test, test_raises  # noqa: F401, F811
from ...test.fixtures import session, testset

from ...syntax import macros, continuations, multishot, myield, myield_from  # noqa: F401, F811
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

    with testset("MultishotIterator: send(value) on a bare-myield continuation drops the value"):
        # Standard-generator parity: gen.send(value) on a bare yield discards
        # the value. The `_step` helper detects partial-wrapping (the shape of
        # a bare-myield continuation) and routes the advance as a no-arg call.
        with continuations:
            @multishot
            def g():
                myield[1]   # bare myield; the captured continuation is partial-wrapped
                myield[2]
                myield[3]

            mi = MultishotIterator(g())
            test[next(mi) == 1]
            # Sending to a bare-myield continuation: value silently dropped, advance proceeds.
            test[mi.send("ignored") == 2]
            # send(None) on a bare-myield continuation also works (≡ next).
            test[mi.send(None) == 3]

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

    with testset("myield_from: linear delegation (statement form)"):
        with continuations:
            @multishot
            def inner():
                myield[1]
                myield[2]

            @multishot
            def outer():
                myield[0]
                myield_from[inner()]
                myield[3]

            mi = MultishotIterator(outer())
            test[list(mi) == [0, 1, 2, 3]]

    with testset("myield_from: assignment form binds inner's StopIteration value"):
        with continuations:
            @multishot
            def inner():
                myield[1]
                return 99

            @multishot
            def outer():
                v = myield_from[inner()]
                myield[v]   # outer yields whatever inner returned via StopIteration

            mi = MultishotIterator(outer())
            test[list(mi) == [1, 99]]

    with testset("myield_from: gi_yieldfrom tracks the inner iterator while delegating"):
        with continuations:
            @multishot
            def inner():
                myield[1]
                myield[2]

            @multishot
            def outer():
                myield[0]
                myield_from[inner()]
                myield[3]

            mi = MultishotIterator(outer())
            test[mi.gi_yieldfrom is None]    # not yet delegating

            test[next(mi) == 0]              # outer's myield[0]
            test[mi.gi_yieldfrom is None]    # still not delegating; outer hasn't entered _drive

            test[next(mi) == 1]              # entered _drive; first inner value
            test[isinstance(mi.gi_yieldfrom, MultishotIterator)]
            inner_mi_seen = mi.gi_yieldfrom

            test[next(mi) == 2]              # second inner value
            test[mi.gi_yieldfrom is inner_mi_seen]   # same inner iterator object

            test[next(mi) == 3]              # back in outer; inner exhausted
            test[mi.gi_yieldfrom is None]    # delegation done

            test_raises[StopIteration, next(mi)]

    with testset("myield_from: send forwards value into inner"):
        with continuations:
            @multishot
            def inner():
                v = myield[10]
                myield[v]   # echo the sent value

            @multishot
            def outer():
                myield_from[inner()]

            mi = MultishotIterator(outer())
            test[next(mi) == 10]
            test[mi.send(42) == 42]   # 42 reached inner's `v`

    with testset("myield_from: throw forwards exception into inner; uncaught propagates out"):
        with continuations:
            @multishot
            def inner():
                myield[1]
                myield[2]   # throw fires here; inner doesn't catch

            @multishot
            def outer():
                myield_from[inner()]
                myield["unreached"]

            mi = MultishotIterator(outer())
            test[next(mi) == 1]
            test[next(mi) == 2]
            test_raises[ValueError, mi.throw(ValueError("boom"))]
            # State after a propagated throw: outer's continuation is unchanged
            # (no advance happened in `_advance`); next consumer attempt re-enters
            # the same continuation.

    with testset("myield_from: multi-shot fork around delegation (copy.copy)"):
        # When a fork happens *before* delegation begins, each iterator's
        # resume re-runs `MultishotIterator(inner())`, so each gets its own
        # fresh inner. Forks then iterate the delegation independently —
        # both see inner's full sequence.
        with continuations:
            @multishot
            def inner():
                myield[1]
                myield[2]
                myield[3]

            @multishot
            def outer():
                myield[0]
                myield_from[inner()]

            mi = MultishotIterator(outer())
            test[next(mi) == 0]

            fork = copy.copy(mi)   # before delegation; forks are independent

            # mi consumes its own delegation
            test[next(mi) == 1]
            test[next(mi) == 2]
            test[next(mi) == 3]
            test_raises[StopIteration, next(mi)]

            # fork consumes its own delegation
            test[next(fork) == 1]
            test[next(fork) == 2]
            test[next(fork) == 3]
            test_raises[StopIteration, next(fork)]


if __name__ == '__main__':  # pragma: no cover
    with session(__file__):
        runtests()
