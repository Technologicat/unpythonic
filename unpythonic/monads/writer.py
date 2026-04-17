# -*- coding: utf-8 -*-
"""The Writer monad — pure-functional debug/audit log.

A ``Writer w a`` wraps a pair ``(value, log)``. Binding threads the value
through the chain while concatenating logs. The log can be any type that
supports ``+`` and has a sensible empty value — the defaults assume a
``str`` log (empty ``""``).

Classical use: produce a computation result along with a trace of what was
done, without resorting to mutable state or ``print`` side-effects.
"""

__all__ = ["Writer"]

from collections.abc import Callable
from typing import Any

from .abc import LiftableMonad


class Writer(LiftableMonad):
    """The Writer monad. ``Writer(value, log)``; log defaults to ``""``.

    Usage::

        from unpythonic.monads import Writer

        result = (Writer(10)
                  >> (lambda x: Writer(x + 1, f"added 1 to {x}; "))
                  >> (lambda y: Writer(y * 2, f"doubled {y}; ")))
        value, log = result.data
        # value == 22
        # log == "added 1 to 10; doubled 11; "

    Use the classmethod ``Writer.tell(msg)`` to add a log entry without
    touching the value: ``writer_a.then(Writer.tell(msg))`` appends ``msg``
    to the log and passes ``writer_a``'s value through (actually: yields
    ``None`` as the value of the ``tell`` step; use ``.then`` to replace
    with the real value on the next step).

    **Semantics note**. ``fmap`` does **not** add a log entry of its own —
    the teaching code did, which in turn forced a manual override of bind
    to avoid double-logging. Here we keep fmap transparent so the default
    bind (``fmap . join``) from the ``Monad`` base works as-is.
    """

    def __init__(self, value: Any, log: Any = "") -> None:
        """Unit: wrap ``value: a`` with an optional ``log: w`` (default empty string)."""
        self.data = (value, log)

    def fmap(self, f: Callable) -> "Writer":
        """``fmap: Writer w a -> (a -> b) -> Writer w b``. Log passes through unchanged."""
        value, log = self.data
        cls = self.__class__
        return cls(f(value), log)

    def join(self) -> "Writer":
        """``join: Writer w (Writer w a) -> Writer w a``. Concatenates outer + inner logs."""
        cls = self.__class__
        if not isinstance(self.data[0], cls):
            raise TypeError(
                f"Expected a nested {cls.__name__}, got {type(self.data[0])} with data {self.data[0]!r}"
            )
        inner, outer_log = self.data
        inner_value, inner_log = inner.data
        return cls(inner_value, outer_log + inner_log)

    @classmethod
    def tell(cls, log_entry: Any) -> "Writer":
        """Emit a log entry and yield a dummy value.

        ``tell: w -> Writer w None``

        Use with ``.then`` to interleave logging into a chain: e.g.
        ``computation.then(Writer.tell("done; "))`` yields a Writer whose
        value is ``None`` and whose log has ``"done; "`` appended.
        """
        return cls(None, log_entry)

    def __eq__(self, other: Any) -> bool:
        if other is self:
            return True
        if not isinstance(other, Writer):
            return NotImplemented
        return self.data == other.data

    def __hash__(self) -> int:
        return hash((Writer, self.data))

    def __repr__(self) -> str:  # pragma: no cover
        return f"{self.__class__.__name__}{self.data!r}"
