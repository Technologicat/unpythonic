# -*- coding: utf-8; -*-

import typing
from ..typecheck import match_value_to_typespec as matcht

def test():
    # a concrete type
    assert matcht(17, int)
    assert matcht("hello", str)
    assert not matcht(17, str)

    # a callable
    assert matcht(lambda: ..., typing.Callable)
    assert not matcht("blah", typing.Callable)

    # typing.Any (i.e. explicitly say "don't care")
    assert matcht(5, typing.Any)
    assert matcht("something", typing.Any)
    assert matcht(lambda: ..., typing.Any)

    # TypeVar, bare; a named type, but behaves like Any.
    X = typing.TypeVar("X")
    assert matcht(3.14, X)
    assert matcht("anything", X)
    assert matcht(lambda: ..., X)

    # TypeVar, with arguments; matches only the specs in the constraints.
    Number = typing.TypeVar("Number", int, float, complex)
    assert matcht(31337, Number)
    assert matcht(3.14159, Number)
    assert matcht(1 + 2j, Number)
    assert not matcht("blargh", Number)

    Silly = typing.TypeVar("Silly", int, typing.Callable)
    assert matcht(123456, Silly)
    assert matcht(lambda: ..., Silly)
    assert not matcht(3.14, Silly)

    # typing.Union
    assert matcht(23, typing.Union[int, str])
    assert matcht("hello again", typing.Union[int, str])
    assert not matcht(3.14, typing.Union[int, str])

    # typing.Optional
    assert matcht(None, typing.Optional[int])
    assert matcht(1337, typing.Optional[int])
    assert not matcht(3.14, typing.Optional[int])

    # typing.Tuple
    assert matcht((1, 2, 3), typing.Tuple)
    assert matcht((1, 2, 3), typing.Tuple[int, ...])
    assert matcht((1, 2.1, "footgun"), typing.Tuple[int, float, str])
    assert not matcht((1.1, 2.2, 3.3), typing.Tuple[int, ...])
    assert not matcht((1, 2.1, 9001), typing.Tuple[int, float, str])
    assert matcht((), typing.Tuple)
    assert matcht((), typing.Tuple[int, ...])  # empty tuple matches a homogeneous tuple of any element type
    assert matcht((), typing.Tuple[float, ...])

    # type alias (at run time, this is just an assignment)
    U = typing.Union[int, str]
    assert matcht(42, U)
    assert matcht("hello yet again", U)
    assert not matcht(3.14, U)

    # Text (in Python 3, alias of str)
    assert matcht("hi", typing.Text)
    assert not matcht(42, typing.Text)

    # AnyStr
    assert matcht("hi", typing.AnyStr)
    assert matcht(b"hi", typing.AnyStr)
    assert not matcht(42, typing.AnyStr)

    print("All tests PASSED")

if __name__ == '__main__':
    test()
