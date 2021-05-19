# -*- coding: utf-8 -*-
"""Inspect the arity of a callable.

This module uses ``inspect`` out of necessity. The idea is to provide something
like Racket's (arity-includes?).
"""

__all__ = ["getfunc",
           "arities", "arity_includes",
           "required_kwargs", "optional_kwargs", "kwargs",
           "resolve_bindings", "resolve_bindings_partial", "tuplify_bindings",
           "UnknownArity"]

from collections import OrderedDict
import copy
from inspect import signature, Parameter, ismethod, BoundArguments, _empty
import itertools
import operator

class UnknownArity(ValueError):
    """Raised when the arity of a function cannot be inspected."""

# HACK: some built-ins report incorrect arities (0, 0) at least in Python 3.4
# TODO: re-test on 3.8 and on PyPy3 (3.7), just to be sure.
#
# Full list of built-ins:
#   https://docs.python.org/3/library/functions.html
# Some are accessible via the operator module:
#   https://docs.python.org/3/library/operator.html
#
# Note this doesn't cover methods such as list.append, or any other parts
# of the standard library.
_infty = float("+inf")
_builtin_arities = {  # inspectable, but reporting incorrectly
                    bool: (1, 1),       # bool(x)
                    bytes: (0, 3),      # see help(bytes)
                    complex: (1, 2),    # complex(real, [imag])
                    enumerate: (1, 2),  # enumerate(iterable, [start])
                    filter: (2, 2),     # filter(function or None, iterable)
                    float: (1, 1),      # float(x)
                    frozenset: (0, 1),  # frozenset(), frozenset(iterable)
                    int: (0, 2),        # int(x=0), int(x, base=10)
                    map: (1, _infty),   # map(func, *iterables)
                    memoryview: (1, 1),  # memoryview(object)
                    object: (0, 0),     # object()
                    range: (1, 3),      # range(stop), range(start, stop, [step])
                    reversed: (1, 1),   # reversed(sequence)
                    slice: (1, 3),      # slice(stop), slice(start, stop, [step])
                    str: (0, 3),        # see help(str)
                    tuple: (0, 1),      # tuple(), tuple(iterable)
                    zip: (1, _infty),   # zip(iter1 [,iter2 [...]])
                    # not inspectable
                    abs: (1, 1),
                    all: (1, 1),
                    any: (1, 1),
                    ascii: (1, 1),
                    bin: (1, 1),
                    bytearray: (0, 3),
                    callable: (1, 1),
                    chr: (1, 1),
                    classmethod: (1, 1),
                    compile: (3, 5),
                    delattr: (2, 2),
                    dict: (0, 1),       # dict(), dict(mapping), dict(iterable)
                    dir: (0, 1),
                    divmod: (2, 2),
                    eval: (1, 3),
                    exec: (1, 3),
                    format: (1, 2),
                    getattr: (2, 3),
                    globals: (0, 0),
                    hasattr: (2, 2),
                    hash: (1, 1),
                    help: (0, 1),
                    hex: (1, 1),
                    id: (1, 1),
                    input: (0, 1),      # input([prompt])
                    isinstance: (2, 2),
                    issubclass: (2, 2),
                    iter: (1, 2),
                    len: (1, 1),
                    list: (0, 1),       # list(), list(iterable)
                    locals: (0, 0),
                    max: (1, _infty),   # max(iterable), max(a1, a2, ...)
                    min: (1, _infty),   # min(iterable), min(a1, a2, ...)
                    next: (1, 2),
                    oct: (1, 1),
                    open: (1, 8),       # FIXME: is this correct? are the rest positional or by-name?
                    ord: (1, 1),
                    pow: (2, 3),
                    print: (1, _infty),
                    property: (1, 4),   # property(getx), ..., property(getx, setx, delx, docstring)
                    repr: (1, 1),
                    round: (1, 2),
                    set: (0, 1),        # set(), set(iterable)
                    setattr: (3, 3),
                    sorted: (1, 1),
                    staticmethod: (1, 1),
                    sum: (1, 2),
                    super: (0, 2),
                    type: (1, 3),       # FIXME: exactly 1 or 3: type(object), type(name, bases, dict)
                    vars: (0, 1),
                    __import__: (1, 5),  # FIXME: is this correct? are the rest positional or by-name?
                    # operator module
                    operator.lt: (2, 2),
                    operator.le: (2, 2),
                    operator.eq: (2, 2),
                    operator.ne: (2, 2),
                    operator.ge: (2, 2),
                    operator.gt: (2, 2),
                    operator.not_: (1, 1),
                    operator.truth: (1, 1),
                    operator.is_: (2, 2),
                    operator.is_not: (2, 2),
                    operator.abs: (1, 1),
                    operator.add: (2, 2),
                    operator.and_: (2, 2),
                    operator.floordiv: (2, 2),
                    operator.index: (1, 1),
                    operator.inv: (1, 1),
                    operator.invert: (1, 1),
                    operator.lshift: (2, 2),
                    operator.mod: (2, 2),
                    operator.mul: (2, 2),
                    operator.matmul: (2, 2),
                    operator.neg: (1, 1),
                    operator.or_: (2, 2),
                    operator.pos: (1, 1),
                    operator.pow: (2, 2),
                    operator.rshift: (2, 2),
                    operator.sub: (2, 2),
                    operator.truediv: (2, 2),
                    operator.xor: (2, 2),
                    operator.concat: (2, 2),
                    operator.contains: (2, 2),
                    operator.countOf: (2, 2),
                    operator.delitem: (2, 2),
                    operator.getitem: (2, 2),
                    operator.indexOf: (2, 2),
                    operator.setitem: (3, 3),
                    operator.length_hint: (1, 2),
                    operator.attrgetter: (1, _infty),
                    operator.itemgetter: (1, _infty),
                    operator.methodcaller: (1, _infty),
                    operator.iadd: (2, 2),
                    operator.iand: (2, 2),
                    operator.iconcat: (2, 2),
                    operator.ifloordiv: (2, 2),
                    operator.ilshift: (2, 2),
                    operator.imod: (2, 2),
                    operator.imul: (2, 2),
                    operator.imatmul: (2, 2),
                    operator.ior: (2, 2),
                    operator.ipow: (2, 2),
                    operator.irshift: (2, 2),
                    operator.isub: (2, 2),
                    operator.itruediv: (2, 2),
                    operator.ixor: (2, 2)}

