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

class UnknownArity(ValueError):
    """Raised when the arity of a function cannot be inspected."""

def arities(f):
    """Inspect f's minimum and maximum positional arity.

    This uses inspect.signature; note that the signature of builtin functions
    cannot be inspected.

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
                u = float("+inf")  # no upper limit
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

    print("All tests PASSED")

if __name__ == '__main__':
    test()
