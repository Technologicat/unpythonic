# -*- coding: utf-8 -*-
"""The Reader monad — a read-only shared environment.

A ``Reader e a`` wraps a function ``e -> a``, where ``e`` is some
environment (configuration, dependency-injection context, etc.). Binding
threads a single environment ``e`` through the chain; each sub-computation
can ``ask()`` for the environment and do something with it.

Does **not** inherit from ``LiftableMonad`` — the teaching code leaves
``Reader.lift`` unimplemented, and there's no canonical shape for it.

Based on:
  - https://wiki.haskell.org/Monads_as_containers
  - https://www.mjoldfield.com/atelier/2014/08/monads-reader.html
"""

__all__ = ["Reader"]

from collections.abc import Callable
from typing import Any

from .abc import Monad


class Reader(Monad):
    """The Reader monad. Wraps a function ``e -> a``.

    Usage::

        from unpythonic.monads import Reader

        # A config-reading chain.
        config = {"multiplier": 3, "offset": 10}

        chain = (Reader.asks(lambda e: e["multiplier"])
                 >> (lambda m: Reader.asks(lambda e: e["offset"])
                 >> (lambda o: Reader.unit(m * 5 + o))))

        result = chain.run(config)
        # result == 25
    """

    def __init__(self, f: Callable) -> None:
        """Wrap a reader function ``f: e -> a``."""
        if not callable(f):
            raise TypeError(f"Expected a callable e -> a, got {f!r}")
        self.r = f

    @classmethod
    def unit(cls, x: Any) -> "Reader":
        """Unit: ``a -> Reader e a``. Ignores the environment."""
        return cls(lambda _: x)

    def run(self, env: Any) -> Any:
        """Run the reader against an environment ``env: e``. Returns ``a``."""
        return self.r(env)

    @classmethod
    def ask(cls) -> "Reader":
        """Yield the environment itself as the data value. ``-> Reader e e``."""
        return cls(lambda env: env)

    @classmethod
    def asks(cls, f: Callable) -> "Reader":
        """Apply ``f: e -> a`` to the environment; yield ``a`` as data."""
        return cls.ask() >> (lambda env: cls.unit(f(env)))

    def local(self, f: Callable) -> "Reader":
        """Run this computation in an ``f``-modified environment. ``f: e -> e``."""
        return self.__class__(lambda env: self.run(f(env)))

    def fmap(self, f: Callable) -> "Reader":
        """``fmap: Reader e a -> (a -> b) -> Reader e b``"""
        cls = self.__class__
        return cls(lambda env: f(self.run(env)))

    def join(self) -> "Reader":
        """``join: Reader e (Reader e a) -> Reader e a``

        Given a reader that yields another reader, run the outer reader to
        get the inner, then run the inner with the same environment.
        """
        cls = self.__class__
        return cls(lambda env: self.run(env).run(env))

    def __repr__(self) -> str:  # pragma: no cover
        return f"{self.__class__.__name__}({self.r!r})"
