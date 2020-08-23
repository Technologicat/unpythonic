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

__all__ = ["generic", "typed"]

from functools import wraps
from itertools import chain
import inspect
import typing

from .arity import resolve_bindings, _getfunc
from .typecheck import isoftype

_dispatcher_registry = {}
def generic(f):
    """Decorator. Make `f` a generic function (in the sense of CLOS or Julia).

    **How to use**:

    Just make several function definitions, one for each call signature you
    want to support, and decorate each of them with `@generic`. Here
    *signature* refers to specific combinations of argument types and/or
    different shapes for the argument list.

    The first definition implicitly creates the generic function (like in
    Julia). All of the definitions, including the first one, become registered
    as *methods* of the *generic function*.

    A generic function is identified by its *fullname*, defined as
    "{f.__module__}.{f.__qualname__}". The fullname is computed
    automatically when the `@generic` decorator runs. For example:

        - Top-level function in main module: "__main__.myfunction"
        - Top-level function in another module: "unpythonic.fold.scanl"
        - Nested function (closure) in main module: "__main__.test.<locals>.myhelper"

    Example::

        @generic
        def example(x: int, y: int):
            ...  # implementation here
        @generic  # noqa: F811, registered as a method of the same generic function.
        def example(x: str, y: int):
            ...  # implementation here
        @generic  # noqa: F811
        def example(x: str, y: float):
            ...  # implementation here
        @generic  # noqa: F811
        def example(x: str):
            ...  # implementation here
        @generic  # noqa: F811
        def example():
            ...  # implementation here

    Due to the need to have a meaningful `__qualname__` to construct the
    fullname, lambdas are not officially supported. If you must, you can try to
    `unpythonic.misc.namelambda` your lambda first, but be aware that even
    then, nested lambdas are not supported.

    Be careful that if you later rebind a variable that refers to a generic
    function; that will not remove previously existing method definitions.
    If you later rebind the same name again, pointing to a new generic function,
    it will suddenly gain all of the methods of the previous function that had
    the same fullname.

    **Method lookup**:

    Each method definition must specify type hints **on all of its parameters**
    except `**kwargs` (if it has one). Then, at call time, the types of **all**
    arguments (except any bound to `**kwargs`), as well as the number of
    arguments, are automatically used for *dispatching*, i.e. choosing which
    method to call. In other words, multiple parameters participate in
    dispatching, thus the term *multiple dispatch*.

    **Varargs are supported**. To have the contents of `*args` participate in
    dispatching, annotate the parameter as `*args: typing.Tuple[...]`. For the
    `...` part, see the documentation of the `typing` module. Both homogeneous
    and heterogeneous tuples are supported.

    **The first method that matches wins, in most-recently-registered order.**
    (This is unlike in Julia, which matches the most specific applicable method.)

    In other words, later definitions override earlier ones. So specify the
    implementation with the most generic types first, and then move on to the
    more specific ones. The mnemonic is, "the function is generally defined
    like this, except if the arguments match these particular types..."

    The main point of this feature is to eliminate `if`/`elif`/`elif`... blocks
    that switch by `isinstance` on arguments, and then raise `TypeError`
    in the final `else`, by implementing this machinery centrally.

    Another use case of `@generic` are functions like the builtin `range`, where
    the *role* of an argument in a particular position depends on the *number of*
    arguments passed in the call.

    **Differences to tools in the standard library**:

    Unlike in `functools.singledispatch`, there is no "master" definition and
    no public `register` attribute. Instead, generic functions are saved in a
    global registry.

    Unlike `typing.overload`, the implementations are given in the method bodies.

    **CAUTION**:

    To declare a parameter of a method as dynamically typed, explicitly
    annotate it as `typing.Any`; don't just omit the type annotation.
    Explicit is better than implicit; **this is a feature**.

    Dispatching by the contents of the `**kwargs` dictionary is not (yet)
    supported.

    See the limitations in `unpythonic.typecheck` for which features of the
    `typing` module are supported and which are not.

    At the moment, `@generic` does not work with `curry`. Adding curry support
    needs changes to the dispatch logic in `curry`.
    """
    fullname = "{}.{}".format(f.__module__, f.__qualname__)
    if fullname not in _dispatcher_registry:
        # Create the dispatcher. This will replace the original f.
        @wraps(f)
        def dispatcher(*args, **kwargs):
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
                return reversed(dispatcher._method_registry)
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

        dispatcher._method_registry = []
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

            dispatcher._method_registry.append((thecallable, signature))
            # TODO: Does this work properly with instance methods and class methods?
            # TODO: (At the moment, probably not. Just might, if `self` has a type annotation.)
            return dispatcher  # Replace the callable with the dispatcher for this generic function.

        dispatcher._register = register  # save it for use by us later
        _dispatcher_registry[fullname] = dispatcher
    dispatcher = _dispatcher_registry[fullname]
    if hasattr(dispatcher, "_register"):  # co-operation with @typed, below
        return dispatcher._register(f)
    raise TypeError("@typed: cannot register additional methods.")


def typed(f):
    """Decorator. Restrict allowed argument types to one combination only.

    This can be used to eliminate `isinstance` boilerplate code in the
    function body, by allowing the types (for dynamic, run-time checking)
    to be specified with a very compact syntax - namely, type annotations.

    Also, unlike a basic `isinstance` check, this allows using features
    from the `typing` stdlib module in the type specifications.

    After a `@typed` function has been created, no more methods can be
    attached to it.

    `@typed` works with `curry`, because the function has only one call
    signature, as usual.

    **CAUTION**:

    If used with `curry`, argument type errors will only be detected when
    `curry` triggers the actual call. To fix this, `curry` would need to
    perform some more introspection on the callable, and to actually know
    about this dispatch system. It's not high on the priority list.
    """
    # TODO: Fix the epic fail at fail-fast, and update the corresponding test.
    s = generic(f)
    del s._register  # remove the ability to attach more methods
    return s
