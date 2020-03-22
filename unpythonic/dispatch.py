# -*- coding: utf-8; -*-
"""A multiple-dispatch decorator for Python.

Somewhat like `functools.singledispatch`, but for multiple dispatch.

    https://docs.python.org/3/library/functools.html#functools.singledispatch

**WARNING: EXPERIMENTAL FEATURE**

This experimental feature is a proof-of-concept provided for technical preview
and teaching purposes only.

Details may still change in a backwards-incompatible way, or the whole
feature may still be removed. Do not depend on it in production!
"""

__all__ = ["generic", "specific"]

from functools import wraps
from itertools import chain
import inspect
import typing

from .arity import resolve_bindings, _getfunc
from .typecheck import isoftype

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

    Each method must specify type hints **on all of its parameters** except
    `**kwargs` (if it has one). Then, at call time, the types of **all** arguments
    (except any bound to `**kwargs`) as well as the number of arguments, are
    automatically used for choosing which method to call. In other words,
    multiple parameters are used for dispatching.

    **Varargs are supported**. To have the contents of `*args` participate in
    dispatching, annotate the parameter as `*args: typing.Tuple[...]`. For the
    `...` part, see the documentation of the `typing` module. Both homogeneous
    and heterogeneous tuples are supported.

    The first method that matches wins, in most-recently-registered order. That
    is, later definitions override earlier ones. So specify the implementation
    with the most generic types first, and then move on to the more specific
    ones. The mnemonic is, "the function is generally defined like this, except
    if the arguments match these particular types..."

    The point of this feature is to eliminate `if`/`elif`/`elif`... blocks
    that switch by `isinstance` on arguments, and then raise `TypeError`
    in the final `else`, by implementing the machinery once centrally.

    Another use case of `@generic` are functions like the builtin `range`, where
    the *role* of an argument in a particular position depends on the *number of*
    arguments passed in the call.

    **Differences to tools in the standard library**:

    Unlike `functools.singledispatch`, the `@generic` function itself is unused.

    Unlike `typing.overload`, the implementations are given in the method bodies.

    **CAUTION**:

    To declare a parameter of a method as dynamically typed, explicitly
    annotate it as `typing.Any`; don't just omit the type annotation.
    Explicit is better than implicit; **this is a feature**.

    Dispatching by the contents of the `**kwargs` dictionary is not (yet)
    supported.

    See the limitations in `unpythonic.typecheck` for which features of the
    `typing` module are supported and which are not.
    """
    # Dispatcher - this will replace the original f.
    @wraps(f)
    def multidispatch(*args, **kwargs):
        # signature comes from typing.get_type_hints.
        def match_argument_types(signature):
            # TODO: handle **kwargs (bindings["kwarg"], bindings["kwarg_name"])
            args_items = bindings["args"].items()
            if bindings["vararg_name"]:
                vararg_item = (bindings["vararg_name"], bindings["vararg"])  # *args
                all_items = tuple(chain(args_items, (vararg_item,)))
            else:
                all_items = args_items

            for parameter, value in all_items:
                assert parameter in signature  # resolve_bindings should already TypeError when not.
                expected_type = signature[parameter]
                if not isoftype(value, expected_type):
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
        a = [repr(a) for a in args]
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
