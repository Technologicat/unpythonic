# -*- coding: utf-8 -*-
"""Lispy prefix syntax for function calls.

**CAUTION**: Experimental, **not** recommended for use in production code."""

# Use "with show_expanded:" to see what it did.
#from macropy.tracing import macros, show_expanded

from ...syntax import macros, prefix, q, u, kw, curry, let, do  # noqa: F401

from ...fold import foldr
from ...fun import composerc as compose, apply
from ...llist import cons, nil, ll

def test():
    with prefix:
        (print, "hello world")
        x = 42  # can write any regular Python, too

        # quote operator q locally turns off the function-call transformation:
        t1 = (q, 1, 2, (3, 4), 5)  # q takes effect recursively
        t2 = (q, 17, 23, x)  # unlike in Lisps, x refers to its value even in a quote
        (print, t1, t2)

        # unquote operator u locally turns the transformation back on:
        t3 = (q, (u, print, 42), (print, 42), "foo", "bar")
        assert t3 == (q, None, (print, 42), "foo", "bar")

        # quotes nest; call transformation made when quote level == 0
        t4 = (q, (print, 42), (q, (u, u, print, 42)), "foo", "bar")
        assert t4 == (q, (print, 42), (None,), "foo", "bar")

        # Be careful:
        try:
            (x,)  # in a prefix block, this means "call the 0-arg function x"
        except TypeError:
            pass  # 'int' object is not callable
        else:
            assert False, "should have attempted to call x"
        (q, x)  # OK!

        # give named args with kw(...) [it's syntax, not really a function!]:
        def f(*, a, b):
            return (q, a, b)
        # in one kw(...), or...
        assert (f, kw(a="hi there", b="foo")) == (q, "hi there", "foo")
        # in several kw(...), doesn't matter
        assert (f, kw(a="hi there"), kw(b="foo")) == (q, "hi there", "foo")
        # in case of duplicate name across kws, rightmost wins
        assert (f, kw(a="hi there"), kw(b="foo"), kw(b="bar")) == (q, "hi there", "bar")

        # give *args with unpythonic.fun.apply, like in Lisps:
        lst = [1, 2, 3]
        def g(*args, **kwargs):
            return args + tuple(sorted(kwargs.items()))
        assert (apply, g, lst) == (q, 1, 2, 3)
        # lst goes last; may have other args first
        assert (apply, g, "hi", "ho", lst) == (q, "hi", "ho", 1, 2, 3)
        # named args in apply are also fine
        assert (apply, g, "hi", "ho", lst, kw(myarg=4)) == (q, "hi", "ho", 1, 2, 3, ('myarg', 4))

        # Function call transformation only applies to tuples in load context
        # (i.e. NOT on the LHS of an assignment)
        a, b = (q, 100, 200)
        assert a == 100 and b == 200
        a, b = (q, b, a)  # pythonic swap in prefix syntax; must quote RHS
        assert a == 200 and b == 100

        # prefix leaves alone the let binding syntax ((name0, value0), ...)
        a = let((x, 42))[x << x + 1]
        assert a == 43

        # but the RHSs of the bindings are transformed normally:
        def double(x):
            return 2 * x
        a = let((x, (double, 21)))[x << x + 1]
        assert a == 43

        # similarly, prefix leaves the "body tuple" of a do alone
        # (syntax, not semantically a tuple), but recurses into it:
        a = do[1, 2, 3]
        assert a == 3
        a = do[1, 2, (double, 3)]
        assert a == 6

        # the extra bracket syntax has no danger of confusion, as it's a list, not tuple
        a = let((x, 3))[[
                  1,
                  2,
                  (double, x)]]
        assert a == 6

    # Introducing the LisThEll programming language: an all-in-one solution with
    # the prefix syntax of Lisp, the speed of Python, and the readability of Haskell!
    with prefix, curry:
        mymap = lambda f: (foldr, (compose, cons, f), nil)
        double = lambda x: 2 * x
        (print, (mymap, double, (q, 1, 2, 3)))
        assert (mymap, double, (q, 1, 2, 3)) == ll(2, 4, 6)

    print("All tests PASSED")

if __name__ == '__main__':
    test()
