# -*- coding: utf-8 -*-

from ..syntax import macros, test, test_raises, the  # noqa: F401
from ..test.fixtures import session, testset

from ..let import let, letrec, dlet, dletrec, blet, bletrec

from ..env import env as _envcls
from ..misc import call
from ..seq import begin

def runtests():
    with testset("order-preserving list uniqifier example"):
        def uniqify_test():
            def f(lst):  # classical solution
                seen = set()
                def see(x):
                    seen.add(x)
                    return x
                return [see(x) for x in lst if x not in seen]

            # one-liner
            f2 = lambda lst: (lambda seen: [seen.add(x) or x for x in lst if x not in seen])(seen=set())

            # context manager only
            def f3(lst):
                with _envcls(seen=set()) as myenv:
                    return [myenv.seen.add(x) or x for x in lst if x not in myenv.seen]
                # myenv itself still lives due to Python's scoping rules.
                # This is why we provide a separate let construct
                # and not just the env class.

            # solution using let
            f4 = lambda lst: let(seen=set(),
                                 body=lambda e: [e.seen.add(x) or x for x in lst if x not in e.seen])

            f5 = lambda lst: letrec(seen=set(),
                                    see=lambda e: lambda x: begin(e.seen.add(x), x),
                                    body=lambda e: [e.see(x) for x in lst if x not in e.seen])

            L = [1, 1, 3, 1, 3, 2, 3, 2, 2, 2, 4, 4, 1, 2, 3]

            # Call each implementation twice to make sure that a fresh `seen`
            # is indeed created at each call.
            test[the[f(L)] == the[f(L)]]
            test[the[f2(L)] == the[f2(L)]]
            test[the[f3(L)] == the[f3(L)]]
            test[the[f4(L)] == the[f4(L)]]
            test[the[f5(L)] == the[f5(L)]]

            test[the[f(L)] == the[f2(L)] == the[f3(L)] == the[f4(L)] == the[f5(L)] == [1, 3, 2, 4]]

        uniqify_test()

    with testset("let over lambda"):
        # Let over lambda. The inner lambda is the definition of the function f.
        counter = let(x=0,
                      body=lambda e: lambda: begin(e.set("x", e.x + 1),
                                                   e.x))
        counter()
        counter()
        test[counter() == 3]

    with testset("let over def"):
        @dlet(count=0)
        def counter2(*, env=None):  # env: named argument containing the let bindings
            env.count += 1
            return env.count
        counter2()
        counter2()
        test[counter2() == 3]

        @dlet(y=23)
        def foo(x, *, env):
            return x + env.y
        test[foo(17) == 40]

        @dlet(x=5)
        def bar(*, env):
            test[env.x == 5]

            @dlet(x=42)
            def baz(*, env):  # this env shadows the outer env
                test[env.x == 42]
            baz()

            test[env.x == 5]
        bar()

    with testset("let block"):
        @call
        @dlet(x=5)
        def _ignored1(*, env):  # this is now the let block, run immediately
            test[env.x == 5]

            @call
            @dlet(x=42)
            def _(*, env):
                test[env.x == 42]

            test[env.x == 5]

        # same effect
        @blet(x=5)
        def _ignored2(*, env):
            test[env.x == 5]

            @blet(x=42)
            def _ignored3(*, env):
                test[env.x == 42]

            test[env.x == 5]

    # example from https://docs.racket-lang.org/reference/let.html
    with testset("evenp-oddp example"):
        t = letrec(evenp=lambda e: lambda x: (x == 0) or e.oddp(x - 1),
                   oddp=lambda e: lambda x: (x != 0) and e.evenp(x - 1),
                   body=lambda e: e.evenp(42))
        test[t is True]

        # somewhat pythonic solution:
        @call
        def t():
            def evenp(x): return x == 0 or oddp(x - 1)
            def oddp(x): return x != 0 and evenp(x - 1)
            return evenp(42)
        test[t is True]

        # letrec over def
        @dletrec(evenp=lambda e: lambda x: (x == 0) or e.oddp(x - 1),
                 oddp=lambda e: lambda x: (x != 0) and e.evenp(x - 1))
        def is_even(x, *, env):
            return env.evenp(x)
        test[is_even(23) is False]

        # code block with letrec
        @bletrec(evenp=lambda e: lambda x: (x == 0) or e.oddp(x - 1),
                 oddp=lambda e: lambda x: (x != 0) and e.evenp(x - 1))
        def result(*, env):
            return env.evenp(23)
        test[result is False]

    with testset("error cases"):
        test_raises[AttributeError,
                    letrec(a=lambda e: e.b + 1,  # error, e.b does not exist yet (simple value refers to binding below it)
                           b=42,
                           body=lambda e: e.a)]

        test_raises[AttributeError,
                    let(x=0,
                        body=lambda e: e.set('y', 3)),
                    "e.y should not be defined"]

        with test_raises[AttributeError, "let environment should be final (should not be able to create new bindings in it inside the let body)"]:
            @blet(x=1)
            def error1(*, env):
                env.y = 2  # error, cannot introduce new bindings into a let environment

        test_raises[TypeError, let(body="not a callable")]
        test_raises[TypeError, let(body=lambda: None)]  # body callable must be able to take in environment
        # Reassigning the same name is blocked by Python itself (SyntaxError), so no test for that.
        test_raises[TypeError, letrec(x=lambda: 1,
                                      body=lambda e: e.x)]  # callable value must be able to take in environment

if __name__ == '__main__':  # pragma: no cover
    with session(__file__):
        runtests()
