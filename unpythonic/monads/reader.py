# -*- coding: utf-8 -*-
"""The Reader monad — a read-only shared environment.

**Mind-bending parts inside.**

Something between a container and a computation. On the one hand,
``Reader e a`` is essentially just the function type ``e -> a`` with a
monad API wrapped around it; on the other, like ``State``, the
environment only becomes bound when we ``.run`` the Reader — until
then, everything is just planning.

A ``Reader e a`` wraps a function ``e -> a``, where ``e`` is some
environment (configuration, dependency-injection context, etc.). Binding
threads a single environment ``e`` through the chain; each sub-computation
can ``.ask()`` for the environment and do something with it.

Does **not** inherit from ``LiftableMonad`` — the teaching code leaves
``Reader.lift`` unimplemented, and there's no canonical shape for it.

Based on:

- https://wiki.haskell.org/Monads_as_containers
- https://www.mjoldfield.com/atelier/2014/08/monads-reader.html
- https://blog.ssanj.net/posts/2014-09-23-A-Simple-Reader-Monad-Example.html
- https://stackoverflow.com/questions/14178889/what-is-the-purpose-of-the-reader-monad
"""

__all__ = ["Reader"]

from collections.abc import Callable
from typing import Any

from .abc import Monad


class Reader(Monad):
    """The Reader monad. Wraps a function ``e -> a``.

    **What bind does**: taking a computation that may read from the
    environment before producing a value of type ``a``, and a function
    from values of type ``a`` to computations that may read from the
    environment before returning a value of type ``b``, and composing
    these — yielding a computation that may read from the (shared)
    environment before returning a value of type ``b``.

    Uses the default ``Monad.__rshift__`` (``fmap . join``); no override
    needed, the generic definition fits Reader perfectly.

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
        """Wrap a reader function ``f: e -> a``.

        Essentially, ``Reader e a = (e -> a)``, with a thin monad wrapper.
        """
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
