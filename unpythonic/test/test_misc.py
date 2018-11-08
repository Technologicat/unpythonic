# -*- coding: utf-8 -*-

from operator import add

from ..misc import call, raisef, pack, namelambda

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

    assert call(add, 2, 3) == add(2, 3)

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
    assert square.__name__ == "<lambda>"
    square = namelambda(square, "square")
    assert square.__name__ == "square (lambda)"

    print("All tests PASSED")

if __name__ == '__main__':
    test()
