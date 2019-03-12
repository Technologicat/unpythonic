# -*- coding: utf-8 -*-
"""Test the Lispython dialect."""

# The lang-import must be the first statement after the module docstring, if any.
# It sets the dialect this module is parsed in.
from __lang__ import lispython

# can use macros, too
from unpythonic.syntax import macros, continuations, call_cc

# unpythonic is lispython's stdlib; not everything gets imported by default
from unpythonic import foldl

# of course, all of Python's stdlib is available too
#
# So is **any** Python library; the ability to use arbitrary Python libraries in
# a customized Python-based language is pretty much the whole point of Pydialect.
#
from operator import mul

def main():
    print("hello, my dialect is {}".format(__lang__))

    assert prod((2, 3, 4)) == 24  # bye missing battery, hello new dialect builtin
    assert foldl(mul, 1, (2, 3, 4)) == 24

    # cons, car, cdr, ll, llist are builtins (for more linked list utils, import them from unpythonic)
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

    # rackety cond
    a = lambda x: cond[x < 0, "nope",
                       x % 2 == 0, "even",
                       "odd"]
    assert a(-1) == "nope"
    assert a(2) == "even"
    assert a(3) == "odd"

    # auto-TCO (both in defs and lambdas), implicit return in tail position
    def fact(n):
        def f(k, acc):
            if k == 1:
                return acc  # "return" still available for early return
            f(k - 1, k*acc)
        f(n, acc=1)
    assert fact(4) == 24
    fact(5000)  # no crash (and correct result, since Python uses bignums transparently)

    t = letrec[((evenp, lambda x: (x == 0) or oddp(x - 1)),
                (oddp, lambda x:(x != 0) and evenp(x - 1))) in
               evenp(10000)]  # no crash
    assert t is True

    # lambdas are named automatically
    square = lambda x: x**2
    assert square(3) == 9
    assert square.__name__ == "square"

    # the underscore (NOTE: due to this, "f" is a reserved name in lispython)
    cube = f[_**3]
    assert cube(3) == 27
    assert cube.__name__ == "cube"

    # lambdas can have multiple expressions and local variables
    #
    # If you need to return a literal list from a lambda, use an extra set of
    # brackets; the outermost brackets always enable multiple-expression mode.
    #
    test = lambda x: [local[y << 2*x],  # local[name << value] makes a local variable
                      y + 1]
    assert test(10) == 21

    a = lambda x: [local[t << x % 2],
                   cond[t == 0, "even",
                        t == 1, "odd",
                        None]]  # cond[] requires an else branch
    assert a(2) == "even"
    assert a(3) == "odd"

    # actually the multiple-expression environment is an unpythonic.syntax.do[],
    # which can be used in any expression position.
    x = do[local[z << 2],
           3*z]
    assert x == 6

    # do0[] is the same, but returns the value of the first expression instead of the last one.
    x = do0[local[z << 3],
            print("hi from do0, z is {}".format(z))]
    assert x == 3

    # MacroPy #21; namedlambda must be in its own with block in the
    # dialect implementation or this particular combination will fail
    # (uncaught jump, __name__ not set).
    t = letrec[((evenp, lambda x: (x == 0) or oddp(x - 1)),
                (oddp,  lambda x:(x != 0) and evenp(x - 1))) in
               [local[x << evenp(100)],  # multi-expression let body is a do[] environment
                (x, evenp.__name__, oddp.__name__)]]
    assert t == (True, "evenp", "oddp")

    with continuations:  # should be skipped by the implicit tco inserted by the dialect
        k = None  # kontinuation
        def setk(*args, cc):
            nonlocal k
            k = cc  # current continuation, i.e. where to go after setk() finishes
            args  # tuple means multiple-return-values
        def doit():
            lst = ['the call returned']
            *more, = call_cc[setk('A')]
            lst + list(more)
        assert doit() == ['the call returned', 'A']
        # We can now send stuff into k, as long as it conforms to the
        # signature of the assignment targets of the "call_cc".
        assert k('again') == ['the call returned', 'again']
        assert k('thrice', '!') == ['the call returned', 'thrice', '!']

if __name__ == '__main__':
    main()
