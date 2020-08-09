# -*- coding: utf-8 -*-

from collections import Counter

from ..fun import (memoize, curry, apply,
                   identity, const,
                   andf, orf, notf,
                   flip, rotate,
                   composel1, composer1, composel, composer,
                   to1st, to2nd, tolast, to,
                   withself)

from ..dynassign import dyn

def test():
    evaluations = Counter()
    @memoize
    def f(x):
        evaluations[x] += 1
        return x**2
    f(3)
    f(3)
    f(4)
    f(3)
    assert all(n == 1 for n in evaluations.values())  # called only once for each unique set of arguments

    evaluations = 0
    @memoize  # <-- important part
    def square(x):
        nonlocal evaluations
        evaluations += 1
        return x**2
    assert square(2) == 4
    assert evaluations == 1
    assert square(3) == 9
    assert evaluations == 2
    assert square(3) == 9
    assert evaluations == 2  # called only once for each unique set of arguments
    assert square(x=3) == 9
    assert evaluations == 2  # only the resulting bindings matter, not how you pass the args

    # A tuple with only one object instance per unique contents (contents must be hashable):
    @memoize
    def memotuple(*args):
        return tuple(args)
    assert memotuple((1, 2, 3)) is memotuple((1, 2, 3))
    assert memotuple((1, 2, 3)) is not memotuple((1, 2))

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
    assert evaluations == 1

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
    assert all(n == 1 for n in foo1.evaluations.values())
    foo2 = Foo()
    assert not foo2.evaluations
    foo2.doit(1)
    foo2.doit(1)
    foo2.doit(2)
    foo2.doit(3)
    foo2.doit(2)
    assert all(n == 1 for n in foo2.evaluations.values())

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
            if olderr is not None and err is not olderr:
                assert False  # exception instance memoized, should be same every time
            olderr = err
        else:
            assert False  # memoize should not block raise
    assert evaluations == 1

    @curry
    def add3(a, b, c):
        return a + b + c
    assert add3(1)(2)(3) == 6
    # actually uses partial application so these work, too
    assert add3(1, 2)(3) == 6
    assert add3(1)(2, 3) == 6
    assert add3(1, 2, 3) == 6

    @curry
    def lispyadd(*args):
        return sum(args)
    assert lispyadd() == 0  # no args is a valid arity here

    @curry
    def foo(a, b, *, c, d):
        return a, b, c, d
    assert foo(5, c=23)(17, d=42) == (5, 17, 23, 42)

    # currying a thunk is essentially a no-op
    evaluations = 0
    @curry
    def t():
        nonlocal evaluations
        evaluations += 1
    t()
    assert evaluations == 1  # t has no args, so it should have been invoked

    add = lambda x, y: x + y
    a = curry(add)
    assert curry(a) is a  # curry wrappers should not stack

    # top-level curry context handling
    def double(x):
        return 2 * x
    with dyn.let(curry_context=["whatever"]):
        curry(double, 2, "foo") == (4, "foo")
    try:
        curry(double, 2, "foo")
    except TypeError:
        pass
    else:
        assert False, "should fail by default when top-level curry context exits with args remaining"

    # flip
    def f(a, b):
        return (a, b)
    assert f(1, 2) == (1, 2)
    assert (flip(f))(1, 2) == (2, 1)
    assert (flip(f))(1, b=2) == (1, 2)  # b -> kwargs

    double = lambda x: 2 * x
    inc = lambda x: x + 1
    inc_then_double = composer1(double, inc)
    double_then_inc = composel1(double, inc)
    assert inc_then_double(3) == 8
    assert double_then_inc(3) == 7

    inc2_then_double = composer1(double, inc, inc)
    double_then_inc2 = composel1(double, inc, inc)
    assert inc2_then_double(3) == 10
    assert double_then_inc2(3) == 8

    inc_then_double = composer(double, inc)
    double_then_inc = composel(double, inc)
    assert inc_then_double(3) == 8
    assert double_then_inc(3) == 7

    inc2_then_double = composer(double, inc, inc)
    double_then_inc2 = composel(double, inc, inc)
    assert inc2_then_double(3) == 10
    assert double_then_inc2(3) == 8

    assert to1st(double)(1, 2, 3) == (2, 2, 3)
    assert to2nd(double)(1, 2, 3) == (1, 4, 3)
    assert tolast(double)(1, 2, 3) == (1, 2, 6)

    processor = to((0, double),
                   (-1, inc),
                   (1, composer(double, double)),
                   (0, inc))
    assert processor(1, 2, 3) == (3, 8, 4)

    assert identity(1, 2, 3) == (1, 2, 3)
    assert identity(42) == 42
    assert identity() is None
    assert (rotate(-1)(identity))(1, 2, 3) == (3, 1, 2)
    assert (rotate(1)(identity))(1, 2, 3) == (2, 3, 1)

    # inner to outer: (a, b, c) -> (b, c, a) -> (a, c, b)
    assert flip(rotate(-1)(identity))(1, 2, 3) == (1, 3, 2)

    def hello(*args):
        return args
    assert apply(hello, (1, 2, 3)) == (1, 2, 3)
    assert apply(hello, 1, (2, 3, 4)) == (1, 2, 3, 4)
    assert apply(hello, 1, 2, (3, 4, 5)) == (1, 2, 3, 4, 5)
    assert apply(hello, 1, 2, [3, 4, 5]) == (1, 2, 3, 4, 5)

    assert const(1, 2, 3)(42, "foo") == (1, 2, 3)
    assert const(42)("anything") == 42
    assert const()("anything") is None

    assert notf(lambda x: 2 * x)(3) is False
    assert notf(lambda x: 2 * x)(0) is True
    isint = lambda x: isinstance(x, int)
    iseven = lambda x: x % 2 == 0
    isstr = lambda s: isinstance(s, str)
    assert andf(isint, iseven)(42) is True
    assert andf(isint, iseven)(43) is False
    pred = orf(isstr, andf(isint, iseven))
    assert pred(42) is True
    assert pred("foo") is True
    assert pred(None) is False  # neither condition holds

    fact = withself(lambda self, n: n * self(n - 1) if n > 1 else 1)
    assert fact(5) == 120

    print("All tests PASSED")

if __name__ == '__main__':
    test()
