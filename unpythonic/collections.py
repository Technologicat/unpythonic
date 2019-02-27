# -*- coding: utf-8 -*-
"""Additional containers and container utilities."""

__all__ = ["box", "frozendict", "SequenceView", "ShadowedSequence",
           "get_abcs", "in_slice", "index_in_slice"]

from functools import wraps
from collections import abc
from collections.abc import Container, Iterable, Hashable, Sized, \
                            Sequence, Mapping, Set, \
                            MutableSequence, MutableMapping, MutableSet
from inspect import isclass
from operator import lt, le, ge, gt
from math import ceil

from .llist import cons

def get_abcs(cls):
    """Return a set of the collections.abc superclasses of cls (virtuals too)."""
    return {v for k, v in vars(abc).items() if isclass(v) and issubclass(cls, v)}

# TODO: allow multiple input container args in mogrify, like map does (also support longest, fillvalue)
#   OTOH, that's assuming an ordered iterable... so maybe not for general containers?
# TODO: move to unpythonic.it? This is a spork...
def mogrify(func, container):
    """In-place recursive map for mutable containers.

    Recurse on container, apply func to each atom. Containers can be nested,
    with an arbitrary combination of types.

    Containers are detected by checking for instances of ``collections.abc``
    superclasses (also virtuals are ok).

    Supported abcs are ``MutableMapping``, ``MutableSequence``, ``MutableSet``,
    ``Mapping``, ``Sequence`` and ``Set``.

    For convenience, we introduce some special cases:

        - Any classes created by ``collections.namedtuple``, because they
          do not conform to the standard constructor API for a ``Sequence``.

          Thus, for a ``Sequence``, we first check for the presence of a
          ``._make()`` method, and if found, use it as the constructor.
          Otherwise we use the regular constructor.

        - ``str`` is treated as an atom, although technically a ``Sequence``.

          It doesn't conform to the exact same API (its constructor does not take
          an iterable), and often we don't want to mogrify strings inside other
          containers anyway.

          (If you want to process strings, implement it in your ``func``.)

        - The ``box`` container provided by this module; although mutable,
          its update is not conveniently expressible by the abc APIs.

        - The ``cons`` container from ``unpythonic.llist`` (including the
          ``llist`` linked lists). This is treated with the general tree
          strategy, so for long linked lists this will crash.

    Any value that does not match any of these is treated as an atom.

    Any **mutable** container encountered is updated in-place.

    Any **immutable** container encountered is transformed into a new copy,
    just like in ``map``.
    """
    def doit(x):
        # mutable containers
        if isinstance(x, MutableSequence):
            y = [doit(elt) for elt in x]
            if hasattr(x, "clear"):
                x.clear()  # list has this, but not guaranteed by MutableSequence
            else:
                while x:
                    x.pop()
            x.extend(y)
            return x
        elif isinstance(x, MutableSet):
            y = {doit(elt) for elt in x}
            x.clear()
            if hasattr(x, "update"):
                x.update(y)  # set has this, but not guaranteed by MutableSet
            else:
                for elt in y:
                    x.add(elt)
            return x
        elif isinstance(x, MutableMapping):
            y = {k: doit(v) for k, v in x.items()}
            x.clear()
            x.update(y)
            return x
        elif isinstance(x, box):
            x.x = doit(x.x)  # unfortunate attr name :)
            return x
        # immutable containers
        elif isinstance(x, cons):
            return cons(doit(x.car), doit(x.cdr))
        elif isinstance(x, Mapping):
            ctor = type(x)
            return ctor({k: doit(v) for k, v in x.items()})
        elif isinstance(x, Sequence) and not isinstance(x, (str, bytes, range)):
            # namedtuple support (nonstandard constructor for a Sequence!)
            cls = type(x)
            ctor = cls._make if hasattr(cls, "_make") else cls
            return ctor(doit(elt) for elt in x)
        elif isinstance(x, Set):
            ctor = type(x)
            return ctor({doit(elt) for elt in x})
        return func(x)  # atom
    return doit(container)

# -----------------------------------------------------------------------------

class box:
    """Minimalistic, mutable single-item container à la Racket.

    Motivation::

        x = 17
        def f(x):
            x = 23  # no!
        f(x)
        print(x)  # still 17

    Solution - box it, to keep the actual data in an attribute::

        b = box(17)
        def f(b):
            b.x = 23  # yes!
        f(b)
        print(b.x)  # 23

    (It's called ``x`` and not ``value`` to minimize the number of additional
    keystrokes needed.)

    In terms of ``collections.abc``, a ``box`` is a ``Container``, ``Iterable``
    and ``Sized``. A box is **not** hashable, because it is a mutable container.

    Additionally, ``box`` supports equality testing with ``==`` and ``!=``.
    A box is considered equal to the item it contains, and two boxes with
    items that compare equal are considered equal.

    Iterating over the box returns the item and then stops iteration.

    The length of a ``box`` is always 1; even if ``x is None``, the box still
    has the empty slot. (Or in other words, ``None`` in a box is just a data
    value like any other.)

    **Disclaimer**: maybe silly. The standard pythonic solutions are to box
    with a ``list`` (then trying to remember it represents a box, not a list),
    or use the ``nonlocal`` or ``global`` statements if lexically appropriate
    for the particular situation. This class just makes the programmer's intent
    more explicit.
    """
    def __init__(self, x=None):
        self.x = x
    def __repr__(self):
        return "box({})".format(repr(self.x))
    def __contains__(self, x):
        return self.x == x
    def __iter__(self):
        return (x for x in (self.x,))
    def __len__(self):
        return 1
    def __eq__(self, other):
        if other is self:
            return True
        if isinstance(other, box):
            other = other.x
        return self.x == other

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
        if other is self:
            return True
        other = other._data if isinstance(other, frozendict) else other
        return self._data.__eq__(other)

