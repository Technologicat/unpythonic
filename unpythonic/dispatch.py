# -*- coding: utf-8; -*-
"""A multiple-dispatch system (a.k.a. multimethods) for Python.

Terminology:

  - The function that supports multiple call signatures is a *generic function*.
  - Its individual implementations are *multimethods*.

We use the term *multimethod* to distinguish them from the usual sense of *method*
in Python, and because this is multiple dispatch.

Somewhat like `functools.singledispatch`, but for multiple dispatch.

    https://docs.python.org/3/library/functools.html#functools.singledispatch

Somewhat like `typing.overload`, but for run-time use, not static type-checking.
Here the implementations are given in the multimethod bodies.

    https://docs.python.org/3/library/typing.html#typing.overload
"""

__all__ = ["isgeneric", "generic", "augment", "typed",
           "methods", "format_methods", "list_methods"]

from functools import partial, wraps
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
# self_parameter_names.__doc__ = """`self`/`cls` parameter names for `@generic`.
#
# When one of these parameter names appears in the first positional parameter position
# of a function decorated with `@generic` (or `@typed`), it is detected as being an
# OOP-related `self` or `cls` parameter, triggering special handling.
#
# If you use something other than the usual Python naming conventions for the `self`/`cls`
# parameter, just append the names you use to this list.
# """

def isgeneric(f):
    """Return whether the callable `f` is a generic function.

    If `f` was declared `@generic` (which see), return the string `"generic"`.
    If `f` was declared `@typed` (which see), return the string `"typed"`.
    Else return `False`.
    """
    if hasattr(f, "_method_registry"):
        if hasattr(f, "_register"):
            return "generic"
        return "typed"
    return False

# TODO: We essentially need the fullname because the second and further invocations
# TODO: of `@generic`, for the same generic function, receive an entirely different
# TODO: run-time object - the new multimethod. There is no way to know which existing
# TODO: dispatcher to connect that to, other than having a registry that maps the
# TODO: fullname of each already-existing generic function to its dispatcher object.
@register_decorator(priority=98)
def generic(f):
    """Decorator. Make `f` a generic function (in the sense of CLOS or Julia).

    Multiple dispatch solves *the expression problem*:
        https://en.wikipedia.org/wiki/Expression_problem

    Practical use cases:

      - Eliminate `if`/`elif`/`elif`... blocks that switch by `isinstance` on
        function arguments, and then raise `TypeError` in the final `else`,
        by having a central implementation for this machinery.

        This not only kills boilerplate, but makes the dispatch extensible,
        since the dispatcher lives outside the original function definition.
        There is no need to monkey-patch the original to add a new case.

        See `@augment`.

      - Dispatch on an extensible hierarchy of abstract features (called *traits*)
        that is separate from the concrete type hierarchy, using the *holy traits*
        pattern. For example, "behaves like a number" can be a trait.

        See `unpythonic/tests/test_dispatch.py` for an example.

      - Functions like the builtin `range`, where the *role* of an argument in a
        particular position depends on the *number of* arguments passed in the call.
        With `@generic`, each case can have its parameters named descriptively.

    **How to use**:

    Make several function definitions, with the same name in the same lexical
    scope, one for each call signature you want to support, and decorate each of
    them with `@generic`. Here *signature* refers to specific combinations of
    argument types and/or different shapes for the argument list.

    The first definition implicitly creates the generic function (like in
    Julia). All of the definitions, including the first one, become registered
    as *multimethods* of the *generic function*.

    The return value of `generic` is the multiple-dispatch dispatcher
    for the generic function that was created or modified.

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
        @generic  # noqa: F811, registered as a multimethod of the same generic function.
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
    function, that will not remove previously existing method definitions.
    If you later rebind the same name again, pointing to a new generic function,
    it will suddenly gain all of the methods of the previous function that had
    the same fullname.

    As of v0.15.0, multimethods cannot be unregistered.

    **Multimethod lookup**:

    Each method definition must specify type hints **on all of its parameters**.
    Then, at call time, the types of **all** arguments, as well as the number
    of arguments, are automatically used for *dispatching*, i.e. choosing which
    implementation to call. In other words, multiple parameters participate in
    dispatching, hence *multiple dispatch*.

    **Varargs are supported**. Vararg type hint examples::

        - `*args: typing.Tuple[int, ...]` means "any number of `int`s"
        - `*args: typing.Tuple[int, float, str]` means "exactly `(int, float, str)`,
          in that order"
        - `**kwargs: typing.Dict[str, int]` means "all **kwargs are of type `int`".
          Note the key type for the `**kwargs` dict is always `str`.

    **The first multimethod that matches wins, in most-recently-registered order.**
    (This is unlike in Julia, which matches the most specific applicable multimethod.)

    In other words, later multimethod definitions override earlier ones. So specify
    the implementation with the most generic types first, and then move on to the
    more specific ones. The mnemonic is, "the function is generally defined like
    this, except if the arguments match these particular types..."

    **Differences to tools in the standard library**:

    Unlike in `functools.singledispatch`, there is no "master" definition and
    no public `register` attribute. Instead, generic functions are saved in a
    global registry.

    Unlike `typing.overload`, the implementations are given in the multimethod
    bodies.

    **Interaction with OOP**:

    Beside regular functions, `@generic` can be installed on instance, class
    or static *methods* (in the OOP sense). `self` and `cls` parameters do not
    participate in dispatching, and need no type annotation.

    On instance and class methods, the self-like parameter, beside appearing as
    the first positional-or-keyword parameter, **must be named** one of `self`,
    `this`, `cls`, or `klass` to be detected by the ignore mechanism. This
    limitation is due to implementation reasons; while a class body is being
    evaluated, the context needed to distinguish a method from a regular function
    is not yet present.

    When `@generic` is installed on an instance method or on a `@classmethod`,
    then at call time, classes are tried in MRO order. **All** multimethods
    of the method defined in the class currently being looked up are tested
    for matches first, **before** moving on to the next class in the MRO.
    This has subtle consequences, related to in which class in the hierarchy
    the various multimethods for a particular method are defined.

    For *static methods* MRO lookup is not supported. Basically, one of the
    roles of `cls` or `self` is to define the MRO; a `@staticmethod` doesn't
    have that.

    To work with OOP inheritance, in the decorator list, `@generic` must be
    on inside of (i.e. run before) `@classmethod` or `@staticmethod`.

    **CAUTION**:

    To declare a parameter of a multimethod as dynamically typed, explicitly
    annotate it as `typing.Any`; don't just omit the type annotation.
    Explicit is better than implicit; **this is a feature**.

    See the limitations in `unpythonic.typecheck` for which features of the
    `typing` module are supported and which are not.

    At the moment, `@generic` does not work with `curry`. Adding curry support
    needs changes to the dispatch logic in `curry`.

    """
    return _register_generic(_function_fullname(f), f)

