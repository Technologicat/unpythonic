# -*- coding: utf-8 -*-
"""The Maybe monad.

Sketch of how to implement an exception system in pure FP. Not really
needed in Python for that purpose — Python has real exceptions — but a
clean informative example of a short-circuiting monad, and occasionally
handy in its own right when you want to thread "maybe a value, maybe
nothing" through a pipeline without crufting up the happy path with
explicit None checks.

**Future improvement**: a proper Maybe in Haskell is an ADT (algebraic
data type) with two data constructors, ``Just x`` and ``Nothing``. We
could use mcpyrate (syntactic macros) together with ``@generic``
(multiple-dispatch) to approximate that shape — case classes ``Just``
and ``Nothing`` sharing a ``Maybe`` supertype, with pattern matching.
Not done here; the in-band encoding below is the direct port of the
teaching code.

**Conventions** (no user-facing ``Just``/``Nothing`` wrapper classes —
just ``Maybe(value)``):

- ``Maybe(x)`` for ``x is not nil`` wraps a present value.
- ``Maybe(nil)`` represents absence (``nil`` from ``unpythonic.llist``
  is unpythonic's project-wide "nothing" sentinel, chosen to avoid
  proliferating null singletons).

Trade-off: This encoding cannot wrap ``nil`` itself as a present value.
In all other cases this yields better UX vs. demanding a ``Some(...)``
wrapper per value.
"""

__all__ = ["Maybe"]

from collections.abc import Callable
from typing import Any

from ..llist import nil

from .abc import LiftableMonad


class Maybe(LiftableMonad):
    """The Maybe monad. ``Maybe(x)`` is ``Just x``; ``Maybe(nil)`` is ``Nothing``.

    Binding through ``Nothing`` short-circuits the rest of the chain::

        from unpythonic.llist import nil
        from unpythonic.monads import Maybe

        # happy path: one bind at a time walks the chain
        result = Maybe(10) >> (lambda x: Maybe(x + 1))
        # result == Maybe(11)

        # short-circuit: the remaining lambdas are never called
        result = Maybe(nil) >> (lambda x: Maybe(x + 1))
        # result == Maybe(nil)
    """

    def __init__(self, x: Any) -> None:
        """Unit: wrap ``x: a`` into ``Maybe a``.

        Pass ``nil`` (from ``unpythonic.llist``) to construct ``Nothing``.
        """
        self.x = x

    def fmap(self, f: Callable) -> "Maybe":
        """``fmap: Maybe a -> (a -> b) -> Maybe b``. Preserves ``Nothing``."""
        if self.x is nil:
            return self
        cls = self.__class__
        return cls(f(self.x))

    def join(self) -> "Maybe":
        """``join: Maybe (Maybe a) -> Maybe a``. Preserves ``Nothing``."""
        if self.x is nil:
            return self
        cls = self.__class__
        if not isinstance(self.x, cls):
            raise TypeError(f"Expected a nested {cls.__name__}, got {type(self.x)} with data {self.x!r}")
        return self.x

    @classmethod
    def guard(cls, b: Any) -> "Maybe":
        """Turn a boolean into a pass/short-circuit token.

        ``guard: bool -> Maybe b``

        When ``b`` is truthy, returns a dummy ``Just``; when falsy, returns
        ``Nothing``. Typical use: ``Maybe(x) >> (lambda v: Maybe.guard(v > 0).then(Maybe(v)))``
        — the ``.then`` discards the guard's dummy and yields the value on
        success, ``Nothing`` on failure.
        """
        if b:
            return cls(True)  # dummy Just; the value isn't used
        return cls(nil)  # Nothing

    def __eq__(self, other: Any) -> bool:
        if other is self:
            return True
        if not isinstance(other, Maybe):
            return NotImplemented
        # nil is a singleton; `is` comparison would also work, but == is fine too.
        return self.x == other.x

    def __hash__(self) -> int:
        return hash((Maybe, self.x))

    def __repr__(self) -> str:
        # Round-trippable: eval(repr(m)) reconstructs the Maybe (given nil is in scope).
        return f"Maybe({self.x!r})"

    def __str__(self) -> str:  # pragma: no cover
        # Haskell-flavored display for humans: "Nothing" / "Just x".
        if self.x is nil:
            return "Nothing"
        return f"Just {self.x!r}"
