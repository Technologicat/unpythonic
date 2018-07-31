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

SELF actually means "keep current target", so the last function that was
explicitly named in that trampoline remains as the target. When the trampoline
starts, the current target is set to the initial entry point (also for lambdas).

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

    @looped
    def s(loop, acc=0, i=0):
        if i == 10:
            return acc
        else:
            return loop(acc + i, i + 1)  # same as return jump(SELF, acc+i, i+1)
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
    @looped
    def _(loop, i=0):
        if i < 3:
            out.append(i)
            return loop(i + 1)
    assert out == [0, 1, 2]

    # this old chestnut:
    funcs = []
    for i in range(3):
        funcs.append(lambda x: i*x)  # always the same "i", which "for" just mutates
    assert [f(10) for f in funcs] == [20, 20, 20]  # not what we wanted!

    # with FP loop:
    funcs = []
    @looped
    def iter(loop, i=0):
        if i < 3:
            funcs.append(lambda x: i*x)  # new "i" each time, no mutation!
            return loop(i + 1)
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

__all__ = ["SELF", "jump", "trampolined", "looped", "looped_over"]

from functools import wraps

from unpythonic.misc import immediate
from unpythonic.ec import escape

# evil inspect dependency, used only to provide informative error messages.
from unpythonic.arity import arity_includes, UnknownArity

@immediate  # immediate a class to make a singleton
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
            elif isinstance(v, escape):  # allow lambdas to use escape
                raise v
            else:  # final result, exit trampoline
                return v
    # fortunately functions in Python are just objects; stash for jump constructor
    decorated._entrypoint = function
    return decorated

