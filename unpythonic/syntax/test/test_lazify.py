# -*- coding: utf-8 -*-
"""Automatic lazy evaluation of function arguments."""

from ...misc import raisef
from ...it import flatten
from ...collections import frozendict

from ...syntax import macros, lazify, lazyrec, let, letseq, letrec, curry, local
from ...syntax import force

# doesn't really override the earlier curry import, the first one went into MacroPy's macro registry
from ...fun import curry, memoize, flip, rotate, apply
from ...misc import call, callwith

from macropy.quick_lambda import macros, lazy
from macropy.quick_lambda import Lazy  # usually not needed in client code; for our tests only

from macropy.tracing import macros, show_expanded

def test():
    # first test the low-level tools

    # supported container types: tuple, list, set, frozenset, dict, frozendict
    tpl = lazyrec[(2+3, 2*21, 1/0)]
    assert all(type(x) is Lazy for x in tpl)

    lst = lazyrec[[2+3, 2*21, 1/0]]
    assert all(type(x) is Lazy for x in lst)

    s = lazyrec[{2+3, 2*21, 1/0}]
    assert all(type(x) is Lazy for x in s)

    fs = lazyrec[frozenset({2+3, 2*21, 1/0})]
    assert all(type(x) is Lazy for x in fs)

    dic = lazyrec[{'a': 2+3, 'b': 2*21, 'c': 1/0}]
    assert all(type(v) is Lazy for k, v in dic.items())

    fdic = lazyrec[frozendict({'a': 2+3, 'b': 2*21, 'c': 1/0})]
    assert all(type(v) is Lazy for k, v in fdic.items())

    # force(), the inverse of lazyrec[]
    tpl = lazyrec[(2+3, 2*21)]
    assert force(tpl) == (5, 42)

    assert force(dic['a']) == 5
    assert force(dic['b']) == 42
    try:
        force(dic['c'])
    except ZeroDivisionError:
        pass
    else:
        assert False, "should have attempted to divide by zero"

    tpl = lazyrec[(2+3, 2*21, 1/0)]
    assert force(tpl[:-1]) == (5, 42)

    # recursion into nested containers
    tpl = lazyrec[((2+3, 2*21, (1/0, 2/1)), (4*5, 6*7))]
    assert all(type(x) is Lazy for x in flatten(tpl))

    tpl = lazyrec[((1+2, 3+4), (5+6, 7+8))]
    assert force(tpl) == ((3, 7), (11, 15))

