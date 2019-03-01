# -*- coding: utf-8 -*-
"""Dynamic assignment."""

__all__ = ["dyn", "make_dynvar"]

import threading
from collections import ChainMap
from collections.abc import Container, Sized, Iterable, Mapping

# Each new thread, when spawned, inherits the contents of the main thread's
# dynamic scope stack.
#
# TODO: preferable to use the parent thread's current stack, but difficult to get.
# Could monkey-patch threading.Thread.__init__ to record this information in self...
class MyLocal(threading.local):  # see help(_threading_local)
    initialized = False
    def __init__(self, **kw):
        if self.initialized:
            raise SystemError('__init__ called too many times')
        self.initialized = True
        self.__dict__.update(kw)

# LEG rule for dynvars: allow a global definition with make_dynvar(a=...)
_global_dynvars = {}

_mainthread_stack = []
_L = MyLocal(default_stack=_mainthread_stack)
def _getstack():
    if threading.current_thread() is threading.main_thread():
        return _mainthread_stack
    if not hasattr(_L, "_stack"):
        _L._stack = _L.default_stack.copy()  # copy main thread's current stack
    return _L._stack

def _getobservers():
    if not hasattr(_L, "_observers"):
        _L._observers = {}
    return _L._observers

class _EnvBlock(object):
    def __init__(self, bindings):
        self.bindings = bindings
    def __enter__(self):
        if self.bindings:  # optimization, skip pushing an empty scope
            _getstack().append(self.bindings)
            for o in _getobservers().values():
                o._refresh()
    def __exit__(self, t, v, tb):
        if self.bindings:
            _getstack().pop()
            for o in _getobservers().values():
                o._refresh()

class _DynLiveView(ChainMap):
    def __init__(self):
        super().__init__(self)
        self._refresh()
        _getobservers()[id(self)] = self
    def __del__(self):
        del _getobservers()[id(self)]
    def _refresh(self):
        self.maps = list(reversed(_getstack())) + [_global_dynvars]

class _Env(object):
    """This module exports a single object instance, ``dyn``, which provides
    dynamic assignment (like Racket's ``parameterize``; akin to Common Lisp's
    special variables).

    For implicitly passing stuff through several layers of function calls,
    in cases where a lexical closure is not the right tool for the job
    (i.e. when some of the functions are defined elsewhere in the code).

      - Dynamic variables are set by ``with dyn.let()``.

      - The created dynamic variables exist while the with block is executing,
        and fall out of scope when the with block exits. (I.e. dynamic variables
        exist during the dynamic extent of the with block.)

      - The blocks can be nested. Inner definitions shadow outer ones, as usual.

      - Each thread has its own dynamic scope stack.

      - Additionally, there is one global dynamic scope, shared between all
        threads, that can be used to set default values for dynamic variables.
        See ``make_dynvar``.

    Similar to (parameterize) in Racket.

    Example::

        from unpythonic.dynassign import dyn

        def f():
            print(dyn.a)

        def main():
            with dyn.let(a=2, b="foo"):
                print(dyn.a)  # 2
                f()           # note f is defined outside the lexical scope of main()!

                with dyn.let(a=3):
                    print(dyn.a)  # 3

                print(dyn.a)  # 2

            print(dyn.b)      # AttributeError, dyn.b no longer exists

        main()

    Initial version of this was based on a StackOverflow answer by Jason Orendorff (2010).

    https://stackoverflow.com/questions/2001138/how-to-create-dynamical-scoped-variables-in-python
    """
    def __getattr__(self, name):
        # Essentially asdict() and look up, but without creating the ChainMap every time.
        for scope in reversed(_getstack()):
            if name in scope:
                return scope[name]
        if name in _global_dynvars:  # default value from make_dynvar
            return _global_dynvars[name]
        raise AttributeError("dynamic variable '{:s}' is not defined".format(name))

    def let(self, **bindings):
        """Introduce dynamic bindings.

        Context manager; usage is ``with dyn.let(name=value, ...):``

        See ``dyn``.
        """
        return _EnvBlock(bindings)

    def __setattr__(self, name, value):
        raise AttributeError("dynamic variables can only be set using 'with dyn.let()'")

    # membership test (in, not in)
    def __contains__(self, name):
        try:
            getattr(self, name)
            return True
        except AttributeError:
            return False

    # iteration
    def asdict(self):
        """Return a view of dyn as a ``collections.ChainMap``.

        When new dynamic scopes begin or old ones exit, its ``.maps`` attribute
        is automatically updated to reflect the changes.
        """
        return _DynLiveView()

    def __iter__(self):
        return iter(self.asdict())
    # no __next__, iterating over dict.

    # Mapping
    def items(self):
        """Abbreviation for asdict().items()."""
        return self.asdict().items()
    def keys(self):
        return self.asdict().keys()
    def values(self):
        return self.asdict().values()
    def get(self, k, default=None):
        return self[k] if k in self else default
    def __eq__(self, other):  # dyn is a singleton, but its contents can be compared to another mapping.
        return other == self.asdict()

    def __len__(self):
        return len(self.asdict())

    # subscripting
    def __getitem__(self, k):
        return getattr(self, k)

    def __setitem__(self, k, v):
        # writing not supported, but should behave consistently with setattr.
        setattr(self, k, v)

    # pretty-printing
    def __repr__(self):
        bindings = ["{:s}={}".format(k,repr(self[k])) for k in self]
        return "<dyn object at 0x{:x}: {{{:s}}}>".format(id(self), ", ".join(bindings))

def make_dynvar(**bindings):
    """Create and set default value for dynamic variables.

    The default value is used when ``dyn`` is queried for the value outside the
    dynamic extent of any ``with dyn.let()`` blocks.

    This is convenient for eliminating the need for ``if "x" in dyn``
    checks, since the variable will always be there (after the global
    definition has been executed).

    The kwargs should be ``name=value`` pairs. Note ``value`` is mandatory,
    since the whole point of this function is to assign a value. If you need
    a generic placeholder value, just use ``None``.

    Each dynamic variable, of the same name, should only have one default set;
    the (dynamically) latest definition always overwrites. However, we do not
    prevent this, because in some codebases the same module may run its
    top-level initialization code multiple times (e.g. if a module has a
    ``main()`` for tests, and the file gets loaded both as a module and as
    the main program).

    Similar to (make-parameter) in Racket.
    """
    for name in bindings:
        _global_dynvars[name] = bindings[name]

dyn = _Env()

# register virtual base classes
for abscls in (Container, Sized, Iterable, Mapping):
    abscls.register(_Env)
del abscls
