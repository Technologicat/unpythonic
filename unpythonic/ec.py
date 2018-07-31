#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Escape continuations."""

__all__ = ["escape", "setescape"]

from functools import wraps

class escape(Exception):
    """Exception that essentially represents an escape continuation.

    Use ``raise escape(value)`` to escape to the nearest (dynamically) surrounding
    ``@setescape``. The @setescape'd function immediately terminates, returning
    ``value``.

    Trampolined functions may also use ``return escape(value)``; the trampoline
    will then raise the exception (this is to make it work also with lambdas).

    The optional ``tag`` parameter can be used to limit which ``@setescape``
    points see this particular escape instance. Default is to be catchable
    by any ``@setescape``.
    """
    def __init__(self, value, tag=None):
        self.value = value
        self.tag = tag

def setescape(tag=None):
    """Decorator. Mark function as exitable by ``raise escape(value)``.

    In Lisp terms, this essentially captures the escape continuation (ec)
    of the decorated function. The ec can then be invoked by raising escape(value).

    To make this work with lambdas, in trampolined functions it is also legal
    to ``return escape(value)``. The trampoline specifically detects ``escape``
    instances, and performs the ``raise``.

    Technically, this is a decorator factory; the optional tag parameter can be
    used to catch only those escapes with the same tag. ``tag`` can be a single
    value, or a tuple. Single value means catch that specific tag; tuple means
    catch any of those tags. Default is None, i.e. catch all.

    Multi-return using escape continuation::

        @setescape()
        def f():
            def g():
                raise escape("hello from g")  # the arg becomes the return value of f()
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
                    return escape(acc)  # the argument becomes the return value of f()
                return loop(acc + i, i + 1)
            print("never reached")
            return False
        assert f() == 15

    For more control, tagged escape::

        @setescape("foo")
        def foo():
            @immediate
            @setescape("bar")
            def bar():
                @looped
                def s(loop, acc=0, i=0):
                    if i > 5:
                        return escape(acc, tag="foo")
                    return loop(acc + i, i + 1)
                print("never reached")
                return False
            print("never reached either")
            return False
        assert f() == 15
    """
    if tag is None:
        tags = None
    elif isinstance(tag, (tuple, list)):  # multiple tags
        tags = set(tag)
    else: # single tag
        tags = set((tag,))

    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            try:
                return f(*args, **kwargs)
            except escape as e:
                if tags is None or e.tag is None or e.tag in tags:
                    return e.value
                else:  # meant for someone else, pass it on
                    raise
        return decorated
    return decorator

def test():
    # "multi-return" using escape continuation
    @setescape()
    def f():
        def g():
            raise escape("hello from g")  # the argument becomes the return value of f()
            print("not reached")
        g()
        print("not reached either")
    assert f() == "hello from g"

    # tests with @looped in tco.py to prevent cyclic dependency

    print("All tests PASSED")

if __name__ == '__main__':
    test()
