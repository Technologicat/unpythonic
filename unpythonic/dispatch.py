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

from .arity import resolve_bindings, getfunc
from .typecheck import isoftype
from .regutil import register_decorator

_dispatcher_registry = {}

# Not strictly part of "the" public API, but stealthily public (with the usual
# public-API guarantees) because, although unlikely, an occasional user may
# need to customize this.
self_parameter_names = ["self", "this", "cls", "klass"]

# TODO: meh, a list instance's __doc__ is not writable. Put this doc somewhere.
#
# self_parameter_names.__doc__ = """self/cls parameter names for `@generic`.
#
# When one of these parameter names appears in the first positional parameter position
# of a function decorated with `@generic` (or `@typed`), it is detected as being an
# OOP-related `self` or `cls` parameter, triggering special handling.
#
# If you use something other than the usual Python naming conventions for the self/cls
# parameter, just append the names you use to this list.
# """

@register_decorator(priority=98)
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

    **Interaction with OOP**:

    Beside regular functions, `@generic` can be installed on instance, class
    or static methods (in the OOP sense). `self` and `cls` parameters do not
    participate in dispatching, and need no type annotation.

    On instance and class methods, the self-like parameter, beside appearing as
    the first positional-or-keyword parameter, **must be named** one of `self`,
    `this`, `cls`, or `klass` to be detected by the ignore mechanism. This
    limitation is due to implementation reasons; while a class body is being
    evaluated, the context needed to distinguish a method (OOP sense) from a
    regular function is not yet present.

    When `@generic` is installed on an instance method or on a `@classmethod`,
    then at call time, classes are tried in MRO order. **All** generic-function
    methods of the OOP method defined in the class currently being looked up
    are tested for matches first, **before** moving on to the next class in the
    MRO. (This has subtle consequences, related to in which class in the
    hierarchy the various generic-function methods for a particular OOP method
    are defined.)

    For *static methods* MRO lookup is not supported. Basically, one of the
    roles of `cls` or `self` is to define the MRO; a `@staticmethod` doesn't
    have that.

    To work with OOP inheritance, in the decorator list, `@generic` must be
    on inside of (i.e. run before) `@classmethod` or `@staticmethod`.

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
    # The inspect stdlib module docs are useful here:
    #     https://docs.python.org/3/library/inspect.html
    def getfullname(f):
        function, _ = getfunc(f)
        return "{}.{}".format(inspect.getmodule(f), function.__qualname__)
    fullname = getfullname(f)

    # HACK for cls/self analysis
    def name_of_1st_positional_parameter(f):
        function, _ = getfunc(f)
        params = inspect.signature(function).parameters
        poskinds = set((inspect.Parameter.POSITIONAL_ONLY,
                        inspect.Parameter.POSITIONAL_OR_KEYWORD))
        for param in params.values():
            if param.kind in poskinds:
                return param.name
        return None

    if fullname not in _dispatcher_registry:
        # Create the dispatcher. This will replace the original f.
        @wraps(f)
        def dispatcher(*args, **kwargs):
            # `signature` comes from typing.get_type_hints.
            # `bindings` is populated in the surrounding scope below.
            def match_argument_types(type_signature):
                # TODO: handle **kwargs (bindings["kwarg"], bindings["kwarg_name"])
                args_items = bindings["args"].items()
                if bindings["vararg_name"]:
                    vararg_item = (bindings["vararg_name"], bindings["vararg"])  # *args
                    all_items = tuple(chain(args_items, (vararg_item,)))
                else:
                    all_items = args_items

                for parameter, value in all_items:
                    assert parameter in type_signature  # resolve_bindings should already TypeError when not.
                    expected_type = type_signature[parameter]
                    if not isoftype(value, expected_type):
                        return False
                return True

            # Dispatch.
            def methods():
                # For regular functions, ours is the only registry we need to look at:
                relevant_registries = [reversed(dispatcher._method_registry)]

                # But if this dispatcher is installed on an OOP method, we must
                # look up generic function methods also in the class's MRO.
                #
                # For *static methods* MRO is not supported. Basically, one of
                # the roles of `cls` or `self` is to define the MRO; a static
                # method doesn't have that.
                #
                # See discussions on interaction between `@staticmethod` and `super` in Python:
                #   https://bugs.python.org/issue31118
                #    https://stackoverflow.com/questions/26788214/super-and-staticmethod-interaction/26807879
                #
                # TODO/FIXME: Not possible to detect self/cls parameters correctly.
                # Here we're operating at the wrong abstraction level for that,
                # since we see just bare functions.
                #
                # Let's see if we might have a self/cls parameter, and if so, get its value.
                first_param_name = name_of_1st_positional_parameter(f)
                if first_param_name in self_parameter_names:
                    if len(args) < 1:  # pragma: no cover, shouldn't happen.
                        raise TypeError("MRO lookup failed: no value provided for self-like parameter {} when calling generic-function OOP method {}".format(repr(first_param_name), fullname))
                    first_arg_value = args[0]
                    dynamic_instance = first_arg_value  # self/cls
                    theclass = None
                    if isinstance(dynamic_instance, type):  # cls
                        theclass = dynamic_instance
                    elif hasattr(dynamic_instance, "__class__"):  # self
                        theclass = dynamic_instance.__class__
                    if theclass is not None:  # ignore false positives when possible
                        for base in theclass.__mro__[1:]:  # skip the class itself in the MRO
                            if hasattr(base, f.__name__):  # does this particular super have f?
                                base_oop_method = getattr(base, f.__name__)
                                base_raw_function, _ = getfunc(base_oop_method)
                                if hasattr(base_raw_function, "_method_registry"):  # it's @generic
                                    base_registry = getattr(base_raw_function, "_method_registry")
                                    relevant_registries.append(reversed(base_registry))

                return chain.from_iterable(relevant_registries)
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
                thecallable, type_signature = method
                function, _ = getfunc(thecallable)
                filename = inspect.getsourcefile(function)
                source, firstlineno = inspect.getsourcelines(function)
                return "{} from {}:{}".format(type_signature, filename, firstlineno)
            methods_str = ["  {}".format(format_method(x)) for x in methods()]
            candidates = "\n".join(methods_str)
            function, _ = getfunc(f)
            msg = ("No method found matching {}({}{}{}).\n"
                   "Candidate signatures (in order of match attempts):\n{}").format(function.__qualname__,
                                                                                    ", ".join(a),
                                                                                    sep, ", ".join(kw),
                                                                                    candidates)
            raise TypeError(msg)

        dispatcher._method_registry = []
        def register(thecallable):
            """Decorator. Register a new method for this generic function.

            The method must have type annotations for all of its parameters;
            these are used for dispatching.

            An exception is the `self` or `cls` parameter of an OOP instance
            method or class method; that does not participate in dispatching,
            and does not need a type annotation.
            """
            # Using `inspect.signature` et al., we could auto-`Any` parameters
            # that have no type annotation, but that would likely be a footgun.
            # So we require a type annotation for each parameter.
            #
            # One exception: the self/cls parameter of OOP instance methods and
            # class methods is not meaningful for dispatching, and we don't
            # have a runtime value to auto-populate its expected type when the
            # definition runs. So we set it to `typing.Any` in the method's
            # expected type signature, which makes the dispatcher ignore it.

            function, kind = getfunc(thecallable)
            params = inspect.signature(function).parameters
            params_names = [p.name for p in params.values()]
            type_signature = typing.get_type_hints(function)

            # In the type signature, auto-`Any` the self/cls parameter, if any.
            #
            # TODO/FIXME: Not possible to detect self/cls parameters correctly.
            #
            # The `@generic` decorator runs while the class body is being
            # evaluated. In that context, an instance method looks just like a
            # regular function.
            #
            # Also if `@generic` runs before `@classmethod` (to place Python's
            # implicit `cls` handling outermost), also a class method looks
            # just like a regular function to us.
            #
            # So we HACK, and special-case some suggestive *parameter names*
            # when they appear the first position, though **Python itself
            # doesn't do that**. For any crazy person not following Python
            # naming conventions, our approach won't work.
            if len(params_names) >= 1 and params_names[0] in self_parameter_names:
                # In Python 3.6+, `dict` preserves insertion order. Make sure
                # the `self` parameter appears first, for clearer error messages
                # when no matching method is found.
                #
                # TODO: Due to Python 3.4 compatibility, we have to do it like this:
                type_signature_new = {params_names[0]: typing.Any}
                type_signature_new.update(type_signature)
                type_signature = type_signature_new
                # In Python 3.5+, we could just:
                # type_signature = {params_names[0]: typing.Any, **type_signature}

            if not all(name in type_signature for name in params_names):
                failures = [name for name in params_names if name not in type_signature]
                wrapped = ["'{}'".format(x) for x in failures]
                plural = "s" if len(failures) > 1 else ""
                msg = "Method definition missing type annotation for parameter{}: {}".format(plural,
                                                                                             ", ".join(wrapped))
                raise TypeError(msg)

            dispatcher._method_registry.append((thecallable, type_signature))
            return dispatcher  # Replace the callable with the dispatcher for this generic function.

        dispatcher._register = register  # save it for use by us later
        _dispatcher_registry[fullname] = dispatcher
    dispatcher = _dispatcher_registry[fullname]
    if hasattr(dispatcher, "_register"):  # co-operation with @typed, below
        return dispatcher._register(f)
    raise TypeError("@typed: cannot register additional methods.")


@register_decorator(priority=98)
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
    del s._register  # remove the ability to register more methods
    return s
