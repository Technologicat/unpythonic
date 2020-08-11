# -*- coding: utf-8 -*-

from ..amb import forall, choice, insist, deny, ok, fail

def runtests():
    out = forall(choice(x=range(5)),
                 lambda e: e.x)
    assert out == tuple(range(5))

    # Because this is based on the List monad, a line that returns N items
    # causes the lines below it to be evaluated N times (once for each value).
    #
    # Note this happens even if the output is not assigned to a variable!
    #
    out = forall(range(2),  # do the rest twice
                 choice(x=range(1, 4)),
                 lambda e: e.x)
    assert out == (1, 2, 3, 1, 2, 3)

    # simple filtering
    out = forall(choice(y=range(3)),
                 choice(x=range(3)),
                 lambda e: (fail if e.x % 2 == 0 else ok),
                 lambda e: (e.x, e.y))
    assert out == ((1, 0), (1, 1), (1, 2))

    # same as:
    out = forall(choice(y=range(3)),
                 choice(x=range(3)),
                 lambda e: deny(e.x % 2 == 0),   # <-- here
                 lambda e: (e.x, e.y))
    assert out == ((1, 0), (1, 1), (1, 2))

    # the opposite of:
    out = forall(choice(y=range(3)),
                 choice(x=range(3)),
                 lambda e: insist(e.x % 2 == 0),  # <-- here
                 lambda e: (e.x, e.y))
    assert out == ((0, 0), (2, 0), (0, 1), (2, 1), (0, 2), (2, 2))

    # capture the "ok" flag
    out = forall(choice(y=range(3)),
                 choice(x=range(3)),
                 choice(z=lambda e: (fail if e.x % 2 == 0 else ok)),
                 lambda e: (e.x, e.y, e.z))
    assert out == ((1, 0, 'ok'), (1, 1, 'ok'), (1, 2, 'ok'))

    # pythagorean triples
    pt = forall(choice(z=range(1, 21)),                 # hypotenuse
                choice(x=lambda e: range(1, e.z + 1)),    # shorter leg
                choice(y=lambda e: range(e.x, e.z + 1)),  # longer leg
                lambda e: insist(e.x * e.x + e.y * e.y == e.z * e.z),
                lambda e: (e.x, e.y, e.z))
    assert tuple(sorted(pt)) == ((3, 4, 5), (5, 12, 13), (6, 8, 10),
                                 (8, 15, 17), (9, 12, 15), (12, 16, 20))

    print("All tests PASSED")

if __name__ == '__main__':
    runtests()
