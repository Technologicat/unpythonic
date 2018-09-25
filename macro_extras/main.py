#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Macro extras. Main program.

Uses MacroPy; must be run through the bootstrap script run.py,
since macro expansion occurs at import time.
"""

from autocurry import macros, curry
from letm import macros, let, letseq, letrec
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
# Lexical scoping supported.
#
let((x, 17),  # parallel binding, i.e. bindings don't see each other
    (y, 23))[
      print(x, y)]

letseq((x, 1),  # sequential binding, i.e. Scheme/Racket let*
       (y, x+1))[
         print(x, y)]

try:
    let((x, 1),
        (y, x+1))[  # parallel binding, doesn't see the x in the same let
          print(x, y)]
except NameError:
    pass  # no x in surrounding scope

try:
    letseq((x, y+1),
           (y, 2))[
             print(x, y)]
except NameError:  # y is not yet defined on the first line
    pass

# letrec sugars unpythonic.lispylet.letrec, removing the need for quotes
# and "lambda e: ..." wrappers (these are inserted by the macro):
letrec((evenp, lambda x: (x == 0) or oddp(x - 1)),
       (oddp,  lambda x: (x != 0) and evenp(x - 1)))[
         print(evenp(42))]

# nested letrecs work, too - each environment is internally named by a gensym
# so that outer ones can be seen:
letrec((z, 9000))[
  letrec((evenp, lambda x: (x == 0) or oddp(x - 1)),
         (oddp,  lambda x: (x != 0) and evenp(x - 1)))[
           print(evenp(42), z)]]

# also letrec supports lexical scoping, since in MacroPy 1.1.0 and later,
# macros are expanded from inside out (the z in the inner scope expands to
# the inner environment's z, which makes the outer expansion leave it alone):
from unpythonic import begin
letrec((z, 1))[
  begin(print(z),
        letrec((z, 2))[
          print(z)])]  # (be careful with the parentheses!)

# this works, too
letrec((x, 1),
       (y, x+2))[
  print(y)]

# but this is an error (just like in Racket):
try:
    letrec((x, y+1),
           (y, 2))[
      print(x)]
except AttributeError:  # y is not defined on the first line (lispylet and env together detect this)
    pass

# this is ok, because the y on the RHS of the definition of f
# is evaluated only when the function is called
letrec((f, lambda t: t + y + 1),
       (y, 2))[
  print(f(3))]