#    with show_expanded:
    # in a "with lazify" block, function arguments are evaluated only when actually used.
    with lazify:
        # basic usage
        def my_if(p, a, b):
            if p:
                return a  # b never evaluated in this code path
            else:
                return b  # a never evaluated in this code path

        # basic test for argument passing/returns
        assert my_if(True, 23, 0) == 23
        assert my_if(False, 0, 42) == 42

        # test the laziness
        # note the raisef() calls; in regular Python, they'd run anyway before my_if() gets control.
        assert my_if(True, 23, raisef(RuntimeError, "I was evaluated!")) == 23
        assert my_if(False, raisef(RuntimeError, "I was evaluated!"), 42) == 42

        # In this example, the divisions by zero are never performed.
        assert my_if(True, 23, 1/0) == 23
        assert my_if(False, 1/0, 42) == 42

        # named args
        def my_if2(*, test, then, otherwise):
            if test:
                return then
            else:
                return otherwise
        assert my_if2(test=True, then=23, otherwise=1/0) == 23
        assert my_if2(test=False, then=1/0, otherwise=42) == 42

        # starargs
        def foo(*args):
            return args
        # case 1: pass as regular positional args
        assert foo(1, 2, 3) == (1, 2, 3)
        # case 2: pass a literal tuple of computations as *args
        assert foo(*(2+2, 2+3, 3+3)) == (4, 5, 6)
        # case 3: pass already computed data as *args
        t = (4, 5, 6)
        assert foo(*t) == (4, 5, 6)

        # accessing only part of starargs (at the receiving end)
        def foo2(*args):
            return args[0]
        assert foo2(42, 1/0, 1/0) == 42
        assert foo2(*(42, 1/0, 1/0)) == 42
        def foo3(*args):
            return args[:-1]
        assert foo3(23, 42, 1/0) == (23, 42)
        assert foo3(*(23, 42, 1/0)) == (23, 42)

        # kwargs
        def bar(**dic):
            return dic["a"], dic["b"]
        # case 1: pass as regular named args
        assert bar(a="tavern", b="pub") == ("tavern", "pub")
        # case 2: pass a literal dict of computations as **kwargs
        assert bar(**{"a": ("tav"+"ern"), "b": ("p"+"ub")}) == ("tavern", "pub")
        # case 3: pass already computed data as **kwargs
        d = {"a": "tavern", "b": "pub"}
        assert bar(**d) == ("tavern", "pub")

        # accessing only part of kwargs (at the receiving end)
        assert bar(a=1, b=2, c=1/0) == (1, 2)
        assert bar(**{"a": 1, "b": 2, "c": 1/0}) == (1, 2)

        def f(x):
            assert x == 17  # auto-forced because "x" is the name of a formal parameter

            x = lazy[2*21]  # assign another promise
            assert x == 42  # still auto-forced due to name "x"

            x = 23          # assign a bare data value
            assert x == 23  # still auto-forced due to name "x", but ok, because
                            # force(x) evaluates to x when x is not a promise.
        f(17)

        def g(x):
            y = x  # auto-forced due to the read of a formal parameter on the RHS
            assert y == 42  # y is just a value
            assert x == 42  # auto-forced (now gets the cached value) since "x" is the original name
        g(2*21)

    # constructing a literal container in a function argument auto-lazifies it
    with lazify:
        def f(lst):
            return lst[:-1]
        assert f([1, 2, 3/0]) == [1, 2]

        # works also using function call syntax (only for certain types; see lazyrec[])
        def f(lst):
            return lst[:-1]
        assert f(list((1, 2, 3/0))) == [1, 2]

        def g(s):
            return s
        assert g(frozenset({1, 2, 3})) == {1, 2, 3}

    # mutable container as a function argument
    with lazify:
        def f(lst):
            lst[0] = 10*lst[0]
        lst = [1, 2, 3]
        f(lst)
        assert lst == [10, 2, 3]

    # manually lazified mutable container
    # note we **do not** auto-lazify assignment RHSs, because that creates an
    # infinite loop trap for the unwary (since assignment allows imperative update,
    # which is not an equation)
    with lazify:
        def f(lst):
            lst[0] = 10*lst[0]
        lst = lazyrec[[1, 2, 3/0]]
        f(lst)
        assert lst[:-1] == [10, 2]

    # manually lazified argument; not necessary, but allowed; should not stack Lazy
    with lazify:
        def f(lst):
            lst[0] = 10*lst[0]
        lst = [1, 2, 3]
        f(lazy[lst])
        assert lst == [10, 2, 3]

    # attributes
    with lazify:
        class C:
            def __init__(self):
                self.x = 1
                self.y = [1, 2, 3]
        c = C()
        assert c.x == 1
        c.y.append(4)
        assert c.y == [1, 2, 3, 4]

        lst = lazyrec[[1, 2, 3/0]]
        lst.append(lazy[4])
        assert lst[0] == 1

        lst = lazyrec[[[1, 2/0], 3/0]]
        lst[0].append(lazy[4])
        assert lst[0][0] == 1 and lst[0][2] == 4

    # Passthrough of lazy args
    with lazify:
        # positional arg -> positional arg
        def f2(a, b):
            return a
        def f1(a, b):
            return f2(a, b)
        assert f1(42, 1/0) == 42

        # named arg -> named arg
        def f4(*, a, b):
            return a
        def f3(*, a, b):
            return f4(a=a, b=b)
        assert f3(a=42, b=1/0) == 42

        # positional arg -> named arg
        def f11(*, a, b):
            return a
        def f10(a, b):
            return f11(a=a, b=b)
        assert f10(42, 1/0) == 42

        # named arg -> positional arg
        def f13(a, b):
            return a
        def f12(*, a, b):
            return f13(a, b)
        assert f12(a=42, b=1/0) == 42

        # received *args -> *args in a call (in Python 3.5+, multiple *args in a call possible)
        def f6(*args):
            return args[0]
        def f5(*args):
            return f6(*args)
        assert f5(42, 1/0) == 42
        assert f5(*(42, 1/0)) == 42

        # received **kwargs -> **kwargs in a call (in Python 3.5+, multiple **kwargs in a call possible)
        def f8(**kwargs):
            return kwargs['a']
        def f7(**kwargs):
            return f8(**kwargs)
        assert f7(a=42, b=1/0) == 42
        assert f7(**{'a': 42, 'b': 1/0}) == 42

        # computation involving a positional arg -> positional arg
        # The "2*b" is never evaluated, because f15 does not use its "b".
        def f15(a, b):
            return a
        def f14(a, b):
            return f15(2*a, 2*b)
        assert f14(21, 1/0) == 42

    # let bindings have a role similar to function arguments, so we auto-lazify there
    with lazify:
        def f(a, b):
            return a
        assert let[((c, 42), (d, 1/0)) in f(c, d)] == 42

        # a reference on a let binding RHS works like a reference in a function call: just pass it through
        e = lazy[1/0]
        assert let[((c, 42), (d, e)) in f(c, d)] == 42

        # nested lets
        assert letseq[((c, 42), (d, e)) in f(c, d)] == 42
        assert letseq[((a, 2), (a, 2*a), (a, 2*a)) in a] == 8  # name shadowing, no infinite loop

        b = 2  # let[] should already have taken care of resolving references when lazify expands
        assert letseq[((b, 2*b), (b, 2*b)) in b] == 8
        assert b == 2

        b = lazy[2]  # should work also for lazy input
        assert letseq[((b, 2*b), (b, 2*b)) in b] == 8
        assert b == 2

        # letrec injects lambdas into its bindings, so test it too.
        assert letrec[((c, 42), (d, e)) in f(c, d)] == 42

    # various higher-order functions, mostly from unpythonic.fun
    with lazify:
        @curry
        def add2first(a, b, c):
            return a + b
        assert add2first(2)(3)(1/0) == 5

        assert call(add2first, 2)(3)(1/0) == 5
        assert call(add2first, 2)(3, 1/0) == 5
        assert call(add2first, 2, 3)(1/0) == 5

        assert (callwith(2)(add2first))(3, 1/0) == 5
        assert (callwith(2)(add2first))(3)(1/0) == 5
        assert (callwith(2, 3)(add2first))(1/0) == 5

        @memoize
        def add2first(a, b, c):
            return a + b
        assert add2first(2, 3, 1/0) == 5
        assert add2first(2, 3, 1/0) == 5  # from memo

        @flip
        def add2last(a, b, c):
            return a + b
        assert add2last(1/0, 2, 3) == 5

        @rotate(1)
        def derp(a, b, c):
            return (c, a)
        assert derp(1, 2, 3/0) == (1, 2)

        assert apply(derp, (1, 2, 3/0)) == (1, 2)
        assert apply(derp, 1, (2, 3/0)) == (1, 2)
        assert apply(derp, 1, 2, (3/0,)) == (1, 2)

    # introducing the HasThon programming language (it has 100% more Thon than popular brands)
#    with curry, lazify:
    with lazify:
      with curry:
        def add3(a, b, c):
            return a + b + c
        assert add3(1)(2)(3) == 6

        def add2first(a, b, c):
            return a + b
        assert add2first(2)(3)(1/0) == 5

        def f(a, b):
            return a
        assert let[((c, 42), (d, 1/0)) in f(c)(d)] == 42
        assert letrec[((c, 42), (d, 1/0), (e, 2*c)) in f(e)(d)] == 84

        assert letrec[((c, 42), (d, 1/0), (e, 2*c)) in [local[x << f(e)(d)],
                                                        x/2]] == 42

    print("All tests PASSED")
