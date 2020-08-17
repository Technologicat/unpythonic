# -*- coding: utf-8 -*-

from ..syntax import macros, test, test_raises  # noqa: F401
from .fixtures import testset

from itertools import repeat
from collections import namedtuple

from ..fup import fupdate
from ..collections import frozendict

def runtests():
    with testset("unpythonic.fup"):
        with testset("mutable sequence"):
            lst = [1, 2, 3]
            out = fupdate(lst, 1, 42)
            test[lst == [1, 2, 3]]
            test[out == [1, 42, 3]]
            test[type(out) is type(lst)]

        with testset("immutable sequence"):
            lst = (1, 2, 3, 4, 5)
            out = fupdate(lst, slice(1, 5, 2), tuple(repeat(10, 2)))
            test[lst == (1, 2, 3, 4, 5)]
            test[out == (1, 10, 3, 10, 5)]
            test[type(out) is type(lst)]

        with testset("namedtuple"):
            A = namedtuple("A", "p q")
            a = A(17, 23)
            out = fupdate(a, 0, 42)
            test[a == A(17, 23)]
            test[out == A(42, 23)]
            test[type(out) is type(a)]

        with testset("mutable mapping"):
            d1 = {'foo': 'bar', 'fruit': 'apple'}
            d2 = fupdate(d1, foo='tavern')
            test[sorted(d1.items()) == [('foo', 'bar'), ('fruit', 'apple')]]
            test[sorted(d2.items()) == [('foo', 'tavern'), ('fruit', 'apple')]]
            test[type(d2) is type(d1)]

        with testset("immutable mapping (unpythonic.collections.frozendict)"):
            d3 = frozendict({'a': 1, 'b': 2})
            d4 = fupdate(d3, a=23)
            test[d4['a'] == 23 and d4['b'] == 2]
            test[d3['a'] == 1]
            test[type(d4) is type(d3)]

        with testset("negative index"):
            lst = [1, 2, 3]
            out = fupdate(lst, -1, 42)
            test[lst == [1, 2, 3]]
            test[out == [1, 2, 42]]

        with testset("no start index"):
            lst = (1, 2, 3, 4, 5)
            out = fupdate(lst, slice(None, 5, 2), tuple(repeat(10, 3)))
            test[lst == (1, 2, 3, 4, 5)]
            test[out == (10, 2, 10, 4, 10)]

        with testset("no stop index"):
            lst = (1, 2, 3, 4, 5)
            out = fupdate(lst, slice(1, None, 2), tuple(repeat(10, 2)))
            test[lst == (1, 2, 3, 4, 5)]
            test[out == (1, 10, 3, 10, 5)]

        with testset("no start or stop index, just step"):
            lst = (1, 2, 3, 4, 5)
            out = fupdate(lst, slice(None, None, 2), tuple(repeat(10, 3)))
            test[lst == (1, 2, 3, 4, 5)]
            test[out == (10, 2, 10, 4, 10)]

        with testset("just step, backwards"):
            lst = (1, 2, 3, 4, 5)
            out = fupdate(lst, slice(None, None, -1), tuple(range(5)))
            test[lst == (1, 2, 3, 4, 5)]
            test[out == (4, 3, 2, 1, 0)]

        with testset("multiple individual items"):
            lst = (1, 2, 3, 4, 5)
            out = fupdate(lst, (1, 2, 3), (17, 23, 42))
            test[lst == (1, 2, 3, 4, 5)]
            test[out == (1, 17, 23, 42, 5)]

        with testset("multiple slices and sequences"):
            lst = tuple(range(10))
            out = fupdate(lst, (slice(0, 10, 2), slice(1, 10, 2)),
                          (tuple(repeat(2, 5)), tuple(repeat(3, 5))))
            test[lst == tuple(range(10))]
            test[out == (2, 3, 2, 3, 2, 3, 2, 3, 2, 3)]

        with testset("mix and match"):
            lst = tuple(range(10))
            out = fupdate(lst, (slice(0, 10, 2), slice(1, 10, 2), 6),
                          (tuple(repeat(2, 5)), tuple(repeat(3, 5)), 42))
            test[lst == tuple(range(10))]
            test[out == (2, 3, 2, 3, 2, 3, 42, 3, 2, 3)]

        with testset("error cases"):
            with test_raises(IndexError, "should detect replacement sequence too short"):
                lst = (1, 2, 3, 4, 5)
                out = fupdate(lst, slice(1, None, 2), (10,))  # need 2 items, have 1

if __name__ == '__main__':
    runtests()
