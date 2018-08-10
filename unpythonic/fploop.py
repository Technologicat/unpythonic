#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Functional loops with TCO. No mutation of loop variables.

Where this is useful::

    funcs = []
    for i in range(3):
        funcs.append(lambda x: i*x)  # always the same "i", which "for" mutates
    assert [f(10) for f in funcs] == [20, 20, 20]  # not what we wanted!

    @looped_over(range(3), acc=())
    def funcs(loop, i, acc):
        return loop(acc + ((lambda x: i*x),))  # new "i" each time, no mutation
    assert [f(10) for f in funcs] == [0, 10, 20]  # yes!

FP loops don't have to be pure::

    funcs = []
    @looped
    def iter(loop, i=0):
        if i < 3:
            funcs.append(lambda x: i*x)  # cheeky side effect
            return loop(i + 1)
    assert [f(10) for f in funcs] == [0, 10, 20]
"""

__all__ = ["looped", "looped_over", "breakably_looped", "breakably_looped_over"]

from functools import partial

# TCO implementation switchable at runtime
import unpythonic.rc
if unpythonic.rc._tco_impl == "exc":
    from unpythonic.tco import SELF, jump, trampolined, _jump
elif unpythonic.rc._tco_impl == "fast":
    from unpythonic.fasttco import SELF, jump, trampolined, _jump
else:
    raise ValueError("Unknown TCO implementation '{}'".format(unpythonic.rc._tco_impl))

from unpythonic.ec import call_ec

# evil inspect dependency, used only to provide informative error messages.
from unpythonic.arity import arity_includes, UnknownArity

def looped(body):
    """Decorator to make a functional loop and run it immediately.

    This essentially chains @trampolined and @call, with some extra magic.

    Parameters:
        `body`: function
          The function to decorate, representing the loop body.

          The first positional parameter of ``body`` is the magic parameter ``loop``.
          It is "self-ish", representing a jump back to the loop body itself.

          The body may take any additional parameters, both positionally and by name.
          Their initial values must be declared as defaults; @looped automatically
          starts the loop by calling ``body`` with the magic ``loop`` parameter
          as the only argument.

    The expression ``loop(...)`` is otherwise the same as ``jump(SELF, ...)``,
    but it also inserts the magic parameter ``loop``, which can only be set up
    via this mechanism.

    When using ``fasttco``, **loop is a noun, not a verb**, because
    ``unpythonic.tco.jump`` is.

    Simple example::

        @looped
        def result(loop, acc=0, i=0):
            if i == 10:
                return acc
            else:
                return loop(acc + i, i + 1)  # provide the additional parameters
        print(result)

    Imperative body, no meaningful return value::

        @looped
        def _(loop, i=0):
            if i < 3:
                print(i)
                return loop(i + 1)
            # terminated by implicit "return None"

    ``@looped`` is not specifically ``for`` or ``while``, but a general looping
    construct that can express both. FP version of ``while True``::

        @looped
        def _(loop):
            print("Enter your name (or 'q' to quit): ", end='')
            s = input()
            if s.lower() == 'q':
                return  # ...the implicit None. In a "while True:", "break" here.
            else:
                print("Hello, {}!".format(s))
                return loop()

    Strictly, ``@looped`` is just sugar. Consider again the first example.
    These explicit forms are also legal (and slightly faster since no need
    to set up the ``loop`` magic parameter at each iteration)::

        @trampolined
        def s(acc=0, i=0):
            if i == 10:
                return acc
            else:
                return jump(s, acc + i, i + 1)  # or return jump(SELF, ...)
        s = s()  # when using just @trampolined, must start the loop manually
        print(s)

        @trampolined
        def s(acc, i):
            if i == 10:
                return acc
            else:
                return jump(s, acc + i, i + 1)
        s = s(0, 0)
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
    return tb(loop)  # like @call, run the (now trampolined) body.

