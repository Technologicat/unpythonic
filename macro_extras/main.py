#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Macro extras. Main program.

Uses MacroPy; must be run through the bootstrap script run.py,
since macro expansion occurs at import time.
"""

from autocurry import macros, curry
from letm import macros, let, letseq, letrec, do
from aif import macros, aif
from cond import macros, cond
from prefix import macros, prefix
from unpythonic import foldr, composerc as compose, cons, nil

def main():
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

    # Write Python almost like Lisp!
    with prefix:
        (print, "hello world")
        x = 42  # can write any regular Python, too
        # quote operator q locally turns off the function-call transformation:
        t1 = (q, 1, 2, (3, 4), 5)  # q takes effect recursively
        t2 = (q, 17, 23, x)  # unlike in Lisps, x refers to its value even in a quote
        (print, t1, t2)
        # unquote operator u locally turns the transformation back on:
        t3 = (q, (u, print, 42), (print, 42), "foo", "bar")
        (print, t3)
        # quotes nest; call transformation made when quote level == 0
        t4 = (q, (print, 42), (q, (u, u, print, 42)), "foo", "bar")
        (print, t4)
        # Be careful:
        try:
            (x,)  # in a prefix block, this means "call the 0-arg function x"
        except TypeError:
            pass  # 'int' object is not callable
        (q, x)  # OK!

    # Introducing LisThEll:
    with prefix, curry:  # important: apply prefix first, then curry
        mymap = lambda f: (foldr, (compose, cons, f), nil)
        double = lambda x: 2 * x
        (print, (mymap, double, (q, 1, 2, 3)))

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

    # assignment updates the innermost value by that name:
    letrec((z, 1))[
      begin(print("outer z is", z),
            print("changing outer z to", z << 5),  # assignment to env is an expression, returns the new value
            letrec((z, 2))[
              begin(print("inner z is", z),
                    print("changing inner z to", z << 7))],
            print("outer z is still", z))]
    letrec((x, 1))[
      begin(print("x is", x),
            letrec((z, 2))[
              begin(print("z is", z),
                    print("changing x to", x << 7))],
            print("x is now", x))]

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

    a = letrec((x, 1),
               (y, x+2))[
                 begin(x << 1337,
                       (x, y))]
    print(a)

    a = let((x, 1),
            (y, 2))[
              begin(y << 1337,
                    (x, y))]
    print(a)

    a = letseq((x, 1),
               (y, x+1))[
                 begin(x << 1337,
                       (x, y))]
    print(a)

    # Anaphoric if: aif[test, then, otherwise]
    # Magic identifier "it" refers to the test result.
    aif[2*21,
        print("it is {}".format(it)),
        print("it is False")]

    # Lispy "cond" - a human-readable multi-branch conditional for lambdas.
    answer = lambda x: cond[x == 2, "two",
                            x == 3, "three",
                            "something else"]
    print(answer(42))

    # macro wrapper for seq.do (stuff imperative code into a lambda)
    #  - assignment is ``var << value``
    #  - no need for ``lambda e: ...`` wrappers, inserted automatically,
    #    so the lines are only evaluated as the seq.do() runs
    y = do[x << 17,
           print(x),
           x << 23,
           x]
    print(y)

if __name__ == '__main__':
    main()
