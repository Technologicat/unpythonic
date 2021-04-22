# -*- coding: utf-8 -*-
"""Let constructs; do (imperative code in expression position)."""

# TODO: Update the @dlet, @dletseq, @dletrec, @blet, @bletseq, @bletrec examples
# TODO: to pass macro arguments using brackets once we bump to minimum Python 3.9.

from ...syntax import macros, test, test_raises  # noqa: F401
from ...test.fixtures import session, testset

from ...syntax import (macros, let, letseq, letrec, where,  # noqa: F401, F811
                       dlet, dletseq, dletrec,
                       blet, bletseq, bletrec,
                       do, do0, local, delete)

from ...seq import begin

x = "the global x"  # for lexical scoping tests

def runtests():
    with testset("do (imperative code in an expression)"):
        # Macro wrapper for unpythonic.seq.do (imperative code in expression position)
        #  - Declare and initialize a local variable with ``local[var << value]``.
        #    Is in scope from the next expression onward, for the (lexical) remainder
        #    of the do.
        #  - Assignment is ``var << value``. Valid from any level inside the ``do``
        #    (including nested ``let`` constructs and similar).
        #  - No need for ``lambda e: ...`` wrappers. Inserted automatically,
        #    so the lines are only evaluated as the underlying seq.do() runs.
        d1 = do[local[x << 17],
                print(x),
                x << 23,
                x]  # do[] returns the value of the last expression
        test[d1 == 23]

        # v0.14.0: do[] now supports deleting previously defined local names with delete[]
        a = 5
        d = do[local[a << 17],  # noqa: F841, yes, d is unused.
               test[a == 17],
               delete[a],
               test[a == 5],  # lexical scoping
               True]

        test_raises[KeyError, do[delete[a], ], "should have complained about deleting nonexistent local 'a'"]

        # do0[]: like do[], but return the value of the **first** expression
        d2 = do0[local[y << 5],  # noqa: F821, `local` defines the name on the LHS of the `<<`.
                 print("hi there, y =", y),  # noqa: F821
                 42]  # evaluated but not used
        test[d2 == 5]

    # Let macros. Lexical scoping supported.
    with testset("let, letseq, letrec basic usage"):
        # parallel binding, i.e. bindings don't see each other
        test[let[(x, 17),
                 (y, 23)][  # noqa: F821, `let` defines `y` here.
                     (x, y)] == (17, 23)]  # noqa: F821

        # sequential binding, i.e. Scheme/Racket let*
        test[letseq[(x, 1),
                    (y, x + 1)][  # noqa: F821
                        (x, y)] == (1, 2)]  # noqa: F821

        test[letseq[(x, 1),
                    (x, x + 1)][  # in a letseq, rebinding the same name is ok
                        x] == 2]

        # letrec sugars unpythonic.lispylet.letrec, removing the need for quotes on LHS
        # and "lambda e: ..." wrappers on RHS (these are inserted by the macro):
        test[letrec[(evenp, lambda x: (x == 0) or oddp(x - 1)),  # noqa: F821, `letrec` defines `evenp` here.
                    (oddp, lambda x: (x != 0) and evenp(x - 1))][  # noqa: F821
                        evenp(42)] is True]  # noqa: F821

        # nested letrecs work, too - each environment is internally named by a gensym
        # so that outer ones "show through":
        test[letrec[(z, 9000)][  # noqa: F821
                 letrec[(evenp, lambda x: (x == 0) or oddp(x - 1)),  # noqa: F821
                        (oddp, lambda x: (x != 0) and evenp(x - 1))][  # noqa: F821
                            (evenp(42), z)]] == (True, 9000)]  # noqa: F821

    with testset("error cases"):
        # let is parallel binding, doesn't see the X in the same let
        test_raises[NameError,
                    let[(X, 1),  # noqa: F821
                        (y, X + 1)][  # noqa: F821
                            print(X, y)],  # noqa: F821
                    "should not see the X in the same let"]

        test_raises[NameError,
                    letseq[(X, y + 1),  # noqa: F821
                           (y, 2)][  # noqa: F821
                               (X, y)],  # noqa: F821
                    "y should not yet be defined on the first line"]

        test_raises[AttributeError,
                    let[(x, 1),
                        (x, 2)][
                            print(x)],
                    "should not be able to rebind the same name in the same let"]

    # implicit do: an extra set of brackets denotes a multi-expr body
    with testset("implicit do (extra bracket syntax for multi-expr let body)"):
        a = let[(x, 1),
                (y, 2)][[  # noqa: F821
                    y << 1337,  # noqa: F821
                    (x, y)]]  # noqa: F821
        test[a == (1, 1337)]

        # only the outermost extra brackets denote a multi-expr body
        a = let[(x, 1),
                (y, 2)][[  # noqa: F821
                    [1, 2]]]
        test[a == [1, 2]]

        # implicit do works also in letseq, letrec
        a = letseq[(x, 1),
                   (y, x + 1)][[  # noqa: F821
                       x << 1337,
                       (x, y)]]  # noqa: F821
        test[a == (1337, 2)]

        a = letrec[(x, 1),
                   (y, x + 1)][[  # noqa: F821
                       x << 1337,
                       (x, y)]]  # noqa: F821
        test[a == (1337, 2)]

    with testset("scoping, name shadowing"):
        # also letrec supports lexical scoping, since `letrec` expands inside out
        # (so the z in the inner scope expands to the inner environment's z,
        # which makes the outer expansion leave it alone):
        out = []
        letrec[(z, 1)][  # noqa: F821
            begin(out.append(z),  # noqa: F821
                  letrec[(z, 2)][  # noqa: F821
                      out.append(z)])]  # (be careful with the parentheses!)  # noqa: F821
        test[out == [1, 2]]

        # same using implicit do (extra brackets)
        out = []
        letrec[(z, 1)][[  # noqa: F821
                 out.append(z),  # noqa: F821
                 letrec[(z, 2)][  # noqa: F821
                     out.append(z)]]]  # noqa: F821
        test[out == [1, 2]]

        # lexical scoping: assignment updates the innermost value by that name:
        out = []
        letrec[(z, 1)][  # noqa: F821
            begin(out.append(z),  # outer z  # noqa: F821
                  # assignment to env is an expression, returns the new value
                  out.append(z << 5),  # noqa: F821
                  letrec[(z, 2)][  # noqa: F821
                      begin(out.append(z),         # inner z  # noqa: F821
                            out.append(z << 7))],  # update inner z  # noqa: F821
                  out.append(z))]  # outer z  # noqa: F821
        test[out == [1, 5, 2, 7, 5]]

        out = []
        letrec[(x, 1)][
            begin(out.append(x),
                  letrec[(z, 2)][  # noqa: F821
                      begin(out.append(z),  # noqa: F821
                            out.append(x << 7))],  # x only defined in outer letrec, updates that
                  out.append(x))]
        test[out == [1, 2, 7, 7]]

        # same using implicit do
        out = []
        letrec[(x, 1)][[
                 out.append(x),
                 letrec[(z, 2)][[  # noqa: F821
                     out.append(z),  # noqa: F821
                     out.append(x << 7)]],
                 out.append(x)]]
        test[out == [1, 2, 7, 7]]

        # letrec bindings are evaluated sequentially
        test[letrec[(x, 1),
                    (y, x + 2)][  # noqa: F821
                        (x, y)] == (1, 3)]  # noqa: F821

        # so this is an error (just like in Racket):
        test_raises[AttributeError,
                    letrec[(x, y + 1),  # noqa: F821, `y` being undefined here is the point of this test.
                           (y, 2)][  # noqa: F821
                               print(x)],
                    "y should not be yet defined on the first line"]

        # This is ok, because the y on the RHS of the definition of f
        # is evaluated only when the function is called.
        #
        # This is the whole point of having a letrec construct,
        # instead of just let, letseq.
        test[letrec[(f, lambda t: t + y + 1),  # noqa: F821
                    (y, 2)][  # noqa: F821
                        f(3)] == 6]  # noqa: F821

        # bindings are evaluated only once
        a = letrec[(x, 1),
                   (y, x + 2)][[   # y computed now, using the current value of x  # noqa: F821
                       x << 1337,  # x updated now, no effect on y
                       (x, y)]]  # noqa: F821
        test[a == (1337, 3)]

        # lexical scoping: a comprehension or lambda in a let body
        # shadows names from the surrounding let, but only in that subexpr
        test[let[(x, 42)][[
                   [x for x in range(10)]]] == list(range(10))]
        test[let[(x, 42)][[
                   [x for x in range(10)],
                   x]] == 42]
        test[let[(x, 42)][
                   (lambda x: x**2)(10)] == 100]
        test[let[(x, 42)][[
                   (lambda x: x**2)(10),
                   x]] == 42]

    # let over lambda - in Python!
    with testset("let over lambda"):
        count = let[(x, 0)][
                      lambda: x << x + 1]
        test[count() == 1]
        test[count() == 2]

    # decorator version: let over def - a more pythonic approach?
    #   - sugar around unpythonic.lispylet.dlet et al.
    #   - env is passed implicitly, and named with a gensym (so lexical scoping works)
    with testset("let over def"):
        @dlet((x, 0))
        def count():
            x << x + 1  # assigment to let environment uses the "assignment expr" syntax
            return x
        test[count() == 1]
        test[count() == 2]

        # nested dlets respect lexical scoping
        @dlet((x, 22))
        def outer():
            x << x + 1
            @dlet((x, 41))
            def inner():
                return x << x + 1
            return (x, inner())
        test[outer() == (23, 42)]

        # letseq over def
        @dletseq((x, 1),
                 (x, x + 1),
                 (x, x + 2))
        def g(a):
            return a + x
        test[g(10) == 14]

        # letrec over def
        @dletrec((evenp, lambda x: (x == 0) or oddp(x - 1)),  # noqa: F821, `dletrec` defines `evenp` here.
                 (oddp, lambda x: (x != 0) and evenp(x - 1)))  # noqa: F821
        def f(x):
            return evenp(x)  # noqa: F821
        test[f(42) is True]
        test[f(23) is False]

    with testset("let block"):
        # block version
        #   - the def takes no args, runs immediately, replaced with return value
        @blet((x, 21))
        def result():
            return 2 * x
        test[result == 42]

        @bletseq((x, 1),
                 (x, x + 1),
                 (x, x + 2))  # noqa: F823, `bletseq` defines and assigns to `x`.
        def result():
            return x
        test[result == 4]

        @bletrec((evenp, lambda x: (x == 0) or oddp(x - 1)),  # noqa: F821, `bletrec` defines `evenp` here.
                 (oddp, lambda x: (x != 0) and evenp(x - 1)))  # noqa: F821
        def result():
            return evenp(42)  # noqa: F821
        test[result is True]

    # interaction of unpythonic's scoping system with Python's own lexical scoping
    with testset("integration of let scoping with Python's scoping"):
        x = "the nonlocal x"
        @dlet((x, "the env x"))
        def test1():
            return x
        test[test1() == "the env x"]

        @dlet((x, "the env x"))
        def test2():
            return x  # local var assignment not in effect yet  # noqa: F823, `dlet` defines `x` here.
            x = "the unused local x"  # noqa: F841, this `x` being unused is the point of this test.  # pragma: no cover
        test[test2() == "the env x"]

        @dlet((x, "the env x"))
        def test3():
            x = "the local x"
            return x
        test[test3() == "the local x"]

        @dlet((x, "the env x"))
        def test4():
            nonlocal x
            return x
        test[test4() == "the nonlocal x"]

        @dlet((x, "the env x"))
        def test5():
            global x
            return x
        test[test5() == "the global x"]

        @dlet((x, "the env x"))
        def test6():
            class Foo:
                x = "the classattr x"  # name in store context, not the env x
            return x
        test[test6() == "the env x"]

        @dlet((x, "the env x"))
        def test7():
            class Foo:
                x = "the classattr x"
                def doit(self):
                    return self.x
            return (Foo().doit(), x)
        test[test7() == ("the classattr x", "the env x")]

        @dlet((x, "the env x"))
        def test8():
            class Foo:
                x = "the classattr x"
                def doit(self):
                    return x  # no "self.", should grab the next lexically outer bare "x"
            return Foo().doit()
        test[test8() == "the env x"]

        # CAUTION: "del" is inherently a dynamic operation.
        #
        # Especially in "nonlocal x; del x" and "global x; del x", there is no
        # **lexical** section of code where the global/nonlocal x exists and
        # where it does not; the result depends on **when** those statements
        # are executed.
        #
        # For a local "del x", the situation is slightly simpler because inside one
        # scope, code runs top-down, statement by statement (or left-to-right,
        # expression by expression), but still there is the possibility of loops;
        # and in a "while", the loop condition is dynamic.
        #
        # For symmetry with how we treat assignments, we support "lexical deletion"
        # of local names: "del x" deletes x **for the lexically remaining part**
        # of the scope it appears in, and only if x has not been declared nonlocal
        # or global. "nonlocal x; del x" and "global x; del x" are ignored, by design.
        #
        # This is different from how Python itself behaves, but Python itself
        # doesn't have to resolve references statically at compile-time. ;)
        #
        # (What we do is actually pretty similar to what you get from symtable.symtable()
        # in the standard library, but we also perform some expression-by-expression
        # analysis to make it possible to refer to the old bindings on the RHS of
        # "name << value", as well as to support local deletion.)
        @dlet((x, "the env x"))
        def test9():
            x = x + " (copied to local)"  # the local x = the env x  # noqa: F823
            return x  # the local x
        test[test9() == "the env x (copied to local)"]

        @dlet((x, "the env x"))
        def test10():
            x = x + " (copied to local)"  # noqa: F823
            del x     # comes into effect for the next statement
            return x  # so this is env's original x
        test[test10() == "the env x"]

        @dlet((x, "the env x"))
        def test11():
            x = "the local x"
            return x  # not deleted yet
            del x  # this seems to be optimized out by Python.  # pragma: no cover
        test[test11() == "the local x"]

        @dlet((x, "the env x"))
        def test12():
            x = "the local x"
            del x
            x = "the other local x"
            return x
        test[test12() == "the other local x"]

        @dlet((x, "the env x"))
        def test13():
            x = "the local x"
            del x
            return x  # noqa: F823, this `x` refers to the `x` in the `dlet` env.
            x = "the unused local x"  # noqa: F841, this `x` being unused is the point of this test.  # pragma: no cover
        test[test13() == "the env x"]

        with test_raises(NameError, "should have tried to access the deleted nonlocal x"):
            x = "the nonlocal x"
            @dlet((x, "the env x"))
            def test14():
                nonlocal x
                del x       # ignored by unpythonic's scope analysis, too dynamic
                return x    # trying to refer to the nonlocal x, which was deleted
            test14()
        x = "the nonlocal x"  # restore the test environment

        # in do[] (also the implicit do), local[] takes effect from the next item
        test[let[(x, "the let x"),
                 (y, None)][  # noqa: F821
                     do[y << x,                  # still the "x" of the let  # noqa: F821
                        local[x << "the do x"],  # from here on, "x" refers to the "x" of the do
                        (x, y)]] == ("the do x", "the let x")]  # noqa: F821

        # don't code like this! ...but the scoping mechanism should understand it
        result = []
        let[(lst, [])][do[result.append(lst),       # the let "lst"  # noqa: F821
                          local[lst << lst + [1]],  # LHS: do "lst", RHS: let "lst"  # noqa: F821
                          result.append(lst)]]      # the do "lst"  # noqa: F821
        test[result == [[], [1]]]

        # same using implicit do
        result = []
        let[(lst, [])][[result.append(lst),  # noqa: F821
                        local[lst << lst + [1]],  # noqa: F821
                        result.append(lst)]]  # noqa: F821
        test[result == [[], [1]]]

    with testset("haskelly syntax"):
        result = let[((foo, 5),  # noqa: F821, `let` defines `foo` here.
                      (bar, 2))  # noqa: F821
                     in foo + bar]  # noqa: F821
        test[result == 7]

        result = letseq[((foo, 100),  # noqa: F821, `letseq` defines `foo` here.
                         (foo, 2 * foo),  # noqa: F821
                         (foo, 4 * foo))  # noqa: F821
                        in foo]  # noqa: F821
        test[result == 800]

        result = letrec[((evenp, lambda x: (x == 0) or oddp(x - 1)),  # noqa: F821, `letrec` defines `evenp` here.
                         (oddp, lambda x: (x != 0) and evenp(x - 1)))  # noqa: F821
                        in [print("hi from letrec-in"),
                            evenp(42)]]  # noqa: F821
        test[result is True]

        # inverted let, for situations where a body-first style improves readability:
        result = let[foo + bar,  # noqa: F821, the names in this expression are defined in the `where` clause of the `let`.
                     where((foo, 5),  # noqa: F821, this defines `foo`.
                           (bar, 2))]  # noqa: F821
        test[result == 7]

        result = letseq[foo,  # noqa: F821
                        where((foo, 100),  # noqa: F821
                              (foo, 2 * foo),  # noqa: F821
                              (foo, 4 * foo))]  # noqa: F821
        test[result == 800]

        # can also use the extra bracket syntax to get an implicit do
        # (note the [] should then enclose the body only).
        result = letrec[[print("hi from letrec-where"),
                         evenp(42)],  # noqa: F821
                        where((evenp, lambda x: (x == 0) or oddp(x - 1)),  # noqa: F821
                              (oddp, lambda x: (x != 0) and evenp(x - 1)))]  # noqa: F821
        test[result is True]

        # TODO: for now, with more than one binding the outer parentheses
        # are required, even in this format where they are somewhat redundant.
        result = let[((x, 1), (y, 2)) in x + y]  # noqa: F821
        test[result == 3]

    # single binding special syntax, no need for outer parentheses
    with testset("special syntax for single binding case"):
        result = let[x, 1][2 * x]
        test[result == 2]
        result = let[(x, 1) in 2 * x]
        test[result == 2]
        result = let[2 * x, where(x, 1)]
        test[result == 2]

        @dlet(x, 1)
        def qux():
            return x
        test[qux() == 1]

        @dletseq(x, 1)
        def qux():
            return x
        test[qux() == 1]

        @dletrec(x, 1)
        def qux():
            return x
        test[qux() == 1]

        @blet(x, 1)
        def quux():
            return x
        test[quux == 1]

        @bletseq(x, 1)
        def quux():
            return x
        test[quux == 1]

        @bletrec(x, 1)
        def quux():
            return x
        test[quux == 1]

    with testset("object instance bound to let variable"):
        # The point is to test whether `s.a` below transforms
        # correctly to `e.s.a`.
        class Silly:
            a = "Ariane 5"
        test[let[(s, Silly()) in s.a] == "Ariane 5"]  # noqa: F821

if __name__ == '__main__':  # pragma: no cover
    with session(__file__):
        runtests()
