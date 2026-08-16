# -*- coding: utf-8 -*-
"""Assign-once environment."""

__all__ = ["assignonce"]

from typing import Any

from .env import env as _envcls

class assignonce(_envcls):
    """Environment with assign-once names.

    **Reach for this only when you want the assign-once discipline itself.**
    The macro layer supports plain ``env`` far more thoroughly, so choosing
    ``assignonce`` costs you that support.

    Note ``env.finalize()`` is *not* a substitute, and the two guarantees are
    orthogonal: ``finalize()`` freezes the *set of names* (no additions, no
    deletions) while leaving existing bindings rebindable, whereas this class
    fixes each binding's *first value* while leaving the set of names open.
    Pick by which of the two you actually need.

    In Scheme terms, this makes ``define`` and ``set!`` look different::

        with assignonce() as e:
            e.foo = "bar"           # new definition, ok
            e.set("foo", "tavern")  # explicitly rebind e.foo, ok
            e << ("foo", "tavern")  # same (but returns e instead of new value)
            e.foo = "quux"          # AttributeError, e.foo already defined.

    If you don't need the automatic clear on exiting the `with` block::

        e = assignonce()
        e.foo = "bar"
        e.set("foo", "tavern")
        e.foo = "quux"  # AttributeError
    """
    def __setattr__(self, name: str, value: Any) -> None:
        if name in self._reserved_names or name not in self:
            return super().__setattr__(name, value)
        else:
            raise AttributeError(f"name {repr(name)} is already defined")

    def __delattr__(self, name: str) -> None:
        """Forbid `del e.foo` on a defined name.

        Otherwise the assign-once contract could be bypassed via
        ``del e.foo; e.foo = new_value``. Use ``.set(name, value)`` for
        explicit rebinding instead.
        """
        if name not in self._reserved_names and name in self:
            raise AttributeError(f"name {repr(name)} is defined; deletion not allowed in an assign-once environment (use .set() to rebind)")
        super().__delattr__(name)

    def set(self, name: str, value: Any) -> Any:
        """Rebind an existing name to a new value."""
        env = self._env
        if name not in env:
            raise AttributeError(f"name {repr(name)} is not defined")
        # important part: bypass our own __setattr__, which would refuse the update.
        super().__setattr__(name, value)
        return value
