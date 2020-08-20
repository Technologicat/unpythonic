# -*- coding: utf-8 -*-

from ..syntax import macros, test, test_raises  # noqa: F401
from .fixtures import session, testset

from ..env import env

def runtests():
    with testset("basic usage"):
        with env(x=1) as e:
            test[len(e) == 1]
            test[e.x == 1]

        # create new item inside the "with" block
        with env(x=1) as e:
            test[len(e) == 1]
            e.y = 42
            test[e.y == 42]
            test[len(e) == 2]

        # manual clear
        with env(x=1) as e:
            e.clear()
            test[len(e) == 0]
        test[len(e) == 0]

        # auto-clear upon exit from "with" block
        with env(a=42) as e:
            test[len(e) == 1]
        test[len(e) == 0]

    with testset("syntactic sugar"):
        with env(x=1, y=2, z=3) as e:
            # iteration, subscripting
            test[{name for name in e} == set(("x", "y", "z"))]
            test[{(name, e[name]) for name in e} == set((("x", 1),
                                                         ("y", 2),
                                                         ("z", 3)))]
            test[dict(e.items()) == {"x": 1, "y": 2, "z": 3}]

            # membership testing
            test["x" in e]
            test["a" not in e]

            # modify existing binding
            test[e.set("x", 42) == 42]  # returns the new value
            test[e << ("x", 23) is e]   # instance passthrough for chaining

    with testset("error cases"):
        with env(x=1) as e:
            e.finalize()
            with test_raises(AttributeError, "should not be able to add new bindings to a finalized environment"):
                e.y = 42

        # undefined name
        with env(x=1) as e:
            test_raises[AttributeError, e.y]  # invalid, no y in e

        with env() as e:
            test_raises[AttributeError, e.set("foo", 42)]  # invalid, set() only modifies existing bindings

        with env() as e:
            with test_raises(ValueError, "should detect invalid identifier in __setitem__"):
                e["∞"] = 1  # invalid identifier in store context (__setitem__)

        with env() as e:
            with test_raises(ValueError, "should detect invalid identifier in __getitem__"):
                e["∞"]  # invalid identifier in load context (__getitem__)

if __name__ == '__main__':  # pragma: no cover
    with session(__file__):
        runtests()
