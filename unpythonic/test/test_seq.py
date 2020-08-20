# -*- coding: utf-8 -*-

from ..syntax import macros, test, test_raises, fail  # noqa: F401
from .fixtures import session, testset

from ..seq import (begin, begin0, lazy_begin, lazy_begin0,
                   pipe1, pipe, pipec,
                   piped1, piped, exitpipe,
                   lazy_piped1, lazy_piped,
                   do, do0, assign)

from ..ec import call_ec

def runtests():
    with testset("sequencing side effects in a lambda"):
        f1 = lambda x: begin(print("cheeky side effect"), 42 * x)
        test[f1(2) == 84]

        f2 = lambda x: begin0(42 * x, print("cheeky side effect"))
        test[f2(2) == 84]

        f3 = lambda x: lazy_begin(lambda: print("cheeky side effect"),
                                  lambda: 42 * x)
        test[f3(2) == 84]

        f4 = lambda x: lazy_begin0(lambda: 42 * x,
                                   lambda: print("cheeky side effect"))
        test[f4(2) == 84]

    # pipe: sequence functions
    with testset("pipe (sequence functions)"):
        double = lambda x: 2 * x
        inc = lambda x: x + 1
        test[pipe1(42, double, inc) == 85]  # 1-in-1-out
        test[pipe1(42, inc, double) == 86]
        test[pipe(42, double, inc) == 85]   # n-in-m-out, supports also 1-in-1-out
        test[pipe(42, inc, double) == 86]

        # 2-in-2-out
        a, b = pipe((2, 3),
                    lambda x, y: (x + 1, 2 * y),
                    lambda x, y: (x * 2, y + 1))
        test[(a, b) == (6, 7)]

        # 2-in-eventually-3-out
        a, b, c = pipe((2, 3),
                       lambda x, y: (x + 1, 2 * y, "foo"),
                       lambda x, y, z: (x * 2, y + 1, "got {}".format(z)))
        test[(a, b, c) == (6, 7, "got foo")]

        # 2-in-3-in-between-2-out
        a, b = pipe((2, 3),
                    lambda x, y: (x + 1, 2 * y, "foo"),
                    lambda x, y, s: (x * 2, y + 1, "got {}".format(s)),
                    lambda x, y, s: (x + y, s))
        test[(a, b) == (13, "got foo")]

        # pipec: curry the functions before running the pipeline
        a, b = pipec((1, 2),
                     lambda x: x + 1,  # extra args passed through on the right
                     lambda x, y: (x * 2, y + 1))
        test[(a, b) == (4, 3)]

        with test_raises(TypeError, "should error when the curry context exits with args remaining"):
            a, b = pipec((1, 2),
                         lambda x: x + 1,
                         lambda x: x * 2)

        # optional shell-like syntax
        test[piped1(42) | double | inc | exitpipe == 85]

        y = piped1(42) | double
        test[y | inc | exitpipe == 85]
        test[y | exitpipe == 84]  # y is never modified by the pipe system

        # multi-arg version
        f = lambda x, y: (2 * x, y + 1)
        g = lambda x, y: (x + 1, 2 * y)
        x = piped(2, 3) | f | g | exitpipe  # --> (5, 8)
        test[x == (5, 8)]

        # abuse multi-arg version for single-arg case
        test[piped(42) | double | inc | exitpipe == 85]

    with testset("lazy pipe (plan computations)"):
        # lazy pipe: compute later
        lst = [1]
        def append_succ(l):
            l.append(l[-1] + 1)
            return l  # important, handed to the next function in the pipe
        p = lazy_piped1(lst) | append_succ | append_succ  # plan a computation
        test[lst == [1]]        # nothing done yet
        p | exitpipe              # run the computation
        test[lst == [1, 2, 3]]  # now the side effect has updated lst.

        # lazy pipe as an unfold
        fibos = []
        def nextfibo(state):
            a, b = state
            fibos.append(a)      # store result by side effect
            return (b, a + b)    # new state, handed to next function in the pipe
        p = lazy_piped1((1, 1))  # load initial state into a lazy pipe
        for _ in range(10):      # set up pipeline
            p = p | nextfibo
        p | exitpipe
        test[fibos == [1, 1, 2, 3, 5, 8, 13, 21, 34, 55]]

        # multi-arg lazy pipe
        p1 = lazy_piped(2, 3)
        p2 = p1 | (lambda x, y: (x + 1, 2 * y, "foo"))
        p3 = p2 | (lambda x, y, s: (x * 2, y + 1, "got {}".format(s)))
        p4 = p3 | (lambda x, y, s: (x + y, s))
        # nothing done yet, and all computations purely functional:
        test[(p1 | exitpipe) == (2, 3)]
        test[(p2 | exitpipe) == (3, 6, "foo")]      # runs the chain up to p2
        test[(p3 | exitpipe) == (6, 7, "got foo")]  # runs the chain up to p3
        test[(p4 | exitpipe) == (13, "got foo")]

        # multi-arg lazy pipe as an unfold
        fibos = []
        def nextfibo(a, b):    # now two arguments
            fibos.append(a)
            return (b, a + b)  # two return values, still expressed as a tuple
        p = lazy_piped(1, 1)
        for _ in range(10):
            p = p | nextfibo
        p | exitpipe
        test[fibos == [1, 1, 2, 3, 5, 8, 13, 21, 34, 55]]

    # do: improved begin() that can name intermediate results
    with testset("do (code imperatively in expressions)"):
        y = do(assign(x=17),
               lambda e: print(e.x),  # 17; uses environment, needs lambda e: ...
               assign(x=23),          # overwrite e.x
               lambda e: print(e.x),  # 23
               42)                    # return value
        test[y == 42]

        y = do(assign(x=17),
               assign(z=lambda e: 2 * e.x),
               lambda e: e.z)
        test[y == 34]

        y = do(assign(x=5),
               assign(f=lambda e: lambda x: x**2),  # callable, needs lambda e: ...
               print("hello from 'do'"),  # value is None; not callable
               lambda e: e.f(e.x))
        test[y == 25]

        # Beware of this pitfall:
        do(lambda e: print("hello 2 from 'do'"),  # delayed because lambda e: ...
           print("hello 1 from 'do'"),
           "foo")
        # Python prints "hello 1 from 'do'" immediately, before do() gets control,
        # because technically, it is **the return value** that is an argument for
        # do().

        # If you need to return the first value instead, use this trick:
        y = do(assign(result=17),
               print("assigned 'result' in env"),
               lambda e: e.result)  # return value
        test[y == 17]

        # or use do0, which does it for you:
        y = do0(17,
                assign(x=42),
                lambda e: print(e.x),
                print("hello from 'do0'"))
        test[y == 17]

        y = do0(assign(x=17),  # the first item of do0 can be an assignment, too
                lambda e: print(e.x))
        test[y == 17]

        # pitfalls!
        #
        # WRONG!
        s = set()
        z = do(lambda e: test[s],   # there is already an item...
               s.add("foo"),        # ...because already added here, before do() gets control.
               lambda e: s)
        test[z == {"foo"}]

        # OK
        s = set()
        z = do(lambda e: test[not s],   # empty, ok!
               lambda e: s.add("foo"),  # now this is delayed until do() hits this line
               lambda e: s)
        test[z == {"foo"}]

        z = call_ec(lambda ec:
                    do(assign(x=42),
                       lambda e: ec(e.x),                                    # IMPORTANT: must delay this!
                       lambda e: fail["This line should not be reached."]))  # and this (as above)
        test[z == 42]

if __name__ == '__main__':  # pragma: no cover
    with session(__file__):
        runtests()
