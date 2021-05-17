# -*- coding: utf-8; -*-

from ..syntax import macros, test, test_raises, fail, the  # noqa: F401
from ..test.fixtures import session, testset, returns_normally

import typing
from ..fun import curry
from ..dispatch import generic, augment, typed, format_methods

@generic
def zorblify(x: int, y: int):
    return 2 * x + y
@generic
def zorblify(x: str, y: int):  # noqa: F811, registered as a multimethod of the same generic function.
    # Because dispatching occurs on both arguments, this method is not reached by the tests.
    fail["this method should not be reached by the tests"]  # pragma: no cover
@generic
def zorblify(x: str, y: float):  # noqa: F811
    return f"{x[::-1]} {y}"
@generic
def zorblify(x: int, *args: typing.Sequence[str]):  # noqa: F811
    return f"{x}, {', '.join(args)}"

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
@generic
def example(start: int, stop: int):  # noqa: F811
    return _example_impl(start, 1, stop)
@generic
def example(start: int, step: int, stop: int):  # noqa: F811
    return _example_impl(start, step, stop)
def _example_impl(start, step, stop):  # no @generic!
    return start, step, stop

# shorter, same effect
@generic
def example2(stop: int):
    return example2(0, 1, stop)  # just call the multimethod that has the implementation
@generic
def example2(start: int, stop: int):  # noqa: F811
    return example2(start, 1, stop)
@generic
def example2(start: int, step: int, stop: int):  # noqa: F811
    return start, step, stop

# varargs are supported via `typing.Tuple`
@generic
def gargle(*args: typing.Tuple[int, ...]):  # any number of ints
    return "int"
@generic
def gargle(*args: typing.Tuple[float, ...]):  # any number of floats  # noqa: F811
    return "float"
@generic
def gargle(*args: typing.Tuple[int, float, str]):  # three args, matching the given types  # noqa: F811
    return "int, float, str"

# v0.15.0: dispatching on a homogeneous type inside **kwargs is also supported, via `typing.Dict`
@generic
def kittify(**kwargs: typing.Dict[str, int]):  # all kwargs are ints
    return "int"
