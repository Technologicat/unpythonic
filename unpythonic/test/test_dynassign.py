# -*- coding: utf-8 -*-

from ..syntax import macros, test, test_raises  # noqa: F401
from .fixtures import testset

import threading
from queue import Queue

from ..dynassign import dyn, make_dynvar

def runtests():
    with testset("unpythonic.dynassign"):
        def f():
            test[dyn.a == 2]  # no a in lexical scope

        def runtest():
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
        runtest()

        with testset("syntactic sugar"):
            # various parts of unpythonic use dynvars, so get what's there before we insert anything for testing
            implicits = [k for k in dyn]
            def noimplicits(kvs):
                return tuple(sorted((k, v) for k, v in kvs if k not in implicits))
            D = {"a": 1, "b": 2}
            with dyn.let(**D):
                # membership test
                test["a" in dyn]
                test["c" not in dyn]

                # subscript syntax as an alternative notation to refer to dynamic vars
                test[dyn.a is dyn["a"]]

                test[noimplicits(dyn.items()) == (("a", 1), ("b", 2))]
            test[noimplicits(dyn.items()) == ()]

        with testset("update existing bindings"):
            D2 = {"c": 3, "d": 4}
            with dyn.let(**D):
                with dyn.let(**D2):
                    test[noimplicits(dyn.items()) == (("a", 1), ("b", 2), ("c", 3), ("d", 4))]
                    dyn.c = 23
                    test[noimplicits(dyn.items()) == (("a", 1), ("b", 2), ("c", 23), ("d", 4))]
                    dyn.a = 42  # update occurs in the nearest enclosing dynamic scope that has the name bound
                    test[noimplicits(dyn.items()) == (("a", 42), ("b", 2), ("c", 23), ("d", 4))]
                    with test_raises(AttributeError, "updating unbound dynamic variable"):
                        dyn.e = 5
                test[noimplicits(dyn.items()) == (("a", 42), ("b", 2))]
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

        with testset("make_dynvar (default values)"):
            make_dynvar(im_always_there=True)
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

            # as does dyn.items() (it's an abbreviation for dyn.asdict().items())
            items = dyn.items()
            test[noimplicits(items) == (("im_always_there", True),)]
            with dyn.let(a=1, b=2):
                test[noimplicits(items) == (("a", 1), ("b", 2),
                                            ("im_always_there", True))]

if __name__ == '__main__':
    runtests()
