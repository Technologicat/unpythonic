# -*- coding: utf-8 -*-
"""Automatic currying."""

from ...syntax import macros, curry

from ...fold import foldr
from ...fun import composerc as compose
from ...llist import cons, nil, ll

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

    # Outside the with block, autocurry is not active, but the function was
    # defined inside the block, so it has implicit @curry.
    #
    # Note this works only if add3 contains no uninspectable functions,
    # because we are now outside the dynamic extent of the "with curry" block,
    # so the special mode of unpythonic.fun.curry is no longer active.
    assert add3(1)(2)(3) == 6

    print("All tests PASSED")