@generic
def kittify(**kwargs: typing.Dict[str, float]):  # all kwargs are floats  # noqa: F811
    return "float"

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
        test[zorblify(23, "cat", "meow") == "23, cat, meow"]

        test_raises[TypeError, zorblify(1.0, 2.0)]  # there's no zorblify(float, float)

        test[example(10) == (0, 1, 10)]
        test[example(2, 10) == (2, 1, 10)]
        test[example(2, 3, 10) == (2, 3, 10)]

        test[example2(5) == (0, 1, 5)]
        test[example2(1, 5) == (1, 1, 5)]
        test[example2(1, 1, 5) == (1, 1, 5)]
        test[example2(1, 2, 5) == (1, 2, 5)]

        test[gargle(1, 2, 3, 4, 5) == "int"]
        test[gargle(2.71828, 3.14159) == "float"]
        test[gargle(42, 6.022e23, "hello") == "int, float, str"]
        test[gargle(1, 2, 3) == "int"]  # as many as in the [int, float, str] case

        test[kittify(x=1, y=2) == "int"]
        test[kittify(x=1.0, y=2.0) == "float"]
        test_raises[TypeError, kittify(x=1, y=2.0)]

    with testset("@generic integration with curry"):
        @generic
        def curryable(x: int, y: int):
            return "int"
        @generic
        def curryable(x: float, y: float):  # noqa: F811
            return "float"
        f = curry(curryable, 1)
        test[callable(the[f])]
        test[f(2) == "int"]

        # When the final set of arguments does not match any multimethod, it is a type error.
        test_raises[TypeError, f(2.0)]

        # CAUTION: Partially applying by name starts keyword-only processing in `inspect.signature`,
        # which is used by `unpythonic.arity.arities`, which in turn is used by `unpythonic.fun.curry`.
        # Hence, if we pass `x=1` by name here, the remaining positional arity becomes 0...
        f = curry(curryable, x=1)
        test[callable(the[f])]
        # ...so, we must pass `y` by name here.
        test[f(y=2) == "int"]

        # When no multimethod can match the given partial signature, it is a type error.
        test_raises[TypeError, curry(curryable, "abc")]

    with testset("@augment"):
        @generic
        def f1(x: typing.Any):
            return False
        @augment(f1)
        def f2(x: int):
            return x
        test[f1("hello") is False]
        test[f1(42) == 42]

        def f3(x: typing.Any):  # not @generic!
            return False
        with test_raises[TypeError, "should not be able to @augment a non-generic function"]:
            @augment(f3)
            def f4(x: int):
                return x

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
            @staticmethod
            @generic
            def staticmeth(x: int):  # noqa: F811
                return 2 * x

            # `cls` does not need a type annotation.
            @classmethod
            @generic
            def clsmeth(cls, x: str):
                return f"{cls.myname} says: {' '.join(2 * [x])}"
            # be careful, generic can't check that all variants are a @classmethod!
            @classmethod
            @generic
            def clsmeth(cls, x: int):  # noqa: F811
                return f"{cls.myname} computes: {2 * x}"

            # `self` does not need a type annotation.
            @generic
            def instmeth(self, x: str):
                return " ".join(self.a * [x])
            @generic
            def instmeth(self, x: int):  # noqa: F811
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

    # In OOP, `@generic` dispatches across the MRO.
    #
    # The classes are tried in MRO order, matching all methods in a single class
    # before moving on to the next one.
    with testset("@generic integration with OOP, with inheritance"):
        class BabyTestTarget(TestTarget):  # child class, get it?
            @staticmethod
            @generic
            def staticmeth(x: float):
                return f"float {2 * x}"

            @classmethod
            @generic
            def clsmeth(cls, x: float):
                return f"{cls.myname} floats: {2 * x}"

            @generic
            def instmeth(self, x: float):
                return f"floating with {self.a * x}"

        tt2 = BabyTestTarget(3)
        # the new multimethods become available, installed on the OOP method
        test[tt2.instmeth(3.14) == "floating with 9.42"]
        # old multimethods registered by the ancestor remain available
        test[tt2.instmeth("hi") == "hi hi hi"]
        test[tt2.instmeth(21) == 63]
        test[tt2.clsmeth(3.14) == "Test target floats: 6.28"]
        test[tt2.clsmeth("hi") == "Test target says: hi hi"]
        test[tt2.clsmeth(21) == "Test target computes: 42"]
        test[BabyTestTarget.clsmeth(3.14) == "Test target floats: 6.28"]
        test[BabyTestTarget.clsmeth("hi") == "Test target says: hi hi"]
        test[BabyTestTarget.clsmeth(21) == "Test target computes: 42"]

        # `@generic` on *static methods* **does not** support MRO lookup.
        # Basically, one of the roles of `cls` or `self` is to define the MRO;
        # a static method doesn't have that.
        #
        # See discussions on interaction between `@staticmethod` and `super` in Python:
        #   https://bugs.python.org/issue31118
        #   https://stackoverflow.com/questions/26788214/super-and-staticmethod-interaction/26807879
        test[tt2.staticmeth(3.14) == "float 6.28"]  # this is available on `tt2`
        test_raises[TypeError, tt2.staticmeth("hi")]  # but this is not (no MRO)
        test_raises[TypeError, tt2.staticmeth(21)]
        test[BabyTestTarget.staticmeth(3.14) == "float 6.28"]  # available on `BabyTestTarget`
        test_raises[TypeError, BabyTestTarget.staticmeth("hi")]  # not available (no MRO)
        test_raises[TypeError, BabyTestTarget.staticmeth(21)]

        test_raises[TypeError, tt2.clsmeth(None)]  # not defined for NoneType

    with testset("@typed"):
        test[blubnify(2, 21.0) == 42]
        test_raises[TypeError, blubnify(2, 3)]  # blubnify only accepts (int, float)
        with test_raises[TypeError, "should not be able to add more multimethods to a @typed function"]:
            @augment(blubnify)
            def blubnify2(x: float, y: float):
                pass

        test[jack(42) == 42]
        test[jack("foo") == "foo"]
        test_raises[TypeError, jack(3.14)]  # jack only accepts int or str

    with testset("list_methods"):
        def check_formatted_multimethods(result, expected):
            def _remove_space_before_typehint(string):  # Python 3.6 doesn't print a space there
                return string.replace(": ", ":")
            result_list = result.split("\n")
            human_readable_header, *multimethod_descriptions = result_list
            multimethod_descriptions = [x.strip() for x in multimethod_descriptions]
            test[the[len(multimethod_descriptions)] == the[len(expected)]]
            for r, e in zip(multimethod_descriptions, expected):
                r = _remove_space_before_typehint(r)
                e = _remove_space_before_typehint(e)
                test[the[r].startswith(the[e])]
        # @generic
        check_formatted_multimethods(format_methods(example2),
                                     ["example2(start: int, step: int, stop: int)",
                                      "example2(start: int, stop: int)",
                                      "example2(stop: int)"])
        # @typed
        check_formatted_multimethods(format_methods(blubnify),
                                     ["blubnify(x: int, y: float)"])

    with testset("error cases"):
        with test_raises[TypeError, "@typed should only accept a single method"]:
            @typed
            def errorcase1(x: int):
                pass  # pragma: no cover
            @typed
            def errorcase1(x: str):  # noqa: F811
                pass  # pragma: no cover

        with test_raises[TypeError, "@generic should complain about missing type annotations"]:
            @generic
            def errorcase2(x):
                pass  # pragma: no cover

    with testset("@typed integration with curry"):
        f = curry(blubnify, 2)
        test[callable(the[f])]
        test[f(21.0) == 42]

        # Wrong argument type during partial application of @typed function - error reported immediately.
        test_raises[TypeError, curry(blubnify, 2.0)]

    with testset("holy traits in Python with @generic"):
        # Note we won't get the performance benefits of Julia, because this is a
        # purely run-time implementation.
        #
        # For what this is about, see:
        # https://ahsmart.com/pub/holy-traits-design-patterns-and-best-practice-book/
        # https://www.juliabloggers.com/the-emergent-features-of-julialang-part-ii-traits/

        # The traits, orthogonal to the type hierarchy of the actual data.
        # Here we have just one.
        class FlippabilityTrait:
            pass
        class IsFlippable(FlippabilityTrait):
            pass
        class IsNotFlippable(FlippabilityTrait):
            pass

        # Mapping of concrete types to traits. This is the extensible part.
        @generic
        def flippable(x: typing.Any):  # default
            raise NotImplementedError(f"`flippable` trait not registered for any type specification matching {type(x)}")

        # Since these are in the same lexical scope as the original definition of the
        # generic function `flippable`, we could do this using `@generic`, but
        # later extensions (which are the whole point of traits) will need to specify
        # on which function the new methods are to be registered, using `@augment`.
        # So let's do that to show how it's done.
        @augment(flippable)
        def flippable(x: str):  # noqa: F811
            return IsFlippable()
        @augment(flippable)
        def flippable(x: int):  # noqa: F811
            return IsNotFlippable()

        # Trait-based dispatcher for the operation `flip`, implemented as a
        # generic function. The dispatcher maps the concrete type of `x` to
        # the desired trait (relevant to that particular operation), while
        # passing the value `x` itself along.
        #
        # The "flip" operation is just a silly example of something that is
        # applicable to "flippable" objects but not to "nonflippable" ones.
        @generic
        def flip(x: typing.Any):
            return flip(flippable(x), x)

        # Implementation of `flip`. Same comment about `@augment` as above.
        #
        # Here we provide one implementation for "flippable" objects and another one
        # for "nonflippable" objects. Note this dispatches regardless of the actual
        # data type of `x`, and particularly, does not care which class hierarchy
        # `type(x)` belongs to, as long as it has been registered to the relevant trait.
        #
        # We could also add methods for specific types if needed. Note this is not
        # Julia, so the first matching definition wins, instead of the most specific
        # one.
        @augment(flip)
        def flip(traitvalue: IsFlippable, x: typing.Any):  # noqa: F811
            return x[::-1]
        @augment(flip)
        def flip(traitvalue: IsNotFlippable, x: typing.Any):  # noqa: F811
            raise TypeError(f"{repr(x)} is IsNotFlippable")

        test[flip("abc") == "cba"]
        test_raises[TypeError, flip(42), "int should not be flippable"]
        test_raises[NotImplementedError, flip(2.0), "float should not be registered for the flippable trait"]

if __name__ == '__main__':  # pragma: no cover
    with session(__file__):
        runtests()
