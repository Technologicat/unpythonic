# -*- coding: utf-8 -*-

from ..env import env

def test():
    # basic functionality
    with env(x=1) as e:
        assert len(e) == 1
        assert e.x == 1

    # create new item
    with env(x=1) as e:
        e.y = 42
        assert e.y == 42
        assert len(e) == 2

    # undefined name
    try:
        with env(x=1) as e:
            e.y  # invalid, no y in e
    except AttributeError:
        pass
    else:
        assert False

    # manual clear
    with env(x=1) as e:
        e.clear()
        assert len(e) == 0

    # auto-clear upon exit from "with" block
    with env(a=42) as e:
        assert len(e) == 1
    assert len(e) == 0

    # finalize
    try:
        with env(x=1) as e:
            e.finalize()
            e.y = 42  # invalid, a finalized environment doesn't accept new bindings
    except AttributeError:
        pass
    else:
        assert False

    with env(x=1, y=2, z=3) as e:
        # iteration, subscripting
        assert {name for name in e} == set(("x", "y", "z"))
        assert {(name, e[name]) for name in e} == set((("x", 1),
                                                       ("y", 2),
                                                       ("z", 3)))
        assert dict(e.items()) == {"x": 1, "y": 2, "z": 3}

        # membership testing
        assert "x" in e
        assert "a" not in e

        # modify existing binding
        assert e.set("x", 42) == 42  # returns the new value
        assert e << ("x", 23) is e   # instance passthrough for chaining

    try:
        with env() as e:
            e.set("foo", 42)  # invalid, set() only modifies existing bindings
    except AttributeError:
        pass
    else:
        assert False

    try:
        with env() as e:
            e["∞"] = 1  # invalid identifier in store context (__setitem__)
    except ValueError:
        pass
    else:
        assert False

    try:
        with env() as e:
            e["∞"]  # invalid identifier in load context (__getitem__)
    except ValueError:
        pass
    else:
        assert False

    print("All tests PASSED")

if __name__ == '__main__':
    test()
