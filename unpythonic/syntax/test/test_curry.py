# -*- coding: utf-8 -*-
"""Automatic currying."""

from ...syntax import macros, curry

from ...fold import foldr
from ...fun import composerc as compose
from ...llist import cons, nil, ll

from macropy.tracing import macros, show_expanded

def test():
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
#        # v0.10.2: Workaround added for top-level builtins. Now this works.
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

        def stuffinto(lst, x):
            lst.append(x)  # uninspectable, currycall should no-op
        lst = [1, 2, 3]
        stuffinto(lst, 4)
        assert lst == [1, 2, 3, 4]

    # Outside the with block, autocurry is not active, but the function was
    # defined inside the block, so it has implicit @curry.
    assert add3(1)(2)(3) == 6

    stuffinto(lst, 5)
    assert lst == [1, 2, 3, 4, 5]

    # should not insert an extra @curry even if we curry manually
    # (convenience, for with-currying existing code)
    with show_expanded:
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

    print("All tests PASSED")
