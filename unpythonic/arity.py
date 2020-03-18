# -*- coding: utf-8 -*-
"""Inspect the arity of a callable.

This module uses ``inspect`` out of necessity. The idea is to provide something
like Racket's (arity-includes?).
"""

__all__ = ["arities", "arity_includes",
           "required_kwargs", "optional_kwargs", "kwargs",
           "resolve_bindings", "tuplify_bindings",
           "UnknownArity"]

from inspect import signature, Parameter
from collections import OrderedDict
from types import ModuleType
import operator

from .symbol import gensym

try:  # Python 3.5+
    from operator import matmul, imatmul
except ImportError:
    NoSuchBuiltin = gensym("NoSuchBuiltin")
    matmul = imatmul = NoSuchBuiltin

class UnknownArity(ValueError):
    """Raised when the arity of a function cannot be inspected."""

# HACK: some built-ins report incorrect arities (0, 0) at least in Python 3.4
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
                    matmul: (2, 2),
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
                    imatmul: (2, 2),
                    operator.ior: (2, 2),
                    operator.ipow: (2, 2),
                    operator.irshift: (2, 2),
                    operator.isub: (2, 2),
                    operator.itruediv: (2, 2),
                    operator.ixor: (2, 2)}

def _getfunc(f):
    """Given a function or method, return the underlying function.

    Return value is a tuple ``(f, kind)``, where ``kind`` is one of
    ``function``, ``methodoninstance``, ``methodonclass``.
    """
    # inspect.ismethod() does a slightly different thing:
    #    a = A()
    #    inspect.ismethod(A.meth) -> False
    #    inspect.ismethod(A.classmeth) -> True
    #    inspect.ismethod(A.staticmeth) -> False
    #    inspect.ismethod(a.meth) -> True
    #    inspect.ismethod(a.classmeth) -> True
    #    inspect.ismethod(a.staticmeth) -> False
    # whereas we want True for meth and classmeth for both A and a.
    def ismethod(f):
        if not hasattr(f, "__self__"):
            return False
        self = f.__self__
        if isinstance(self, ModuleType) and self.__name__ == "builtins":  # e.g. print
            return False
        return True
    kind = "function"
    if ismethod(f):
        obj_or_cls = f.__self__
        if isinstance(obj_or_cls, type):  # TODO: do all custom metaclasses inherit from type?
            cls = obj_or_cls
            kind = "methodonclass"
        else:
            cls = obj_or_cls.__class__
            kind = "methodoninstance"
        return (getattr(cls, f.__name__), kind)
    else:
        return (f, kind)