# Register virtual ABCs for our collections (like the builtins have).
#
# https://stackoverflow.com/questions/42781267/is-there-a-pythonics-way-to-distinguish-sequences-objects-like-tuple-and-list
# https://docs.python.org/3/library/abc.html#abc.ABCMeta.register
# Further reading: https://stackoverflow.com/questions/40764347/python-subclasscheck-subclasshook
for abscls in get_abcs(dict) - {MutableMapping} | {Hashable}:
    abscls.register(frozendict)
for abscls in (Container, Iterable, Sized):
    abscls.register(box)
del abscls  # namespace cleanup

# -----------------------------------------------------------------------------

class SequenceViewIterator:  # essentially this islices manually (also backwards).
    def __init__(self, theview):
        self.view = theview
        self._reset()
    def __iter__(self):
        self._reset()
        return self
    def __next__(self):
        j = self.j
        if self.outside(j, self.stop):
            raise StopIteration()
        self.j += self.step
        return self.view.seq[j]
    def _reset(self):
        self.start, self.stop, self.step = _canonize_slice(self.view.slice, len(self.view.seq))
        self.outside = ge if self.step > 0 else le
        self.j = self.start

class SequenceView(Sequence):
    """Writable view into a sequence.

    Supports slicing (also recursively, i.e. can be sliced again).

    Does **not** support ``append``, ``extend``, ``pop``, ``remove`` or
    ``__iadd__``. But we store slice specs, not actual indices, so this
    works also if the underlying sequence itself undergoes length changes.

    **Not** hashable, since the whole point is a live view to input that may
    change at any time. (Perhaps, indeed, by writing into the view, just like
    for NumPy arrays.)

    Examples::

        lst = list(range(10))
        v = SequenceView(lst, slice(None, None, 2))
        assert v == [0, 2, 4, 6, 8]
        v2 = v[1:-1]
        assert v2 == [2, 4, 6]
        v2[1:] = (10, 20)
        assert lst == [0, 1, 2, 3, 10, 5, 20, 7, 8, 9]

        lst[2] = 42
        assert v == [0, 42, 10, 20, 8]
        assert v2 == [42, 10, 20]

        lst = list(range(5))
        v = SequenceView(lst, slice(2, None))
        assert v == [2, 3, 4]
        lst.append(5)
        assert v == [2, 3, 4, 5]
        lst.insert(0, 42)
        assert v == [1, 2, 3, 4, 5]
        assert lst == [42, 0, 1, 2, 3, 4, 5]

    Slicing a view returns a new view. Slicing anything else will copy, because
    Python does, before we get control. To slice lazily, pass a ``slice`` object
    into the ``SequenceView`` constructor.

    The view can be (somewhat) efficiently iterated over. Iteration assumes
    that the underlying sequence does not change during the iteration.

    Getting/setting an item (subscripting) applies the slice spec to the current
    state of the underlying sequence during each access, so it can be slow.
    Setting a slice creates a view for that slice, and uses it to update the
    items individually.

    Core idea based on StackOverflow answer by Mathieu Caroff (2018):

        http://stackoverflow.com/q/3485475/can-i-create-a-view-on-a-python-list
    """
    def __init__(self, sequence, s=None):
        """If s is None, view the whole input. If s is a slice, view that slice."""
        if s is None:
            s = slice(None, None, None)
        self.seq = sequence
        self.slice = s
    def __iter__(self):
        return SequenceViewIterator(self)
    def __len__(self):
        start, stop, step = _canonize_slice(self.slice, len(self.seq))
        return ceil((stop - start) / step)
    def __getitem__(self, k):
        if isinstance(k, slice):
            if k == slice(None, None, None):  # v[:]
                return self
            return SequenceView(self, k)
        elif isinstance(k, tuple):
            raise TypeError("multidimensional subscripting not supported; got '{}'".format(k))
        else:
            start, stop, step = _canonize_slice(self.slice, len(self.seq))
            outside = ge if step > 0 else le
            idx = start + k*step
            if outside(idx, stop):
                raise IndexError()
            return self.seq[idx]
    def __setitem__(self, k, v):
        if isinstance(k, slice):
            view = self if k == slice(None, None, None) else SequenceView(self, k)
            for j, item in enumerate(v):
                view[j] = item
        elif isinstance(k, tuple):
            raise TypeError("multidimensional subscripting not supported; got '{}'".format(k))
        else:
            start, stop, step = _canonize_slice(self.slice, len(self.seq))
            outside = ge if step > 0 else le
            idx = start + k*step
            if outside(idx, stop):
                raise IndexError()
            self.seq[idx] = v
    def reverse(self):
        self[::-1] = [x for x in self]

    def _lowlevel_repr(self):
        r = self.seq
        while type(r) is SequenceView:
            r = r.seq
        cls = type(r)
        ctor = cls._make if hasattr(cls, "_make") else cls
        return ctor(x for x in self)
    def __str__(self):
        return str(self._lowlevel_repr())
    def __repr__(self):
        return "SequenceView({!r})".format(self._lowlevel_repr())

    def __eq__(self, other):
        if other is self:
            return True
        if len(self) != len(other):
            return False
        for v, w in zip(self, other):
            if v != w:
                return False
        return True

# -----------------------------------------------------------------------------

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
                # TODO: Would be nice to raise IndexError, but the genexpr in
                # unpythonic.fup.fupdate catches that, hiding the error.
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
