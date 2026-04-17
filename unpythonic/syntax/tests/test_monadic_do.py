# -*- coding: utf-8 -*-
"""Tests for the `with monadic_do[M] as result:` macro."""

from ...syntax import macros, test, test_raises, the, monadic_do  # noqa: F401
from ...test.fixtures import session, testset

from ...llist import nil
from ...monads import Maybe, Either, Left, Right, List, Writer, State, Reader


def runtests():
    with testset("basic expansion (Maybe)"):
        with monadic_do[Maybe] as a:
            [x := Maybe(10),
             y := Maybe(x + 1)] in Maybe(x + y)
        test[a == Maybe(21)]

        # Short-circuit: Nothing propagates; later bindings never fire.
        with monadic_do[Maybe] as b:
            [x := Maybe(nil),
             y := Maybe(x + 1)] in Maybe(x + y)
        test[b == Maybe(nil)]

        # Empty bindings shorthand.
        with monadic_do[Maybe] as c:
            [] in Maybe(42)
        test[c == Maybe(42)]

    with testset("binding-syntax variants"):
        # := is the primary binding syntax
        with monadic_do[Maybe] as a:
            [x := Maybe(3)] in Maybe(x * 2)
        test[a == Maybe(6)]

        # << is the legacy (discordian-deprecated) alternative
        with monadic_do[Maybe] as b:
            [x << Maybe(3)] in Maybe(x * 2)
        test[b == Maybe(6)]

        # Mixed (letdoutil allows both in the same block)
        with monadic_do[Maybe] as c:
            [x := Maybe(2),
             y << Maybe(x + 3)] in Maybe(x * y)
        test[c == Maybe(10)]

    with testset("sequencing — bare expressions in bindings"):
        # Bare expression on a binding line = Haskell's `do { mx; ... }`
        # (sequence, not bind). The macro wraps it synthetically as `_ := mexpr`.
        with monadic_do[List] as filtered:
            [x := List.from_iterable(range(1, 6)),
             List.guard(x % 2 == 0)] in List(x)
        test[filtered == List(2, 4)]

        # Mixed bare + binding lines
        with monadic_do[List] as mixed:
            [x := List(1, 2, 3),
             List.guard(x > 1),
             y := List(x * 10)] in List((x, y))
        test[mixed == List((2, 20), (3, 30))]

    with testset("Either short-circuit"):
        with monadic_do[Either] as a:
            [x := Right(10),
             y := Right(x * 2)] in Right(x + y)
        test[a == Right(30)]

        # Left short-circuits; second binding not evaluated
        called = []
        def track(v):
            called.append(v)
            return Right(v * 2)
        with monadic_do[Either] as b:
            [x := Left("boom"),
             y := track(x)] in Right(x + y)
        test[b == Left("boom")]
        test[called == []]  # `track` never invoked

    with testset("List monad — Pythagorean triples"):
        def r(lo, hi):
            return List.from_iterable(range(lo, hi))
        with monadic_do[List] as pt:
            [z := r(1, 21),
             x := r(1, z + 1),
             y := r(x, z + 1),
             List.guard(x * x + y * y == z * z)] in List((x, y, z))
        test[tuple(sorted(pt)) == ((3, 4, 5), (5, 12, 13), (6, 8, 10),
                                   (8, 15, 17), (9, 12, 15), (12, 16, 20))]

    with testset("Writer"):
        with monadic_do[Writer] as w:
            [x := Writer(10, "got 10; "),
             y := Writer(x + 1, "added 1; ")] in Writer(y * 2, "doubled; ")
        value, log = w.data
        test[value == 22]
        test[log == "got 10; added 1; doubled; "]

    with testset("State"):
        bump = State(lambda s: (s, s + 1))
        with monadic_do[State] as st:
            [a := bump,
             b := bump,
             c := bump] in State.unit((a, b, c))
        vals, final = st.run(10)
        test[vals == (10, 11, 12)]
        test[final == 13]

    with testset("Reader"):
        with monadic_do[Reader] as rd:
            [m := Reader.asks(lambda env: env["multiplier"]),
             o := Reader.asks(lambda env: env["offset"])] in Reader.unit(m * 5 + o)
        test[rd.run({"multiplier": 3, "offset": 10}) == 25]

    with testset("nested do-blocks"):
        # Nested do works because the outer's body is a single statement
        # but inside the final expression we can invoke another do.
        def maybe_addone():
            with monadic_do[Maybe] as inner:
                [x := Maybe(10)] in Maybe(x + 1)
            return inner

        with monadic_do[Maybe] as outer:
            [y := maybe_addone()] in Maybe(y * 2)
        test[outer == Maybe(22)]


if __name__ == '__main__':  # pragma: no cover
    with session(__file__):
        runtests()
