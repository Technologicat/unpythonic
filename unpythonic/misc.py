#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Miscellaneous lispy constructs."""

__all__ = ["begin", "begin0", "lazy_begin", "lazy_begin0", "immediate"]

def begin(*vals):
    """Racket-like begin: return the last value.

    Eager; bodys already evaluated by Python when this is called.

        f = lambda x: begin(print("hi"),
                            42*x)
        print(f(1))  # 42
    """
    return vals[-1]

def begin0(*vals):  # eager, bodys already evaluated when this is called
    """Racket-like begin0: return the first value.

    Eager; bodys already evaluated by Python when this is called.

        g = lambda x: begin0(23*x,
                             print("hi"))
        print(g(1))  # 23
    """
    return vals[0]

def lazy_begin(*bodys):
    """Racket-like begin: run bodys in sequence, return the last return value.

    Lazy; each body must be a thunk (0-argument function), to delay its evaluation
    until begin() runs.

        f = lambda x: lazy_begin(lambda: print("hi"),
                                 lambda: 42*x)
        print(f(1))  # 42
    """
    *rest,last = bodys
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
    first,*rest = bodys
    out = first()
    for body in rest:
        body()
    return out

def immediate(thunk):
    """Decorator: run immediately, overwrite function by its return value.

    Can be used to make lispy not-quite-functions where the def just delimits
    a block of code that runs immediately (think call-with-something in Lisp).

    The function will be called with zero arguments.

        @immediate
        def result():  # this block of code runs immediately
            return "hello"
        print(result)  # "hello"

        # if the return value is of no interest:
        @immediate
        def _():
            ...  # code with cheeky side effects goes here

        @immediate
        def x():
            a = 2  #    many temporaries that help readability...
            b = 3  # ...of this calculation, but just pollute locals...
            c = 5  # ...after the block exits
            return a * b * c

        @immediate
        def _():
            for x in range(10):
                for y in range(10).
                    if x * y == 42:
                        return  # "multi-break" out of both loops!
                    ...

    (Note, however, that in the multi-break case, "x" and "y" are
     no longer in scope outside the block, since the block is a function.)
    """
    return thunk()

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

    @immediate
    def result():
        return "hello"
    assert result == "hello"

    print("All tests PASSED")

if __name__ == '__main__':
    test()