def breakably_looped(body):
    """Functionally loop over an iterable.

    Like ``@looped``, but the client now gets two positionally passed magic parameters:

        `loop`: function
            Like in ``@looped``.

        `brk`: function
            **Break**. Terminate the loop and return the given value as the return
            value of the loop. Usage: `brk(value)`.

    Additional arguments can be sent to ``return loop(...)``. When the body
    is called, they are appended to the implicit ones, and can be anything.
    Their initial values must be set as defaults in the formal parameter list
    of the body.

    The point of `brk(value)` over just `return value` is that `brk` is
    first-class, so it can be passed on to functions called by the loop body
    (so that those functions then have the power to directly terminate the loop).

    There is no `cnt`, because the concept of *continue* does not make sense at
    this level of abstraction. It is entirely up to the client code to define
    what it even *means* to "proceed to the next iteration". But see
    ``@breakably_looped_over``.

    Example::

        @breakably_looped
        def result(loop, brk, acc=0, i=0):
            if i == 10:
                return brk(acc)  # escape ("return" not mandatory)
            else:
                return loop(acc + i, i + 1)
        print(result)
"""
    @call_ec
    def result(brk):
        def loop(*args, **kwargs):
            return _jump(SELF, (loop, brk) + args, kwargs)  # already packed args, inst directly.
        try:
            if not arity_includes(body, 2):
                raise ValueError("Body arity mismatch. (Are (loop, brk) declared? Do all extra parameters have their defaults set?)")
        except UnknownArity:  # well, we tried!
            pass
        tb = trampolined(body)
        return tb(loop, brk)
    return result

