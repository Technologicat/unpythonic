# -*- coding: utf-8 -*-
"""Test the Listhell dialect."""

# from mcpyrate.debug import dialects, StepExpansion
from ...dialects import dialects, Listhell  # noqa: F401

from ...syntax import macros, test  # noqa: F401
from ...test.fixtures import session, testset

from ...syntax import macros, let, where, local, delete, do  # noqa: F401, F811
from unpythonic import foldr, cons, nil, ll

def runtests():
    # Function calls can be made in prefix notation, like in Lisps.
    # The first element of a literal tuple is the function to call,
    # the rest are its arguments.
    (print, f"Hello from {__lang__}!")  # noqa: F821, the dialect template defines it.

    x = 42  # can write any regular Python, too

    # quote operator q locally turns off the function-call transformation:
    t1 = (q, 1, 2, (3, 4), 5)  # q takes effect recursively  # noqa: F821, the dialect template defines `q`.
    t2 = (q, 17, 23, x)  # unlike in Lisps, x refers to its value even in a quote  # noqa: F821
    (print, t1, t2)

    # Calls to the test framework are written with pythonic function call notation,
    # because if the `prefix` macro isn't working, then writing them in prefix notation
    # could cause a crash while testing.
    with testset("quoting"):
        # unquote operator u locally turns the transformation back on:
        t3 = (q, (u, print, 42), (print, 42), "foo", "bar")  # noqa: F821
        test[t3 == (q, None, (print, 42), "foo", "bar")]  # noqa: F821

        # quotes nest; call transformation made when quote level == 0
        t4 = (q, (print, 42), (q, (u, u, print, 42)), "foo", "bar")  # noqa: F821
        test[t4 == (q, (print, 42), (None,), "foo", "bar")]  # noqa: F821

        # Be careful:
        #
        # In Listhell, `(x,)` means "call the 0-arg function `x`".
        # But if `x` is not callable, `currycall` will return
        # the value as-is (needed for interaction with `call_ec`
        # and some other replace-def-with-value decorators).
        #
        # `(q, x)` means "the tuple where the first element is `x`".
        test[(x,) == 42]
        test[(q, x) == (tuple, [x])]  # noqa: F821

    # give named args with kw(...) [it's syntax, not really a function!]:
    with testset("named arguments with kw()"):
        def f(*, a, b):
            return (q, a, b)  # noqa: F821
        # in one kw(...), or...
        test[(f, kw(a="hi there", b="foo")) == (q, "hi there", "foo")]  # noqa: F821
        # in several kw(...), doesn't matter
        test[(f, kw(a="hi there"), kw(b="foo")) == (q, "hi there", "foo")]  # noqa: F821
        # in case of duplicate name across kws, rightmost wins
        test[(f, kw(a="hi there"), kw(b="foo"), kw(b="bar")) == (q, "hi there", "bar")]  # noqa: F821

    # give *args with unpythonic.apply, like in Lisps:
    with testset("starargs with apply()"):
        lst = [1, 2, 3]
        def g(*args, **kwargs):
            return args + (tuple, (sorted, (kwargs.items,)))
        test[(apply, g, lst) == (q, 1, 2, 3)]  # noqa: F821
        # lst goes last; may have other args first
        test[(apply, g, "hi", "ho", lst) == (q, "hi", "ho", 1, 2, 3)]  # noqa: F821
        # named args in apply are also fine
        test[(apply, g, "hi", "ho", lst, kw(myarg=4)) == (q, "hi", "ho", 1, 2, 3, ('myarg', 4))]  # noqa: F821

    # Function call transformation only applies to tuples in load context
    # (i.e. NOT on the LHS of an assignment)
    with testset("no transform on LHS of assignment"):
        a, b = (q, 100, 200)  # noqa: F821
        test[a == 100 and b == 200]
        a, b = (q, b, a)  # pythonic swap in prefix syntax; must quote RHS  # noqa: F821
        test[a == 200 and b == 100]

    with testset("transform of let bindings"):
        # the prefix syntax leaves alone the let binding syntax even when using tuples, ((name0, value0), ...)
        a = let[(x, 42)][x << x + 1]
        test[a == 43]

        # but the RHSs of the bindings are transformed normally:
        def double(x):
            return 2 * x
        a = let[(x, (double, 21))][x << x + 1]
        test[a == 43]

        # As of v0.15.0, the preferred let bindings syntax is env-assignment,
        # so these examples become:
        a = let[x << 42][x << x + 1]
        test[a == 43]

        a = let[x << (double, 21)][x << x + 1]
        test[a == 43]

    # similarly, the prefix syntax leaves the "body tuple" of a do alone
    # (syntax, not semantically a tuple), but recurses into it:
    with testset("transform of do body"):
        a = do[1, 2, 3]
        test[a == 3]
        a = do[1, 2, (double, 3)]
        test[a == 6]

        # the extra bracket syntax (implicit do) has no danger of confusion, as it's a list, not tuple
        a = let[x << 3][[
                  1,
                  2,
                  (double, x)]]
        test[a == 6]

    with testset("final example"):
        my_map = lambda f: (foldr, (compose, cons, f), nil)  # noqa: F821
        test[(my_map, double, (q, 1, 2, 3)) == (ll, 2, 4, 6)]  # noqa: F821

if __name__ == '__main__':
    with (session, __file__):
        (runtests,)
