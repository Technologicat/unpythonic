#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Macro extras. Main program.

Uses MacroPy; must be run through the bootstrap script run.py,
since macro expansion occurs at import time.
"""

from unpythonic.syntax import macros, \
                              curry, \
                              simple_let, simple_letseq, \
                              let, letseq, letrec, \
                              do, do0, \
                              forall, insist, deny, \
                              aif, it, \
                              cond, \
                              prefix, q, u, kw, \
                              λ

from unpythonic import foldr, composerc as compose, cons, nil, ll, apply

def main():
    with curry:
        mymap = lambda f: foldr(compose(cons, f), nil)
        double = lambda x: 2 * x
        assert mymap(double, (1, 2, 3)) == ll(2, 4, 6)

        def add3(a, b, c):
            return a + b + c
        assert add3(1)(2)(3) == 6
        assert add3(1, 2)(3) == 6
        assert add3(1)(2, 3) == 6
        assert add3(1, 2, 3) == 6

        # NOTE: because builtins cannot be inspected, curry just no-ops on them.
        # So this won't work:
        from operator import add
        try:
            f = add(1)
            assert f(2) == 3
        except TypeError:
            pass
        else:
            assert False, "update documentation"
        # In cases like this, make a wrapper:
        myadd = lambda a, b: add(a, b)
        f = myadd(1)
        assert f(2) == 3

    # outside the with block, autocurry is not active, so this is an error:
    try:
        add3(1)
    except TypeError:
        pass
    else:
        assert False

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
        assert t3 == (q, None, (print, 42), "foo", "bar")

        # quotes nest; call transformation made when quote level == 0
        t4 = (q, (print, 42), (q, (u, u, print, 42)), "foo", "bar")
        assert t4 == (q, (print, 42), (None,), "foo", "bar")

        # Be careful:
        try:
            (x,)  # in a prefix block, this means "call the 0-arg function x"
        except TypeError:
            pass  # 'int' object is not callable
        else:
            assert False, "should have attempted to call x"
        (q, x)  # OK!

        # give named args with kw(...) [it's syntax, not really a function!]:
        def f(*, a, b):
            return (q, a, b)
        # in one kw(...), or...
        assert (f, kw(a="hi there", b="foo")) == (q, "hi there", "foo")
        # in several kw(...), doesn't matter
        assert (f, kw(a="hi there"), kw(b="foo")) == (q, "hi there", "foo")
        # in case of duplicate name across kws, rightmost wins
        assert (f, kw(a="hi there"), kw(b="foo"), kw(b="bar")) == (q, "hi there", "bar")

        # give *args with unpythonic.fun.apply, like in Lisps:
        lst = [1, 2, 3]
        def g(*args):
            return args
        assert (apply, g, lst) == (q, 1, 2, 3)
        # lst goes last; may have other args first
        assert (apply, g, "hi", "ho", lst) == (q, "hi" ,"ho", 1, 2, 3)

    # Introducing LisThEll:
    with prefix, curry:  # important: apply prefix first, then curry
        mymap = lambda f: (foldr, (compose, cons, f), nil)
        double = lambda x: 2 * x
        (print, (mymap, double, (q, 1, 2, 3)))
        assert (mymap, double, (q, 1, 2, 3)) == ll(2, 4, 6)

    # Let macros. Lexical scoping supported.
    #
    assert let((x, 17),  # parallel binding, i.e. bindings don't see each other
               (y, 23))[
                 (x, y)] == (17, 23)

    assert letseq((x, 1),  # sequential binding, i.e. Scheme/Racket let*
                  (y, x+1))[
                    (x, y)] == (1, 2)

    try:
        let((X, 1),
            (y, X+1))[  # parallel binding, doesn't see the x in the same let
              print(X, y)]
    except NameError:
        pass  # no X in surrounding scope
    else:
        assert False, "should not see the X in the same let"

    try:
        letseq((X, y+1),
               (y, 2))[
                 (X, y)]
    except NameError:  # y is not yet defined on the first line
        pass
    else:
        assert False, "y should not yet be defined on the first line"

    try:
        let((x, 1),
            (x, 2))[  # error, cannot rebind the same name
              print(x)]
    except AttributeError:
        pass
    else:
        assert False, "should not be able to rebind the same name x in the same let"

#    # this will SyntaxError (correctly)
#    simple_let((x, 1), (x, 2))[  # error, cannot rebind the same name
#          print(x)]

    assert letseq((x, 1),
                  (x, x+1))[  # but in a letseq it's ok
                    x] == 2

    # letrec sugars unpythonic.lispylet.letrec, removing the need for quotes
    # and "lambda e: ..." wrappers (these are inserted by the macro):
    assert letrec((evenp, lambda x: (x == 0) or oddp(x - 1)),
                  (oddp,  lambda x: (x != 0) and evenp(x - 1)))[
                    evenp(42)] is True

    # nested letrecs work, too - each environment is internally named by a gensym
    # so that outer ones "show through":
    assert letrec((z, 9000))[
             letrec((evenp, lambda x: (x == 0) or oddp(x - 1)),
                    (oddp,  lambda x: (x != 0) and evenp(x - 1)))[
                      (evenp(42), z)]] == (True, 9000)

    # also letrec supports lexical scoping, since in MacroPy 1.1.0 and later,
    # macros are expanded from inside out (the z in the inner scope expands to
    # the inner environment's z, which makes the outer expansion leave it alone):
    from unpythonic import begin
    out = []
    letrec((z, 1))[
      begin(out.append(z),
            letrec((z, 2))[
              out.append(z)])]  # (be careful with the parentheses!)
    assert out == [1, 2]

    # assignment updates the innermost value by that name:
    out = []
    letrec((z, 1))[
      begin(out.append(z), # outer z
            # assignment to env is an expression, returns the new value
            out.append(z << 5),
            letrec((z, 2))[
              begin(out.append(z), # inner z
                    out.append(z << 7))],
            out.append(z))]  # outer z
    assert out == [1, 5, 2, 7, 5]

    out = []
    letrec((x, 1))[
      begin(out.append(x),
            letrec((z, 2))[
              begin(out.append(z),
                    out.append(x << 7))],  # x only defined in outer letrec, updates that
            out.append(x))]
    assert out == [1, 2, 7, 7]

    # this works, too
    assert letrec((x, 1),
                  (y, x+2))[
                    (x, y)] == (1, 3)

    # but this is an error (just like in Racket):
    try:
        letrec((x, y+1),
               (y, 2))[
          print(x)]
    except AttributeError:  # y is not defined on the first line (lispylet and env together detect this)
        pass
    else:
        assert False, "y should not be yet defined on the first line"

    # this is ok, because the y on the RHS of the definition of f
    # is evaluated only when the function is called
    assert letrec((f, lambda t: t + y + 1),
                  (y, 2))[
                    f(3)] == 6

    a = letrec((x, 1),
               (y, x+2))[  # y computed now
                 begin(x << 1337,  # x updated now, no effect on y
                       (x, y))]
    assert a == (1337, 3)

    a = let((x, 1),
            (y, 2))[
              begin(y << 1337,
                    (x, y))]
    assert a == (1, 1337)

    a = letseq((x, 1),
               (y, x+1))[
                 begin(x << 1337,
                       (x, y))]
    assert a == (1337, 2)

    # let over lambda
    count = let((x, 0))[
              lambda: x << x + 1]
    assert count() == 1
    assert count() == 2

    # multilambda: lambda with implicit begin. Usage:
    #   λ(arg0, ...)[body0, ...]
    # Limitations:
    #  - no default values for arguments
    #  - no *args, **kwargs
    count = let((x, 0))[
              λ()[x << x + 1,
                  x]]
    assert count() == 1
    assert count() == 2

    echo = λ(x)[print(x), x]
    z = echo("hi there")
    assert z == "hi there"

    myadd = λ(x, y)[print("myadding", x, y), x + y]
    assert myadd(2, 3) == 5

    # But this must be done manually. Having λ with implicit do (instead of begin)
    # would cause the problem that it is then impossible to assign to let variables
    # defined outside the λ, because the do then captures all assignments
    # (because macros are expanded from inside out).
    myadd = lambda x, y: do[print("myadding", x, y),
                            tmp << x + y,
                            print("result is", tmp),
                            tmp]
    assert myadd(2, 3) == 5

    # Anaphoric if: aif[test, then, otherwise]
    # Magic identifier "it" refers to the test result.
    assert aif[2*21,
               "it is {}".format(it),
               "it is False"] == "it is 42"

    # Lispy "cond" - a human-readable multi-branch conditional for lambdas.
    answer = lambda x: cond[x == 2, "two",
                            x == 3, "three",
                            "something else"]
    assert answer(42) == "something else"

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
    assert y == 23

    y2 = do0[y << 5,  # y << val assigns, then returns val
             print("hi there, y =", y),
             42]  # evaluated but not used, do0 returns the first value
    assert y2 == 5

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
