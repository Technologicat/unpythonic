# -*- coding: utf-8 -*-
"""Functionally update sequences and mappings."""

__all__ = ["fupdate"]

from copy import copy

from .collections import frozendict, ShadowedSequence

def fupdate(target, indices=None, values=None, **bindings):
    """Return a functionally updated copy of a sequence or a mapping.

    The input can be mutable or immutable; it does not matter.

    **For mappings**, ``fupdate`` supports any mutable mapping that has an
    ``.update(**kwargs)`` method (such as ``dict``), and the immutable mapping
    ``unpythonic.collections.frozendict``.

    By design, the behavior of ``fupdate`` differs from ``collections.ChainMap``.
    Whereas ``ChainMap`` keeps references to the original mappings, ``fupdate``
    makes a shallow copy, to prevent any later mutations of the original from
    affecting the functionally updated copy.

    **For sequences**, the requirement is that the target's type must provide
    a way to construct an instance from an iterable.

    We first check whether target's type provides ``._make(iterable)``,
    and if so, call that to build the output. Otherwise, we call the
    regular constructor, which must then accept a single iterable argument.

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
        The updated sequence or mapping.

        The input is never mutated, and it is **always** shallow-copied, so any
        later mutations to the original do not affect the functionally updated
        copy.

        Also, the invariant ``type(output) is type(input)`` holds.

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
    if indices is not None and bindings:
        raise ValueError("Cannot use both indices and bindings.")
    if indices is not None:
        def make_output(seq):
            cls = type(target)
            ctor = cls._make if hasattr(cls, "_make") else cls  # namedtuple support
            gen = (x for x in seq)
            return ctor(gen)
        if not isinstance(indices, (list, tuple)):
            # one index (or slice), value(s) pair only
            return make_output(ShadowedSequence(target, indices, values))
        seq = target
        for index, value in zip(indices, values):
            seq = ShadowedSequence(seq, index, value)
        return make_output(seq)
    if bindings:
        if isinstance(target, frozendict):
            cls = type(target)  # subclassing is possible...
            return cls(target, **bindings)
        # assume mutable mapping
        t = copy(target)
        t.update(**bindings)
        return t
    return copy(target)
