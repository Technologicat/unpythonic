#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Escape continuations."""

__all__ = ["escape", "setescape", "call_ec"]

from functools import wraps

def escape(value, tag=None, allow_catchall=True):
    """Escape to a ``@setescape`` point.

    Essentially this just raises an ``Escape`` instance with the given arguments.
    Wrapping the raise in a function call allows also lambdas to use escapes.

    For the escape to work, we must be inside the dynamic extent
    of the intended ``@setescape`` point.

    Parameters:

        value: anything
            The value to send to the escape point.

        tag: anything comparable with ``==``
            Can be used to restrict which ``@setescape`` points may catch
            this escape instance. Default ``None``, meaning "no tag".

        allow_catchall: bool
            Whether untagged "catch-all" ``@setescape`` points may catch
            this escape instance (regardless of tag!).

            Even if ``False``, if ``tag`` is ``None``, a ``@setescape``
            point may still override this with ``catch_untagged=True``.
            (See the table in ``help(setescape)``, case ``b0``.)
    """
    raise Escape(value, tag, allow_catchall)

class Escape(Exception):
    """Exception that essentially represents an escape continuation.

    Constructor parameters: see ``escape()``.
    """
    def __init__(self, value, tag=None, allow_catchall=True):
        self.value = value
        self.tag = tag
        self.allow_catchall = allow_catchall

        # Error message when uncaught
        self.args = ("Not within the dynamic extent of a @setescape",)

def setescape(tags=None, catch_untagged=True):
    """Decorator. Mark function as exitable by ``escape(value)``.

    In Lisp terms, this essentially captures the escape continuation (ec)
    of the decorated function. The ec can then be invoked by ``escape(value)``.

    Technically, this is a decorator factory, since we take parameters.

    Parameters:
        tags: ``t``, or tuple of ``t``
          where ``t`` is anything comparable with ``==``
            A tuple is OR'd, like in ``isinstance()``.

            Restrict which escapes will be caught by this ``@setescape`` point.

        catch_untagged: bool
            Whether this ``@setescape`` point catches untagged escapes.

            Even if ``False``, if ``tags`` is ``None``, an escape instance
            may still override this with ``allow_catchall=True``. (See the
            table below, case ``a1``.)

    The exact catch condition is::

        # e is an Escape instance
        if (tags is None and e.allow_catchall) or
           (catch_untagged and e.tag is None) or
           (tags is not None and e.tag is not None and e.tag in tags):
            # caught

    resulting in the following table. Here a ``@setescape`` point with no tags
    is a "catch-all"::

        escape instance                     @setescape point
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

      - If setting a ``@setescape`` point, pick a row. Read off what you'll catch.

      - If raising an ``escape`` instance, pick a column. Read off what will catch it.

    Default settings for both ends give case ``b1``. For a guaranteed one-to-one
    relationship, pick a unique tag, and use settings for case ``c2``.

    **Examples**

    Multi-return using escape continuation::

        @setescape()
        def f():
            def g():
                escape("hello from g")  # the arg becomes the return value of f()
                print("not reached")
                return False
            g()
            print("not reached either")
            return False
        assert f() == "hello from g"

    Escape from FP loop::

        @setescape()  # no tag, catch any escape instance
        def f():
            @looped
            def s(loop, acc=0, i=0):
                if i > 5:
                    escape(acc)  # the argument becomes the return value of f()
                return loop(acc + i, i + 1)
            print("never reached")
            return False
        assert f() == 15

    For more control, tagged escape::

        @setescape("foo")
        def foo():
            @call
            @setescape("bar")
            def bar():
                @looped
                def s(loop, acc=0, i=0):
                    if i > 5:
                        escape(acc, tag="foo")
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
        else: # single tag
            tags = set((tags,))

    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            try:
                return f(*args, **kwargs)
            except Escape as e:
                if (tags is None and e.allow_catchall) or \
                   (catch_untagged and e.tag is None) or \
                   (tags is not None and e.tag is not None and e.tag in tags):
                    return e.value
                else:  # meant for someone else, pass it on
                    raise
        return decorated
    return decorator

def call_ec(f):
    """Decorator. Call with escape continuation (call/ec).

    Parameters:
        `f`: function
            The function to call. It must take one positional argument,
            the first-class escape continuation (ec).

            The ec, in turn, takes one positional argument; the value
            to send to the escape point. It becomes the return value
            of the ``call_ec``.

            The ec instance and the escape point are connected one-to-one.
            Both are tagged with a process-wide unique id. The ec is set to
            disallow catch-all (so that it will always reach its intended
            destination), and the point is set to ignore any untagged escapes
            (so that it catches only this particular ec).

    Like in ``@call``, the function ``f`` is called immediately,
    and the def'd name is replaced by the return value of ``f(ec).``

    Example::

        @call_ec
        def result(ec):
            answer = 42
            def inner():
                ec(answer)  # directly escapes from the outer def
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
    anchor = object()
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
        # Be catchable only by our own escape point.
        escape(value, uid, allow_catchall=False)
    try:
        # Set up a tagged escape point that catches only the ec we just set up.
        @setescape(uid, catch_untagged=False)
        def wrapper():
            return f(ec)
        return wrapper()
    finally:  # Our dynamic extent ends; this ec instance is no longer valid.
              # Clear the flag (it will live on in the closure of the ec instance).
        ec_valid = False

