#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Functionally updated sequences."""

__all__ = ["fupdate", "ShadowedSequence", "in_indices", "indexof"]

from collections.abc import Sequence
from operator import lt, le, ge, gt
from copy import copy

def fupdate(target, indices=None, values=None, **mappings):
    """Functionally update a sequence or a mapping.

    The input sequence can be immutable. For mappings, only mutables are
    supported (since Python doesn't provide an immutable dict type).

    Parameters:

        target: sequence or mapping
            The target to be functionally updated.

        If ``target`` is a sequence:

            indices: t or sequence of t, where t: int or slice
                The index or indices where ``target`` will be updated.

            values: one item or sequence
                The corresponding values.

        If ``target`` is a mapping:

            Use the kwargs syntax to provide any number of ``key=new_value`` pairs.

    Returns:
        The updated sequence or mapping. The input is not modified.

    Examples::

        lst = [1, 2, 3]
        out = fupdate(lst, 1, 42)
        assert lst == [1, 2, 3]
        assert out == [1, 42, 3]

        from itertools import repeat
        lst = (1, 2, 3, 4, 5)
        out = fupdate(lst, slice(1, 5, 2), tuple(repeat(10, 2)))
        assert lst == (1, 2, 3, 4, 5)
        assert out == (1, 10, 3, 10, 5)

        # a sequence of indices
        lst = (1, 2, 3, 4, 5)
        out = fupdate(lst, (1, 2, 3), (17, 23, 42))
        assert lst == (1, 2, 3, 4, 5)
        assert out == (1, 17, 23, 42, 5)

        d1 = {'foo': 'bar', 'fruit': 'apple'}
        d2 = fupdate(d1, foo='tavern')
        assert sorted(d1.items()) == [('foo', 'bar'), ('fruit', 'apple')]
        assert sorted(d2.items()) == [('foo', 'tavern'), ('fruit', 'apple')]
    """
    if indices is not None and mappings:
        raise ValueError("Cannot use both indices and mappings.")
    if indices is not None:
        # We jump through some hoops to support also immutable targets.
        def doit(seq, ix, v):
            s = ShadowedSequence(seq, ix, v)
            cls = type(seq)
            return cls(x for x in s)
        if isinstance(indices, (list, tuple)):
            seq = target
            for index, value in zip(indices, values):
                seq = doit(seq, index, value)
            return seq
        else:  # one index (or slice), value(s) pair only
            return doit(target, indices, values)
    elif mappings:
        # No immutable dicts in Python so here this is enough.
        t = copy(target)
        t.update(**mappings)
        return t
    return copy(target)

class ShadowedSequence(Sequence):
    def __init__(self, seq, ix, v):
        """Sequence with some elements shadowed by those from another sequence.

        Or in other words, a functionally updated view of a sequence.

        Essentially, ``result[k] = v[indexof(k, ix)] if k in ix else seq[k]``,
        but supports immutable inputs.

        ``ix`` may be integer (if ``v`` represents one item only)
        or slice (if ``v`` is intended as a sequence).
        """
        self.seq = seq
        self.ix = ix
        self.v = v

    def __getitem__(self, k):
        ix = self.ix
        if in_indices(k, ix):
            if isinstance(ix, slice):
                return self.v[indexof(k, ix)]
            else:  # int, just one item
                return self.v
        else:
            return self.seq[k]

    def __len__(self):
        return len(self.seq)

# TODO: support negative indices
def in_indices(i, s):
    if not isinstance(s, (slice, int)):
        raise TypeError("s must be slice or int, got {} with value {}".format(type(s), s))
    if not isinstance(i, int):
        raise TypeError("i must be int, got {} with value {}".format(type(i), i))
    if isinstance(s, slice):
        start = s.start or 0
        step = s.step or +1
        cmp_start, cmp_end = (ge, lt) if step > 0 else (le, gt)
        after_start = cmp_start(i, start)
        before_stop = cmp_end(i, s.stop)
        on_grid = (i - start) % step == 0
        return after_start and on_grid and before_stop
    else:
        return s == i

def indexof(i, s):
    if not isinstance(s, slice):
        raise TypeError("s must be slice, got {} with value {}".format(type(s), s))
    if in_indices(i, s):
        start = s.start or 0
        step = s.step or +1
        return (i - start) // step

def test():
    lst = [1, 2, 3]
    out = fupdate(lst, 1, 42)
    assert lst == [1, 2, 3]
    assert out == [1, 42, 3]

    from itertools import repeat
    lst = (1, 2, 3, 4, 5)
    out = fupdate(lst, slice(1, 5, 2), tuple(repeat(10, 2)))
    assert lst == (1, 2, 3, 4, 5)
    assert out == (1, 10, 3, 10, 5)

    lst = (1, 2, 3, 4, 5)
    out = fupdate(lst, (1, 2, 3), (17, 23, 42))
    assert lst == (1, 2, 3, 4, 5)
    assert out == (1, 17, 23, 42, 5)

    d1 = {'foo': 'bar', 'fruit': 'apple'}
    d2 = fupdate(d1, foo='tavern')
    assert sorted(d1.items()) == [('foo', 'bar'), ('fruit', 'apple')]
    assert sorted(d2.items()) == [('foo', 'tavern'), ('fruit', 'apple')]

    print("All tests PASSED")

if __name__ == '__main__':
    test()
