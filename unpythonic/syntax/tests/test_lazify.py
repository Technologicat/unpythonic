# -*- coding: utf-8 -*-
"""Automatic lazy evaluation of function arguments."""

from ...syntax import macros, test, test_raises, error, the  # noqa: F401
from ...test.fixtures import session, testset, returns_normally

from mcpyrate.quotes import macros, q  # noqa: F811
from mcpyrate.compiler import run, temporary_module

from ...syntax import (macros, lazify, lazy, lazyrec,  # noqa: F811, F401
                       let, letseq, letrec, local,
                       tco,
                       autocurry,
                       continuations, call_cc)

from ...collections import frozendict
from ...ec import call_ec
from ...excutil import raisef
from ...fun import (curry, memoize, flip, rotate, apply,
                    notf, andf, orf, tokth, withself)
from ...funutil import call, callwith, Values
from ...it import flatten
from ...llist import ll
from ...seq import pipe1, piped1, lazy_piped1, pipe, pipec, piped, lazy_piped, exitpipe
from ...tco import trampolined, jump

from ...lazyutil import islazy, Lazy, force1, force  # Lazy usually not needed in client code; for our tests only

from sys import stderr
import gc

def runtests():
    # first test the low-level tools
    with testset("lazyrec (lazify a container literal, recursing into sub-containers)"):
        # supported container types: tuple, list, set, frozenset, dict, frozendict
        tpl = lazyrec[(2 + 3, 2 * 21, 1 / 0)]
        test[all(the[type(x)] is Lazy for x in tpl)]

        lst = lazyrec[[2 + 3, 2 * 21, 1 / 0]]
        test[all(the[type(x)] is Lazy for x in lst)]

        s = lazyrec[{2 + 3, 2 * 21, 1 / 0}]
        test[all(the[type(x)] is Lazy for x in s)]

        fs = lazyrec[frozenset({2 + 3, 2 * 21, 1 / 0})]
        test[all(the[type(x)] is Lazy for x in fs)]

        dic = lazyrec[{'a': 2 + 3, 'b': 2 * 21, 'c': 1 / 0}]
        test[all(the[type(v)] is Lazy for k, v in dic.items())]

        fdic = lazyrec[frozendict({'a': 2 + 3, 'b': 2 * 21, 'c': 1 / 0})]
        test[all(the[type(v)] is Lazy for k, v in fdic.items())]

        # Works also when using the constructor call syntax for the container.
        tpl = lazyrec[tuple((2 + 3, 2 * 21, 1 / 0))]
        test[all(the[type(x)] is Lazy for x in tpl)]

        lst = lazyrec[list((2 + 3, 2 * 21, 1 / 0))]
        test[all(the[type(x)] is Lazy for x in lst)]

        s = lazyrec[set((2 + 3, 2 * 21, 1 / 0))]
        test[all(the[type(x)] is Lazy for x in s)]

        dic = lazyrec[dict(a=2 + 3, b=2 * 21, c=1 / 0)]
        test[all(the[type(v)] is Lazy for k, v in dic.items())]

        dic = lazyrec[dict(a=2 + 3, b=2 * 21, **{'c': 1 / 0})]
        test[all(the[type(v)] is Lazy for k, v in dic.items())]

        llst = lazyrec[ll(*(1 / 0, 2 / 0, 3 / 0))]
        test[all(the[type(x)] is Lazy for x in llst)]

        # Works also when a constructor call is nested inside a constructor call being lazified.
        llst = lazyrec[ll(2 + 3, ll(2 * 21))]
        it = iter(llst)
        first, second = next(it), next(it)
        test[type(first) is Lazy]
        second_firstitem = next(iter(second))
        test[type(second_firstitem) is Lazy]

    with testset("force (compute the lazy value now; the inverse of lazyrec)"):
        # force1() forces a promise
        promise = lazy[2 + 3]
        test[type(promise) is Lazy]
        test[type(force1(promise)) == int]
        test[force1("not a promise") == "not a promise"]  # anything else is passed through

        # force() recurses into containers, forcing any promises found therein
        promises = (lazy[2 + 3], lazy[2 * 21])
        test[type(force1(promises)) is tuple]
        test[all(the[type(x)] is Lazy for x in force1(promises))]
        test[type(force(promises)) is tuple]
        test[all(the[type(x)] is int for x in force(promises))]

        # so force() is the inverse of lazyrec[]
        tpl = lazyrec[(2 + 3, 2 * 21)]
        test[force(tpl) == (5, 42)]

        test[force(dic['a']) == 5]
        test[force(dic['b']) == 42]
        test_raises[ZeroDivisionError, force(dic['c']), "should have attempted to divide by zero"]

        tpl = lazyrec[(2 + 3, 2 * 21, 1 / 0)]
        test[force(tpl[:-1]) == (5, 42)]

        # recursion into nested containers
        tpl = lazyrec[((2 + 3, 2 * 21, (1 / 0, 2 / 1)), (4 * 5, 6 * 7))]
        test[all(the[type(x)] is Lazy for x in flatten(tpl))]

        tpl = lazyrec[((1 + 2, 3 + 4), (5 + 6, 7 + 8))]
        test[force(tpl) == ((3, 7), (11, 15))]

    with testset("basic usage"):
        # in a "with lazify" block, function arguments are evaluated only when actually used.
        with lazify:
            # basic usage
            def my_if(p, a, b):
                if p:
                    return a  # b never evaluated in this code path
                else:
                    return b  # a never evaluated in this code path

            # basic test for argument passing/returns
            test[my_if(True, 23, 0) == 23]
            test[my_if(False, 0, 42) == 42]

            # test the laziness
            # note the raisef() calls; in regular Python, they'd run anyway before my_if() gets control.
            test[my_if(True, 23, raisef(RuntimeError("I was evaluated!"))) == 23]
            test[my_if(False, raisef(RuntimeError("I was evaluated!")), 42) == 42]

            # In this example, the divisions by zero are never performed.
            test[my_if(True, 23, 1 / 0) == 23]
            test[my_if(False, 1 / 0, 42) == 42]

    with testset("lazify functions that have decorators"):
        # With a `def` or `async def` that has decorators, `lazify`
        # consults `suggest_decorator_index` as to where to plonk
        # `passthrough_lazy_args`.
        # TODO: Currently decorated lambdas aren't as lucky; difficult to do.
        with lazify:
            @trampolined
            def fact(n, acc=1):
                if n == 1:
                    return acc
                return jump(fact, n - 1, n * acc)
            test[fact(5) == 120]

    with testset("named args"):
        with lazify:
            def my_if2(*, test, then, otherwise):
                if test:
                    return then
                else:
                    return otherwise
            test[my_if2(test=True, then=23, otherwise=1 / 0) == 23]
            test[my_if2(test=False, then=1 / 0, otherwise=42) == 42]

    with testset("starargs"):
        with lazify:
            def foo(*args):
                return args
            # case 1: pass as regular positional args
            test[foo(1, 2, 3) == (1, 2, 3)]
            # case 2: pass a literal tuple of computations as *args
            test[foo(*(2 + 2, 2 + 3, 3 + 3)) == (4, 5, 6)]
            # case 3: pass already computed data as *args
            t = (4, 5, 6)
            test[foo(*t) == (4, 5, 6)]

            # accessing only part of starargs (at the receiving end)
            def foo2(*args):
                return args[0]
            test[foo2(42, 1 / 0, 1 / 0) == 42]
            test[foo2(*(42, 1 / 0, 1 / 0)) == 42]
            def foo3(*args):
                return args[:-1]
            test[foo3(23, 42, 1 / 0) == (23, 42)]
            test[foo3(*(23, 42, 1 / 0)) == (23, 42)]

    with testset("kwargs"):
        with lazify:
            # kwargs
            def bar(**dic):
                return dic["a"], dic["b"]
            # case 1: pass as regular named args
            test[bar(a="tavern", b="pub") == ("tavern", "pub")]
            # case 2: pass a literal dict of computations as **kwargs
            test[bar(**{"a": ("tav" + "ern"), "b": ("p" + "ub")}) == ("tavern", "pub")]
            # case 3: pass already computed data as **kwargs
            d = {"a": "tavern", "b": "pub"}
            test[bar(**d) == ("tavern", "pub")]

            # accessing only part of kwargs (at the receiving end)
            test[bar(a=1, b=2, c=1 / 0) == (1, 2)]
            test[bar(**{"a": 1, "b": 2, "c": 1 / 0}) == (1, 2)]

    with testset("literal containers appearing starred in calls"):
        with lazify:
            # To trigger this edge case, we have to star a constructor call
            # to a literal container that accepts multiple arguments.
            def bar(*args):
                return args
            test[bar(*ll("tavern", "pub")) == ("tavern", "pub")]

            # And similarly for **kwargs.
            def bar(**dic):
                return dic["a"], dic["b"]
            test[bar(**dict(a="tavern", b="pub"))]

    with testset("auto-force"):
        with lazify:
            def f(x):
                test[x == 17]  # auto-forced because "x" is the name of a formal parameter

                x = lazy[2 * 21]  # assign another promise
                test[x == 42]     # still auto-forced due to name "x"

                x = 23         # assign a bare data value
                # still auto-forced due to name "x", but ok, because
                # force(x) evaluates to x when x is not a promise.
                test[x == 23]
            f(17)

            def g(x):
                y = x  # auto-forced due to the read of a formal parameter on the RHS
                test[y == 42]  # y is just a value
                test[x == 42]  # auto-forced (now gets the cached value) since "x" is the original name
            g(2 * 21)

    with testset("auto-lazify when a literal container appears as a function argument"):
        # constructing a literal container in a function argument auto-lazifies it
        with lazify:
            def f(lst):
                return lst[:-1]
            test[f([1, 2, 3 / 0]) == [1, 2]]

            # works also using function call syntax (only for certain types; see lazyrec[])
            def f(lst):
                return lst[:-1]
            test[f(list((1, 2, 3 / 0))) == [1, 2]]

            def g(s):
                return s
            test[g(frozenset({1, 2, 3})) == {1, 2, 3}]

    with testset("mutable container as a function argument"):
        with lazify:
            def f(lst):
                lst[0] = 10 * lst[0]
            lst = [1, 2, 3]
            f(lst)
            test[lst == [10, 2, 3]]

    with testset("lambda"):
        with lazify:
            test[tuple(map((lambda x: 2 * x), (1, 2, 3))) == (2, 4, 6)]

    # manually lazified mutable container
    # note we **do not** auto-lazify assignment RHSs, because that creates an
    # infinite loop trap for the unwary (since assignment allows imperative update,
    # which is not an equation)
    with testset("manually lazified mutable container as a function argument"):
        with lazify:
            def f(lst):
                lst[0] = 10 * lst[0]
            lst = lazyrec[[1, 2, 3 / 0]]
            f(lst)
            test[lst[:-1] == [10, 2]]

    # manually lazified argument; not necessary, but allowed; should not stack Lazy
    with testset("manually lazified function argument does not stack Lazy"):
        with lazify:
            def f(lst):
                lst[0] = 10 * lst[0]
            lst = [1, 2, 3]
            f(lazy[lst])
            test[lst == [10, 2, 3]]

    with testset("object attributes"):
        with lazify:
            class C:
                def __init__(self):
                    self.x = 1
                    self.y = [1, 2, 3]
            c = C()
            test[c.x == 1]
            c.y.append(4)
            test[c.y == [1, 2, 3, 4]]

            lst = lazyrec[[1, 2, 3 / 0]]
            lst.append(lazy[4])
            test[lst[0] == 1]

            lst = lazyrec[[[1, 2 / 0], 3 / 0]]
            lst[0].append(lazy[4])
            test[the[lst[0][0]] == 1 and the[lst[0][2]] == 4]

    with testset("passthrough of lazy args"):
        with lazify:
            # positional arg -> positional arg
            def f2(a, b):
                return a
            def f1(a, b):
                return f2(a, b)
            test[f1(42, 1 / 0) == 42]

            # named arg -> named arg
            def f4(*, a, b):
                return a
            def f3(*, a, b):
                return f4(a=a, b=b)
            test[f3(a=42, b=1 / 0) == 42]

            # positional arg -> named arg
            def f11(*, a, b):
                return a
            def f10(a, b):
                return f11(a=a, b=b)
            test[f10(42, 1 / 0) == 42]

            # named arg -> positional arg
            def f13(a, b):
                return a
            def f12(*, a, b):
                return f13(a, b)
            test[f12(a=42, b=1 / 0) == 42]

            # received *args -> *args in a call (in Python 3.5+, multiple *args in a call possible)
            def f6(*args):
                return args[0]
            def f5(*args):
                return f6(*args)
            test[f5(42, 1 / 0) == 42]
            test[f5(*(42, 1 / 0)) == 42]

            # received **kwargs -> **kwargs in a call (in Python 3.5+, multiple **kwargs in a call possible)
            def f8(**kwargs):
                return kwargs['a']
            def f7(**kwargs):
                return f8(**kwargs)
            test[f7(a=42, b=1 / 0) == 42]
            test[f7(**{'a': 42, 'b': 1 / 0}) == 42]

            # computation involving a positional arg -> positional arg
            # The "2*b" is never evaluated, because f15 does not use its "b".
            def f15(a, b):
                return a
            def f14(a, b):
                return f15(2 * a, 2 * b)
            test[f14(21, 1 / 0) == 42]

    with testset("integration: expand nested inner macro invocations"):
        # Here we need precise control over what the expander is doing,
        # so we use `mcpyrate`'s run-time compiler access.
        #
        # Particularly, we need to enable expand-once mode to see whether the
        # innermost macro expands correctly. This depends on `lazify` expanding
        # inner macro invocations in recursive mode, regardless of the mode of
        # the expander.
        #
        # If it doesn't, the innermost macro won't be expanded before `lazify`
        # performs its own AST edits (editing also `Subscript` nodes), and in
        # the result, it will no longer be a macro invocation, and will hence
        # cause a `NameError` at run time.
        #
        # This block becomes a module. It's quoted, so macros won't expand
        # when the parent module does. We're just constructing an AST here.
        with q as quoted:
            from mcpyrate.debug import macros, step_expansion  # noqa: F811
            from unpythonic.syntax import macros, test  # noqa: F811

            from unpythonic.syntax import macros, lazify, lazy  # noqa: F811, F401
            # TODO: This prints a lot of stuff, because that's its primary purpose.
            # TODO: Here it would be nicer to use a macro that only enables expand-once mode.
            with step_expansion:
                with lazify:
                    # Here we need any macro that expands outside-in. The important thing is
                    # it doesn't recurse (`expander.visit`) on its own, instead relying on the
                    # expander's recursive mode to expand any remaining macro invocations inside
                    # the tree. Here we use `with test` in this dummy role.
                    with test:
                        lazy[...]  # <-- this should get expanded, not raise NameError at run time
        # And this is where we compile and run that AST, within a new temporary module.
        # The filename should be descriptive, but not end in `.py`, since it's not an actual file.
        with temporary_module(filename="tests in unpythonic.syntax.tests.test_lazify") as module:
            test[returns_normally(run(quoted, module))]

    # let bindings have a role similar to function arguments, so we auto-lazify there
    with testset("integration with let, letseq, letrec"):
        with lazify:
            def f(a, b):
                return a
            test[let[[c << 42, d << 1 / 0] in f(c, d)] == 42]

            # a reference on a let binding RHS works like a reference in a function call: just pass it through
            e = lazy[1 / 0]
            test[let[[c << 42, d << e] in f(c, d)] == 42]

            # nested lets
            test[letseq[[c << 42, d << e] in f(c, d)] == 42]
            test[letseq[[a << 2, a << 2 * a, a << 2 * a] in a] == 8]  # name shadowing, no infinite loop  # noqa: F821, `letseq` defines `a` here.

            b = 2  # let[] should already have taken care of resolving references when lazify expands
            test[letseq[[b << 2 * b, b << 2 * b] in b] == 8]
            test[b == 2]

            b = lazy[2]  # should work also for lazy input
            test[letseq[[b << 2 * b, b << 2 * b] in b] == 8]
            test[b == 2]

            # letrec injects lambdas into its bindings, so test it too.
            test[letrec[[c << 42, d << e] in f(c, d)] == 42]

    # In `unpythonic`, return values are never implicitly lazy.
    # At the minimum, you can always inspect whether it is an object or a `Values` instance,
    # representing multiple and/or named return values.
    with testset("interaction with Values (multiple and named return values)"):
        with lazify:
            def multireturn1(a, b):
                # As usual, the mention of `a` and `b` inside the function body forces the promises.
                # It doesn't matter whether the mention occurs in a `Values(...)` call.
                return Values(a, b)
            test[isinstance(multireturn1(2, 3), Values)]
            test[multireturn1(2, 3) == Values(2, 3)]

            def multireturn2(a, b):
                # Assignment to a temporary doesn't matter; `lazify` detects the `Values(...)` call anywhere.
                tmp = Values(a, b)
                return tmp
            test[isinstance(multireturn2(2, 3), Values)]
            test[multireturn2(2, 3) == Values(2, 3)]

            def namedreturn1(x, y):
                # Named return values can be given as named arguments.
                return Values(x=x, y=y)
            test[isinstance(namedreturn1(2, 3), Values)]
            test[namedreturn1(2, 3) == Values(x=2, y=3)]

            def namedreturn2(x, y):
                tmp = Values(x=x, y=y)
                return tmp
            test[isinstance(namedreturn2(2, 3), Values)]
            test[namedreturn2(2, 3) == Values(x=2, y=3)]

    # various higher-order functions, mostly from unpythonic.fun
    with testset("interaction with higher-order functions"):
        with lazify:
            @curry
            def add2first(a, b, c):
                return a + b
            test[add2first(2)(3)(1 / 0) == 5]

            test[call(add2first, 2)(3)(1 / 0) == 5]
            test[call(add2first, 2)(3, 1 / 0) == 5]
            test[call(add2first, 2, 3)(1 / 0) == 5]

            test[(callwith(2)(add2first))(3, 1 / 0) == 5]
            test[(callwith(2)(add2first))(3)(1 / 0) == 5]
            test[(callwith(2, 3)(add2first))(1 / 0) == 5]

            @memoize
            def add2first(a, b, c):
                return a + b
            test[add2first(2, 3, 1 / 0) == 5]
            test[add2first(2, 3, 1 / 0) == 5]  # from memo

            @flip
            def add2last(a, b, c):
                return a + b
            test[add2last(1 / 0, 2, 3) == 5]

            @rotate(1)
            def derp(a, b, c):
                return (c, a)
            test[derp(1, 2, 3 / 0) == (1, 2)]

            test[apply(derp, (1, 2, 3 / 0)) == (1, 2)]
            test[apply(derp, 1, (2, 3 / 0)) == (1, 2)]
            test[apply(derp, 1, 2, (3 / 0,)) == (1, 2)]

            # relevant utilities in unpythonic.fun preserve the "passthrough lazy args" mark
            def g1(x):
                return x < 3
            test[islazy(g1)]
            test[g1(2) is True]
            g2 = notf(g1)
            test[islazy(g2)]
            test[g2(2) is False]

            def g3(x):
                return x > 1
            test[islazy(g3)]
            test[g3(2) is True]
            g4 = andf(g1, g3)
            test[islazy(g4)]
            test[g4(2) is True]

            g5 = orf(g1, g3)
            test[islazy(g5)]
            test[g5(2) is True]

            def h1(x):
                return 42 * x
            test[islazy(h1)]
            test[h1(2) == 84]
            h2 = tokth(1, h1)
            test[islazy(h2)]
            # args 0 and 2 never *used* by h2, so we need to force()
            # to get their values to compare the reference answer to.
            # Also, h2 uses tokth, which wraps its multiple-return-values in a Values.
            test[force(h2(1, 2, 3)) == Values(1, 84, 3)]

            fact = withself(lambda self, n, acc=1: self(n - 1, acc * n) if n > 1 else acc)  # linear process
            test[islazy(fact)]
            test[fact(5) == 120]

    with testset("integration with pipes"):
        # This is the testset from unpythonic/tests/test_seq.py, slightly modified.
        with lazify:
            double = lambda x: 2 * x
            inc = lambda x: x + 1
            test[pipe1(42, double, inc) == 85]  # 1-in-1-out
            test[pipe1(42, inc, double) == 86]
            test[pipe(42, double, inc) == 85]   # n-in-m-out, supports also 1-in-1-out
            test[pipe(42, inc, double) == 86]

            # 2-in-2-out
            a, b = pipe(Values(2, 3),
                        lambda x, y: Values(x + 1, 2 * y),
                        lambda x, y: Values(x * 2, y + 1))
            test[(a, b) == (6, 7)]

            # 2-in-2-out, pass intermediate result by name
            a, b = pipe(Values(2, 3),
                        lambda x, y: Values(x=(x + 1), y=(2 * y)),
                        lambda x, y: Values(x * 2, y + 1))
            test[(a, b) == (6, 7)]

            # 2-in-2-out, also return final result by name
            v = pipe(Values(2, 3),
                     lambda x, y: Values(x=(x + 1), y=(2 * y)),
                     lambda x, y: Values(a=(x * 2), b=(y + 1)))
            test[v == Values(a=6, b=7)]
            test[v["a"] == 6 and v["b"] == 7]  # can access them via subscripting too

            # 2-in-eventually-3-out
            a, b, c = pipe(Values(2, 3),
                           lambda x, y: Values(x + 1, 2 * y, "foo"),
                           lambda x, y, z: Values(x * 2, y + 1, f"got {z}"))
            test[(a, b, c) == (6, 7, "got foo")]

            # 2-in-3-in-between-2-out
            a, b = pipe(Values(2, 3),
                        lambda x, y: Values(x + 1, 2 * y, "foo"),
                        lambda x, y, s: Values(x * 2, y + 1, f"got {s}"),
                        lambda x, y, s: Values(x + y, s))
            test[(a, b) == (13, "got foo")]

            # pipec: curry the functions before running the pipeline
            a, b = pipec(Values(1, 2),
                         lambda x: x + 1,  # extra values passed through by curry (positionals on the right)
                         lambda x, y: Values(x * 2, y + 1))
            test[(a, b) == (4, 3)]

            with test_raises[TypeError, "should error when the curry context exits with args remaining"]:
                a, b = pipec(Values(1, 2),
                             lambda x: x + 1,
                             lambda x: x * 2)

            # optional shell-like syntax
            test[piped1(42) | double | inc | exitpipe == 85]

            y = piped1(42) | double
            test[y | inc | exitpipe == 85]
            test[y | exitpipe == 84]  # y is never modified by the pipe system

            # multi-arg version
            f = lambda x, y: Values(2 * x, y + 1)
            g = lambda x, y: Values(x + 1, 2 * y)
            x = piped(2, 3) | f | g | exitpipe  # --> (5, 8)
            test[x == Values(5, 8)]

            # abuse multi-arg version for single-arg case
            test[piped(42) | double | inc | exitpipe == 85]

    with testset("integration with lazy pipes (plan computations)"):
        # This is the testset from unpythonic/tests/test_seq.py, slightly modified.
        with lazify:
            # lazy pipe: compute later
            lst = [1]
            def append_succ(lis):
                lis.append(lis[-1] + 1)
                return lis  # important, handed to the next function in the pipe
            p = lazy_piped1(lst) | append_succ | append_succ  # plan a computation
            test[lst == [1]]        # nothing done yet
            p | exitpipe              # run the computation
            test[lst == [1, 2, 3]]  # now the side effect has updated lst.

            # lazy pipe as an unfold
            fibos = []
            def nextfibo(state):
                a, b = state
                fibos.append(a)      # store result by side effect
                return (b, a + b)    # new state, handed to next function in the pipe
            p = lazy_piped1((1, 1))  # load initial state into a lazy pipe
            for _ in range(10):      # set up pipeline
                p = p | nextfibo
            p | exitpipe
            test[fibos == [1, 1, 2, 3, 5, 8, 13, 21, 34, 55]]

            # multi-arg lazy pipe
            p1 = lazy_piped(2, 3)
            p2 = p1 | (lambda x, y: Values(x + 1, 2 * y, "foo"))
            p3 = p2 | (lambda x, y, s: Values(x * 2, y + 1, f"got {s}"))
            p4 = p3 | (lambda x, y, s: Values(x + y, s))
            # nothing done yet, and all computations purely functional:
            test[(p1 | exitpipe) == Values(2, 3)]
            test[(p2 | exitpipe) == Values(3, 6, "foo")]      # runs the chain up to p2
            test[(p3 | exitpipe) == Values(6, 7, "got foo")]  # runs the chain up to p3
            test[(p4 | exitpipe) == Values(13, "got foo")]

            # multi-arg lazy pipe as an unfold
            fibos = []
            def nextfibo(a, b):    # now two arguments
                fibos.append(a)
                return Values(a=b, b=(a + b))  # can return by name too
            p = lazy_piped(1, 1)
            for _ in range(10):
                p = p | nextfibo
            test[p | exitpipe == Values(a=89, b=144)]  # final state
            test[fibos == [1, 1, 2, 3, 5, 8, 13, 21, 34, 55]]

            # abuse multi-arg version for single-arg case
            test[lazy_piped(42) | double | inc | exitpipe == 85]

    with testset("integration with TCO"):
        with lazify:
            @trampolined
            def func1(x):
                return jump(func2, x)
            @trampolined
            def func2(x):
                return 2 * x
            test[func1(21) == 42]

            print("*** This error case SHOULD PRINT A WARNING:", file=stderr)
            with test_raises[RuntimeError]:
                @trampolined
                def func3():
                    return jump(42)
                func3()
            gc.collect()

    with testset("integration with TCO and call_ec"):
        with lazify:
            @trampolined
            @call_ec
            def withec1(ec):
                ec(42)
            test[withec1 == 42]

        with tco, lazify:
            @call_ec
            def withec2(ec):
                ec(42)
            test[withec2 == 42]

    # Introducing the HasThon programming language.
    # If you want to play around with this idea, see `unpythonic.dialects.pytkell`.
    with testset("HasThon, with 100% more Thon than popular brands"):
        with lazify, autocurry:
            def add3(a, b, c):
                return a + b + c
            test[add3(1)(2)(3) == 6]

            def add2first(a, b, c):
                return a + b
            test[add2first(2)(3)(1 / 0) == 5]

            def f(a, b):
                return a
            test[let[[c << 42, d << 1 / 0] in f(c)(d)] == 42]
            test[letrec[[c << 42, d << 1 / 0, e << 2 * c] in f(e)(d)] == 84]

            test[letrec[[c << 42, d << 1 / 0, e << 2 * c] in [local[x << f(e)(d)],  # noqa: F821, `letrec` defines `x` here.
                                                              x / 2]] == 42]  # noqa: F821

    # works also with continuations
    #  - also conts are transformed into lazy functions
    #  - cc built by chain_conts is treated as lazy, **itself**; then it's up to
    #    the continuations chained by it to decide whether to force their args.
    #  - the default cont ``identity`` is strict, so it will force return values
    #    - if you want a non-strict identity for use at the entry point to your
    #      continuation-enabled computation, do this:
    #
    #          from unpythonic import identity
    #          from unpythonic.lazyutil import passthrough_lazy_args
    #          lazy_identity = passthrough_lazy_args(identity)
    #
    #      and then explicitly set the kwarg `cc=lazy_identity` when invoking the
    #      continuation-enabled computation (e.g. in the example below, we could
    #      `ourpromises = doit(cc=lazy_identity)`).
    with testset("integration with continuations"):
        with lazify, continuations:
            k = None
            def setk(*args, cc):
                nonlocal k
                k = cc
                return args[0]
            def doit():
                lst = ['the call returned']
                *more, = call_cc[setk('A', 1 / 0)]  # <-- this 1/0 goes into setk's args
                return lst + [more[0]]
            test[doit() == ['the call returned', 'A']]
            # We can now send stuff into k, as long as it conforms to the
            # signature of the assignment targets of the "call_cc".
            test[k('again') == ['the call returned', 'again']]
            # beware; if the cont tries to read the 1/0, that will lead to lots of
            # head-scratching, as the error will appear to come from this line
            # with no further debug info. (That's a limitation of the CPS conversion
            # technique combined with Python's insistence that there must be a line
            # and column in the original source file where the error occurred.)
            #
            # this 1/0 is sent directly into "more", as the call_cc returns again
            test[k('thrice', 1 / 0) == ['the call returned', 'thrice']]

if __name__ == '__main__':  # pragma: no cover
    with session(__file__):
        runtests()
