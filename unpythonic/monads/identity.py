# -*- coding: utf-8 -*-
"""The identity monad.

Cf. the identity function. This is a no-op — just regular function
composition dressed as a monad. Its value is pedagogical: it shows the
monad structure in its simplest form, and serves as a sanity reference
when building other monads.
"""

__all__ = ["Identity"]

from collections.abc import Callable
from typing import Any

from .abc import LiftableMonad


class Identity(LiftableMonad):
    """The identity monad.

    Binding through ``Identity`` is the same as ordinary function
    composition: ``Identity(x) >> f  ==  f(x)`` (where ``f: a -> M b``).

    Usage::

        from unpythonic.monads import Identity

        result = Identity(2) >> (lambda x: Identity(x + 1))
        # result == Identity(3)
    """

    def __init__(self, x: Any) -> None:
        """Unit: wrap a plain value ``x: a`` into ``Identity a``."""
        self.x = x

    def fmap(self, f: Callable) -> "Identity":
        """``fmap: Identity a -> (a -> b) -> Identity b``"""
        cls = self.__class__
        return cls(f(self.x))

    def join(self) -> "Identity":
        """``join: Identity (Identity a) -> Identity a``"""
        cls = self.__class__
        if not isinstance(self.x, cls):
            raise TypeError(f"Expected a nested {cls.__name__}, got {type(self.x)} with data {self.x!r}")
        return self.x

    def __eq__(self, other: Any) -> bool:
        if other is self:
            return True
        if not isinstance(other, Identity):
            return NotImplemented
        return self.x == other.x

    def __hash__(self) -> int:
        return hash((Identity, self.x))

    def __repr__(self) -> str:  # pragma: no cover
        return f"{self.__class__.__name__}({self.x!r})"
