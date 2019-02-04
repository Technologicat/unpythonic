# -*- coding: utf-8 -*-
"""Functionally update sequences and mappings."""

__all__ = ["fupdate", "frozendict", "get_collection_abcs",
           "ShadowedSequence", "in_slice", "index_in_slice"]

from functools import wraps
import collections
from collections.abc import Sequence, MutableMapping, Hashable
from inspect import isclass
from operator import lt, le, ge, gt
from copy import copy

_the_empty_frozendict = None
class frozendict:
    """Immutable dictionary.

    Basic usage::

        d = frozendict(m)
        d = frozendict({'a': 1, 'b': 2})
        d = frozendict(a=1, b=2)

    where ``m`` is any type valid for ``E`` in ``dict.update``.

    Functional update::

        d = frozendict(m0, m1, ...)
        d = frozendict({'a': 1, 'b': 2}, {'a': 42})
        d = frozendict(m, a=1, b=2)
        d = frozendict(m0, m1, ..., a=1, b=2)

    Then ``d`` behaves just like a regular dictionary, except it is not writable.
    As usual, this does **not** protect from mutating the values themselves,
    if they happen to be mutable objects (such as containers).

    Any ``m`` used in the initialization of a ``frozendict`` is shallow-copied
    to make sure the bindings in the ``frozendict`` do not change even if the
    original is later mutated.

    Just like for ``tuple`` and ``frozenset``, the empty ``frozendict`` is a
    singleton; each no-argument call ``frozendict()`` will return the same object
    instance. (But don't pickle it; it is freshly created in each session).

    In terms of ``collections.abc``, a ``frozendict`` is a ``Container``,
    ``Hashable``, ``Iterable``, ``Mapping`` and ``Sized``.

    Just like for ``dict``, the abstract superclasses are virtual; they are
    detected by the built-ins ``issubclass`` and ``isinstance``, but they are
    not part of the MRO.
    """
    def __new__(cls, *ms, **mappings):  # make the empty frozendict() a singleton
        if not ms and not mappings:
            global _the_empty_frozendict
            if _the_empty_frozendict is None:
                _the_empty_frozendict = super().__new__(cls)
            return _the_empty_frozendict
        return super().__new__(cls)  # object() takes no args, but we need to see them

    def __init__(self, *ms, **mappings):
        """Arguments:

               ms: mappings; optional
                   If one argument is provided: the input mapping to freeze.

                   If more are provided, the second and later ones will
                   functionally update the data, in the order given.

                   Accepts any type understood by ``dict.update``.

               mappings: kwargs in the form key=value; optional
                   Essentially like the ``**F`` argument of ``dict.update``.

                   Functional updates applied at the end, after the last mapping
                   in ``ms``. Can be useful for overriding individual items.
        """
        super().__init__()
        self._data = {}
        for m in ms:
            try:
                self._data.update(m)
            except TypeError:
                pass
        self._data.update(mappings)

    @wraps(dict.__repr__)
    def __repr__(self):
        return "frozendict({})".format(self._data.__repr__())

    def __hash__(self):
        return hash(frozenset(self.items()))

    # Provide any read-access parts of the dict API.
    #
    # This is somewhat hacky, but "composition over inheritance", and if we
    # subclassed dict, that would give us the wrong ABC (MutableMapping)
    # with no way to customize it away (short of monkey-patching MutableMapping).
    #
    # https://docs.python.org/3/library/collections.abc.html
    # https://docs.python.org/3/reference/datamodel.html#emulating-container-types
    @wraps(dict.__getitem__)
    def __getitem__(self, k):
        return self._data.__getitem__(k)
    @wraps(dict.__iter__)
    def __iter__(self):
        return self._data.__iter__()
    @wraps(dict.__len__)
    def __len__(self):
        return self._data.__len__()
    @wraps(dict.__contains__)
    def __contains__(self, k):
        return self._data.__contains__(k)
    @wraps(dict.keys)
    def keys(self):
        return self._data.keys()
    @wraps(dict.items)
    def items(self):
        return self._data.items()
    @wraps(dict.values)
    def values(self):
        return self._data.values()
    @wraps(dict.get)
    def get(self, k, *d):
        return self._data.get(k, *d)
    @wraps(dict.__eq__)
    def __eq__(self, other):
        other = other._data if isinstance(other, frozendict) else other
        return self._data.__eq__(other)
    @wraps(dict.__ne__)
    def __ne__(self, other):
        other = other._data if isinstance(other, frozendict) else other
        return self._data.__ne__(other)

# Register implicit ABCs for frozendict (like dict has).
#
# https://stackoverflow.com/questions/42781267/is-there-a-pythonics-way-to-distinguish-sequences-objects-like-tuple-and-list
# https://docs.python.org/3/library/abc.html#abc.ABCMeta.register
# Further reading: https://stackoverflow.com/questions/40764347/python-subclasscheck-subclasshook
def get_collection_abcs(cls):
    """Return a set of the collections.abc superclasses of cls (virtuals too)."""
    return {v for k, v in vars(collections.abc).items() if isclass(v) and issubclass(cls, v)}
for abscls in get_collection_abcs(dict) - {MutableMapping} | {Hashable}:
    abscls.register(frozendict)
del abscls  # namespace cleanup

def fupdate(target, indices=None, values=None, **mappings):
    """Return a functionally updated copy of a sequence or a mapping.

    The input can be mutable or immutable; it does not matter.

    **For mappings**, ``fupdate`` supports any mutable mapping that has an
    ``.update(**kwargs)`` method (such as ``dict``), and the immutable mapping
    ``unpythonic.fup.frozendict``.

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
        if isinstance(target, frozendict):
            cls = type(target)  # subclassing is possible...
            return cls(target, **mappings)
        # assume mutable mapping
        t = copy(target)
        t.update(**mappings)
        return t
    return copy(target)

# Needed by fupdate for immutable sequence inputs (no item assignment).
class ShadowedSequence(Sequence):
    """Sequence with some elements shadowed by those from another sequence.

    Or in other words, a functionally updated view of a sequence. Or somewhat
    like ``collections.ChainMap``, but for sequences.

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
