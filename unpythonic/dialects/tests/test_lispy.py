# -*- coding: utf-8 -*-
"""Test the Lispy dialect.

Like Lispython, but more pythonic: nothing is imported implicitly,
except the macros injected by the dialect template (to perform the
whole-module semantic changes at macro expansion time).
"""

from ...dialects import dialects, Lispy  # noqa: F401

from ...syntax import macros, test, the  # noqa: F401
from ...test.fixtures import session, testset

from ...syntax import macros, continuations, call_cc, letrec, fn, local, cond  # noqa: F401, F811
from ...syntax import _  # optional, makes IDEs happy
from ...funutil import Values

def runtests():
    print(f"Hello from {__lang__}!")  # noqa: F821, the dialect template defines it.

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

        # the underscore (in Lispy, the `fn` macro must be imported explicitly)
        cube = fn[_**3]
        test[cube(3) == 27]
        test[cube.__name__ == "cube"]

        my_mul = fn[_ * _]
        test[my_mul(2, 3) == 6]
        test[my_mul.__name__ == "my_mul"]

    # lambdas can have multiple expressions and local variables
    #
    # If you need to return a literal list from a lambda, use an extra set of
    # brackets; the outermost brackets always enable multiple-expression mode.
    #
    with testset("implicit multilambda"):
        # In Lispy, the `local` macro must be imported explicitly.
        # `local[name << value]` makes a local variable in a multilambda (or in any `do[]` environment).
        mylam = lambda x: [local[y << 2 * x],  # noqa: F821
                           y + 1]  # noqa: F821
        test[mylam(10) == 21]

        a = lambda x: [local[t << x % 2],  # noqa: F821
                       cond[t == 0, "even",  # noqa: F821
                            t == 1, "odd",
                            None]]  # cond[] requires an else branch
        test[a(2) == "even"]
        test[a(3) == "odd"]

    # MacroPy #21; namedlambda must be in its own with block in the
    # dialect implementation or the particular combination of macros
    # invoked by Lispy will fail (uncaught jump, __name__ not set).
    #
    # With `mcpyrate` this shouldn't matter, but we're keeping the example.
    with testset("autonamed letrec lambdas, multiple-expression let body"):
        t = letrec[[evenp << (lambda x: (x == 0) or oddp(x - 1)),  # noqa: F821
                    oddp << (lambda x:(x != 0) and evenp(x - 1))] in  # noqa: F821
                   [local[x << evenp(100)],  # noqa: F821, multi-expression let body is a do[] environment
                    (x, evenp.__name__, oddp.__name__)]]  # noqa: F821
        test[t == (True, "evenp", "oddp")]

    with testset("integration with continuations"):
        with continuations:  # has TCO; should be skipped by the implicit `with tco` inserted by the dialect
            k = None  # kontinuation
            def setk(*args, cc):
                nonlocal k
                k = cc  # current continuation, i.e. where to go after setk() finishes
                Values(*args)  # multiple-return-values
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
