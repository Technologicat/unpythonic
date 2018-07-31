#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Short quick tour. See tour.py for a full tour."""

from unpythonic import *

# assign-once environment
with assignonce() as e:
    e.foo = "bar"           # new definition, ok
    e.set("foo", "tavern")  # explicitly rebind e.foo, ok
    e << ("foo", "tavern")  # same thing (but returns e instead of new value)

    try:
        e.foo = "quux"      # AttributeError, e.foo already defined.
    except AttributeError:
        pass

# def as a lexically scoped code block
@immediate
def x():
    a = 2
    b = 3
    c = 5
    return a * b * c
assert x == 30

# multiple expressions in a lambda
b = lambda x: begin(print("cheeky side effect"),
                     42*x)
b(2)  # --> 84

# let & letrec
counter = let(x=0,
              body=lambda e:  # <-- ympäristö
                     lambda:  # <-- funktion "counter" määritelmä
                       begin(e.set("x", e.x + 1),
                             e.x))
counter()  # --> 1
counter()  # --> 2

u = lambda lst: letrec(seen=set(),
                       see=lambda e:
                              lambda x:
                                begin(e.seen.add(x),
                                      x),
                       body=lambda e:
                              [e.see(x) for x in lst if x not in e.seen])
L = [1, 1, 3, 1, 3, 2, 3, 2, 2, 2, 4, 4, 1, 2, 3]
u(L)  # --> [1, 3, 2, 4]

# tail call optimization (TCO) (w.r.t. stack space, not speed!)
@trampolined
def fact(n, acc=1):
    if n == 0:
        return acc
    else:
        return jump(fact, n - 1, n * acc)
fact(10000)

# FP loop
@looped
def s(loop, acc=0, i=0):
    if i == 10:
        return acc
    else:
        return loop(acc + i, i + 1)
assert s == 45

# FP loop over an iterable
@looped_over(range(10), acc=0)
def s(loop, x, acc):  # new x every iteration; no mutation!
    return loop(acc + x)  # return value of the loop = last value sent to loop()
assert s == 45

# escape continuations
@setescape()
def f():
    def g():
        raise escape("hello from g")  # arg becomes the return value of f
        print("not reached")
        return False
    g()
    print("not reached either")
    return False
assert f() == "hello from g"

# dynamic scoping
def f1():  # no "a" in lexical scope here
    assert dyn.a == 2

def f2():
    with dyn.let(a=2, b="foo"):
        assert dyn.a == 2

        f1()

        with dyn.let(a=3):  # these can be nested
            assert dyn.a == 3

        # now "a" has reverted to its previous value
        assert dyn.a == 2

    try:
        print(dyn.b)  # error, dyn.b no longer exists
    except AttributeError:
        pass
f2()
