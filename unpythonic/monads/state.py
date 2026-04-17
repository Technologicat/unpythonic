# -*- coding: utf-8 -*-
"""The State monad — threading a state value through a pure computation.

Mind-bending at first. Where the container-style monads (``Identity``,
``Maybe``, ``List``, etc.) wrap a *value*, a ``State`` wraps a *computation*:
a function ``s -> (a, s)`` that takes an input state, produces a data value,
and returns a new state.

The state itself only becomes bound when the composed chain is ``.run(s0)``
with an initial state — until then, we're building a recipe. Composition
threads the state implicitly, so the user code in the middle of the chain
sees only data values, not state.

Based on:
  - https://en.wikibooks.org/wiki/Haskell/Understanding_monads/State
  - https://wiki.haskell.org/State_Monad
  - https://wiki.haskell.org/Monads_as_computation

Does **not** inherit from ``LiftableMonad`` — ``lift f = a -> M b`` doesn't
have a useful shape for State (the lifted function would need to choose
what to do with the state; there's no canonical answer).
"""

__all__ = ["State"]

from collections.abc import Callable
from typing import Any

from .abc import Monad


class State(Monad):
    """The State monad. Wraps a state-processor function ``s -> (a, s)``.

    **Constructor vs. unit**: ``State(f)`` wraps an existing processor;
    ``State.unit(a)`` wraps the value ``a`` as a state-ignoring processor
    (``lambda s: (a, s)``). They are genuinely different, unlike in most
    other monads where unit is just the constructor.

    Usage::

        from unpythonic.monads import State

        # A counter: reads state, bumps it, returns previous value as data
        bump = State(lambda s: (s, s + 1))

        chain = (bump
                 >> (lambda a: bump
                 >> (lambda b: bump
                 >> (lambda c: State.unit((a, b, c))))))

        result, final_state = chain.run(10)
        # result == (10, 11, 12)
        # final_state == 13
    """

    def __init__(self, f: Callable) -> None:
        """Wrap a state-processor function ``f: s -> (a, s)``."""
        if not callable(f):
            raise TypeError(f"Expected a callable s -> (a, s), got {f!r}")
        self.processor = f

    @classmethod
    def unit(cls, a: Any) -> "State":
        """Unit: ``a -> State(s -> (a, s))``. The state-ignoring processor."""
        return cls(lambda s: (a, s))

    def run(self, s: Any) -> tuple:
        """Run the wrapped processor starting from state ``s``. Returns ``(a, s')``."""
        return self.processor(s)

    def eval(self, s: Any) -> Any:
        """Run and return just the data value (discarding the final state)."""
        value, _ = self.run(s)
        return value

    def exec(self, s: Any) -> Any:
        """Run and return just the final state (discarding the data value)."""
        _, final_state = self.run(s)
        return final_state

    def __rshift__(self, f: Callable) -> "State":
        """Monadic bind. Composes state processors.

        ``bind: State(s -> (a, s)) -> (a -> State(s -> (b, s))) -> State(s -> (b, s))``

        Overridden (rather than using the Monad default of ``fmap . join``)
        because direct composition is much clearer here than going through
        the ``(M a)``-wrapping round trip. See the module docstring
        references for a detailed derivation.
        """
        def composed(s: Any) -> tuple:
            value, s_prime = self.run(s)  # current processor yields (value, new state)
            next_processor = f(value)     # user code chooses the next processor
            return next_processor.run(s_prime)
        return State(composed)

    @classmethod
    def get(cls) -> "State":
        """Return the current state value as the data part. ``-> State(s -> (s, s))``."""
        return cls(lambda s: (s, s))

    @classmethod
    def put(cls, s: Any) -> "State":
        """Replace the state with ``s``; yield ``None`` as data. ``s -> State(s -> (None, s))``."""
        return cls(lambda _: (None, s))

    @classmethod
    def modify(cls, f: Callable) -> "State":
        """Apply ``f: s -> s`` to the state; yield ``None`` as data."""
        return cls.get() >> (lambda s: cls.put(f(s)))

    @classmethod
    def gets(cls, f: Callable) -> "State":
        """Run ``f: s -> a`` on the state; yield ``a`` as data, state unchanged."""
        return cls.get() >> (lambda s: cls.unit(f(s)))

    def fmap(self, f: Callable) -> "State":
        """``fmap: State(s -> (a, s)) -> (a -> b) -> State(s -> (b, s))``"""
        return self >> (lambda a: State.unit(f(a)))

    def join(self) -> "State":
        """``join: State(s -> (State(s -> (a, s)), s)) -> State(s -> (a, s))``

        Plain-words derivation: given ``mm : State(s -> (State(s -> (a, s)), s))``,
        run the outer state function to get ``(inner_m, s')``, then run the inner
        with ``s'`` — standard "thread the state" pattern.
        """
        def joined(s: Any) -> tuple:
            inner_m, s_prime = self.run(s)  # outer yields (inner State, new state)
            if not isinstance(inner_m, State):
                raise TypeError(
                    f"Expected a nested State, got {type(inner_m)} with value {inner_m!r}"
                )
            return inner_m.run(s_prime)  # run inner with the threaded state
        return State(joined)

    def __repr__(self) -> str:  # pragma: no cover
        return f"{self.__class__.__name__}({self.processor!r})"
