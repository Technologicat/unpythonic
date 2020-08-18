# -*- coding: utf-8 -*-
"""Tuple comprehension with multiple-expression body."""

from ...syntax import macros, test  # noqa: F401
from ...test.fixtures import testset

# There's also `deny`, which is `insist not`, but let's not import stuff we don't use.
from ...syntax import macros, forall, insist  # noqa: F401, F811

def runtests():
    with testset("unpythonic.syntax.forall"):
        # forall: pure AST transformation, with real lexical variables
        #   - assignment (with List-monadic magic) is ``var << iterable``
        out = forall[y << range(3),  # noqa: F821, `forall` defines the name on the LHS of the `<<`.
                     x << range(3),  # noqa: F821
                     insist(x % 2 == 0),  # noqa: F821
                     (x, y)]  # noqa: F821
        test[out == ((0, 0), (2, 0), (0, 1), (2, 1), (0, 2), (2, 2))]

        # pythagorean triples
        pt = forall[z << range(1, 21),   # hypotenuse  # noqa: F821
                    x << range(1, z + 1),  # shorter leg  # noqa: F821
                    y << range(x, z + 1),  # longer leg  # noqa: F821
                    insist(x * x + y * y == z * z),  # noqa: F821
                    (x, y, z)]  # noqa: F821
        test[tuple(sorted(pt)) == ((3, 4, 5), (5, 12, 13), (6, 8, 10),
                                   (8, 15, 17), (9, 12, 15), (12, 16, 20))]

if __name__ == '__main__':
    runtests()
