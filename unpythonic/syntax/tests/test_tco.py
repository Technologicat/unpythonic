# -*- coding: utf-8 -*-
"""Automatic tail-call optimization (TCO)."""

from ...syntax import macros, test, test_raises, fail  # noqa: F401
from ...test.fixtures import session, testset, returns_normally

from ...syntax import (macros, tco, autoreturn, autocurry, do, let, letseq, dletrec,  # noqa: F401, F811
                       quicklambda, f, _, continuations, call_cc)

from ...ec import call_ec
from ...fploop import looped_over
from ...fun import withself, curry

def runtests():
    # - any explicit return statement in a function body is TCO'd
    # - any expression determined to be in a return-value position is analyzed
    #   to find the subexpression in tail position, and that subexpression is TCO'd
    #   - so this works with lambdas, too
    #   - the analyzer supports "a if p else b", "and", "or", do[] and the
    #     let[] constructs (aif[] and cond[] expand to a combination of these
    #     so they're ok, too)
    #   - in an expression involving "and" or "or", only
    #     **the last item of the whole and/or expression**
    #     is considered to be in tail position.
    with tco:
        with testset("basic usage in def"):
            def deftest():
                def evenp(x):
                    if x == 0:
                        return True
                    return oddp(x - 1)
                def oddp(x):
                    if x != 0:
                        return evenp(x - 1)
                    return False
                test[evenp(10000) is True]
                test[oddp(10000) is False]
            deftest()

        with testset("basic usage in lambda"):
            def lamtest():
                evenp = lambda x: (x == 0) or oddp(x - 1)
                oddp = lambda x: (x != 0) and evenp(x - 1)
                test[evenp(10000) is True]
            lamtest()

            # test also without the surrounding def inside the "with tco" block
            evenp = lambda x: (x == 0) or oddp(x - 1)
            oddp = lambda x: (x != 0) and evenp(x - 1)
            test[evenp(10000) is True]

            # self-referring lambda
            fact = withself(lambda self, n, acc=1:
                            acc if n == 0 else self(n - 1, n * acc))
            test[fact(5) == 120]
            test[returns_normally(fact(5000))]  # no crash

        # works with let constructs
        with testset("basic usage in let constructs"):
            @dletrec((evenp, lambda x: (x == 0) or oddp(x - 1)),  # noqa: F821, `dletrec` defines `evenp` here.
                     (oddp, lambda x: (x != 0) and evenp(x - 1)))  # noqa: F821
            def g(x):
                return evenp(x)
            test[g(9001) is False]

            def g(x):
                return let[(y, 3 * x)][y]  # noqa: F821, `let` defines `y` here.
            test[g(10) == 30]

            def h(x):
                return let[(y, 2 * x)][g(y)]  # noqa: F821
            test[h(10) == 60]

            def h(x):
                return letseq[(y, x),  # noqa: F821, `letseq` defines `y` here.
                              (y, y + 1),  # noqa: F821
                              (y, y + 1)][g(y)]  # noqa: F821
            test[h(10) == 36]

    with testset("integration with autoreturn"):
        # note: apply autoreturn first (first pass, so must be on the outside to run first)
        with autoreturn:
            with tco:
                def evenp(x):
                    if x == 0:
                        True
                    else:
                        oddp(x - 1)
                def oddp(x):
                    if x != 0:
                        evenp(x - 1)
                    else:
                        False
                test[evenp(10000) is True]
                test[oddp(10000) is False]

    with testset("integration with call_ec"):
        with tco:
            def g(x):
                return 2 * x

            @call_ec
            def result(ec):
                print("hi")
                ec(g(21))  # the call in the args of an ec gets TCO'd
                fail["This line should not be reached."]  # pragma: no cover
            test[result == 42]

            result = call_ec(lambda ec:
                               do[print("hi2"),
                                  ec(g(21)),
                                  fail["This line should not be reached."]])
            test[result == 42]

            @call_ec
            def silly(ec):
                return ec(g(21))  # redundant "return" optimized away from the AST; the ec already escapes.
                fail["This line should not be reached."]  # pragma: no cover
            test[silly == 42]

    with testset("integration with autocurry"):
        def testcurrycombo():
            with tco:
                # Currying here makes no sense, but test that it expands correctly.
                # We should get trampolined(curry(call_ec(...))), which produces the desired result.
                test[call_ec(curry(lambda ec: ec(42))) == 42]
        testcurrycombo()
        # This version auto-inserts curry after the inner macros have expanded.
        # This should work, too.
        with autocurry:
            with tco:
                test[call_ec(lambda ec: ec(42)) == 42]

    with testset("integration with fploop"):
        # This requires special handling. `@looped_over` has its own trampoline,
        # `with tco` must avoid adding another one.
        with tco:
            @looped_over(range(10), acc=0)
            def result(loop, x, acc):
                return loop(acc + x)
            test[result == 45]
            test[looped_over(range(10), acc=0)(lambda loop, x, acc: loop(acc + x)) == 45]

    with testset("integration with quicklambda"):
        # f[] must expand first so that tco sees it as a lambda.
        # `quicklambda` is a first-pass macro, so placed on the outside, it expands first.
        with quicklambda:
            with tco:
                def g(x):
                    return 2 * x

                # TODO: Improve test to actually detect the tail call.
                # TODO: Now we just test this runs without errors.
                func1 = f[g(3 * _)]  # tail call
                test[func1(10) == 60]

                func2 = f[3 * g(_)]  # no tail call
                test[func2(10) == 60]

    with testset("integration with continuations"):
        with tco:
            evenp = lambda x: (x == 0) or oddp(x - 1)
            oddp = lambda x: (x != 0) and evenp(x - 1)  # noqa: F811, the previous one is no longer used.
            test[evenp(10000) is True]

            with continuations:  # should be skipped by `tco`, since `continuations` already has TCO
                k = None  # kontinuation
                def setk(*args, cc):
                    nonlocal k
                    k = cc  # current continuation, i.e. where to go after setk() finishes
                    return args  # tuple means multiple-return-values
                def doit():
                    lst = ['the call returned']
                    *more, = call_cc[setk('A')]
                    return lst + list(more)
                test[doit() == ['the call returned', 'A']]
                # We can now send stuff into k, as long as it conforms to the
                # signature of the assignment targets of the "call_cc".
                test[k('again') == ['the call returned', 'again']]
                test[k('thrice', '!') == ['the call returned', 'thrice', '!']]

if __name__ == '__main__':  # pragma: no cover
    with session(__file__):
        runtests()
