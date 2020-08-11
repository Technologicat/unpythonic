# -*- coding: utf-8 -*-
"""Let constructs; do (imperative code in expression position)."""

# IDE doesn't understand "let" as a binding form, so this generates lots of
# spurious "undefined name" warnings, but there's not much we can do about that
# (aside from patching pyflakes and pylint to handle the binding forms that are
# added by unpythonic).

from ...syntax import (macros, let, letseq, letrec, where,  # noqa: F401
                       dlet, dletseq, dletrec,
                       blet, bletseq, bletrec,
                       do, do0, local, delete)

from ...seq import begin

x = "the global x"  # for lexical scoping tests

def runtests():
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
    assert d1 == 23

    # v0.14.0: do[] now supports deleting previously defined local names with delete[]
    def assertf(v):
        assert v
    a = 5
    d = do[local[a << 17],
           assertf(a == 17),
           delete[a],
           assertf(a == 5),  # lexical scoping
           True]

    try:
        d = do[delete[a], ]  # noqa: F841, `d` is unused, this is a silly test.
    except KeyError:
        pass
    else:
        assert False, "should have complained about deleting nonexistent local 'a'"

    # do0[]: like do[], but return the value of the **first** expression
    d2 = do0[local[y << 5],  # noqa: F821, `local` defines the name on the LHS of the `<<`.
             print("hi there, y =", y),  # noqa: F821
             42]  # evaluated but not used
    assert d2 == 5

    # Let macros. Lexical scoping supported.
    #
    assert let((x, 17),  # parallel binding, i.e. bindings don't see each other
               (y, 23))[  # noqa: F821, `let` defines `y` here.
                 (x, y)] == (17, 23)  # noqa: F821

    assert letseq((x, 1),  # sequential binding, i.e. Scheme/Racket let*
                  (y, x + 1))[  # noqa: F821
                    (x, y)] == (1, 2)  # noqa: F821

    try:
        let((X, 1),
            (y, X + 1))[  # parallel binding, doesn't see the X in the same let
              print(X, y)]
    except NameError:
        pass  # no X in surrounding scope
    else:
        assert False, "should not see the X in the same let"

    try:
        letseq((X, y + 1),
               (y, 2))[
                 (X, y)]
    except NameError:  # y is not yet defined on the first line
        pass
    else:
        assert False, "y should not yet be defined on the first line"

    try:
        let((x, 1),
            (x, 2))[  # error, cannot rebind the same name
              print(x)]
    except AttributeError:
        pass
    else:
        assert False, "should not be able to rebind the same name x in the same let"

