# -*- coding: utf-8 -*-
"""The List monad — multivalued computations.

One of the most genuinely useful monads in Python. Binding through a
``List`` is essentially ``flatMap``: each value in the list becomes a
sub-computation that produces its own list of results, and all the
sub-results are concatenated into a single flat list.

The classical motivating example is McCarthy's *amb* operator
(non-deterministic choice) — expressed here as combining ``List``
monads in a do-notation.

This module replaces the implementation that previously lived as
``MonadicList`` in ``unpythonic.amb``. ``amb.MonadicList`` is kept as
a deprecated alias — see ``amb.py`` for the alias and the 3.0.0 removal
note.

**Constructor style**. The varargs form ``List(1, 2, 3)`` is primary
because it makes monadic unit the class itself: ``unit x = List(x)``
(singleton list). ``List.from_iterable(xs)`` is the iterable form.

**Empty lists**. The sentinel ``nil`` from ``unpythonic.llist`` is
accepted as a single-argument special case: ``List(nil)`` constructs
an empty list. This is analogous to Maybe's use of ``nil`` for
``Nothing``, and supports the ``liftm2``-style "no result" signaling
without needing a dedicated Empty singleton of our own.
"""

__all__ = ["List"]

from collections.abc import Callable, Iterable, Iterator, Sequence, Sized
from typing import Any

from ..llist import nil

from .abc import LiftableMonad


class List(LiftableMonad):
    """The list monad."""

    def __init__(self, *elts: Any) -> None:
        """Construct a ``List`` from the given elements.

        Usage::

            List()           # empty
            List(1)          # singleton  — the monadic unit
            List(1, 2, 3)    # three elements
            List(nil)        # also empty — sentinel form, convenient for
                             # liftm2-style "no result" signaling

        Use `from_iterable` to build a List from an existing iterable.
        """
        # sentinel: a single-argument call with `nil` means "empty list."
        # This is analogous to Maybe's convention (Maybe(nil) = Nothing),
        # and lets liftm2/3-style constructions produce empty results
        # without needing a separate Empty singleton of our own.
        if len(elts) == 1 and elts[0] is nil:
            self.x: tuple = ()
        else:
            self.x = elts

    def fmap(self, f: Callable) -> "List":
        """``fmap: List a -> (a -> b) -> List b``

        Applies ``f`` to each element; result is a list of the same length.
        """
        cls = self.__class__
        return cls.from_iterable(f(elt) for elt in self.x)

    def join(self) -> "List":
        """``join: List (List a) -> List a``

        Concatenates a list of lists into a single flat list.
        """
        cls = self.__class__
        if not all(isinstance(elt, cls) for elt in self.x):
            raise TypeError(f"Expected a nested {cls.__name__}, got {self.x!r}")
        return cls.from_iterable(elt for sublist in self.x for elt in sublist)

    @classmethod
    def guard(cls, b: Any) -> "List":
        """Turn a boolean into a pass/short-circuit token for list monad filtering.

        ``b`` truthy → singleton dummy list (continues the branch);
        ``b`` falsy → empty list (short-circuits this branch). Pair with
        ``.then`` to yield the real result on success.
        """
        if b:
            return cls(True)  # non-empty; value isn't used
        return cls()  # empty — short-circuits this branch

    @classmethod
    def from_iterable(cls, iterable: Iterable) -> "List":
        """Construct a ``List`` from an existing iterable. Eager."""
        # avoid the varargs special-case for single-nil by constructing directly
        instance = cls.__new__(cls)
        instance.x = tuple(iterable)
        return instance

    # `unpythonic.collections.mogrify` uses `cls._make(iterable)` when available
    # to reconstruct sequence-like containers element-by-element (matching the
    # namedtuple convention). Without this, mogrify would fall back to
    # `cls(iterable)` = varargs, which packs the whole iterable as a single
    # element. This hook preserves correct behavior under ``lazify`` and other
    # places that recursively rebuild containers.
    _make = from_iterable

    def copy(self) -> "List":
        """Return a shallow copy of this list."""
        return self.__class__.from_iterable(self.x)

    # Sequence ABC interface — registered below.
    def __iter__(self) -> Iterator:
        return iter(self.x)

    def __len__(self) -> int:
        return len(self.x)

    def __getitem__(self, i: int) -> Any:
        return self.x[i]

    def __reversed__(self) -> Iterator:
        return reversed(self.x)

    def __contains__(self, value: Any) -> bool:
        return value in self.x

    def index(self, value: Any) -> int:
        return self.x.index(value)

    def count(self, value: Any) -> int:
        return self.x.count(value)

    def __eq__(self, other: Any) -> bool:
        if other is self:
            return True
        if isinstance(other, List):
            return self.x == other.x
        # Accept comparison against plain sequences for convenience.
        try:
            return len(self) == len(other) and all(a == b for a, b in zip(self.x, other))
        except TypeError:
            return NotImplemented

    def __hash__(self) -> int:
        return hash((List, self.x))

    def __add__(self, other: "List") -> "List":
        """Concatenation of Lists."""
        if not isinstance(other, List):
            raise TypeError(f"Expected a List, got {type(other)} with value {other!r}")
        return self.__class__.from_iterable(self.x + other.x)

    def __repr__(self) -> str:  # pragma: no cover
        return f"{self.__class__.__name__}{self.x}"


# Register as a virtual subclass of the Sequence ABCs — matches the old
# MonadicList behavior so `isinstance(List(...), Sequence)` is True.
for _abscls in (Iterable, Sized, Sequence):
    _abscls.register(List)
del _abscls
