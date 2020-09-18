# -*- coding: utf-8 -*-
"""Additional containers and container utilities."""

__all__ = ["box", "ThreadLocalBox", "unbox", "Some", "Shim",
           "frozendict", "roview", "view", "ShadowedSequence",
           "mogrify",
           "get_abcs", "in_slice", "index_in_slice",
           "SequenceView", "MutableSequenceView"]  # ABCs

from functools import wraps
from itertools import repeat
from abc import abstractmethod
from collections import abc
from collections.abc import (Container, Iterable, Hashable, Sized,
                             Sequence, Mapping, Set,
                             MutableSequence, MutableMapping, MutableSet,
                             MappingView)
from inspect import isclass
from operator import lt, le, ge, gt
import threading

from .llist import cons, Nil
from .misc import getattrrec
from .env import env
from .dynassign import _Dyn

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
          strategy. Any ``nil`` is passed through as-is.

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
            else:  # pragma: no cover, no realistic `MutableSequence` that is missing `clear`?
                while x:
                    x.pop()
            x.extend(y)
            return x
        elif isinstance(x, MutableSequenceView):  # our own cat food
            y = [doit(elt) for elt in x]
            x[:] = y
            return x
        elif isinstance(x, MutableSet):
            y = {doit(elt) for elt in x}
            x.clear()
            if hasattr(x, "update"):
                x.update(y)  # set has this, but not guaranteed by MutableSet
            else:  # pragma: no cover, no realistic `MutableSet` that is missing `update`?
                for elt in y:
                    x.add(elt)
            return x
        # env provides the MutableMapping API, but shouldn't get the general treatment here.
        # (This is important for the lazify macro.)
        elif isinstance(x, MutableMapping) and not isinstance(x, env):
            y = {k: doit(v) for k, v in x.items()}
            x.clear()
            x.update(y)
            return x
        elif isinstance(x, (box, ThreadLocalBox)):
            x.set(doit(x.get()))
            return x
        # immutable containers
        elif isinstance(x, Nil):  # for unpythonic.llist.ll() support
            return x
        elif isinstance(x, cons):
            return cons(doit(x.car), doit(x.cdr))
        elif isinstance(x, Some):
            return Some(doit(x.get()))
        elif isinstance(x, SequenceView):  # our own cat food
            ctor = type(getattrrec(x, "seq"))  # de-onionize
            return ctor(doit(elt) for elt in x)
        # dict_items and similar cannot be instantiated, and they support only iteration,
        # not in-place modification, so return a regular set
        # (this turns up in "with curry" blocks using somedict.items() as a function argument,
        #  due to the maybe_force_args() in curry)
        elif isinstance(x, MappingView):
            return {doit(elt) for elt in x}
        # env and dyn provide the Mapping API, but shouldn't get the general Mapping treatment here.
        # (This is important for the curry and lazify macros.)
        elif isinstance(x, Mapping) and not isinstance(x, (env, _Dyn)):
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
            b << 23  # yes!
        f(b)
        print(unbox(b))  # 23

    This is the recommended unpythonic syntax. If you like OOP, you can
    `b.set(23)` instead of `b << 23`, and `b.get()` instead of `unbox(b)`.

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
    def __repr__(self):  # pragma: no cover
        return "box({})".format(repr(self.x))
    def __contains__(self, x):
        return self.x == x
    def __iter__(self):
        return (x for x in (self.x,))
    def __len__(self):
        return 1
    def __eq__(self, other):
        return other == self.x
    def set(self, x):
        """Store a new value in the box, replacing the old one.

        As a convenience, returns the new value.

        Since a function call is an expression, you can use this form
        also in a lambda, or indeed in any expression position.
        """
        self.x = x
        return x
    def __lshift__(self, x):
        """Syntactic sugar for storing a new value.

        `b << 42` is the same as `b.set(42)`.

        (Note that for `env`, the `<<` operator returns the *environment* so it
        can be chained to make several assignments, but that doesn't make sense
        for a `box`, so we just return the new value.)
        """
        return self.set(x)
    def get(self):
        """Return the value currently in the box.

        The syntactic sugar for `b.get()` is `unbox(b)`.
        """
        return self.x

