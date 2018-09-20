#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tail call optimization / explicit continuations.

Where speed matters, prefer the usual ``for`` and ``while`` constructs.
Where speed *really* matters, add Cython on top of those. And as always,
profile first.

**API reference**:

 - Functions that use TCO must be ``@trampolined``. They are called just like
   any normal function.

 - When inside a ``@trampolined`` function:

   - ``f(a, ..., kw=v, ...)`` is just a normal call, no TCO.

   - ``return jump(f, a, ..., kw=v, ...)`` is a tail call to *target* ``f``.

     - `return` explicitly marks a tail position, naturally enforcing that
       the caller finishes immediately after its purported *tail* call.

   - When done (no more tail calls to make), just return the final result normally.

 - In this implementation, **"jump" is a noun, not a verb**.

   - Returning a ``jump`` instance makes the trampoline perform the tail call.

   - ``jump(f, ...)`` by itself just evaluates to a jump instance, **doing nothing**.

     - If you're getting ``None`` instead of the result of your computation,
       check for ``jump`` where it should be ``return jump``; and then check
       that you're returning your final result normally.

       Most often you'll get "unclaimed jump" warnings printed to stderr if you
       run into this.

 - **Lambdas welcome!** For example, ``trampolined(lambda x: ...)``.

   - Just keep in mind how Python expands the decorator syntax; the rest follows.

   - Use the special target ``SELF``, as in ``jump(SELF, ...)``, for tail recursion.

     - Just ``jump``, not ``return jump``, since lambdas do not use ``return``.

   - Or assign the lambda expressions to names; this allows also mutual recursion.

 - **Use only where TCO matters**. Stack traces will be hurt, as usual.

   - Tail recursion is a good use case; so is mutual recursion. Here TCO allows
     elegantly expressed algorithms without blowing the stack.

   - Danger zone is if one applies TCO just because some call happens to be
     in a tail position. This makes debugging a nightmare, since some entries
     will be missing from the call stack.

     This implementation retains the original entry point - due to entering
     the decorator ``trampolined`` - and the final one where the uncaught exception
     actually occurred. Anything in between will have been zapped by TCO.

**Notes**:

Actually it is sufficient that the initial entry point to a computation using
TCO is ``@trampolined``. The trampoline keeps running until a normal value
(i.e. anything that is not a ``jump`` instance) is returned. That normal value
is returned to the original caller.

The ``jump`` constructor automatically strips the target's trampoline,
if it has one - making sure this remains a one-trampoline party even if
the tail-call target is another ``@trampolined`` function. So just declare
anything using TCO as ``@trampolined`` and don't worry about stacking trampolines.

SELF actually means "keep current target", so the last function that was
jumped to by name in that trampoline remains as the target. When the trampoline
starts, the current target is set to the initial entry point (also for lambdas).

Beside TCO, trampolining can also be thought of as *explicit continuations*.
Each trampolined function tells the trampoline where to go next, and with what
parameters. All hail lambda, the ultimate GO TO!

Based on a quick test, running a do-nothing loop with this is about 40-80x
slower than Python's ``for``.

**Examples**::

    # tail recursion
    @trampolined
    def fact(n, acc=1):
        if n == 0:
            return acc
        else:
            return jump(fact, n - 1, n * acc)
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
            return jump(odd, n - 1)
    @trampolined
    def odd(n):
        if n == 0:
            return False
        else:
            return jump(even, n - 1)
    assert even(42) is True
    assert odd(4) is False

    # explicit continuations - DANGER: functional spaghetti code!
    @trampolined
    def foo():
        return jump(bar)
    @trampolined
    def bar():
        return jump(baz)
    @trampolined
    def baz():
        raise RuntimeError("Look at the call stack, where did bar() go?")
    try:
        foo()
    except RuntimeError:
        pass
