# -*- coding: utf-8; -*-

from ..syntax import macros, test, test_raises, warn  # noqa: F401
from ..test.fixtures import session, testset

import asyncio
import collections
import contextlib
import io
import re
import sys
import typing

from ..collections import frozendict
from ..typecheck import isoftype

def runtests():
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

    # NoReturn / Never — the bottom type; no value can match.
    with testset("typing.NoReturn"):
        test[not isoftype(None, typing.NoReturn)]
        test[not isoftype(42, typing.NoReturn)]
        test[not isoftype("anything", typing.NoReturn)]

    if sys.version_info >= (3, 11):
        with testset("typing.Never"):
            test[not isoftype(None, typing.Never)]
            test[not isoftype(42, typing.Never)]

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
        test[isoftype(1 + 2j, Number)]
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

    with testset("typing.Literal"):
        test[isoftype(1, typing.Literal[1, 2, 3])]
        test[isoftype(3, typing.Literal[1, 2, 3])]
        test[not isoftype(4, typing.Literal[1, 2, 3])]
        test[isoftype("red", typing.Literal["red", "green", "blue"])]
        test[not isoftype("yellow", typing.Literal["red", "green", "blue"])]
        # Literal values are compared by equality, not identity
        test[isoftype(True, typing.Literal[True, False])]
        test[not isoftype(None, typing.Literal[True, False])]

    with testset("typing.Type"):
        test[isoftype(int, typing.Type[int])]
        test[isoftype(bool, typing.Type[int])]  # bool is a subclass of int
        test[not isoftype(str, typing.Type[int])]
        test[not isoftype(42, typing.Type[int])]  # an instance, not a class
        # bare Type: any class matches
        test[isoftype(int, typing.Type)]
        test[isoftype(str, typing.Type)]
        test[not isoftype(42, typing.Type)]

    with testset("typing.ClassVar"):
        test[isoftype(42, typing.ClassVar[int])]
        test[not isoftype("hello", typing.ClassVar[int])]
        # Compound: ClassVar wrapping a Union
        test[isoftype(42, typing.ClassVar[typing.Union[int, str]])]
        test[isoftype("hello", typing.ClassVar[typing.Union[int, str]])]
        test[not isoftype(3.14, typing.ClassVar[typing.Union[int, str]])]

    with testset("typing.Final"):
        test[isoftype(42, typing.Final[int])]
        test[not isoftype("hello", typing.Final[int])]
        test[isoftype("hello", typing.Final[str])]

    # Empty collections reject parametric type specs (e.g. `Tuple[int, ...]`,
    # `List[int]`, `Dict[str, int]`). An empty collection has no elements to
    # infer the type from, so matching it against a specific element type would
    # be guesswork — which would make multiple dispatch unpredictable.
    # Bare (unparametrized) specs like `Tuple` or `Dict` still accept empties.

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

    with testset("typing.DefaultDict"):
        dd = collections.defaultdict(int, {"a": 1, "b": 2})
        test[isoftype(dd, typing.DefaultDict[str, int])]
        test[not isoftype(dd, typing.DefaultDict[int, int])]
        test[not isoftype({}, typing.DefaultDict[str, int])]  # regular dict is not defaultdict
        test[not isoftype(collections.defaultdict(int), typing.DefaultDict[str, int])]  # empty

    with testset("typing.OrderedDict"):
        od = collections.OrderedDict({"x": 1, "y": 2})
        test[isoftype(od, typing.OrderedDict[str, int])]
        test[not isoftype(od, typing.OrderedDict[int, int])]
        test[not isoftype({}, typing.OrderedDict[str, int])]  # regular dict is not OrderedDict
        test[not isoftype(collections.OrderedDict(), typing.OrderedDict[str, int])]  # empty

    with testset("typing.Counter"):
        c = collections.Counter("abracadabra")
        test[isoftype(c, typing.Counter[str])]
        test[not isoftype(c, typing.Counter[int])]
        test[not isoftype({}, typing.Counter[str])]  # regular dict is not Counter
        test[not isoftype(collections.Counter(), typing.Counter[str])]  # empty

    with testset("typing.ChainMap"):
        cm = collections.ChainMap({"a": 1}, {"b": 2})
        test[isoftype(cm, typing.ChainMap[str, int])]
        test[not isoftype(cm, typing.ChainMap[int, int])]
        test[not isoftype({}, typing.ChainMap[str, int])]  # regular dict is not ChainMap
        test[not isoftype(collections.ChainMap(), typing.ChainMap[str, int])]  # empty

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
        test[isoftype(b"hi", typing.AnyStr)]
        test[not isoftype(42, typing.AnyStr)]

    with testset("typing.ByteString (bytes, bytearray, memoryview)"):
        test[isoftype(b"hi", typing.ByteString)]

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

    with testset("typing.IO, typing.TextIO, typing.BinaryIO"):
        sio = io.StringIO("hello")
        bio = io.BytesIO(b"hello")
        test[isoftype(sio, typing.IO)]
        test[isoftype(bio, typing.IO)]
        test[isoftype(sio, typing.TextIO)]
        test[not isoftype(bio, typing.TextIO)]
        test[isoftype(bio, typing.BinaryIO)]
        test[not isoftype(sio, typing.BinaryIO)]
        test[not isoftype(42, typing.IO)]
        # Parametric IO: IO[str] matches text, IO[bytes] matches binary
        test[isoftype(sio, typing.IO[str])]
        test[not isoftype(bio, typing.IO[str])]
        test[isoftype(bio, typing.IO[bytes])]
        test[not isoftype(sio, typing.IO[bytes])]

    with testset("typing.Pattern, typing.Match"):
        pstr = re.compile(r"\d+")
        pbytes = re.compile(rb"\d+")
        mstr = pstr.match("123")
        mbytes = pbytes.match(b"123")
        # Bare Pattern/Match — any string type
        test[isoftype(pstr, typing.Pattern)]
        test[isoftype(pbytes, typing.Pattern)]
        test[isoftype(mstr, typing.Match)]
        test[isoftype(mbytes, typing.Match)]
        test[not isoftype("not a pattern", typing.Pattern)]
        test[not isoftype(42, typing.Match)]
        # Parametric — string type checked
        test[isoftype(pstr, typing.Pattern[str])]
        test[not isoftype(pstr, typing.Pattern[bytes])]
        test[isoftype(pbytes, typing.Pattern[bytes])]
        test[not isoftype(pbytes, typing.Pattern[str])]
        test[isoftype(mstr, typing.Match[str])]
        test[not isoftype(mstr, typing.Match[bytes])]
        test[isoftype(mbytes, typing.Match[bytes])]
        test[not isoftype(mbytes, typing.Match[str])]

    with testset("typing.ContextManager"):
        # contextlib.nullcontext is a context manager
        cm = contextlib.nullcontext()
        test[isoftype(cm, typing.ContextManager)]
        test[isoftype(cm, typing.ContextManager[None])]  # type arg ignored (can't check)
        test[not isoftype(42, typing.ContextManager)]

    with testset("typing.Generator"):
        def mygen():
            yield 1
            yield 2
        g = mygen()
        test[isoftype(g, typing.Generator)]
        test[isoftype(g, typing.Generator[int, None, None])]  # type args ignored
        test[not isoftype(42, typing.Generator)]
        test[not isoftype([1, 2, 3], typing.Generator)]  # iterable, but not a generator

    with testset("typing.Awaitable, typing.Coroutine"):
        async def mycoro():
            return 42
        c = mycoro()
        test[isoftype(c, typing.Awaitable)]
        test[isoftype(c, typing.Coroutine)]
        test[isoftype(c, typing.Awaitable[int])]  # type arg ignored
        test[not isoftype(42, typing.Awaitable)]
        test[not isoftype(42, typing.Coroutine)]
        c.close()  # prevent RuntimeWarning about unawaited coroutine

    with testset("typing.AsyncIterable, typing.AsyncIterator"):
        class MyAsyncIter:
            def __aiter__(self):
                return self
            async def __anext__(self):
                raise StopAsyncIteration
        ai = MyAsyncIter()
        test[isoftype(ai, typing.AsyncIterable)]
        test[isoftype(ai, typing.AsyncIterator)]
        test[isoftype(ai, typing.AsyncIterable[int])]  # type arg ignored
        test[not isoftype(42, typing.AsyncIterable)]
        test[not isoftype([1, 2], typing.AsyncIterator)]  # sync iterable, not async

    with testset("typing.AsyncGenerator"):
        async def myasyncgen():
            yield 1
        ag = myasyncgen()
        test[isoftype(ag, typing.AsyncGenerator)]
        test[isoftype(ag, typing.AsyncGenerator[int, None])]  # type args ignored
        test[not isoftype(42, typing.AsyncGenerator)]
        asyncio.run(ag.aclose())  # prevent RuntimeWarning

if __name__ == '__main__':  # pragma: no cover
    with session(__file__):
        runtests()
