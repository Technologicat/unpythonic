# -*- coding: utf-8 -*-
"""Lispy prefix syntax for function calls.

**CAUTION**: Experimental, **not** recommended for use in production code."""

from ...syntax import macros, test, test_raises  # noqa: F401
from ...test.fixtures import testset, returns_normally

from ...syntax import macros, prefix, q, u, kw, curry, let, do  # noqa: F401, F811

from ...fold import foldr
from ...fun import composerc as compose, apply
from ...llist import cons, nil, ll

# Use "with show_expanded:" to see what it did.
#from macropy.tracing import macros, show_expanded

def runtests():
    with testset("unpythonic.syntax.prefix"):
        with prefix:
            (print, "hello world")
            x = 42  # can write any regular Python, too

            with testset("quote operator"):
                # quote operator q locally turns off the function-call transformation:
                t1 = (q, 1, 2, (3, 4), 5)  # q takes effect recursively
                t2 = (q, 17, 23, x)  # unlike in Lisps, x refers to its value even in a quote
                (print, t1, t2)

                # unquote operator u locally turns the transformation back on:
                t3 = (q, (u, print, 42), (print, 42), "foo", "bar")
                test[t3 == (q, None, (print, 42), "foo", "bar")]

                # quotes nest; call transformation made when quote level == 0
                t4 = (q, (print, 42), (q, (u, u, print, 42)), "foo", "bar")
                test[t4 == (q, (print, 42), (None,), "foo", "bar")]

            with testset("tuple in load context denotes a call"):
                # Be careful:
                test_raises[TypeError,
                            (x,),  # in a prefix block, this 1-element tuple means "call the 0-arg function x"
                            "should have attempted to call x"]

                test[returns_normally((q, x))]  # quoted, OK!

                # Function call transformation only applies to tuples in load context
                # (i.e. NOT on the LHS of an assignment)
                a, b = (q, 100, 200)
                test[a == 100 and b == 200]
                a, b = (q, b, a)  # pythonic swap in prefix syntax; must quote RHS
                test[a == 200 and b == 100]

            with testset("kwargs"):
                # give named args with kw(...) [it's syntax, not really a function!]:
                def f(*, a, b):
                    return (q, a, b)
                # in one kw(...), or...
                test[(f, kw(a="hi there", b="foo")) == (q, "hi there", "foo")]
                # in several kw(...), doesn't matter
                test[(f, kw(a="hi there"), kw(b="foo")) == (q, "hi there", "foo")]
                # in case of duplicate name across kws, rightmost wins
                test[(f, kw(a="hi there"), kw(b="foo"), kw(b="bar")) == (q, "hi there", "bar")]

            with testset("starargs"):
                # give *args with unpythonic.fun.apply, like in Lisps:
                lst = [1, 2, 3]
                def g(*args, **kwargs):
                    return args + tuple(sorted(kwargs.items()))
                test[(apply, g, lst) == (q, 1, 2, 3)]
                # lst goes last; may have other args first
                test[(apply, g, "hi", "ho", lst) == (q, "hi", "ho", 1, 2, 3)]
                # named args in apply are also fine
                test[(apply, g, "hi", "ho", lst, kw(myarg=4)) == (q, "hi", "ho", 1, 2, 3, ('myarg', 4))]

            with testset("integration with let and do"):
                # prefix leaves alone the let binding syntax ((name0, value0), ...)
                a = let((x, 42))[x << x + 1]
                test[a == 43]

                # but the RHSs of the bindings are transformed normally:
                def double(x):
                    return 2 * x
                a = let((x, (double, 21)))[x << x + 1]
                test[a == 43]

                # similarly, prefix leaves the "body tuple" of a do alone
                # (syntax, not semantically a tuple), but recurses into it:
                a = do[1, 2, 3]
                test[a == 3]
                a = do[1, 2, (double, 3)]
                test[a == 6]

                # the extra bracket syntax has no danger of confusion, as it's a list, not tuple
                a = let((x, 3))[[
                          1,
                          2,
                          (double, x)]]
                test[a == 6]

        # Introducing the LisThEll programming language: an all-in-one solution with
        # the prefix syntax of Lisp, the speed of Python, and the readability of Haskell!
        with testset("LisThEll"):
            # `prefix` is a first-pass macro, so placed on the outside, it expands first.
            with prefix:
                with curry:
                    mymap = lambda f: (foldr, (compose, cons, f), nil)
                    double = lambda x: 2 * x
                    (print, (mymap, double, (q, 1, 2, 3)))
                    test[(mymap, double, (q, 1, 2, 3)) == ll(2, 4, 6)]

if __name__ == '__main__':
    runtests()
