# -*- coding: utf-8 -*-

from ..syntax import macros, test, test_raises  # noqa: F401
from .fixtures import session, testset

from operator import add, mul
from functools import partial

from ..fold import (scanl, scanr, scanl1, scanr1, rscanl, rscanl1,
                    foldl, foldr, reducel, reducer, rreducel, rfoldl,
                    unfold, unfold1, prod, running_minmax, minmax)
from ..fun import curry, composer, composerc, composel, to1st, rotate
from ..llist import cons, nil, ll, lreverse
from ..it import take, tail

def runtests():
    # scan/accumulate: lazy fold that yields intermediate results.
    with testset("scan"):
        test[tuple(scanl(add, 0, range(1, 5))) == (0, 1, 3, 6, 10)]
        test[tuple(scanr(add, 0, range(1, 5))) == (0, 4, 7, 9, 10)]
        test[tuple(scanl(mul, 1, range(2, 6))) == (1, 2, 6, 24, 120)]
        test[tuple(scanr(mul, 1, range(2, 6))) == (1, 5, 20, 60, 120)]

        test[tuple(scanl(cons, nil, ll(1, 2, 3))) == (nil, ll(1), ll(2, 1), ll(3, 2, 1))]
        test[tuple(scanr(cons, nil, ll(1, 2, 3))) == (nil, ll(3), ll(2, 3), ll(1, 2, 3))]

        # scanl1, scanr1 are a scan with a single input, with init optional.
        test[tuple(scanl1(add, (1, 2, 3))) == (1, 3, 6)]
        test[tuple(scanr1(add, (1, 2, 3))) == (3, 5, 6)]

        # empty input with no init yields an empty iterable
        test[tuple(scanl1(add, ())) == ()]
        test[tuple(scanr1(add, ())) == ()]

        # rscanl1: reverse input, then scanl1.
        test[tuple(rscanl1(add, (1, 2, 3))) == (3, 5, 6)]

    # in contrast, fold just returns the final result.
    with testset("fold"):
        test[foldl(cons, nil, ll(1, 2, 3)) == ll(3, 2, 1)]
        test[foldr(cons, nil, ll(1, 2, 3)) == ll(1, 2, 3)]

        # reduce is a fold with a single input, with init optional.
        test[reducel(add, (1, 2, 3)) == 6]
        test[reducer(add, (1, 2, 3)) == 6]

        # rreducel: reverse input, then reducel.
        test[rreducel(add, (1, 2, 3)) == 6]

    with testset("partial sums and products via scan"):
        psums = composer(tail, curry(scanl, add, 0))  # tail to drop the init value
        pprods = composer(tail, curry(scanl, mul, 1))
        data = range(1, 5)
        test[tuple(psums(data)) == (1, 3, 6, 10)]
        test[tuple(pprods(data)) == (1, 2, 6, 24)]

        psums = curry(scanl1, add)  # or use the fact the 1-input variant needs no init
        pprods = curry(scanl1, mul)
        data = range(1, 5)
        test[tuple(psums(data)) == (1, 3, 6, 10)]
        test[tuple(pprods(data)) == (1, 2, 6, 24)]

    with testset("append tuple example"):
        def append_tuple(a, b, acc):
            return acc + ((a, b),)
        test[foldl(append_tuple, (), (1, 2, 3), (4, 5)) == ((1, 4), (2, 5))]
        test[foldr(append_tuple, (), (1, 2, 3), (4, 5)) == ((2, 5), (1, 4))]
        test[rfoldl(append_tuple, (), (1, 2, 3), (4, 5)) == ((3, 5), (2, 4))]
        test[tuple(rscanl(append_tuple, (), (1, 2, 3), (4, 5))) == ((), ((3, 5),), ((3, 5), (2, 4)))]

    with testset("lispy map via folding"):
        def mymap_one(f, iterable):
            f_then_cons = composer(cons, to1st(f))  # args: elt, acc
            return foldr(f_then_cons, nil, iterable)
        double = lambda x: 2 * x
        test[mymap_one(double, ll(1, 2, 3)) == ll(2, 4, 6)]
        def mymap_one2(f, iterable):
            f_then_cons = composel(to1st(f), cons)  # args: elt, acc
            return foldr(f_then_cons, nil, iterable)
        test[mymap_one2(double, ll(1, 2, 3)) == ll(2, 4, 6)]

        # point-free-ish style
        mymap_one3 = lambda f: partial(foldr, composer(cons, to1st(f)), nil)
        doubler = mymap_one3(double)
        test[doubler(ll(1, 2, 3)) == ll(2, 4, 6)]

        # one arg too many; cons in the compose chain expects 2 args (acc is one)
        test_raises[TypeError, doubler(ll(1, 2, 3), ll(4, 5, 6))]

    with testset("integration with curry"):
        # minimum arity of fold functions is 3, to allow use with curry:
        mymap_one4 = lambda f: curry(foldr, composer(cons, to1st(f)), nil)
        doubler = mymap_one4(double)
        test[doubler(ll(1, 2, 3)) == ll(2, 4, 6)]

        # curry supports passing through on the right any args over the max arity.
        # If an intermediate result is a callable, it is invoked on the remaining
        # positional args:
        test[curry(mymap_one4, double, ll(1, 2, 3)) == ll(2, 4, 6)]

        # But having any args remaining when the top-level curry context exits
        # is an error:
        test_raises[TypeError, curry(double, 2, "unused extra arg")]

        # This also works; curried f takes one argument and the second one is passed
        # through on the right; this two-tuple then ends up as the arguments to cons.
        mymap_one5 = lambda f: curry(foldr, composer(cons, curry(f)), nil)
        test[curry(mymap_one5, double, ll(1, 2, 3)) == ll(2, 4, 6)]

        # Finally, we can drop the inner curry by using a currying compose.
        # This is as close to "(define (map f) (foldr (compose cons f) empty)"
        # (#lang spicy) as we're gonna get in pure Python.
        mymap = lambda f: curry(foldr, composerc(cons, f), nil)
        test[curry(mymap, double, ll(1, 2, 3)) == ll(2, 4, 6)]

        # The currying has actually made it not just map one, but general map that
        # accepts multiple inputs.
        #
        # The iterables are taken by the processing function. acc, being the last
        # argument, is passed through on the right. The output from the processing
        # function - one new item - and acc then become a two-tuple, which gets
        # passed into cons.
        myadd = lambda x, y: x + y  # can't inspect signature of builtin add
        test[curry(mymap, myadd, ll(1, 2, 3), ll(2, 4, 6)) == ll(3, 6, 9)]

        # map_longest. foldr would walk the inputs from the right; use foldl.
        mymap_longestrev = lambda f: curry(foldl, composerc(cons, f), nil, longest=True)
        mymap_longest = composerc(lreverse, mymap_longestrev)
        def noneadd(a, b):
            if all(x is not None for x in (a, b)):
                return a + b
        test[curry(mymap_longest, noneadd, ll(1, 2, 3), ll(2, 4)) == ll(3, 6, None)]

        # Lazy map, like Python's builtin.
        def makeop(f):
            @rotate(-1)  # --> op(*elts, acc)
            def op(acc, *elts):
                return f(*elts)
            return op
        mymap_ = curry(lambda f: curry(scanl, makeop(f), None))  # --> (None, *map(...))
        mymap2 = lambda *args: tail(mymap_(*args))
        test[tuple(curry(mymap2, myadd, (1, 2, 3), (2, 4, 6))) == (3, 6, 9)]

        reverse_one = curry(foldl, cons, nil)
        test[reverse_one(ll(1, 2, 3)) == ll(3, 2, 1)]

        append_two = lambda a, b: foldr(cons, b, a)  # a, b: linked lists
        test[append_two(ll(1, 2, 3), ll(4, 5, 6)) == ll(1, 2, 3, 4, 5, 6)]

        # see upythonic.llist.lappend
        append_many = lambda *lsts: foldr(append_two, nil, lsts)
        test[append_many(ll(1, 2), ll(3, 4), ll(5, 6)) == ll(1, 2, 3, 4, 5, 6)]

        mysum = curry(foldl, add, 0)
        myprod = curry(foldl, mul, 1)
        a = ll(1, 2)
        b = ll(3, 4)
        test[mysum(append_two(a, b)) == 10]
        test[myprod(b) == 12]

        # using a tuple return value here would confuse curry, see #32.
        # https://github.com/Technologicat/unpythonic/issues/32
        packtwo = lambda a, b: ll(a, b)
        test[(foldl(composerc(cons, packtwo), nil, (1, 2, 3), (4, 5), longest=True) ==
              ll(ll(3, None), ll(2, 5), ll(1, 4)))]

        @rotate(-1)               # use rotate...
        def zipper(acc, *rest):   # ...so that we can use the *args syntax to declare this...
            return acc + (rest,)  # ...even though the input is (e1, ..., en, acc).
        # def zipper(*args):  # straightforward version
        #     *rest, acc = args
        #     return acc + (tuple(rest),)
        zipl1 = curry(foldl, zipper, ())
        zipr1 = curry(foldr, zipper, ())
        test[zipl1((1, 2, 3), (4, 5, 6), (7, 8)) == ((1, 4, 7), (2, 5, 8))]
        test[zipr1((1, 2, 3), (4, 5, 6), (7, 8)) == ((2, 5, 8), (1, 4, 7))]

    with testset("unfold"):
        def step2(k):  # x0, x0 + 2, x0 + 4, ...
            return (k, k + 2)  # (value, newstate)

        def fibo(a, b):
            return (a, b, a + b)  # (value, *newstates)

        def myiterate(f, x):  # x0, f(x0), f(f(x0)), ...
            return (x, f, f(x))

        def zip_two(As, Bs):
            if len(As) and len(Bs):
                (A0, *moreAs), (B0, *moreBs) = As, Bs
                return ((A0, B0), moreAs, moreBs)

        test[tuple(take(10, unfold1(step2, 10))) == (10, 12, 14, 16, 18, 20, 22, 24, 26, 28)]
        test[tuple(take(10, unfold(fibo, 1, 1))) == (1, 1, 2, 3, 5, 8, 13, 21, 34, 55)]
        test[tuple(take(5, unfold(myiterate, lambda x: x**2, 2))) == (2, 4, 16, 256, 65536)]
        test[tuple(unfold(zip_two, (1, 2, 3, 4), (5, 6, 7))) == ((1, 5), (2, 6), (3, 7))]

        # A finite sequence can return `None` from the proc to signify the sequence ends.
        def upto10(k):
            if k < 10:
                return (k, k + 1)
            # else: return None, to signify the sequence ends.
        test[tuple(unfold1(upto10, 0)) == tuple(range(10))]

    # Product. Missing battery, considering stdlib has sum().
    with testset("prod (product of elements of iterable)"):
        test[prod((2, 3, 4)) == 24]

    # Extract both min and max in one pass over an iterable.
    with testset("minmax"):
        test[tuple(running_minmax((1, 2, 3))) == ((1, 1), (1, 2), (1, 3))]
        test[tuple(running_minmax((3, 2, 1))) == ((3, 3), (2, 3), (1, 3))]
        test[minmax((1, 2, 3)) == (1, 3)]

        test[tuple(running_minmax(())) == ()]

if __name__ == '__main__':  # pragma: no cover
    with session(__file__):
        runtests()
