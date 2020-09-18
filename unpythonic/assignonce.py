# -*- coding: utf-8 -*-
"""Assign-once environment."""

__all__ = ["assignonce"]

from .env import env as _envcls

class assignonce(_envcls):
    """Environment with assign-once names.

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
    def __setattr__(self, name, value):
        if name in self._reserved_names or name not in self:
            return super().__setattr__(name, value)
        else:
            raise AttributeError("name {} is already defined".format(repr(name)))

    def set(self, name, value):
        """Rebind an existing name to a new value."""
        env = self._env
        if name not in env:
            raise AttributeError("name {} is not defined".format(repr(name)))
        # important part: bypass our own __setattr__, which would refuse the update.
        super().__setattr__(name, value)
        return value
