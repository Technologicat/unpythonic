# -*- coding: utf-8 -*-
"""Tuple comprehension with multiple-expression body."""

from ...syntax import macros, forall, insist, deny

def test():
    # forall: pure AST transformation, with real lexical variables
    #   - assignment (with List-monadic magic) is ``var << iterable``
    out = forall[y << range(3),
                 x << range(3),
                 insist(x % 2 == 0),
                 (x, y)]
    assert out == ((0, 0), (2, 0), (0, 1), (2, 1), (0, 2), (2, 2))

    # pythagorean triples
    pt = forall[z << range(1, 21),   # hypotenuse
                x << range(1, z+1),  # shorter leg
                y << range(x, z+1),  # longer leg
                insist(x*x + y*y == z*z),
                (x, y, z)]
    assert tuple(sorted(pt)) == ((3, 4, 5), (5, 12, 13), (6, 8, 10),
                                 (8, 15, 17), (9, 12, 15), (12, 16, 20))

    print("All tests PASSED")