def getfunc(f):  # public as of v0.14.3+
    """Given a function or method, return the underlying function.

    Return value is a tuple ``(function, kind)``, where ``kind`` is one of
    "function", "instancemethod", "classmethod", "staticmethod".

    Note how `inspect.ismethod()`, which we use, behaves::
       a = A()
       inspect.ismethod(A.meth)        # -> False (not bound to instance, __self__ is None)
       inspect.ismethod(A.classmeth)   # -> True
       inspect.ismethod(A.staticmeth)  # -> False
       inspect.ismethod(a.meth)        # -> True
       inspect.ismethod(a.classmeth)   # -> True
       inspect.ismethod(a.staticmeth)  # -> False

    so often you'll get "function" when the sensible answer would be "staticmethod".
    The "staticmethod" kind is only seen if this is called while evaluating a class body;
    particularly, from a decorator that further decorates some `@staticmethod`.
    """
    if ismethod(f):
        # If __self__ points to a class, it's a @classmethod, otherwise a regular instance method.
        # Classes are instances of `type`.
        if isinstance(f.__self__, type):  # TODO: do all custom metaclasses inherit from type?
            kind = "classmethod"
        else:
            kind = "instancemethod"
        raw_function = f.__func__
    else:
        # A staticmethod behaves like a regular function, though it lives in
        # the namespace of a class. `ismethod` doesn't recognize it.
        #
        # Also, while evaluating a class body, `ismethod` always returns False.
        # (Use case: decorator that further decorates a `@classmethod` or a
        # `@staticmethod` calls us to get the underlying function.)
        if isinstance(f, staticmethod):
            kind = "staticmethod"
            raw_function = f.__func__
        elif isinstance(f, classmethod):
            kind = "classmethod"
            raw_function = f.__func__
        else:
            kind = "function"  # a regular function (not a method)
            raw_function = f
    return (raw_function, kind)

