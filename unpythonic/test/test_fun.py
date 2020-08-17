# -*- coding: utf-8 -*-

from ..syntax import macros, test, test_raises  # noqa: F401
from .fixtures import testset

from collections import Counter

from ..fun import (memoize, curry, apply,
                   identity, const,
                   andf, orf, notf,
                   flip, rotate,
                   composel1, composer1, composel, composer,
                   to1st, to2nd, tolast, to,
                   withself)

from ..dynassign import dyn

def runtests():
    with testset("unpythonic.fun"):
        with testset("identity function"):
            test[identity(1, 2, 3) == (1, 2, 3)]
            test[identity(42) == 42]
            test[identity() is None]  # no args, default value

        with testset("constant function"):
            test[const(1, 2, 3)(42, "foo") == (1, 2, 3)]
            test[const(42)("anything") == 42]
            test[const()("anything") is None]

        with testset("@memoize"):
            evaluations = Counter()
            @memoize
            def f(x):
                evaluations[x] += 1
                return x**2
            f(3)
            f(3)
            f(4)
            f(3)
            test[all(n == 1 for n in evaluations.values())]  # called only once for each unique set of arguments

            evaluations = 0
            @memoize  # <-- important part
            def square(x):
                nonlocal evaluations
                evaluations += 1
                return x**2
            test[square(2) == 4]
            test[evaluations == 1]
            test[square(3) == 9]
            test[evaluations == 2]
            test[square(3) == 9]
            test[evaluations == 2]  # called only once for each unique set of arguments
            test[square(x=3) == 9]
            test[evaluations == 2]  # only the resulting bindings matter, not how you pass the args

            # A tuple with only one object instance per unique contents (contents must be hashable):
            @memoize
            def memotuple(*args):
                return tuple(args)
            test[memotuple((1, 2, 3)) is memotuple((1, 2, 3))]
            test[memotuple((1, 2, 3)) is not memotuple((1, 2))]

            # "memoize lambda": classic evaluate-at-most-once thunk
            thunk = memoize(lambda: print("hi from thunk"))
            thunk()
            thunk()

            evaluations = 0
            @memoize
            def t():
                nonlocal evaluations
                evaluations += 1
            t()
            t()
            test[evaluations == 1]

            # memoizing an instance method
            #
            # This works essentially because self is an argument, and custom classes
            # have a default __hash__. Hence it doesn't matter that the memo lives in
            # the "memoized" closure on the class object (type), where the method is,
            # and not directly on the instances.
            #
            # For a solution storing the memo on the instances, see:
            #    https://github.com/ActiveState/code/tree/master/recipes/Python/577452_memoize_decorator_instance
            class Foo:
                def __init__(self):
                    self.evaluations = Counter()
                    self.x = 42
                    self.lst = []  # mutable attribute, just to be sure this works generally
                @memoize
                def doit(self, y):
                    self.evaluations[(id(self), y)] += 1
                    return self.x * y
            foo1 = Foo()
            foo1.doit(1)
            foo1.doit(1)
            foo1.doit(2)
            foo1.doit(3)
            foo1.doit(2)
            test[all(n == 1 for n in foo1.evaluations.values())]
            foo2 = Foo()
            assert not foo2.evaluations
            foo2.doit(1)
            foo2.doit(1)
            foo2.doit(2)
            foo2.doit(3)
            foo2.doit(2)
            test[all(n == 1 for n in foo2.evaluations.values())]

        with testset("@memoize caches exceptions"):
            # exception storage in memoize
            class AllOkJustTesting(Exception):
                pass
            evaluations = 0
            @memoize
            def t():
                nonlocal evaluations
                evaluations += 1
                raise AllOkJustTesting()
            olderr = None
            for _ in range(3):
                try:
                    t()
                except AllOkJustTesting as err:
                    if olderr is not None:
                        test[err is olderr]  # exception instance memoized, should be the same every time
                    olderr = err
                else:
                    test[False, "memoize should not prevent exception propagation"]
            test[evaluations == 1]

        with testset("@curry"):
            @curry
            def add3(a, b, c):
                return a + b + c
            test[add3(1)(2)(3) == 6]
            # actually uses partial application so these work, too
            test[add3(1, 2)(3) == 6]
            test[add3(1)(2, 3) == 6]
            test[add3(1, 2, 3) == 6]

            @curry
            def lispyadd(*args):
                return sum(args)
            test[lispyadd() == 0]  # no args is a valid arity here

            @curry
            def foo(a, b, *, c, d):
                return a, b, c, d
            test[foo(5, c=23)(17, d=42) == (5, 17, 23, 42)]

            # currying a thunk is essentially a no-op
            evaluations = 0
            @curry
            def t():
                nonlocal evaluations
                evaluations += 1
            t()
            test[evaluations == 1]  # t has no args, so it should have been invoked

            add = lambda x, y: x + y
            a = curry(add)
            test[curry(a) is a]  # curry wrappers should not stack

        with testset("top-level curry context handling"):
            def double(x):
                return 2 * x
            # curry raises by default when top-level curry context exits with args remaining:
            with test_raises(TypeError, "leftover args should not be allowed by default"):
                curry(double, 2, "foo")
            # to disable the error, use this trick to explicitly state your intent:
            with test("leftover args should be allowed with manually created surrounding context"):
                with dyn.let(curry_context=["whatever"]):  # any human-readable label is fine.
                    curry(double, 2, "foo") == (4, "foo")

        with testset("compose"):
            double = lambda x: 2 * x
            inc = lambda x: x + 1
            inc_then_double = composer1(double, inc)
            double_then_inc = composel1(double, inc)
            test[inc_then_double(3) == 8]
            test[double_then_inc(3) == 7]

            inc2_then_double = composer1(double, inc, inc)
            double_then_inc2 = composel1(double, inc, inc)
            test[inc2_then_double(3) == 10]
            test[double_then_inc2(3) == 8]

            inc_then_double = composer(double, inc)
            double_then_inc = composel(double, inc)
            test[inc_then_double(3) == 8]
            test[double_then_inc(3) == 7]

            inc2_then_double = composer(double, inc, inc)
            double_then_inc2 = composel(double, inc, inc)
            test[inc2_then_double(3) == 10]
            test[double_then_inc2(3) == 8]

        with testset("to1st, to2nd, tolast, to (argument shunting)"):
            test[to1st(double)(1, 2, 3) == (2, 2, 3)]
            test[to2nd(double)(1, 2, 3) == (1, 4, 3)]
            test[tolast(double)(1, 2, 3) == (1, 2, 6)]

            processor = to((0, double),
                           (-1, inc),
                           (1, composer(double, double)),
                           (0, inc))
            test[processor(1, 2, 3) == (3, 8, 4)]

        with testset("flip arglist"):
            def f(a, b):
                return (a, b)
            test[f(1, 2) == (1, 2)]
            test[(flip(f))(1, 2) == (2, 1)]
            test[(flip(f))(1, b=2) == (1, 2)]  # b -> kwargs

        with testset("rotate arglist"):
            test[(rotate(-1)(identity))(1, 2, 3) == (3, 1, 2)]
            test[(rotate(1)(identity))(1, 2, 3) == (2, 3, 1)]

            # inner to outer: (a, b, c) -> (b, c, a) -> (a, c, b)
            test[flip(rotate(-1)(identity))(1, 2, 3) == (1, 3, 2)]

        with testset("lispy apply"):
            def hello(*args):
                return args
            test[apply(hello, (1, 2, 3)) == (1, 2, 3)]
            test[apply(hello, 1, (2, 3, 4)) == (1, 2, 3, 4)]
            test[apply(hello, 1, 2, (3, 4, 5)) == (1, 2, 3, 4, 5)]
            test[apply(hello, 1, 2, [3, 4, 5]) == (1, 2, 3, 4, 5)]

        with testset("logical combinators"):
            test[notf(lambda x: 2 * x)(3) is False]
            test[notf(lambda x: 2 * x)(0) is True]

            isint = lambda x: isinstance(x, int)
            iseven = lambda x: x % 2 == 0
            isstr = lambda s: isinstance(s, str)
            test[andf(isint, iseven)(42) is True]
            test[andf(isint, iseven)(43) is False]

            pred = orf(isstr, andf(isint, iseven))
            test[pred(42) is True]
            test[pred("foo") is True]
            test[pred(None) is False]  # neither condition holds

        with testset("withself (Y combinator trick)"):
            fact = withself(lambda self, n: n * self(n - 1) if n > 1 else 1)
            test[fact(5) == 120]

if __name__ == '__main__':
    runtests()
