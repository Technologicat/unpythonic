# -*- coding: utf-8; -*-
"""A multiple-dispatch decorator for Python.

Somewhat like `functools.singledispatch`, but multiple dispatch.

    https://docs.python.org/3/library/functools.html#functools.singledispatch

For now this is just a simplistic test. If we want to get serious, we must
add support for things like `*args`, `**kwargs`, `typing.Sequence[int]`,
and in 3.8, `typing.Literal['a', 'b', 'c', 'd']`.

**WARNING: PROVISIONAL FEATURE**

This provisional feature is provided for technical preview purposes only.
Details may still change in a backwards-incompatible way, or the whole
feature may still be removed. Do not depend on it in production!
"""

from collections import defaultdict
from functools import wraps
import inspect
import typing

from .arity import resolve_bindings

registry = defaultdict(list)

def generic(f):
    """Decorator. Make `f` a generic function (in the sense of CLOS or Julia).

    Methods are attached by specifying type hints on parameters when defining
    implementations. Then, at call time, types of **all** arguments are then
    automatically used for choosing which method to call. Multiple parameters
    may be used for dispatching.

    The point of this feature is to eliminate `if`/`elif`/`elif`... blocks
    that switch by `isinstance` on arguments (and then raise `TypeError`
    in the final `else`), by implementing the machinery once centrally.

    Unlike `typing.overload`, the implementation belongs right there in the
    type-specialized methods. Unlike `functools.singledispatch`, there is
    no need to provide a fallback non-annotated implementation (and in fact
    that is not supported).

    Upon ambiguity, the method that was most recently registered wins. So
    specify the implementation with the most generic types first, and then
    move on to the more specific ones. The mnemonic is, "the function is
    generally defined like this, except if you get arguments that match
    these particular types..."

    **CAUTION**:

    Currently, the shape of the parameter list must agree between all methods
    of the same generic function, and advanced features of `typing` are not
    supported.

    Use `typing.Any` to declare a dynamically typed parameter - don't just omit
    the type annotation, that won't work.
    """
    fullname = "{}.{}".format(f.__module__, f.__qualname__)
    signature = typing.get_type_hints(f)
    registry[fullname].append((f, signature))
    @wraps(f)
    def multidispatch(*args, **kwargs):
        # TODO: This uses the definition of `f` this particular instance of the decorator
        # TODO: was applied to. Maybe we should check, upon registration, that the shape
        # TODO: of the parameter list matches for each method of the same generic function.
        bindings = resolve_bindings(f, *args, **kwargs)

        def match(signature):
            # TODO: handle *args (bindings["vararg"]) and **kwargs (bindings["kwarg"])
            for parameter, value in bindings["args"].items():
                p = signature[parameter]  # TODO: what if parameter is not there? TypeError?
                if p is not typing.Any and not isinstance(value, p):
                    return False
            return True

        methods = tuple(reversed(registry[fullname]))
        for method, signature in methods:
            if match(signature):
                return method(*args, **kwargs)

        # No match, report error.
        #
        # TODO: It would be nice to show the type signature of the args actually given,
        # TODO: but in the general case this is difficult. We can't just `type(x)`, since
        # TODO: the signature may specify something like `Sequence[int]`. Knowing a `list`
        # TODO: was passed doesn't help debug that it was `Sequence[str]` when a `Sequence[int]`
        # TODO: was expected. The actual value at least contains the type information implicitly.
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
        methods_str = ["  {}".format(format_method(x)) for x in methods]
        candidates = "\n".join(methods_str)
        msg = ("No method found matching {}({}{}{}).\n"
               "Candidate signatures (in order of match attempts):\n{}").format(f.__qualname__,
                                                                                ", ".join(a),
                                                                                sep, ", ".join(kw),
                                                                                candidates)
        raise TypeError(msg)
    return multidispatch

# --------------------------------------------------------------------------------

@generic
def zorblify(x: int, y: int):
    return 2 * x + y
@generic
def zorblify(x: str, y: int):
    # Because dispatching occurs on both arguments, this is not reached in tests.
    assert False
@generic
def zorblify(x: str, y: float):
    return "{} {}".format(x[::-1], y)

# TODO: def zorblify(x: int, *args: typing.Sequence[str]):

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
        assert False  # should have noticed there's no method registered for zorblify(float, float)

    print("All tests PASSED")

if __name__ == '__main__':
    test()