def arities(f):
    """Inspect f's minimum and maximum positional arity.

    This uses inspect.signature; note that the signature of builtin functions
    cannot be inspected. This is worked around to some extent, but e.g.
    methods of built-in classes (such as ``list``) might not be inspectable
    (at least on CPython < 3.7).

    For bound methods, ``self`` or ``cls`` does not count toward the arity,
    because these are passed implicitly by Python. Note a `@classmethod` becomes
    bound already when accessed as an attribute of the class, whereas an instance
    method only becomes bound if accessed as an attribute of an instance.

    (In other words, accessing an *instance* method as an attribute of a *class*
     does not implicitly provide a `self`, because there is none to be had. This
     behavior is reflected in the return value of `arities`.)

    If `f` is `@generic` (see `unpythonic.dispatch`), we scan its multimethods,
    and return the smallest `min_arity` and the largest `max_arity`.

    Parameters:
        `f`: function
            The function to inspect.

    Returns:
        `(min_arity, max_arity)`: (int, int_or_infinity)
            where ``max_arity >= min_arity``. If no positional parameters
            of ``f`` have defaults, then ``max_arity == min_arity``.

            If ``f`` takes ``*args``, then ``max_arity == float("+inf")``.

    Raises:
        UnknownArity
            If inspection failed.
    """
    f, kind = getfunc(f)
    try:
        if f in _builtin_arities:
            return _builtin_arities[f]
    except TypeError:  # f is of an unhashable type
        pass

    # Integration with the multiple-dispatch system (multimethods).
    from .dispatch import isgeneric, list_methods  # circular import
    if isgeneric(f):
        min_lower = _infty
        max_upper = 0
        for (thecallable, type_signature) in list_methods(f):
            lower, upper = arities(thecallable)  # let UnknownArity propagate
            if lower < min_lower:
                min_lower = lower
            if upper > max_upper:
                max_upper = upper
        return min_lower, max_upper

    try:
        lower = 0
        upper = 0
        poskinds = set((Parameter.POSITIONAL_ONLY,
                        Parameter.POSITIONAL_OR_KEYWORD))
        for _, v in signature(f).parameters.items():
            if v.kind in poskinds:
                upper += 1
                if v.default is Parameter.empty:
                    lower += 1  # no default --> required parameter
            elif v.kind is Parameter.VAR_POSITIONAL:
                upper = _infty  # no upper limit
        if kind in ("instancemethod", "classmethod"):  # self/cls is passed implicitly
            lower -= 1
            upper -= 1
        return lower, upper
    except (TypeError, ValueError) as e:  # likely an uninspectable method of a builtin
        raise UnknownArity(*e.args)

def required_kwargs(f):
    """Return a set containing the names of required name-only arguments of `f`.

    *Required* means the parameter has no default.

    If `f` is `@generic` (see `unpythonic.dispatch`), we scan its multimethods,
    and return the names of required kwargs accepted by *any* of its multimethods.

    Raises `UnknownArity` if inspection failed.
    """
    return _kwargs(f, optionals=False)

def optional_kwargs(f):
    """Return a set containing the names of optional name-only arguments of `f`.

    *Optional* means the parameter has a default.

    If `f` is `@generic` (see `unpythonic.dispatch`), we scan its multimethods,
    and return the names of optional kwargs accepted by *any* of its multimethods.

    Raises `UnknownArity` if inspection failed.
    """
    return _kwargs(f, optionals=True)

def _kwargs(f, optionals=True):
    f, _ = getfunc(f)

    # Integration with the multiple-dispatch system (multimethods).
    from .dispatch import isgeneric, list_methods  # circular import
    if isgeneric(f):
        thekwargs = {}
        for (thecallable, type_signature) in list_methods(f):
            thekwargs.update(_kwargs(thecallable, optionals=optionals))
        return thekwargs

    try:
        if optionals:
            pred = lambda v: v.default is not Parameter.empty  # optionals
        else:
            pred = lambda v: v.default is Parameter.empty      # requireds
        return {v.name for k, v in signature(f).parameters.items()
                       if v.kind is Parameter.KEYWORD_ONLY and pred(v)}
    except (TypeError, ValueError) as e:
        raise UnknownArity(*e.args)

def kwargs(f):
    """Like Racket's (procedure-keywords).

    Return two sets: the first contains the `required_kwargs` of ``f``,
    the second contains the `optional_kwargs`.

    Raises UnknownArity if inspection failed.
    """
    return (required_kwargs(f), optional_kwargs(f))

def arity_includes(f, n):
    """Check whether f's positional arity includes n.

    I.e., return whether ``f()`` can be called with ``n`` positional arguments.
    """
    lower, upper = arities(f)
    return lower <= n <= upper

def resolve_bindings_partial(f, *args, **kwargs):
    """Like `resolve_bindings`, but use `inspect.Signature.bind_partial`.

    That is, it is acceptable for some parameters of `f` not to have a binding.
    """
    return _resolve_bindings(f, args, kwargs, _partial=True)