@register_decorator(priority=98)
def augment(target):
    """Parametric decorator. Add a multimethod to generic function `target`.

    Like `@generic`, but the generic function on which the method will be
    registered is chosen separately, so that you can augment a generic
    function previously defined in some other `.py` source file.

    The return value of `augment` is the multiple-dispatch dispatcher
    for the generic function that was modified.

    Usage::

        # example.py
        from unpythonic import generic

        @generic
        def f(x: int):
            ...


        # main.py
        from unpythonic import augment
        import example

        class MyOwnType:
            ...

        @augment(example.f)
        def f(x: MyOwnType):
            ...

    **CAUTION**: Beware of type piracy when you use `@augment`. That is:

        1. For arbitrary input types you don't own, augment only a function you own, OR
        2. Augment a function defined somewhere else only if at least one parameter
           (in the call signature you are adding) is of a type you own.

    Satisfying **one** of these conditions is sufficient to avoid type piracy.

    See:
        https://lexi-lambda.github.io/blog/2016/02/18/simple-safe-multimethods-in-racket/
        https://en.wikipedia.org/wiki/Action_at_a_distance_(computer_programming)
        https://docs.julialang.org/en/v1/manual/style-guide/#Avoid-type-piracy
    """
    if not isgeneric(target):
        raise TypeError(f"{target} is not a generic function, cannot add multimethods to it.")
    return partial(_register_generic, _function_fullname(target))

