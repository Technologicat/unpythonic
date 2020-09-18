# -*- coding: utf-8 -*-
"""Environment for let-like constructs."""

__all__ = ["env"]

from collections.abc import Container, Sized, Iterable, Mapping, MutableMapping
from .lazyutil import passthrough_lazy_args

# co-operate with unpythonic.syntax.lazify; this is essentially a binding construct,
# so it shouldn't force any promises that are stuffed into the env.
@passthrough_lazy_args
class env:
    """Environment for let-like constructs.

    Names must be identifiers (see str.isidentifier()), even when introduced
    by subscripting the env instance.

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

        with env(s="hello", orange="fruit", answer=42) as e:
            ...  # ...code that uses e...

    When the `with` block exits, ``e`` forgets all its bindings. The ``e``
    instance itself will remain alive due to Python's scoping rules.
    """
    # do not allow bindings that would break functionality.
    _reserved_names = ("set", "clear", "finalize", "_env", "_finalized",
                       "_direct_write", "_reserved_names")
    _direct_write = ("_env", "_finalized")

    def __init__(self, **bindings):
        self._env = {}
        self._finalized = False  # "let" sets this once env setup done
        for name, value in bindings.items():
            setattr(self, name, value)

    # item access by name
    # https://docs.python.org/3/reference/datamodel.html#object.__setattr__
    # https://docs.python.org/3/reference/datamodel.html#object.__getattr__
    def __setattr__(self, name, value):
        # TODO: doesn't protect against client code writing to the _direct_write names.
        if name in self._direct_write:  # hook to allow creating internal variables directly in self
            return super().__setattr__(name, value)
        if name in self._reserved_names:
            raise AttributeError("cannot overwrite reserved name {}; complete list: {}".format(repr(name), self._reserved_names))
        if self._finalized and name not in self:
            raise AttributeError("name {} is not defined; adding new bindings to a finalized environment is not allowed".format(repr(name)))
        # Block invalid names in subscripting (which redirects here).
        if not name.isidentifier():
            raise ValueError("'{}' is not a valid identifier".format(name))
#        value = self._wrap(name, value)  # for "e.x << value" rebind syntax.
        self._env[name] = value  # make all other attrs else live inside _env

    def __getattr__(self, name):
        # Block invalid names in subscripting (which redirects here).
        if not name.isidentifier():
            raise ValueError("{} is not a valid identifier".format(repr(name)))
        e = self._env   # __getattr__ not called if direct attr lookup succeeds, no need for hook.
        if name not in e:
            raise AttributeError("name {} is not defined".format(repr(name)))
        return e[name]

    def __delattr__(self, name):
        if not name.isidentifier():  # Can happen through __delitem__.
            raise ValueError("{} is not a valid identifier".format(repr(name)))
        if self._finalized:
            raise TypeError("deleting bindings from a finalized environment not allowed; attempted to delete '{:s}'".format(name))
        e = self._env   # __getattr__ not called if direct attr lookup succeeds, no need for hook.
        if name not in e:
            raise AttributeError("name {} is not defined".format(repr(name)))
        del e[name]

    # membership test (in, not in)
    def __contains__(self, k):
        return self._env.__contains__(k)

    # iteration
    def __iter__(self):
        return self._env.__iter__()
    # no __next__, iterating over dict.

    # Mapping
    def items(self):
        """Like dict.items()."""
        return self._env.items()
    def keys(self):
        return self._env.keys()
    def values(self):
        return self._env.values()
    def get(self, k, default=None):
        return self[k] if k in self else default
    def __eq__(self, other):
        return other == self._env

    def __len__(self):
        return len(self._env)

    # MutableMapping
    def pop(self, k, *default):
        if self._finalized:
            raise TypeError("deleting bindings from a finalized environment not allowed; attempted to delete {}".format(repr(k)))
        return self._env.pop(k, *default)
    def popitem(self):
        if self._finalized:
            raise TypeError("deleting bindings from a finalized environment not allowed")
        return self._env.popitem()
    def clear(self):
        if self._finalized:
            raise TypeError("clearing a finalized environment not allowed")
        return self._env.clear()
    def update(self, *mapping, **bindings):
        """See `dict.update` for the signature."""
        if mapping:
            if len(mapping) > 1:
                raise ValueError("Expected at most one `mapping`, got {}.".format(len(mapping)))
            m = mapping[0]
            if self._finalized and any(k not in self for k in m):
                raise AttributeError("adding new bindings to a finalized environment is not allowed")
        if self._finalized and any(k not in self for k in bindings):
            raise AttributeError("adding new bindings to a finalized environment is not allowed")
        return self._env.update(*mapping, **bindings)
    def setdefault(self, k, *default):
        if self._finalized and k not in self:
            raise AttributeError("name {} is not defined; adding new bindings to a finalized environment is not allowed".format(repr(k)))
        return self._env.setdefault(k, *default)

    # subscripting
    def __getitem__(self, k):
        return getattr(self, k)

    def __setitem__(self, k, v):
        setattr(self, k, v)

    def __delitem__(self, k):
        delattr(self, k)

    # context manager
    def __enter__(self):
        return self

    def __exit__(self, exctype, excvalue, traceback):
        self._env.clear()  # on context exit, clear even if we are a finalized env

    # pretty-printing
    def __repr__(self):  # pragma: no cover
        bindings = ["{:s}={}".format(name, repr(value)) for name, value in self._env.items()]
        return "<env object at 0x{:x}: {{{:s}}}>".format(id(self), ", ".join(bindings))

    # other
    def set(self, name, value):
        """Convenience method to allow assignment in expression contexts.

        Like Scheme's set! function. Only rebinding is allowed.

        For convenience, returns the `value` argument.
        """
        if name not in self:  # allow only rebinding
            raise AttributeError("name {} is not defined".format(repr(name)))
        return self._set(name, value)

    # for co-operation with the do[] macro: internal function with no already-defined check.
    def _set(self, name, value):
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

    def finalize(self):
        """Finalize environment.

        This stops the instance from accepting any more new bindings,
        or any deletions of existing bindings.

        Existing bindings can still be given new values even in a finalized
        environment.
        """
        self._finalized = True

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

# register virtual base classes
for abscls in (Container, Sized, Iterable, Mapping, MutableMapping):
    abscls.register(env)
del abscls
