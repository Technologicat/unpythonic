# -*- coding: utf-8 -*-
"""Tuple comprehension with multiple-expression body."""

from ...syntax import macros, test  # noqa: F401
from ...test.fixtures import session, testset

# There's also `deny`, which is `insist not`, but let's not import stuff we don't use.
from ...syntax import macros, forall  # noqa: F401, F811
from ...syntax import insist  # not a macro

def runtests():
    # forall: pure AST transformation, with real lexical variables
    #   - assignment (with List-monadic magic) is ``var << iterable``
    with testset("basic usage"):
        out = forall[y << range(3),  # noqa: F821, `forall` defines the name on the LHS of the `<<`.
                     x << range(3),  # noqa: F821
                     insist(x % 2 == 0),  # noqa: F821
                     (x, y)]  # noqa: F821
        # Like Haskell's do-notation, this should transform to:
        #   out = (range(3) >>
        #          (lambda y: range(3) >>              # this lambda is named forall_y
        #           (lambda x: insist(x % 2 == 0) >>   # this lambda is named forall_x
        #            (lambda _ignored: (x, y)))))      # this lambda is named forall_item2 (since no assignment)
        # where `>>` is the monadic bind operator.
        test[out == ((0, 0), (2, 0), (0, 1), (2, 1), (0, 2), (2, 2))]

    with testset("pythagorean triples"):
        pt = forall[z << range(1, 21),   # hypotenuse  # noqa: F821
                    x << range(1, z + 1),  # shorter leg  # noqa: F821
                    y << range(x, z + 1),  # longer leg  # noqa: F821
                    insist(x * x + y * y == z * z),  # noqa: F821
                    (x, y, z)]  # noqa: F821
        test[tuple(sorted(pt)) == ((3, 4, 5), (5, 12, 13), (6, 8, 10),
                                   (8, 15, 17), (9, 12, 15), (12, 16, 20))]

    with testset("single item special case"):
        test[forall[range(3), ] == (range(3),)]

if __name__ == '__main__':  # pragma: no cover
    with session(__file__):
        runtests()
