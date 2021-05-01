# -*- coding: utf-8 -*-
"""Test the Pytkell dialect."""

# from mcpyrate.debug import dialects, StepExpansion
from ...dialects import dialects, Pytkell  # noqa: F401

from ...syntax import macros, continuations, call_cc, tco  # noqa: F401
from ...misc import timer

from types import FunctionType
from operator import add, mul

# TODO: use the test framework

def runtests():
    print(f"Hello from {__lang__}!")  # noqa: F821, the dialect template defines it.

    # function definitions (both def and lambda) and calls are auto-curried
    def add3(a, b, c):
        return a + b + c

    a = add3(1)
    assert isinstance(a, FunctionType)
    a = a(2)
    assert isinstance(a, FunctionType)
    a = a(3)
    assert isinstance(a, int)

    # actually partial evaluation so any of these works
    assert add3(1)(2)(3) == 6
    assert add3(1, 2)(3) == 6
    assert add3(1)(2, 3) == 6
    assert add3(1, 2, 3) == 6

    # arguments of a function call are auto-lazified (converted to promises, MacroPy lazy[])
    def addfirst2(a, b, c):
        # a and b are read, so their promises are forced
        # c is not used, so not evaluated either
        return a + b
    assert addfirst2(1)(2)(1 / 0) == 3

    # let-bindings are auto-lazified
    x = let[((x, 42),  # noqa: F821
             (y, 1 / 0)) in x]  # noqa: F821
    assert x == 42

    # assignments are not (because they can imperatively update existing names)
    try:
        a = 1 / 0
    except ZeroDivisionError:
        pass
    else:
        assert False, "expected a zero division error"

    # so if you want that, use lazy[] manually (it's a builtin in Pytkell)
    a = lazy[1 / 0]  # this blows up only when the value is read (name 'a' in Load context)  # noqa: F821

    # manually lazify items in a data structure literal, recursively (see unpythonic.syntax.lazyrec):
    a = lazyrec[(1, 2, 3 / 0)]  # noqa: F821
    assert a[:-1] == (1, 2)  # reading a slice forces only that slice

    # laziness passes through
    def g(a, b):
        return a  # b not used
    def f(a, b):
        return g(a, b)  # b is passed along, but its value is not used
    assert f(42, 1 / 0) == 42

    def f(a, b):
        return (a, b)
    assert f(1, 2) == (1, 2)
    assert (flip(f))(1, 2) == (2, 1)  # NOTE flip reverses all (doesn't just flip the first two)  # noqa: F821

