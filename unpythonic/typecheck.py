# -*- coding: utf-8; -*-
"""Simplistic run-time type checker.

This implements just a minimal feature set needed for checking function
arguments in typical uses of multiple dispatch (see `unpythonic.dispatch`).
That said, this DOES support many (but not all) features of the `typing` stdlib
module.

We currently provide `isoftype` (cf. `isinstance`), but no `issubtype` (cf. `issubclass`).

If you need a run-time type checker for serious general use, consider `typeguard`:

    https://github.com/agronholm/typeguard

**WARNING: EXPERIMENTAL FEATURE**

This experimental feature is a proof-of-concept provided for technical preview
and teaching purposes only.

Details may still change in a backwards-incompatible way, or the whole
feature may still be removed. Do not depend on it in production!
"""

import collections
import typing

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
    # TODO: This function is one big hack.
    #
    # As of Python 3.6, there seems to be no consistent way to identify a type
    # specification at run time. So what we have is a mess.
    #
    # - Many `typing` meta-utilities explicitly `raise TypeError` when one
    #   attempts The One Obvious Way To Do It (`isinstance`, `issubclass`).
    #
    # - Their `type` can be something like `typing.TypeVar`, `typing.Union`,
    #   `<class typing.TupleMeta>`, `<class typing.CallableMeta>`... the
    #   format is case-dependent. A check like `type(T) is typing.TypeVar`
    #   doesn't work.
    #
    # So, we inspect `repr(T.__class__)` to match on the names of the prickly types,
    # and call `issubclass` on those that don't hate us for doing so (catching
    # `TypeError`, just in case `T` is an unsupported yet prickly type).
    #
    # Obviously, this won't work if someone subclasses one of the prickly types.
    # `issubclass` would be The Right Thing, but since it's explicitly blocked,
    # there's not much we can do.

    # TODO: Right now we're accessing internal fields to get what we need.
    # TODO: Would be nice to update this if Python, at some point, adds an
    # TODO: official API to access the static type information at run time.

    if T is typing.Any:
        return True

    if repr(T.__class__) == "typing.TypeVar":  # AnyStr normalizes to TypeVar("AnyStr", str, bytes)
        if not T.__constraints__:  # just an abstract type name
            return True
        return any(isoftype(value, U) for U in T.__constraints__)

    # TODO: Here is THE FULL LIST of `typing` features we **don't** currently support,
    # TODO: as of Python 3.8 (March 2020). https://docs.python.org/3/library/typing.html
    # TODO: If you add a feature to the type checker, please update this list.
    #
    # Python 3.6+:
    #   NamedTuple, DefaultDict, Counter, ChainMap,
    #   IO, TextIO, BinaryIO,
    #   Pattern, Match, (regular expressions)
    #   Generic, Type,
    #   Awaitable, Coroutine, AsyncIterable, AsyncIterator,
    #   ContextManager, AsyncContextManager,
    #   Generator, AsyncGenerator,
    #   NoReturn (callable return value only),
    #   ClassVar, Final
    #
    # Python 3.7+: OrderedDict
    # Python 3.8+: Protocol, SupportsIndex, TypedDict, Literal
    #
    # TODO: Do we need to support `typing.ForwardRef`?
    # No, if `get_type_hints` already resolves that. Consider our main use case,
    # in `unpythonic.dispatch`. And see:
    # https://docs.python.org/3/library/typing.html#typing.get_type_hints

    # TODO: Python 3.8 adds `typing.get_origin` and `typing.get_args`, which may be useful
    # TODO: to analyze generics once we bump our minimum Python to that.
    # https://docs.python.org/3/library/typing.html#typing.get_origin
    # if repr(T).startswith("typing.Generic["):
    #     pass

    if repr(T.__class__) == "typing.Union":  # Optional normalizes to Union[argtype, NoneType].
        if T.__args__ is None:  # bare `typing.Union`; empty, has no types in it, so no value can match.
            return False
        if not any(isoftype(value, U) for U in T.__args__):
            return False
        return True

    if callable(T) and hasattr(T, "__qualname__") and T.__qualname__ == "NewType.<locals>.new_type":
        # This is the best we can do, because the static types created by `typing.NewType`
        # have a constructor that discards the type information at runtime:
        #   UserId = typing.NewType("UserId", int)
        #   i = UserId(42)  # UserId is the identity function, as per `typing` module docs
        #   print(type(i))  # int
        return isinstance(value, T.__supertype__)

    # Some one-trick ponies.
    for U in (typing.Iterator,    # can't non-destructively check element type
              typing.Iterable,    # can't non-destructively check element type
              typing.Reversible,  # can't non-destructively check element type
              typing.Container,   # can't check element type
              typing.Collection,  # Sized Iterable Container; can't check element type
              typing.Hashable,
              typing.Sized):
        if U is T:
            return isinstance(value, U)
    # "Protocols cannot be used with isinstance()", so:
    for U in (typing.SupportsInt,
              typing.SupportsFloat,
              typing.SupportsComplex,
              typing.SupportsBytes,
              # typing.SupportsIndex,  # TODO: enable this once our minimum is Python 3.8
              typing.SupportsAbs,
              typing.SupportsRound):
        if U is T:
            return issubclass(type(value), U)

    # We don't have a match yet, so T might still be one of those meta-utilities
    # that hate `issubclass` with a passion.
    try:
        if issubclass(T, typing.Text):  # https://docs.python.org/3/library/typing.html#typing.Text
            return isinstance(value, str)  # alias for str

        if issubclass(T, typing.Tuple):
            if not isinstance(value, tuple):
                return False
            # bare `typing.Tuple`, no restrictions on length or element type.
            if T.__args__ is None:
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
            if T.__args__ is None:
                raise TypeError("Missing mandatory key, value type arguments of `{}`".format(statictype))
            assert len(T.__args__) == 2
            if not value:  # An empty dict has no key and value types.
                return False
            K, V = T.__args__
            return all(isoftype(k, K) and isoftype(v, V) for k, v in value.items())
        for statictype, runtimetype in ((typing.Dict, dict),
                                        (typing.MutableMapping, collections.abc.MutableMapping),
                                        (typing.Mapping, collections.abc.Mapping)):
            if issubclass(T, statictype):
                return ismapping(statictype, runtimetype)

        # ItemsView is a special-case mapping in that we must not call
        # `.items()` on `value`.
        if issubclass(T, typing.ItemsView):
            if not isinstance(value, collections.abc.ItemsView):
                return False
            if T.__args__ is None:
                raise TypeError("Missing mandatory key, value type arguments of `{}`".format(statictype))
            assert len(T.__args__) == 2
            if not value:  # An empty dict has no key and value types.
                return False
            K, V = T.__args__
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
                if issubclass(statictype, typing.ByteString):
                    # WTF? A ByteString is a Sequence[int], but only statically.
                    # At run time, the `__args__` are actually empty - it looks
                    # like a bare Sequence, which is invalid. Hack the special case.
                    typeargs = (int,)
                else:
                    typeargs = T.__args__
                if typeargs is None:
                    raise TypeError("Missing mandatory element type argument of `{}`".format(statictype))
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
                if issubclass(T, statictype):
                    return iscollection(statictype, runtimetype)

        if issubclass(T, typing.Callable):
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
    except TypeError:  # probably one of those meta-utilities that hates issubclass.
        # assert False  # this is a good idea while debugging the type checker.
        pass

    # Catch any `typing` meta-utilities we don't currently support.
    if hasattr(T, "__module__") and T.__module__ == "typing":
        fullname = repr(T.__class__)
        raise NotImplementedError("This run-time type checker doesn't currently support '{}'".format(fullname))

    try:  # DEBUG
        return isinstance(value, T)  # T is a concrete class, so delegate.
    except TypeError:
        raise(TypeError(str(T)))

# TODO: Add an `issubtype` function. It's needed to fully resolve callable types in `isoftype`.
#
# - It must take two typespec arguments, T1 and T2, but matches will be on the diagonal
#   (e.g. a `Union` can only be a subtype of another `Union`).
# - If T1 and T2 are both concrete types, delegate to `issubclass`.
# - If exactly one of T1 or T2 is a concrete type, return `False.`
