# -*- coding: utf-8 -*-
"""Monadic helpers that don't belong to any single monad.

``liftm`` and its arity variants ``liftm2``, ``liftm3`` turn a regular
multi-argument function into a monadic one. See Haskell ``Control.Monad``
for the originals (which go up to ``liftM8``). These three cover the
common cases; if more are ever needed, the pattern is obvious.

Note the slight but important distinction between ``lift`` (on
``LiftableMonad``) and ``liftm`` here::

    lift:    f: (a -> b)            ->  lifted: (a -> M b)
    liftm:   f: (a -> r)            ->  lifted: (M a -> M r)
    liftm2:  f: ((a, b) -> r)       ->  lifted: ((M a, M b) -> M r)
    liftm3:  f: ((a, b, c) -> r)    ->  lifted: ((M a, M b, M c) -> M r)

(Type signatures: each letter stands for a type such as int, str, ....
For example, ``f: (a -> r)`` means ``f`` is a function that takes a
single input parameter of type ``a`` and returns a value of type ``r``.
``M a`` roughly means "monad containing data of type ``a``".)

Why the ``M`` in the input of ``liftm``'s result? Because in ``liftm``
the *lifted* function binds, whereas ``lift`` expects the use site to
do that.

Don't worry if this doesn't make sense at first — return to these
details once you've played with a few monad examples. The important
practical distinction: ``liftm`` takes monadic input and binds
internally; ``lift`` takes a plain value, wraps it, and hands you
something you then bind.
"""

__all__ = ["liftm", "liftm2", "liftm3"]

from collections.abc import Callable
from functools import wraps

from .abc import Monad


def liftm(M: type, f: Callable) -> Callable:
    """Lift a unary function into a monadic one.

    ``liftm: f: (a -> r)  ->  lifted: (M a -> M r)``

    Given a regular function ``f: a -> r``, produce a function that takes
    one monadic argument ``M a`` and returns ``M r``. The lifted function
    binds internally using ``>>``.

    The first parameter ``M`` (the monad type) is fixed per call site and
    changes rarely, so the signature is curry-friendly — use
    ``partial(liftm, Maybe)`` to get a Maybe-specific lifter.
    """
    @wraps(f)
    def lifted(Mx: Monad) -> Monad:
        if not isinstance(Mx, M):
            raise TypeError(f"argument: expected monad {M}, got {type(Mx)} with data {Mx!r}")
        return Mx >> (lambda x:
                      M(f(x)))
    return lifted


def liftm2(M: type, f: Callable) -> Callable:
    """Lift a binary function into a monadic one.

    ``liftm2: f: ((a, b) -> r)  ->  lifted: ((M a, M b) -> M r)``

    Like `liftm`, but for two-argument ``f``.
    """
    @wraps(f)
    def lifted(Mx: Monad, My: Monad) -> Monad:
        if not isinstance(Mx, M):
            raise TypeError(f"first argument: expected monad {M}, got {type(Mx)} with data {Mx!r}")
        if not isinstance(My, M):
            raise TypeError(f"second argument: expected monad {M}, got {type(My)} with data {My!r}")
        return Mx >> (lambda x:
               My >> (lambda y:  # noqa: E128 -- monadic style
                      M(f(x, y))))
    return lifted


def liftm3(M: type, f: Callable) -> Callable:
    """Lift a ternary function into a monadic one.

    ``liftm3: f: ((a, b, c) -> r)  ->  lifted: ((M a, M b, M c) -> M r)``

    Like `liftm`, but for three-argument ``f``.
    """
    @wraps(f)
    def lifted(Mx: Monad, My: Monad, Mz: Monad) -> Monad:
        if not isinstance(Mx, M):
            raise TypeError(f"first argument: expected monad {M}, got {type(Mx)} with data {Mx!r}")
        if not isinstance(My, M):
            raise TypeError(f"second argument: expected monad {M}, got {type(My)} with data {My!r}")
        if not isinstance(Mz, M):
            raise TypeError(f"third argument: expected monad {M}, got {type(Mz)} with data {Mz!r}")
        return Mx >> (lambda x:
               My >> (lambda y:  # noqa: E128 -- monadic style
               Mz >> (lambda z:  # noqa: E128 -- monadic style
                      M(f(x, y, z)))))
    return lifted
