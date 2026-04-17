# -*- coding: utf-8 -*-
"""The State monad — threading a state value through a pure computation.

**Warning**: mind-bending material.

In Python, in the same vein as ``unfold()``, we don't really *need* the
State monad for its basic uses — generators already handle implicit
state nicely (though they use genuine destructive imperative updates,
whereas this doesn't). But it's worth studying, because in the process
we see a different way of thinking about monads.

Where the container-style monads (``Identity``, ``Maybe``, ``List``, etc.)
wrap a *value*, a ``State`` wraps a *computation*: a function
``s -> (a, s)`` that takes an input state, produces a data value, and
returns a new state. The main idea is **monads as computation** rather
than monads as containers.

**How it's used** — two alternating phases:

1. State processor ``s -> (a, s)``: old state in; a data value and new
   state out.
2. The code at the use site: do something with the data value ``a``,
   then tell phase 1 which state processor to run next.

The state ``s`` only becomes bound when the composed chain starts
running — and we start the chain only after we're done composing it.
In the call to ``.run(s0)``, we give the chain the initial state it
will start in; then the monad does the plumbing required to pass the
state across the state-processor calls, in a functional (FP) manner.
Just like in an FP loop, there is no mutation, but in effect, the state
changes (via fresh instances). Until the chain runs, everything is, so
to speak, just hypothetical — planning what we'll do once we get our
hands on an initial state value. This is an important difference from
the data-container monads.

**On the three-chainee puzzle** (one of the most difficult points to
grasp at first): at first glance, it would seem the state processor in
the middle of a chain ``A >> B >> C`` runs twice — once as the second
operation of the first State instance, and again as the first operation
of the second State instance. But actually that's wrong. Binding is
essentially function composition, and we return the composed function.
Hence ``A >> B`` becomes a new composed state processor — call it ``D``
— and the chain is transformed into ``D >> C``. At this point, *nothing
has actually run yet*; we are just planning what to do by building
composed functions. Now the second bind composes a new state processor
out of ``D`` and ``C``. When we eventually ``.run`` the chain, running
``D`` internally runs both ``A`` and ``B``, so each of ``A``, ``B``,
``C`` runs exactly once — as they should.

The monad is, in effect, *shunting the state value around the code that
is only interested in the data*, and delivering the state only where
it's actually needed — into the actual state processors.

**Type invariant**: in Haskell, the type of the state value stays the
same in a chain, whereas the type of the data value may change. Python
doesn't enforce that, but readers familiar with the typed version will
expect it.

Based on:

- http://brandon.si/code/the-state-monad-a-tutorial-for-the-confused/
- https://wiki.haskell.org/Monads_as_computation
- https://en.wikibooks.org/wiki/Haskell/Understanding_monads/State
- https://wiki.haskell.org/State_Monad

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

        Here ``f`` is expected to be ``a -> State(s -> (b, s))``: it takes
        a *data value* (not a state value!) and returns a state processor.
        What's this crazy kind of function? Somewhat similarly to "lambda
        as a code block" in Lisp, it's not really a function in the usual
        sense (though formally it is one) — it's the code block that the
        chain binds into. It's a thing to be performed *between* two
        processings of the state. So it makes sense that it takes the data
        value (the ``a`` part of the result of the current state
        processor), does something with it, and then tells us what to do
        next — i.e. provides a new state processor.

        The beauty: the user-level code block *doesn't even see* the state
        value. It only gets the data value of the result, just as if
        computing with plain functions that need no state. The monad
        shunts the state value around, delivering it only where it's
        actually needed — into the actual state processors.

        See also the ``wrap`` / ``unwrap`` comments at
        https://en.wikibooks.org/wiki/Haskell/Understanding_monads/State
        """
        def composed(s: Any) -> tuple:
            value, s_prime = self.run(s)  # apply current processor
            # Take the contained data value from inside the monad (= the
            # data result of our wrapped computation) and send it to the
            # user's code block. The block gives us a new State monad,
            # which wraps the next state processor to run.
            next_processor = f(value)
            return next_processor.run(s_prime)  # then apply the new processor
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
