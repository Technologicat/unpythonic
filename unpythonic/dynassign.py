# -*- coding: utf-8 -*-
"""Dynamic assignment."""

__all__ = ["dyn", "make_dynvar"]

import threading
from collections import ChainMap
from collections.abc import Container, Sized, Iterable, Mapping

from .singleton import Singleton

# LEG rule for dynvars: allow a global definition (shared between threads) with make_dynvar(a=...)
_global_dynvars = {}

_L = threading.local()

_mainthread_stack = []
_mainthread_lock = threading.RLock()
def _getstack():
    if threading.current_thread() is threading.main_thread():
        return _mainthread_stack
    if not hasattr(_L, "_stack"):
        # Each new thread, when spawned, inherits the contents of the main thread's
        # dynamic scope stack.
        #
        # TODO: preferable to use the parent thread's current stack, but difficult to get.
        # Could monkey-patch threading.Thread.__init__ to record this information in self...
        with _mainthread_lock:
            _L._stack = _mainthread_stack.copy()
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

# We need multiple observer instances, because dynamic scope stacks are thread-local.
# If they weren't, this could be a singleton and the __del__ method wouldn't be needed.
class _DynLiveView(ChainMap):
    def __init__(self):
        super().__init__(self)
        self._refresh()
        _getobservers()[id(self)] = self
    # TODO: __del__ most certainly runs during test_dynassign (as can be
    # evidenced by placing a debug print inside it), but coverage fails
    # to report it as covered.
    def __del__(self):  # pragma: no cover
        # No idea how, but our REPL server can trigger a KeyError here
        # if the user views `help()`, which causes the client to get stuck.
        # Then pressing `q` in the server console to quit the help, and then
        # asking the REPL client (which is now responsive again) to disconnect
        # (Ctrl+D), triggers the `KeyError` when the server cleans up the
        # disconnected session.
        #
        # Anyway, if `id(self)` is not in the current thread's observers,
        # we don't need to do anything here, so the Right Thing to do is
        # to absorb `KeyError` if it occurs.
        try:
            del _getobservers()[id(self)]
        except KeyError:
            pass
    def _refresh(self):
        self.maps = list(reversed(_getstack())) + [_global_dynvars]

class _Dyn(Singleton):
    """This module exports a singleton, ``dyn``, which provides dynamic assignment
    (like Racket's ``parameterize``; akin to Common Lisp's special variables.).

    For implicitly passing stuff through several layers of function calls,
    in cases where a lexical closure is not the right tool for the job
    (i.e. when some of the functions are defined elsewhere in the code).

      - Dynamic variables are introduced by ``with dyn.let()``.

      - The created dynamic variables exist while the with block is executing,
        and fall out of scope when the with block exits. (I.e. dynamic variables
        exist during the dynamic extent of the with block.)

      - The blocks can be nested. Inner definitions shadow outer ones, as usual.

      - Each thread has its own dynamic scope stack.

      - Additionally, there is one global dynamic scope, shared between all
        threads, that can be used to set default values for dynamic variables.
        See ``make_dynvar``.

      - An existing dynamic variable ``x`` can be mutated by assigning to ``dyn.x``,
        or by calling ``dyn.update(x=...)`` (syntax similar to ``let``, for mass updates).
        The variable is mutated in the nearest enclosing dynamic scope that has that
        name bound. If the name is not bound in any dynamic scope, ``AttributeError``
        is raised.

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
    # NOTE: Pickling `dyn` makes no sense. The whole point of `dyn` is that it
    # tracks dynamic state; in a manner of speaking, it has one foot on the
    # call stack.
    #
    # But we can't prevent pickling, because MacroPy's hygienic quasiquotes (`hq[]`)
    # build on `pickle`. If `dyn` fails to pickle, some macros in `unpythonic.syntax`
    # (notably `autoref` and `lazify`) crash, because they need both `dyn` and `hq[]`.
    #
    # Fortunately, no state is saved in the `dyn` singleton instance itself, so
    # it doesn't matter that the default `__setstate__` clobbers the `__dict__`
    # of the singleton instance at unpickle time.

    def _resolve(self, name):
        # Essentially asdict() and look up, but without creating the ChainMap
        # every time _resolve() is called.
        for scope in reversed(_getstack()):
            if name in scope:
                return scope
        if name in _global_dynvars:  # default value from make_dynvar
            return _global_dynvars
        raise AttributeError("dynamic variable {} is not defined".format(repr(name)))

    def __getattr__(self, name):
        """Read the value of a dynamic binding."""
        scope = self._resolve(name)
        return scope[name]

    def __setattr__(self, name, value):
        """Update an existing dynamic binding.

        The update occurs in the closest enclosing dynamic scope that has
        ``name`` bound.

        If the name cannot be found in any dynamic scope, ``AttributeError`` is
        raised.

        **CAUTION**: Use carefully, if at all. Stealth updates of dynamic
        variables defined in enclosing dynamic scopes can destroy readability.
        """
        scope = self._resolve(name)
        scope[name] = value

    def let(self, **bindings):
        """Introduce dynamic bindings.

        Context manager; usage is ``with dyn.let(name=value, ...):``

        When binding a name that already exists in an enclosing dynamic scope,
        the inner binding shadows the enclosing one for the dynamic extent of
        the ``with dyn.let``.

        This dynamic binding is the main advantage of dynamic assignment,
        as opposed to simple global variables.

        See ``dyn``.
        """
        return _EnvBlock(bindings)

    def update(self, **bindings):
        """Mass-update existing dynamic bindings.

        For each binding, the update occurs in the closest enclosing dynamic
        scope that has a binding with that name.

        If at least one of the names cannot be found in any dynamic scope, the
        update is canceled (without changes) and ``AttributeError`` is raised.

        **CAUTION**: Like ``__setattr__``, but for mass updates, so the same
        caution applies. Use carefully, if at all.
        """
        # validate, and resolve scopes (let AttributeError propagate)
        def doit():
            scopes = {k: self._resolve(k) for k in bindings}
            for k, v in bindings.items():
                scope = scopes[k]
                scope[k] = v
        # If we're the main thread, any new threads spawned will copy our scope stack
        # in whatever state it happens to be in. Make the update atomic.
        if threading.current_thread() is threading.main_thread():
            with _mainthread_lock:
                doit()
        else:
            doit()

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
        setattr(self, k, v)

    # pretty-printing
    def __repr__(self):  # pragma: no cover
        bindings = ["{:s}={}".format(k, repr(self[k])) for k in self]
        return "<dyn object at 0x{:x}: {{{:s}}}>".format(id(self), ", ".join(bindings))
dyn = _Dyn()

def make_dynvar(**bindings):
    """Create a dynamic variable and set its default value.

    The default value is used when ``dyn`` is queried for the value outside the
    dynamic extent of any ``with dyn.let()`` blocks.

    This is convenient for eliminating the need for ``if "x" in dyn``
    checks, since the variable will always be there (after the global
    ``make_dynvar`` call has been executed).

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

# register virtual base classes
for abscls in (Container, Sized, Iterable, Mapping):
    abscls.register(_Dyn)
del abscls
