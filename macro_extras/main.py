#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Macro extras. Main program.

Uses MacroPy; must be run through the bootstrap script run.py,
since macro expansion occurs at import time.
"""

from autocurry import macros, curry
from letm import macros, let, letseq
from unpythonic import foldr, composerc as compose, cons, nil

with curry:
    mymap = lambda f: foldr(compose(cons, f), nil)
    double = lambda x: 2 * x
    print(mymap(double, (1, 2, 3)))

    def add3(a, b, c):
        return a + b + c
    print(add3(1)(2)(3))
    print(add3(1, 2)(3))
    print(add3(1)(2, 3))
    print(add3(1, 2, 3))

    # NOTE: because builtins cannot be inspected, curry just no-ops on them.
    # So this won't work:
    from operator import add
    try:
        f = add(1)
        print(f(2))
    except TypeError:
        pass
    # In cases like this, make a wrapper:
    myadd = lambda a, b: add(a, b)
    f = myadd(1)
    print(f(2))

# outside the with block, autocurry is not active, so this is an error:
try:
    add3(1)
except TypeError:
    pass

# Let macros, performing essentially the same transformation as Scheme/Racket.
#
let((x, 17),  # parallel binding, i.e. bindings don't see each other
    (y, 23))[print(x, y)]
letseq((x, 1),  # sequential binding, using Python's lexical scoping
       (y, x+1))[print(x, y)]  # Scheme/Racket let*
