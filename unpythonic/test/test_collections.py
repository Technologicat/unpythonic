# -*- coding: utf-8 -*-

from collections.abc import Mapping, MutableMapping, Hashable

from ..collections import box, frozendict

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

    print("All tests PASSED")

if __name__ == '__main__':
    test()
