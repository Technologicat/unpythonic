# -*- coding: utf-8; -*-

from ..syntax import macros, test, test_raises, the  # noqa: F401
from ..test.fixtures import session, testset, returns_normally

import pickle
import gc
import threading
from queue import Queue

from ..singleton import Singleton
from ..misc import slurp
from ..it import allsame

# For testing. Defined at the top level to allow pickling.
class Foo(Singleton):
    pass
class Bar(Foo):
    pass
class Baz(Singleton):
    def __init__(self, x=42):
        self.x = x
class Qux(Baz):
    def __getstate__(self):
        return None
    # TODO: coverage says this is never actually called. Maybe the data in the
    # pickle file knows that `__getstate__` returned `None`, and `loads` skips
    # calling `__setstate__`?
    def __setstate__(self, state):
        return

def runtests():
    with testset("basic usage"):
        # IMPORTANT: be sure to keep the reference to the object instance the constructor
        # gives you. This is the only time you'll see it.
        foo = Foo()
        test_raises[TypeError, Foo(), "should have errored out, a Foo already exists"]

        del foo  # deleting the only strong reference kills the Foo instance from the singleton instances
        gc.collect()  # Need to request garbage collection on PyPy, because otherwise no guarantee when it'll happen.
        test[returns_normally(Foo())]    # so now it's ok to create a new Foo

        # another class that inherits from a singleton class
        bar = Bar()  # noqa: F841, our strong reference keeps the object alive while testing.
        test_raises[TypeError, Bar(), "should have errored out, a Bar already exists"]

    with testset("pickling"):
        # TODO: FIXME: This module is not the real "__main__" when running under the `macropython` wrapper.
        # We HACK this for now so that these pickling tests can run. Not quite sure whether `macropython` even
        # should attempt to overwrite `sys.modules["__main__"]` with the "main" module it imports; doing
        # that might just break something.
        import sys
        sys.modules["__main__"].Baz = Baz
        sys.modules["__main__"].Qux = Qux

        # pickling: basic use
        baz = Baz(17)
        s = pickle.dumps(baz)
        baz2 = pickle.loads(s)
        test[the[baz2 is baz]]  # it's the same instance

        # pickling: by default (if no custom `__getstate__`/`__setstate__`),
        # the state of the singleton object is restored (overwritten!) upon
        # unpickling it.
        baz.x = 23
        test[baz.x == 23]
        baz2 = pickle.loads(s)
        test[the[baz2 is baz]]   # again, it's the same instance
        test[baz.x == 17]  # but unpickling has overwritten the state

        # With custom no-op `__getstate__` and `__setstate__`, the existing
        # singleton instance's state remains untouched even after unpickling an
        # instance of that singleton. This strategy may be useful when defining
        # singletons which have no meaningful state to serialize/deserialize.
        qux = Qux(17)
        s = pickle.dumps(qux)
        qux.x = 23
        qux2 = pickle.loads(s)
        test[the[qux2 is qux]]   # it's the same instance
        test[qux.x == 23]  # and unpickling didn't change the state

    with testset("thread safety"):
        with test:  # just interested that it runs to completion
            class Quux(Singleton):
                pass
            que = Queue()
            def worker():
                try:
                    que.put(Quux())
                except TypeError:
                    pass
            n = 1000
            threads = [threading.Thread(target=worker) for _ in range(n)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()
            lst = slurp(que)
            test[len(lst) == 1]

        # TODO: These must be outside the `with test` because a test block
        # implicitly creates a function (whence a local scope).
        s = pickle.dumps(baz)
        del baz
        gc.collect()
        with test:
            que = Queue()
            def worker():
                try:
                    que.put(pickle.loads(s))  # let's race!
                except TypeError:  # pragma: no cover
                    que.put(None)
            n = 1000
            threads = [threading.Thread(target=worker) for _ in range(n)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()
            lst = slurp(que)
            test[the[len(lst)] == the[n]]
            test[all(x is not None for x in lst)]
            test[allsame(lst)]

if __name__ == '__main__':  # pragma: no cover
    with session(__file__):
        runtests()
