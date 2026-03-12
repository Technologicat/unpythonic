# -*- coding: utf-8; -*-
"""Lightweight run-time type checker.

Originally built for the minimal feature set needed by multiple dispatch
(see `unpythonic.dispatch`), but designed as a general-purpose utility.
Supports many (but not all) features of the `typing` stdlib module.

We currently provide `isoftype` (cf. `isinstance`), but no `issubtype` (cf. `issubclass`).

If you need a run-time type checker, but not the other features of `unpythonic`,
see `typeguard`:

    https://github.com/agronholm/typeguard
"""

import collections
import contextlib
import io
import re
import sys
import types
import typing

from .misc import safeissubclass

__all__ = ["isoftype"]

def isoftype(value, T):
    """Perform a type check at run time.

    Like `isinstance`, but check `value` against a *type specification* `T`.

        value: The run-time value whose type to check.

        T:     When `T` is a concrete type (e.g. `int`, `somemodule.MyClass`),
               we just delegate to the builtin `isinstance`.

               The interesting case is when `T` is a *type specification*,
               using one of the meta-utilities defined in the `typing` module.
               The most important ones are:

                 - `Any`
                 - `TypeVar`
                 - `NewType` (any instance of the underlying actual type will match)
                 - `Union[T1, T2, ..., TN]`
                 - `NoReturn`, `Never` (no value matches; `Never` requires Python 3.11+)
                 - `Literal[v1, v2, ...]`
                 - `Type[X]` (value must be a class that is `X` or a subclass of `X`)
                 - `ClassVar[T]`, `Final[T]` (wrapper stripped, inner type checked)
                 - `Tuple`, `Tuple[T, ...]`, `Tuple[T1, T2, ..., TN]`, `Sequence[T]`
                 - `List[T]`, `MutableSequence[T]`
                 - `FrozenSet[T]`, `AbstractSet[T]`
                 - `Set[T]`, `MutableSet[T]`
                 - `Dict[K, V]`, `DefaultDict[K, V]`, `OrderedDict[K, V]`
                 - `Counter[T]` (element type checked; value type is always `int`)
                 - `ChainMap[K, V]`
                 - `MutableMapping[K, V]`, `Mapping[K, V]`
                 - `ItemsView[K, V]`, `KeysView[K]`, `ValuesView[V]`
                 - `Callable` (argument and return value types currently NOT checked)
                 - `IO`, `TextIO`, `BinaryIO` (mapped to ``io`` module ABCs)
                 - `Pattern[T]`, `Match[T]` (string type checked when parametric)
                 - `ContextManager[T]`, `AsyncContextManager[T]`
                 - `Awaitable[T]`, `Coroutine[T1, T2, T3]`
                 - `AsyncIterable[T]`, `AsyncIterator[T]`
                 - `Generator[Y, S, R]`, `AsyncGenerator[Y, S]`
                 - `Iterable[T]`, `Collection[T]`, `Reversible[T]` (best-effort element
                   checking: elements checked when value is ``Sized``; ABC-only when not)
                 - `Iterator[T]`, `Container[T]` (parametric form accepted; type arg ignored)
                 - `Hashable`, `Sized` (non-generic; bare form only)
                 - `TypedDict` (structural check: required/optional keys, value types)
                 - ``@runtime_checkable`` ``Protocol`` subclasses
                 - `Text` (deprecated since Python 3.11; will be removed at floor Python 3.12)

               Any checks on the type arguments of the meta-utilities are performed
               recursively using `isoftype`, in order to allow compound specifications.

               Additionally, the following meta-utilities also work, because the
               `typing` module automatically normalizes them into supported ones:

                 - `Optional[T]` (becomes `Union[T, NoneType]`)
                 - `AnyStr` (becomes `TypeVar("AnyStr", str, bytes)`)

    Returns `True` if `value` matches the type specification; `False` if not.
    """
    # Many `typing` meta-utilities explicitly raise TypeError from isinstance/issubclass,
    # so we identify them via typing.get_origin, isinstance checks, or identity comparisons.
    # We also access some internal fields (__args__, __constraints__, __supertype__) where
    # Python provides no official public API for run-time type introspection.
    #
    # Unsupported typing features:
    #   NamedTuple (specific NamedTuple subclasses work via isinstance fallback),
    #   Generic, ForwardRef

    if T is typing.Any:
        return True

    # NoReturn means a function never returns — no value has this type.
    # Never (3.11+) is the bottom type; semantically the same for our purposes.
    if T is typing.NoReturn:
        return False
    if sys.version_info >= (3, 11) and T is typing.Never:
        return False

    # AnyStr normalizes to TypeVar("AnyStr", str, bytes)
    if isinstance(T, typing.TypeVar):
        if not T.__constraints__:  # just an abstract type name
            return True
        return any(isoftype(value, U) for U in T.__constraints__)

    # typing.Union[X, Y] and the builtin X | Y syntax (types.UnionType, Python 3.10+).
    # Optional[X] normalizes to Union[X, NoneType].
    if typing.get_origin(T) is typing.Union or isinstance(T, types.UnionType):
        if not any(isoftype(value, U) for U in T.__args__):
            return False
        return True

    # Bare typing.Union; empty, has no types in it, so no value can match.
    if T is typing.Union:
        return False  # pragma: no cover

    def isNewType(T):
        return isinstance(T, typing.NewType)
    if isNewType(T):
        # This is the best we can do, because the static types created by `typing.NewType`
        # have a constructor that discards the type information at runtime:
        #   UserId = typing.NewType("UserId", int)
        #   i = UserId(42)  # UserId is the identity function, as per `typing` module docs
        #   print(type(i))  # int
        return isinstance(value, T.__supertype__)

    # Literal[v1, v2, ...] — value must be one of the listed constants.
    if typing.get_origin(T) is typing.Literal:
        return value in T.__args__

    # Type[X] — value must be a class that is X or a subclass of X.
    if typing.get_origin(T) is type:
        if not isinstance(value, type):
            return False
        args = getattr(T, "__args__", None)
        if args is None:
            return True  # bare Type, any class matches
        return issubclass(value, args[0])

    # ClassVar[T] and Final[T] — these are declaration wrappers. At runtime,
    # we just strip the wrapper and check the inner type.
    for wrapper_origin in (typing.ClassVar, typing.Final):
        if typing.get_origin(T) is wrapper_origin:
            args = getattr(T, "__args__", None)
            if args is None:
                return True  # bare ClassVar or Final, no inner type constraint
            return isoftype(value, args[0])

    # Non-generic ABCs, and parametric ABCs where element type can't be checked.
    # Iterator: consumed by iteration. Container: only has __contains__, can't enumerate.
    # Hashable, Sized: not generic (can't be parameterized).
    for abc in (collections.abc.Hashable,
                collections.abc.Sized,
                collections.abc.Iterator,
                collections.abc.Container):
        if typing.get_origin(T) is abc:
            return isinstance(value, abc)

    # Parametric ABCs with best-effort element checking.
    # If the value is Sized (a concrete collection), we can safely iterate
    # and check elements. Otherwise (opaque iterator), accept on ABC alone.
    for abc in (collections.abc.Iterable,
                collections.abc.Collection,
                collections.abc.Reversible):
        if typing.get_origin(T) is abc:
            if not isinstance(value, abc):
                return False
            args = getattr(T, "__args__", None)
            if args is None:
                return True  # bare form, no element type constraint
            assert len(args) == 1
            if not isinstance(value, collections.abc.Sized):
                return True  # opaque iterator — can't check elements non-destructively
            if not value:  # empty sized collection has no element type
                return False
            U = args[0]
            return all(isoftype(elt, U) for elt in value)

    # "Protocols cannot be used with isinstance()", so:
    for U in (typing.SupportsInt,
              typing.SupportsFloat,
              typing.SupportsComplex,
              typing.SupportsBytes,
              typing.SupportsIndex,
              typing.SupportsAbs,
              typing.SupportsRound):
        if U is T:
            return safeissubclass(type(value), U)

    # TypedDict — structural check on dict contents.
    # isinstance doesn't work with TypedDict, so we check keys and value types.
    if typing.is_typeddict(T):
        if not isinstance(value, dict):
            return False
        hints = typing.get_type_hints(T)
        required = T.__required_keys__
        optional = T.__optional_keys__
        allowed = required | optional
        if not required.issubset(value.keys()):
            return False
        if not set(value.keys()).issubset(allowed):
            return False
        for k, v in value.items():
            if not isoftype(v, hints[k]):
                return False
        return True

    # We don't have a match yet, so T might still be one of those meta-utilities
    # that hate `issubclass` with a passion.
    # DEPRECATED: typing.Text is deprecated since Python 3.11 (it's just an alias for str).
    # TODO: Remove this branch when the floor bumps to Python 3.12.
    if safeissubclass(T, typing.Text):
        return isinstance(value, str)

    # IO, TextIO, BinaryIO — typing module stubs that don't participate in the
    # MRO of real IO classes. Map to the io module ABCs instead.
    # IO[str] → TextIO, IO[bytes] → BinaryIO when parametric.
    if T is typing.IO or typing.get_origin(T) is typing.IO:
        args = getattr(T, "__args__", None)
        if args is not None:
            if args[0] is str:
                return isinstance(value, io.TextIOBase)
            if args[0] is bytes:
                return isinstance(value, (io.RawIOBase, io.BufferedIOBase))
        return isinstance(value, io.IOBase)
    if T is typing.TextIO:
        return isinstance(value, io.TextIOBase)
    if T is typing.BinaryIO:
        return isinstance(value, (io.RawIOBase, io.BufferedIOBase))

    # Pattern[T] and Match[T] — the type arg (str or bytes) can be checked.
    if typing.get_origin(T) is re.Pattern:
        if not isinstance(value, re.Pattern):
            return False
        args = getattr(T, "__args__", None)
        if args is not None:
            return isinstance(value.pattern, args[0])
        return True
    if typing.get_origin(T) is re.Match:
        if not isinstance(value, re.Match):
            return False
        args = getattr(T, "__args__", None)
        if args is not None:
            return isinstance(value.string, args[0])
        return True

    # ContextManager and AsyncContextManager — can't check the return type
    # of __enter__ non-destructively, so just check the ABC.
    if typing.get_origin(T) is contextlib.AbstractContextManager:
        return isinstance(value, contextlib.AbstractContextManager)
    if typing.get_origin(T) is contextlib.AbstractAsyncContextManager:
        return isinstance(value, contextlib.AbstractAsyncContextManager)

    # Async ABCs and generator types — type parameters (yield, send, return)
    # can't be checked non-destructively, so just check the ABC.
    for runtimetype in (collections.abc.Awaitable,
                        collections.abc.Coroutine,
                        collections.abc.AsyncIterable,
                        collections.abc.AsyncIterator,
                        collections.abc.Generator,
                        collections.abc.AsyncGenerator):
        if typing.get_origin(T) is runtimetype:
            return isinstance(value, runtimetype)

    if typing.get_origin(T) is tuple:
        if not isinstance(value, tuple):
            return False
        # bare `typing.Tuple`, no restrictions on length or element type.
        if not getattr(T, "__args__", None):
            return True
        # homogeneous element type, arbitrary length
        if len(T.__args__) == 2 and T.__args__[1] is Ellipsis:
            if not value:  # no elements
                # An empty tuple has no element type, so to make multiple dispatch
                # behave predictably (so it doesn't guess), we must reject it.
                return False
            U = T.__args__[0]
            return all(isoftype(elt, U) for elt in value)
        # heterogeneous element types, exact length
        if len(value) != len(T.__args__):
            return False
        return all(isoftype(elt, U) for elt, U in zip(value, T.__args__))

    # Check mapping types that allow non-destructive iteration.
    def ismapping(runtimetype):
        if not isinstance(value, runtimetype):
            return False
        args = getattr(T, "__args__", None)
        if args is None:
            args = (typing.TypeVar("KT"), typing.TypeVar("VT"))
        assert len(args) == 2
        if not value:  # An empty dict has no key and value types.
            return False
        K, V = args
        return all(isoftype(k, K) and isoftype(v, V) for k, v in value.items())
    # Counter[T] is a mapping (keys: T, values: int), but has only one type arg.
    if typing.get_origin(T) is collections.Counter:
        if not isinstance(value, collections.Counter):
            return False
        args = getattr(T, "__args__", None)
        if args is None:
            args = (typing.TypeVar("T"),)
        assert len(args) == 1
        if not value:
            return False
        U = args[0]
        return all(isoftype(k, U) and isinstance(v, int) for k, v in value.items())

    for runtimetype in (dict,
                        collections.defaultdict,
                        collections.OrderedDict,
                        collections.ChainMap,
                        collections.abc.MutableMapping,
                        collections.abc.Mapping):
        if typing.get_origin(T) is runtimetype:
            return ismapping(runtimetype)

    # ItemsView is a special-case mapping in that we must not call
    # `.items()` on `value`.
    if typing.get_origin(T) is collections.abc.ItemsView:
        if not isinstance(value, collections.abc.ItemsView):
            return False
        args = getattr(T, "__args__", None)
        if args is None:
            args = (typing.TypeVar("KT"), typing.TypeVar("VT"))
        assert len(args) == 2
        if not value:  # An empty dict has no key and value types.
            return False
        K, V = args
        return all(isoftype(k, K) and isoftype(v, V) for k, v in value)

    # Check iterable types that allow non-destructive iteration.
    #
    # Special-case strings; they match typing.Sequence, but they're not
    # generics; the class has no `__args__` so this code doesn't apply to
    # them.
    if T not in (str, bytes):
        def iscollection(statictype, runtimetype):
            if not isinstance(value, runtimetype):
                return False
            if typing.get_origin(statictype) is collections.abc.ByteString:
                # DEPRECATED: typing.ByteString is deprecated since Python 3.12.
                # TODO: Remove this branch and the ByteString entry in the loop below
                # when the floor bumps to Python 3.12.
                #
                # WTF? A ByteString is a Sequence[int], but only statically.
                # At run time, the `__args__` are actually empty — it looks
                # like a bare Sequence, which is invalid. HACK the special case.
                typeargs = (int,)
            else:
                typeargs = getattr(T, "__args__", None)
            if typeargs is None:
                typeargs = (typing.TypeVar("T"),)
            # Judging by the docs, List takes one type argument. The rest are similar.
            # https://docs.python.org/3/library/typing.html#typing.List
            assert len(typeargs) == 1
            if not value:  # An empty collection has no element type.
                return False
            U = typeargs[0]
            return all(isoftype(elt, U) for elt in value)
        for statictype, runtimetype in ((typing.List, list),
                                        (typing.FrozenSet, frozenset),
                                        (typing.Set, set),
                                        (typing.Deque, collections.deque),
                                        (typing.ByteString, collections.abc.ByteString),  # DEPRECATED; must check before Sequence
                                        (typing.MutableSet, collections.abc.MutableSet),  # must check mutable first
                                        # because a mutable value has *also* the interface of the immutable variant
                                        # (e.g. MutableSet is a subtype of AbstractSet)
                                        (typing.KeysView, collections.abc.KeysView),
                                        (typing.ValuesView, collections.abc.ValuesView),
                                        (typing.MappingView, collections.abc.MappingView),  # MappingView has one type argument so it goes here?
                                        (typing.AbstractSet, collections.abc.Set),
                                        (typing.MutableSequence, collections.abc.MutableSequence),
                                        (typing.MappingView, collections.abc.MappingView),
                                        (typing.Sequence, collections.abc.Sequence)):
            if typing.get_origin(T) is runtimetype:
                return iscollection(statictype, runtimetype)

    if typing.get_origin(T) is collections.abc.Callable:
        if not callable(value):
            return False
        return True
        # # TODO: analyze Callable[[a0, a1, ...], ret], Callable[..., ret].
        # if T.__args__ is None:  # bare `typing.Callable`, no restrictions on arg/return types.
        #     return True
        # sig = typing.get_type_hints(value)
        # *argtypes, rettype = T.__args__
        # if len(argtypes) == 1 and argtypes[0] is Ellipsis:
        #     pass  # argument types not specified
        # else:
        #     # TODO: we need the names of the positional arguments of the `value` callable here.
        #     for a in argtypes:
        #         # TODO: We need to compare two specs against each other, not a value against T.
        #         # This needs an `issubtype` function.
        #         #
        #         # Note arguments behave contravariantly, while return values behave covariantly:
        #         #   - f(x: animal) is a *subtype* of f(x: cat), since any use site that passes
        #         #     in a cat (more specific) works fine with a function that accepts any animal
        #         #     (more general).
        #         #   - g() -> int is a subtype of g() -> Number, because any use site that
        #         #     expects a Number (more general) can deal with an int (more specific).
        #         # https://en.wikipedia.org/wiki/Covariance_and_contravariance_(computer_science)
        #         if not issubtype(???, a):
        #             return False
        # if not issubtype(rettype, sig["return"]):
        #     return False
        # return True

    # Protocol — support @runtime_checkable Protocols; clear error for others.
    # Specific Protocols (Supports* ABCs) are already handled above by identity check.
    # We use _is_protocol (not issubclass) because issubclass(X, Protocol) returns
    # True for some non-Protocol types (e.g. int) on Python 3.10.
    if isinstance(T, type) and T is not typing.Protocol and getattr(T, '_is_protocol', False):
        if getattr(T, '_is_runtime_protocol', False):
            return isinstance(value, T)
        raise TypeError(
            f"isoftype: {T.__qualname__} is a Protocol but not @typing.runtime_checkable, "
            f"so runtime structural checks are not possible. "
            f"Add @typing.runtime_checkable to enable isinstance checks.")

    # Catch any `typing` meta-utilities we don't currently support.
    if hasattr(T, "__module__") and T.__module__ == "typing":  # pragma: no cover, only happens when something goes wrong.
        fullname = repr(T.__class__)
        raise NotImplementedError(f"This run-time type checker doesn't currently support {repr(fullname)}")

    try:
        return isinstance(value, T)  # T should be a concrete class, so delegate.
    except TypeError as err:  # pragma: no cover, for debugging when things go wrong
        raise NotImplementedError(f"Failed to understand the type, so here's some debug data: {type(T)}, {repr(T.__class__)}, {str(T)}, {repr(T)}") from err

# TODO: Add an `issubtype` function. It's needed to fully resolve callable types in `isoftype`.
#
# - It must take two typespec arguments, T1 and T2, but matches will be on the diagonal
#   (e.g. a `Union` can only be a subtype of another `Union`).
# - If T1 and T2 are both concrete types, delegate to `issubclass`.
# - If exactly one of T1 or T2 is a concrete type, return `False.`
