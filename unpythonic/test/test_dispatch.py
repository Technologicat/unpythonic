# -*- coding: utf-8; -*-

import typing
from ..dispatch import generic, specific

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

# One-method pony.
@specific
def blubnify(x: int, y: float):
    return x * y

@specific
def gargle(x: typing.Union[int, str]):
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

    assert blubnify(2, 21.0) == 42
    try:
        blubnify(2, 3)
    except TypeError:
        pass
    else:
        assert False  # blubnify only accepts (int, float)
    assert not hasattr(blubnify, "register")  # and no more methods can be registered on it

    assert gargle(42) == 42
    assert gargle("foo") == "foo"
    try:
        gargle(3.14)
    except TypeError:
        pass
    else:
        assert False  # gargle only accepts int or str

    print("All tests PASSED")

if __name__ == '__main__':
    test()
