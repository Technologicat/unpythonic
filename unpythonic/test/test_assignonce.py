# -*- coding: utf-8 -*-

from ..syntax import macros, test, test_raises  # noqa: F401
from .fixtures import testset

from ..assignonce import assignonce

def runtests():
    with testset("unpythonic.assignonce"):
        with assignonce() as e:
            with test("basic usage"):
                e.a = 2
                e.b = 3

            with test_raises(AttributeError, "trying to redefine an already defined name"):
                e.a = 5

            with test("rebind"):
                e.set("a", 42)  # rebind

            with test_raises(AttributeError, "trying to rebind an unbound name"):
                e.set("c", 3)

if __name__ == '__main__':
    runtests()
