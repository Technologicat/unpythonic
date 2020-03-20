# -*- coding: utf-8; -*-
"""Simplistic run-time type checker.

This implements just a minimal feature set needed for checking function arguments in
typical uses of multiple dispatch (see `unpythonic.dispatch`).

If you need a run-time type checker for serious general use, consider `typeguard`:

    https://github.com/agronholm/typeguard
"""

import typing

__all__ = ["match_value_to_typespec"]

# Many `typing` meta-utilities explicitly reject using isinstance and issubclass on them,
# so we hack those by inspecting the repr.
def match_value_to_typespec(value, T):
    """A simple run-time type check.

    Check that `value` matches the type specification `T`.

        value: a regular run-time value whose type to check.

        T:     a type specification to check against.

               Either a concrete type (e.g. `int`, `somemodule.MyClass`), or a specification
               using one of the meta-utilities defined by the `typing` module.

               Only the most fundamental meta-utilities are currently supported:
                 - Any, TypeVar
                 - Union, Tuple
                 - Callable
                 - Text

               Additionally, the `typing` module itself automatically normalizes the
               following specifications:
                 - Optional[T] -> Union[T, NoneType]
                 - AnyStr -> TypeVar("AnyStr", str, bytes)

    Returns `True` if the type matches; `False` if not.
    """
    # TODO: Python 3.8 adds `typing.get_origin` and `typing.get_args`, which may be useful
    # TODO: to analyze generics once we bump our minimum Python to that.
    #
    # TODO: Right now we're accessing internal fields to get what we need.
    # https://docs.python.org/3/library/typing.html#typing.get_origin

    if T is typing.Any:
        return True

    if repr(T.__class__) == "typing.TypeVar":  # AnyStr normalizes to TypeVar("AnyStr", str, bytes)
        if not T.__constraints__:  # just an abstract type name
            return True
        return any(match_value_to_typespec(value, U) for U in T.__constraints__)

    # TODO: List, Set, FrozenSet, Dict, NamedTuple
    # TODO: Protocol, Type, Iterable, Iterator, Reversible, ...
    # TODO: typing.Generic
    # if repr(T).startswith("typing.Generic["):
    #     pass
    # TODO: typing.Literal (Python 3.8)
    # TODO: many, many others; see https://docs.python.org/3/library/typing.html

    if repr(T.__class__) == "typing.Union":  # Optional normalizes to Union[argtype, NoneType].
        if T.__args__ is None:  # bare `typing.Union`; empty, has no types in it, so no value can match.
            return False
        if not any(match_value_to_typespec(value, U) for U in T.__args__):
            return False
        return True

    # Because many (but not all) of the meta-utilities hate issubclass with a passion,
    # we must catch TypeError. We don't have a match yet, so T might still be one of them.
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
                U = T.__args__[0]
                return all(match_value_to_typespec(elt, U) for elt in value)
            # heterogeneous types, exact length
            if len(value) != len(T.__args__):
                return False
            return all(match_value_to_typespec(elt, U) for elt, U in zip(value, T.__args__))

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
            #         # TODO: Can't use match_value_to_typespec here; we're comparing two specs against
            #         # TODO: each other, not a value against T. Need to implement an `issubtype` function.
            #         # https://en.wikipedia.org/wiki/Covariance_and_contravariance_(computer_science)
            #         if not issubtype(???, a):  # arg types behave contravariantly.
            #             return False
            # if not issubtype(rettype, sig["return"]):  # return type behaves covariantly.
            #     return False
            # return True
    except TypeError:  # probably one of those meta-utilities that hates issubclass.
        pass

    # catch any meta-utilities we don't currently support
    if hasattr(T, "__module__") and T.__module__ == "typing":
        fullname = "{}.{}".format(T.__module__, T.__qualname__)
        raise NotImplementedError("This simple run-time type checker doesn't support '{}'".format(fullname))

    return isinstance(value, T)  # T is a concrete class
