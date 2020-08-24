# -*- coding: utf-8 -*-
"""Escape continuations, i.e. jumping outward on the call stack.

First see `call_ec`, which works like `call/ec` in Scheme and Racket. If you
want more detailed control, see `catch` and `throw`.

**Etymology**:

The `catch`/`throw` functions are named after the `catch`/`throw` construct in
Emacs Lisp and several precursors of Common Lisp, so this terminology dates
from the mid-1980s, at the latest.

Semantically this has nothing to do with exception handling, except that both
are essentially a goto outward on the call stack. These names that are standard
for this functionality in the Lisp family just happened to be available in
Python, since Python's exception mechanism has chosen to use `except`/`raise`
as its keywords.

Common Lisp retains the `CATCH`/`THROW` construct, but there it is nowadays
more idiomatic to use the lexically scoped variant `BLOCK`/`RETURN-FROM`
(which we do not provide here).

See Peter Seibel: Practical Common Lisp, chapter 20:
    http://www.gigamonkeys.com/book/the-special-operators.html
"""

__all__ = ["throw", "catch", "call_ec",
           "setescape", "escape"]  # old names, pre-0.14.2, will go away in 0.15.0

from warnings import warn
from functools import wraps

from .regutil import register_decorator
# from .symbol import gensym

def escape(value, tag=None, allow_catchall=True):  # pragma: no cover
    """Alias for `throw`, for backward compatibility.

    Will be removed in 0.15.0.
    """
    warn("`escape` has been renamed `throw` as in Common Lisp; this alias will be removed in 0.15.0.", FutureWarning)
    return throw(value, tag, allow_catchall)

def setescape(tags=None, catch_untagged=True):  # pragma: no cover
    """Alias for `catch`, for backward compatibility.

    Will be removed in 0.15.0.
    """
    warn("`setescape` has been renamed `catch` as in Common Lisp; this alias will be removed in 0.15.0.", FutureWarning)
    return catch(tags, catch_untagged)

def throw(value, tag=None, allow_catchall=True):
    """Escape to a dynamically surrounding ``@catch``.

    Essentially this just raises an ``Escape`` instance with the given arguments.
    Wrapping the raise in a function call allows also lambdas to use escapes.

    For the ``throw`` to work, we must be inside the dynamic extent
    of the intended ``@catch``.

    Parameters:

        value: anything
            The value to send to the ``@catch``.

        tag: anything comparable with ``==``
            Can be used to restrict which ``@catch`` may catch
            this `throw`. Default ``None``, meaning "no tag".

        allow_catchall: bool
            Whether untagged "catch-all" ``@catch`` may catch
            this `throw` (regardless of tag!).

            Even if ``False``, if ``tag`` is ``None``, a ``@catch``
            point may still override this with ``catch_untagged=True``.
            (See the table in ``help(catch)``, case ``b0``.)
    """
    raise Escape(value, tag, allow_catchall)

class Escape(Exception):
    """Exception that essentially represents the invocation of an escape continuation.

    Constructor parameters: see ``throw()``.
    """
    def __init__(self, value, tag=None, allow_catchall=True):
        self.value = value
        self.tag = tag
        self.allow_catchall = allow_catchall

        # Error message when uncaught
        self.args = ("Not within the dynamic extent of a @catch",)

