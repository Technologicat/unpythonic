# -*- coding: utf-8 -*-
"""Implicitly reference attributes of an object."""

from ...syntax import macros, test, test_raises, the  # noqa: F401
from ...test.fixtures import session, testset, returns_normally

from ...syntax import macros, autoref, let, do, local, lazify, autocurry  # noqa: F401, F811
#from mcpyrate.debug import macros, step_expansion  # noqa: F811
#from mcpyrate.debug import macros, show_bindings  # noqa: F811

from ...env import env

def runtests():
    #show_bindings
    with testset("basic usage"):
        e = env(a=1, b=2)
        c = 3
        with autoref[e]:
            test[a == 1]  # a --> e.a  # noqa: F821
            test[b == 2]  # b --> e.b  # noqa: F821
            test[c == 3]  # no c in e, so just c

        # v0.14.1+:

        with autoref[e]:
            e.d = 4        # write --> no transformation
            test[d == 4]  # d --> e.d  # noqa: F821
            del e["d"]     # delete --> no transformation

        with autoref[e]:
            e.d = 5
            test[d == 5]  # noqa: F821
            del e.d        # delete --> no transformation

        with autoref[e] as e3:
            x = 3
            test["x" not in the[e3]]
            test[x == 3]
            del x

        ee = e
        with autoref[e]:        # no asname means "gensym a new variable to hold the value of the expr"
            test[ee is e]       # so here both sides expand to autoref lookups

        with autoref[e] as e3:  # but name it explicitly...
            test[ee is e3]      # ...and the reference to "e3" is smart enough to skip the autoref lookup

    # nested autorefs allowed (lexically scoped)
    with testset("nesting"):
        e2 = env(a=42, c=17)
        with autoref[e]:
            with autoref[e2]:
                test[a == 42]  # noqa: F821
                test[b == 2]  # noqa: F821
                test[c == 17]

        with autoref[e] as outer:  # noqa: F841, we're invoking a different case inside the macro code.
            with autoref[e2] as inner:  # noqa: F841
                test[returns_normally(outer.a)]  # exists
                test[a == 42]  # noqa: F821
                test[b == 2]  # noqa: F821
                test[c == 17]

        # # Explicit asname optimizes lookups also in nested autoref blocks.
        # # TODO: To test this, we need to use run-time compiler access and look at the AST.
        # # TODO: See how `mcpyrate` does its tests.
        # # TODO: For now, just "with step_expansion" this and eyeball the result.
        # with autoref[env(a=1, b=2)] as e1:
        #     e1  # just e1, no autoref lookup
        #     with autoref[env(c=3, d=4, e1=None)] as e2:
        #         e2  # just e2
        #         e1  # just e1 (special handling; already inserted lookup is removed by the outer block when it expands)
        # But this special case we can test easily:
        with autoref[env(a=1, b=2)] as e1:
            # Place a key "e1" into our second env so that a spurious lookup for that triggers an error.
            with autoref[env(c=3, d=4, e1=None)] as e2:
                test[isinstance(e1, env)]  # just e1, no lookup

    with testset("attributes and subscripts"):
        e2 = env(x=e, s=[1, 2, 3])
        with autoref[e2] as e2:
            test["x" in the[e2]]
            test["e" not in the[e2]]
            test[x is e]       # --> e2.x is e (attempts to look up "e" in e2, fails, lets Python resolve "e")  # noqa: F821
            test[x.a == 1]     # --> e2.x.a  # noqa: F821
            test[x["b"] == 2]  # --> e2.x["b"]  # noqa: F821
            test[s[2] == 3]    # --> e2.s[2]  # noqa: F821

    # the intended use is something like env(**scipy.io.loadmat('foo.mat'))
    # and then omit the environment name prefix in math formulas
    with testset("usage example"):
        dic = {"a": 1, "b": 2}  # loadmat returns a dictionary; mock result
        c = 3
        with autoref[env(**dic)] as t:
            test[a == 1]  # noqa: F821
            test[b == 2]  # noqa: F821
            test[c == 3]
            test[t.a == 1]  # can also refer explicitly
            test[t.b == 2]
            test_raises[AttributeError, t.c, "t should not have an attribute 'c' here"]

    # let and do envs skip the autoref lookup
    with testset("integration with let and do envs"):
        e = env(a=1)
        with autoref[e]:
            x = do[local[a << 2], 2 * a]  # noqa: F821
            test[x == 4]
            y = let[[x << 21] in 2 * x]
            test[y == 42]
            z = let[[x << 21] in 2 * a]  # e.a  # noqa: F821
            test[z == 2]

    with testset("integration with lazify"):
        with lazify:
            e = env(a=1, b=1 / 0)
            with autoref[e]:
                test[a == 1]  # noqa: F821

    with testset("integration with autocurry"):
        with autocurry:
            e = env(a=1)
            with autoref[e]:
                test[a == 1]  # noqa: F821

if __name__ == '__main__':  # pragma: no cover
    with session(__file__):
        runtests()
