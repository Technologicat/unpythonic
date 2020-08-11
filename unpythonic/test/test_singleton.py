# -*- coding: utf-8; -*-

import pickle
import gc

from ..singleton import Singleton

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
    def __setstate__(self, state):
        return

def runtests():
    # basic usage
    #
    # IMPORTANT: be sure to keep the reference to the object instance the constructor
    # gives you. This is the only time you'll see it.
    foo = Foo()
    try:
        Foo()
    except TypeError:
        pass
    else:
        assert False  # should have errored out, a Foo already exists!

    del foo  # deleting the only strong reference kills the Foo instance from the singleton instances
    gc.collect()  # Need to request garbage collection on PyPy, because otherwise no guarantee when it'll happen.
    Foo()    # so now it's ok to create a new Foo

    # another class that inherits from a singleton class
    bar = Bar()  # noqa: F841, our strong reference keeps the object alive while testing.
    try:
        Bar()
    except TypeError:
        pass
    else:
        assert False  # should have errored out, a Bar already exists!

    # pickling: basic use
    baz = Baz(17)
    s = pickle.dumps(baz)
    baz2 = pickle.loads(s)
    assert baz2 is baz  # it's the same instance

    # pickling: by default (if no custom `__getstate__`/`__setstate__`),
    # the state of the singleton object is restored (overwritten!) upon
    # unpickling it.
    baz.x = 23
    assert baz.x == 23
    baz2 = pickle.loads(s)
    assert baz2 is baz   # again, it's the same instance
    assert baz.x == 17  # but unpickling has overwritten the state

    # With a custom no-op `__setstate__`, the existing singleton instance's
    # state remains untouched even after unpickling an instance of that
    # singleton. This strategy may be useful when defining singletons which
    # have no meaningful state to serialize/deserialize.
    qux = Qux(17)
    s = pickle.dumps(qux)
    qux.x = 23
    qux2 = pickle.loads(s)
    assert qux2 is qux   # it's the same instance
    assert qux.x == 23  # and unpickling didn't change the state

    print("All tests PASSED")

if __name__ == '__main__':
    runtests()
