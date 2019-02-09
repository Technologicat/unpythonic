# -*- coding: utf-8 -*-

from collections.abc import Mapping, MutableMapping, Hashable, Container, Iterable, Sized
from pickle import dumps, loads

from ..collections import box, frozendict, mogrify

def test():
    # box: mutable single-item container à la Racket
    b = box(17)
    def f(b):
        b.x = 23
    assert b.x == 17
    f(b)
    assert b.x == 23

    b2 = box(17)
    assert 17 in b2
    assert 23 not in b2
    assert [x for x in b2] == [17]
    assert b2 == 17  # for convenience, a box is considered equal to the item it contains
    assert len(b2) == 1
    assert b2 != b

    b3 = box(17)
    assert b3 == b2  # boxes are considered equal if their contents are

    try:
        d = {}
        d[b] = "foo"
    except TypeError:
        pass
    else:
        assert False, "box should not be hashable"

    assert not issubclass(box, Hashable)
    assert issubclass(box, Container)
    assert issubclass(box, Iterable)
    assert issubclass(box, Sized)

    b1 = box("abcdefghijklmnopqrstuvwxyzåäö")
    b2 = loads(dumps(b1))  # pickling
    assert b2 == b1

    # frozendict: like frozenset, but for dictionaries
    d3 = frozendict({'a': 1, 'b': 2})
    assert d3['a'] == 1
    try:
        d3['c'] = 42
    except TypeError:
        pass
    else:
        assert False, "frozendict should not be writable"

    d4 = frozendict(d3, a=42)  # functional update
    assert d4['a'] == 42 and d4['b'] == 2
    assert d3['a'] == 1  # original not mutated

    d5 = frozendict({'a': 1, 'b': 2}, {'a': 42})  # rightmost definition of each key wins
    assert d5['a'] == 42 and d5['b'] == 2

    assert frozendict() is frozendict()  # empty-frozendict singleton property

    d7 = frozendict({1:2, 3:4})
    assert 3 in d7
    assert len(d7) == 2
    assert set(d7.keys()) == {1, 3}
    assert set(d7.values()) == {2, 4}
    assert set(d7.items()) == {(1, 2), (3, 4)}
    assert d7 == frozendict({1:2, 3:4})
    assert d7 != frozendict({1:2})
    assert d7 == {1:2, 3:4}  # like frozenset, __eq__ doesn't care whether mutable or not
    assert d7 != {1:2}
    assert {k for k in d7} == {1, 3}
    assert d7.get(3) == 4
    assert d7.get(5, 0) == 0
    assert d7.get(5) is None

    assert issubclass(frozendict, Mapping)
    assert not issubclass(frozendict, MutableMapping)

    assert issubclass(frozendict, Hashable)
    assert hash(d7) == hash(frozendict({1:2, 3:4}))
    assert hash(d7) != hash(frozendict({1:2}))

    assert issubclass(frozendict, Container)
    assert issubclass(frozendict, Iterable)
    assert issubclass(frozendict, Sized)

    d1 = frozendict({1: 2, 3: 4, "somekey": "somevalue"})
    d2 = loads(dumps(d1))  # pickling
    assert d2 == d1

    # in-place map
    double = lambda x: 2*x
    lst = [1, 2, 3]
    lst2 = mogrify(double, lst)
    assert lst2 == [2, 4, 6]
    assert lst2 is lst

    s = {1, 2, 3}
    s2 = mogrify(double, s)
    assert s2 == {2, 4, 6}
    assert s2 is s

    d = {1: 2, 3: 4}
    d2 = mogrify(double, d)
    assert set(d2.items()) == {(1, 4), (3, 8)}
    assert d2 is d

    b = box(17)
    b2 = mogrify(double, b)
    assert b2 == 34
    assert b2 is b

    tup = (1, 2, 3)
    tup2 = mogrify(double, tup)
    assert tup2 == (2, 4, 6)
    assert tup2 is not tup  # immutable, cannot be updated in-place

    fs = frozenset({1, 2, 3})
    fs2 = mogrify(double, fs)
    assert fs2 == {2, 4, 6}
    assert fs2 is not fs

    fd = frozendict({1: 2, 3: 4})
    fd2 = mogrify(double, fd)
    assert set(fd2.items()) == {(1, 4), (3, 8)}
    assert fd2 is not fd

    atom = 17
    atom2 = mogrify(double, atom)
    assert atom2 == 34
    assert atom2 is not atom

    print("All tests PASSED")

if __name__ == '__main__':
    test()
