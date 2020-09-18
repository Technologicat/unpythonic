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

   - For tail recursion, use ``unpythonic.fun.withself`` (see below for an example).

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
    t = trampolined(withself(lambda self, n, acc=1:
                               acc if n == 0 else jump(self, n - 1, n * acc)))
    assert t(4) == 24
    t(5000)  # no crash

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
        raise RuntimeError("Look at the call stack, bar() was zapped by TCO!")
    try:
        foo()
    except RuntimeError:
        pass
"""

__all__ = ["jump", "trampolined"]

from functools import wraps
from sys import stderr

from .regutil import register_decorator
from .lazyutil import islazy, passthrough_lazy_args, maybe_force_args
from .dynassign import dyn

# In principle, jump should have @passthrough_lazy_args, but for performance reasons
# it doesn't. "force(target)" is slow, so strict code shouldn't have to do that.
# This is handled by a special case in maybe_force_args.
def jump(target, *args, **kwargs):
    """A jump (noun, not verb).

    Used in the syntax `return jump(f, ...)` to request the trampoline to
    perform a tail call.

    Instances of `jump` are not callable, and do nothing on their own.
    This is just passive data.

    Parameters:
        target:
            The function to be called.
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
        return "<_jump at 0x{:x}: target={}, args={}, kwargs={}>".format(id(self),
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
            # We can't raise exceptions in __del__, but at least on Linux we can terminate the process. ;)
            # Not sure if that's a good idea, though...
            # https://stackoverflow.com/questions/905189/why-does-sys-exit-not-exit-when-called-inside-a-thread-in-python
            # import os
            # import signal
            # os.kill(os.getpid(), signal.SIGTERM)

# We want @wraps to preserve docstrings, so the decorator must be a function, not a class.
# https://stackoverflow.com/questions/6394511/python-functools-wraps-equivalent-for-classes
# https://stackoverflow.com/questions/25973376/functools-update-wrapper-doesnt-work-properly#25973438
@register_decorator(priority=40, istco=True)
def trampolined(function):
    """Decorator to make a function trampolined.

    Trampolined functions can use ``return jump(f, a, ..., kw=v, ...)``
    to perform optimized tail calls. (*Optimized* in the sense of not
    increasing the call stack depth, not for speed.)
    """
    if not dyn._build_lazy_trampoline:
        # building a trampoline for regular strict code
        @wraps(function)
        def trampoline(*args, **kwargs):
            f = function
            while True:
                if callable(f):  # general case
                    v = f(*args, **kwargs)
                else:  # inert-data return value from call_ec or similar
                    v = f
                if isinstance(v, _jump):
                    f = v.target
                    if not callable(f):  # protect against jump() to inert data from call_ec or similar
                        raise RuntimeError("Cannot jump into a non-callable value {}".format(repr(f)))
                    args = v.args
                    kwargs = v.kwargs
                    v._claimed = True
                else:  # final result, exit trampoline
                    return v
        # Work together with call_ec and other do-it-now decorators.
        #
        # The function has already been replaced by its return value. E.g. call_ec
        # must work that way, because the ec is only valid during the dynamic extent
        # of the call_ec. OTOH, the trampoline must be **outside**, to be able to
        # catch a jump() from the result of the call_ec. So we treat a non-callable
        # "function" as an inert-data return value.
        if callable(function):
            # fortunately functions in Python are just objects; stash for jump constructor
            trampoline._entrypoint = function
            return trampoline
        else:  # return value from call_ec or similar do-it-now decorator
            return trampoline()
    else:
        # Exact same code as above, except has the lazify-aware stuff.
        # This is to avoid a drastic (~10x) performance hit in trampolines
        # built for regular strict code.
        @wraps(function)
        def trampoline(*args, **kwargs):
            f = function
            while True:
                if callable(f):  # the maybe_force_args here causes the performance hit
                    v = maybe_force_args(f, *args, **kwargs)    # <--
                else:
                    v = f
                if isinstance(v, _jump):
                    f = v.target
                    if not callable(f):
                        raise RuntimeError("Cannot jump into a non-callable value {}".format(repr(f)))
                    args = v.args
                    kwargs = v.kwargs
                    v._claimed = True
                else:  # final result, exit trampoline
                    return v
        if callable(function):
            trampoline._entrypoint = function
            # Mark the trampolined function for passthrough of lazy args if the
            # original function has the mark. This is needed because the mark is
            # implemented as an attribute on the function object.
            if islazy(function):                                # <--
                trampoline = passthrough_lazy_args(trampoline)  # <--
            return trampoline
        else:
            return trampoline()
