#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Assign-once names."""

__all__ = ["assignonce"]

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

class assignonce:
    """Environment with assign-once names.

    In Scheme terms, this makes ``define`` and ``set!`` look different::

        with assignonce() as e:
            e.foo = "bar"       # new definition, ok
            e.foo << "tavern"   # explicitly rebind e.foo, ok
            e.foo = "quux"      # AttributeError, e.foo already defined.
    """
    def __init__(self):
        self._env = {}      # should be private...

    def __setattr__(self, name, value):
        if name == "_env":  # ...but this looks clearer with no name mangling.
            return super().__setattr__(name, value)

        env = self._env
        if name not in env:
            env[name] = self._wrap(name, value)
#            env[name] = value  # to disable the rebind syntax, use this instead.
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

    # For rebind syntax: "e.foo << newval" --> "e.foo.__lshift__(newval)",
    # so foo.__lshift__() must be set up to rebind e.foo.
    #
    # For some types (such as int), __lshift__ is read-only.
    # Also, __ilshift__ does not exist and new attributes cannot be added.
    # Hence we wrap obj, just adding (or overriding) __lshift__.
    #
    # The first call to _wrap(), from setattr(), tells foo its name in e,
    # capturing it (as well as a reference to e) in the closure of
    # _assignonce_wrapper. Any re-wrapping (triggered by <<) then
    # just passes on the same name and e.
    #
    # We use << instead of <<= for consistency with let's env, because
    # there rebind needs to be an expression.
    #
    # TODO: this doesn't currently work if obj is a function. Need a different
    # approach; or just remove this and add e.set(name, value) like let() has.
    def _wrap(self, name, obj):
        e = self
        class _assignonce_wrapper(obj.__class__):  # new type each time we are called!
            def __lshift__(self, newval):
                rewrapped = e._wrap(name, unwrap(newval))  # avoid wrapper stacking.
                e._env[name] = rewrapped  # bypass setattr() so that it can always refuse updates.
                return rewrapped
        def unwrap(obj):  # find first parent class that is not a _wrapper
            for cls in obj.__class__.__mro__:
                if cls.__name__ != "_assignonce_wrapper":
                    return cls(obj)  # copy-construct obj without wrapper
            assert False, "wrapped value missing in {} {}".format(type(obj), obj)
        return _assignonce_wrapper(obj)  # copy-construct obj with wrapper

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
            e.a << 42     # rebind
            e.a << 2*e.a  # type(newval) is int also in this case
            e.a << e.b    # but here type(newval) is an _assignonce_wrapper
        except AttributeError as err:
            print('Test 3 FAILED: {}'.format(err))
        else:
            print('Test 3 PASSED')

        try:
            e.c << 3  # fail, e.c not bound
        except AttributeError as err:
            print('Test 4 PASSED')
        else:
            print('Test 4 FAILED')

        try:
            e.a = e.b  # any correct implementation must refuse this.
        except AttributeError:
            print('Test 5 PASSED')
        else:
            print('Test 5 FAILED')

if __name__ == '__main__':
    test()
