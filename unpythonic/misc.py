#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Miscellaneous lispy constructs."""

__all__ = ["call", "raisef", "pack"]

def call(thunk):
    """Decorator: run immediately, overwrite function by its return value.

    Can be used to make lispy not-quite-functions where the def just delimits
    a block of code that runs immediately (think call-with-something in Lisps).

    The function will be called with zero arguments.

    Name inspired by "call-with-something", but since here we're calling
    without any arguments, it's just "call".

    Examples::

        @call
        def result():  # this block of code runs immediately
            return "hello"
        print(result)  # "hello"

        # if the return value is of no interest:
        @call
        def _():
            ...  # code with cheeky side effects goes here

        @call
        def x():
            a = 2  #    many temporaries that help readability...
            b = 3  # ...of this calculation, but would just pollute locals...
            c = 5  # ...after the block exits
            return a * b * c

        @call
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

def pack(*args):
    """Multi-argument constructor for tuples.

    In other words, the inverse of tuple unpacking, as a function.

    E.g. `pack(a, b, c)` is the same as `(a, b, c)`.

    We provide this because the default constructor `tuple(...)` requires an
    iterable, and there are use cases (especially in Python 3.4, before PEP 448)
    where it is useful to be able to say *pack these args into a tuple*.

    See:
        https://www.python.org/dev/peps/pep-0448/

    Examples. If args naturally arrive separately::

        myzip = lambda lol: map(pack, *lol)
        lol = ((1, 2), (3, 4), (5, 6))
        for z in myzip(lol):
            print(z)

    Eliminate an ugly trailing comma::

        @looped_over(zip((1, 2, 3), ('a', 'b', 'c')), acc=())
        def p(loop, item, acc):
            numb, lett = item
            return loop(acc + pack("{:d}{:s}".format(numb, lett)))
        assert p == ('1a', '2b', '3c')
    """
    return args  # pretty much like in Lisps, (define (list . args) args)

def test():
    @call
    def result():
        return "hello"
    assert result == "hello"

    l = lambda: raisef(ValueError, "all ok")
    try:
        l()
    except ValueError:
        pass
    else:
        assert False

    myzip = lambda lol: map(pack, *lol)
    lol = ((1, 2), (3, 4), (5, 6))
    assert tuple(myzip(lol)) == ((1, 3, 5), (2, 4, 6))

    print("All tests PASSED")

if __name__ == '__main__':
    test()
