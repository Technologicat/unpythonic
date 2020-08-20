# -*- coding: utf-8 -*-
"""Automatic currying."""

from ...syntax import macros, test  # noqa: F401
from ...test.fixtures import session, testset

from ...syntax import macros, curry  # noqa: F401, F811

from ...fold import foldr
from ...fun import composerc as compose
from ...llist import cons, nil, ll
from ...collections import frozendict

def runtests():
    with testset("basic usage"):
        with curry:
            mymap = lambda f: foldr(compose(cons, f), nil)
            double = lambda x: 2 * x
            assert mymap(double, (1, 2, 3)) == ll(2, 4, 6)

            def add3(a, b, c):
                return a + b + c
            test[add3(1)(2)(3) == 6]
            test[add3(1, 2)(3) == 6]
            test[add3(1)(2, 3) == 6]
            test[add3(1, 2, 3) == 6]

            # # NOTE: because builtins cannot be inspected, curry just no-ops on them.
            # # So this won't work:
            # # v0.10.2: Workaround added for top-level builtins. Now this works.
            # from operator import add
            # try:
            #     f = add(1)
            #     test[f(2) == 3]
            # except TypeError:
            #     pass
            # else:
            #     fail["update unpythonic documentation"]
            # # In cases like this, make a wrapper:
            # myadd = lambda a, b: add(a, b)
            # f = myadd(1)
            # assert f(2) == 3

            def stuffinto(lst, x):
                lst.append(x)  # uninspectable, currycall should no-op and pass the given args through as-is
            lst = [1, 2, 3]
            stuffinto(lst)(4)
            test[lst == [1, 2, 3, 4]]

    # The function "add3" was defined inside the block, so it has the implicit
    # @curry decorator. Hence a call into "add3" is a curry context.
    with testset("implicit @curry decorator"):
        test[add3(1)(2)(3) == 6]
        test[add3(1, 2)(3) == 6]
        test[add3(1)(2, 3) == 6]
        test[add3(1, 2, 3) == 6]

        stuffinto(lst)(5)
        test[lst == [1, 2, 3, 4, 5]]

    # should not insert an extra @curry even if we curry manually
    # (convenience, for with-currying existing code)
    with testset("extra @curry insertion avoidance logic"):
        with curry:
            from unpythonic.fun import curry
            @curry
            def add3(a, b, c):
                return a + b + c
            test[add3(1)(2)(3) == 6]

            f = curry(lambda a, b, c: a + b + c)
            test[f(1)(2)(3) == 6]

            from unpythonic.tco import trampolined, jump
            from unpythonic.fun import withself
            fact = trampolined(withself(curry(lambda self, n, acc=1:
                                              acc if n == 0 else jump(self, n - 1, n * acc))))
            test[fact(5) == 120]

    with testset("integration: dict_items handling in mogrify"):
        with curry:
            d1 = frozendict(foo='bar', bar='tavern')
            d2 = frozendict(d1, bar='pub')
            test[tuple(sorted(d1.items())) == (('bar', 'tavern'), ('foo', 'bar'))]
            test[tuple(sorted(d2.items())) == (('bar', 'pub'), ('foo', 'bar'))]

if __name__ == '__main__':  # pragma: no cover
    with session(__file__):
        runtests()
