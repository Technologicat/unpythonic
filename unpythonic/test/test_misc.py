# -*- coding: utf-8 -*-

from operator import add
from functools import partial
from collections import deque
from sys import float_info
from queue import Queue

from ..misc import call, callwith, raisef, pack, namelambda, timer, \
                   getattrrec, setattrrec, Popper, CountingIterator, ulp, slurp
from ..fun import withself

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

    # CAUTION: in case of nested lambdas, the inner doesn't see the outer's new name:
    nested = namelambda("outer")(lambda: namelambda("inner")(withself(lambda self: self)))
    assert nested.__qualname__ == "test.<locals>.outer"
    assert nested().__qualname__ == "test.<locals>.<lambda>.<locals>.inner"

    # simple performance timer as a context manager
    with timer() as tictoc:
        for _ in range(int(1e6)):
            pass
    assert tictoc.dt > 0  # elapsed time in seconds (float)

    with timer(p=True):  # auto-print mode for convenience
        for _ in range(int(1e6)):
            pass

    # access underlying data in an onion of wrappers
    class Wrapper:
        def __init__(self, x):
            self.x = x

    w = Wrapper(Wrapper(42))
    assert type(getattr(w, "x")) == Wrapper
    assert type(getattrrec(w, "x")) == int
    assert getattrrec(w, "x") == 42

    setattrrec(w, "x", 23)
    assert type(getattr(w, "x")) == Wrapper
    assert type(getattrrec(w, "x")) == int
    assert getattrrec(w, "x") == 23

    # pop-while iterator
    inp = deque(range(5))  # efficiency: deque can popleft() in O(1) time
    out = []
    for x in Popper(inp):
        out.append(x)
    assert inp == deque([])
    assert out == list(range(5))

    inp = deque(range(3))
    out = []
    for x in Popper(inp):
        out.append(x)
        if x < 10:
            inp.appendleft(x + 10)
    assert inp == deque([])
    assert out == [0, 10, 1, 11, 2, 12]

    # works for a list, too, although not efficient (pop(0) takes O(n) time)
    inp = list(range(5))
    out = []
    for x in Popper(inp):
        out.append(x)
    assert inp == []
    assert out == list(range(5))

    # iterator that counts how many items have been yielded (as a side effect)
    inp = range(5)
    it = CountingIterator(inp)
    assert it.count == 0
    _ = list(it)
    assert it.count == 5

    inp = range(5)
    it = CountingIterator(inp)
    assert it.count == 0
    for k, _ in enumerate(it, start=1):
        assert it.count == k
    assert it.count == 5

    # Unit in the Last Place, float utility
    # https://en.wikipedia.org/wiki/Unit_in_the_last_place
    eps = float_info.epsilon
    assert ulp(1.0) == eps
    # test also at some base-2 exponent switch points
    assert ulp(2.0) == 2 * eps
    assert ulp(0.5) == 0.5 * eps

    q = Queue()
    for k in range(10):
        q.put(k)
    assert slurp(q) == list(range(10))

    print("All tests PASSED")

if __name__ == '__main__':
    test()
