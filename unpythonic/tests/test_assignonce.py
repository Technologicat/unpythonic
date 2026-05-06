# -*- coding: utf-8 -*-

from ..syntax import macros, test, test_raises  # noqa: F401
from ..test.fixtures import session

from ..assignonce import assignonce

def runtests():
    with assignonce() as e:
        with test["basic usage"]:
            e.a = 2
            e.b = 3

        with test_raises[AttributeError, "should not be able to redefine an already defined name"]:
            e.a = 5

        with test["rebind"]:
            e.set("a", 42)  # rebind

        with test_raises[AttributeError, "should not be able to rebind an unbound name"]:
            e.set("c", 3)

        with test_raises[AttributeError, "should not be able to delete a defined name (would bypass assign-once)"]:
            del e.a

        # `e.a` was 42 from the rebind above; the failed delete must not have removed it.
        test[e.a == 42]

if __name__ == '__main__':  # pragma: no cover
    with session(__file__):
        runtests()
