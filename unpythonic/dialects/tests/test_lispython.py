# -*- coding: utf-8 -*-
"""Test the Lispython dialect."""

from ...dialects import dialects, Lispython  # noqa: F401

from ...syntax import macros, test, the  # noqa: F401
from ...test.fixtures import session, testset

from ...syntax import macros, continuations, call_cc  # noqa: F401, F811

# `unpythonic` is effectively `lispython`'s stdlib; not everything gets imported by default.
from ...fold import foldl

# Of course, all of Python's stdlib is available too.
#
# So is **any** Python library; the ability to use arbitrary Python libraries in
# a customized Python-based language is pretty much the whole point of dialects.
#
from operator import mul

def runtests():
    print(f"Hello from {__lang__}!")  # noqa: F821, the dialect template defines it.

    with testset("dialect builtins"):
        test[prod((2, 3, 4)) == 24]  # noqa: F821, bye missing battery, hello new dialect builtin
        test[foldl(mul, 1, (2, 3, 4)) == 24]

        # cons, car, cdr, ll, llist are builtins (for more linked list utils, import them from unpythonic)
        c = cons(1, 2)  # noqa: F821
        test[tuple(c) == (1, 2)]
        test[car(c) == 1]  # noqa: F821
        test[cdr(c) == 2]  # noqa: F821
        test[ll(1, 2, 3) == llist((1, 2, 3))]  # noqa: F821

        # all unpythonic.syntax let[], letseq[], letrec[] constructs are considered dialect builtins
        # (including the decorator versions, let_syntax and abbrev)
        x = let[[a << 21] in 2 * a]  # noqa: F821
        test[x == 42]

        x = letseq[[a << 1,  # noqa: F821
                    a << 2 * a,  # noqa: F821
                    a << 2 * a] in  # noqa: F821
                   a]  # noqa: F821
        test[x == 4]

        # rackety cond
        a = lambda x: cond[x < 0, "nope",  # noqa: F821
                           x % 2 == 0, "even",
                           "odd"]
        test[a(-1) == "nope"]
        test[a(2) == "even"]
        test[a(3) == "odd"]

    # auto-TCO (both in defs and lambdas), implicit return in tail position
    with testset("implicit tco, implicit autoreturn"):
        def fact(n):
            def f(k, acc):
                if k == 1:
                    return acc  # "return" still available for early return
                f(k - 1, k * acc)
            f(n, acc=1)
        test[fact(4) == 24]
        fact(5000)  # no crash (and correct result, since Python uses bignums transparently)

        t = letrec[[evenp << (lambda x: (x == 0) or oddp(x - 1)),  # noqa: F821
                    oddp << (lambda x:(x != 0) and evenp(x - 1))] in  # noqa: F821
                   evenp(10000)]  # no crash  # noqa: F821
        test[t is True]

    # lambdas are named automatically
    with testset("implicit namedlambda"):
        square = lambda x: x**2
        test[square(3) == 9]
        test[square.__name__ == "square"]

        # the underscore (NOTE: due to this, "f" is a reserved name in lispython)
        cube = f[_**3]  # noqa: F821
        test[cube(3) == 27]
        test[cube.__name__ == "cube"]

    # lambdas can have multiple expressions and local variables
    #
    # If you need to return a literal list from a lambda, use an extra set of
    # brackets; the outermost brackets always enable multiple-expression mode.
    #
    with testset("implicit multilambda"):
        mylam = lambda x: [local[y << 2 * x],  # noqa: F821, local[name << value] makes a local variable
                           y + 1]  # noqa: F821
        test[mylam(10) == 21]

        a = lambda x: [local[t << x % 2],  # noqa: F821
                       cond[t == 0, "even",  # noqa: F821
                            t == 1, "odd",
                            None]]  # cond[] requires an else branch
        test[a(2) == "even"]
        test[a(3) == "odd"]

    # MacroPy #21; namedlambda must be in its own with block in the
    # dialect implementation or this particular combination will fail
    # (uncaught jump, __name__ not set).
    #
    # With `mcpyrate` this shouldn't matter, but we're keeping the example.
    with testset("autonamed letrec lambdas, multiple-expression let body"):
        t = letrec[[evenp << (lambda x: (x == 0) or oddp(x - 1)),  # noqa: F821
                    oddp << (lambda x:(x != 0) and evenp(x - 1))] in  # noqa: F821
                   [local[x << evenp(100)],  # noqa: F821, multi-expression let body is a do[] environment
                    (x, evenp.__name__, oddp.__name__)]]  # noqa: F821
        test[t == (True, "evenp", "oddp")]

    # actually the multiple-expression environment is an unpythonic.syntax.do[],
    # which can be used in any expression position.
    with testset("do and do0"):
        x = do[local[z << 2],  # noqa: F821
               3 * z]  # noqa: F821
        test[x == 6]

        # do0[] is the same, but returns the value of the first expression instead of the last one.
        x = do0[local[z << 3],  # noqa: F821
                print("hi from do0, z is {}".format(z))]  # noqa: F821
        test[x == 3]

    with testset("integration with continuations"):
        with continuations:  # should be skipped by the implicit tco inserted by the dialect
            k = None  # kontinuation
            def setk(*args, cc):
                nonlocal k
                k = cc  # current continuation, i.e. where to go after setk() finishes
                Values(*args)  # multiple-return-values  # noqa: F821, Lispython imports Values by default.
            def doit():
                lst = ['the call returned']
                *more, = call_cc[setk('A')]
                lst + list(more)
            test[doit() == ['the call returned', 'A']]
            # We can now send stuff into k, as long as it conforms to the
            # signature of the assignment targets of the "call_cc".
            test[k('again') == ['the call returned', 'again']]
            test[k('thrice', '!') == ['the call returned', 'thrice', '!']]

    # We must have some statement here to make the implicit autoreturn happy,
    # because the continuations testset is the last one, and the top level of
    # a `with continuations` block is not allowed to have a `return`.
    pass

if __name__ == '__main__':
    with session(__file__):
        runtests()
