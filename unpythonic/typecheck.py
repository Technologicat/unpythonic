# -*- coding: utf-8; -*-
"""Simplistic run-time type checker.

This implements just a minimal feature set needed for checking function arguments in
typical uses of multiple dispatch (see `unpythonic.dispatch`).

We currently provide `isoftype` (cf. `isinstance`), but no `issubtype` (cf. `issubclass`).

If you need a run-time type checker for serious general use, consider `typeguard`:

    https://github.com/agronholm/typeguard

**WARNING: EXPERIMENTAL FEATURE**

This experimental feature is a proof-of-concept provided for technical preview
and teaching purposes only.

Details may still change in a backwards-incompatible way, or the whole
feature may still be removed. Do not depend on it in production!
"""

import typing

__all__ = ["isoftype"]

def isoftype(value, T):
    """Perform a type check at run time.

    A relative of the builtin `isinstance`, but subtly different. This function
    checks `value` against the *type specification* `T`.

        value: The run-time value whose type to check.

        T:     Either a concrete type (e.g. `int`, `somemodule.MyClass`), or a type
               specification using one of the meta-utilities defined by the `typing`
               stdlib module.

               If `T` is a concrete type, we just delegate to `isinstance`.

               Currently supported meta-utilities:

                 - `Any`
                 - `TypeVar`
                 - `Union[T1, T2, ..., TN]`
                 - `Tuple`, `Tuple[T, ...]`, `Tuple[T1, T2, ..., TN]`
                 - `Callable` (argument and return value types currently NOT checked)
                 - `Text`

               Any checks on the type arguments of the meta-utilities are performed
               recursively using `isoftype`, in order to allow compound specifications.

               Additionally, the following meta-utilities also work, because the
               `typing` module automatically normalizes them into supported ones:

                 - `Optional[T]` (becomes `Union[T, NoneType]`)
                 - `AnyStr` (becomes `TypeVar("AnyStr", str, bytes)`)

    Returns `True` if the type matches; `False` if not.
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
    # and call `issubclass` on those that don't hate us for that (catching `TypeError`
    # in case `T` is an unsupported yet prickly type).
    #
    # Obviously, this won't work if someone subclasses one of the prickly types.
    # `issubclass` would be The Right Thing, but since it's explicitly blocked,
    # there's not much we can do.
    #
    # TODO: Right now we're accessing internal fields to get what we need.
    # https://docs.python.org/3/library/typing.html#typing.get_origin

    if T is typing.Any:
        return True

    if repr(T.__class__) == "typing.TypeVar":  # AnyStr normalizes to TypeVar("AnyStr", str, bytes)
        if not T.__constraints__:  # just an abstract type name
            return True
        return any(isoftype(value, U) for U in T.__constraints__)

    # TODO: List, Set, FrozenSet, Dict, NamedTuple
    #
    # TODO: Protocol, Type, Iterable, Iterator, Reversible, ...
    #
    # TODO: typing.Generic
    # TODO: Python 3.8 adds `typing.get_origin` and `typing.get_args`, which may be useful
    # TODO: to analyze generics once we bump our minimum Python to that.
    # if repr(T).startswith("typing.Generic["):
    #     pass
    #
    # TODO: typing.Literal (Python 3.8)
    #
    # TODO: many, many others; for the full list, see https://docs.python.org/3/library/typing.html

    if repr(T.__class__) == "typing.Union":  # Optional normalizes to Union[argtype, NoneType].
        if T.__args__ is None:  # bare `typing.Union`; empty, has no types in it, so no value can match.
            return False
        if not any(isoftype(value, U) for U in T.__args__):
            return False
        return True

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
            # homogeneous type, arbitrary length
            if len(T.__args__) == 2 and T.__args__[1] is Ellipsis:
                if not value:  # no elements
                    # An empty tuple has no element type, so to make multiple dispatch
                    # behave predictably (so it doesn't guess), we must reject it.
                    return False
                U = T.__args__[0]
                return all(isoftype(elt, U) for elt in value)
            # heterogeneous types, exact length
            if len(value) != len(T.__args__):
                return False
            return all(isoftype(elt, U) for elt, U in zip(value, T.__args__))

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
        pass

    # catch any meta-utilities we don't currently support
    if hasattr(T, "__module__") and T.__module__ == "typing":
        fullname = repr(T.__class__)
        raise NotImplementedError("This simple run-time type checker doesn't support '{}'".format(fullname))

    return isinstance(value, T)  # T is a concrete class

# TODO: Add an `issubtype` function. It's needed to fully resolve callable types in `isoftype`.
#
# - It must take two typespec arguments, T1 and T2, but matches will be on the diagonal
#   (e.g. a `Union` can only be a subtype of another `Union`).
# - If T1 and T2 are both concrete types, delegate to `issubclass`.
# - If exactly one of T1 or T2 is a concrete type, return `False.`