"""

__all__ = ["SELF", "jump", "trampolined"]

from functools import wraps
from sys import stderr

from unpythonic.misc import call

@call  # make a singleton
class SELF:  # sentinel, could be any object but we want a nice __repr__.
    def __repr__(self):
        return "SELF"

def jump(target, *args, **kwargs):
    """A jump (noun, not verb).

    Used in the syntax `return jump(f, ...)` to request the trampoline to
    perform a tail call.

    Instances of `jump` are not callable, and do nothing on their own.
    This is just passive data.

    Parameters:
        target:
            The function to be called. The special value SELF means
            tail-recursion; useful with a ``lambda``. When the target
            has a name, it is legal to explicitly give the name also
            for tail-recursion.
        *args:
            Positional arguments to be passed to `target`.
        **kwargs:
            Named arguments to be passed to  `target`.
    """
    return _jump(target, args, kwargs)

class _jump:
    """The actual class representing a jump.

    If you have already packed args and kwargs, you can instantiate this
    directly; the public API just performs the packing.
    """
    def __init__(self, target, args, kwargs):
        # IMPORTANT: don't let target bring along its trampoline if it has one
        self.target = target._entrypoint if hasattr(target, "_entrypoint") else target
        self.args = args
        self.kwargs = kwargs
        self._claimed = False  # set when the instance is caught by a trampoline

    def __repr__(self):
        return "<_jump at 0x{:x}: target={}, args={}, kwargs={}".format(id(self),
                                                                        self.target,
                                                                        self.args,
                                                                        self.kwargs)

    def __del__(self):
        """Warn about bugs in client code.

        Since it's ``__del__``, we can't raise any exceptions - which includes
        things such as ``AssertionError`` and ``SystemExit``. So we print a
        warning.

        **CAUTION**:

            This warning mechanism should help find bugs, but it is not 100% foolproof.
            Since ``__del__`` is managed by Python's GC, some object instances may
            not get their ``__del__`` called when the Python interpreter itself exits
            (if those instances are still alive at that time).

        **Typical causes**:

        *Missing "return"*::

            @trampolined
            def foo():
                jump(bar, 42)

        The jump instance was never actually passed to the trampoline; it was
        just created and discarded. The trampoline got the ``None`` from the
        implicit ``return None`` at the end of the function.

        (See ``tco.py`` if you prefer this syntax, without a ``return``.)

        *No trampoline*::

            def foo():
                return jump(bar, 42)

        Here ``foo`` is not trampolined.

        We **have** a trampoline when the function that returns the jump
        instance is itself ``@trampolined``, or is running in a trampoline
        implicitly (due to having been entered via a tail call).

        *Trampoline at the wrong level*::

            @trampolined
            def foo():
                def bar():
                    return jump(qux, 23)
                bar()  # normal call, no TCO

        Here ``bar`` has no trampoline; only ``foo`` does. **Only** a ``@trampolined``
        function, or a function entered via a tail call, may return a jump.
        """
        if not self._claimed:
            print("WARNING: unclaimed {}".format(repr(self)), file=stderr)

# We want @wraps to preserve docstrings, so the decorator must be a function, not a class.
# https://stackoverflow.com/questions/6394511/python-functools-wraps-equivalent-for-classes
# https://stackoverflow.com/questions/25973376/functools-update-wrapper-doesnt-work-properly#25973438
def trampolined(function):
    """Decorator to make a function trampolined.

    Trampolined functions can use ``return jump(f, a, ..., kw=v, ...)``
    to perform optimized tail calls. (*Optimized* in the sense of not
    increasing the call stack depth, not for speed.)
    """
    @wraps(function)
    def decorated(*args, **kwargs):
        f = function
        while True:  # trampoline
            v = f(*args, **kwargs)
            if isinstance(v, _jump):
                if v.target is not SELF:  # if SELF, then keep current target
                    f = v.target
                args = v.args
                kwargs = v.kwargs
                v._claimed = True
            else:  # final result, exit trampoline
                return v
    # fortunately functions in Python are just objects; stash for jump constructor
    decorated._entrypoint = function
    return decorated

def test():
    # tail recursion
    @trampolined
    def fact(n, acc=1):
        if n == 0:
            return acc
        return jump(fact, n - 1, n * acc)
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
        return jump(odd, n - 1)
    @trampolined
    def odd(n):
        if n == 0:
            return False
        return jump(even, n - 1)
    assert even(42) is True
    assert odd(4) is False
    assert even(10000) is True  # no crash

    # explicit continuations - DANGER: functional spaghetti code!
    @trampolined
    def foo():
        return jump(bar)
    @trampolined
    def bar():
        return jump(baz)
    @trampolined
    def baz():
        raise RuntimeError("Look at the call stack, bar() was zapped by TCO!")
    try:
        foo()
    except RuntimeError:
        pass

    # trampolined lambdas in a letrec
    from unpythonic.let import letrec
    t = letrec(evenp=lambda e:
                     trampolined(lambda x:
                                   (x == 0) or jump(e.oddp, x - 1)),
             oddp=lambda e:
                     trampolined(lambda x:
                                   (x != 0) and jump(e.evenp, x - 1)),
             body=lambda e:
                     e.evenp(10000))
    assert t is True

    print("All tests PASSED")

    print("*** These two error cases SHOULD PRINT A WARNING:", file=stderr)
    print("** No surrounding trampoline:", file=stderr)
    def bar2():
        pass
    def foo2():
        return jump(bar2)
    foo2()
    print("** Missing 'return' in 'return jump':", file=stderr)
    def foo3():
        jump(bar2)
    foo3()

    # loop performance?
    n = 100000
    import time

    t0 = time.time()
    for _ in range(n):
        pass
    dt_ip = time.time() - t0

    t0 = time.time()
    @trampolined
    def dowork(i=0):
        if i < n:
            return jump(dowork, i + 1)
    dowork()
    dt_fp1 = time.time() - t0

    print("do-nothing loop, {:d} iterations:".format(n))
    print("  builtin for {:g}s ({:g}s/iter)".format(dt_ip, dt_ip/n))
    print("  @trampolined {:g}s ({:g}s/iter)".format(dt_fp1, dt_fp1/n))
    print("@trampolined slowdown {:g}x".format(dt_fp1/dt_ip))

if __name__ == '__main__':
    test()