@register_decorator(priority=98)
def typed(f):
    """Decorator. Restrict allowed argument types to one combination only.

    This can be used to eliminate `isinstance` boilerplate code in the
    function body, by allowing the types (for dynamic, run-time checking)
    to be specified with a very compact syntax - namely, type annotations.

    Also, unlike a basic `isinstance` check, this allows using features
    from the `typing` stdlib module in the type specifications.

    Once a `@typed` function has been created, no more multimethods can be
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

def methods(f):
    """Print, to stdout, a human-readable list of multimethods currently registered to `f`.

    For introspection in the REPL. This works by calling `list_methods`, which see.

    This is like the `methods` function of Julia.
    """
    print(format_methods(f))

def format_methods(f):
    """Format, as a string, a human-readable list of multimethods currently registered to `f`.

    One level lower than `methods`; format a human-readable message, but return it
    instead of printing it.

    This works by calling `list_methods`, which see.
    """
    function, _ = getfunc(f)
    multimethods = list_methods(f)
    if multimethods:
        methods_list = [f"  {_format_method(x)}" for x in multimethods]
        methods_str = "\n".join(methods_list)
    else:  # pragma: no cover, in practice should always have one method.
        methods_str = "  <no multimethods registered>"
    return f"Multimethods for @{isgeneric(f)} {repr(function.__qualname__)}:\n{methods_str}"

def list_methods(f):
    """Return a list of the multimethods currently registered to `f`.

    The multimethods are returned in the order they would be tested by the dispatcher
    when the generic function is called.

    The return value is a list, where each item is `(callable, type_signature)`.
    Each type signature is in the format returned by `typing.get_type_hints`.

    `f`: a callable that has been declared `@generic` or `@typed`.

         **Interaction with OOP**:

         Bound methods are resolved to the underlying function automatically.
         The `self`/`cls` argument is extracted from the `__self__` attribute of
         the bound method, enabling linked dispatcher lookups in the MRO.

         **CAUTION**:

         Recall that in Python, instance methods when accessed through the *class*
         are just raw functions; the method becomes bound, and thus `self` is set,
         when accessed through *an instance* of that class.

         Let `Cat` be a class with an OOP instance method `meow`, and `cat` an
         instance of that class. If you call `list_methods(cat.meow)`, you get the
         MRO lookup for linked dispatchers, as expected.

         But if you call `list_methods(Cat.meow)` instead, it won't see the MRO,
         because the value of the `self` argument isn't set for an unbound method
         (which is really just a raw function).

         If `Cat` has a `@classmethod` `iscute`, calling `list_methods(Cat.iscute)`
         performs the MRO lookup for linked dispatchers. This is because a class
         method is already bound (to the class, so the `cls` argument already has
         a value) when it is accessed through the class.

         Finally, note that while that is how `list_methods` works, it is not the
         mechanism actually used to determine `self`/`cls` when *calling* the
         generic function. There, the value of `self`/`cls` is extracted from the
         first positional argument of the call. This is because the dispatcher is
         actually installed on the underlying raw function, so it has no access to
         the metadata of the bound method (which, as seen from the dispatcher, is
         on the outside).
    """
    function, _ = getfunc(f)
    if not isgeneric(function):
        raise TypeError(f"{repr(function.__qualname__)} is not a generic function, it does not have multimethods.")

    # In case of a bound method (either `Foo.classmeth` or `foo.instmeth`),
    # we can get the value for `self`/`cls` argument from its `__self__` attribute.
    #
    # Otherwise we have a regular function, an unbound method, or a `@staticmethod`;
    # in those cases, there's no `self`/`cls`. (Technically, an unbound method has
    # a parameter to receive it, but no value has been set yet.)
    self_or_cls = f.__self__ if hasattr(f, "__self__") else None
    return _list_multimethods(function, self_or_cls)

# --------------------------------------------------------------------------------

# Modeled after `mcpyrate.utils.format_macrofunction`, which does the same thing for macros.
def _function_fullname(f):
    function, _ = getfunc(f)  # get the raw function also for OOP methods
    if not function.__module__:  # At least macros defined in the REPL have `__module__=None`.
        return function.__qualname__
    return f"{function.__module__}.{function.__qualname__}"

def _name_of_1st_positional_parameter(f):
    function, _ = getfunc(f)  # get the raw function also for OOP methods
    parameters = inspect.signature(function).parameters
    poskinds = set((inspect.Parameter.POSITIONAL_ONLY,
                    inspect.Parameter.POSITIONAL_OR_KEYWORD))
    for param in parameters.values():
        if param.kind in poskinds:
            return param.name
    return None

def _list_multimethods(dispatcher, self_or_cls=None):
    """List multimethods currently registered to a given dispatcher.

    `self_or_cls`: If `dispatcher` is installed on an instance method
                   or on a `@classmethod`, set this to perform MRO
                   lookups to find linked dispatchers.
    """
    # TODO: Compute closest candidates, like Julia does? (see `methods`, `MethodError` in Julia)
    # TODO: (If we do that, we need to look at the bound arguments. When just listing multimethods
    # TODO: in the REPL, the current ordering is probably fine.)

    # For regular functions, ours is the only registry we need to look at:
    relevant_registries = [reversed(dispatcher._method_registry)]

    # But if this dispatcher is installed on a method, we must
    # look up multimethods also in the class's MRO.
    #
    # For *static methods* MRO is not supported. Basically, one of
    # the roles of `cls` or `self` is to define the MRO; a static
    # method doesn't have that.
    #
    # See discussions on interaction between `@staticmethod` and `super` in Python:
    #   https://bugs.python.org/issue31118
    #   https://stackoverflow.com/questions/26788214/super-and-staticmethod-interaction/26807879
    if self_or_cls:
        if isinstance(self_or_cls, type):
            cls = self_or_cls
        elif hasattr(self_or_cls, "__class__"):
            cls = self_or_cls.__class__
        else:
            assert False

        for base in cls.__mro__[1:]:  # skip the class itself in the MRO
            if hasattr(base, dispatcher.__name__):  # does this particular super have f?
                base_oop_method = getattr(base, dispatcher.__name__)
                base_raw_function, _ = getfunc(base_oop_method)
                if isgeneric(base_raw_function):  # it's @generic or @typed
                    base_registry = getattr(base_raw_function, "_method_registry")
                    relevant_registries.append(reversed(base_registry))

    return list(chain.from_iterable(relevant_registries))

# input format is an item returned by `_list_multimethods`
def _format_method(method):  # Taking a page from Julia and some artistic liberty here.
    thecallable, type_signature = method
    # Our `type_signature` is based on `typing.get_type_hints`,
    # but for the error message, we need something that formats
    # like source code. Hence we use `inspect.signature`.
    thesignature = inspect.signature(thecallable)
    function, _ = getfunc(thecallable)
    filename = inspect.getsourcefile(function)
    source, firstlineno = inspect.getsourcelines(function)
    return f"{thecallable.__qualname__}{str(thesignature)} from {filename}:{firstlineno}"

# `type_signature`: in the format returned by `typing.get_type_hints`.
# `bound_arguments`: see `unpythonic.arity.resolve_bindings`.
def _match_argument_types(type_signature, bound_arguments):
    for parameter, value in bound_arguments.arguments.items():
        assert parameter in type_signature  # resolve_bindings should already TypeError when not.
        expected_type = type_signature[parameter]
        if not isoftype(value, expected_type):
            return False
    return True

def _raise_multiple_dispatch_error(dispatcher, args, kwargs, *, candidates):
    # TODO: It would be nice to show the type signature of the args actually given,
    # TODO: but in the general case this is difficult. We can't just `type(x)`, since
    # TODO: the signature may specify something like `Sequence[int]`. Knowing a `list`
    # TODO: was passed doesn't help debug that it was `Sequence[str]` when a `Sequence[int]`
    # TODO: was expected. The actual value at least implicitly contains the type information.
    args_list = [repr(x) for x in args]
    args_str = ", ".join(args_list)
    sep = ", " if args and kwargs else ""
    kws_list = [f"{k}={repr(v)}" for k, v in kwargs.items()]
    kws_str = ", ".join(kws_list)
    methods_list = [f"  {_format_method(x)}" for x in candidates]
    methods_str = "\n".join(methods_list)
    msg = (f"No multiple-dispatch match for the call {dispatcher.__qualname__}({args_str}{sep}{kws_str}).\n"
           f"Multimethods for @{isgeneric(dispatcher)} {repr(dispatcher.__qualname__)} (most recent match attempt last):\n{methods_str}")
    raise TypeError(msg)

def _register_generic(fullname, multimethod):
    """Register a multimethod for a generic function.

    This is a low-level function; you'll likely want `@generic` or `@augment`.

    fullname: str, fully qualified name of function to register the multimethod
              on, used as key in the dispatcher registry.

              Registering the first multimethod on a given `fullname` makes
              that function generic, and creates the dispatcher for it.

              Second and further registrations using the same `fullname` add
              the new multimethod to the existing dispatcher.

    multimethod: callable, the new multimethod to register.

    Return value is the dispatcher.
    """
    if fullname not in _dispatcher_registry:
        # Create the dispatcher. This will replace the original function.
        #
        # TODO/FIXME: Not possible to detect `self`/`cls` parameters correctly.
        #
        # Here we're operating at the wrong abstraction level for that,
        # since we see just bare functions. In the OOP case, the dispatcher
        # is installed on the raw function before it becomes a bound method.
        # (That in itself is just as it should be.)
        first_param_name = _name_of_1st_positional_parameter(multimethod)
        most_likely_an_oop_method = first_param_name in self_parameter_names
        @wraps(multimethod)
        def dispatcher(*args, **kwargs):
            # Let's see if we might have been passed a `self`/`cls` parameter,
            # and if so, get its value. (Recall that in Python, it is always
            # the first positional parameter.)
            if most_likely_an_oop_method:
                if len(args) < 1:  # pragma: no cover, shouldn't happen.
                    raise TypeError(f"MRO lookup failed: no value provided for self-like parameter {repr(first_param_name)} when calling OOP method-like generic function {fullname}")
                self_or_cls = args[0]
            else:
                self_or_cls = None

            # Dispatch.
            multimethods = _list_multimethods(dispatcher, self_or_cls)
            for thecallable, type_signature in multimethods:
                try:
                    bound_arguments = resolve_bindings(thecallable, *args, **kwargs)
                except TypeError:  # arity mismatch, so this method can't be the one the call is looking for.
                    continue
                if _match_argument_types(type_signature, bound_arguments):
                    return thecallable(*args, **kwargs)

            # No match, report error.
            _raise_multiple_dispatch_error(dispatcher, args, kwargs, candidates=multimethods)

        dispatcher._method_registry = []
        def register(multimethod):
            """Decorator. Register a new multimethod for this generic function.

            The multimethod must have type annotations for all of its parameters;
            these are used for dispatching.

            An exception is the `self` or `cls` parameter of an OOP instance
            method or class method; that does not participate in dispatching,
            and does not need a type annotation.
            """
            # Using `inspect.signature` et al., we could auto-`Any` parameters
            # that have no type annotation, but that would likely be a footgun.
            # So we require a type annotation for each parameter.
            #
            # One exception: the `self`/`cls` parameter of OOP instance methods and
            # class methods is not meaningful for dispatching, and we don't
            # have a runtime value to auto-populate its expected type when the
            # definition runs. So we set it to `typing.Any` in the multimethod's
            # expected type signature, which makes the dispatcher ignore it.

            function, _ = getfunc(multimethod)
            parameters = inspect.signature(function).parameters
            parameter_names = [p.name for p in parameters.values()]
            type_signature = typing.get_type_hints(function)

            # In the type signature, auto-`Any` the `self`/`cls` parameter, if any.
            #
            # TODO/FIXME: Not possible to detect `self`/`cls` parameters correctly.
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
            if len(parameter_names) >= 1 and parameter_names[0] in self_parameter_names:
                # In Python 3.6+, `dict` preserves insertion order. Make sure
                # the `self` parameter appears first, for clearer error messages
                # when no matching method is found.
                type_signature = {parameter_names[0]: typing.Any, **type_signature}

            if not all(name in type_signature for name in parameter_names):
                failures = [name for name in parameter_names if name not in type_signature]
                plural = "s" if len(failures) > 1 else ""
                repr_list = [repr(x) for x in failures]
                repr_str = ", ".join(repr_list)
                msg = f"Multimethod definition missing type annotation for parameter{plural}: {repr_str}"
                raise TypeError(msg)

            dispatcher._method_registry.append((multimethod, type_signature))

            # Update entry point docstring to include docs for the new multimethod,
            # and its call signature.
            call_signature_desc = _format_method((multimethod, type_signature))
            our_doc = call_signature_desc
            if multimethod.__doc__:
                our_doc += "\n" + multimethod.__doc__

            isfirstmultimethod = len(dispatcher._method_registry) == 1
            if isfirstmultimethod or not dispatcher.__doc__:
                # Override the original doc of the function that was converted
                # into the dispatcher; this adds the call signature to the top.
                dispatcher.__doc__ = our_doc
            else:
                # Add the call signature and doc for the new multimethod.
                dispatcher.__doc__ += "\n\n" + ("-" * 80) + "\n"
                dispatcher.__doc__ += our_doc

            return dispatcher  # Replace the multimethod callable with this generic function's dispatcher.

        dispatcher._register = register
        _dispatcher_registry[fullname] = dispatcher

    dispatcher = _dispatcher_registry[fullname]
    if isgeneric(dispatcher) == "typed":
        raise TypeError("@typed: cannot register additional multimethods.")
    return dispatcher._register(multimethod)
