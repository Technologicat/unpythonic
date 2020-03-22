# -*- coding: utf-8; -*-

import collections
import typing

from ..collections import frozendict
from ..typecheck import isoftype

def test():
    # a concrete type
    assert isoftype(17, int)
    assert isoftype("hello", str)
    assert not isoftype(17, str)

    # a callable
    assert isoftype(lambda: ..., typing.Callable)
    assert not isoftype("blah", typing.Callable)

    # typing.NewType
    UserId = typing.NewType("UserId", int)
    assert isoftype(UserId(42), UserId)
    # Note limitation: since NewType types discard their type information at
    # run time, any instance of the underlying actual run-time type will match.
    assert isoftype(42, UserId)

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

    # typing.List
    assert isoftype([1, 2, 3], typing.List[int])
    assert not isoftype([1, 2, 3], typing.List[float])
    assert not isoftype((1, 2, 3), typing.List[int])  # it's a tuple, silly
    assert not isoftype(42, typing.List[int])  # try something that's not even a collection

    # typing.Set
    assert isoftype({"cat", "fox", "python"}, typing.Set[str])
    assert not isoftype({1, 2, 3}, typing.Set[str])
    assert not isoftype(42, typing.Set[str])

    # typing.FrozenSet
    assert isoftype(frozenset({"cat", "fox", "python"}), typing.FrozenSet[str])
    assert not isoftype(frozenset({1, 2, 3}), typing.FrozenSet[str])
    assert not isoftype(42, typing.FrozenSet[str])

    # typing.Dict
    assert isoftype({17: "cat", 23: "fox", 42: "python"}, typing.Dict[int, str])
    assert not isoftype({"bar": "foo", "tavern": "a place"}, typing.Dict[int, str])
    assert not isoftype(42, typing.Dict[int, str])

    # type alias (at run time, this is just an assignment)
    U = typing.Union[int, str]
    assert isoftype(42, U)
    assert isoftype("hello yet again", U)
    assert not isoftype(3.14, U)

    # typing.Text (in Python 3, alias of str)
    assert isoftype("hi", typing.Text)
    assert not isoftype(42, typing.Text)

    # typing.AnyStr
    assert isoftype("hi", typing.AnyStr)
    assert isoftype(b"hi", typing.AnyStr)
    assert not isoftype(42, typing.AnyStr)

    # typing.ByteString (bytes, bytearray, memoryview)
    assert isoftype(b"hi", typing.ByteString)

    # collections.deque
    d = collections.deque()
    assert not isoftype(d, typing.Deque[int])  # empty deque has no element type
    d.append(42)
    assert isoftype(d, typing.Deque[int])
    assert not isoftype(d, typing.Deque[float])

    # typing.Mapping, typing.MutableMapping
    assert isoftype(frozendict({1: "foo", 2: "bar"}), typing.Mapping[int, str])
    assert not isoftype(frozendict({1: "foo", 2: "bar"}), typing.MutableMapping[int, str])
    assert not isoftype(frozendict({1: "foo", 2: "bar"}), typing.Mapping[str, str])
    assert isoftype({1: "foo", 2: "bar"}, typing.MutableMapping[int, str])
    assert not isoftype(42, typing.Mapping[int, str])
    # empty mapping has no key/value types
    assert not isoftype({}, typing.MutableMapping[int, str])
    assert not isoftype({}, typing.Mapping[int, str])
    assert not isoftype(frozendict(), typing.Mapping[int, str])

    # typing.Sequence, typing.MutableSequence
    assert not isoftype((), typing.Sequence[int])  # empty sequence has no element type
    assert isoftype((1, 2, 3), typing.Sequence[int])
    assert not isoftype((1, 2, 3), typing.Sequence[float])
    assert not isoftype((1, 2, 3), typing.MutableSequence[int])
    assert isoftype([1, 2, 3], typing.Sequence[int])
    assert isoftype([1, 2, 3], typing.MutableSequence[int])
    assert not isoftype([], typing.MutableSequence[int])  # empty mutable sequence has no element type
    assert not isoftype([1, 2, 3], typing.MutableSequence[float])
    assert not isoftype(42, typing.Sequence[int])
    assert not isoftype(42, typing.MutableSequence[int])

    # typing.AbstractSet, typing.MutableSet
    assert isoftype({1, 2, 3}, typing.AbstractSet[int])
    assert isoftype({1, 2, 3}, typing.MutableSet[int])
    assert not isoftype({1, 2, 3}, typing.AbstractSet[float])
    assert isoftype(frozenset({1, 2, 3}), typing.AbstractSet[int])
    assert not isoftype(frozenset({1, 2, 3}), typing.MutableSet[int])
    assert not isoftype(42, typing.AbstractSet[int])
    assert not isoftype(42, typing.MutableSet[int])

    # one-trick ponies
    assert isoftype(3.14, typing.SupportsInt)
    # assert isoftype(3.14, typing.SupportsComplex)  # ehm, WTF?
    assert isoftype(3.14, typing.SupportsAbs)
    assert isoftype(3.14, typing.SupportsRound)
    assert isoftype(42, typing.SupportsFloat)
    assert isoftype((1, 2, 3), typing.Sized)
    assert isoftype((1, 2, 3), typing.Hashable)
    assert isoftype([1, 2, 3], typing.Sized)
    assert not isoftype([1, 2, 3], typing.Hashable)
    # TODO: test SupportsComplex, SupportsBytes

    # For these it's impossible, in general, to non-destructively check the
    # element type, so this run-time type checker ignores making that check.
    # It only checks that the value is an instance of the appropriate ABC.
    assert isoftype(iter([1, 2, 3]), typing.Iterator)
    assert isoftype([1, 2, 3], typing.Iterable)
    assert isoftype([1, 2, 3], typing.Reversible)
    assert isoftype([1, 2, 3], typing.Container)
    assert isoftype([1, 2, 3], typing.Collection)  # Sized Iterable Container

    # KeysView, ValuesView, MappingView, ItemsView
    d = {17: "cat", 23: "fox", 42: "python"}
    assert isoftype(d.keys(), typing.KeysView[int])
    assert isoftype(d.values(), typing.ValuesView[str])
    assert isoftype(d.items(), typing.ItemsView[int, str])

    # TODO: test MappingView
    # The language docs don't exactly make it clear what MappingView is for.
    # All these documentation pages only talk about `.keys()`, `.values()`
    # and `.items()`, which correspond to the other three view types.
    #  https://docs.python.org/3/library/typing.html#typing.MappingView
    #  https://docs.python.org/3/library/collections.abc.html#collections.abc.MappingView
    #  https://docs.python.org/3/glossary.html#term-dictionary-view
    #  https://docs.python.org/3/library/stdtypes.html#dict-views

    print("All tests PASSED")

if __name__ == '__main__':
    test()
