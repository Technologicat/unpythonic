# -*- coding: utf-8 -*-

import threading
from queue import Queue

from ..dynassign import dyn, make_dynvar

def test():
    def f():
        assert dyn.a == 2  # no a in lexical scope

    def runtest():
        with dyn.let(a=2, b="foo"):
            assert dyn.a == 2
            f()

            with dyn.let(a=3):
                assert dyn.a == 3

            assert dyn.a == 2

        try:
            print(dyn.b)      # AttributeError, dyn.b no longer exists
        except AttributeError:
            pass
        else:
            assert False, "dyn.b should no longer exist"

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
        v = comm.get()
        if v is None:
            pass
        else:
            assert False, v

        t2 = threading.Thread(target=threadtest, args=(comm,), kwargs={})
        t2.start()  # should crash, dyn.c no longer exists in the main thread
        t2.join()
        v = comm.get()
        if v is not None:
            pass
        else:
            assert False
    runtest()

    # various parts of unpythonic use dynvars, so get what's there before we insert anything for testing
    implicits = [k for k in dyn]
    def noimplicits(kvs):
        return tuple(sorted((k, v) for k, v in kvs if k not in implicits))
    D = {"a": 1, "b": 2}
    with dyn.let(**D):
        # membership test
        assert "a" in dyn
        assert "c" not in dyn

        # subscript syntax as an alternative notation to refer to dynamic vars
        assert dyn.a is dyn["a"]

        assert noimplicits(dyn.items()) == (("a", 1), ("b", 2))
    assert noimplicits(dyn.items()) == ()

    make_dynvar(im_always_there=True)
    with dyn.let(a=1, b=2):
        assert noimplicits(dyn.items()) == (("a", 1), ("b", 2),
                                            ("im_always_there", True))
    assert noimplicits(dyn.items()) == (("im_always_there", True),)

    # dyn.asdict() returns a live view, which is essentially a collections.ChainMap
    view = dyn.asdict()
    assert noimplicits(view.items()) == (("im_always_there", True),)
    with dyn.let(a=1, b=2):
        assert noimplicits(view.items()) == (("a", 1), ("b", 2),
                                             ("im_always_there", True))

    # as does dyn.items() (it's an abbreviation for dyn.asdict().items())
    items = dyn.items()
    assert noimplicits(items) == (("im_always_there", True),)
    with dyn.let(a=1, b=2):
        assert noimplicits(items) == (("a", 1), ("b", 2),
                                      ("im_always_there", True))

    print("All tests PASSED")

if __name__ == '__main__':
    test()