#    # TODO: this doesn't work, because curry sees f's arities as (2, 2) (kwarg handling!)
#    assert (flip(f))(1, b=2) == (1, 2)  # b -> kwargs

    # http://www.cse.chalmers.se/~rjmh/Papers/whyfp.html
    my_sum = foldl(add, 0)  # noqa: F821
    my_prod = foldl(mul, 1)  # noqa: F821
    my_map = lambda f: foldr(compose(cons, f), nil)  # compose is unpythonic.fun.composerc  # noqa: F821

    assert my_sum(range(1, 5)) == 10
    assert my_prod(range(1, 5)) == 24
    assert tuple(my_map((lambda x: 2 * x), (1, 2, 3))) == (2, 4, 6)

    assert tuple(scanl(add, 0, (1, 2, 3))) == (0, 1, 3, 6)  # noqa: F821
    assert tuple(scanr(add, 0, (1, 2, 3))) == (0, 3, 5, 6)  # NOTE output ordering different from Haskell  # noqa: F821

    # let-in
    x = let[(a, 21) in 2 * a]  # noqa: F821
    assert x == 42

    x = let[((a, 21),  # noqa: F821
             (b, 17)) in  # noqa: F821
            2 * a + b]  # noqa: F821
    assert x == 59

    # let-where
    x = let[2 * a, where(a, 21)]  # noqa: F821
    assert x == 42

    x = let[2 * a + b,  # noqa: F821
            where((a, 21),  # noqa: F821
                  (b, 17))]  # noqa: F821
    assert x == 59

    # nondeterministic evaluation (essentially do-notation in the List monad)
    #
    # pythagorean triples
    pt = forall[z << range(1, 21),   # hypotenuse  # noqa: F821
                x << range(1, z + 1),  # shorter leg  # noqa: F821
                y << range(x, z + 1),  # longer leg  # noqa: F821
                insist(x * x + y * y == z * z),  # see also deny()  # noqa: F821
                (x, y, z)]  # noqa: F821
    assert tuple(sorted(pt)) == ((3, 4, 5), (5, 12, 13), (6, 8, 10),
                                 (8, 15, 17), (9, 12, 15), (12, 16, 20))

    # functional update for sequences
    #
    tup1 = (1, 2, 3, 4, 5)
    tup2 = fup(tup1)[2:] << (10, 20, 30)  # fup(sequence)[idx_or_slice] << sequence_of_values  # noqa: F821
    assert tup2 == (1, 2, 10, 20, 30)
    assert tup1 == (1, 2, 3, 4, 5)

    # immutable dict, with functional update
    #
    d1 = frozendict(foo='bar', bar='tavern')  # noqa: F821
    d2 = frozendict(d1, bar='pub')  # noqa: F821
    assert tuple(sorted(d1.items())) == (('bar', 'tavern'), ('foo', 'bar'))
    assert tuple(sorted(d2.items())) == (('bar', 'pub'), ('foo', 'bar'))

    # s = mathematical Sequence (const, arithmetic, geometric, power)
    #
    assert last(take(10000, s(1, ...))) == 1  # noqa: F821
    assert last(take(5, s(0, 1, ...))) == 4  # noqa: F821
    assert last(take(5, s(1, 2, 4, ...))) == (1 * 2 * 2 * 2 * 2)  # 16  # noqa: F821
    assert last(take(5, s(2, 4, 16, ...))) == (((((2)**2)**2)**2)**2)  # 65536  # noqa: F821

    # s() takes care to avoid roundoff
    assert last(take(1001, s(0, 0.001, ...))) == 1  # noqa: F821

    # iterables returned by s() support infix math
    # (to add infix math support to some other iterable, m(iterable))
    c = s(1, 3, ...) + s(2, 4, ...)  # noqa: F821
    assert tuple(take(5, c)) == (3, 7, 11, 15, 19)  # noqa: F821
    assert tuple(take(5, c)) == (23, 27, 31, 35, 39)  # consumed!  # noqa: F821

    # imemoize = memoize Iterable (makes a gfunc, drops math support)
    # gmathify returns a new gfunc that adds infix math support
    #          to generators the original gfunc makes.
    #
    # see also gmemoize, fimemoize in unpythonic
    #
    mi = lambda x: gmathify(imemoize(x))  # noqa: F821
    a = mi(s(1, 3, ...))  # noqa: F821
    b = mi(s(2, 4, ...))  # noqa: F821
    c = lambda: a() + b()
    assert tuple(take(5, c())) == (3, 7, 11, 15, 19)  # noqa: F821
    assert tuple(take(5, c())) == (3, 7, 11, 15, 19)  # now it's a new instance; no recomputation  # noqa: F821

    factorials = mi(scanl(mul, 1, s(1, 2, ...)))  # 0!, 1!, 2!, ...  # noqa: F821
    assert last(take(6, factorials())) == 120  # noqa: F821
    assert first(drop(5, factorials())) == 120  # noqa: F821

    squares = s(1, 2, ...)**2  # noqa: F821
    assert last(take(10, squares)) == 100  # noqa: F821

    harmonic = 1 / s(1, 2, ...)  # noqa: F821
    assert last(take(10, harmonic)) == 1 / 10  # noqa: F821

    # unpythonic's continuations are supported
    with continuations:
        k = None  # kontinuation
        def setk(*args, cc):
            nonlocal k
            k = cc  # current continuation, i.e. where to go after setk() finishes
            return args  # tuple means multiple-return-values
        def doit():
            lst = ['the call returned']
            *more, = call_cc[setk('A')]
            return lst + list(more)
        assert doit() == ['the call returned', 'A']
        # We can now send stuff into k, as long as it conforms to the
        # signature of the assignment targets of the "call_cc".
        assert k('again') == ['the call returned', 'again']
        assert k('thrice', '!') == ['the call returned', 'thrice', '!']

    # as is unpythonic's tco
    with tco:
        def fact(n):
            def f(k, acc):
                if k == 1:
                    return acc
                return f(k - 1, k * acc)
            return f(n, 1)  # TODO: doesn't work as f(n, acc=1) due to curry's kwarg handling
        assert fact(4) == 24
        print("Performance...")
        with timer() as tictoc:
            fact(5000)  # no crash, but Pytkell is a bit slow
        print("    Time taken for factorial of 5000: {:g}s".format(tictoc.dt))

    print("All tests PASSED")

if __name__ == '__main__':
    runtests()
