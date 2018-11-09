# -*- coding: utf-8 -*-
"""Multi-expression lambdas with implicit do; named lambdas."""

from ...syntax import macros, multilambda, namedlambda, local, let

def test():
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
                 lambda: [x << x + 1,      # x belongs to the surrounding let
                          local(y << 42),  # y is local to the implicit do
                          (x, y)]]
        assert test() == (1, 42)
        assert test() == (2, 42)

        myadd = lambda x, y: [print("myadding", x, y),
                              local(tmp << x + y),
                              print("result is", tmp),
                              tmp]
        assert myadd(2, 3) == 5

        # only the outermost set of brackets denote a multi-expr body:
        t = lambda: [[1, 2]]
        assert t() == [1, 2]

    with namedlambda:
        f = lambda x: x**3                       # lexical rule: name as "f"
        assert f.__name__ == "f (lambda)"
        gn, hn = let((x, 42), (g, None), (h, None))[[
                       g << (lambda x: x**2),    # dynamic rule: name as "g"
                       h << f,                   # no-rename rule: still "f"
                       (g.__name__, h.__name__)]]
        assert gn == "g (lambda)"
        assert hn == "f (lambda)"

    print("All tests PASSED")

if __name__ == '__main__':
    test()