# We re-implement instead of making `box` use an `env` as a place
# so that the thread-locality feature is pay-as-you-go (no loss in
# performance for the regular, non-thread-local `box`.)
class ThreadLocalBox(box):
    """Like box, but the store is thread-local.

    The initially provided `x` is used as the default object, which serves as
    the initial contents of the box in all threads. (Note what this implies if
    that `x` happens to be mutable.)
    """
    def __init__(self, x=None):
        self.storage = threading.local()
        self._default = x
    def __repr__(self):  # pragma: no cover
        """**WARNING**: the repr shows only the content seen by the current thread."""
        return "ThreadLocalBox({})".format(repr(self.get()))
    def __contains__(self, x):
        return self.get() == x
    def __iter__(self):
        return (x for x in (self.get(),))
    def __eq__(self, other):
        return other == self.get()
    def set(self, x):
        self.storage.x = x
        return x
    def __lshift__(self, x):
        return self.set(x)
    def get(self):
        if hasattr(self.storage, "x"):  # default overridden in this thread?
            return self.storage.x
        return self._default
    def setdefault(self, x):
        """Change the default object."""
        self._default = x
    def getdefault(self):
        """Get the default object."""
        return self._default
    def clear(self):
        """Remove the value in the box in this thread, thus unshadowing the default."""
        if hasattr(self.storage, "x"):
            del self.storage.x

class Some:
    """Explicitly represent thing-ness as opposed to nothingness.

    Useful for optional fields. Using a `Some` container makes it possible to
    tell apart the presence of a `None` value from the absence of a value::

        x = Some(42)    # we have a value, it's `42`
        x = Some(None)  # we have a value, it's `None`
        x = None        # we don't have a value

    In a way, `Some` is a relative of `box`: it's an **immutable** single-item
    container. It supports `.get` and `unbox`, but no `<<` or `.set`.
    """
    def __init__(self, x=None):
        self.x = x
    def __repr__(self):  # pragma: no cover
        return "Some({})".format(repr(self.x))
    def __contains__(self, x):
        return self.x == x
    def __iter__(self):
        return (x for x in (self.x,))
    def __len__(self):
        return 1
    def __eq__(self, other):
        return other == self.x
    def get(self):
        """Return the value currently in the `Some`.

        The syntactic sugar for `b.get()` is `unbox(b)`.
        """
        return self.x

def unbox(b):
    """Return the value from inside the box b.

    Syntactic sugar for `b.get()`.

    If `b` is not a `box` (or `ThreadLocalBox` or `Some`), raises `TypeError`.
    """
    if not isinstance(b, (box, Some)):
        raise TypeError("Expected box, got {} with value {}".format(type(b), repr(b)))
    return b.get()

