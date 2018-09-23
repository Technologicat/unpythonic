#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Functionally update sequences and mappings."""

__all__ = ["fupdate", "ShadowedSequence", "in_slice", "index_in_slice"]

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
        def make_output(seq):
            cls = type(target)
            gen = (x for x in seq)
            if hasattr(cls, "_make"):  # namedtuple support
                return cls._make(gen)
            return cls(gen)
        if not isinstance(indices, (list, tuple)):
            # one index (or slice), value(s) pair only
            return make_output(ShadowedSequence(target, indices, values))
        seq = target
        for index, value in zip(indices, values):
            seq = ShadowedSequence(seq, index, value)
        return make_output(seq)
    if mappings:
        t = copy(target)
        t.update(**mappings)  # TODO: use collections.ChainMap instead?
        return t
    return copy(target)

# Needed by fupdate for immutable sequence inputs (no item assignment).
class ShadowedSequence(Sequence):
    """Sequence with some elements shadowed by those from another sequence.

    Or in other words, a functionally updated view of a sequence.

    Essentially, ``out[k] = v[index_in_slice(k, ix)] if in_slice(k, ix) else seq[k]``,
    but doesn't actually allocate ``out``.

    ``ix`` may be integer (if ``v`` represents one item only)
    or slice (if ``v`` is intended as a sequence).
    """
    def __init__(self, seq, ix, v):
        if not isinstance(ix, (slice, int)):
            raise TypeError("ix: expected slice or int, got {} with value {}".format(type(ix), ix))
        self.seq = seq
        self.ix = ix
        self.v = v

    def __getitem__(self, k):
        ix = self.ix
        l = len(self)
        if in_slice(k, ix, l):
            if isinstance(ix, int):
                return self.v  # just one item
            # we already know k is in ix, so skip validation for speed.
            i = _index_in_slice(k, ix, l, _validate=False)
            if i >= len(self.v):
                # TODO: Would be nice to raise IndexError, but the genexpr
                # in fupdate automatically catches that, hiding the error.
                raise ValueError("Replacement sequence too short; attempted to access index {} with len {} (items: {})".format(i, len(self.v), self.v))
            return self.v[i]
        return self.seq[k]  # not in slice

    def __len__(self):
        return len(self.seq)

def in_slice(i, s, l=None):
    """Return whether the int i is in the slice s.

    For convenience, ``s`` may be int instead of slice; then return
    whether ``i == s``.

    The optional ``l`` is the length of the sequence being indexed, used for
    interpreting any negative indices, and default start and stop values
    (if ``s.start`` or ``s.stop`` is ``None``).

    If ``l is None``, negative or missing ``s.start`` or ``s.stop`` may raise
    ValueError. (A negative ``s.step`` by itself does not need ``l``.)
    """
    if not isinstance(s, (slice, int)):
        raise TypeError("s must be slice or int, got {} with value {}".format(type(s), s))
    if not isinstance(i, int):
        raise TypeError("i must be int, got {} with value {}".format(type(i), i))
    wrap = _make_negidx_converter(l)
    i = wrap(i)
    if isinstance(s, int):
        s = wrap(s)
        return i == s
    start, stop, step = _canonize_slice(s, l, wrap)
    cmp_start, cmp_end = (ge, lt) if step > 0 else (le, gt)
    at_or_after_start = cmp_start(i, start)
    before_stop = cmp_end(i, stop)
    on_grid = (i - start) % step == 0
    return at_or_after_start and on_grid and before_stop

def index_in_slice(i, s, l=None):
    """Return the index of the int i in the slice s, or None if i is not in s.

    (I.e. how-manyth item of the slice the index i is.)

    The optional sequence length ``l`` works the same as in ``in_slice``.
    """
    return _index_in_slice(i, s, l)

# efficiency: allow skipping the validation check for call sites
# that have already checked with in_slice().
def _index_in_slice(i, s, l=None, _validate=True):
    if (not _validate) or in_slice(i, s, l):
        wrap = _make_negidx_converter(l)
        start, _, step = _canonize_slice(s, l, wrap)
        return (wrap(i) - start) // step

def _make_negidx_converter(l):  # l: length of sequence being indexed
    if l is not None:
        if not isinstance(l, int):
            raise TypeError("l must be int, got {} with value {}".format(type(l), l))
        if l <= 0:
            raise ValueError("l must be an int >= 1, got {}".format(l))
        def apply_conversion(k):
            return k % l
    else:
        def apply_conversion(k):
            raise ValueError("Need l to interpret negative indices")
    def convert(k):
        if k is not None:
            if not isinstance(k, int):
                raise TypeError("k must be int, got {} with value {}".format(type(k), k))
            return apply_conversion(k) if k < 0 else k
    return convert

def _canonize_slice(s, l=None, w=None):  # convert negatives, inject defaults.
    if not isinstance(s, slice):
        raise TypeError("s must be slice, got {} with value {}".format(type(s), s))

    step = s.step if s.step is not None else +1  # no "s.step or +1"; someone may try step=0
    if step == 0:
        raise ValueError("slice step cannot be zero")  # message copied from range(5)[0:4:0]

    wrap = w or _make_negidx_converter(l)

    start = wrap(s.start)
    if start is None:
        if step > 0:
            start = 0
        else:
            if l is None:
                raise ValueError("Need l to determine default start for step < 0")
            start = wrap(-1)

    stop = wrap(s.stop)
    if stop is None:
        if step > 0:
            if l is None:
                raise ValueError("Need l to determine default stop for step > 0")
            stop = l
        else:
            stop = -1  # yes, really -1 to have index 0 inside the slice

    return start, stop, step

def test():
    # mutable input
    lst = [1, 2, 3]
    out = fupdate(lst, 1, 42)
    assert lst == [1, 2, 3]
    assert out == [1, 42, 3]

    # immutable input
    from itertools import repeat
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
    from collections import namedtuple
    A = namedtuple("A", "p q")
    a = A(17, 23)
    out = fupdate(a, 0, 42)
    assert a == A(17, 23)
    assert out == A(42, 23)

    print("All tests PASSED")

if __name__ == '__main__':
    test()