def resolve_bindings(f, *args, **kwargs):
    """Resolve parameter bindings established by `f` when called with the given args and kwargs.

    This is an inspection tool, which does not actually call `f`. This is useful for memoizers
    and other similar decorators that need a canonical representation of `f`'s parameter bindings.

    **NOTE**: As of v0.15.0, this is a thin wrapper on top of `inspect.Signature.bind`,
    which was added in Python 3.5. In `unpythonic` 0.14.2 and 0.14.3, we used to have
    our own implementation of the parameter binding algorithm (that ran also on Python 3.4),
    but it is no longer needed, since now we support only Python 3.6 and later.

    The only thing we do beside call `inspect.Signature.bind` is that we apply default values
    (from the definition of `f`) automatically.

    The return value is an `inspect.BoundArguments`. If you want a hashable result,
    postprocess the return value with `tuplify_bindings(result)`.

    For illustration, consider a simplistic memoizer::

        from operator import itemgetter

        def memoize(f):
            memo = {}
            def memoized(*args, **kwargs):
                k = (args, tuple(sorted(kwargs.items(), key=itemgetter(0))))
                if k in memo:
                    return memo[k]
                memo[k] = v = f(*args, **kwargs)
                return v
            return memoized

        @memoize
        def f(a):
            return 2 * a

        f(42)    # --> memoized sees args = (42,), kwargs = {}
        f(a=42)  # --> memoized sees args = (), kwargs = {"a": 42}

    Even though both calls bind {"a": 42} in the body of `f`, the memoizer sees the invocations
    differently, so its cache will miss.

    This problem is solved by `resolve_bindings`::

        from operator import itemgetter

        def memoize(f):
            memo = {}
            def memoized(*args, **kwargs):
                # --> sees the binding {"a": 42} in either case
                k = tuplify_bindings(resolve_bindings(f, *args, **kwargs))
                if k in memo:
                    return memo[k]
                memo[k] = v = f(*args, **kwargs)
                return v
            return memoized

        @memoize
        def f(a):
            return 2 * a

        f(42)
        f(a=42)  # now the cache hits
    """
    return _resolve_bindings(f, args, kwargs, _partial=False)

def _resolve_bindings(f, args, kwargs, *, _partial):
    thesignature = signature(f)
    if _partial:
        bound_arguments = thesignature.bind_partial(*args, **kwargs)
    else:
        bound_arguments = thesignature.bind(*args, **kwargs)
    bound_arguments.apply_defaults()
    return bound_arguments

def tuplify_bindings(bound_arguments):
    """Convert the return value of `resolve_bindings` into a hashable form.

    This is useful for memoizers and similar use cases, which need to use a
    representation of the bindings as a dictionary key.

    `bound_arguments` is an `inspect.BoundArguments` object.

    In our return value, `bound_arguments.arguments` itself, as well as the value of
    the `**kwargs` parameter contained in it, if any, are converted from `OrderedDict`
    to `tuple` using `tuple(od.items())`.

    The result is hashable, if all the passed arguments are.

    See `resolve_bindings` for an example.
    """
    def tuplify(ordereddict):
        return tuple(ordereddict.items())

    # Tuplify the **kwargs dict.
    #
    # The information of which parameter it is, if any, is not contained in the
    # `arguments` attribute of the `BoundArguments` instance; we need to scan
    # the signature (stored in the `signature` attribute) against which the
    # bindings were made.
    for parameter in bound_arguments.signature.parameters.values():
        if parameter.kind == Parameter.VAR_KEYWORD:
            kwargs_param = parameter.name
            break
    else:
        kwargs_param = None

    if kwargs_param:
        thearguments = copy.copy(bound_arguments.arguments)  # avoid mutating our input
        thearguments[kwargs_param] = tuplify(thearguments[kwargs_param])
    else:
        thearguments = bound_arguments.arguments

    return tuplify(thearguments)