class Shim:
    """Attribute access proxy.

    Hold a target object inside a box. When an attribute of the shim
    is accessed (whether to get or set it), redirect that access to
    the object that is currently inside the box.

    The target may be replaced at any time, simply by sending a new value
    into the box instance you gave to the `Shim` constructor.

    Another use case is to combo with `ThreadLocalBox`, e.g. to redirect
    stdin/stdout only when used from some specific threads.

    Since deep down, attribute access is the whole point of objects, `Shim` is
    essentially a transparent object proxy. (For example, a method call is an
    attribute read (via a descriptor), followed by a function call.)

    thebox:   a `box` instance that holds the target object. The box must
              be created manually, to maximize composability: a `box` or
              `ThreadLocalBox` can be chosen as appropriate for the
              particular use case.

    fallback: optional; a fallback object. Either any object (not boxed),
              or a `box` instance (in case you want to replace the fallback
              later).

              **For attribute reads** (i.e. `__getattr__`), if the object in
              the box does not have the requested attribute, `Shim` will try
              to get it from the fallback. If `fallback` is boxed, the
              attribute read takes place on the object in the box. If it is
              not boxed, the attribute read takes place directly on `fallback`.

              Any **attribute writes** (i.e. `__setattr__`, binding or rebinding
              an attribute) always take place on the primary target object
              in `thebox`.

    If you need to chain fallbacks, this can be done with `foldr`::

        boxes = [box(obj) for obj in ...]
        *others, final_fallback = boxes
        s = foldr(Shim, final_fallback, others)

    Here `Shim(box, fallback)` is foldr's `op(elt, acc)`.
    """
    def __init__(self, thebox, fallback=None):
        if not isinstance(thebox, box):
            raise TypeError("Expected box, got {} with value {}".format(type(thebox), repr(thebox)))
        self._shim_box = thebox
        self._shim_fallback = fallback
    def __getattr__(self, k):
        thing = unbox(self._shim_box)
        fallback = self._shim_fallback
        if not fallback or hasattr(thing, k):
            return getattr(thing, k)
        # fallback and not hasattr(thing, k)
        otherthing = unbox(fallback) if isinstance(fallback, box) else fallback
        return getattr(otherthing, k)
    def __setattr__(self, k, v):
        if k in ("_shim_box", "_shim_fallback"):
            return super().__setattr__(k, v)
        thing = unbox(self._shim_box)
        return setattr(thing, k, v)

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
    instance.

    In terms of ``collections.abc``, a ``frozendict`` is a ``Container``,
    ``Hashable``, ``Iterable``, ``Mapping`` and ``Sized``.

    Just like for ``dict``, the abstract superclasses are virtual; they are
    detected by the built-ins ``issubclass`` and ``isinstance``, but they are
    not part of the MRO.
    """
    # Make the empty frozendict() a singleton, but allow invoking the constructor
    # multiple times, always returning the same instance.
    def __new__(cls, *ms, **bindings):
        if not ms and not bindings:
            global _the_empty_frozendict
            if _the_empty_frozendict is None:
                _the_empty_frozendict = super().__new__(cls)
            return _the_empty_frozendict
        return super().__new__(cls)  # object() takes no args, but we need to see them

    # Pickling support.
    # https://github.com/Technologicat/unpythonic/issues/55
    # https://docs.python.org/3/library/pickle.html#object.__getnewargs_ex__
    # https://docs.python.org/3/library/pickle.html#object.__getnewargs__
    def __getnewargs__(self):
        if self is not _the_empty_frozendict:
            # In our case it doesn't matter what the value is, as long as there is one,
            # because `__new__` uses the *presence* of any args to know the instance is
            # nonempty, and hence an instance should actually be created instead of
            # just returning the empty singleton frozendict.
            return ("nonempty",)
        return ()

    def __init__(self, *ms, **bindings):
        """Arguments:

               ms: mappings; optional
                   If one argument is provided: the input mapping to freeze.

                   If more are provided, the second and later ones will
                   functionally update the data, in the order given.

                   Accepts any type understood by ``dict.update``.

               bindings: kwargs in the form key=value; optional
                   Essentially like the ``**F`` argument of ``dict.update``.

                   Functional updates applied at the end, after the last mapping
                   in ``ms``. Can be useful for overriding individual items.
        """
        super().__init__()
        self._data = {}
        for m in ms:
            self._data.update(m)
        self._data.update(bindings)

    @wraps(dict.__repr__)
    def __repr__(self):  # pragma: no cover
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
        return other == self._data

# Register virtual ABCs for our collections (like the builtins have).
#
# https://stackoverflow.com/questions/42781267/is-there-a-pythonics-way-to-distinguish-sequences-objects-like-tuple-and-list
# https://docs.python.org/3/library/abc.html#abc.ABCMeta.register
# Further reading: https://stackoverflow.com/questions/40764347/python-subclasscheck-subclasshook
for abscls in get_abcs(dict) - {MutableMapping} | {Hashable}:
    abscls.register(frozendict)
for abscls in (Container, Iterable, Sized):
    abscls.register(box)
    abscls.register(ThreadLocalBox)
    abscls.register(Some)
del abscls  # namespace cleanup

# -----------------------------------------------------------------------------

class SequenceView(Sequence):
    """ABC: view of a sequence.

    Provides the same API as ``collections.abc.Sequence``."""

# can't be a MutableSequence since we can't provide ``__delitem__`` and ``insert``
class MutableSequenceView(SequenceView):
    """ABC: mutable view of a sequence.

    Provides the same API as ``SequenceView``, plus ``__setitem__`` and ``reverse``.

    Unlike ``MutableSequence``, does **not** provide ``append``, ``extend``,
    ``pop``, ``remove`` or ``__iadd__``. (Use those of the underlying sequence
    instead.)

    The length of the underlying sequence **is allowed to change at any time**;
    classes that implement ``MutableSequenceView`` must account for this.
    """
    @abstractmethod
    def __setitem__(self, k, v):
        pass  # pragma: no cover
    @abstractmethod
    def reverse(self):
        pass  # pragma: no cover

# -----------------------------------------------------------------------------

class _StrReprEqMixin:
    def _lowlevel_repr(self):  # pragma: no cover
        cls = type(getattrrec(self, "seq"))  # de-onionize
        ctor = tuple if hasattr(cls, "_make") else cls  # slice of namedtuple -> tuple
        return ctor(x for x in self)
    def __str__(self):  # pragma: no cover
        return str(self._lowlevel_repr())
    def __repr__(self):  # pragma: no cover
        return "{:s}({!r})".format(self.__class__.__name__, self._lowlevel_repr())

    def __eq__(self, other):
        if other is self:
            return True
        if len(self) != len(other):
            return False
        for v1, v2 in zip(self, other):
            if v1 != v2:
                return False
        return True

class roview(SequenceView, _StrReprEqMixin):
    """Read-only live view into a sequence.

    Supports slicing (also recursively, i.e. can be sliced again).

    We store slice specs, not actual indices, so this works also if the
    underlying sequence undergoes length changes.

    **Not** hashable, since the whole point is a live view to input that
    may change at any time. However, as usual, iteration assumes that
    no inserts/deletes in the underlying sequence occur during iteration.
    (So be careful with threads.)

    The read-only cousin of ``view``. For usage examples, see ``view``; this
    behaves the same except no ``__setitem__`` or ``reverse``.

    **Notes**

    In terms of ABCs, this is an ``unpythonic.collections.SequenceView``.

    Slicing an ``roview`` or a ``view`` returns a new ``roview``. Slicing
    anything else will usually copy, because the object being sliced does,
    before we get control.

    To slice lazily, first view the sequence itself and then slice that.
    The initial no-op view is optimized away, so it won't slow down accesses.
    Alternatively, pass a ``slice`` object into the view constructor.

    The view can be efficiently iterated over.

    Getting/setting an item (subscripting) checks whether the index cache needs
    updating during each access, so it can be a bit slow. Setting a slice checks
    just once, and then updates the underlying iterable directly.

    Core idea based on StackOverflow answer by Mathieu Caroff (2018):

        http://stackoverflow.com/q/3485475/can-i-create-a-view-on-a-python-list
    """
    def __init__(self, sequence, s=None):
        """If s is None, view the whole input. If s is a slice, view that slice.

        The slice can also be specified later by subscripting with a slice
        (doing that creates a new view instance, which bypasses the original
        no-op view).
        """
        if s is None:
            s = slice(None, None, None)
        self.seq = sequence
        self.slice = s
        self._seql = None

    def __iter__(self):
        data, r = self._update_cache()
        def view_iterator():
            for j in r:
                yield data[j]
        return view_iterator()
    def __len__(self):
        _, r = self._update_cache()
        return len(r)

    def _update_cache(self):
        seql = len(self.seq)
        if seql != self._seql:
            self._seql = seql
            self._cache = self._range()
        return self._cache
    def _range(self):  # return underlying sequence, current range of all elements of self in it
        def buildr(seq):
            if not isinstance(seq, (roview, view)):
                return seq, range(len(seq))
            data, r = buildr(seq.seq)
            return data, r[seq.slice]
        return buildr(self)

    def __getitem__(self, k):
        if isinstance(k, slice):
            if k == slice(None, None, None):  # v[:]
                return self
            ctor = type(self)
            if self.slice == slice(None, None, None):  # bypass us if we're a no-op (good for subscript curry)
                return ctor(self.seq, k)
            return ctor(self, k)
        elif isinstance(k, tuple):
            raise TypeError("multidimensional subscripting not supported; got {}".format(repr(k)))
        else:
            data, r = self._update_cache()
            n = len(r)
            if k >= n or k < -n:
                raise IndexError("view index out of range")
            return data[r[k]]

class view(roview, MutableSequenceView):
    """Writable live view into a sequence.

    The writable cousin of ``roview``. Provides the same API plus ``__setitem__``
    and ``reverse``.

    Writing a scalar value into a slice broadcasts it, à la NumPy.

    In terms of ABCs, this is an ``unpythonic.collections.MutableSequenceView``.

    Examples::

        lst = list(range(10))
        v = view(lst, slice(None, None, 2))  # or view(lst)[::2]
        assert v == [0, 2, 4, 6, 8]
        v2 = v[1:-1]
        assert v2 == [2, 4, 6]
        v2[1:] = (10, 20)
        assert lst == [0, 1, 2, 3, 10, 5, 20, 7, 8, 9]

        lst[2] = 42
        assert v == [0, 42, 10, 20, 8]
        assert v2 == [42, 10, 20]

        lst = list(range(5))
        v = view(lst, slice(2, 4))  # or view(lst)[2:4]
        v[:] = 42  # scalar broadcast
        assert lst == [0, 1, 42, 42, 4]

        lst = list(range(5))
        v = view(lst, slice(2, None))  # or view(lst)[2:]
        assert v == [2, 3, 4]
        lst.append(5)
        assert v == [2, 3, 4, 5]
        lst.insert(0, 42)
        assert v == [1, 2, 3, 4, 5]
        assert lst == [42, 0, 1, 2, 3, 4, 5]
    """
    def __init__(self, sequence, s=None):
        # some fandango because MutableSequenceView is not a MutableSequence for technical reasons.
        if isinstance(sequence, SequenceView):
            if not isinstance(sequence, MutableSequenceView):
                raise TypeError("cannot create writable view into a read-only view")
        elif isinstance(sequence, Sequence) and not isinstance(sequence, MutableSequence):
            raise TypeError("cannot create writable view into a read-only sequence")
        super().__init__(sequence, s)
    def __setitem__(self, k, v):
        data, r = self._update_cache()
        if isinstance(k, slice):
            # TODO: would be nicer if we could convert a range into a slice, then just data[rk] = v.
            # TODO: The problem is that we need transformations like range(4, -1, -1) --> slice(4, None, -1)
            try:
                vs = iter(v)
            except TypeError:  # scalar broadcast à la NumPy
                vs = repeat(v)
            for j, item in zip(r[k], vs):
                data[j] = item
        elif isinstance(k, tuple):
            raise TypeError("multidimensional subscripting not supported; got {}".format(repr(k)))
        else:
            n = len(r)
            if k >= n or k < -n:
                raise IndexError("view assigment index out of range")
            data[r[k]] = v
    def reverse(self):
        self[::-1] = [x for x in self]

# -----------------------------------------------------------------------------

# Inherit from Sequence, because we want the default implementations of e.g. count, index to be found in the MRO.
class ShadowedSequence(Sequence, _StrReprEqMixin):
    """Sequence with some elements shadowed by those from another sequence.

    Or in other words, a functionally updated view of a sequence. Or somewhat
    like ``collections.ChainMap``, but for sequences.

    Essentially, ``out[k] = v[index_in_slice(k, ix)] if in_slice(k, ix) else seq[k]``,
    but doesn't actually allocate ``out``.

    ``ix`` may be integer (if ``v`` represents one item only) or slice (if ``v``
    is intended as a sequence). The default ``None`` means ``out[k] = seq[k]``
    with no shadower.
    """
    def __init__(self, seq, ix=None, v=None):
        if ix is not None and not isinstance(ix, (slice, int)):
            raise TypeError("ix: expected slice or int, got {} with value {}".format(type(ix), ix))
        self.seq = seq
        self.ix = ix
        self.v = v

    # Provide __iter__ (even though implemented using len() and __getitem__())
    # so that our __getitem__ can raise IndexError when needed, without it
    # getting caught by the genexpr in unpythonic.fup.fupdate when it builds
    # the output sequence.
    def __iter__(self):
        if self.ix is None:  # allow no-op ShadowedSequences since the repr suggests one could do that
            return iter(self.seq)
        n = len(self)
        getone = self._getone
        def ShadowedSequenceIterator():
            for j in range(n):
                yield getone(j)
        return ShadowedSequenceIterator()

    def __len__(self):
        return len(self.seq)

    def __getitem__(self, k):
        if self.ix is None:  # allow no-op ShadowedSequences since the repr suggests one could do that
            return self.seq[k]
        n = len(self)
        if isinstance(k, slice):
            cls = type(self.seq)
            ctor = tuple if hasattr(cls, "_make") else cls  # slice of namedtuple -> tuple
            return ctor(self._getone(j) for j in range(n)[k])
        elif isinstance(k, tuple):
            raise TypeError("multidimensional subscripting not supported; got {}".format(repr(k)))
        else:
            if k >= n or k < -n:
                raise IndexError("ShadowedSequence index out of range")
            return self._getone(k)

    def _getone(self, k):
        ix = self.ix
        n = len(self)
        if in_slice(k, ix, n):
            if isinstance(ix, int):
                return self.v  # just one item
            # we already know k is in ix, so skip validation for speed.
            i = _index_in_slice(k, ix, n, _validate=False)
            if i >= len(self.v):
                raise IndexError("Replacement sequence too short; attempted to access index {} with len {} (items: {})".format(i, len(self.v), self.v))
            return self.v[i]
        return self.seq[k]  # not in slice

# TODO: fix flake8 E741 ambiguous variable name "l". Here it's part of the public API, so we'll have to wait until 15.0 to change the name.
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

# TODO: fix flake8 E741 ambiguous variable name "l". Here it's part of the public API, so we'll have to wait until 15.0 to change the name.
def index_in_slice(i, s, l=None):
    """Return the index of the int i in the slice s, or None if i is not in s.

    (I.e. how-manyth item of the slice the index i is.)

    The optional sequence length ``l`` works the same as in ``in_slice``.
    """
    return _index_in_slice(i, s, l)

# efficiency: allow skipping the validation check for call sites
# that have already checked with in_slice().
def _index_in_slice(i, s, n=None, _validate=True):  # n: length of sequence being indexed
    if (not _validate) or in_slice(i, s, n):
        wrap = _make_negidx_converter(n)
        start, _, step = _canonize_slice(s, n, wrap)
        return (wrap(i) - start) // step

def _make_negidx_converter(n):  # n: length of sequence being indexed
    if n is not None:
        if not isinstance(n, int):
            raise TypeError("n must be int, got {} with value {}".format(type(n), n))
        if n <= 0:
            raise ValueError("n must be an int >= 1, got {}".format(n))
        def apply_conversion(k):
            return k % n
    else:
        def apply_conversion(k):
            raise ValueError("Need n to interpret negative indices")
    def convert(k):
        if k is not None:
            if not isinstance(k, int):
                # This is not triggered in the current code because the outer
                # layers protect against having to check here, but since the
                # `convert` function is returned to the caller, let's be
                # careful.
                raise TypeError("k must be int, got {} with value {}".format(type(k), k))  # pragma: no cover
            # Almost standard semantics for negative indices. Usually -n < k < n,
            # but here we must allow for conversion of the end position, for
            # which the last valid value is one past the end.
            if n is not None and not -n <= k <= n:
                raise IndexError("Should have -n <= k <= n, but n = {}, and k = {}".format(n, k))
            return apply_conversion(k) if k < 0 else k
    return convert

def _canonize_slice(s, n=None, wrap=None):  # convert negatives, inject defaults.
    if not isinstance(s, slice):
        # Not triggered in the current code, because this is an internal function
        # and `in_slice` already checks; but let's be careful in case this is later
        # used elsewhere. (And, it's already possible that some internal caller
        # incorrectly uses the no-check mode of the internal implementation function
        # `_index_in_slice`.)
        raise TypeError("s must be slice, got {} with value {}".format(type(s), s))  # pragma: no cover

    step = s.step if s.step is not None else +1  # no "s.step or +1"; someone may try step=0
    if step == 0:
        raise ValueError("slice step cannot be zero")  # message copied from range(5)[0:4:0]

    wrap = wrap or _make_negidx_converter(n)

    start = wrap(s.start)
    if start is None:
        if step > 0:
            start = 0
        else:
            if n is None:
                raise ValueError("Need n to determine default start for step < 0")
            start = wrap(-1)

    stop = wrap(s.stop)
    if stop is None:
        if step > 0:
            if n is None:
                raise ValueError("Need n to determine default stop for step > 0")
            stop = n
        else:
            stop = -1  # yes, really -1 to have index 0 inside the slice

    return start, stop, step
