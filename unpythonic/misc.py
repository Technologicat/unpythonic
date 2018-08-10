#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Miscellaneous lispy constructs."""

__all__ = ["begin", "begin0", "lazy_begin", "lazy_begin0", "do", "call", "raisef", "pack"]

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

def do(value0, *bodys):
    """Perform a sequence of operations on an initial value.

    Bodys are applied left to right.

    Each body must be a 1-argument function. It takes the current value,
    and it must return the next value (the last body, the final value).

    The name ``do`` was chosen because of the Haskell construct performing a
    somewhat similar function (allow imperative-looking functional code),
    but this one has nothing to do with monads.

    Example. Given::

        double = lambda x: 2 * x
        inc    = lambda x: x + 1

    these two lines are equivalent::

        x = do(42, double, inc)  # --> 85

        x = inc(double(42))      # --> 85

    but now we don't need to read the source code backwards. This is essentially::

        f = compose(reversed(bodys))
        x = f(42)

    if you have a library that provides ``compose``.

    Perhaps the most common alternative in Python is this imperative code::

        x = 42
        x = double(x)
        x = inc(x)
        assert x == 85

    but now ``x`` no longer has a single definition. This is confusing, because
    mutation is not an essential feature of the algorithm, but instead is used
    as an implementation detail to avoid introducing extra temporaries.

    The definition issue can be avoided by::

        x0 = 42
        x1 = double(x0)
        x  = inc(x1)
        assert x == 85

    at the cost of namespace pollution.
    """
    # Ideally we should use fploop, but tco depends on us (misc),
    # so we choose to cheat imperatively to avoid the circular dependency.
    #
    # This is preferable because we need to be careful about importing fploop,
    # so that we can be sure it uses the desired TCO implementation.

#    # Truly equivalent to the final form above without namespace pollution.
#    @looped_over(bodys, acc=value0)
#    def x(loop, update, acc):
#        return loop(update(acc))
#    return x

    # Imperative cheating; since "x" is a local, the damage is contained here
    # and won't spread to the call site.
    x = value0
    for update in bodys:
        x = update(x)
    return x

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

    Examples. If args naturally come in separately::

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
    return args

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

    double = lambda x: 2 * x
    inc    = lambda x: x + 1
    assert do(42, double, inc) == 85
    assert do(42, inc, double) == 86

    print("All tests PASSED")

if __name__ == '__main__':
    test()
