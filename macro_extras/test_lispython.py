# -*- coding: utf-8 -*-
"""Test the Lispython dialect."""

# The lang-import must be the first statement after the module docstring, if any.
from __lang__ import lispython

# unpythonic is lispython's stdlib; not everything gets imported by default
from unpythonic import foldl

# of course, Python's stdlib is available too
#
# So is **any** Python library; the ability to use arbitrary Python libraries
# in a new language with Python-based but customized syntax pretty much being
# the whole point of Pydialect.
#
from operator import mul

def main():
    print("hello, my dialect is {}".format(__lang__))

    x = let[(a, 21) in 2*a]
    assert x == 42

    c = cons(1, 2)
    assert tuple(c) == (1, 2)
    assert car(c) == 1
    assert cdr(c) == 2

    assert prod((2, 3, 4)) == 24  # missing battery

    # auto-TCO, implicit return in tail position
    def fact(n):
        def f(k, acc):
            if k == 1:
                acc
            else:  # "else" required to make also the "else" branch into a tail position
                f(k - 1, k*acc)
        f(n, acc=1)
    assert fact(4) == 24
    fact(5000)  # no crash

    # lambdas are named automatically
    square = lambda x: x**2
    assert square(3) == 9
    assert square.__name__ == "square"

    # underscore (NOTE: due to this, "f" is a reserved name in lispython)
    cube = f[_**3]
    assert cube(3) == 27
    assert cube.__name__ == "cube"

    assert foldl(mul, 1, (2, 3, 4)) == 24

if __name__ == '__main__':
    main()
