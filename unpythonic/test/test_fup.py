# -*- coding: utf-8 -*-

from itertools import repeat
from collections import namedtuple

from ..fup import fupdate

def test():
    # mutable input
    lst = [1, 2, 3]
    out = fupdate(lst, 1, 42)
    assert lst == [1, 2, 3]
    assert out == [1, 42, 3]

    # immutable input
    lst = (1, 2, 3, 4, 5)
    out = fupdate(lst, slice(1, 5, 2), tuple(repeat(10, 2)))
    assert lst == (1, 2, 3, 4, 5)
    assert out == (1, 10, 3, 10, 5)

    # negative index
    lst = [1, 2, 3]
    out = fupdate(lst, -1, 42)
    assert lst == [1, 2, 3]
    assert out == [1, 2, 42]

    # no start index
    lst = (1, 2, 3, 4, 5)
    out = fupdate(lst, slice(None, 5, 2), tuple(repeat(10, 3)))
    assert lst == (1, 2, 3, 4, 5)
    assert out == (10, 2, 10, 4, 10)

    # no stop index
    lst = (1, 2, 3, 4, 5)
    out = fupdate(lst, slice(1, None, 2), tuple(repeat(10, 2)))
    assert lst == (1, 2, 3, 4, 5)
    assert out == (1, 10, 3, 10, 5)

    # no start or stop index, just step
    lst = (1, 2, 3, 4, 5)
    out = fupdate(lst, slice(None, None, 2), tuple(repeat(10, 3)))
    assert lst == (1, 2, 3, 4, 5)
    assert out == (10, 2, 10, 4, 10)

    # just step, backwards
    lst = (1, 2, 3, 4, 5)
    out = fupdate(lst, slice(None, None, -1), tuple(range(5)))
    assert lst == (1, 2, 3, 4, 5)
    assert out == (4, 3, 2, 1, 0)

    # multiple individual items
    lst = (1, 2, 3, 4, 5)
    out = fupdate(lst, (1, 2, 3), (17, 23, 42))
    assert lst == (1, 2, 3, 4, 5)
    assert out == (1, 17, 23, 42, 5)

    # multiple slices and sequences
    lst = tuple(range(10))
    out = fupdate(lst, (slice(0, 10, 2), slice(1, 10, 2)),
                       (tuple(repeat(2, 5)), tuple(repeat(3, 5))))
    assert lst == tuple(range(10))
    assert out == (2, 3, 2, 3, 2, 3, 2, 3, 2, 3)

    # mix and match
    lst = tuple(range(10))
    out = fupdate(lst, (slice(0, 10, 2), slice(1, 10, 2), 6),
                       (tuple(repeat(2, 5)), tuple(repeat(3, 5)), 42))
    assert lst == tuple(range(10))
    assert out == (2, 3, 2, 3, 2, 3, 42, 3, 2, 3)

    # replacement sequence too short
    try:
        lst = (1, 2, 3, 4, 5)
        out = fupdate(lst, slice(1, None, 2), (10,))  # need 2 items, have 1
    except ValueError:
        pass
    else:
        assert False

    # mapping
    d1 = {'foo': 'bar', 'fruit': 'apple'}
    d2 = fupdate(d1, foo='tavern')
    assert sorted(d1.items()) == [('foo', 'bar'), ('fruit', 'apple')]
    assert sorted(d2.items()) == [('foo', 'tavern'), ('fruit', 'apple')]

    # namedtuple
    A = namedtuple("A", "p q")
    a = A(17, 23)
    out = fupdate(a, 0, 42)
    assert a == A(17, 23)
    assert out == A(42, 23)

    print("All tests PASSED")

if __name__ == '__main__':
    test()