def looped(body):
    """Decorator to make a functional loop and run it immediately.

    Parameters:
        body: function
          The function to decorate, representing the loop body.

    This essentially chains @trampolined and @immediate, with some extra magic::

        @looped
        def result(loop, acc=0, i=0):
            if i == 10:
                return acc
            else:
                return loop(acc + i, i + 1)
        print(result)

        @looped
        def _(loop, i=0):
            if i < 3:
                print(i)
                return loop(i + 1)

    The first positional parameter is the magic parameter ``loop``.
    It is "self-ish", representing a jump back to the loop body itself.

    Here **loop is a noun, not a verb.** The expression ``loop(...)`` is
    otherwise the same as ``jump(SELF, ...)``, but it also inserts the magic
    parameter ``loop``, which can only be set up via this mechanism.

    The initial values for any other parameters must be set as the defaults.
    @looped automatically starts the loop body by calling it with the magic
    ``loop`` parameter as the only argument.

    If this feels inelegant, no need for ``@looped``. These explicit forms
    are also legal (and slightly faster since no work to set up the ``loop``
    magic parameter at each iteration)::

        @trampolined
        def dowork(acc=0, i=0):
            if i == 10:
                return acc
            else:
                return jump(dowork, acc + i, i + 1)  # or return jump(SELF, ...)
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
    # The magic parameter that, when called, inserts itself into the
    # positional args of the jump target.
    def loop(*args, **kwargs):
        # This jump works because SELF actually means "keep current target".
        # The client calls loop() normally, so the trampoline doesn't register us;
        # hence the client itself remains as the current target.
        return _jump(SELF, (loop,) + args, kwargs)  # already packed args, inst directly.
    try:
        if not arity_includes(body, 1):
            raise ValueError("Body arity mismatch. (Is 'loop' parameter declared? Do all extra parameters have their defaults set?)")
    except UnknownArity:  # well, we tried!
        pass
    tb = trampolined(body)  # enable "return jump(...)"
    return tb(loop)  # like @immediate, run the (now trampolined) body.

def looped_over(iterable, acc=None):  # decorator factory
    """Functionally loop over an iterable.

    Like ``@looped``, but the client now gets three positionally passed magic parameters:

        `loop`: function
            Like in ``@looped``.

        `x`: anything
            The current element.

        `acc`: anything
            The accumulator. Initially, this is set to the ``acc`` value
            given to ``@looped_over``, and then reset at each iteration
            to the first positional argument sent to ``return loop(...)``,
            if any positional arguments were sent. (If not, ``acc``
            is reset to its initial value.)

    Additional arguments can be sent to ``return loop(...)``. When the body is
    called, they are appended to the three implicit ones, and can be anything.
    Their initial values must be set as defaults in the formal parameter list
    of the body.

    The return value of the loop is always the final value of ``acc``.

    Here **loop is a noun, not a verb.** The expression ``loop(...)`` is
    otherwise the same as ``jump(SELF, ...)``, but it also inserts the magic
    parameters ``loop``, ``x`` and ``acc``, which can only be set up via
    this mechanism.

    Examples::

        @looped_over(range(10), acc=0)
        def s(loop, x, acc):
            return loop(acc + x)
        assert s == 45

        def map(function, iterable):
            @looped_over(iterable, acc=[])
            def out(loop, x, acc):
                return loop(acc + [function(x)])
            return out
        assert map(lambda x: 2*x, range(3)) == [0, 2, 4]

    For lambdas this is a bit unwieldy. Equivalent with the first example above::

        r10 = looped_over(range(10), acc=0)
        s = r10(lambda loop, x, acc:
                  loop(acc + x))
        assert s == 45

    If you **really** need to make that into an expression, bind ``r10`` using ``let``,
    or to make your code unreadable, just inline it.
    """
    # Decorator that plays the role of @immediate, with "iterable" bound by closure.
    def run(body):
        it = iter(iterable)
        # The magic parameter that, when called, inserts the implicit parameters
        # into the positional args of the jump target. Runs between iterations.
        def loop(*args, **kwargs):
            newacc = args[0] if len(args) else acc
            try:
                newx = next(it)
            except StopIteration:
                return newacc
            rest = args[1:] if len(args) >= 2 else ()
            return _jump(SELF, (loop, newx, newacc) + rest, kwargs)  # already packed args, inst directly.
        try:
            if not arity_includes(body, 3):
                raise ValueError("Body arity mismatch. (Are (loop, x, acc) declared? Do all extra parameters have their defaults set?)")
        except UnknownArity:  # well, we tried!
            pass
        try:
            x0 = next(it)
        except StopIteration:  # empty iterable
            return acc
        tb = trampolined(body)
        return tb(loop, x0, acc)
    return run

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

    @looped
    def s(loop, acc=0, i=0):
        if i == 10:
            return acc
        else:
            return loop(acc + i, i + 1)
    assert s == 45

    try:
        @looped
        def s():  # invalid definition, no loop parameter
            pass
    except ValueError:
        pass
    else:
        assert False

    try:
        @looped
        def s(loop, myextra):  # invalid definition, extra parameter not initialized
            pass
    except ValueError:
        pass
    else:
        assert False

    try:
        @looped_over(range(10), acc=())
        def s():  # invalid definition, no (loop, x, acc)
            pass
    except ValueError:
        pass
    else:
        assert False

    try:
        @looped_over(range(10), acc=())
        def s(loop, x):  # invalid definition, no acc
            pass
    except ValueError:
        pass
    else:
        assert False

    try:
        @looped_over(range(10), acc=())
        def s(loop, x, acc, myextra):  # invalid definition, myextra not initialized
            pass
    except ValueError:
        pass
    else:
        assert False


    @trampolined
    def dowork(acc=0, i=0):
        if i == 10:
            return acc
        else:
            return jump(dowork, acc + i, i + 1)
    s = dowork()  # must start loop by calling it
    assert s == 45

    out = []
    @looped
    def _(loop, i=0):
        if i < 3:
            out.append(i)
            return loop(i + 1)
    assert out == [0, 1, 2]

    @looped_over(zip((1, 2, 3), ('a', 'b', 'c')), acc=())
    def p(loop, item, acc):
        numb, lett = item
        return loop(acc + ("{:d}{:s}".format(numb, lett),))
    assert p == ('1a', '2b', '3c')

    @looped_over(enumerate(zip((1, 2, 3), ('a', 'b', 'c'))), acc=())
    def q(loop, item, acc):
        idx, (numb, lett) = item
        return loop(acc + ("Item {:d}: {:d}{:s}".format(idx, numb, lett),))
    assert q == ('Item 0: 1a', 'Item 1: 2b', 'Item 2: 3c')

    @looped_over(range(1, 4), acc=[])
    def outer_result(outer_loop, y, outer_acc):
        @looped_over(range(1, 3), acc=[])
        def inner_result(inner_loop, x, inner_acc):
            return inner_loop(inner_acc + [y*x])
        return outer_loop(outer_acc + [inner_result])
    assert outer_result == [[1, 2], [2, 4], [3, 6]]

    # this old chestnut:
    funcs = []
    for i in range(3):
        funcs.append(lambda x: i*x)  # always the same "i", which "for" just mutates
    assert [f(10) for f in funcs] == [20, 20, 20]  # not what we wanted!

    # with FP loop:
    @looped_over(range(3), acc=())
    def funcs(loop, i, acc):
        return loop(acc + ((lambda x: i*x),))  # new "i" each time, no mutation!
    assert [f(10) for f in funcs] == [0, 10, 20]  # yes!

    # FP loop, using the more primitive @looped:
    funcs = []
    @looped
    def _(loop, i=0):
        if i < 3:
            funcs.append(lambda x: i*x)  # new "i" each time, no mutation!
            return loop(i + 1)
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

    # escape surrounding function from inside FP loop
    from unpythonic.ec import setescape
    @setescape()
    def f():
        @looped
        def s(loop, acc=0, i=0):
            if i > 5:
                return escape(acc)  # trampolined functions may also "return escape(...)"
            return loop(acc + i, i + 1)
        print("not reached")
        return False
    assert f() == 15

    # setescape point tag can be single value or tuple (tuples OR'd, like isinstance())
    @setescape(tag="foo")
    def foo():
        @immediate
        @setescape(tag="bar")
        def bar():
            @looped
            def s(loop, acc=0, i=0):
                if i > 5:
                    return escape(acc, tag="foo")  # escape instance tag must be a single value
                return loop(acc + i, i + 1)
            print("never reached")
            return False
        print("never reached either")
        return False
    assert foo() == 15

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
            return jump(dowork, i + 1)
    dowork()
    dt_fp1 = time.time() - t0

    t0 = time.time()
    @looped
    def _(loop, i=0):
        if i < n:
            return loop(i + 1)
    dt_fp2 = time.time() - t0

    t0 = time.time()
    @looped_over(range(n))  # no need for acc, not interested in it
    def _(loop, x, acc):    # but body always takes at least these three parameters
        return loop()
    dt_fp3 = time.time() - t0

    print("do-nothing loop, {:d} iterations:".format(n))
    print("  builtin for {:g}s ({:g}s/iter)".format(dt_ip, dt_ip/n))
    print("  @trampolined {:g}s ({:g}s/iter)".format(dt_fp1, dt_fp1/n))
    print("  @looped {:g}s ({:g}s/iter)".format(dt_fp2, dt_fp2/n))
    print("  @looped_over {:g}s ({:g}s/iter)".format(dt_fp3, dt_fp3/n))
    print("@trampolined slowdown {:g}x".format(dt_fp1/dt_ip))
    print("@looped slowdown {:g}x".format(dt_fp2/dt_ip))
    print("@looped_over slowdown {:g}x".format(dt_fp3/dt_ip))

if __name__ == '__main__':
    test()
