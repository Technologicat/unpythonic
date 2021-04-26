# -*- coding: utf-8 -*-

from ..syntax import macros, test, test_raises, the  # noqa: F401
from ..test.fixtures import session, testset

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

        # deleting a binding
        with env(a=42) as e:
            del e.a
            test[len(e) == 0]

    with testset("syntactic sugar"):
        with env(x=1, y=2, z=3) as e:
            # iteration, subscripting
            test[{name for name in e} == set(("x", "y", "z"))]
            test[{(name, e[name]) for name in e} == set((("x", 1),
                                                         ("y", 2),
                                                         ("z", 3)))]
            with env(x=1, y=2, z=3) as e2:
                test[the[e2] == the[e]]
            with env(x=1, y=2, z=4) as e2:  # at least one different value
                test[the[e2] != the[e]]
            with env(x=1, y=2) as e2:  # different length
                test[the[e2] != the[e]]

            # membership testing
            test["x" in the[e]]
            test["a" not in the[e]]

            # modify existing binding
            test[e.set("x", 42) == 42]  # returns the new value
            test[the[e << ("x", 23) is e]]   # instance passthrough for chaining

        # delete a binding with subscript syntax
        with env(x=1) as e:
            del e["x"]
            test[len(e) == 0]

    with testset("MutableMapping interface"):
        with env(x=1, y=2, z=3) as e:
            test[dict(e.items()) == {"x": 1, "y": 2, "z": 3}]

            test[tuple(e.keys()) == ("x", "y", "z")]
            test[tuple(e.values()) == (1, 2, 3)]

            test[e.get("x") == 1]
            test[e.get("å") is None]

        with env(x=1, y=2) as e:
            test[e.pop("x") == 1]
            test[len(e) == 1]

        with env(x=1) as e:
            test[e.popitem() == ("x", 1)]
            test[len(e) == 0]

        with env(x=1) as e:
            d = {"y": 2}
            e.update(d)
            test[set(e.keys()) == {"x", "y"}]
            test[e.x == 1 and e.y == 2]

        with env(x=1) as e:
            e.update(y=2)
            test[set(e.keys()) == {"x", "y"}]
            test[e.x == 1 and e.y == 2]

        with env(x=1) as e:
            e.setdefault("y")
            test[e.y is None]

        with env(x=1) as e:
            e.setdefault("y", 2)
            test[e.y == 2]

        with env(x=1) as e:
            e.setdefault("x", 3)
            test[e.x == 1]  # already exists, so not updated by `setdefault`.

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

        with env() as e:
            with test_raises(ValueError, "should detect invalid identifier in __delitem__"):
                del e["∞"]  # invalid identifier in del context (__delitem__)

        with env() as e:
            with test_raises(AttributeError, "overwriting a reserved name should not be allowed"):
                e.set = {1, 2, 3}

        with env(x=1) as e:
            e.finalize()
            with test_raises(TypeError, "deleting binding from finalized environment should not be allowed"):
                del e.x

        with env() as e:
            with test_raises(AttributeError, "deleting nonexistent binding should not be allowed"):
                del e.x

        with env(x=1, y=2) as e:
            e.finalize()
            test_raises[TypeError, e.pop("x"), "popping from finalized environment should not be allowed"]

        with env(x=1) as e:
            e.finalize()
            test_raises[TypeError, e.popitem(), "popping from finalized environment should not be allowed"]

        with env(x=1) as e:
            e.finalize()
            test_raises[TypeError, e.clear(), "clearing a finalized environment should not be allowed"]

        with env(x=1) as e:
            e.finalize()
            d = {"y": 2}
            test_raises[AttributeError, e.update(d), "should not be able to add new bindings to a finalized environment"]

        with env(x=1) as e:
            e.finalize()
            test_raises[AttributeError, e.update(y=2), "should not be able to add new bindings to a finalized environment"]

        with env(x=1) as e:
            d1 = {"y": 2}
            d2 = {"z": 3}
            test_raises[ValueError, e.update(d1, d2), "should take at most one mapping"]

        with env(x=1) as e:
            e.finalize()
            test_raises[AttributeError, e.setdefault("y"), "should not be able to add new bindings to a finalized environment"]

if __name__ == '__main__':  # pragma: no cover
    with session(__file__):
        runtests()