def test():
    # "multi-return" using escape continuation
    #
    @setescape()
    def f():
        def g():
            escape("hello from g")  # the argument becomes the return value of f()
            print("not reached")
        g()
        print("not reached either")
    assert f() == "hello from g"

    # lispy call/ec (call-with-escape-continuation)
    #
    @call_ec
    def result(ec):  # effectively, just a code block!
        answer = 42
        ec(answer)  # here this has the same effect as "return answer"...
        print("never reached")
        answer = 23
        return answer
    assert result == 42

    @call_ec
    def result(ec):
        answer = 42
        def inner():
            ec(answer)  # ...but here this directly escapes from the outer def
            print("never reached")
            return 23
        answer = inner()
        print("never reached either")
        return answer
    assert result == 42

    try:
        @call_ec
        def erroneous(ec):
            return ec
        erroneous(42)  # invalid, dynamic extent of the call_ec has ended
    except RuntimeError:
        pass
    else:
        assert False

    # begin() returns the last value. What if we don't want that?
    # (this works because ec() uses the exception mechanism)
    from unpythonic.seq import begin
    result = call_ec(lambda ec:
                       begin(print("hi from lambda"),
                             ec(42),  # now we can effectively "return ..." at any point from a lambda!
                             print("never reached")))
    assert result == 42

    # tests with @looped in fploop.py to prevent cyclic dependency

#    def catching_truth_table():
#        def check(tags, catch_untagged, e):
#            if (tags is None and e.allow_catchall) or \
#               (catch_untagged and e.tag is None):
#                return 2  # unconditional catch
#            if (tags is not None and e.tag is not None): # and e.tag in tags):
#                   return 1  # catch if tags match
#            return 0  # don't catch, pass on
#        _ = None
#        # in this table, we're essentially projecting bool**4 into two dimensions.
#        ps = ((None, False), (None, True),  # @setescape points
#              (set(("tag",)), False), (set(("tag",)), True))
#        es = (Escape(_, None, False),  Escape(_, None, True),  # escape instances
#              Escape(_, "tag", False), Escape(_, "tag", True))
##        # the other reasonable projection:
##        ps = ((None, False), (set(("tag",)), False),
##              (None, True), (set(("tag",)), True))
##        es = (escape(_, None, False), escape(_, "tag", False),
##              escape(_, None, True), escape(_, "tag", True))
#        table = [[check(t, c, e) for e in es] for (t, c) in ps]  # col = e, row = p
#        for row in table:
#            print(row)
#    catching_truth_table()

    print("All tests PASSED")

if __name__ == '__main__':
    test()
