# -*- coding: utf-8 -*-

from ..syntax import macros, test, test_raises  # noqa: F401
from .fixtures import session, testset

from ..amb import (forall, choice, insist, deny, ok, fail,
                   Assignment, MonadicList, nil)

def runtests():
    with testset("MonadicList (internal utility)"):
        m = MonadicList(1, 2, 3)
        test[tuple(m) == (1, 2, 3)]
        test[len(m) == 3]
        test[m[0] == 1 and m[1] == 2 and m[2] == 3]

        m = MonadicList(nil)  # special *item* that produces an empty *list*
        test[tuple(m) == ()]

        # Monadic bind (for MonadicList, it's flatmap).
        # This also tests fmap and join.
        m = MonadicList(1, 2, 3)
        f = lambda a: MonadicList(a, 10 * a)  # a -> M b
        test[tuple(m >> f) == (1, 10, 2, 20, 3, 30)]

        # .then(...): discard current value, replace by given value.
        # The new value must be wrapped in MonadicList.
        m = MonadicList(1, 2, 3)
        const = MonadicList(42)  # M b
        test[tuple(m.then(const)) == (42, 42, 42)]  # one 42 for each element of m

        test_raises[TypeError, m.then(f)]  # expected a MonadicList, got a function

        m1 = MonadicList(1, 2)
        m2 = MonadicList(3, 4, 5)
        test[m1 == m1]
        test[m2 != m1]

        m1 = MonadicList(1, 2)
        m2 = MonadicList(3, 4)
        test[m1 + m2 == MonadicList(1, 2, 3, 4)]

        m1 = MonadicList(1, 2)
        notamonadiclist = (3, 4)
        test_raises[TypeError, m1 + notamonadiclist]

        test[MonadicList.from_iterable(range(3)) == MonadicList(0, 1, 2)]

        m1 = MonadicList(1, 2, 3)
        m2 = m1.copy()
        test[m2 is not m1 and m2 == m1]

        double = lambda x: 2 * x
        m = MonadicList(1, 2, 3)
        test[tuple(m >> MonadicList.lift(double)) == (2, 4, 6)]

        m = MonadicList(1, 2, 3)
        test_raises[TypeError, m.join()]  # join() flattens a nested list, which m isn't

        # Usage example for `guard`
        m = MonadicList(1, 2, 3)
        test[tuple(m >> (lambda x: MonadicList.guard(x % 2 == 1)
                                              .then(MonadicList(x)))) == (1, 3)]

    with testset("basic usage"):
        test[forall(choice(x=range(5)),
                    lambda e: e.x) == tuple(range(5))]

        # a single choice is silly but allowed
        test[forall(choice(x=42),
                    lambda e: e.x) == (42,)]

        # Because this is based on the List monad, a line that returns N items
        # causes the lines below it to be evaluated N times (once for each value).
        #
        # Note this happens even if the output is not assigned to a variable!
        #
        test[forall(range(2),  # do the rest twice
                    choice(x=range(1, 4)),
                    lambda e: e.x) == (1, 2, 3, 1, 2, 3)]

        # simple filtering
        test[forall(choice(y=range(3)),
                    choice(x=range(3)),
                    lambda e: (fail if e.x % 2 == 0 else ok),
                    lambda e: (e.x, e.y)) == ((1, 0), (1, 1), (1, 2))]

        # same as:
        test[forall(choice(y=range(3)),
                    choice(x=range(3)),
                    lambda e: deny(e.x % 2 == 0),   # <-- here
                    lambda e: (e.x, e.y)) == ((1, 0), (1, 1), (1, 2))]

        # the opposite of:
        test[forall(choice(y=range(3)),
                    choice(x=range(3)),
                    lambda e: insist(e.x % 2 == 0),  # <-- here
                    lambda e: (e.x, e.y)) == ((0, 0), (2, 0), (0, 1), (2, 1), (0, 2), (2, 2))]

        # capture the "ok" flag
        test[forall(choice(y=range(3)),
                    choice(x=range(3)),
                    choice(z=lambda e: (fail if e.x % 2 == 0 else ok)),
                    lambda e: (e.x, e.y, e.z)) == ((1, 0, 'ok'), (1, 1, 'ok'), (1, 2, 'ok'))]

        # pythagorean triples
        pt = lambda: forall(choice(z=range(1, 21)),                 # hypotenuse
                            choice(x=lambda e: range(1, e.z + 1)),    # shorter leg
                            choice(y=lambda e: range(e.x, e.z + 1)),  # longer leg
                            lambda e: insist(e.x * e.x + e.y * e.y == e.z * e.z),
                            lambda e: (e.x, e.y, e.z))
        test[tuple(sorted(pt())) == ((3, 4, 5), (5, 12, 13), (6, 8, 10),
                                     (8, 15, 17), (9, 12, 15), (12, 16, 20))]

    with testset("error cases"):
        test_raises[ValueError, choice(a=1, b=2)]  # choice() takes only one binding

        # To trigger this corner case, we must manually create an `Assignment`
        # that has an invalid name - in normal use, `choice()` protects against
        # that by its syntax, since the name of a kwarg must be a valid identifier.
        invalid_name = "∀δ>0∃ε>0:f(x+δ)-f(x)<ε"
        test_raises[ValueError, forall(Assignment(invalid_name, 42))]

        test_raises[TypeError, forall(lambda: 42)]  # callable body must be able to take in the environment

if __name__ == '__main__':  # pragma: no cover
    with session(__file__):
        runtests()
