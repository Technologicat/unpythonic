# -*- coding: utf-8 -*-
"""Automatic tail-call optimization (TCO)."""

from ...syntax import macros, tco, autoreturn, curry, do, let, letseq, dletrec

from ...ec import call_ec
from ...fploop import looped_over

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
            oddp  = lambda x: (x != 0) and evenp(x - 1)
            assert evenp(10000) is True
        lamtest()

        # works with let constructs
        @dletrec((evenp, lambda x: (x == 0) or oddp(x - 1)),
                 (oddp,  lambda x: (x != 0) and evenp(x - 1)))
        def f(x):
            return evenp(x)
        assert f(9001) is False

        def f(x):
            return let((y, 3*x))[y]
        assert f(10) == 30

        def g(x):
            return let((y, 2*x))[f(y)]
        assert g(10) == 60

        def h(x):
            return letseq((y, x),
                          (y, y+1),
                          (y, y+1))[f(y)]
        assert h(10) == 36

    # test also lambdas with no surrounding def inside the "with tco" block
    with tco:
        evenp = lambda x: (x == 0) or oddp(x - 1)
        oddp  = lambda x: (x != 0) and evenp(x - 1)
        assert evenp(10000) is True

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
            return 2*x

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

    print("All tests PASSED")

if __name__ == '__main__':
    test()
