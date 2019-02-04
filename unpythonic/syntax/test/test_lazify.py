# -*- coding: utf-8 -*-
"""Automatic lazy evaluation of function arguments."""

from ...misc import raisef
from ...it import flatten
from ...fup import frozendict

from ...syntax import macros, lazify, lazyrec
from ...syntax import force

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

    print("All tests PASSED")