#    # using "from unpythonic.syntax.simplelet import macros, let, letseq",
#    # this will SyntaxError (correctly)
#    let((x, 1), (x, 2))[  # error, cannot rebind the same name
#          print(x)]

    assert letseq((x, 1),
                  (x, x + 1))[  # but in a letseq it's ok
                    x] == 2

    # letrec sugars unpythonic.lispylet.letrec, removing the need for quotes
    # and "lambda e: ..." wrappers (these are inserted by the macro):
    assert letrec((evenp, lambda x: (x == 0) or oddp(x - 1)),  # noqa: F821, `letrec` defines `evenp` here.
                  (oddp, lambda x: (x != 0) and evenp(x - 1)))[  # noqa: F821
                    evenp(42)] is True  # noqa: F821

    # nested letrecs work, too - each environment is internally named by a gensym
    # so that outer ones "show through":
    assert letrec((z, 9000))[  # noqa: F821
             letrec((evenp, lambda x: (x == 0) or oddp(x - 1)),  # noqa: F821
                    (oddp, lambda x: (x != 0) and evenp(x - 1)))[  # noqa: F821
                      (evenp(42), z)]] == (True, 9000)  # noqa: F821

    # implicit do: an extra set of brackets denotes a multi-expr body
    a = let((x, 1),
            (y, 2))[[  # noqa: F821
                y << 1337,  # noqa: F821
                (x, y)]]  # noqa: F821
    assert a == (1, 1337)

    a = let((x, 1),
            (y, 2))[[  # noqa: F821
              [1, 2]]]
    assert a == [1, 2]  # only the outermost extra brackets denote a multi-expr body

    # implicit do works also in letseq, letrec
    a = letseq((x, 1),
               (y, x + 1))[[  # noqa: F821
                 x << 1337,
                 (x, y)]]  # noqa: F821
    assert a == (1337, 2)
    a = letrec((x, 1),
               (y, x + 1))[[  # noqa: F821
                 x << 1337,
                 (x, y)]]  # noqa: F821
    assert a == (1337, 2)

    # also letrec supports lexical scoping, since in MacroPy 1.1.0 and later,
    # macros are expanded from inside out (the z in the inner scope expands to
    # the inner environment's z, which makes the outer expansion leave it alone):
    out = []
    letrec((z, 1))[  # noqa: F821
      begin(out.append(z),  # noqa: F821
            letrec((z, 2))[  # noqa: F821
              out.append(z)])]  # (be careful with the parentheses!)  # noqa: F821
    assert out == [1, 2]

    # same using implicit do (extra brackets)
    out = []
    letrec((z, 1))[[  # noqa: F821
             out.append(z),  # noqa: F821
             letrec((z, 2))[  # noqa: F821
                      out.append(z)]]]  # noqa: F821
    assert out == [1, 2]

    # lexical scoping: assignment updates the innermost value by that name:
    out = []
    letrec((z, 1))[  # noqa: F821
        begin(out.append(z),  # outer z  # noqa: F821
              # assignment to env is an expression, returns the new value
              out.append(z << 5),  # noqa: F821
              letrec((z, 2))[  # noqa: F821
              begin(out.append(z),         # inner z  # noqa: F821
                    out.append(z << 7))],  # update inner z  # noqa: F821
              out.append(z))]  # outer z  # noqa: F821
    assert out == [1, 5, 2, 7, 5]

    out = []
    letrec((x, 1))[
        begin(out.append(x),
              letrec((z, 2))[  # noqa: F821
                  begin(out.append(z),  # noqa: F821
                        out.append(x << 7))],  # x only defined in outer letrec, updates that
              out.append(x))]
    assert out == [1, 2, 7, 7]

    # same using implicit do
    out = []
    letrec((x, 1))[[
             out.append(x),
             letrec((z, 2))[[  # noqa: F821
                      out.append(z),  # noqa: F821
                      out.append(x << 7)]],
             out.append(x)]]
    assert out == [1, 2, 7, 7]

    # letrec bindings are evaluated sequentially
    assert letrec((x, 1),
                  (y, x + 2))[  # noqa: F821
                    (x, y)] == (1, 3)  # noqa: F821

    # so this is an error (just like in Racket):
    try:
        letrec((x, y + 1),  # noqa: F821, `y` being undefined here is the point of this test.
               (y, 2))[  # noqa: F821
          print(x)]
    except AttributeError:  # y is not defined on the first line (lispylet and env together detect this)
        pass
    else:
        assert False, "y should not be yet defined on the first line"

    # this is ok, because the y on the RHS of the definition of f
    # is evaluated only when the function is called
    #
    # (this is the whole point of having a letrec construct instead of just let, letseq)
    assert letrec((f, lambda t: t + y + 1),  # noqa: F821
                  (y, 2))[  # noqa: F821
                    f(3)] == 6  # noqa: F821

    # bindings are evaluated only once
    a = letrec((x, 1),
               (y, x + 2))[[   # y computed now, using the current value of x  # noqa: F821
                   x << 1337,  # x updated now, no effect on y
                   (x, y)]]  # noqa: F821
    assert a == (1337, 3)

    # lexical scoping: a comprehension or lambda in a let body
    # shadows names from the surrounding let, but only in that subexpr
    assert let((x, 42))[[
                 [x for x in range(10)]]] == list(range(10))
    assert let((x, 42))[[
                 [x for x in range(10)],
                 x]] == 42
    assert let((x, 42))[
                 (lambda x: x**2)(10)] == 100
    assert let((x, 42))[[
                 (lambda x: x**2)(10),
                 x]] == 42

    # let over lambda - in Python!
    count = let((x, 0))[
              lambda: x << x + 1]
    assert count() == 1
    assert count() == 2

    # decorator version: let over def - a more pythonic approach?
    #   - sugar around unpythonic.lispylet.dlet et al.
    #   - env is passed implicitly, and named with a gensym (so lexical scoping works)
    @dlet((x, 0))
    def count():
        x << x + 1  # assigment to let environment uses the "assignment expr" syntax
        return x
    assert count() == 1
    assert count() == 2

    # nested dlets respect lexical scoping
    @dlet((x, 22))
    def outer():
        x << x + 1
        @dlet((x, 41))
        def inner():
            return x << x + 1
        return (x, inner())
    assert outer() == (23, 42)

    # letrec over def
    @dletrec((evenp, lambda x: (x == 0) or oddp(x - 1)),  # noqa: F821, `dletrec` defines `evenp` here.
             (oddp, lambda x: (x != 0) and evenp(x - 1)))  # noqa: F821
    def f(x):
        return evenp(x)  # noqa: F821
    assert f(42) is True
    assert f(23) is False

    # letseq over def
    @dletseq((x, 1),
             (x, x + 1),
             (x, x + 2))
    def g(a):
        return a + x
    assert g(10) == 14

    # block version
    #   - the def takes no args, runs immediately, replaced with return value
    @blet((x, 21))
    def result():
        return 2 * x
    assert result == 42

    @bletseq((x, 1),
             (x, x + 1),
             (x, x + 2))  # noqa: F823, `bletseq` defines and assigns to `x`.
    def result():
        return x
    assert result == 4

    @bletrec((evenp, lambda x: (x == 0) or oddp(x - 1)),  # noqa: F821, `bletrec` defines `evenp` here.
             (oddp, lambda x: (x != 0) and evenp(x - 1)))  # noqa: F821
    def result():
        return evenp(42)  # noqa: F821
    assert result is True

    # interaction of unpythonic's scoping system with Python's own lexical scoping
    x = "the nonlocal x"
    @dlet((x, "the env x"))
    def test1():
        return x
    assert test1() == "the env x"

    @dlet((x, "the env x"))
    def test2():
        return x  # local var assignment not in effect yet  # noqa: F823, `dlet` defines `x` here.
        x = "the unused local x"  # noqa: F841, this `x` being unused is the point of this test.
    assert test2() == "the env x"

    @dlet((x, "the env x"))
    def test3():
        x = "the local x"
        return x
    assert test3() == "the local x"

    @dlet((x, "the env x"))
    def test4():
        nonlocal x
        return x
    assert test4() == "the nonlocal x"

    @dlet((x, "the env x"))
    def test5():
        global x
        return x
    assert test5() == "the global x"

    @dlet((x, "the env x"))
    def test6():
        class Foo:
            x = "the classattr x"  # name in store context, not the env x
        return x
    assert test6() == "the env x"

    @dlet((x, "the env x"))
    def test7():
        class Foo:
            x = "the classattr x"
            def doit(self):
                return self.x
        return (Foo().doit(), x)
    assert test7() == ("the classattr x", "the env x")

    @dlet((x, "the env x"))
    def test8():
        class Foo:
            x = "the classattr x"
            def doit(self):
                return x  # no "self.", should grab the next lexically outer bare "x"
        return Foo().doit()
    assert test8() == "the env x"

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
    assert test9() == "the env x (copied to local)"

    @dlet((x, "the env x"))
    def test10():
        x = x + " (copied to local)"  # noqa: F823
        del x     # comes into effect for the next statement
        return x  # so this is env's original x
    assert test10() == "the env x"

    @dlet((x, "the env x"))
    def test11():
        x = "the local x"
        return x  # not deleted yet
        del x
    assert test11() == "the local x"

    @dlet((x, "the env x"))
    def test12():
        x = "the local x"
        del x
        x = "the other local x"
        return x
    assert test12() == "the other local x"

    @dlet((x, "the env x"))
    def test13():
        x = "the local x"
        del x
        return x  # noqa: F823, this `x` refers to the `x` in the `dlet` env.
        x = "the unused local x"  # noqa: F841, this `x` being unused is the point of this test.
    assert test13() == "the env x"

    try:
        x = "the nonlocal x"
        @dlet((x, "the env x"))
        def test14():
            nonlocal x
            del x       # ignored by unpythonic's scope analysis, too dynamic
            return x    # trying to refer to the nonlocal x, which was deleted
        test14()
    except NameError:
        pass
    else:
        assert False, "should have tried to access the deleted nonlocal x"
    finally:  # restore the test environment
        x = "the nonlocal x"

    # in do[] (also the implicit do), local[] takes effect from the next item
    assert let((x, "the let x"),
               (y, None))[  # noqa: F821
                 do[y << x,                  # still the "x" of the let  # noqa: F821
                    local[x << "the do x"],  # from here on, "x" refers to the "x" of the do
                    (x, y)]] == ("the do x", "the let x")  # noqa: F821

    # don't code like this! ...but the scoping mechanism should understand it
    result = []
    let((lst, []))[do[result.append(lst),       # the let "lst"  # noqa: F821
                      local[lst << lst + [1]],  # LHS: do "lst", RHS: let "lst"  # noqa: F821
                      result.append(lst)]]      # the do "lst"  # noqa: F821
    assert result == [[], [1]]

    # same using implicit do
    result = []
    let((lst, []))[[result.append(lst),  # noqa: F821
                    local[lst << lst + [1]],  # noqa: F821
                    result.append(lst)]]  # noqa: F821
    assert result == [[], [1]]

    # haskelly syntax
    result = let[((foo, 5),  # noqa: F821, `let` defines `foo` here.
                  (bar, 2))  # noqa: F821
                 in foo + bar]  # noqa: F821
    assert result == 7

    result = letseq[((foo, 100),  # noqa: F821, `letseq` defines `foo` here.
                     (foo, 2 * foo),  # noqa: F821
                     (foo, 4 * foo))  # noqa: F821
                    in foo]  # noqa: F821
    assert result == 800

    result = letrec[((evenp, lambda x: (x == 0) or oddp(x - 1)),  # noqa: F821, `letrec` defines `evenp` here.
                     (oddp, lambda x: (x != 0) and evenp(x - 1)))  # noqa: F821
                    in [print("hi from letrec-in"),
                        evenp(42)]]  # noqa: F821

    # inverted let, for situations where a body-first style improves readability:
    result = let[foo + bar,  # noqa: F821, the names in this expression are defined in the `where` clause of the `let`.
                 where((foo, 5),  # noqa: F821, this defines `foo`.
                       (bar, 2))]  # noqa: F821
    assert result == 7

    result = letseq[foo,  # noqa: F821
                    where((foo, 100),  # noqa: F821
                          (foo, 2 * foo),  # noqa: F821
                          (foo, 4 * foo))]  # noqa: F821
    assert result == 800

    # can also use the extra bracket syntax to get an implicit do
    # (note the [] should then enclose the body only).
    result = letrec[[print("hi from letrec-where"),
                     evenp(42)],  # noqa: F821
                    where((evenp, lambda x: (x == 0) or oddp(x - 1)),  # noqa: F821
                          (oddp, lambda x: (x != 0) and evenp(x - 1)))]  # noqa: F821
    assert result is True

    # single binding special syntax, no need for outer parentheses
    result = let(x, 1)[2 * x]
    assert result == 2
    result = let[(x, 1) in 2 * x]
    assert result == 2
    result = let[2 * x, where(x, 1)]
    assert result == 2

    @dlet(x, 1)
    def qux():
        return x
    assert qux() == 1

    @dletseq(x, 1)
    def qux():
        return x
    assert qux() == 1

    @dletrec(x, 1)
    def qux():
        return x
    assert qux() == 1

    @blet(x, 1)
    def quux():
        return x
    assert quux == 1

    @bletseq(x, 1)
    def quux():
        return x
    assert quux == 1

    @bletrec(x, 1)
    def quux():
        return x
    assert quux == 1

    # TODO: for now, with more than one binding the outer parentheses
    # are required, even in this format where they are somewhat redundant.
    result = let[((x, 1), (y, 2)) in x + y]  # noqa: F821
    assert result == 3

    print("All tests PASSED")

if __name__ == '__main__':
    runtests()
