# -*- coding: utf-8 -*-

from ..syntax import macros, test, test_raises  # noqa: F401
from .fixtures import session

from ..assignonce import assignonce

def runtests():
    with assignonce() as e:
        with test("basic usage"):
            e.a = 2
            e.b = 3

        with test_raises(AttributeError, "should not be able to redefine an already defined name"):
            e.a = 5

        with test("rebind"):
            e.set("a", 42)  # rebind

        with test_raises(AttributeError, "should not be able to rebind an unbound name"):
            e.set("c", 3)

if __name__ == '__main__':  # pragma: no cover
    with session(__file__):
        runtests()
