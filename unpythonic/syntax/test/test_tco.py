# -*- coding: utf-8 -*-
"""Automatic tail-call optimization (TCO)."""

from ...syntax import (macros, tco, autoreturn, curry, do, let, letseq, dletrec,  # noqa: F401
                       quicklambda, f, _, continuations, call_cc)

from ...ec import call_ec
from ...fploop import looped_over
from ...fun import withself

def test():
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
        # works with defs
        def deftest():
            def evenp(x):
                if x == 0:
                    return True
                return oddp(x - 1)
            def oddp(x):
                if x != 0:
                    return evenp(x - 1)
                return False
            assert evenp(10000) is True
        deftest()

        # works with lambdas
        def lamtest():
            evenp = lambda x: (x == 0) or oddp(x - 1)
            oddp = lambda x: (x != 0) and evenp(x - 1)
            assert evenp(10000) is True
        lamtest()

        # works with let constructs
        @dletrec((evenp, lambda x: (x == 0) or oddp(x - 1)),  # noqa: F821, `dletrec` defines `evenp` here.
                 (oddp, lambda x: (x != 0) and evenp(x - 1)))  # noqa: F821
        def g(x):
            return evenp(x)
        assert g(9001) is False

        def g(x):
            return let((y, 3 * x))[y]  # noqa: F821, `let` defines `y` here.
        assert g(10) == 30

        def h(x):
            return let((y, 2 * x))[g(y)]  # noqa: F821
        assert h(10) == 60

        def h(x):
            return letseq((y, x),  # noqa: F821, `letseq` defines `y` here.
                          (y, y + 1),  # noqa: F821
                          (y, y + 1))[g(y)]  # noqa: F821
        assert h(10) == 36

    # test also lambdas with no surrounding def inside the "with tco" block
    with tco:
        evenp = lambda x: (x == 0) or oddp(x - 1)
        oddp = lambda x: (x != 0) and evenp(x - 1)
        assert evenp(10000) is True

    # test also with self-referring lambda
    with tco:
        fact = withself(lambda self, n, acc=1:
                          acc if n == 0 else self(n - 1, n * acc))
        assert fact(5) == 120
        fact(5000)  # no crash

    # tco and autoreturn combo (note: apply autoreturn first)
    with autoreturn, tco:
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
        assert evenp(10000) is True

    # call_ec combo
    with tco:
        def g(x):
            return 2 * x

        @call_ec
        def result(ec):
            print("hi")
            ec(g(21))  # the call in the args of an ec gets TCO'd
            print("ho")
        assert result == 42

        result = call_ec(lambda ec: do[print("hi2"), ec(g(21)), print("ho2")])
        assert result == 42

    # curry combo
    def testcurrycombo():
        with tco:
            from ...fun import curry  # TODO: can't rename, unpythonic.syntax.util.sort_lambda_decorators won't detect it
            # Currying here makes no sense, but test that it expands correctly.
            # We should get trampolined(call_ec(curry(...))), which produces the desired result.
            assert call_ec(curry(lambda ec: ec(42))) == 42
    testcurrycombo()
    # This version auto-inserts curry after the inner macros have expanded.
    # This should work, too.
    with curry:
        with tco:
            assert call_ec(lambda ec: ec(42)) == 42

    # fploop combo, requires special handling
    # (has its own trampoline, must avoid adding another one)
    with tco:
        @looped_over(range(10), acc=0)
        def result(loop, x, acc):
            return loop(acc + x)
        assert result == 45
        assert looped_over(range(10), acc=0)(lambda loop, x, acc: loop(acc + x)) == 45

    # quicklambda combo (f[] must expand first so that tco sees it as a lambda)
    # TODO: improve test to actually detect the tail call
    with quicklambda, tco:
        def g(x):
            return 2 * x
        func1 = f[g(3 * _)]  # tail call
        assert func1(10) == 60

        func2 = f[3 * g(_)]  # no tail call
        assert func2(10) == 60

    with tco:
        evenp = lambda x: (x == 0) or oddp(x - 1)
        oddp = lambda x: (x != 0) and evenp(x - 1)  # noqa: F811, the previous one is no longer used.
        assert evenp(10000) is True

        with continuations:  # should be skipped by tco, since this already has TCO
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

    print("All tests PASSED")

if __name__ == '__main__':
    test()
