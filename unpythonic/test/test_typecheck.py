# -*- coding: utf-8; -*-

import typing
from ..typecheck import isoftype

def test():
    # a concrete type
    assert isoftype(17, int)
    assert isoftype("hello", str)
    assert not isoftype(17, str)

    # a callable
    assert isoftype(lambda: ..., typing.Callable)
    assert not isoftype("blah", typing.Callable)

    # typing.Any (i.e. explicitly say "don't care")
    assert isoftype(5, typing.Any)
    assert isoftype("something", typing.Any)
    assert isoftype(lambda: ..., typing.Any)

    # TypeVar, bare; a named type, but behaves like Any.
    X = typing.TypeVar("X")
    assert isoftype(3.14, X)
    assert isoftype("anything", X)
    assert isoftype(lambda: ..., X)

    # TypeVar, with arguments; matches only the specs in the constraints.
    Number = typing.TypeVar("Number", int, float, complex)
    assert isoftype(31337, Number)
    assert isoftype(3.14159, Number)
    assert isoftype(1 + 2j, Number)
    assert not isoftype("blargh", Number)

    Silly = typing.TypeVar("Silly", int, typing.Callable)
    assert isoftype(123456, Silly)
    assert isoftype(lambda: ..., Silly)
    assert not isoftype(3.14, Silly)

    # typing.Union
    assert isoftype(23, typing.Union[int, str])
    assert isoftype("hello again", typing.Union[int, str])
    assert not isoftype(3.14, typing.Union[int, str])

    # typing.Optional
    assert isoftype(None, typing.Optional[int])
    assert isoftype(1337, typing.Optional[int])
    assert not isoftype(3.14, typing.Optional[int])

    # typing.Tuple
    assert isoftype((1, 2, 3), typing.Tuple)
    assert isoftype((1, 2, 3), typing.Tuple[int, ...])
    assert isoftype((1, 2.1, "footgun"), typing.Tuple[int, float, str])
    assert not isoftype((1.1, 2.2, 3.3), typing.Tuple[int, ...])
    assert not isoftype((1, 2.1, 9001), typing.Tuple[int, float, str])
    assert isoftype((), typing.Tuple)
    assert not isoftype((), typing.Tuple[int, ...])  # empty tuple has no element type
    assert not isoftype((), typing.Tuple[float, ...])

    # type alias (at run time, this is just an assignment)
    U = typing.Union[int, str]
    assert isoftype(42, U)
    assert isoftype("hello yet again", U)
    assert not isoftype(3.14, U)

    # Text (in Python 3, alias of str)
    assert isoftype("hi", typing.Text)
    assert not isoftype(42, typing.Text)

    # AnyStr
    assert isoftype("hi", typing.AnyStr)
    assert isoftype(b"hi", typing.AnyStr)
    assert not isoftype(42, typing.AnyStr)

    print("All tests PASSED")

if __name__ == '__main__':
    test()
