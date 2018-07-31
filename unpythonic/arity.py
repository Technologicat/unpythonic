#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Inspect the arity of a callable.

This module uses ``inspect`` out of necessity. The idea is to provide something
like Racket's (arity-includes).
"""

__all__ = ["arities", "arity_includes", "UnknownArity"]

from inspect import signature, Parameter

class UnknownArity(ValueError):
    pass

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
        for k, v in signature(f).parameters.items():
            if v.kind in poskinds:
                u += 1
                if v.default is Parameter.empty:
                    l += 1  # no default --> required parameter
            elif v.kind is Parameter.VAR_POSITIONAL:
                u = float("+inf")  # no upper limit
        return l, u
    except (TypeError, ValueError) as e:
        raise UnknownArity(*e.args)

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
    print("All tests PASSED")

if __name__ == '__main__':
    test()
