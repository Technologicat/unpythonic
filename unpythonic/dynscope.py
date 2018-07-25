#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Dynamic scoping."""

__all__ = ["dyn"]

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

_mainthread_stack = []
_L = MyLocal(default_stack=_mainthread_stack)
def _getstack():
    if threading.current_thread() is threading.main_thread():
        return _mainthread_stack
    if not hasattr(_L, "_stack"):
        _L._stack = _L.default_stack.copy()  # copy main thread's current stack
    return _L._stack

class _EnvBlock(object):
    def __init__(self, kwargs):
        self.kwargs = kwargs
    def __enter__(self):
        _getstack().append(self.kwargs)
    def __exit__(self, t, v, tb):
        _getstack().pop()

class _Env(object):
    """This module exports a single object instance, ``dyn``, which emulates dynamic
    scoping (Lisp's special variables; Racket's ``parameterize``).

    For implicitly passing stuff through several layers of function calls,
    in cases where a lexical closure is not the right tool for the job
    (i.e. when some of the functions are defined elsewhere in the code).

      - Dynamic variables are created by ``with dyn.let()``.

      - The created dynamic variables exist while the with block is executing,
        and fall out of scope when the with block exits. (I.e. dynamic variables
        exist during the dynamic extent of the with block.)

      - The blocks can be nested. Inner scopes mask outer ones, as usual.

      - Each thread has its own dynamic scope stack.

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
        raise AttributeError("dynamic variable '{:s}' is not defined".format(name))
    def let(self, **kwargs):
        return _EnvBlock(kwargs)
    def __setattr__(self, name, value):
        raise AttributeError("dynamic variables can only be set using 'with dyn.let()'")

dyn = _Env()

def test():
    def f():
        assert dyn.a == 2

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

if __name__ == '__main__':
    test()
