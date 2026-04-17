# -*- coding: utf-8 -*-
"""Monad base classes.

Two-level split:

- ``Monad``: the base class all monads inherit from. Requires ``__init__``
  (unit), ``fmap``, ``join``. Provides default implementations of
  ``__rshift__`` (bind) and ``then`` (sequence) based on ``fmap`` + ``join``.

- ``LiftableMonad(Monad)``: adds ``lift``, i.e. ``(a -> b) -> (a -> M b)``.
  Used by monads where lift is well-defined in the usual "compose with unit"
  sense (``Identity``, ``Maybe``, ``Either``, ``List``, ``Writer``). ``State``
  and ``Reader`` inherit from ``Monad`` directly — their ``lift`` is not
  well-defined in that shape.

Following unpythonic's duck-first philosophy (see ``unpythonic.slicing.Sliced``
as the model), abstract methods are marked with ``@abstractmethod`` as an
intent marker for documentation; the classes are not strict ABCs. Enforcement
is soft: the decorator tells the reader what to implement, but instantiating
an incomplete subclass will not fail until an unimplemented method is called.
"""

__all__ = ["Monad", "LiftableMonad"]

from abc import abstractmethod
from collections.abc import Callable


class Monad:
    """Base class for monads.

    A **must-override** method is tagged ``@abstractmethod`` and the docstring
    says so. Other methods are concrete; override only for efficiency or if a
    particular monad genuinely needs different semantics.

    Must override:

    - ``__init__`` (the unit operation): wrap a plain value into a monadic one.
      Type: ``unit: a -> M a``. Not tagged ``@abstractmethod`` because every
      Python class has its own ``__init__``; the contract is by convention.

    - ``fmap(self, f)``: apply ``f: a -> b`` inside the monad, returning
      ``M b``. Type: ``fmap: M a -> (a -> b) -> M b``.

    - ``join(self)``: flatten a nested monadic value.
      Type: ``join: M (M a) -> M a``.

    Provided (override only if needed):

    - ``__rshift__(self, f)`` (bind, Haskell ``>>=``): default
      ``bind ma f = join (fmap f ma)``. Override e.g. for ``Writer``, which
      bypasses ``fmap`` to avoid double-logging.

    - ``then(self, other)`` (sequence, Haskell ``>>``): default
      ``self >> (lambda _: other)``. Rarely worth overriding.

    **Python note**. The usual Haskell bind symbol is ``>>=``, but in Python
    that maps to ``__irshift__``, which is an in-place operation and does not
    chain. We use ``>>`` (``__rshift__``) instead, consistent with the
    teaching-code monads this subpackage is ported from.
    """

    @abstractmethod
    def fmap(self, f: Callable) -> "Monad":
        """The map operator. **Must override.**

        ``fmap: M a -> (a -> b) -> M b``

        Apply the regular function ``f: a -> b`` to the value(s) inside this
        monadic container, returning a new monadic value of the same type.
        """
        ...

    @abstractmethod
    def join(self) -> "Monad":
        """The join operator. **Must override.**

        ``join: M (M a) -> M a``

        Flatten a doubly-wrapped monadic value into a singly-wrapped one.
        """
        ...

    def __rshift__(self, f: Callable) -> "Monad":
        """Monadic bind (Haskell ``>>=``, spelled ``>>`` in Python).

        ``bind: M a -> (a -> M b) -> M b``

        Default: ``bind ma f = join (fmap f ma)``. Override for efficiency
        (e.g. ``Writer`` implements bind directly to avoid double-logging
        via ``fmap``).
        """
        return self.fmap(f).join()

    def then(self, other: "Monad") -> "Monad":
        """Monadic sequence (Haskell ``>>``, spelled ``.then`` in Python).

        ``then: M a -> M b -> M b``

        Like bind, but discarding the input value; yields ``other`` regardless
        of what's inside ``self`` (subject to the monad's short-circuit rules,
        e.g. ``Maybe(Empty).then(x) is Maybe(Empty)``).
        """
        cls = self.__class__
        if not isinstance(other, cls):
            raise TypeError(f"Expected a {cls.__name__}, got {type(other)} with value {other!r}")
        return self >> (lambda _: other)


class LiftableMonad(Monad):
    """A monad with a well-defined ``lift`` operation.

    Adds ``lift``, which promotes a regular function ``f: a -> b`` into a
    monad-producing one ``a -> M b``. Default implementation: compose with
    unit, i.e. ``lift f = lambda x: cls(f(x))``.

    Inherits from ``Monad``; the usual ``fmap``/``join``/unit contract still
    applies.

    ``State`` and ``Reader`` deliberately do **not** inherit from this class —
    their ``lift`` is not well-defined in the compose-with-unit sense. Use
    ``Monad`` directly for those.
    """

    @classmethod
    def lift(cls, f: Callable) -> Callable:
        """Lift a regular function into a monad-producing one.

        ``lift: (a -> b) -> (a -> M b)``

        Default: ``lift f = lambda x: cls(f(x))``, i.e. compose with unit.
        Override if the monad needs a different construction (e.g. ``Writer``
        produces a log entry as part of the lift).
        """
        return lambda x: cls(f(x))
