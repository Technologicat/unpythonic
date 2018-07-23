#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""In Scheme terms, make define and set! look different.

For defensive programming, to avoid accidentally overwriting existing names.

Usage:

from norebind import norebind

with norebind() as e:
    e.foo = "bar"       # new name, ok
    e.foo <<= "tavern"  # rebind "foo" in e
    e.foo = "quux"      # AttributeError, foo already defined.
"""

__all__ = ["norebind"]

# To be able to create _env, in __setattr__ we must special-case it,
# falling back to default behaviour (which is object.__setattr__,
# hence super().__setattr__).
#
# __getattr__ is never called if standard attribute lookup succeeds,
# so there we don't need a hook for _env (as long as we don't try to
# look up _env before it is created).
#
# __enter__ should "return self" to support the binding form "with ... as ...".
#
# https://docs.python.org/3/reference/datamodel.html#object.__setattr__
# https://docs.python.org/3/reference/datamodel.html#object.__getattr__

class norebind:
    def __init__(self):
        self._env = {}      # should be private...

    def __setattr__(self, name, value):
        if name == "_env":  # ...but this looks clearer with no name mangling.
            return super().__setattr__(name, value)

        env = self._env
        if name not in env:
            env[name] = self._make_rebindable(value)
        elif value.__class__.__name__ == "_wrapper":  # from <<=, allow rebind
            env[name] = value
        else:
            raise AttributeError("name '{:s}' is already defined".format(name))

    def __getattr__(self, name):
        env = self._env
        if name in env:
            return env[name]
        else:
            raise AttributeError("name '{:s}' is not defined".format(name))

    def __enter__(self):
        return self

    def __exit__(self, exctype, excvalue, traceback):
        pass

    def _make_rebindable(self, obj):
        # TODO: use << for set!
        # For some types (such as int), __ilshift__ does not exist and cannot be
        # written to. Also __lshift__ is read-only, so it's not a possible syntax either.
        #
        # Hence we wrap obj, just adding an (or overriding the) __ilshift__ method.
        env_instance = self
        class _wrapper(obj.__class__):  # new _wrapper type each time we are called!
            def __ilshift__(self, newval):
                return env_instance._make_rebindable(unwrap(newval))
        def unwrap(obj):  # find first parent class that is not a _wrapper
            for cls in obj.__class__.__mro__:
                if cls.__name__ != "_wrapper":
                    return cls(obj)  # rebuild obj without wrapper
            assert False, "wrapped value missing in {} {}".format(type(obj), obj)
        return _wrapper(obj)  # rebuild obj with wrapper

def test():
    with norebind() as e:
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
            e.a <<= 42     # rebind
            e.a <<= 2*e.a  # type(newval) is int also in this case
            e.a <<= e.b    # but here type(newval) is a _wrapper
        except AttributeError as err:
            print('Test 3 FAILED: {}'.format(err))
        else:
            print('Test 3 PASSED')

        try:
            e.c <<= 3  # fail, e.c not bound
        except AttributeError as err:
            print('Test 4 PASSED')
        else:
            print('Test 4 FAILED')

if __name__ == '__main__':
    test()