def arities(f):
    """Inspect f's minimum and maximum positional arity.

    This uses inspect.signature; note that the signature of builtin functions
    cannot be inspected. This is worked around to some extent, but e.g.
    methods of built-in classes (such as ``list``) might not be inspectable.

    For methods, ``self`` or ``cls`` does not count toward the arity,
    because it is passed implicitly by Python.

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
    f, kind = _getfunc(f)
    try:
        if f in _builtin_arities:
            return _builtin_arities[f]
    except TypeError:  # f is of an unhashable type
        pass
    try:
        l = 0
        u = 0
        poskinds = set((Parameter.POSITIONAL_ONLY,
                        Parameter.POSITIONAL_OR_KEYWORD))
        for _, v in signature(f).parameters.items():
            if v.kind in poskinds:
                u += 1
                if v.default is Parameter.empty:
                    l += 1  # no default --> required parameter
            elif v.kind is Parameter.VAR_POSITIONAL:
                u = _infty  # no upper limit
        if kind == "methodoninstance":  # self is passed implicitly
            l -= 1
            u -= 1
        return l, u
    except (TypeError, ValueError) as e:
        raise UnknownArity(*e.args)

def required_kwargs(f):
    """Return a set containing the names of required name-only arguments of f.

    "Required": has no default.

    Raises UnknownArity if inspection failed.
    """
    return _kwargs(f, optionals=False)

def optional_kwargs(f):
    """Return a set containing the names of optional name-only arguments of f.

    "Optional": has a default.

    Raises UnknownArity if inspection failed.
    """
    return _kwargs(f, optionals=True)

def _kwargs(f, optionals=True):
    f, _ = _getfunc(f)
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
    l, u = arities(f)
    return l <= n <= u

def resolve_bindings(f, *args, **kwargs):
    """Resolve parameter bindings established by `f` when called with the given args and kwargs.

    This is an inspection tool, which does not actually call `f`. This is useful for memoizers
    and other similar decorators that need a canonical representation of `f`'s parameter bindings.
    If you want a hashable result, postprocess the return value with `tuplify_bindings(result)`.

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

    The return value of `resolve_bindings` is an `OrderedDict` with four keys:
        args: `OrderedDict` of bindings made for regular parameters
              (positional only, positional or keyword, keyword only).
        vararg: `tuple` of arguments gathered by the vararg (`*args`) parameter
                if the function definition has one; otherwise `None`.
        vararg_name: `str`, the name of the vararg parameter; or `None`.
        kwarg: `OrderedDict` of bindings gathered by `**kwargs` if the
               function definition has one; otherwise `None`.

    **NOTE**:

    We attempt to implement the exact same algorithm Python itself uses for
    resolving argument bindings. The process is explained in the language
    reference, although not in a step-by-step algorithmic form.

        https://docs.python.org/3/reference/compound_stmts.html#function-definitions
        https://docs.python.org/3/reference/expressions.html#calls

    This function should report exactly those bindings that would actually be
    established if `f` was actually called with the given `args` and `kwargs`.

    If you encounter a case with any difference between what the result claims and
    how Python itself assigns the bindings, that is a bug in our code. In such a
    case, please report the issue, so it can be fixed, and then added to the unit
    tests to ensure it won't come back.
    """
    f, _ = _getfunc(f)
    params = signature(f).parameters

    # https://docs.python.org/3/library/inspect.html#inspect.Signature
    # https://docs.python.org/3/library/inspect.html#inspect.Parameter
    poskinds = set((Parameter.POSITIONAL_ONLY,
                    Parameter.POSITIONAL_OR_KEYWORD))
    kwkinds = set((Parameter.POSITIONAL_OR_KEYWORD,
                   Parameter.KEYWORD_ONLY))
    varkinds = set((Parameter.VAR_POSITIONAL,
                    Parameter.VAR_KEYWORD))

    index = {}
    nposparams = 0
    varpos = varkw = None
    for slot, param in enumerate(params.values()):
        if param.kind in poskinds:
            nposparams += 1
        if param.kind in kwkinds:
            index[param.name] = slot
        if param.kind == Parameter.VAR_POSITIONAL:
            varpos = slot
            varpos_name = param.name
        elif param.kind == Parameter.VAR_KEYWORD:
            varkw = slot

    # https://docs.python.org/3/reference/compound_stmts.html#function-definitions
    # https://docs.python.org/3/reference/expressions.html#calls
    unassigned = object()  # gensym("unassigned"), but object() is much faster, and we don't need a label, or pickle support.
    slots = [unassigned for _ in range(len(params))]  # yes, varparams too

    # fill from positional arguments
    for slot, (param, value) in enumerate(zip(params.values(), args)):
        if param.kind in varkinds:  # these are always last in the function def
            break
        slots[slot] = value

    if varpos is not None:
        slots[varpos] = []
    if varkw is not None:
        slots[varkw] = OrderedDict()
        vkdict = slots[varkw]

    # gather excess positional arguments
    if len(args) > nposparams:
        if varpos is None:
            raise TypeError("{}() takes {} positional arguments but {} were given".format(f.__name__,
                                                                                          nposparams,
                                                                                          len(args)))
        slots[varpos] = args[nposparams:]

    # fill from keyword arguments
    for identifier, value in kwargs.items():
        if identifier in index:
            slot = index[identifier]
            if slots[slot] is unassigned:
                slots[slot] = value
            else:
                raise TypeError("{}() got multiple values for argument '{}'".format(f.__name__,
                                                                                    identifier))
        elif varkw is not None:  # gather excess keyword arguments
            vkdict[identifier] = value
        else:
            raise TypeError("{}() got an unexpected keyword argument '{}'".format(f.__name__,
                                                                                  identifier))

    # fill missing with defaults from function definition
    failures = []
    for slot, param in enumerate(params.values()):
        if slots[slot] is unassigned:
            if param.default is Parameter.empty:
                failures.append(param.name)
            slots[slot] = param.default
    # Python 3.6 goes so far to make this particular error message into proper
    # English, that aping the standard error message takes the most effort here...
    if failures:
        if len(failures) == 1:
            n1 = failures[0]
            raise TypeError("{}() missing required positional argument: '{}'".format(f.__name__, n1))
        if len(failures) == 2:
            n1, n2 = failures
            raise TypeError("{}() missing 2 required positional arguments: '{}' and '{}'".format(f.__name__, n1, n2))
        wrapped = ["'{}'".format(x) for x in failures]
        others = ", ".join(wrapped[:-1])
        msg = "{}() missing {} required positional arguments: {}, and '{}'".format(f.__name__,
                                                                                   len(failures),
                                                                                   others,
                                                                                   failures[-1])
        raise TypeError(msg)

    # build the result
    regularargs = OrderedDict()
    for param, value in zip(params.values(), slots):
        if param.kind in varkinds:  # skip varpos, varkw
            continue
        regularargs[param.name] = value

    # Naming of the fields matches `ast.arguments`
    # https://greentreesnakes.readthedocs.io/en/latest/nodes.html#arguments
    bindings = OrderedDict()
    bindings["args"] = regularargs
    bindings["vararg"] = slots[varpos] if varpos else None
    bindings["vararg_name"] = varpos_name if varpos else None  # for introspection
    bindings["kwarg"] = slots[varkw] if varkw else None

    return bindings

def tuplify_bindings(bindings):
    """Convert the return value of `resolve_bindings` into a hashable form.

    This is useful for memoizers and similar use cases, which need to use a
    representation of the bindings as a dictionary key.

    The values stored in the `"args"` and `"kwarg"` keys, as well as `bindings`
    itself, are converted from `OrderedDict` to `tuple` using `tuple(od.items())`.
    The result is hashable, if all the arguments passed in the bindings are.
    """
    def tuplify(od):
        return tuple(od.items())
    result = OrderedDict()
    result["args"] = tuplify(bindings["args"])
    result["vararg"] = bindings["vararg"]
    result["vararg_name"] = bindings["vararg_name"]
    result["kwarg"] = tuplify(bindings["kwarg"]) if bindings["kwarg"] is not None else None
    return tuplify(result)
