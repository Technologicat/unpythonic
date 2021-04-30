# -*- coding: utf-8 -*-

from ..syntax import macros, test, test_raises, the  # noqa: F401
from ..test.fixtures import session, testset, returns_normally

import threading
from queue import Queue
import gc

from ..dynassign import dyn, make_dynvar
from ..misc import slurp

def runtests():
    # various parts of unpythonic use dynvars, so get what's there before we insert anything for testing
    implicits = [k for k in dyn]
    def noimplicits(kvs):
        return tuple(sorted((k, v) for k, v in kvs if k not in implicits))
    def noimplicits_keys(keys):
        return tuple(sorted(k for k in keys if k not in implicits))

    # some test data
    D = {"a": 1, "b": 2}
    D2 = {"c": 3, "d": 4}

    def f():
        test[dyn.a == 2]  # no a in lexical scope

    def basictests():
        with testset("basic usage"):
            with dyn.let(a=2, b="foo"):
                test[dyn.a == 2]
                f()

                with dyn.let(a=3):
                    test[dyn.a == 3]

                test[dyn.a == 2]

            test_raises[AttributeError, dyn.b]  # no longer exists

        with testset("multithreading"):
            comm = Queue()
            def threadtest(q):
                try:
                    dyn.c  # just access dyn.c
                except AttributeError as err:
                    q.put(err)
                q.put(None)

            with dyn.let(c=42):
                t1 = threading.Thread(target=threadtest, args=(comm,), kwargs={})
                t1.start()
                t1.join()
            err = comm.get()
            test[err is None]

            t2 = threading.Thread(target=threadtest, args=(comm,), kwargs={})
            t2.start()  # should crash, dyn.c no longer exists in the main thread
            t2.join()
            err = comm.get()
            test[err is not None]
    basictests()

    with testset("syntactic sugar"):
        with dyn.let(**D):
            # membership test
            test["a" in the[dyn]]
            test["c" not in the[dyn]]

            # subscript syntax as an alternative notation to refer to dynamic vars
            test[the[dyn.a is dyn["a"]]]

            test[noimplicits(dyn.items()) == (("a", 1), ("b", 2))]
        test[noimplicits(dyn.items()) == ()]

    with testset("update existing bindings"):
        with dyn.let(**D):
            with dyn.let(**D2):
                test[noimplicits(dyn.items()) == (("a", 1), ("b", 2), ("c", 3), ("d", 4))]
                dyn.c = 23
                test[noimplicits(dyn.items()) == (("a", 1), ("b", 2), ("c", 23), ("d", 4))]
                dyn.a = 42  # update occurs in the nearest enclosing dynamic scope that has the name bound
                test[noimplicits(dyn.items()) == (("a", 42), ("b", 2), ("c", 23), ("d", 4))]
                with test_raises[AttributeError, "should not be able to update unbound dynamic variable"]:
                    dyn.e = 5

                # subscript notation also works for updating
                with test:
                    dyn["a"] = 9001
                test[dyn.a == 9001]
            test[noimplicits(dyn.items()) == (("a", 9001), ("b", 2))]
        test[noimplicits(dyn.items()) == ()]

    with testset("update in presence of name shadowing"):
        with dyn.let(**D):
            with dyn.let(**D):
                test[noimplicits(dyn.items()) == (("a", 1), ("b", 2))]
                dyn.a = 42
                test[noimplicits(dyn.items()) == (("a", 42), ("b", 2))]
            # the inner "a" was updated, the outer one remains untouched
            test[noimplicits(dyn.items()) == (("a", 1), ("b", 2))]
        test[noimplicits(dyn.items()) == ()]

    with testset("mass update"):
        with dyn.let(**D):
            with dyn.let(**D2):
                test[noimplicits(dyn.items()) == (("a", 1), ("b", 2), ("c", 3), ("d", 4))]
                dyn.update(a=-1, b=-2, c=-3, d=-4)
                test[noimplicits(dyn.items()) == (("a", -1), ("b", -2), ("c", -3), ("d", -4))]
            test[noimplicits(dyn.items()) == (("a", -1), ("b", -2))]
            dyn.update(a=10, b=20)
            test[noimplicits(dyn.items()) == (("a", 10), ("b", 20))]
        test[noimplicits(dyn.items()) == ()]

    with testset("mass update with multithreading"):
        comm = Queue()
        def worker():
            # test[] itself is thread-safe, but the worker threads don't have a
            # surrounding testset to catch failures, since we don't want to print in them.
            try:
                local_successes = 0
                with dyn.let(**D):
                    with dyn.let(**D2):
                        if noimplicits(dyn.items()) == (("a", 1), ("b", 2), ("c", 3), ("d", 4)):
                            local_successes += 1
                        dyn.update(a=-1, b=-2, c=-3, d=-4)
                        if noimplicits(dyn.items()) == (("a", -1), ("b", -2), ("c", -3), ("d", -4)):
                            local_successes += 1
                    if noimplicits(dyn.items()) == (("a", -1), ("b", -2)):
                        local_successes += 1
                    dyn.update(a=10, b=20)
                    if noimplicits(dyn.items()) == (("a", 10), ("b", 20)):
                        local_successes += 1
                if noimplicits(dyn.items()) == ():
                    local_successes += 1
                if local_successes == 5:
                    comm.put(1)
            except Exception:  # pragma: no cover, only happens if the test fails.
                pass
        n = 100
        threads = [threading.Thread(target=worker) for _ in range(n)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        successes = sum(slurp(comm))
        test[the[successes] == the[n]]

    with testset("make_dynvar (default values)"):
        make_dynvar(im_always_there=True)
        test[dyn.im_always_there is True]
        with dyn.let(a=1, b=2):
            test[noimplicits(dyn.items()) == (("a", 1), ("b", 2),
                                              ("im_always_there", True))]
        test[noimplicits(dyn.items()) == (("im_always_there", True),)]

    with testset("live view"):
        # dyn.asdict() returns a live view, which is essentially a collections.ChainMap
        view = dyn.asdict()
        test[noimplicits(view.items()) == (("im_always_there", True),)]
        with dyn.let(a=1, b=2):
            test[noimplicits(view.items()) == (("a", 1), ("b", 2),
                                               ("im_always_there", True))]
        del view
        gc.collect()

        # as does dyn.items() (it's an abbreviation for dyn.asdict().items())
        items = dyn.items()
        test[noimplicits(items) == (("im_always_there", True),)]
        with dyn.let(a=1, b=2):
            test[noimplicits(items) == (("a", 1), ("b", 2),
                                        ("im_always_there", True))]

        # the rest of the Mapping API
        keys = dyn.keys()  # live!
        with dyn.let(a=1, b=2):
            test[noimplicits_keys(keys) == ("a", "b", "im_always_there")]

            test[dyn.get("a") == 1]
            test[dyn.get("c") is None]  # default

            d = dict(items)
            test[dyn == d]

        # Not much we can do with the output so let's just check these don't crash.
        test[returns_normally(dyn.values())]
        test[returns_normally(len(dyn))]


if __name__ == '__main__':  # pragma: no cover
    with session(__file__):
        runtests()
