#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Unpythonic constructs that change the rules.

Tour of the features.
"""

from unpythonic import assignonce, \
                       dyn,        \
                       let, letrec, dlet, dletrec, blet, bletrec, \
                       immediate, begin, begin0, lazy_begin, lazy_begin0

def dynscope_demo():
    assert dyn.a == 2

def main():
    # assign-once environment
    #
    with assignonce() as e:
        e.foo = "bar"           # new definition, ok
        e.set("foo", "tavern")  # explicitly rebind e.foo, ok
        e << ("foo", "tavern")  # same thing (but returns e instead of new value)

        try:
            e.foo = "quux"      # AttributeError, e.foo already defined.
        except AttributeError:
            pass

    # dynamic scoping
    #
    with dyn.let(a=2, b="foo"):
        assert dyn.a == 2

        dynscope_demo()  # defined outside the lexical scope of main()!

        with dyn.let(a=3):
            assert dyn.a == 3

        assert dyn.a == 2

    try:
        print(dyn.b)  # AttributeError, dyn.b no longer exists
    except AttributeError:
        pass

    # let, letrec
    #
    u = lambda lst: let(seen=set(),
                        body=lambda e: [e.seen.add(x) or x for x in lst if x not in e.seen])
    L = [1, 1, 3, 1, 3, 2, 3, 2, 2, 2, 4, 4, 1, 2, 3]
    assert u(L) == [1, 3, 2, 4]

    t = letrec(evenp=lambda e: lambda x: (x == 0) or e.oddp(x - 1),
               oddp=lambda e: lambda x: (x != 0) and e.evenp(x - 1),
               body=lambda e: e.evenp(42))
    assert t is True

    u2 = lambda lst: letrec(seen=lambda e: set(),
                            see=lambda e: lambda x: begin(e.seen.add(x), x),
                            body=lambda e: [e.see(x) for x in lst if x not in e.seen])
    assert u2(L) == [1, 3, 2, 4]

    # let-over-lambda
    counter = let(x=0,
              body=lambda e: lambda: begin(e << ("x", e.x + 1),
                                           e.x))
    counter()  # --> 1
    counter()  # --> 2
    assert(counter() == 3)

    # let-over-def
    @dlet(count=0)
    def counter2(*, env=None):  # env: named argument containing the let bindings
        env.count += 1
        return env.count
    counter2()
    counter2()
    assert(counter2() == 3)

    # code block with let
    @blet(x=5)
    def result(*, env):  # runs immediately (see also @immediate))
        return 2 * env.x
    assert result == 10

    # letrec-over-def
    @dletrec(evenp=lambda e: lambda x: (x == 0) or e.oddp(x - 1),
             oddp=lambda e: lambda x: (x != 0) and e.evenp(x - 1))
    def is_even(x, *, env):
        return env.evenp(x)
    assert is_even(23) is False

    # code block with letrec
    @bletrec(evenp=lambda e: lambda x: (x == 0) or e.oddp(x - 1),
             oddp=lambda e: lambda x: (x != 0) and e.evenp(x - 1))
    def result(*, env):
        return env.evenp(23)
    assert result is False

    # def as a code block (function overwritten by return value)
    #
    @immediate
    def result():
        return "hello"
    assert result == "hello"

    # use case 1: make temporaries fall out of scope
    @immediate
    def x():
        a = 2  #    many temporaries that help readability...
        b = 3  # ...of this calculation, but would just pollute locals...
        c = 5  # ...after the block exits
        return a * b * c
    assert x == 30

    # use case 2: multi-break out of nested loops
    @immediate
    def result():
        for x in range(10):
            for y in range(10):
                if x * y == 42:
                    return (x, y)
                ... # more code here
    assert result == (6, 7)

    # multiple expressions in a lambda
    #
    f1 = lambda x: begin(print("cheeky side effect"), 42*x)
    assert f1(2) == 84

    f2 = lambda x: begin0(42*x, print("cheeky side effect"))
    assert f2(2) == 84

    f3 = lambda x: lazy_begin(lambda: print("cheeky side effect"),
                              lambda: 42*x)
    assert f3(2) == 84

    f4 = lambda x: lazy_begin0(lambda: 42*x,
                               lambda: print("cheeky side effect"))
    assert f4(2) == 84


if __name__ == '__main__':
    main()