# This is `inspect.Signature.bind` from Python 3.8.5, modified for our purposes so we can determine
# unbound *and extra* arguments (both positional and by-name) without raising a `TypeError`.
# We need this for kwargs support in `curry`, because we want to pass through unmatched args and kwargs
# (which otherwise trigger a `TypeError`).
#
# This is only for `curry`; all other code uses the standard implementation.
#
# Used under the PSF license. Copyright (c) 2001, 2002, 2003, 2004, 2005, 2006, 2007, 2008, 2009, 2010,
# 2011, 2012, 2013, 2014, 2015, 2016, 2017, 2018, 2019, 2020 Python Software Foundation; All Rights Reserved
def _bind(thesignature, args, kwargs, *, partial):
    """Private method. Don't use directly."""

    arguments = OrderedDict()

    parameters = iter(thesignature.parameters.values())
    parameters_ex = ()
    arg_vals = iter(args)

    # These are added for `unpythonic`.
    unbound_parameters = []
    extra_args = []
    extra_kwargs = OrderedDict()
    kwargs = copy.copy(kwargs)  # the caller might need the original later

    while True:
        # Let's iterate through the positional arguments and corresponding
        # parameters
        try:
            arg_val = next(arg_vals)
        except StopIteration:
            # No more positional arguments
            try:
                param = next(parameters)
            except StopIteration:
                # No more parameters. That's it. Just need to check that
                # we have no `kwargs` after this while loop
                break
            else:
                if param.kind == Parameter.VAR_POSITIONAL:
                    # That's OK, just empty *args.  Let's start parsing
                    # kwargs
                    break
                elif param.name in kwargs:
                    if param.kind == Parameter.POSITIONAL_ONLY:
                        msg = '{arg!r} parameter is positional only, ' \
                              'but was passed as a keyword'
                        msg = msg.format(arg=param.name)
                        raise TypeError(msg) from None
                    parameters_ex = (param,)
                    break
                elif (param.kind == Parameter.VAR_KEYWORD or
                                            param.default is not _empty):
                    # That's fine too - we have a default value for this
                    # parameter.  So, lets start parsing `kwargs`, starting
                    # with the current parameter
                    parameters_ex = (param,)
                    break
                else:
                    # No default, not VAR_KEYWORD, not VAR_POSITIONAL,
                    # not in `kwargs`
                    if partial:
                        parameters_ex = (param,)
                        break
                    else:
                        # msg = 'missing a required argument: {arg!r}'
                        # msg = msg.format(arg=param.name)
                        # raise TypeError(msg) from None
                        unbound_parameters.append(param)
        else:
            # We have a positional argument to process
            try:
                param = next(parameters)
            except StopIteration:
                # raise TypeError('too many positional arguments') from None
                extra_args.append(arg_val)
            else:
                if param.kind in (Parameter.VAR_KEYWORD, Parameter.KEYWORD_ONLY):
                    # Looks like we have no parameter for this positional
                    # argument
                    # raise TypeError(
                    #     'too many positional arguments') from None
                    extra_args.append(arg_val)

                if param.kind == Parameter.VAR_POSITIONAL:
                    # We have an '*args'-like argument, let's fill it with
                    # all positional arguments we have left and move on to
                    # the next phase
                    values = [arg_val]
                    values.extend(arg_vals)
                    arguments[param.name] = tuple(values)
                    break

                if param.name in kwargs and param.kind != Parameter.POSITIONAL_ONLY:
                    raise TypeError(
                        'multiple values for argument {arg!r}'.format(
                            arg=param.name)) from None

                arguments[param.name] = arg_val

    # Now, we iterate through the remaining parameters to process
    # keyword arguments
    kwargs_param = None
    for param in itertools.chain(parameters_ex, parameters):
        if param.kind == Parameter.VAR_KEYWORD:
            # Memorize that we have a '**kwargs'-like parameter
            kwargs_param = param
            continue

        if param.kind == Parameter.VAR_POSITIONAL:
            # Named arguments don't refer to '*args'-like parameters.
            # We only arrive here if the positional arguments ended
            # before reaching the last parameter before *args.
            continue

        param_name = param.name
        try:
            arg_val = kwargs.pop(param_name)
        except KeyError:
            # We have no value for this parameter.  It's fine though,
            # if it has a default value, or it is an '*args'-like
            # parameter, left alone by the processing of positional
            # arguments.
            if (not partial and param.kind != Parameter.VAR_POSITIONAL and
                                                param.default is _empty):
                # raise TypeError('missing a required argument: {arg!r}'.
                #                 format(arg=param_name)) from None
                unbound_parameters.append(param)

        else:
            if param.kind == Parameter.POSITIONAL_ONLY:
                # This should never happen in case of a properly built
                # Signature object (but let's have this check here
                # to ensure correct behaviour just in case)
                raise TypeError('{arg!r} parameter is positional only, '
                                'but was passed as a keyword'.
                                format(arg=param.name))

            arguments[param_name] = arg_val

    if kwargs:
        if kwargs_param is not None:
            # Process our '**kwargs'-like parameter
            arguments[kwargs_param.name] = kwargs
        else:
            # raise TypeError(
            #     'got an unexpected keyword argument {arg!r}'.format(
            #         arg=next(iter(kwargs))))
            extra_kwargs.update(kwargs)

    return (BoundArguments(thesignature, arguments),
            tuple(unbound_parameters),
            (tuple(extra_args), extra_kwargs))
