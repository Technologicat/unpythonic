#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Exception-based TCO.

This is a drop-in replacement for ``tco.py``; feel free to use this version
if you prefer. For docs, see ``tco.py``.

The only difference in the API is:

  - ``jump`` **is now a verb**. No need for ``return jump(...)`` to denote
    a tail call, a bare ``jump(...)`` will do.

  - Using ``return jump(...)`` does no harm, though, so do that if you want
    your code to remain compatible with both TCO implementations.

If you change ``fploop.py`` to load this implementation, then the magic ``loop``
becomes a verb, too, because it is essentially a fancy wrapper over ``jump``.

But be careful, the TCO implementations **cannot be mixed and matched**.

Based on a quick test, running a do-nothing loop with this is about 150-200x
slower than Python's ``for``. Or in other words, the additional performance hit
is somewhere between 2-5x.
"""

from functools import wraps

from unpythonic.misc import call

__all__ = ["jump", "trampolined", "SELF"]

@call  # make a singleton
class SELF:
    def __repr__(self):
        return "SELF"

def jump(target, *args, **kwargs):
    """arg packer, public API. Invokes ``_jump``."""
    return _jump(target, args, kwargs)

def _jump(target, args, kwargs):  # implementation
    """Jump (verb) to target function with given args and kwargs.

    Only valid when running in a trampoline.
    """
    raise TrampolinedJump(target, args, kwargs)

class TrampolinedJump(Exception):
    """Exception representing a jump (noun).

    Raised by ``_jump``, caught by the trampoline.

    Prints an informative message if uncaught (i.e. if no trampoline).
    """
    def __init__(self, target, args, kwargs):
        if hasattr(target, "_entrypoint"):  # strip target's trampoline if any
            target = target._entrypoint

        self.target = target
        self.targs = args
        self.tkwargs = kwargs

        # Error message when uncaught
        # (This can still be caught by the wrong trampoline, if an inner trampoline
        #  has been forgotten when nesting TCO chains - there's nothing we can do
        #  about that.)
        self.args = ("No trampoline, attempted to jump to '{}', args {}, kwargs {}".format(target,
                                                                                           args,
                                                                                           kwargs),)

    def __repr__(self):
        return "<TrampolinedJump at 0x{:x}: target={}, args={}, kwargs={}".format(id(self),
                                                                                  self.target,
                                                                                  self.targs,
                                                                                  self.tkwargs)

def trampolined(function):
    """Decorator to make a function trampolined.

    Trampolined functions can use ``jump(f, a, ..., kw=v, ...)``
    to perform optimized tail calls. (*Optimized* in the sense of not
    increasing the call stack depth, not for speed.)
    """
    @wraps(function)
    def decorated(*args, **kwargs):
        f = function
        while True:  # trampoline
            try:
                v = f(*args, **kwargs)
                return v  # final result, exit trampoline
            except TrampolinedJump as jmp:
                if jmp.target is not SELF:  # if SELF, then keep current target
                    f = jmp.target
                args = jmp.targs
                kwargs = jmp.tkwargs
    # fortunately functions in Python are just objects; stash for TrampolinedJump constructor
    decorated._entrypoint = function
    return decorated

def test():
    # tail recursion
    @trampolined
    def fact(n, acc=1):
        if n == 0:
            return acc
        else:
            jump(fact, n - 1, n * acc)
    assert fact(4) == 24

    # tail recursion in a lambda
    t = trampolined(lambda n, acc=1:
                        acc if n == 0 else jump(SELF, n - 1, n * acc))
    assert t(4) == 24

    # mutual recursion
    @trampolined
    def even(n):
        if n == 0:
            return True
        else:
            jump(odd, n - 1)
    @trampolined
    def odd(n):
        if n == 0:
            return False
        else:
            jump(even, n - 1)
    assert even(42) is True
    assert odd(4) is False
    assert even(10000) is True  # no crash

    try:
        jump(even, 10)
    except TrampolinedJump:  # should raise this if no trampoline
        pass
    else:
        assert False

    print("All tests PASSED")

    # loop performance?
    n = 100000
    import time

    t0 = time.time()
    for i in range(n):
        pass
    dt_ip = time.time() - t0

    t0 = time.time()
    @trampolined
    def dowork(i=0):
        if i < n:
            jump(dowork, i + 1)
    dowork()
    dt_fp1 = time.time() - t0

    print("do-nothing loop, {:d} iterations:".format(n))
    print("  builtin for {:g}s ({:g}s/iter)".format(dt_ip, dt_ip/n))
    print("  @trampolined {:g}s ({:g}s/iter)".format(dt_fp1, dt_fp1/n))
    print("@trampolined slowdown {:g}x".format(dt_fp1/dt_ip))

if __name__ == '__main__':
    test()