def catch(tags=None, catch_untagged=True):
    """Decorator. Mark function as exitable by ``throw(value)``.

    In Lisp terms, this essentially captures the escape continuation (ec)
    of the decorated function. The ec can then be invoked by ``throw(value)``.

    Technically, this is a decorator factory, since we take parameters.

    Parameters:
        tags: ``t``, or tuple of ``t``
          where ``t`` is anything comparable with ``==``
            A tuple is OR'd, like in ``isinstance()``.

            Restrict which ``throw`` will be caught by this ``@catch``.

        catch_untagged: bool
            Whether this ``@catch`` catches untagged throws.

            Even if ``False``, if ``tags`` is ``None``, a ``throw``
            may still override this with ``allow_catchall=True``.
            (See the table below, case ``a1``.)

    The exact catch condition is::

        # e is an Escape instance
        if (tags is None and e.allow_catchall) or
           (catch_untagged and e.tag is None) or
           (tags is not None and e.tag is not None and e.tag in tags):
            # caught

    resulting in the following table. Here a ``@catch`` point with no tags
    is a "catch-all"::

        throw instance                      @catch point
        0: no tag, ignore catch-alls        a: no tags
        1: no tag, allow catch-alls         b: no tags, catch untagged
        2: w/ tag, ignore catch-alls        c: w/ tags
        3: w/ tag, allow catch-alls         d: w/ tags, catch untagged

          0 1 2 3
        a   x   x
        b x x   x
        c     t t
        d x x t t

          = do not catch, pass on
        t = check tags, catch on match
        x = catch

    **How to use the table**:

      - If setting a ``@catch``, pick a row. Read off what you'll catch.

      - If raising a ``throw`` instance, pick a column. Read off what will catch it.

    Default settings for both ends give case ``b1``. For a guaranteed one-to-one
    relationship, pick a unique tag, and use settings for case ``c2``.

    **Examples**

    Multi-return using escape continuation::

        @catch()
        def f():
            def g():
                throw("hello from g")  # the arg becomes the return value of f()
                print("not reached")
                return False
            g()
            print("not reached either")
            return False
        assert f() == "hello from g"

    Escape from FP loop::

        @catch()  # no tag, catch any throw
        def f():
            @looped
            def s(loop, acc=0, i=0):
                if i > 5:
                    throw(acc)  # the argument becomes the return value of f()
                return loop(acc + i, i + 1)
            print("never reached")
            return False
        assert f() == 15

    For more control, tagged throws::

        @catch("foo")
        def foo():
            @call
            @catch("bar")
            def bar():
                @looped
                def s(loop, acc=0, i=0):
                    if i > 5:
                        throw(acc, tag="foo")
                    return loop(acc + i, i + 1)
                print("never reached")
                return False
            print("never reached either")
            return False
        assert f() == 15
    """
    if tags is not None:
        if isinstance(tags, tuple):  # multiple tags
            tags = set(tags)
        else:  # single tag
            tags = set((tags,))

    def shouldcatch(e):
        return ((tags is None and e.allow_catchall) or
                (catch_untagged and e.tag is None) or
                (tags is not None and e.tag is not None and e.tag in tags))

    def decorator(f):
        @wraps(f)
        def catchpoint(*args, **kwargs):
            try:
                return f(*args, **kwargs)
            except Escape as e:
                if shouldcatch(e):
                    return e.value
                else:  # meant for someone else, pass it on
                    raise
        return catchpoint
    return decorator

@register_decorator(priority=80)
def call_ec(f):
    """Decorator. Call with escape continuation (call/ec).

    Parameters:
        `f`: function
            The function to call. It must take one positional argument,
            the first-class escape continuation (ec).

            The ec, in turn, takes one positional argument; the value
            to send to the catch point. It becomes the return value
            of the ``call_ec``.

            The ec instance and the catch point are connected one-to-one.
            Both are tagged with a process-wide unique id. The ec is set to
            disallow catch-all (so that it will always reach its intended
            destination), and the catch point is set to ignore any untagged
            throws (so that it catches only this particular ec).

    Like in ``@call``, the function ``f`` is called immediately,
    and the def'd name is replaced by the return value of ``f(ec).``

    Example::

        @call_ec
        def result(ec):
            answer = 42
            def inner():
                ec(answer)  # directly escape from the outer def
                print("never reached")
                return 23
            answer = inner()
            print("never reached either")
            return answer
        assert result == 42

    This can also be used directly, to provide a "return" for multi-expression
    lambdas::

        from unpythonic.seq import begin
        result = call_ec(lambda ec:
                           begin(print("hi from lambda"),
                                 ec(42),
                                 print("never reached")))
        assert result == 42

    Similar usage is valid for named functions, too.
    """
    # Create a process-wide unique id to tag the ec:
    anchor = object()  # gensym("anchor"), but object() is much faster, and we don't need a label, or pickle support.
    uid = id(anchor)
    # Closure property important here. "ec" itself lives as long as someone
    # retains a reference to it. It's a first-class value; the callee could
    # return it or stash it somewhere.
    #
    # So we must keep track of whether we're still inside the dynamic extent
    # of the call/ec - i.e. whether we can still catch the escape exception
    # if it is raised.
    ec_valid = True
    # First-class ec like in Lisps. What's first-class in Python? Functions!
    def ec(value):
        if not ec_valid:
            raise RuntimeError("Cannot escape after the dynamic extent of the call_ec invocation.")
        # Be catchable only by our own catch point.
        throw(value, uid, allow_catchall=False)
    try:
        # Set up a tagged catch point that catches only the ec we just set up.
        @catch(uid, catch_untagged=False)
        def wrapper():
            return f(ec)
        return wrapper()
    finally:
        # Our dynamic extent ends; this ec instance is no longer valid.
        # Clear the flag (it will live on in the closure of the ec instance).
        ec_valid = False
