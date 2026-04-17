# -*- coding: utf-8 -*-
"""Tests for the pure-Python monad subpackage."""

from math import sqrt

from ...syntax import macros, test, test_raises, the  # noqa: F401
from ...test.fixtures import session, testset

from ...llist import nil

from .. import (
    Monad, LiftableMonad,
    liftm, liftm2, liftm3,
    Identity, Maybe, Either, Left, Right, List, Writer, State, Reader,
)


def runtests():
    with testset("Monad / LiftableMonad base classes"):
        # Every monad subclass inherits from Monad.
        for M in (Identity, Maybe, Either, Left, Right, List, Writer, State, Reader):
            test[issubclass(M, Monad)]

        # The Liftable subset.
        for M in (Identity, Maybe, Either, Left, Right, List, Writer):
            test[issubclass(M, LiftableMonad)]

        # State and Reader are NOT LiftableMonad.
        for M in (State, Reader):
            test[not issubclass(M, LiftableMonad)]

        # isinstance works for concrete monad values.
        test[isinstance(Identity(5), Monad)]
        test[isinstance(Maybe(nil), LiftableMonad)]
        test[isinstance(State.unit(1), Monad)]
        test[not isinstance(State.unit(1), LiftableMonad)]

        # Default bind (fmap . join) actually fires for a minimal subclass.
        # Use Identity as a stand-in — its __rshift__ comes from Monad (no override).
        out = Identity(3) >> (lambda x: Identity(x + 7))
        test[out == Identity(10)]

        # Default then fires similarly.
        out2 = Identity(1).then(Identity(99))
        test[out2 == Identity(99)]

        # then's type check rejects cross-monad sequencing.
        test_raises[TypeError, Identity(1).then(Maybe(5))]

    with testset("liftm, liftm2, liftm3"):
        lifted1 = liftm(Maybe, lambda x: x + 1)
        test[lifted1(Maybe(5)) == Maybe(6)]
        test[lifted1(Maybe(nil)) == Maybe(nil)]  # short-circuit preserved

        # liftm requires a monadic argument.
        test_raises[TypeError, lifted1(5)]

        lifted2 = liftm2(Identity, lambda x, y: x * y)
        test[lifted2(Identity(3), Identity(4)) == Identity(12)]
        test_raises[TypeError, lifted2(3, Identity(4))]
        test_raises[TypeError, lifted2(Identity(3), 4)]

        lifted3 = liftm3(Identity, lambda x, y, z: x + y + z)
        test[lifted3(Identity(1), Identity(2), Identity(3)) == Identity(6)]
        test_raises[TypeError, lifted3(1, Identity(2), Identity(3))]
        test_raises[TypeError, lifted3(Identity(1), 2, Identity(3))]
        test_raises[TypeError, lifted3(Identity(1), Identity(2), 3)]

    with testset("Identity"):
        test[Identity(42) == Identity(42)]
        test[(Identity(2) >> (lambda x: Identity(x + 1))) == Identity(3)]
        test[Identity(5).fmap(lambda x: x * 10) == Identity(50)]
        test[Identity(Identity(7)).join() == Identity(7)]
        test_raises[TypeError, Identity(5).join()]  # not nested
        test[Identity.lift(lambda x: x + 100)(5) == Identity(105)]

    with testset("Maybe"):
        # Happy path
        test[(Maybe(10) >> (lambda x: Maybe(x + 1))) == Maybe(11)]

        # Short-circuit: Nothing propagates; lambda never called
        called = []
        def watcher(x):
            called.append(x)
            return Maybe(x + 1)
        result = Maybe(nil) >> watcher
        test[result == Maybe(nil)]
        test[called == []]  # watcher never invoked

        # fmap preserves Nothing
        test[Maybe(nil).fmap(lambda x: x * 2) == Maybe(nil)]
        test[Maybe(5).fmap(lambda x: x * 2) == Maybe(10)]

        # join
        test[Maybe(Maybe(7)).join() == Maybe(7)]
        test[Maybe(nil).join() == Maybe(nil)]
        test_raises[TypeError, Maybe(5).join()]  # not nested

        # guard
        test[Maybe.guard(True).then(Maybe(42)) == Maybe(42)]
        test[Maybe.guard(False).then(Maybe(42)) == Maybe(nil)]

        # lift
        test[Maybe.lift(lambda x: x + 1)(5) == Maybe(6)]

        # Classical sqrt chain (via Maybe)
        def maybe_sqrt(x):
            if x < 0:
                return Maybe(nil)
            return Maybe(sqrt(x))
        test[Maybe(16) >> maybe_sqrt >> maybe_sqrt == Maybe(2.0)]
        test[Maybe(-1) >> maybe_sqrt >> maybe_sqrt == Maybe(nil)]

    with testset("Either / Left / Right"):
        # Construction
        test[Right(42) == Right(42)]
        test[Left("err") == Left("err")]
        test[Right(42) != Left(42)]  # different branches, same value
        test_raises[TypeError, Either(5)]  # abstract

        # Happy path
        test[(Right(10) >> (lambda x: Right(x + 1))) == Right(11)]

        # Short-circuit
        test[Left("boom") >> (lambda x: Right(x + 1)) == Left("boom")]

        # Left doesn't invoke the lambda
        called = []
        Left("err") >> (lambda x: (called.append(x), Right(x))[1])
        test[called == []]

        # fmap
        test[Right(5).fmap(lambda x: x * 2) == Right(10)]
        test[Left("err").fmap(lambda x: x * 2) == Left("err")]

        # join
        test[Right(Right(7)).join() == Right(7)]
        test[Right(Left("nested err")).join() == Left("nested err")]
        test[Left("outer").join() == Left("outer")]
        test_raises[TypeError, Right(5).join()]  # not nested

        # lift (always produces Right)
        test[Either.lift(lambda x: x + 1)(5) == Right(6)]
        test[Right.lift(lambda x: x + 1)(5) == Right(6)]

        # Cross-subclass then (Right.then(Left) works)
        test[Right(1).then(Left("replace")) == Left("replace")]
        test[Left("err").then(Right(5)) == Left("err")]  # short-circuit wins

        # guard
        test[Either.guard(True).then(Right(42)) == Right(42)]
        test[Either.guard(False, "bad").then(Right(42)) == Left("bad")]

    with testset("List"):
        test[List() == List()]
        test[List(1, 2, 3) == List(1, 2, 3)]
        test[List(nil) == List()]  # sentinel form = empty
        test[List.from_iterable(range(3)) == List(0, 1, 2)]

        # fmap / bind / join
        test[List(1, 2, 3).fmap(lambda x: x * 10) == List(10, 20, 30)]
        test[(List(1, 2, 3) >> (lambda x: List(x, x * 10))) == List(1, 10, 2, 20, 3, 30)]
        test[List(List(1, 2), List(3)).join() == List(1, 2, 3)]

        # guard / filter
        filtered = List(1, 2, 3, 4) >> (lambda x:
                   List.guard(x % 2 == 0).then(List(x)))
        test[filtered == List(2, 4)]

        # Pythagorean triples (the canonical List-monad example)
        def r(low, high):
            return List.from_iterable(range(low, high))
        pt = r(1, 21) >> (lambda z:
             r(1, z + 1) >> (lambda x:
             r(x, z + 1) >> (lambda y:
             List.guard(x * x + y * y == z * z).then(
             List((x, y, z))))))
        test[tuple(sorted(pt)) == ((3, 4, 5), (5, 12, 13), (6, 8, 10),
                                   (8, 15, 17), (9, 12, 15), (12, 16, 20))]

        # Sequence protocol
        from collections.abc import Sequence
        test[isinstance(List(1, 2, 3), Sequence)]
        test[List(1, 2, 3)[1] == 2]
        test[2 in List(1, 2, 3)]
        test[List(1, 2, 3) + List(4, 5) == List(1, 2, 3, 4, 5)]

        # lift
        test[List.lift(lambda x: x + 1)(5) == List(6)]

    with testset("Writer"):
        # Basic chain with log accumulation
        result = (Writer(10)
                  >> (lambda x: Writer(x + 1, "added 1; "))
                  >> (lambda y: Writer(y * 2, "doubled; ")))
        test[result.data == (22, "added 1; doubled; ")]

        # fmap is transparent (doesn't add log)
        test[Writer(5, "start; ").fmap(lambda x: x * 10).data == (50, "start; ")]

        # join
        test[Writer(Writer(7, "inner"), "outer").join().data == (7, "outerinner")]
        test_raises[TypeError, Writer(5).join()]

        # tell
        tr = Writer(10, "step1; ").then(Writer.tell("step2; "))
        test[tr.data == (None, "step1; step2; ")]

        # lift (doesn't auto-log)
        test[Writer.lift(lambda x: x + 1)(5).data == (6, "")]

    with testset("State"):
        bump = State(lambda s: (s, s + 1))

        # Basic chain
        chain = (bump
                 >> (lambda a: bump
                 >> (lambda b: bump
                 >> (lambda c: State.unit((a, b, c))))))
        data, final = chain.run(10)
        test[data == (10, 11, 12)]
        test[final == 13]

        # eval / exec
        test[chain.eval(10) == (10, 11, 12)]
        test[chain.exec(10) == 13]

        # get / put / modify / gets
        test[State.get().run(42) == (42, 42)]
        test[State.put(99).run(5) == (None, 99)]
        test[State.modify(lambda s: s * 2).run(7) == (None, 14)]
        test[State.gets(lambda s: s + 1).run(10) == (11, 10)]

        # fmap
        test[State.unit(5).fmap(lambda x: x * 10).run("anything") == (50, "anything")]

        # join (the plain-words-derivation case)
        def inner(s):
            return (s * 10, s + 1)
        def outer(s):
            return (State(inner), s + 100)
        nested = State(outer)
        # outer(0) -> (inner_state, 100); inner(100) -> (1000, 101)
        test[nested.join().run(0) == (1000, 101)]

        # join rejects non-nested
        test_raises[TypeError, State.unit(5).join().run(0)]

        # State does NOT have lift
        test[not hasattr(State, "lift") or State.lift is not LiftableMonad.__dict__.get("lift")]

        # Constructor rejects non-callables
        test_raises[TypeError, State(42)]

    with testset("Reader"):
        config = {"multiplier": 3, "offset": 10}

        chain = (Reader.asks(lambda e: e["multiplier"])
                 >> (lambda m: Reader.asks(lambda e: e["offset"])
                 >> (lambda o: Reader.unit(m * 5 + o))))
        test[chain.run(config) == 25]

        # ask / asks / unit
        test[Reader.ask().run("env") == "env"]
        test[Reader.asks(lambda e: e.upper()).run("hello") == "HELLO"]
        test[Reader.unit(42).run("ignored") == 42]

        # local: modify the environment for a sub-computation
        test[Reader.ask().local(lambda e: e * 2).run(5) == 10]

        # fmap / join
        test[Reader.unit(5).fmap(lambda x: x * 10).run(None) == 50]
        nested = Reader(lambda e: Reader(lambda e2: e + e2))
        test[nested.join().run(3) == 6]

        # Reader does NOT have lift
        test[not hasattr(Reader, "lift") or Reader.lift is not LiftableMonad.__dict__.get("lift")]

        # Constructor rejects non-callables
        test_raises[TypeError, Reader(42)]


if __name__ == '__main__':  # pragma: no cover
    with session(__file__):
        runtests()
