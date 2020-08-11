# -*- coding: utf-8 -*-
"""Implicitly reference attributes of an object."""

from ...syntax import macros, autoref, let, do, local, lazify, curry  # noqa: F401
#from macropy.tracing import macros, show_expanded  # noqa: F811

from ...env import env

def runtests():
    e = env(a=1, b=2)
    c = 3
    with autoref(e):
        assert a == 1  # a --> e.a  # noqa: F821
        assert b == 2  # b --> e.b  # noqa: F821
        assert c == 3  # no c in e, so just c

    # v0.14.1+:

    with autoref(e):
        e.d = 4        # write --> no transformation
        assert d == 4  # d --> e.d  # noqa: F821
        del e["d"]     # delete --> no transformation

    with autoref(e):
        e.d = 5
        assert d == 5  # noqa: F821
        del e.d        # delete --> no transformation

    with autoref(e) as e3:
        x = 3
        assert "x" not in e3
        assert x == 3
        del x

    # nested autorefs allowed (lexically scoped)
    e2 = env(a=42, c=17)
    with autoref(e):
        with autoref(e2):
            assert a == 42  # noqa: F821
            assert b == 2  # noqa: F821
            assert c == 17

    ee = e
    with autoref(e):        # no asname means "gensym a new variable to hold the value of the expr"
        assert ee is e      # so here both sides expand to autoref lookups

    with autoref(e) as e3:  # but name it explicitly...
        assert ee is e3     # ...and the reference to "e3" is smart enough to skip the autoref lookup

#    # ...also in nested autoref blocks
#    # TODO: how to test? For now, just "with show_expanded" this and eyeball the result.
#    with autoref(env(a=1, b=2)) as e1:
#        e1  # just e1, no autoref lookup
#        with autoref(env(c=3, d=4)) as e2:
#            e2  # just e2
#            e1  # just e1 (special handling; already inserted lookup is removed by the outer block when it expands)

    # attributes and subscripts allowed
    e2 = env(x=e, s=[1, 2, 3])
    with autoref(e2) as e2:
        assert "x" in e2
        assert "e" not in e2
        assert x is e       # --> e2.x is e (attempts to look up "e" in e2, fails, lets Python resolve "e")  # noqa: F821
        assert x.a == 1     # --> e2.x.a  # noqa: F821
        assert x["b"] == 2  # --> e2.x["b"]  # noqa: F821
        assert s[2] == 3    # --> e2.s[2]  # noqa: F821

    # the intended use is something like env(**scipy.io.loadmat('foo.mat'))
    # and then omit the environment name prefix in math formulas
    dic = {"a": 1, "b": 2}  # loadmat returns a dictionary; mock result
    c = 3
    with autoref(env(**dic)) as t:
        assert a == 1  # noqa: F821
        assert b == 2  # noqa: F821
        assert c == 3
        assert t.a == 1  # can also refer explicitly
        assert t.b == 2
        try:
            t.c
        except AttributeError:
            pass
        else:
            assert False, "t should not have an attribute 'c' here"

    # let and do envs skip the autoref lookup
    e = env(a=1)
    with autoref(e):
        x = do[local[a << 2], 2 * a]  # noqa: F821
        assert x == 4
        y = let[(x, 21) in 2 * x]
        assert y == 42
        z = let[(x, 21) in 2 * a]  # e.a  # noqa: F821
        assert z == 2

    with lazify:
        e = env(a=1, b=1 / 0)
        with autoref(e):
            assert a == 1  # noqa: F821

    with curry:
        e = env(a=1)
        with autoref(e):
            assert a == 1  # noqa: F821

    print("All tests PASSED")

if __name__ == '__main__':
    runtests()
