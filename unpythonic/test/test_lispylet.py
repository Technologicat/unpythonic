# -*- coding: utf-8 -*-

from ..syntax import macros, test, test_raises  # noqa: F401
from .fixtures import testset

from functools import partial

from ..lispylet import let, letrec, dlet, dletrec, blet, bletrec

from ..seq import begin

def runtests():
    with testset("unpythonic.lispylet"):
        with testset("basic usage"):
            x = let((('a', 1),
                     ('b', 2)),
                    lambda e: e.a + e.b)
            test[x == 3]

            x = letrec((('a', 1),
                        ('b', lambda e:
                                e.a + 2)),  # hence, b = 3
                       lambda e:
                         e.a + e.b)
            test[x == 4]

            # mutually recursive functions
            t = letrec((('evenp', lambda e:
                                    lambda x:
                                      (x == 0) or e.oddp(x - 1)),
                        ('oddp', lambda e:
                                   lambda x:
                                     (x != 0) and e.evenp(x - 1))),
                       lambda e:
                         e.evenp(42))
            test[t is True]

            f = lambda lst: letrec((("seen", set()),
                                    ("see", lambda e:
                                              lambda x:
                                                begin(e.seen.add(x),
                                                      x))),
                                   lambda e:
                                     [e.see(x) for x in lst if x not in e.seen])
            L = [1, 1, 3, 1, 3, 2, 3, 2, 2, 2, 4, 4, 1, 2, 3]
            test[f(L) == [1, 3, 2, 4]]

        # Callable values always need a surrounding "lambda e: ...".
        with testset("additional examples with callable values"):
            test[letrec((('a', 2),
                         ('f', lambda e:
                                 lambda x:  # callable, needs the surrounding "lambda e: ...", even though it doesn't use e.
                                   42 * x)),
                        lambda e:
                          e.a * e.f(1)) == 84]

            square = lambda x: x**2
            test[letrec((('a', 2),
                         ('f', lambda e: square)),  # callable, needs "lambda e: ..."
                        lambda e:
                          e.a * e.f(10)) == 200]

            def mul(x, y):
                return x * y
            test[letrec((('a', 2),
                         ('f', lambda e: mul)),  # "mul" is a callable
                        lambda e:
                          e.a * e.f(3, 4)) == 24]

            double = partial(mul, 2)
            test[letrec((('a', 2),
                         ('f', lambda e: double)),  # "double" is a callable
                        lambda e:
                          e.a * e.f(3)) == 12]

            class TimesA:
                def __init__(self, a):
                    self.a = a
                def __call__(self, x):
                    return self.a * x
            times5 = TimesA(5)
            test[letrec((('a', 2),
                         ('f', lambda e: times5)),  # "times5" is a callable
                        lambda e:
                          e.a * e.f(3)) == 30]

        with testset("let over lambda"):
            lc = let((('count', 0),),
                     lambda e:
                       lambda: begin(e.set('count', e.count + 1),
                                     e.count))
            lc()
            lc()
            test[lc() == 3]

        with testset("let over def"):
            @dlet((('x', 17),))
            def foo(*, env):
                return env.x
            test[foo() == 17]

            @dletrec((('x', 2),
                      ('y', lambda e: e.x + 3)))
            def bar(a, *, env):
                return a + env.y
            test[bar(10) == 15]

            @dlet((('count', 0),))
            def counter(*, env):
                env.count += 1
                return env.count
            counter()
            counter()
            test[counter() == 3]

        with testset("let block"):
            @blet((('x', 9001),))
            def over9000(*, env):
                return env.x
            test[over9000 == 9001]

            @bletrec((('evenp', lambda e:
                                  lambda x:
                                    (x == 0) or e.oddp(x - 1)),
                      ('oddp', lambda e:
                                 lambda x:
                                   (x != 0) and e.evenp(x - 1)),))
            def result(*, env):
                return env.evenp(42)
            test[result is True]

        with testset("error cases"):
            test_raises[AttributeError,
                        letrec((('a', lambda e:
                                        e.b + 1),  # error, e.b does not exist yet (simple value refers to binding below it)
                                ('b', 42)),
                               lambda e:
                                 e.a)]

            test_raises[AttributeError,
                        let((('x', 0),),
                            lambda e:
                              e.set('y', 3))]  # error, y is not defined

            with test_raises(AttributeError, "let environment is final (no new bindings inside the body)"):
                @blet((('x', 1),))
                def error1(*, env):
                    env.y = 2  # error, cannot introduce new bindings to a let environment

if __name__ == '__main__':
    runtests()
