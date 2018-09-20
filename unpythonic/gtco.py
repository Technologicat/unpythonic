#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tail call optimization for generators."""

__all__ = ["gtco", "gtrampolined"]

from functools import wraps
from inspect import isgenerator

def gtco(generator):
    """Low-level function: run a generator with TCO enabled.

    In the generator, use ``return`` to tail-chain to the next generator.

    Example::

        def march():
            yield 1
            yield 2
            return march()  # tail-chain to a new instance of itself
        assert tuple(take(6, gtco(march()))) == (1, 2, 1, 2, 1, 2)
        last(take(10000, gtco(march())))  # no crash
    """
    while True:  # trampoline
        x = yield from generator  # yield stuff, get final result (return ...)
        # don't let the TCO jump target bring along its trampoline if it has one
        if isinstance(x, _TrampolinedGenerator):
            x = x.g
        if isgenerator(x):
            generator = x
        else:
            # usually the return value is None, but allow for an iterable
            try:
                yield from x  # the last batch!
            except TypeError:
                return x  # passthrough

def gtrampolined(gfunc):
    """Decorator for generator functions (i.e. definitions of generators).

    Decorating the definition avoids the need to use ``gtco`` at call time.

    Example::

        @gtrampolined
        def ones():
            yield 1
            return ones()
        assert tuple(take(10, ones())) == (1,) * 10
        last(take(10000, ones()))  # no crash
    """
    @wraps(gfunc)
    def trampolining_gfunc(*args, **kwargs):
        generator = gfunc(*args, **kwargs)
        return _TrampolinedGenerator(generator)  # inject a trampoline
    return trampolining_gfunc

class _TrampolinedGenerator:
    """Wrapper to inject the gtco() call to the generator g returned by gfunc."""
    def __init__(self, g):
        self.g = g
    def __iter__(self):
        return gtco(iter(self.g))  # start the trampoline
    # no __next__, because __iter__ redirects;
    # this wrapper is never actually iterated over.

def test():
    from unpythonic.it import last, take

    # basic usage:
    def march():
        yield 1
        yield 2
        return march()  # tail-chain to a new instance of itself
    assert tuple(take(6, gtco(march()))) == (1, 2, 1, 2, 1, 2)
    last(take(10000, gtco(march())))  # no crash

    def ones():
        yield 1
        return ones()
    assert tuple(take(10, gtco(ones()))) == (1,) * 10
    last(take(10000, gtco(ones())))  # no crash

    # using decorator:
    @gtrampolined
    def ones2():
        yield 1
        return ones2()
    assert tuple(take(10, ones2())) == (1,) * 10
    last(take(10000, ones2()))  # no crash

    @gtrampolined
    def ranges():
        yield from range(10)
        return range(10, 20)  # can tail-chain into any iterable
    assert tuple(ranges()) == tuple(range(20))

    print("All tests PASSED")

if __name__ == '__main__':
    test()
