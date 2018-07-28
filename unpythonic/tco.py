#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tail call optimization / explicit continuations.

**AIMS**: Maximize readability of client code with clear, explicit syntax.
Keep this simple, with as little magic as possible.

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

 - In this module, **"jump" is a noun, not a verb**.

   - Returning a ``jump`` instance makes the trampoline perform the tail call.

   - ``jump(f, ...)`` by itself just evaluates to a jump instance, **doing nothing**.

     - If you're getting ``None`` instead of the result of your computation,
       check for ``jump`` where it should be ``return jump``; and then check
       that you're returning your final result normally.

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
     ``trampolined.__call__`` - and the final one where the uncaught exception
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

Beside TCO, trampolining can also be thought of as *explicit continuations*.
Each trampolined function tells the trampoline where to go next, and with what
parameters. All hail lambda, the ultimate GO TO!

Based on a quick test, running a do-nothing loop with this is about 50x slower
than Python's ``for``.

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

    # looping in FP style, with TCO

    @loop
    def s(acc=0, i=0):
        if i == 10:
            return acc
        else:
            return jump(SELF, acc + i, i + 1)
    assert s == 45

    @trampolined
    def dowork(acc=0, i=0):
        if i == 10:
            return acc
        else:
            return jump(dowork, acc + i, i + 1)
    s = dowork()  # must start loop by calling it
    assert s == 45

    out = []
    @loop
    def _(i=0):
        if i < 3:
            out.append(i)
            return jump(SELF, i + 1)
    assert out == [0, 1, 2]

    # this old chestnut:
    funcs = []
    for i in range(3):
        funcs.append(lambda x: i*x)  # always the same "i", which "for" just mutates
    assert [f(10) for f in funcs] == [20, 20, 20]  # not what we wanted!

    # with FP loop:
    funcs = []
    @loop
    def iter(i=0):
        if i < 3:
            funcs.append(lambda x: i*x)  # new "i" each time, no mutation!
            return jump(SELF, i + 1)
    assert [f(10) for f in funcs] == [0, 10, 20]  # yes!

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

**Inspiration**:

  - https://github.com/ActiveState/code/tree/master/recipes/Python/474088_Tail_Call_Optimization_Decorator

    - Based on inspect, lots of magic.

  - https://github.com/baruchel/tco

    - Based on abusing exceptions.

  - https://github.com/fnpy/fn.py/blob/master/fn/recur.py

    - Very clean and simple, same core idea as here. Our main improvement
      over fn.py's is the more natural syntax for the client code.
"""

__all__ = ["SELF", "jump", "trampolined", "loop"]

from unpythonic.misc import immediate

SELF = object()  # sentinel

class jump:
    """A jump (noun, not verb).

    Support class, used in the syntax `return jump(f, ...)` to request the
    trampoline to perform a tail call.

    Instances of `jump` are not callable, and do nothing on their own.
    This is just passive data.
    """
    def __init__(self, target, *args, **kwargs):
        """Constructor.

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
        # IMPORTANT: don't let target bring along its trampoline if it has one
        self.target = target.f if isinstance(target, trampolined) else target
        self.args = args
        self.kwargs = kwargs

class trampolined:
    """Decorator to make a function trampolined.

    Trampolined functions can use ``return jump(f, a, ..., kw=v, ...)``
    to perform optimized tail calls. (*Optimized* in the sense of not
    increasing the call stack depth, not for speed.)
    """
    def __init__(self, f):
        """Constructor.

        Parameters:
            f: function
              The function to decorate.
        """
        self.f = f
    def __call__(self, *args, **kwargs):
        f = self.f
        while True:  # trampoline
            v = f(*args, **kwargs)
            if isinstance(v, jump):
                if v.target is not SELF:  # if SELF, then keep current target
                    f = v.target
                args = v.args
                kwargs = v.kwargs
            else:  # final result, exit trampoline
                return v

def loop(f):
    """Decorator to make a functional loop and run it immediately.

    Chains @trampolined and @immediate::

        @loop
        def s(acc=0, i=0):
            if i == 10:
                return acc
            else:
                return jump(SELF, acc + i, i + 1)
        print(s)

        @loop
        def _(i=0):
            if i < 3:
                print(i)
                return jump(SELF, i + 1)

    The initial values must be set as the defaults, since ``@immediate`` calls
    the function with no arguments.

    The loop body must use SELF instead of the def'd name, because the name
    is not bound until the final decorator (here ``@immediate``) returns,
    at which time it is already too late.

    If that feels inelegant, no need for ``@loop``. These explicit forms
    are also legal::

        @trampolined
        def dowork(acc=0, i=0):
            if i == 10:
                return acc
            else:
                return jump(dowork, acc + i, i + 1)
        s = dowork()  # when using just @trampolined, must start the loop manually
        print(s)

        @trampolined
        def dowork(acc, i):
            if i == 10:
                return acc
            else:
                return jump(dowork, acc + i, i + 1)
        s = dowork(0, 0)
        print(s)
    """
    return immediate(trampolined(f))

def test():
    """Usage examples; see the source code."""
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

    # looping in FP style, with TCO

    @loop
    def s(acc=0, i=0):
        if i == 10:
            return acc
        else:
            return jump(SELF, acc + i, i + 1)
    assert s == 45

    @trampolined
    def dowork(acc=0, i=0):
        if i == 10:
            return acc
        else:
            return jump(dowork, acc + i, i + 1)
    s = dowork()  # must start loop by calling it
    assert s == 45

    out = []
    @loop
    def _(i=0):
        if i < 3:
            out.append(i)
            return jump(SELF, i + 1)
    assert out == [0, 1, 2]

    # this old chestnut:
    funcs = []
    for i in range(3):
        funcs.append(lambda x: i*x)  # always the same "i", which "for" just mutates
    assert [f(10) for f in funcs] == [20, 20, 20]  # not what we wanted!

    # with FP loop:
    funcs = []
    @loop
    def iter(i=0):
        if i < 3:
            funcs.append(lambda x: i*x)  # new "i" each time, no mutation!
            return jump(SELF, i + 1)
    assert [f(10) for f in funcs] == [0, 10, 20]  # yes!

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

    print("All tests PASSED")

    # performance?
    n = 100000
    import time

    t0 = time.time()
    @loop
    def _(i=0):
        if i < n:
            return jump(SELF, i + 1)
    dt_fp = time.time() - t0

    t0 = time.time()
    for i in range(n):
        pass
    dt_ip = time.time() - t0

    print("do-nothing loop, {:d} iterations:".format(n))
    print("  @loop {:g}s ({:g}s/iter)".format(dt_fp, dt_fp/n))
    print("  for {:g}s ({:g}s/iter)".format(dt_ip, dt_ip/n))
    print("@loop slowdown {:g}x".format(dt_fp/dt_ip))

if __name__ == '__main__':
    test()
