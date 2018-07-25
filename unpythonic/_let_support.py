#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Environment for let constructs. Internal module."""

class env:
    """Bunch with context manager, iterator and subscripting support.

    Iteration and subscripting just expose the underlying dict.

    Also works as a bare bunch.

    Usage:
        # with context manager:
        with env(x = 0) as myenv:
            print(myenv.x)
        # DANGER: myenv still exists due to Python's scoping rules.

        # bare bunch:
        myenv2 = env(s="hello", orange="fruit", answer=42)
        print(myenv2.s)
        print(myenv2)

        # iteration and subscripting:
        names = [k for k in myenv2]

        for k,v in myenv2.items():
            print("Name {} has value {}".format(k, v))
    """
    def __init__(self, **bindings):
        self._env = {}
        for name,value in bindings.items():
            self._env[name] = value

    # item access by name
    #
    def __setattr__(self, name, value):
        if name == "_env":  # hook to allow creating _env directly in self
            return super().__setattr__(name, value)
        self._env[name] = value  # make all other attrs else live inside _env

    def __getattr__(self, name):
        env = self._env   # __getattr__ not called if direct attr lookup succeeds, no need for hook.
        if name in env:
            return env[name]
        else:
            raise AttributeError("Name '{:s}' not in environment".format(name))

    # context manager
    #
    def __enter__(self):
        return self

    def __exit__(self, et, ev, tb):
        # we could nuke our *contents* to make all names in the environment
        # disappear, but it's simpler and more predictable not to.
        pass

    # iteration
    #
    def __iter__(self):
        return self._env.__iter__()

    def __next__(self):
        return self._env.__next__()

    def items(self):
        return self._env.items()

    # subscripting
    #
    def __getitem__(self, k):
        return getattr(self, k)

    def __setitem__(self, k, v):
        setattr(self, k, v)

    # pretty-printing
    #
    def __str__(self):
        bindings = ["{}: {}".format(name,value) for name,value in self._env.items()]
        return "<env: <{:s}>>".format(", ".join(bindings))

    # other
    #
    def set(self, name, value):
        """Convenience method to allow assignment in expression contexts.

        Like Scheme's set! function. Only rebinding is allowed.

        For convenience, returns the `value` argument.
        """
        if not hasattr(self, name):  # allow only rebinding
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
