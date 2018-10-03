#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Macro extras. Main program.

Uses MacroPy; must be run through the bootstrap script run.py,
since macro expansion occurs at import time.
"""

from unpythonic.syntax import macros, curry, \
                              let, letseq, letrec, do, do0, forall, \
                              simple_let, simple_letseq, \
                              aif, cond, \
                              prefix, q, u, kw, \
                              λ
from unpythonic import insist, deny  # for forall

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

        # give named args with kw(...) [it's syntax, not really a function!]:
        def f(*, a, b):
            (print, a, b)
        (f, kw(a="hi there", b="foo"))
        (f, kw(a="hi there"), kw(b="foo"))
        (f, kw(a="hi there"), kw(b="foo"), kw(b="bar"))

    # Introducing LisThEll:
    with prefix, curry:  # important: apply prefix first, then curry
        mymap = lambda f: (foldr, (compose, cons, f), nil)
        double = lambda x: 2 * x
        (print, (mymap, double, (q, 1, 2, 3)))

    # Let macros. Lexical scoping supported.
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

    try:
        let((x, 1), (x, 2))[  # error, cannot rebind the same name
              print(x)]
    except AttributeError:
        pass

#    simple_let((x, 1), (x, 2))[  # error, cannot rebind the same name
#          print(x)]

    letseq((x, 1), (x, x+1))[  # but in a letseq it's ok
          print(x)]

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

    # let over lambda
    count = let((x, 0))[
              lambda: begin(x << x + 1,
                            "count is {}".format(x))]
    print(count())
    print(count())

    # multilambda: lambda with implicit begin. Usage:
    #   λ(arg0, ...)[body0, ...]
    # Limitations:
    #  - no default values for arguments
    #  - no *args, **kwargs
    count = let((x, 0))[
              λ()[x << x + 1,
                  "count is {}".format(x)]]
    print(count())
    print(count())

    echo = λ(x)[print(x), x]
    z = echo("hi there")
    assert z == "hi there"

    myadd = λ(x, y)[print(x, y), x + y]
    assert myadd(2, 3) == 5

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
    #  - Assignment is ``var << value``.
    #    Transforms to ``begin(setattr(e, var, value), value)``,
    #    so is valid from any level inside the ``do`` (including nested
    #    ``let`` constructs and similar).
    #  - Variables that are bound in a ``do`` are defined as those ``x`` that
    #    have at least one assignment ``x << value`` anywhere inside the ``do``.
    #    These are collected when the macro transformation of the ``do`` starts.
    #  - Note that if a nested binding macro such as a ``let`` also binds an
    #    ``x``, the inner macro will bind first, so the ``do`` environment
    #    will then **not** bind ``x``, as it already belongs to the ``let``.
    #  - No need for ``lambda e: ...`` wrappers, inserted automatically,
    #    so the lines are only evaluated as the seq.do() runs.
    y = do[x << 17,
           print(x),
           x << 23,
           x]
    print(y)

    y2 = do0[y << 5,  # y << val assigns, then returns val
             print("hi there, y =", y),
             42]  # evaluated but not used, do0 returns the first value
    assert(y2 == 5)

    # macro wrapper for amb.forall
    #   - assignment (with List-monadic magic) is ``var << iterable``
    #   - no need for ``lambda e: ...`` wrappers.
    out = forall[y << range(3),  # y << ... --> choice(y=lambda e: ...)
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

if __name__ == '__main__':
    main()
