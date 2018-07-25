#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Environment for let-like constructs."""

__all__ = ["env"]

class env:
    """Environment for let-like constructs.

    Essentially a fancy bunch.

    Bare bunch::

        e = env(s="hello", orange="fruit", answer=42)
        print(e.s)

    Printing support for debugging::

        print(e)

    Iteration and subscripting::

        names = [name for name in e]

        data = [(name, e[name]) for name in e]

        for k, v in e.items():
            print("name {} has value {}".format(k, v))

    Membership testing::

        if "answer" in e:
            print("e has an answer")
        else:
            print("e has no answer")

    Context manager::

        with env(s="hello", orange="fruit", answer=42) as e2:
            ...  # ...code that uses e2...

    When the `with` block exits, `e2` forgets all its bindings. The `e2`
    instance itself will remain alive due to Python's scoping rules.
    """
    def __init__(self, **bindings):
        self._env = {}
        for name,value in bindings.items():
            self._env[name] = value

    # item access by name
    # https://docs.python.org/3/reference/datamodel.html#object.__setattr__
    # https://docs.python.org/3/reference/datamodel.html#object.__getattr__
    def __setattr__(self, name, value):
        if name == "_env":  # hook to allow creating _env directly in self
            return super().__setattr__(name, value)
#        value = self._wrap(name, value)  # for "e.x << value" rebind syntax.
        self._env[name] = value  # make all other attrs else live inside _env

    def __getattr__(self, name):
        env = self._env   # __getattr__ not called if direct attr lookup succeeds, no need for hook.
        if name in env:
            return env[name]
        else:
            raise AttributeError("name '{:s}' is not defined".format(name))

    # membership test (in, not in)
    def __contains__(self, k):
        return self._env.__contains__(k)

    # iteration
    def __iter__(self):
        return self._env.__iter__()

    def __next__(self):
        return self._env.__next__()

    def items(self):
        return self._env.items()

    # subscripting
    def __getitem__(self, k):
        return getattr(self, k)

    def __setitem__(self, k, v):
        setattr(self, k, v)

    # context manager
    def __enter__(self):
        return self

    def __exit__(self, exctype, excvalue, traceback):
        self.clear()

    # pretty-printing
    def __str__(self):
        bindings = ["{:s}={}".format(name,repr(value)) for name,value in self._env.items()]
        return "<env object at 0x{:x}: {{{:s}}}>".format(id(self), ", ".join(bindings))

    # other
    def set(self, name, value):
        """Convenience method to allow assignment in expression contexts.

        Like Scheme's set! function. Only rebinding is allowed.

        For convenience, returns the `value` argument.
        """
        if name not in self:  # allow only rebinding
            raise AttributeError("name '{:s}' is not defined".format(name))
        setattr(self, name, value)
        return value  # for convenience

    def __lshift__(self, arg):
        """Alternative syntax for assignment.

        ``e << ("x", 42)`` is otherwise the same as ``e.set("x", 42)``, except
        it returns `self`, so that it can be chained::

            e << ("x", 42) << ("y", 23)
        """
        name, value = arg
        self.set(name, value)
        return self

    def clear(self):
        """Clear the environment, i.e. forget all bindings."""
        self._env = {}

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
    # TODO: doesn't work if obj is a function (not an acceptable base type).
    #   - Could set up a proxy object providing __lshift__(), and make its
    #     __call__() call the original function. (Also @functools.wraps it
    #     to preserve docstring etc.)
    #   - Then unwrap() needs to know which kind of wrapper it is unwrapping.
    #   - There may also be other pitfalls beside functions?
#    def _wrap(self, name, obj):
#        e = self
#        class _assignonce_wrapper(obj.__class__):  # new type each time we are called!
#            def __lshift__(self, newval):
#                rewrapped = e._wrap(name, unwrap(newval))  # avoid wrapper stacking.
#                e._env[name] = rewrapped  # bypass setattr() so that it can always refuse updates.
#                return rewrapped
#        def unwrap(obj):  # find first parent class that is not a _wrapper
#            for cls in obj.__class__.__mro__:
#                if cls.__name__ != "_assignonce_wrapper":
#                    return cls(obj)  # copy-construct obj without wrapper
#            assert False, "wrapped value missing in {} {}".format(type(obj), obj)
#        return _assignonce_wrapper(obj)  # copy-construct obj with wrapper
