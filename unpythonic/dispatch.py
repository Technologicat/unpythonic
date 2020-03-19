# -*- coding: utf-8; -*-
"""A multiple-dispatch decorator for Python.

Somewhat like `functools.singledispatch`, but for multiple dispatch.

    https://docs.python.org/3/library/functools.html#functools.singledispatch

For now this is just a simplistic test. If we want to get serious, we must
add support for things like `*args`, `**kwargs`, `typing.Sequence[int]`,
and in 3.8, `typing.Literal['a', 'b', 'c', 'd']`.

**WARNING: EXPERIMENTAL FEATURE**

This experimental feature is a proof-of-concept provided for technical preview
and teaching purposes only.

Details may still change in a backwards-incompatible way, or the whole
feature may still be removed. Do not depend on it in production!
"""

__all__ = ["generic", "specific"]

from functools import wraps
import inspect
import typing

from .arity import resolve_bindings, _getfunc

def generic(f):
    """Decorator. Make `f` a generic function (in the sense of CLOS or Julia).

    **How to use**:

    The `@generic`-decorated function definition itself just declares the name
    as a generic function, thus equipping it with the `register` decorator to
    attach methods. That original function is never called, so its body can be
    e.g. `pass` or `...`.

    Like in `functools.singledispatch`, methods (implementations for specific
    combinations of argument types and/or different shapes for the argument list)
    are registered with the decorator `@f.register`, where `f` is the function
    you decorated with `@generic`.

    Each method must specify type hints **on all of its parameters**. Then, at
    call time, the types of **all** arguments, as well as the number of arguments,
    are automatically used for choosing which method to call. In other words, multiple
    parameters are used for dispatching.

    The first match wins, in most-recently-registered order - that is, later
    definitions override earlier ones. So specify the implementation with the
    most generic types first, and then move on to the more specific ones. The
    mnemonic is, "the function is generally defined like this, except if the
    arguments match these particular types..."

    The point of this feature is to eliminate `if`/`elif`/`elif`... blocks
    that switch by `isinstance` on arguments, and then raise `TypeError`
    in the final `else`, by implementing the machinery once centrally.

    Another use case are functions like the builtin `range` where the role
    of an argument in a particular position depends on the number of arguments
    given to the call.

    **Differences to tools in the standard library**:

    Unlike `functools.singledispatch`, the `@generic` function itself is
    unused.

    Unlike `typing.overload`, the implementations are to be provided in the
    method bodies.

    **CAUTION**:

    To declare a parameter of a method as dynamically typed, explicitly
    annotate it as `typing.Any`; don't just omit the type annotation.
    Explicit is better than implicit; this is a feature.

    Currently, advanced features of `typing` such as `Sequence[...]` are
    not supported. This may or may not change in the future.
    """
    # Dispatcher - this will replace the original f.
    @wraps(f)
    def multidispatch(*args, **kwargs):
        # It's silly that while Python supports type annotations, the stdlib doesn't have a function to
        # perform a type annotation based runtime type check. Fuck it, we'll just have to implement one.
        #
        # Many `typing` meta-utilities explicitly reject using isinstance and issubclass on them,
        # so we hack those by inspecting the repr.
        #
        #     value: value whose type to check
        #
        #     spec: match value against this.
        #           Either a concrete type, or one of the meta-utilities from the `typing` module.
        #
        #           Only the most fundamental meta-utilities (Any, TypeVar, Union, Tuple, Callable)
        #           are currently supported.
        #
        # TODO: This is a solved problem, we should use https://github.com/agronholm/typeguard
        def match_type(value, spec):
            # TODO: Python 3.8 adds `typing.get_origin` and `typing.get_args`, which may be useful
            # TODO: once we bump our minimum to that.
            # TODO: Right now we're accessing internal fields to get what we need.
            # https://docs.python.org/3/library/typing.html#typing.get_origin
            if spec is typing.Any:
                return True
            if repr(spec.__class__) == "TypeVar":  # AnyStr gets normalized to TypeVar("AnyStr", str, bytes)
                if not spec.__constraints__:  # just an abstract type name
                    return True
                return any(match_type(value, typ) for typ in spec.__constraints__)
            # TODO: typing.Generic
            # if repr(spec).startswith("typing.Generic["):
            #     pass
            # TODO: Protocol, Type, Iterable, Iterator, Reversible, ...
            # TODO: List, Set, FrozenSet, Dict, NamedTuple
            # TODO: many, many others; see https://docs.python.org/3/library/typing.html
            if repr(spec.__class__) == "typing.Union":  # Optional gets normalized to Union[argtype, NoneType].
                if spec.__args__ is None:  # bare `typing.Union`; has no types in it, so no value can match.
                    return False
                if not any(match_type(value, typ) for typ in spec.__args__):
                    return False
                return True
            try:
                if issubclass(spec, typing.Text):
                    return isinstance(value, str)
                if issubclass(spec, typing.Tuple):
                    if not isinstance(value, tuple):
                        return False
                    if spec.__args__ is None:  # bare `typing.Tuple`, any tuple matches.
                        return True
                    # homogeneous type, arbitrary length
                    if len(spec.__args__ == 2 and spec.__args__[1] is Ellipsis):
                        typ = spec.__args__[0]
                        return all(match_type(elt, typ) for elt in value)
                    # heterogeneous types, exact length
                    if len(value) == len(spec.__args__):
                        return False
                    return all(match_type(elt, typ) for typ, elt in zip(spec.__args__, value))
                if issubclass(spec, typing.Callable):
                    if not callable(value):
                        return False
                    return True
                    # # TODO: Callable[[a0, a1, ...], ret], Callable[..., ret].
                    # if spec.__args__ is None:  # bare `typing.Callable`, no restrictions on arg/return types.
                    #     return True
                    # sig = typing.get_type_hints(value)
                    # *argtypes, rettype = spec.__args__
                    # if len(argtypes) == 1 and argtypes[0] is Ellipsis:
                    #     pass  # argument types not specified
                    # else:
                    #     # TODO: we need the names of the positional arguments of the `value` callable here.
                    #     for a in argtypes:
                    #         # TODO: Can't use match_type here; we're comparing two specs against each other,
                    #         # TODO: not a value against a spec. Need to implement a compatible_specs function.
                    #         if not compatible_specs(???, a):
                    #             return False
                    # if not compatible_specs(sig["return"], rettype):
                    #     return False
                    # return True
            except TypeError:  # probably one of those meta-utilities that hates issubclass for no reason
                pass
            # TODO: typing.Literal (Python 3.8)
            # catch any meta-utilities we don't currently support
            if hasattr(spec, "__module__") and spec.__module__ == "typing":
                fullname = "{}.{}".format(spec.__module__, spec.__qualname__)
                raise NotImplementedError("This simple runtime typechecker doesn't support {}".format(fullname))
            return isinstance(value, spec)  # a concrete type parameter
        # signature comes from typing.get_type_hints.
        def match_argument_types(signature):
            # TODO: handle *args (bindings["vararg"], bindings["vararg_name"])
            # TODO: handle **kwargs (bindings["kwarg"], bindings["kwarg_name"])
            for parameter, value in bindings["args"].items():
                assert parameter in signature  # resolve_bindings should already TypeError when not.
                expected_type = signature[parameter]
                if not match_type(value, expected_type):
                    return False
            return True

        # Dispatch.
        def methods():
            return reversed(multidispatch._registry)
        for method, signature in methods():
            try:
                bindings = resolve_bindings(method, *args, **kwargs)
            except TypeError:  # arity mismatch, so this method can't be the one the call is looking for.
                continue
            if match_argument_types(signature):
                return method(*args, **kwargs)

        # No match, report error.
        #
        # TODO: It would be nice to show the type signature of the args actually given,
        # TODO: but in the general case this is difficult. We can't just `type(x)`, since
        # TODO: the signature may specify something like `Sequence[int]`. Knowing a `list`
        # TODO: was passed doesn't help debug that it was `Sequence[str]` when a `Sequence[int]`
        # TODO: was expected. The actual value at least implicitly contains the type information.
        #
        # TODO: Compute closest candidates, like Julia does? (see methods, MethodError)
        a = [str(a) for a in args]
        sep = ", " if kwargs else ""
        kw = ["{}={}".format(k, str(v)) for k, v in kwargs]
        def format_method(method):  # Taking a page from Julia and some artistic liberty here.
            obj, signature = method
            filename = inspect.getsourcefile(obj)
            source, firstlineno = inspect.getsourcelines(obj)
            return "{} from {}:{}".format(signature, filename, firstlineno)
        methods_str = ["  {}".format(format_method(x)) for x in methods()]
        candidates = "\n".join(methods_str)
        msg = ("No method found matching {}({}{}{}).\n"
               "Candidate signatures (in order of match attempts):\n{}").format(f.__qualname__,
                                                                                ", ".join(a),
                                                                                sep, ", ".join(kw),
                                                                                candidates)
        raise TypeError(msg)

    # fullname = "{}.{}".format(f.__module__, f.__qualname__)
    multidispatch._registry = []
    def register(thecallable):
        """Decorator. Register a new method for this generic function.

        The method must have type annotations for all of its parameters;
        these are used for dispatching.
        """
        # Using `inspect.signature` et al., we could auto-`Any` parameters
        # that have no type annotation, but that would likely be a footgun.
        # So we require a type annotation for each parameter.
        signature = typing.get_type_hints(thecallable)

        # Verify that the method has a type annotation for each parameter.
        function, _ = _getfunc(thecallable)
        params = inspect.signature(function).parameters
        allparamnames = [p.name for p in params.values()]
        if not all(name in signature for name in allparamnames):
            failures = [name for name in allparamnames if name not in signature]
            wrapped = ["'{}'".format(x) for x in failures]
            plural = "s" if len(failures) > 1 else ""
            msg = "Method definition missing type annotation for parameter{}: {}".format(plural,
                                                                                         ", ".join(wrapped))
            raise TypeError(msg)

        multidispatch._registry.append((thecallable, signature))
        # TODO: Does this work properly with instance methods and class methods?
        # TODO: (At the moment, probably not. Just might, if `self` has a type annotation.)
        return multidispatch  # Replace the callable with the dispatcher for this generic function.
    multidispatch.register = register  # publish the @f.register decorator

    return multidispatch


def specific(f):
    """Decorator. A one-method pony, which is kind of the opposite of `@generic`.

    This restricts the allowed argument types to one combination only. This can
    be used to eliminate `isinstance` boilerplate code in the function body, by
    allowing the types (for dynamic, run-time checking) to be specified with a
    very compact syntax.

    Unlike in `@generic`, where the function being decorated is just a stub,
    in `@specific` the only method is provided as the function being decorated.

    A `@specific` function has no `.register` attribute; after it is created,
    no more methods can be attached to it.
    """
    s = generic(f)
    s.register(f)
    del s.register  # remove the ability to attach more methods
    return s
