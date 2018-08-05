#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Miscellaneous lispy constructs."""

__all__ = ["begin", "begin0", "lazy_begin", "lazy_begin0", "now", "raisef"]

def begin(*vals):
    """Racket-like begin: return the last value.

    Eager; bodys already evaluated by Python when this is called.

        f = lambda x: begin(print("hi"),
                            42*x)
        print(f(1))  # 42
    """
    return vals[-1] if len(vals) else None

def begin0(*vals):  # eager, bodys already evaluated when this is called
    """Racket-like begin0: return the first value.

    Eager; bodys already evaluated by Python when this is called.

        g = lambda x: begin0(23*x,
                             print("hi"))
        print(g(1))  # 23
    """
    return vals[0] if len(vals) else None

def lazy_begin(*bodys):
    """Racket-like begin: run bodys in sequence, return the last return value.

    Lazy; each body must be a thunk (0-argument function), to delay its evaluation
    until begin() runs.

        f = lambda x: lazy_begin(lambda: print("hi"),
                                 lambda: 42*x)
        print(f(1))  # 42
    """
    l = len(bodys)
    if not l:
        return None
    if l == 1:
        b = bodys[0]
        return b()
    *rest, last = bodys
    for body in rest:
        body()
    return last()

def lazy_begin0(*bodys):
    """Racket-like begin0: run bodys in sequence, return the first return value.

    Lazy; each body must be a thunk (0-argument function), to delay its evaluation
    until begin0() runs.

        g = lambda x: lazy_begin0(lambda: 23*x,
                                  lambda: print("hi"))
        print(g(1))  # 23
    """
    l = len(bodys)
    if not l:
        return None
    if l == 1:
        b = bodys[0]
        return b()
    first, *rest = bodys
    out = first()
    for body in rest:
        body()
    return out

def now(thunk):
    """Decorator: run immediately, overwrite function by its return value.

    Can be used to make lispy not-quite-functions where the def just delimits
    a block of code that runs immediately (think call-with-something in Lisp).

    The function will be called with zero arguments.

        @now
        def result():  # this block of code runs immediately
            return "hello"
        print(result)  # "hello"

        # if the return value is of no interest:
        @now
        def _():
            ...  # code with cheeky side effects goes here

        @now
        def x():
            a = 2  #    many temporaries that help readability...
            b = 3  # ...of this calculation, but would just pollute locals...
            c = 5  # ...after the block exits
            return a * b * c

        @now
        def _():
            for x in range(10):
                for y in range(10):
                    if x * y == 42:
                        return  # "multi-break" out of both loops!
                    ...

    (In the multi-break case, "x" and "y" are no longer in scope outside
     the block, since the block is a function.)
    """
    return thunk()

def raisef(exctype, *args, **kwargs):
    """``raise`` as a function, to make it possible for lambdas to raise exceptions.

    Example::

        raisef(ValueError, "message")

    is equivalent to::

        raise ValueError("message")

    Parameters:
        exctype: type
            The object type to raise as an exception.

        *args: anything
            Passed on to the constructor of exctype.

        **kwargs: anything
            Passed on to the constructor of exctype.
    """
    raise exctype(*args, **kwargs)

def test():
    f = lambda x: begin(print("hi"),
                        42*x)
    assert f(1) == 42

    g = lambda x: begin0(23*x,
                         print("hi"))
    assert g(1) == 23

    test_lazy_begin = lambda: lazy_begin(lambda: print("hi"),
                                         lambda: "the return value")
    assert test_lazy_begin() == "the return value"

    test_lazy_begin0 = lambda: lazy_begin0(lambda: "the return value",
                                           lambda: print("hi"))
    assert test_lazy_begin0() == "the return value"

    @now
    def result():
        return "hello"
    assert result == "hello"

    print("All tests PASSED")

if __name__ == '__main__':
    test()
