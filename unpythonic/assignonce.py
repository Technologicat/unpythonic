#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Assign-once environment."""

__all__ = ["assignonce"]

from unpythonic.env import env as _envcls

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
            raise AttributeError("name '{:s}' is already defined".format(name))

    def set(self, name, value):
        """Rebind an existing name to a new value."""
        env = self._env
        if name not in env:
            raise AttributeError("name '{:s}' is not defined".format(name))
        # important part: bypass our own __setattr__, which would refuse the update.
        super().__setattr__(name, value)
        return value

def test():
    with assignonce() as e:
        try:
            e.a = 2
            e.b = 3
        except AttributeError as err:
            print('Test 1 FAILED: {}'.format(err))
        else:
            print('Test 1 PASSED')

        try:
            e.a = 5  # fail, e.a already defined
        except AttributeError:
            print('Test 2 PASSED')
        else:
            print('Test 2 FAILED')

        try:
            e.set("a", 42)  # rebind
        except AttributeError as err:
            print('Test 3 FAILED: {}'.format(err))
        else:
            print('Test 3 PASSED')

        try:
            e.set("c", 3)  # fail, e.c not bound
        except AttributeError as err:
            print('Test 4 PASSED')
        else:
            print('Test 4 FAILED')

if __name__ == '__main__':
    test()
