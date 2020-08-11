# -*- coding: utf-8 -*-

from ..let import let, letrec, dlet, dletrec, blet, bletrec

from ..env import env as _envcls
from ..misc import call
from ..seq import begin

def runtests():
    # order-preserving list uniqifier
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

        f4 = lambda lst: let(seen=set(),
                             body=lambda e: [e.seen.add(x) or x for x in lst if x not in e.seen])

        f5 = lambda lst: letrec(seen=set(),
                                see=lambda e: lambda x: begin(e.seen.add(x), x),
                                body=lambda e: [e.see(x) for x in lst if x not in e.seen])

        L = [1, 1, 3, 1, 3, 2, 3, 2, 2, 2, 4, 4, 1, 2, 3]

        # Call each implementation twice to make sure that a fresh `seen`
        # is indeed created at each call.
        assert f(L) == f(L)
        assert f2(L) == f2(L)
        assert f3(L) == f3(L)
        assert f4(L) == f4(L)
        assert f5(L) == f5(L)

        assert f(L) == f2(L) == f3(L) == f4(L) == f5(L) == [1, 3, 2, 4]

    uniqify_test()

    # Let over lambda. The inner lambda is the definition of the function f.
    counter = let(x=0,
                  body=lambda e: lambda: begin(e.set("x", e.x + 1),
                                               e.x))
    counter()
    counter()
    assert counter() == 3

    # let-over-def
    @dlet(count=0)
    def counter2(*, env=None):  # env: named argument containing the let bindings
        env.count += 1
        return env.count
    counter2()
    counter2()
    assert(counter2() == 3)

    @dlet(y=23)
    def foo(x, *, env):
        return x + env.y
    assert foo(17) == 40

    @dlet(x=5)
    def bar(*, env):
        assert env.x == 5

        @dlet(x=42)
        def baz(*, env):  # this env shadows the outer env
            assert env.x == 42
        baz()

        assert env.x == 5
    bar()

    @call
    @dlet(x=5)
    def _ignored1(*, env):  # this is now the let block, run immediately
        assert env.x == 5

        @call
        @dlet(x=42)
        def _(*, env):
            assert env.x == 42

        assert env.x == 5

    # same effect
    @blet(x=5)
    def _ignored2(*, env):
        assert env.x == 5

        @blet(x=42)
        def _ignored3(*, env):
            assert env.x == 42

        assert env.x == 5

    # example from https://docs.racket-lang.org/reference/let.html
    t = letrec(evenp=lambda e: lambda x: (x == 0) or e.oddp(x - 1),
               oddp=lambda e: lambda x: (x != 0) and e.evenp(x - 1),
               body=lambda e: e.evenp(42))
    assert t is True

    # somewhat pythonic solution:
    @call
    def t():
        def evenp(x): return x == 0 or oddp(x - 1)
        def oddp(x): return x != 0 and evenp(x - 1)
        return evenp(42)
    assert t is True

    # letrec-over-def
    @dletrec(evenp=lambda e: lambda x: (x == 0) or e.oddp(x - 1),
             oddp=lambda e: lambda x: (x != 0) and e.evenp(x - 1))
    def is_even(x, *, env):
        return env.evenp(x)
    assert is_even(23) is False

    # code block with letrec
    @bletrec(evenp=lambda e: lambda x: (x == 0) or e.oddp(x - 1),
             oddp=lambda e: lambda x: (x != 0) and e.evenp(x - 1))
    def result(*, env):
        return env.evenp(23)
    assert result is False

    try:
        let(x=0,
            body=lambda e: e.set('y', 3))  # error, y is not defined
    except AttributeError:
        pass
    else:
        assert False

    try:
        @blet(x=1)
        def error1(*, env):
            env.y = 2  # error, cannot introduce new bindings to a let environment
    except AttributeError:
        pass
    else:
        assert False

    print("All tests PASSED")

if __name__ == '__main__':
    runtests()