def looped_over(iterable, acc=None):  # decorator factory
    """Functionally loop over an iterable.

    Like ``@looped``, but the client now gets three positionally passed magic parameters:

        `loop`: function
            Like in ``@looped``.

        `x`: anything
            The current element.

        `acc`: anything
            The accumulator. Initially, this is set to the ``acc`` value
            given to ``@looped_over``, and then at each iteration, set to
            the first positional argument sent to ``return loop(...)``,
            if any positional arguments were sent. If not, ``acc``
            retains its last value.

    Additional arguments can be sent to ``return loop(...)``. When the body
    is called, they are appended to the implicit ones, and can be anything.
    Their initial values must be set as defaults in the formal parameter list
    of the body.

    The return value of the loop is always the final value of ``acc``.

    The expression ``loop(...)`` is otherwise the same as ``jump(SELF, ...)``,
    but it also inserts the magic parameters ``loop``, ``x`` and ``acc``,
    which can only be set up via this mechanism.

    When using ``fasttco``, **loop is a noun, not a verb**, just like ``jump``.

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
    # Decorator that plays the role of @call, with "iterable" bound by closure.
    def run(body):
        it = iter(iterable)
        oldacc = acc  # keep track of the last seen value for acc
        # The magic parameter that, when called, inserts the implicit parameters
        # into the positional args of the jump target. Runs between iterations.
        def loop(*args, **kwargs):
            nonlocal oldacc
            newacc = args[0] if len(args) else oldacc
            oldacc = newacc
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

def breakably_looped_over(iterable, acc=None):  # decorator factory
    """Functionally loop over an iterable.

    Like ``@looped_over``, but with *continue* and *break* functionality.
    The loop body takes five magic parameters:

        `loop`: function
        `x`: anything
        `acc`: anything
            Like in ``@looped_over``.

        `cnt`: function
            **Continue**. Proceed to the next element in the iterable, keeping
            the current value of `acc`.

            Essentially, specialized `loop` with the first positional parameter
            set to the current `acc`. Usage: `cnt()` or `cnt(my, extra, params)`.

        `brk`: function
            **Break**. Terminate the loop and return the given value as the return
            value of the loop. Usage: `brk(value)`.

    The point of `brk(value)` over just `return value` is that `brk` is
    first-class, so it can be passed on to functions called by the loop body
    (so that those functions then have the power to directly terminate the loop).

    The point of `cnt(my, extra, params)` over `loop(acc, my, extra, params)`
    is convenience; especially if passing `cnt` to a function, there is no need
    to pass `acc` (or to perform the partial application in the client code).

    Example::

        @breakably_looped_over(range(100), acc=0)
        def s(loop, x, acc, cnt, brk):
            if x < 5:
                return cnt()  # note "return", just like with "loop"
            if x >= 10:
                return brk(acc)  # escape ("return" not mandatory)
            return loop(acc + x)
        assert s == 35
    """
    def run(body):
        it = iter(iterable)
        @call_ec
        def result(brk):
            oldacc = acc
            def loop(*args, **kwargs):
                nonlocal oldacc
                newacc = args[0] if len(args) else oldacc
                oldacc = newacc
                try:
                    newx = next(it)
                except StopIteration:
                    return newacc
                rest = args[1:] if len(args) >= 2 else ()
                cnt = partial(loop, oldacc)
                return _jump(SELF, (loop, newx, newacc, cnt, brk) + rest, kwargs)  # already packed args, inst directly.
            try:
                if not arity_includes(body, 5):
                    raise ValueError("Body arity mismatch. (Are (loop, x, acc, cnt, brk) declared? Do all extra parameters have their defaults set?)")
            except UnknownArity:  # well, we tried!
                pass
            try:
                x0 = next(it)
            except StopIteration:  # empty iterable
                return acc
            tb = trampolined(body)
            return tb(loop, x0, acc, partial(loop, oldacc), brk)
        return result
    return run

def test():
    # basic usage
    @looped
    def s(loop, acc=0, i=0):
        if i == 10:
            return acc
        else:
            return loop(acc + i, i + 1)
    assert s == 45

    # equivalent
    @trampolined
    def dowork(acc=0, i=0):
        if i == 10:
            return acc
        else:
            return jump(dowork, acc + i, i + 1)
    s = dowork()  # must start loop by calling it
    assert s == 45

    # error cases
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

    # impure FP loop
    out = []
    @looped
    def _(loop, i=0):
        if i < 3:
            out.append(i)
            return loop(i + 1)
    assert out == [0, 1, 2]

    # FP loop over iterable
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

    # the old chestnut
    funcs = []
    for i in range(3):
        funcs.append(lambda x: i*x)  # always the same "i", which "for" just mutates
    assert [f(10) for f in funcs] == [20, 20, 20]  # not what we wanted!

    @looped_over(range(3), acc=())
    def funcs(loop, i, acc):
        return loop(acc + ((lambda x: i*x),))  # new "i" each time, no mutation!
    assert [f(10) for f in funcs] == [0, 10, 20]  # yes!

    funcs = []
    @looped
    def _(loop, i=0):
        if i < 3:
            funcs.append(lambda x: i*x)  # new "i" each time, no mutation!
            return loop(i + 1)
    assert [f(10) for f in funcs] == [0, 10, 20]  # yes!

    # escape surrounding function from inside FP loop
    from unpythonic.ec import setescape, escape
    from unpythonic.misc import call
    @setescape()
    def f():
        @looped
        def s(loop, acc=0, i=0):
            if i > 5:
                escape(acc)
            return loop(acc + i, i + 1)
        print("not reached")
        return False
    assert f() == 15

    # setescape point tags can be single value or tuple (tuples OR'd, like isinstance())
    @setescape(tags="foo")
    def foo():
        @call
        @setescape(tags="bar")
        def bar():
            @looped
            def s(loop, acc=0, i=0):
                if i > 5:
                    escape(acc, tag="foo")  # escape instance tag must be a single value
                return loop(acc + i, i + 1)
            print("never reached")
            return False
        print("never reached either")
        return False
    assert foo() == 15

    # break
    @breakably_looped
    def result(loop, brk, acc=0, i=0):
        if i == 10:
            return brk(acc)
        else:
            return loop(acc + i, i + 1)  # provide the additional parameters
    assert result == 45

    # break, continue
    @breakably_looped_over(range(100), acc=0)
    def s(loop, x, acc, cnt, brk):
        if x < 5:
            return cnt()  # trampolined jump; default newacc=acc
        if x >= 10:
            return brk(acc)  # escape; must specify return value
        return loop(acc + x)
    assert s == 35

    @breakably_looped_over(range(100), acc=0)
    def s(loop, x, acc, cnt, brk):
        if x >= 10:
            return brk(acc)
        if x > 5:
            return cnt()
        return loop(acc + x)
    assert s == 15

    print("All tests PASSED")

    # loop performance?
    n = 100000
    import time

    t0 = time.time()
    for i in range(n):
        pass
    dt_ip = time.time() - t0

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
    print("  @looped {:g}s ({:g}s/iter)".format(dt_fp2, dt_fp2/n))
    print("  @looped_over {:g}s ({:g}s/iter)".format(dt_fp3, dt_fp3/n))
    print("@looped slowdown {:g}x".format(dt_fp2/dt_ip))
    print("@looped_over slowdown {:g}x".format(dt_fp3/dt_ip))

if __name__ == '__main__':
    test()
