# -*- coding: utf-8 -*-

from operator import add
from functools import partial

from ..misc import call, callwith, raisef, pack, namelambda, timer

def test():
    # def as a code block (function overwritten by return value)
    #
    @call
    def result():
        return "hello"
    assert result == "hello"

    # use case 1: make temporaries fall out of scope
    @call
    def x():
        a = 2  #    many temporaries that help readability...
        b = 3  # ...of this calculation, but would just pollute locals...
        c = 5  # ...after the block exits
        return a * b * c
    assert x == 30

    # use case 2: multi-break out of nested loops
    @call
    def result():
        for x in range(10):
            for y in range(10):
                if x * y == 42:
                    return (x, y)
                ... # more code here
    assert result == (6, 7)

    # can also be used normally
    assert call(add, 2, 3) == add(2, 3)

    # to pass arguments when used as decorator, use @callwith instead
    @callwith(3)
    def result(x):
        return x**2
    assert result == 9

    # specialize for given arguments, choose function later
    apply23 = callwith(2, 3)
    def myadd(a, b):
        return a + b
    def mymul(a, b):
        return a * b
    assert apply23(myadd) == 5
    assert apply23(mymul) == 6

    # callwith is not essential; we can do the same pythonically like this:
    a = [2, 3]
    assert myadd(*a) == 5
    assert mymul(*a) == 6

    # build up the argument list as we go
    #   - note curry does not help, must use partial; this is because curry
    #     will happily call "callwith" (and thus terminate the gathering step)
    #     as soon as it gets at least one argument.
    p1 = partial(callwith, 2)
    p2 = partial(p1, 3)
    p3 = partial(p2, 4)
    apply234 = p3()  # terminate gathering step by actually calling callwith
    def add3(a, b, c):
        return a + b + c
    def mul3(a, b, c):
        return a * b * c
    assert apply234(add3) == 9
    assert apply234(mul3) == 24

    # pythonic solution:
    a = [2]
    a += [3]
    a += [4]
    assert add3(*a) == 9
    assert mul3(*a) == 24

    # callwith in map, if we want to vary the function instead of the data
    m = map(callwith(3), [lambda x: 2*x, lambda x: x**2, lambda x: x**(1/2)])
    assert tuple(m) == (6, 9, 3**(1/2))

    # pythonic solution - use comprehension notation:
    m = (f(3) for f in [lambda x: 2*x, lambda x: x**2, lambda x: x**(1/2)])
    assert tuple(m) == (6, 9, 3**(1/2))

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

    square = lambda x: x**2
    assert square.__code__.co_name == "<lambda>"
    assert square.__name__ == "<lambda>"
    assert square.__qualname__ == "test.<locals>.<lambda>"
    square = namelambda("square")(square)
    assert square.__code__.co_name == "square"
    assert square.__name__ == "square"
    assert square.__qualname__ == "test.<locals>.square"

    with timer() as tictoc:
        for _ in range(int(1e6)):
            pass
    assert tictoc.dt > 0  # elapsed time in seconds (float)

    with timer(p=True):
        for _ in range(int(1e6)):
            pass

    print("All tests PASSED")

if __name__ == '__main__':
    test()
