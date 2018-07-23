#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Dynamic scoping.

This module exports a single object instance, dyn, which emulates dynamic scoping
(Lisp's special variables; Racket's parameterize).

For implicitly passing stuff through several layers of function calls,
in cases where a lexical closure is not the right tool for the job
(i.e. when some of the functions are defined elsewhere in the code).

  - Dynamic variables are created by 'with dyn.let()'.

  - The created dynamic variables exist while the with block is executing,
    and fall out of scope when the with block exits. (I.e. dynamic variables
    exist during the dynamic extent of the with block.)

  - The blocks can be nested. Inner scopes mask outer ones, as usual.

  - Each thread has its own dynamic scope stack.

Example:

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

Based on StackOverflow answer by Jason Orendorff (2010):
    https://stackoverflow.com/questions/2001138/how-to-create-dynamical-scoped-variables-in-python
"""

__all__ = ["dyn"]

from threading import local

_L = local()  # each thread gets its own stack
_L._stack = []

class _EnvBlock(object):
    def __init__(self, kwargs):
        self.kwargs = kwargs
    def __enter__(self):
        _L._stack.append(self.kwargs)
    def __exit__(self, t, v, tb):
        _L._stack.pop()

class _Env(object):
    def __getattr__(self, name):
        for scope in reversed(_L._stack):
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

    runtest()

if __name__ == '__main__':
    test()
