# -*- coding: utf-8; -*-

from ..syntax import macros, test, test_raises, fail  # noqa: F401
from .fixtures import session, testset, returns_normally

import typing
from ..fun import curry
from ..dispatch import generic, typed

@generic
def zorblify(x: int, y: int):
    return 2 * x + y
@generic  # noqa: F811, registered as a method of the same generic function.
def zorblify(x: str, y: int):
    # Because dispatching occurs on both arguments, this method is not reached by the tests.
    fail["this method should not be reached by the tests"]  # pragma: no cover
@generic  # noqa: F811
def zorblify(x: str, y: float):
    return "{} {}".format(x[::-1], y)

# TODO: def zorblify(x: int, *args: typing.Sequence[str]):

# @generic can also be used to simplify argument handling code in functions
# where the role of an argument in a particular position changes depending on
# the number of arguments (like the range() builtin).
#
# The pattern is that the generic function canonizes the arguments,
# and then calls the actual implementation, which always gets them
# in the same format.
@generic
def example(stop: int):
    return _example_impl(0, 1, stop)
@generic  # noqa: F811
def example(start: int, stop: int):
    return _example_impl(start, 1, stop)
@generic  # noqa: F811
def example(start: int, step: int, stop: int):
    return _example_impl(start, step, stop)
def _example_impl(start, step, stop):  # no @generic!
    return start, step, stop

# shorter, same effect
@generic
def example2(start: int, stop: int):
    return example2(start, 1, stop)  # just call the method that has the implementation
@generic  # noqa: F811
def example2(start: int, step: int, stop: int):
    return start, step, stop

# varargs are supported via `typing.Tuple`
@generic
def gargle(*args: typing.Tuple[int, ...]):  # any number of ints
    return "int"
@generic  # noqa: F811
def gargle(*args: typing.Tuple[float, ...]):  # any number of floats
    return "float"
@generic  # noqa: F811
def gargle(*args: typing.Tuple[int, float, str]):  # three args, matching the given types
    return "int, float, str"

# One-method pony, which automatically enforces argument types.
# The type specification may use features from the `typing` stdlib module.
@typed
def blubnify(x: int, y: float):
    return x * y

@typed
def jack(x: typing.Union[int, str]):  # look, it's the union-jack!
    return x

def runtests():
    with testset("@generic"):
        test[zorblify(17, 8) == 42]
        test[zorblify(17, y=8) == 42]  # can also use named arguments
        test[zorblify(y=8, x=17) == 42]
        test[zorblify("tac", 1.0) == "cat 1.0"]
        test[zorblify(y=1.0, x="tac") == "cat 1.0"]

        test_raises[TypeError, zorblify(1.0, 2.0)]  # there's no zorblify(float, float)

        test[example(10) == (0, 1, 10)]
        test[example(2, 10) == (2, 1, 10)]
        test[example(2, 3, 10) == (2, 3, 10)]

        test[example2(1, 5) == (1, 1, 5)]
        test[example2(1, 1, 5) == (1, 1, 5)]
        test[example2(1, 2, 5) == (1, 2, 5)]

        test[gargle(1, 2, 3, 4, 5) == "int"]
        test[gargle(2.71828, 3.14159) == "float"]
        test[gargle(42, 6.022e23, "hello") == "int, float, str"]
        test[gargle(1, 2, 3) == "int"]  # as many as in the [int, float, str] case

    with testset("@generic integration with OOP"):
        class TestTarget:
            myname = "Test target"
            def __init__(self, a):
                self.a = a

            # The OOP method type modifier (`@staticmethod` or `@classmethod`),
            # if any, goes on the outside.
            @staticmethod
            @generic
            def staticmeth(x: str):
                return " ".join(2 * [x])
            @staticmethod  # noqa: F811
            @generic
            def staticmeth(x: int):
                return 2 * x

            # `cls` does not need a type annotation.
            @classmethod
            @generic
            def clsmeth(cls, x: str):
                return "{} says: {}".format(cls.myname, " ".join(2 * [x]))
            # be careful, generic can't check that all variants are a @classmethod!
            @classmethod  # noqa: F811
            @generic
            def clsmeth(cls, x: int):
                return "{} computes: {}".format(cls.myname, 2 * x)

            # `self` does not need a type annotation.
            @generic
            def instmeth(self, x: str):
                return " ".join(self.a * [x])
            @generic  # noqa: F811
            def instmeth(self, x: int):
                return self.a * x

            @typed
            def checked(self, x: int):
                pass  # pragma: no cover

        tt = TestTarget(3)
        test[tt.instmeth("hi") == "hi hi hi"]
        test[tt.instmeth(21) == 63]
        test[tt.clsmeth("hi") == "Test target says: hi hi"]  # call via instance
        test[tt.clsmeth(21) == "Test target computes: 42"]
        test[TestTarget.clsmeth("hi") == "Test target says: hi hi"]  # call via class
        test[TestTarget.clsmeth(21) == "Test target computes: 42"]
        test[tt.staticmeth("hi") == "hi hi"]  # call via instance
        test[tt.staticmeth(21) == 42]
        test[TestTarget.staticmeth("hi") == "hi hi"]  # call via class
        test[TestTarget.staticmeth(21) == 42]
        test[returns_normally(tt.checked(42))]
        test_raises[TypeError, tt.checked("hi")]

    with testset("@typed"):
        test[blubnify(2, 21.0) == 42]
        test_raises[TypeError, blubnify(2, 3)]  # blubnify only accepts (int, float)
        test[not hasattr(blubnify, "register")]  # and no more methods can be registered on it

        test[jack(42) == 42]
        test[jack("foo") == "foo"]
        test_raises[TypeError, jack(3.14)]  # jack only accepts int or str

    with testset("error cases"):
        with test_raises(TypeError, "@typed should only accept a single method"):
            @typed
            def errorcase1(x: int):
                pass  # pragma: no cover
            @typed  # noqa: F811
            def errorcase1(x: str):
                pass  # pragma: no cover

        with test_raises(TypeError, "@generic should complain about missing type annotations"):
            @generic
            def errorcase2(x):
                pass  # pragma: no cover

    with testset("@typed integration with curry"):
        f = curry(blubnify, 2)
        test[callable(f)]
        test[f(21.0) == 42]

        # But be careful:
        f = curry(blubnify, 2.0)  # wrong argument type; error not triggered yet
        test[callable(f)]
        test_raises[TypeError, f(21.0) == 42]  # error will occur now, when the call is triggered

if __name__ == '__main__':  # pragma: no cover
    with session(__file__):
        runtests()
