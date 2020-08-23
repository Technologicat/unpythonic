# -*- coding: utf-8; -*-

from ..syntax import macros, test, test_raises, warn  # noqa: F401
from .fixtures import session, testset

import collections
import typing

from ..collections import frozendict
from ..typecheck import isoftype

def runtests():
    warn["Some tests in this module disabled due to https://github.com/azazel75/macropy/issues/26"]  # TODO/FIXME

    with testset("concrete type"):
        test[isoftype(17, int)]
        test[isoftype("hello", str)]
        test[not isoftype(17, str)]

    with testset("callable"):
        test[isoftype(lambda: ..., typing.Callable)]
        test[not isoftype("blah", typing.Callable)]

    with testset("typing.NewType"):
        UserId = typing.NewType("UserId", int)
        test[isoftype(UserId(42), UserId)]
        # Note limitation: since NewType types discard their type information at
        # run time, any instance of the underlying actual run-time type will match.
        test[isoftype(42, UserId)]

    # typing.Any (i.e. explicitly say "don't care")
    with testset("typing.Any"):
        test[isoftype(5, typing.Any)]
        test[isoftype("something", typing.Any)]
        test[isoftype(lambda: ..., typing.Any)]

    # TypeVar, bare; a named type, but behaves like Any.
    with testset("typing.TypeVar (bare; like a named Any)"):
        X = typing.TypeVar("X")
        test[isoftype(3.14, X)]
        test[isoftype("anything", X)]
        test[isoftype(lambda: ..., X)]

    # TypeVar, with arguments; matches only the specs in the constraints.
    with testset("typing.TypeVar (with arguments; constrained)"):
        Number = typing.TypeVar("Number", int, float, complex)
        test[isoftype(31337, Number)]
        test[isoftype(3.14159, Number)]
        # test[isoftype(1 + 2j, Number)]  # TODO/FIXME: MacroPy 1.1.0b2 breaks on complex numbers
        test[not isoftype("blargh", Number)]

        Silly = typing.TypeVar("Silly", int, typing.Callable)
        test[isoftype(123456, Silly)]
        test[isoftype(lambda: ..., Silly)]
        test[not isoftype(3.14, Silly)]

    with testset("typing.Union"):
        test[isoftype(23, typing.Union[int, str])]
        test[isoftype("hello again", typing.Union[int, str])]
        test[not isoftype(3.14, typing.Union[int, str])]
        # The bare Union (no args) is empty, it has no types in it, so no value can match.
        test[not isoftype(23, typing.Union)]
        test[not isoftype("hello again", typing.Union)]
        test[not isoftype(3.14, typing.Union)]
        test[not isoftype(None, typing.Union)]

    with testset("typing.Optional"):
        test[isoftype(None, typing.Optional[int])]
        test[isoftype(1337, typing.Optional[int])]
        test[not isoftype(3.14, typing.Optional[int])]

    with testset("typing.Tuple"):
        test[isoftype((1, 2, 3), typing.Tuple)]
        test[isoftype((1, 2, 3), typing.Tuple[int, ...])]
        test[isoftype((1, 2.1, "footgun"), typing.Tuple[int, float, str])]
        test[not isoftype((1.1, 2.2, 3.3), typing.Tuple[int, ...])]
        test[not isoftype((1, 2.1, 9001), typing.Tuple[int, float, str])]
        test[isoftype((), typing.Tuple)]
        test[not isoftype((), typing.Tuple[int, ...])]  # empty tuple has no element type
        test[not isoftype((), typing.Tuple[float, ...])]
        test[not isoftype([1, 2, 3], typing.Tuple)]  # list is not tuple

    with testset("typing.List"):
        test[isoftype([1, 2, 3], typing.List[int])]
        test[not isoftype([1, 2, 3], typing.List[float])]
        test[not isoftype((1, 2, 3), typing.List[int])]  # it's a tuple, silly
        test[not isoftype(42, typing.List[int])]  # try something that's not even a collection

    with testset("typing.Set"):
        test[isoftype({"cat", "fox", "python"}, typing.Set[str])]
        test[not isoftype({1, 2, 3}, typing.Set[str])]
        test[not isoftype(42, typing.Set[str])]

    with testset("typing.FrozenSet"):
        test[isoftype(frozenset({"cat", "fox", "python"}), typing.FrozenSet[str])]
        test[not isoftype(frozenset({1, 2, 3}), typing.FrozenSet[str])]
        test[not isoftype(42, typing.FrozenSet[str])]

    with testset("typing.Dict"):
        test[isoftype({17: "cat", 23: "fox", 42: "python"}, typing.Dict[int, str])]
        test[not isoftype({"bar": "foo", "tavern": "a place"}, typing.Dict[int, str])]
        test[not isoftype(42, typing.Dict[int, str])]
        # no type arguments: any key/value types ok (consistent with Python 3.7+)
        test[isoftype({"cat": "animal", "pi": 3.14159, 2.71828: "e"}, typing.Dict)]

    # type alias (at run time, this is just an assignment)
    with testset("type alias"):
        U = typing.Union[int, str]
        test[isoftype(42, U)]
        test[isoftype("hello yet again", U)]
        test[not isoftype(3.14, U)]

    # typing.Text (in Python 3, alias of str)
    with testset("typing.Text"):
        test[isoftype("hi", typing.Text)]
        test[not isoftype(42, typing.Text)]

    with testset("typing.AnyStr"):
        test[isoftype("hi", typing.AnyStr)]
        # test[isoftype(b"hi", typing.AnyStr)]  # TODO/FIXME: MacroPy 1.1.0b2 breaks on bytestrings
        test[not isoftype(42, typing.AnyStr)]

    # TODO: FIXME: MacroPy 1.1.0b2 breaks on bytestrings
    # with testset("typing.ByteString (bytes, bytearray, memoryview)"):
    #     test[isoftype(b"hi", typing.ByteString)]

    with testset("collections.deque"):
        d = collections.deque()
        test[not isoftype(d, typing.Deque[int])]  # empty deque has no element type
        d.append(42)
        test[isoftype(d, typing.Deque[int])]
        test[not isoftype(d, typing.Deque[float])]

    with testset("typing.Mapping, typing.MutableMapping"):
        test[isoftype(frozendict({1: "foo", 2: "bar"}), typing.Mapping[int, str])]
        test[not isoftype(frozendict({1: "foo", 2: "bar"}), typing.MutableMapping[int, str])]
        test[not isoftype(frozendict({1: "foo", 2: "bar"}), typing.Mapping[str, str])]
        test[isoftype({1: "foo", 2: "bar"}, typing.MutableMapping[int, str])]
        test[not isoftype(42, typing.Mapping[int, str])]
        # empty mapping has no key/value types
        test[not isoftype({}, typing.MutableMapping[int, str])]
        test[not isoftype({}, typing.Mapping[int, str])]
        test[not isoftype(frozendict(), typing.Mapping[int, str])]

    with testset("typing.Sequence, typing.MutableSequence"):
        test[not isoftype((), typing.Sequence[int])]  # empty sequence has no element type
        test[isoftype((1, 2, 3), typing.Sequence[int])]
        test[not isoftype((1, 2, 3), typing.Sequence[float])]
        test[not isoftype((1, 2, 3), typing.MutableSequence[int])]
        test[isoftype([1, 2, 3], typing.Sequence[int])]
        test[isoftype([1, 2, 3], typing.MutableSequence[int])]
        test[not isoftype([], typing.MutableSequence[int])]  # empty mutable sequence has no element type
        test[not isoftype([1, 2, 3], typing.MutableSequence[float])]
        test[not isoftype(42, typing.Sequence[int])]
        test[not isoftype(42, typing.MutableSequence[int])]

    with testset("typing.AbstractSet, typing.MutableSet"):
        test[isoftype({1, 2, 3}, typing.AbstractSet[int])]
        test[isoftype({1, 2, 3}, typing.MutableSet[int])]
        test[not isoftype({1, 2, 3}, typing.AbstractSet[float])]
        test[isoftype(frozenset({1, 2, 3}), typing.AbstractSet[int])]
        test[not isoftype(frozenset({1, 2, 3}), typing.MutableSet[int])]
        test[not isoftype(42, typing.AbstractSet[int])]
        test[not isoftype(42, typing.MutableSet[int])]

    with testset("one-trick pony ABCs"):
        test[isoftype(3.14, typing.SupportsInt)]
        # test[isoftype(3.14, typing.SupportsComplex)]  # ehm, WTF?
        test[isoftype(3.14, typing.SupportsAbs)]
        test[isoftype(3.14, typing.SupportsRound)]
        test[isoftype(42, typing.SupportsFloat)]
        test[isoftype((1, 2, 3), typing.Sized)]
        test[isoftype((1, 2, 3), typing.Hashable)]
        test[isoftype([1, 2, 3], typing.Sized)]
        test[not isoftype([1, 2, 3], typing.Hashable)]
        # TODO: test SupportsComplex, SupportsBytes

        # For these it's impossible, in general, to non-destructively check the
        # element type, so this run-time type checker ignores making that check.
        # It only checks that the value is an instance of the appropriate ABC.
        test[isoftype(iter([1, 2, 3]), typing.Iterator)]
        test[isoftype([1, 2, 3], typing.Iterable)]
        test[isoftype([1, 2, 3], typing.Reversible)]
        test[isoftype([1, 2, 3], typing.Container)]
        if hasattr(typing, "Collection"):  # Python 3.6+
            test[isoftype([1, 2, 3], typing.Collection)]  # Sized Iterable Container

    with testset("typing.KeysView, typing.ValuesView, typing.ItemsView"):
        d = {17: "cat", 23: "fox", 42: "python"}
        test[isoftype(d.keys(), typing.KeysView[int])]
        test[isoftype(d.values(), typing.ValuesView[str])]
        test[isoftype(d.items(), typing.ItemsView[int, str])]

        # no type arguments: any key/value types ok (consistent with Python 3.7+)
        test[isoftype(d.keys(), typing.KeysView)]
        test[isoftype(d.values(), typing.ValuesView)]
        test[isoftype(d.items(), typing.ItemsView)]

        test[not isoftype("hello", typing.ItemsView)]
        test[not isoftype({}.items(), typing.ItemsView[int, str])]  # empty dict has no key, value types

        # TODO: test MappingView
        # OTOH, do we need to? It seems it's just an ABC for the other three.
        #  https://docs.python.org/3/library/typing.html#typing.MappingView
        #  https://docs.python.org/3/library/collections.abc.html#collections.abc.MappingView
        #  https://docs.python.org/3/glossary.html#term-dictionary-view
        #  https://docs.python.org/3/library/stdtypes.html#dict-views

if __name__ == '__main__':  # pragma: no cover
    with session(__file__):
        runtests()
