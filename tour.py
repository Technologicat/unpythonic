#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Lispy missing batteries for Python.

Tour of the features.
"""

from unpythonic import assignonce, \
                       dyn,        \
                       let, letrec, dlet, dletrec, blet, bletrec, \
                       call, begin, begin0, lazy_begin, lazy_begin0, \
                       trampolined, jump, looped, looped_over, SELF, \
                       setescape, escape, call_ec

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

    u2 = lambda lst: letrec(seen=set(),
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
    def result(*, env):  # runs immediately (see also @call))
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
    @call
    def result():
        return "hello"
    assert result == "hello"

    # use case 1: make temporaries fall out of scope
    @call
    def x():
        a = 2  #    many temporaries that help readability...
        b = 3  # ...of this calculation, but would just pollute locals...
        c = 5  # ...after the block exits
        return a * b * c
    assert x == 30

    # use case 2: multi-break out of nested loops
    @call
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

    # tail recursion with tail call optimization (TCO)
    @trampolined
    def fact(n, acc=1):
        if n == 0:
            return acc
        else:
            return jump(fact, n - 1, n * acc)
    assert fact(4) == 24

    # tail recursion in a lambda
    t = trampolined(lambda n, acc=1:
                        acc if n == 0 else jump(SELF, n - 1, n * acc))
    assert t(4) == 24

    # mutual recursion
    @trampolined
    def even(n):
        if n == 0:
            return True
        else:
            return jump(odd, n - 1)
    @trampolined
    def odd(n):
        if n == 0:
            return False
        else:
            return jump(even, n - 1)
    assert even(42) is True
    assert odd(4) is False
    assert even(10000) is True  # no crash

    # looping in FP style, with TCO

    @looped
    def s(loop, acc=0, i=0):
        if i == 10:
            return acc  # there's no "break"; loop terminates at the first normal return
        else:
            return loop(acc + i, i + 1)  # same as return jump(SELF, acc+i, i+1)
    assert s == 45

    # or explicitly (faster, no setup of magic parameter "loop" at each iteration)
    @trampolined
    def dowork(acc=0, i=0):
        if i == 10:
            return acc
        else:
            return jump(dowork, acc + i, i + 1)
    s = dowork()  # when using just @trampolined, must start the loop manually
    assert s == 45

    # FP looping with side effect
    out = []
    @looped
    def _(loop, i=0):
        if i < 3:
            out.append(i)
            return loop(i + 1)
        # the implicit "return None" terminates the loop.
    assert out == [0, 1, 2]

    # same without using side effects - use an accumulator parameter:
    @looped
    def out(loop, i=0, acc=[]):
        if i < 3:
            acc.append(i)
            return loop(i + 1)
        else:
            return acc
    assert out == [0, 1, 2]

    # there's no "continue"; package your own:
    @looped
    def s(loop, acc=0, i=0):
        cont = lambda newacc=acc: loop(newacc, i + 1)
        if i <= 4:
            return cont()
        elif i == 10:
            return acc
        else:
            return cont(acc + i)
    assert s == 35

    # Using iterators, we can also FP loop over a collection:
    def map_fp(function, iterable):
        it = iter(iterable)
        @looped
        def out(loop, acc=()):
            try:
                x = next(it)
                return loop(acc + (function(x),))
            except StopIteration:
                return acc
        return out
    assert map_fp(lambda x: 2*x, range(5)) == (0, 2, 4, 6, 8)

    # There's a prepackaged @looped_over to simplify the client code:
    def map_fp2(function, iterable):
        @looped_over(iterable, acc=())
        def out(loop, x, acc):  # body always takes at least these three parameters, in this order
            return loop(acc + (function(x),))  # first argument is the new value of acc
        return out
    assert map_fp2(lambda x: 2*x, range(5)) == (0, 2, 4, 6, 8)

    @looped_over(range(10), acc=0)
    def s(loop, x, acc):
        return loop(acc + x)
    assert s == 45

    # similarly
    def filter_fp(predicate, iterable):
        predicate = predicate or (lambda x: x)  # None -> truth value test
        @looped_over(iterable, acc=())
        def out(loop, x, acc):
            if predicate(x):
                return loop(acc + (x,))
            else:
                return loop(acc)
        return out
    assert filter_fp(lambda x: x % 2 == 0, range(10)) == (0, 2, 4, 6, 8)

    # similarly
    def reduce_fp(function, iterable, initial=None):  # foldl
        it = iter(iterable)
        if initial is None:
            try:
                initial = next(it)
            except StopIteration:
                return None  # empty iterable
        @looped_over(it, acc=initial)  # either all elements, or all but first
        def out(loop, x, acc):
            return loop(function(acc, x))
        return out
    add = lambda acc, elt: acc + elt
    assert reduce_fp(add, range(10), 0) == 45
    assert reduce_fp(add, [], 0) == 0
    assert reduce_fp(add, []) is None

    # nested FP loops over collections
    @looped_over(range(1, 4), acc=[])
    def outer_result(outer_loop, y, outer_acc):
        @looped_over(range(1, 3), acc=[])
        def inner_result(inner_loop, x, inner_acc):
            return inner_loop(inner_acc + [y*x])
        return outer_loop(outer_acc + [inner_result])
    assert outer_result == [[1, 2], [2, 4], [3, 6]]

    # this old chestnut:
    funcs = []
    for i in range(3):
        funcs.append(lambda x: i*x)  # always the same "i", which "for" just mutates
    assert [f(10) for f in funcs] == [20, 20, 20]  # not what we wanted!

    # with FP loop:
    @looped_over(range(3), acc=())
    def funcs(loop, i, acc):
        return loop(acc + ((lambda x: i*x),))  # new "i" each time, no mutation!
    assert [f(10) for f in funcs] == [0, 10, 20]  # yes!

    # FP loop, using the more primitive @looped:
    funcs = []
    @looped
    def _(loop, i=0):
        if i < 3:
            funcs.append(lambda x: i*x)  # new "i" each time, no mutation!
            return loop(i + 1)
    assert [f(10) for f in funcs] == [0, 10, 20]  # yes!

    # FP loop in a lambda, with TCO:
    s = looped(lambda loop, acc=0, i=0:
                 loop(acc + i, i + 1) if i < 10 else acc)
    assert s == 45

    # The same, using "let" to define a "cont":
    s = looped(lambda loop, acc=0, i=0:
                 let(cont=lambda newacc=acc:
                            loop(newacc, i + 1),
                     body=lambda e:
                            e.cont(acc + i) if i < 10 else acc))
    assert s == 45

    # We can also use such expressions locally, like "s" here:
    result = let(s=looped(lambda loop, acc=0, i=0:
                            let(cont=lambda newacc=acc:
                                       loop(newacc, i + 1),
                                body=lambda e:
                                       e.cont(acc + i) if i < 10 else acc)),
                 body=lambda e:
                        begin(print("s is {:d}".format(e.s)),
                              2 * e.s))
    assert result == 90

    # but for readability, we can do the same more pythonically:
    @call
    def result():
        @looped
        def s(loop, acc=0, i=0):
            cont = lambda newacc=acc: loop(newacc, i + 1)
            if i < 10:
                return cont(acc + i)
            else:
                return acc
        print("s is {:d}".format(s))
        return 2 * s
    assert result == 90

    # "multi-return" using escape continuation
    @setescape()
    def f():
        def g():
            escape("hello from g")  # the argument becomes the return value of f()
            print("not reached")
        g()
        print("not reached either")
    assert f() == "hello from g"

    # how to terminate surrounding function from inside FP loop
    @setescape()
    def f():
        @looped
        def s(loop, acc=0, i=0):
            if i > 5:
                escape(acc)
            return loop(acc + i, i + 1)
        print("never reached")
    assert f() == 15

    # tagged escapes to control where the escape is sent:
    # setescape point tags can be single value or tuple (tuples OR'd, like isinstance())
    @setescape(tags="foo")
    def foo():
        @call
        @setescape(tags="bar")
        def bar():
            @looped
            def s(loop, acc=0, i=0):
                if i > 5:
                    escape(acc, tag="foo")  # escape instance tag must be a single value
                return loop(acc + i, i + 1)
            print("never reached")
            return False
        print("never reached either")
        return False
    assert foo() == 15

    # lispy call/ec (call-with-escape-continuation)
    @call_ec
    def result(ec):  # effectively, just a code block!
        answer = 42
        ec(answer)  # here this has the same effect as "return answer"...
        print("never reached")
        answer = 23
        return answer
    assert result == 42

    @call_ec
    def result(ec):
        answer = 42
        def inner():
            ec(answer)  # ...but here this directly escapes from the outer def
            print("never reached")
            return 23
        answer = inner()
        print("never reached either")
        return answer
    assert result == 42

    # begin() returns the last value. What if we don't want that?
    result = call_ec(lambda ec:
                       begin(print("hi from lambda"),
                             ec(42),  # now we can effectively "return ..." at any point from a lambda!
                             print("never reached")))
    assert result == 42

if __name__ == '__main__':
    main()
