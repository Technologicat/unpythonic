# -*- coding: utf-8; -*-

import typing
from ..fun import curry
from ..dispatch import generic, typed

@generic
def zorblify():  # could use the ellipsis `...` as the body, but this is a unit test.
    assert False  # Stub, not called.
@zorblify.register
def zorblify(x: int, y: int):
    return 2 * x + y
@zorblify.register
def zorblify(x: str, y: int):
    assert False  # Because dispatching occurs on both arguments, this is not reached in tests.
@zorblify.register
def zorblify(x: str, y: float):
    return "{} {}".format(x[::-1], y)

# TODO: def zorblify(x: int, *args: typing.Sequence[str]):

# @generic can also be used to simplify argument handling code in functions
# where the role of an argument in a particular position changes depending on
# the number of arguments (like the range() builtin).
#
# The pattern is that the generic function canonizes the arguments:
@generic
def example(): ...
@example.register
def example(start: int, stop: int):
    return _example_impl(start, 1, stop)
@example.register
def example(start: int, step: int, stop: int):
    return _example_impl(start, step, stop)
# ...after which the actual implementation always gets them in the same format.
def _example_impl(start, step, stop):
    return start, step, stop

# shorter, same effect
@generic
def example2(): ...
@example2.register
def example2(start: int, stop: int):
    return example2(start, 1, stop)  # just call the method that has the implementation
@example2.register
def example2(start: int, step: int, stop: int):
    return start, step, stop

# varargs are supported via `typing.Tuple`
@generic
def gargle(): ...
@gargle.register
def gargle(*args: typing.Tuple[int, ...]):  # any number of ints
    return "int"
@gargle.register
def gargle(*args: typing.Tuple[float, ...]):  # any number of floats
    return "float"
@gargle.register
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

def test():
    assert zorblify(17, 8) == 42
    assert zorblify(17, y=8) == 42  # can also use named arguments
    assert zorblify(y=8, x=17) == 42
    assert zorblify("tac", 1.0) == "cat 1.0"
    assert zorblify(y=1.0, x="tac") == "cat 1.0"

    try:
        zorblify(1.0, 2.0)
    except TypeError:
        pass
    else:
        assert False  # there's no zorblify(float, float)

    assert example(1, 5) == (1, 1, 5)
    assert example(1, 1, 5) == (1, 1, 5)
    assert example(1, 2, 5) == (1, 2, 5)

    assert example2(1, 5) == (1, 1, 5)
    assert example2(1, 1, 5) == (1, 1, 5)
    assert example2(1, 2, 5) == (1, 2, 5)

    assert gargle(1, 2, 3, 4, 5) == "int"
    assert gargle(2.71828, 3.14159) == "float"
    assert gargle(42, 6.022e23, "hello") == "int, float, str"
    assert gargle(1, 2, 3) == "int"  # as many as in the [int, float, str] case

    assert blubnify(2, 21.0) == 42
    try:
        blubnify(2, 3)
    except TypeError:
        pass
    else:
        assert False  # blubnify only accepts (int, float)
    assert not hasattr(blubnify, "register")  # and no more methods can be registered on it

    assert jack(42) == 42
    assert jack("foo") == "foo"
    try:
        jack(3.14)
    except TypeError:
        pass
    else:
        assert False  # jack only accepts int or str

    # integration: @typed, curry
    f = curry(blubnify, 2)
    assert callable(f)
    assert f(21.0) == 42

    # But be careful:
    f = curry(blubnify, 2.0)  # wrong argument type; error not triggered yet
    assert callable(f)
    try:
        assert f(21.0) == 42  # error will occur now, when the call is triggered
    except TypeError:
        pass
    else:
        assert False  # should have noticed incompatible argument types

    print("All tests PASSED")

if __name__ == '__main__':
    test()
