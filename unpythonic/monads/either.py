# -*- coding: utf-8 -*-
"""The Either monad — Maybe's richer sibling.

Where ``Maybe`` says "present or absent," ``Either`` says "succeeded or
failed, and here's what failed" — it carries an error value down the
short-circuit path instead of just a ``Nothing``.

By convention, ``Right`` is the success path (pun intended: *right* also
means correct) and ``Left`` is the failure path. Binding through a
``Left`` short-circuits the rest of the chain, preserving the error::

    from unpythonic.monads import Left, Right

    result = Right(10) >> (lambda x: Right(x + 1))
    # result == Right(11)

    result = Left("boom") >> (lambda x: Right(x + 1))
    # result == Left("boom")

``Left`` and ``Right`` are sibling subclasses of ``Either``. Use
``Left`` / ``Right`` directly at the construction site; ``Either``
itself is abstract.
"""

__all__ = ["Either", "Left", "Right"]

from collections.abc import Callable
from typing import Any

from .abc import LiftableMonad


class Either(LiftableMonad):
    """Abstract base for ``Left`` and ``Right``.

    Do not instantiate directly — use ``Left(err)`` for failure and
    ``Right(val)`` for success.

    Overrides ``then`` from ``Monad`` so that ``self >> (lambda _: other)``
    accepts any ``Either`` on the RHS, not only the exact same subclass.
    That is, ``Right(1).then(Left("boom"))`` works (and returns
    ``Left("boom")``, since the right-hand side is the next step of the
    computation).
    """

    def __init__(self, value: Any) -> None:
        if type(self) is Either:
            raise TypeError("Either is abstract; use Left(err) or Right(val)")
        self.value = value

    @classmethod
    def lift(cls, f: Callable) -> Callable:
        """Lift into ``Right`` (the success path). ``Left``-lifting doesn't make sense."""
        return lambda x: Right(f(x))

    def then(self, other: "Either") -> "Either":
        if not isinstance(other, Either):
            raise TypeError(f"Expected an Either, got {type(other)} with value {other!r}")
        return self >> (lambda _: other)

    @classmethod
    def guard(cls, b: Any, err: Any = "guard failed") -> "Either":
        """Turn a boolean into a pass/short-circuit token.

        ``b`` truthy → dummy ``Right``; falsy → ``Left(err)``. Use ``.then``
        after to replace the dummy with the real result.
        """
        if b:
            return Right(True)
        return Left(err)

    def __eq__(self, other: Any) -> bool:
        if other is self:
            return True
        if not isinstance(other, Either):
            return NotImplemented
        return type(self) is type(other) and self.value == other.value

    def __hash__(self) -> int:
        return hash((type(self), self.value))

    def __repr__(self) -> str:  # pragma: no cover
        return f"{type(self).__name__}({self.value!r})"


class Left(Either):
    """The failure path. Binding through a ``Left`` short-circuits."""

    def fmap(self, f: Callable) -> "Either":
        # Short-circuit: preserve the error; don't apply f.
        return self

    def join(self) -> "Either":
        # Short-circuit monad, same convention as ``Maybe(nil).join()``:
        # there's no nested monad to unwrap (the payload is an error value,
        # not an Either), and even in Haskell's typed form the Either monad
        # instance has ``join (Left e) = Left e``. Return ``self`` so bind
        # through Left stays Left.
        return self


class Right(Either):
    """The success path. Binding through a ``Right`` proceeds."""

    def fmap(self, f: Callable) -> "Either":
        return Right(f(self.value))

    def join(self) -> "Either":
        if not isinstance(self.value, Either):
            raise TypeError(f"Expected a nested Either, got {type(self.value)} with data {self.value!r}")
        return self.value
