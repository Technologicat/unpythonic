# -*- coding: utf-8 -*-
"""Automatic currying."""

from ...syntax import macros, curry  # noqa: F401

from ...fold import foldr
from ...fun import composerc as compose
from ...llist import cons, nil, ll
from ...collections import frozendict

def runtests():
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

        # # NOTE: because builtins cannot be inspected, curry just no-ops on them.
        # # So this won't work:
        # # v0.10.2: Workaround added for top-level builtins. Now this works.
        # from operator import add
        # try:
        #     f = add(1)
        #     assert f(2) == 3
        # except TypeError:
        #     pass
        # else:
        #     assert False, "update unpythonic documentation"
        # # In cases like this, make a wrapper:
        # myadd = lambda a, b: add(a, b)
        # f = myadd(1)
        # assert f(2) == 3

        def stuffinto(lst, x):
            lst.append(x)  # uninspectable, currycall should no-op and pass the given args through as-is
        lst = [1, 2, 3]
        stuffinto(lst)(4)
        assert lst == [1, 2, 3, 4]

    # The function "add3" was defined inside the block, so it has the implicit
    # @curry decorator. Hence a call into "add3" is a curry context.
    assert add3(1)(2)(3) == 6
    assert add3(1, 2)(3) == 6
    assert add3(1)(2, 3) == 6
    assert add3(1, 2, 3) == 6

    stuffinto(lst)(5)
    assert lst == [1, 2, 3, 4, 5]

    # should not insert an extra @curry even if we curry manually
    # (convenience, for with-currying existing code)
    with curry:
        from unpythonic.fun import curry
        @curry
        def add3(a, b, c):
            return a + b + c
        assert add3(1)(2)(3) == 6

        f = curry(lambda a, b, c: a + b + c)
        assert f(1)(2)(3) == 6

        from unpythonic.tco import trampolined, jump
        from unpythonic.fun import withself
        fact = trampolined(withself(curry(lambda self, n, acc=1:
                                          acc if n == 0 else jump(self, n - 1, n * acc))))
        assert fact(5) == 120

    # dict_items handling in mogrify
    with curry:
        d1 = frozendict(foo='bar', bar='tavern')
        d2 = frozendict(d1, bar='pub')
        assert tuple(sorted(d1.items())) == (('bar', 'tavern'), ('foo', 'bar'))
        assert tuple(sorted(d2.items())) == (('bar', 'pub'), ('foo', 'bar'))

    print("All tests PASSED")

if __name__ == '__main__':
    runtests()
