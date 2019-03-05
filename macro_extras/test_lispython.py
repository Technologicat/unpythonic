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

    assert prod((2, 3, 4)) == 24  # bye missing battery, hello new dialect builtin
    assert foldl(mul, 1, (2, 3, 4)) == 24

    # cons, car, cdr, ll, llist are builtins (for more linked list utils, import from unpythonic)
    c = cons(1, 2)
    assert tuple(c) == (1, 2)
    assert car(c) == 1
    assert cdr(c) == 2
    assert ll(1, 2, 3) == llist((1, 2, 3))

    # all unpythonic.syntax let[], letseq[], letrec[] constructs are builtins
    # (including the decorator versions, let_syntax and abbrev)
    x = let[(a, 21) in 2*a]
    assert x == 42

    x = letseq[((a, 1),
                (a, 2*a),
                (a, 2*a)) in
               a]
    assert x == 4

    # auto-TCO (both in defs and lambdas), implicit return in tail position
    def fact(n):
        def f(k, acc):
            if k == 1:
                acc
            else:  # "else" required to make both branches into tail positions
                f(k - 1, k*acc)
        f(n, acc=1)
    assert fact(4) == 24
    fact(5000)  # no crash

    t = letrec[((evenp, lambda x: (x == 0) or oddp(x - 1)),
                (oddp, lambda x:(x != 0) and evenp(x - 1))) in
               evenp(10000)]  # no crash
    assert t is True

#    # TODO: investigate what goes wrong here, looks like a trampoline is missing somewhere?
#    t = letrec[((evenp, lambda x: (x == 0) or oddp(x - 1)),
#                (oddp, lambda x:(x != 0) and evenp(x - 1))) in
#               [evenp(10000),
#               42]]

    # lambdas are named automatically
    square = lambda x: x**2
    assert square(3) == 9
    assert square.__name__ == "square"

    # underscore (NOTE: due to this, "f" is a reserved name in lispython)
    cube = f[_**3]
    assert cube(3) == 27
    assert cube.__name__ == "cube"

    # lambdas can have multiple expressions and local variables
    #
    # (if you need to return a list from a lambda, use an extra set of brackets;
    #  the outermost brackets always enable multiple-expression mode)
    #
    test = lambda x: [local[y << 2*x],  # local[name << value] makes a local variable
                      y + 1]
    assert test(10) == 21

    # actually the multiple-expression environment is an unpythonic.syntax.do[],
    # which can be used in any expression position
    x = do[local[z << 2],
           3*z]
    assert x == 6

    # do0[] is the same, but returns the value of the first expression instead of the last one
    x = do0[local[z << 3],
            print("hi from do0, z is {}".format(z))]
    assert x == 3

if __name__ == '__main__':
    main()
