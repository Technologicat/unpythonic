#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Dynamic assignment."""

__all__ = ["dyn", "make_dynvar"]

import threading

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

class _EnvBlock(object):
    def __init__(self, bindings):
        self.bindings = bindings
    def __enter__(self):
        if self.bindings:  # optimization, skip pushing an empty scope
            _getstack().append(self.bindings)
    def __exit__(self, t, v, tb):
        if self.bindings:
            _getstack().pop()

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

        from dynscope import dyn

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

    Based on StackOverflow answer by Jason Orendorff (2010).

    https://stackoverflow.com/questions/2001138/how-to-create-dynamical-scoped-variables-in-python
    """
    def __getattr__(self, name):
        for scope in reversed(_getstack()):
            if name in scope:
                return scope[name]
        if name in _global_dynvars:  # default value from make_dynvar
            return _global_dynvars[name]
        raise AttributeError("dynamic variable '{:s}' is not defined".format(name))

    def let(self, **bindings):
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
    def _asdict(self):
        data = {}
        data.update(_global_dynvars)
        for scope in _getstack():
            data.update(scope)
        return data

    def __iter__(self):
        return iter(self._asdict())
    # no __next__, iterating over dict.

    def items(self):
        """Like dict.items(). Return a snapshot of the current state."""
        return self._asdict().items()

    def __len__(self):
        return len(self._asdict())

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

def test():
    def f():
        assert dyn.a == 2  # no a in lexical scope

    def runtest():
        with dyn.let(a=2, b="foo"):
            assert dyn.a == 2
            f()

            with dyn.let(a=3):
                assert dyn.a == 3

            assert dyn.a == 2

        print("Test 1 PASSED")

        try:
            print(dyn.b)      # AttributeError, dyn.b no longer exists
        except AttributeError:
            print("Test 2 PASSED")
        else:
            print("Test 2 FAILED")

        from queue import Queue
        comm = Queue()
        def threadtest(q):
            try:
                dyn.c  # just access dyn.c
            except AttributeError as err:
                q.put(err)
            q.put(None)

        with dyn.let(c=42):
            t1 = threading.Thread(target=threadtest, args=(comm,), kwargs={})
            t1.start()
            t1.join()
        v = comm.get()
        if v is None:
            print("Test 3 PASSED")
        else:
            print("Test 3 FAILED: {}".format(v))

        t2 = threading.Thread(target=threadtest, args=(comm,), kwargs={})
        t2.start()  # should crash, dyn.c no longer exists in the main thread
        t2.join()
        v = comm.get()
        if v is not None:
            print("Test 4 PASSED")
        else:
            print("Test 4 FAILED")

    runtest()

    with dyn.let(a=1, b=2):
        # membership test
        assert "a" in dyn
        assert "c" not in dyn
        # subscript syntax as an alternative way to refer to items
        assert dyn.a is dyn["a"]
        # iteration works like dictionary
        assert tuple(sorted(dyn.items())) == (("a", 1), ("b", 2))

        # vs are frozen in at the time items() is called - it's a snapshot
        assert tuple(sorted((k, v) for k, v in dyn.items())) == (("a", 1), ("b", 2))

        # safer (TOCTTOU) in complex situations, retrieves the current dyn[k]
        assert tuple(sorted((k, dyn[k]) for k in dyn)) == (("a", 1), ("b", 2))

    make_dynvar(im_always_there=True)
    with dyn.let(a=1, b=2):
        assert tuple(sorted(dyn.items())) == (("a", 1), ("b", 2),
                                              ("im_always_there", True))
    assert tuple(sorted(dyn.items())) == (("im_always_there", True),)

    print("All tests PASSED")

if __name__ == '__main__':
    test()
