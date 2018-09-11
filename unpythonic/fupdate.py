#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Functionally updated sequences and mappings."""

__all__ = ["fupdate", "ShadowedSequence", "in_indices", "indexof"]

from collections.abc import Sequence
from operator import lt, le, ge, gt
from copy import copy

def fupdate(target, indices=None, values=None, **mappings):
    """Return a functionally updated copy of a sequence or mapping.

    The input sequence can be immutable. For mappings, only mutables are
    supported (since Python doesn't provide an immutable dict type).

    The requirement for sequences is that the target's type must provide a way
    to construct an instance from an iterable.

    We first check whether target's type provides ``._make(iterable)``,
    and if so, call that to build the output. Otherwise, we call the
    regular constructor.

    In Python's standard library, the ``._make`` mechanism is used by classes
    created by ``collections.namedtuple``.

    **CAUTION**: Negative indices are currently **not** supported.

    Parameters:
        target: sequence or mapping
            The target to be functionally updated.

        If ``target`` is a sequence:

            indices: t or sequence of t, where t: int or slice
                The index or indices where ``target`` will be updated.
                If a sequence of t, applied left to right.

            values: one item or sequence
                The corresponding values.

        If ``target`` is a mapping:

            Use the kwargs syntax to provide any number of ``key=new_value`` pairs.

    Returns:
        The updated sequence or mapping. The input is not modified.

    **Examples**::

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

        # a sequence of slices
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

        from collections import namedtuple
        A = namedtuple("A", "p q")
        a = A(17, 23)
        out = fupdate(a, 0, 42)
        assert a == A(17, 23)
        assert out == A(42, 23)

        d1 = {'foo': 'bar', 'fruit': 'apple'}
        d2 = fupdate(d1, foo='tavern')
        assert sorted(d1.items()) == [('foo', 'bar'), ('fruit', 'apple')]
        assert sorted(d2.items()) == [('foo', 'tavern'), ('fruit', 'apple')]
    """
    if indices is not None and mappings:
        raise ValueError("Cannot use both indices and mappings.")
    if indices is not None:
        def finalize(seq):
            cls = type(target)
            gen = (x for x in seq)
            if hasattr(cls, "_make"):  # namedtuple support
                return cls._make(gen)
            else:
                return cls(gen)
        if isinstance(indices, (list, tuple)):
            seq = target  # stack up ShadowedSequences...
            for index, value in zip(indices, values):
                seq = ShadowedSequence(seq, index, value)
            return finalize(seq)  # ...and flatten them when done.
        else:  # one index (or slice), value(s) pair only
            return finalize(ShadowedSequence(target, indices, values))
    elif mappings:
        # No immutable dicts in Python so here this is enough.
        t = copy(target)
        t.update(**mappings)  # TODO: use collections.ChainMap instead?
        return t
    return copy(target)

# Needed by fupdate for immutable sequence inputs (no item assignment).
class ShadowedSequence(Sequence):
    def __init__(self, seq, ix, v):
        """Sequence with some elements shadowed by those from another sequence.

        Or in other words, a functionally updated view of a sequence.

        Essentially, ``out[k] = v[indexof(k, ix)] if in_indices(k, ix) else seq[k]``,
        but doesn't actually allocate ``out``.

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
    """Return whether the int i is in the slice s.

    For convenience, s may be int instead of slice; then return whether i == s.
    """
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
        return i == s

def indexof(i, s):
    """Return the index of the int i in the slice s, or None if i is not in s.

    (I.e. how-manyth item of the slice the index i is.)
    """
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

    lst = tuple(range(10))
    out = fupdate(lst, (slice(0, 10, 2), slice(1, 10, 2)),
                       (tuple(repeat(2, 5)), tuple(repeat(3, 5))))
    assert lst == tuple(range(10))
    assert out == (2, 3, 2, 3, 2, 3, 2, 3, 2, 3)

    lst = tuple(range(10))
    out = fupdate(lst, (slice(0, 10, 2), slice(1, 10, 2), 6),
                       (tuple(repeat(2, 5)), tuple(repeat(3, 5)), 42))
    assert lst == tuple(range(10))
    assert out == (2, 3, 2, 3, 2, 3, 42, 3, 2, 3)

    d1 = {'foo': 'bar', 'fruit': 'apple'}
    d2 = fupdate(d1, foo='tavern')
    assert sorted(d1.items()) == [('foo', 'bar'), ('fruit', 'apple')]
    assert sorted(d2.items()) == [('foo', 'tavern'), ('fruit', 'apple')]

    from collections import namedtuple
    A = namedtuple("A", "p q")
    a = A(17, 23)
    out = fupdate(a, 0, 42)
    assert a == A(17, 23)
    assert out == A(42, 23)

    print("All tests PASSED")

if __name__ == '__main__':
    test()
