# -*- coding: utf-8 -*-
"""Integration tests for `monadic_do` composed with other block macros.

`monadic_do` is always the innermost `with`; outer block macros expand
inner macros between their passes, so the generated bind chain is
visible to them for further transformation.

See `briefs/monads-implementation.md` for the full analysis of why each
combination works, and `doc/macros.md` (the xmas-tree section) for the
correct nesting order.
"""

from ...syntax import (macros, test, the,  # noqa: F401
                       monadic_do,
                       autocurry, lazify, tco, continuations,
                       multilambda, quicklambda, namedlambda, autoreturn,
                       envify, autoref)
from ...test.fixtures import session, testset

from ...llist import nil
from ...monads import Maybe, Either, Left, Right


def runtests():
    with testset("must: continuations + monadic_do"):
        with continuations:
            with monadic_do[Maybe] as result:
                [x := Maybe(10),
                 y := Maybe(x + 1)] in result << Maybe(x + y)
        test[result == Maybe(21)]

    with testset("must: autocurry + monadic_do"):
        with autocurry:
            with monadic_do[Maybe] as result:
                [x := Maybe(5),
                 y := Maybe(x + 1)] in result << Maybe(x * y)
        test[result == Maybe(30)]

    with testset("must: lazify + monadic_do (basic)"):
        with lazify:
            with monadic_do[Maybe] as result:
                [x := Maybe(10),
                 y := Maybe(x + 1)] in result << Maybe(x + y)
        test[result == Maybe(21)]

    with testset("must: lazify + monadic_do (short-circuit preserves non-forcing)"):
        # The key guarantee: on the short-circuit path, later binding RHSs
        # must NOT be forced (no observable side effect, no exceptions).
        side_effects = []
        def observable_builder():
            side_effects.append("called")
            return Maybe(999)

        with lazify:
            with monadic_do[Maybe] as result:
                [x := Maybe(nil),
                 y := observable_builder()] in result << Maybe(x + y)
        test[result == Maybe(nil)]
        test[side_effects == []]  # observable_builder never invoked

        # Same for Either.
        counter = [0]
        def bump_and_build():
            counter[0] += 1
            return Right(counter[0])

        with lazify:
            with monadic_do[Either] as result2:
                [x := Left("bail"),
                 y := bump_and_build()] in result2 << Right(x + y)
        test[result2 == Left("bail")]
        test[counter[0] == 0]

    with testset("must: tco + monadic_do"):
        with tco:
            with monadic_do[Maybe] as result:
                [x := Maybe(7),
                 y := Maybe(x + 1)] in result << Maybe(x + y)
        test[result == Maybe(15)]

    with testset("smoke: multilambda + monadic_do"):
        with multilambda:
            with monadic_do[Maybe] as result:
                [x := Maybe(3),
                 y := Maybe(x * 2)] in result << Maybe(x + y)
        test[result == Maybe(9)]

    with testset("smoke: quicklambda + monadic_do"):
        with quicklambda:
            with monadic_do[Maybe] as result:
                [x := Maybe(3),
                 y := Maybe(x * 2)] in result << Maybe(x + y)
        test[result == Maybe(9)]

    with testset("smoke: namedlambda + monadic_do"):
        with namedlambda:
            with monadic_do[Maybe] as result:
                [x := Maybe(3),
                 y := Maybe(x * 2)] in result << Maybe(x + y)
        test[result == Maybe(9)]

    with testset("smoke: autoreturn + monadic_do"):
        # autoreturn inserts `return` into function bodies; the monadic_do
        # body is a single Expr inside a `with`, so autoreturn should
        # leave it alone. Verify the `result << expr` exit pattern
        # still works.
        def compute():
            with autoreturn:
                with monadic_do[Maybe] as result:
                    [x := Maybe(4)] in result << Maybe(x + 6)
                return result
        test[compute() == Maybe(10)]

    with testset("smoke: envify + monadic_do"):
        with envify:
            with monadic_do[Maybe] as result:
                [x := Maybe(5)] in result << Maybe(x + 1)
        test[result == Maybe(6)]

    with testset("smoke: autoref + monadic_do"):
        from ...env import env as _env
        the_env = _env(base=100)
        with autoref[the_env]:
            with monadic_do[Maybe] as result:
                [x := Maybe(5)] in result << Maybe(x + base)  # noqa: F821, via autoref
        test[result == Maybe(105)]


if __name__ == '__main__':  # pragma: no cover
    with session(__file__):
        runtests()
