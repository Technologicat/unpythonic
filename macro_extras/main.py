#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Macro extras. Main program for usage examples.

Uses MacroPy; must be run through the bootstrap script run.py,
since macro expansion occurs at import time.
"""

from macropy.tracing import macros, show_expanded

from unpythonic.syntax import macros, \
                              curry, \
                              simple_let, simple_letseq, \
                              let, letseq, letrec, \
                              do, do0, \
                              forall, insist, deny, forall_simple, \
                              aif, it, \
                              cond, \
                              fup, \
                              prefix, q, u, kw, \
                              multilambda, namedlambda, \
                              continuations, bind, \
                              tco, \
                              autoreturn

from itertools import repeat
from unpythonic import foldr, composerc as compose, cons, nil, ll, apply

def main():
    with curry:
        mymap = lambda f: foldr(compose(cons, f), nil)
        double = lambda x: 2 * x
        assert mymap(double, (1, 2, 3)) == ll(2, 4, 6)

        def add3(a, b, c):
            return a + b + c
        assert add3(1)(2)(3) == 6
        assert add3(1, 2)(3) == 6
        assert add3(1)(2, 3) == 6
        assert add3(1, 2, 3) == 6

#        # NOTE: because builtins cannot be inspected, curry just no-ops on them.
#        # So this won't work:
#        # v0.10.2: Workaround added for some builtins. Now this works.
#        from operator import add
#        try:
#            f = add(1)
#            assert f(2) == 3
#        except TypeError:
#            pass
#        else:
#            assert False, "update documentation"
#        # In cases like this, make a wrapper:
#        myadd = lambda a, b: add(a, b)
#        f = myadd(1)
#        assert f(2) == 3

    # Outside the with block, autocurry is not active, but the function was
    # defined inside the block, so it has implicit @curry.
    #
    # Note this works only if add3 contains no uninspectable functions,
    # because we are now outside the dynamic extent of the "with curry" block,
    # so the special mode of unpythonic.fun.curry is no longer active.
    assert add3(1)(2)(3) == 6

    # Anaphoric if: aif[test, then, otherwise]
    # Magic identifier "it" refers to the test result.
    assert aif[2*21,
               "it is {}".format(it),
               "it is False"] == "it is 42"

    # Lispy "cond" - a human-readable multi-branch conditional for lambdas.
    answer = lambda x: cond[x == 2, "two",
                            x == 3, "three",
                            "something else"]
    assert answer(42) == "something else"

    # Let macros. Lexical scoping supported.
    #
    assert let((x, 17),  # parallel binding, i.e. bindings don't see each other
               (y, 23))[
                 (x, y)] == (17, 23)

    assert letseq((x, 1),  # sequential binding, i.e. Scheme/Racket let*
                  (y, x+1))[
                    (x, y)] == (1, 2)

    try:
        let((X, 1),
            (y, X+1))[  # parallel binding, doesn't see the x in the same let
              print(X, y)]
    except NameError:
        pass  # no X in surrounding scope
    else:
        assert False, "should not see the X in the same let"

    try:
        letseq((X, y+1),
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

#    # this will SyntaxError (correctly)
#    simple_let((x, 1), (x, 2))[  # error, cannot rebind the same name
#          print(x)]

    assert letseq((x, 1),
                  (x, x+1))[  # but in a letseq it's ok
                    x] == 2

    # letrec sugars unpythonic.lispylet.letrec, removing the need for quotes
    # and "lambda e: ..." wrappers (these are inserted by the macro):
    assert letrec((evenp, lambda x: (x == 0) or oddp(x - 1)),
                  (oddp,  lambda x: (x != 0) and evenp(x - 1)))[
                    evenp(42)] is True

    # nested letrecs work, too - each environment is internally named by a gensym
    # so that outer ones "show through":
    assert letrec((z, 9000))[
             letrec((evenp, lambda x: (x == 0) or oddp(x - 1)),
                    (oddp,  lambda x: (x != 0) and evenp(x - 1)))[
                      (evenp(42), z)]] == (True, 9000)

    # also letrec supports lexical scoping, since in MacroPy 1.1.0 and later,
    # macros are expanded from inside out (the z in the inner scope expands to
    # the inner environment's z, which makes the outer expansion leave it alone):
    from unpythonic import begin
    out = []
    letrec((z, 1))[
      begin(out.append(z),
            letrec((z, 2))[
              out.append(z)])]  # (be careful with the parentheses!)
    assert out == [1, 2]

    # assignment updates the innermost value by that name:
    out = []
    letrec((z, 1))[
      begin(out.append(z), # outer z
            # assignment to env is an expression, returns the new value
            out.append(z << 5),
            letrec((z, 2))[
              begin(out.append(z), # inner z
                    out.append(z << 7))],
            out.append(z))]  # outer z
    assert out == [1, 5, 2, 7, 5]

    out = []
    letrec((x, 1))[
      begin(out.append(x),
            letrec((z, 2))[
              begin(out.append(z),
                    out.append(x << 7))],  # x only defined in outer letrec, updates that
            out.append(x))]
    assert out == [1, 2, 7, 7]

    # this works, too
    assert letrec((x, 1),
                  (y, x+2))[
                    (x, y)] == (1, 3)

    # but this is an error (just like in Racket):
    try:
        letrec((x, y+1),
               (y, 2))[
          print(x)]
    except AttributeError:  # y is not defined on the first line (lispylet and env together detect this)
        pass
    else:
        assert False, "y should not be yet defined on the first line"

    # this is ok, because the y on the RHS of the definition of f
    # is evaluated only when the function is called
    assert letrec((f, lambda t: t + y + 1),
                  (y, 2))[
                    f(3)] == 6

    a = letrec((x, 1),
               (y, x+2))[[   # y computed now
                 x << 1337,  # x updated now, no effect on y
                 (x, y)]]
    assert a == (1337, 3)

    a = let((x, 1),
            (y, 2))[[  # an extra set of brackets denotes a multi-expr body
              y << 1337,
              (x, y)]]
    assert a == (1, 1337)

    a = let((x, 1),
            (y, 2))[[
              [1, 2]]]
    assert a == [1, 2]  # only the outermost extra brackets denote a multi-expr body

    a = letseq((x, 1),
               (y, x+1))[[
                 x << 1337,
                 (x, y)]]
    assert a == (1337, 2)

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

    # let over lambda
    count = let((x, 0))[
              lambda: x << x + 1]
    assert count() == 1
    assert count() == 2

    # multilambda: multi-expression lambdas with implicit do
    with multilambda:
        # use brackets around the body of a lambda to denote a multi-expr body
        echo = lambda x: [print(x), x]
        assert echo("hi there") == "hi there"

        count = let((x, 0))[
                  lambda: [x << x + 1,
                           x]]  # redundant, but demonstrating multi-expr body.
        assert count() == 1
        assert count() == 2

        test = let((x, 0))[
                 lambda: [x << x + 1,         # x belongs to the surrounding let
                          localdef(y << 42),  # y is local to the implicit do
                          (x, y)]]
        assert test() == (1, 42)
        assert test() == (2, 42)

        myadd = lambda x, y: [print("myadding", x, y),
                              localdef(tmp << x + y),
                              print("result is", tmp),
                              tmp]
        assert myadd(2, 3) == 5

        # only the outermost set of brackets denote a multi-expr body:
        t = lambda: [[1, 2]]
        assert t() == [1, 2]

    # named lambdas!
    with namedlambda:
        f = lambda x: x**3                       # lexical rule: name as "f"
        assert f.__name__ == "f (lambda)"
        gn, hn = let((x, 42), (g, None), (h, None))[[
                       g << (lambda x: x**2),    # dynamic rule: name as "g"
                       h << f,                   # no-rename rule: still "f"
                       (g.__name__, h.__name__)]]
        assert gn == "g (lambda)"
        assert hn == "f (lambda)"

    # macro wrapper for unpythonic.seq.do (stuff imperative code into a lambda)
    #  - Declare and initialize a local variable with ``localdef(var << value)``.
    #  - Assignment is ``var << value``.
    #    Transforms to ``begin(setattr(e, var, value), value)``,
    #    so is valid from any level inside the ``do`` (including nested
    #    ``let`` constructs and similar).
    #  - Note that if a nested binding macro such as a ``let`` also binds an
    #    ``x``, the inner macro will bind first, so the ``do`` environment
    #    will then **not** bind ``x``, as it already belongs to the ``let``.
    #  - No need for ``lambda e: ...`` wrappers. Inserted automatically,
    #    so the lines are only evaluated as the underlying seq.do() runs.
    y = do[localdef(x << 17),
           print(x),
           x << 23,
           x]
    assert y == 23

    y2 = do0[localdef(y << 5),
             print("hi there, y =", y),
             42]  # evaluated but not used, do0 returns the first value
    assert y2 == 5

    # macro wrapper for amb.forall
    #   - assignment (with List-monadic magic) is ``var << iterable``
    #   - no need for ``lambda e: ...`` wrappers.
    out = forall[y << range(3),  # y << ... --> choice(y=lambda e: ...)
                 x << range(3),
                 insist(x % 2 == 0),
                 (x, y)]
    assert out == ((0, 0), (2, 0), (0, 1), (2, 1), (0, 2), (2, 2))

    # pythagorean triples
    pt = forall[z << range(1, 21),   # hypotenuse
                x << range(1, z+1),  # shorter leg
                y << range(x, z+1),  # longer leg
                insist(x*x + y*y == z*z),
                (x, y, z)]
    assert tuple(sorted(pt)) == ((3, 4, 5), (5, 12, 13), (6, 8, 10),
                                 (8, 15, 17), (9, 12, 15), (12, 16, 20))

    # forall_simple: pure AST transformation, with real lexical variables
    pt = forall_simple[z << range(1, 21),   # hypotenuse
                       x << range(1, z+1),  # shorter leg
                       y << range(x, z+1),  # longer leg
                       insist(x*x + y*y == z*z),
                       (x, y, z)]
    assert tuple(sorted(pt)) == ((3, 4, 5), (5, 12, 13), (6, 8, 10),
                                 (8, 15, 17), (9, 12, 15), (12, 16, 20))

    # functional update for sequences
    lst = (1, 2, 3, 4, 5)
    assert fup[lst[3] << 42] == (1, 2, 3, 42, 5)
    assert fup[lst[0::2] << tuple(repeat(10, 3))] == (10, 2, 10, 4, 10)
    assert fup[lst[1::2] << tuple(repeat(10, 3))] == (1, 10, 3, 10, 5)
    assert fup[lst[::2] << tuple(repeat(10, 3))] == (10, 2, 10, 4, 10)
    assert fup[lst[::-1] << tuple(range(5))] == (4, 3, 2, 1, 0)
    assert lst == (1, 2, 3, 4, 5)

    # TCO as a macro
    with tco:
        # works with lambdas
        evenp = lambda x: (x == 0) or oddp(x - 1)
        oddp  = lambda x: (x != 0) and evenp(x - 1)
        assert evenp(10000) is True

        # works with defs
        def evenp(x):
            if x == 0:
                return True
            return oddp(x - 1)
        def oddp(x):
            if x != 0:
                return evenp(x - 1)
            return False
        assert evenp(10000) is True

        # integration with let[] constructs
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

    # call_ec combo
    from unpythonic import call_ec
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

    # allow omitting "return" in tail position
    with autoreturn:
        def f():
            "I'll just return this"
        assert f() == "I'll just return this"

        def g(x):
            if x == 1:
                "one"
            elif x == 2:
                "two"
            else:
                "something else"
        assert g(1) == "one"
        assert g(2) == "two"
        assert g(42) == "something else"

    with autoreturn, tco:  # combo
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

    # continuations!
    # basic testing
    with continuations:
        def add1(x, *, cc):
            return 1 + x
        assert add1(2) == 3

        def message(*, cc):
            return ("hello", "there")
        def baz(*, cc):
            with bind[message()] as (m, n):
                return [m, n]
        assert baz() == ["hello", "there"]

        def f(a, b, *, cc):
            return 2*a, 3*b
        assert f(3, 4) == (6, 12)
        x, y = f(3, 4)
        assert x == 6 and y == 12

        def g(a, b, *, cc):
            with bind[f(a, b)] as (x, y):
                return x, y
            print("never reached")
        assert g(3, 4) == (6, 12)

    # an "and" or "or" return value may have a tail-call in the last item
    with continuations:
        # "or"
        def h1(a, b, *, cc):
            with bind[f(a, b)] as (x, y):
                return None or f(3, 4)
        assert h1(3, 4) == (6, 12)

        def h2(a, b, *, cc):
            with bind[f(a, b)] as (x, y):
                return True or f(3, 4)
        assert h2(3, 4) is True

        # "or" with 3 or more items (testing; handled differently internally)
        def h3(a, b, *, cc):
            with bind[f(a, b)] as (x, y):
                return None or False or f(3, 4)
        assert h3(3, 4) == (6, 12)

        def h4(a, b, *, cc):
            with bind[f(a, b)] as (x, y):
                return None or True or f(3, 4)
        assert h4(3, 4) is True

        def h5(a, b, *, cc):
            with bind[f(a, b)] as (x, y):
                return 42 or None or f(3, 4)
        assert h5(3, 4) == 42

        # "and"
        def i1(a, b, *, cc):
            with bind[f(a, b)] as (x, y):
                return True and f(3, 4)
        assert i1(3, 4) == (6, 12)

        def i2(a, b, *, cc):
            with bind[f(a, b)] as (x, y):
                return False and f(3, 4)
        assert i2(3, 4) is False

        # "and" with 3 or more items
        def i3(a, b, *, cc):
            with bind[f(a, b)] as (x, y):
                return True and 42 and f(3, 4)
        assert i3(3, 4) == (6, 12)

        def i4(a, b, *, cc):
            with bind[f(a, b)] as (x, y):
                return True and False and f(3, 4)
        assert i4(3, 4) is False

        def i5(a, b, *, cc):
            with bind[f(a, b)] as (x, y):
                return None and False and f(3, 4)
        assert i5(3, 4) is False

        # combination of "and" and "or"
        def j1(a, b, *, cc):
            with bind[f(a, b)] as (x, y):
                return None or True and f(3, 4)
        assert j1(3, 4) == (6, 12)

    # call_ec combo
    with continuations:
        def g(x, *, cc):
            return 2*x

        @call_ec
        def result(ec, *, cc):
            ec(g(21))
        assert result == 42

#        # ec doesn't work from inside a "with bind", because the function
#        # containing the "with bind" actually tail-calls the bind and exits.
#        @call_ec
#        def doit(ec, *, cc):
#            with bind[g(21)] as x:
#                ec(x)  # we're actually outside doit(); ec no longer valid

#        # Even this only works the first time; if you stash the cc and
#        # call it later (to re-run the body of the "with bind", at that time
#        # result() will already have exited so the ec no longer works.
#        # (That's just the nature of exceptions.)
#        @call_ec
#        def result(ec, *, cc):
#            def doit(*, cc):
#                with bind[g(21)] as x:
#                    ec(x)
#            r = doit()  # don't tail-call it; result() must be still running when the ec is invoked
#            return r
#        assert result == 42

    # test that ecs expand correctly
    with continuations:
        @call_ec
        def result(ec, *, cc):
            return ec(42)  # doesn't need the "return"; the macro eliminates it
        assert result == 42

        assert call_ec(lambda ec, *, cc: ec(42)) == 42

#    with show_expanded:
    from unpythonic.fun import curry
    with continuations:
        # Currying here makes no sense, but test that it expands correctly.
        # We should get trampolined(call_ec(curry(...))), which produces the desired result.
        assert call_ec(curry(lambda ec, *, cc: ec(42))) == 42
    with tco:  # Same thing in the tco macro.
        assert call_ec(curry(lambda ec: ec(42))) == 42
    # This version auto-inserts curry after the inner macros have expanded.
    # This should work, too.
    with curry:
        with continuations:
            assert call_ec(lambda ec, *, cc: ec(42)) == 42
        with tco:
            assert call_ec(lambda ec: ec(42)) == 42

    # fploop combo (test; requires special handling)
    from unpythonic.fploop import looped_over
    with show_expanded:
      with tco:
        @looped_over(range(10), acc=0)
        def result(loop, x, acc):
            return loop(acc + x)
        assert result == 45
        assert looped_over(range(10), acc=0)(lambda loop, x, acc: loop(acc + x)) == 45

    # silly call/cc example (Paul Graham: On Lisp, p. 261), pythonified
    with continuations:
        k = None  # kontinuation
        def setk(*args, cc):
            nonlocal k
            k = cc  # current continuation, i.e. where to go after setk() finishes
            xs = list(args)
            # - not "return list(args)" because that would be a tail call,
            #   and list() is a regular function, not a continuation-enabled one
            #   (so it would immediately terminate the TCO chain; besides,
            #   it takes only 1 argument and doesn't know what to do with "cc".)
            # - list instead of tuple to return it as one value
            #   (a tuple return value is interpreted as multiple-return-values)
            return xs
        def doit(*, cc):
            lst = ['the call returned']
            with bind[setk('A')] as more:  # call/cc, sort of...
                return lst + more          # ...where the body is the continuation
        print(doit())
        # We can now send stuff into k, as long as it conforms to the
        # signature of the as-part of the "with bind".
        print(k(['again']))
        print(k(['thrice', '!']))

    with continuations:
        # A top-level "with bind" is also allowed, but in that case there is
        # no way to get the return value of the continuation the first time it runs,
        # because "with" is a statement.
        #
        # On further runs, it is of course possible to get the return value as usual.
        k = None
        def setk(*args, cc):
            nonlocal k
            k = cc
            return args  # tuple return value (if not literal, tested at run-time) --> multiple-values
        with bind[setk(1, 2)] as (x, y):
            print(x, y)
            return x, y
        assert k(3, 4) == (3, 4)
        assert k(5, 6) == (5, 6)

    # to combo with multilambda, use this ordering:
    with multilambda, continuations:
        f = lambda x, *, cc: [print(x), x**2]
        assert f(42) == 1764

    # depth-first tree traversal (Paul Graham: On Lisp, p. 271)
    def atom(x):
        return not isinstance(x, (list, tuple))
    t1 = ["a", ["b", ["d", "h"]], ["c", "e", ["f", "i"], "g"]]
    t2 = [1, [2, [3, 6, 7], 4, 5]]

    def dft(tree):  # classical, no continuations
        if not tree:
            return
        if atom(tree):
            print(tree, end='')
            return
        first, *rest = tree
        dft(first)
        dft(rest)
    print("dft")
    dft(t1)  # abdhcefig
    print()

    with continuations:
        saved = []
        def dft_node(tree, *, cc):
            if not tree:
                return restart()
            if atom(tree):
                return tree
            first, *rest = tree
            ourcc = cc  # capture our current continuation
            # override default continuation in the tail-call in the lambda
            saved.append(lambda *, cc: dft_node(rest, cc=ourcc))
            return dft_node(first)
        def restart(*, cc):
            if saved:
                f = saved.pop()
                return f()
            else:
                return "done"
        def dft2(tree, *, cc):
            nonlocal saved
            saved = []
            with bind[dft_node(tree)] as node:
                if node == "done":
                    return "done"
                print(node, end='')
                return restart()
        print("dft2")
        dft2(t1)
        print()

        # The continuation version allows to easily walk two trees simultaneously,
        # generating their cartesian product (example from On Lisp, p. 272):
        def treeprod(ta, tb, *, cc):
            with bind[dft_node(ta)] as node1:
                if node1 == "done":
                    return "done"
                with bind[dft_node(tb)] as node2:
                    return [node1, node2]
        out = []
        x = treeprod(t1, t2)
        while x != "done":
            out.append(x)
            x = restart()
        print(out)

    # maybe more pythonic to make it a generator?
    #
    # We can define and use this outside the block, since at this level
    # we don't need to manipulate cc.
    #
    # (We could as well define and use it inside the block, by adding "*, cc"
    # to the args of the def.)
    def treeprod_gen(ta, tb):
        x = treeprod(t1, t2)
        while x != "done":
            yield x
            x = restart()
    out2 = tuple(treeprod_gen(t1, t2))
    print(out2)

    # The most pythonic way, of course, is to define dft as a generator,
    # since that already provides suspend-and-resume...
    def dft3(tree):
        if not tree:
            return
        if atom(tree):
            yield tree
            return
        first, *rest = tree
        yield from dft3(first)
        yield from dft3(rest)
    print("dft3")
    print("".join(dft3(t1)))  # abdhcefig

    # McCarthy's amb operator is very similar to dft, if a bit shorter:
    with continuations:
        stack = []
        def amb(lst, *, cc):
            if not lst:
                return fail()
            first, *rest = lst
            if rest:
                ourcc = cc
                stack.append(lambda *, cc: amb(rest, cc=ourcc))
            return first
        def fail(*, cc):
            if stack:
                f = stack.pop()
                return f()

        # testing
        def doit1(*, cc):
            with bind[amb((1, 2, 3))] as c1:
                with bind[amb((10, 20))] as c2:
                    if c1 and c2:
                        return c1 + c2
        print(doit1())
        # How this differs from a comprehension is that we can fail()
        # **outside** the dynamic extent of doit1. Doing that rewinds,
        # and returns the next value. The control flow state is kept
        # on the continuation stack just like in Scheme/Racket.
        print(fail())
        print(fail())
        print(fail())
        print(fail())
        print(fail())
        print(fail())

        def doit2(*, cc):
            with bind[amb((1, 2, 3))] as c1:
                with bind[amb((10, 20))] as c2:
                    if c1 + c2 != 22:  # we can require conditions like this
                        return fail()
                    return c1, c2
        print(doit2())
        print(fail())

        # Pythagorean triples.
        count = 0
        def pt(*, cc):
            # This generates 1540 combinations, with several nested tail-calls each,
            # so we really need TCO here. (Without TCO, nothing would return until
            # the whole computation is done; it would blow the call stack very quickly.)
            with bind[amb(tuple(range(1, 21)))] as z:
                with bind[amb(tuple(range(1, z+1)))] as y:
                    with bind[amb(tuple(range(1, y+1)))] as x:
                        nonlocal count
                        count += 1
                        if x*x + y*y != z*z:
                            return fail()
                        return x, y, z
        print(pt())
        print(fail())
        print(fail())
        print(fail())
        print(fail())
        print(fail())
        print(fail())
        print("combinations tested: {:d}".format(count))

    # Pythagorean triples, pythonic way
    def pt_gen():
        for z in range(1, 21):
            for y in range(1, z+1):
                for x in range(1, y+1):
                    if x*x + y*y != z*z:
                        continue
                    yield x, y, z
    print(tuple(pt_gen()))

    # combo
#    with show_expanded:
#     with curry:  # major slowdown, but works; must be in a separate "with"  # TODO: why separate?
    with autoreturn, continuations:
        stack = []
        def amb(lst, *, cc):
            if lst:
                first, *rest = lst
                if rest:
                    ourcc = cc
                    stack.append(lambda *, cc: amb(rest, cc=ourcc))
                first
            else:
                fail()
        def fail(*, cc):
            if stack:
                f = stack.pop()
                f()

        def pyth(*, cc):
            with bind[amb(tuple(range(1, 21)))] as z:
                with bind[amb(tuple(range(1, z+1)))] as y:
                    with bind[amb(tuple(range(1, y+1)))] as x:  # <-- the call/cc
                        if x*x + y*y == z*z:                    # body is the cont
                            x, y, z
                        else:
                            fail()
        x = pyth()
        while x:
            print(x)
            x = fail()

    # Write Python almost like Lisp!
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
        assert (apply, g, "hi", "ho", lst) == (q, "hi" ,"ho", 1, 2, 3)
        # named args in apply are also fine
        assert (apply, g, "hi", "ho", lst, kw(myarg=4)) == (q, "hi" ,"ho", 1, 2, 3, ('myarg', 4))

        # Function call transformation only applies to tuples in load context
        # (i.e. NOT on the LHS of an assignment)
        a, b = (q, 100, 200)
        assert a == 100 and b == 200
        a, b = (q, b, a)  # pythonic swap in prefix syntax; must quote RHS
        assert a == 200 and b == 100

    # Introducing LisThEll:
    with prefix, curry:  # important: apply prefix first, then curry
        mymap = lambda f: (foldr, (compose, cons, f), nil)
        double = lambda x: 2 * x
        (print, (mymap, double, (q, 1, 2, 3)))
        assert (mymap, double, (q, 1, 2, 3)) == ll(2, 4, 6)

if __name__ == '__main__':
    main()
