# -*- coding: utf-8; -*-
"""A multiple-dispatch decorator for Python.

Somewhat like `functools.singledispatch`, but for multiple dispatch.

    https://docs.python.org/3/library/functools.html#functools.singledispatch

For now this is just a simplistic test. If we want to get serious, we must
add support for things like `*args`, `**kwargs`, `typing.Sequence[int]`,
and in 3.8, `typing.Literal['a', 'b', 'c', 'd']`.

**WARNING: PROVISIONAL FEATURE**

This provisional feature is a proof-of-concept provided for technical preview
and teaching purposes only.

Details may still change in a backwards-incompatible way, or the whole
feature may still be removed. Do not depend on it in production!
"""

__all__ = ["generic", "specific"]

from functools import wraps
import inspect
import typing

from .arity import resolve_bindings

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
        def match(signature):
            # TODO: handle *args (bindings["vararg"])
            # TODO: handle **kwargs (bindings["kwarg"])
            # TODO: handle advanced features such as Sequence[int], Optional[str], ...
            for parameter, value in bindings["args"].items():
                p = signature[parameter]  # TODO: what if parameter is not there? TypeError?
                if p is not typing.Any and not isinstance(value, p):
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
            if match(signature):
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
    def register(function):
        """Decorator. Register a new method for this generic function.

        The method must have type annotations for all of its parameters;
        these are used for dispatching.
        """
        # Using `inspect.signature` et al., we could auto-`Any` parameters
        # that have no type annotation, but that would likely be a footgun.
        # So we require a type annotation for each parameter.
        # TODO: verify that there are no parameters that have no type annotation.
        signature = typing.get_type_hints(function)
        multidispatch._registry.append((function, signature))
        return multidispatch  # Replace the function with the dispatcher for this generic function.
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

# --------------------------------------------------------------------------------

@generic
def zorblify():  # could use the ellipsis `...` as the body, but this is a unit test.
    assert False  # Stub, not called.
@zorblify.register
def zorblify(x: int, y: int):
    return 2 * x + y
@zorblify.register
def zorblify(x: str, y: int):
    assert False  # Because dispatching occurs on both arguments, this is not reached in tests.
@zorblify.register
def zorblify(x: str, y: float):
    return "{} {}".format(x[::-1], y)

# TODO: def zorblify(x: int, *args: typing.Sequence[str]):

# @generic can also be used to simplify argument handling code in functions
# where the role of an argument in a particular position changes depending on
# the number of arguments (like the range() builtin).
#
# The pattern is that the generic function canonizes the arguments:
@generic
def example(): ...
@example.register
def example(start: int, stop: int):
    return _example_impl(start, 1, stop)
@example.register
def example(start: int, step: int, stop: int):
    return _example_impl(start, step, stop)
# ...after which the actual implementation always gets them in the same format.
def _example_impl(start, step, stop):
    return start, step, stop

# One-method pony.
@specific
def blubnify(x: int, y: float):
    return x * y

def test():
    assert zorblify(17, 8) == 42
    assert zorblify(17, y=8) == 42  # can also use named arguments
    assert zorblify(y=8, x=17) == 42
    assert zorblify("tac", 1.0) == "cat 1.0"
    assert zorblify(y=1.0, x="tac") == "cat 1.0"

    try:
        zorblify(1.0, 2.0)
    except TypeError:
        pass
    else:
        assert False  # there's no zorblify(float, float)

    assert example(1, 5) == (1, 1, 5)
    assert example(1, 1, 5) == (1, 1, 5)
    assert example(1, 2, 5) == (1, 2, 5)

    assert blubnify(2, 21.0) == 42
    try:
        blubnify(2, 3)
    except TypeError:
        pass
    else:
        assert False  # blubnify only accepts (int, float)
    assert not hasattr(blubnify, "register")

    print("All tests PASSED")

if __name__ == '__main__':
    test()
