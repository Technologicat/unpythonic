# -*- coding: utf-8; -*-
"""Simplistic run-time type checker.

This implements just a minimal feature set needed for checking function
arguments in typical uses of multiple dispatch (see `unpythonic.dispatch`).
That said, this DOES support many (but not all) features of the `typing` stdlib
module.

We currently provide `isoftype` (cf. `isinstance`), but no `issubtype` (cf. `issubclass`).

If you need a run-time type checker, but not the other features of `unpythonic`,
see `typeguard`:

    https://github.com/agronholm/typeguard
"""

import collections
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
                 - `Tuple`, `Tuple[T, ...]`, `Tuple[T1, T2, ..., TN]`, `Sequence[T]`
                 - `List[T]`, `MutableSequence[T]`
                 - `FrozenSet[T]`, `AbstractSet[T]`
                 - `Set[T]`, `MutableSet[T]`
                 - `Dict[K, V]`, `MutableMapping[K, V]`, `Mapping[K, V]`
                 - `ItemsView[K, V]`, `KeysView[K]`, `ValuesView[V]`
                 - `Callable` (argument and return value types currently NOT checked)
                 - `Text`

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
    #   NamedTuple, DefaultDict, Counter, ChainMap, OrderedDict,
    #   IO, TextIO, BinaryIO, Pattern, Match, Generic, Type,
    #   Awaitable, Coroutine, AsyncIterable, AsyncIterator,
    #   ContextManager, AsyncContextManager, Generator, AsyncGenerator,
    #   NoReturn, ClassVar, Final, Protocol, TypedDict, Literal, ForwardRef

    if T is typing.Any:
        return True

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

    # Some one-trick ponies.
    for U in (typing.Iterator,    # can't non-destructively check element type
              typing.Iterable,    # can't non-destructively check element type
              typing.Container,   # can't check element type
              typing.Collection,  # Sized Iterable Container; can't check element type
              typing.Hashable,
              typing.Sized):
        if U is T:
            return isinstance(value, U)

    if T is typing.Reversible:  # can't non-destructively check element type
        return isinstance(value, typing.Reversible)

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

    # We don't have a match yet, so T might still be one of those meta-utilities
    # that hate `issubclass` with a passion.
    if safeissubclass(T, typing.Text):  # https://docs.python.org/3/library/typing.html#typing.Text
        return isinstance(value, str)  # alias for str

    if safeissubclass(T, typing.Tuple) or typing.get_origin(T) is tuple:
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
    def ismapping(statictype, runtimetype):
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
    for statictype, runtimetype in ((typing.Dict, dict),
                                    (typing.MutableMapping, collections.abc.MutableMapping),
                                    (typing.Mapping, collections.abc.Mapping)):
        if safeissubclass(T, statictype) or typing.get_origin(T) is runtimetype:
            return ismapping(statictype, runtimetype)

    # ItemsView is a special-case mapping in that we must not call
    # `.items()` on `value`.
    if safeissubclass(T, typing.ItemsView) or typing.get_origin(T) is collections.abc.ItemsView:
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
            if safeissubclass(statictype, typing.ByteString) or typing.get_origin(statictype) is collections.abc.ByteString:
                # WTF? A ByteString is a Sequence[int], but only statically.
                # At run time, the `__args__` are actually empty - it looks
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
                                        (typing.ByteString, collections.abc.ByteString),  # must check before Sequence
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
            if safeissubclass(T, statictype) or typing.get_origin(T) is runtimetype:
                return iscollection(statictype, runtimetype)

    if safeissubclass(T, typing.Callable) or typing.get_origin(T) is collections.abc.Callable:
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
