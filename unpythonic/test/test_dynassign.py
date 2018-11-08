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

    D = {"a": 1, "b": 2}
    # various parts of unpythonic use dynvars, so get what's there before we insert anything
    implicits = [k for k, v in dyn.items()]  # TODO: add a .keys() method?
    def noimplicits(dic):
        return {k: dic[k] for k in dic if k not in implicits}
    with dyn.let(**D):
        # membership test
        assert "a" in dyn
        assert "c" not in dyn
        # subscript syntax as an alternative way to refer to items
        assert dyn.a is dyn["a"]

        # iteration works like in a dictionary
        assert tuple(sorted(k for k in noimplicits(dyn))) == ("a", "b")

        # items() gives a snapshot, with values read at the time it was called
        assert tuple(sorted(noimplicits(dyn).items())) == (("a", 1), ("b", 2))

        # safer (TOCTTOU) in complex situations to iterate over keys and retrieve the current dyn[k]
        assert tuple(sorted({k: dyn[k] for k in noimplicits(dyn)}.items())) == (("a", 1), ("b", 2))

    make_dynvar(im_always_there=True)
    with dyn.let(a=1, b=2):
        assert tuple(sorted(noimplicits(dyn).items())) == (("a", 1), ("b", 2),
                                                           ("im_always_there", True))
    assert tuple(sorted(noimplicits(dyn).items())) == (("im_always_there", True),)

    print("All tests PASSED")

if __name__ == '__main__':
    test()
