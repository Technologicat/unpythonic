#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Inspect the arity of a callable.

This module uses ``inspect`` out of necessity. The idea is to provide something
like Racket's (arity-includes?).
"""

__all__ = ["arities", "arity_includes",
           "required_kwargs", "optional_kwargs", "kwargs",
           "UnknownArity"]

from inspect import signature, Parameter
from types import ModuleType
import operator

try:  # Python 3.5+
    from operator import matmul, imatmul
except ImportError:
    NoSuchBuiltin = object()
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
_builtin_arities = {# inspectable, but reporting incorrectly
                    bool: (1, 1),       # bool(x)
                    bytes: (0, 3),      # see help(bytes)
                    complex: (1, 2),    # complex(real, [imag])
                    enumerate: (1, 2),  # enumerate(iterable, [start])
                    filter: (2, 2),     # filter(function or None, iterable)
                    float: (1, 1),      # float(x)
                    frozenset: (0, 1),  # frozenset(), frozenset(iterable)
                    int: (0, 2),        # int(x=0), int(x, base=10)
                    map: (1, _infty),   # map(func, *iterables)
                    memoryview: (1, 1), # memoryview(object)
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
                    __import__: (1, 5), # FIXME: is this correct? are the rest positional or by-name?
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

def test():
    _ = None  # just some no-op value
    infty = float("+inf")
    items = (((lambda a: _),                       (1, 1)),
             ((lambda a, b: _),                    (2, 2)),
             ((lambda a, b, c, *args: _),          (3, infty)),
             ((lambda *args: _),                   (0, infty)),
             ((lambda **kwargs: _),                (0, 0)),
             ((lambda *args, **kwargs: _),         (0, infty)),
             ((lambda a, b, *, c: _),              (2, 2)),
             ((lambda *, a: _),                    (0, 0)),
             ((lambda a, b, *arg, c, **kwargs: _), (2, infty)),
             ((lambda a, b=42: _),                 (1, 2)))
    for f, answer in items:
        assert arities(f) == answer

    assert required_kwargs(lambda *, a, b, c=42: _) == set(('a', 'b'))
    assert optional_kwargs(lambda *, a, b, c=42: _) == set(('c'))
    assert kwargs(lambda *, a, b, c=42: _) == (set(('a', 'b')), set(('c')))
    assert required_kwargs(lambda a, b, c=42: _) == set()
    assert optional_kwargs(lambda a, b, c=42: _) == set()
    assert kwargs(lambda a, b, c=42: _) == (set(), set())

    # OOP
    class A:
        def __init__(self):
            pass
        def meth(self, x):
            pass
        @classmethod
        def classmeth(cls, x):
            pass
        @staticmethod
        def staticmeth(x):
            pass
    assert arities(A) == (0, 0)  # no args beside the implicit self
    # methods on the class
    assert arities(A.meth) == (2, 2)
    assert arities(A.classmeth) == (1, 1)
    assert arities(A.staticmeth) == (1, 1)
    # methods on an instance
    a = A()
    assert arities(a.meth) == (1, 1)  # self is implicit, so just one
    # class and static methods are always unbound
    assert arities(a.classmeth) == (1, 1)
    assert arities(a.staticmeth) == (1, 1)

    print("All tests PASSED")

if __name__ == '__main__':
    test()
