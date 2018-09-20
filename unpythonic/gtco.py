#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tail call optimization for generators."""

__all__ = ["gtco", "gtrampolined"]

from functools import wraps
from inspect import isgenerator

from unpythonic.dynscope import dyn

def gtco(generator):
    """Low-level function: run a generator with TCO enabled.

    In the generator, use ``return`` to tail-chain to the next generator.

    Example::

        def gen():
            yield 1
            yield 2
            return gen()  # tail-chain to gen itself
        assert tuple(take(6, gtco(gen()))) == (1, 2, 1, 2, 1, 2)
        last(take(10000, gtco(gen())))  # no crash
    """
    with dyn.let(_gtrampoline_active=True):
        while True:  # trampoline
            x = yield from generator  # yield stuff, get final result (return ...)
            if isgenerator(x) or isinstance(x, _TrampolinedGenerator):
                generator = x
            else:
                if x:  # usually this is None, but allow for an iterable
                    yield from x  # the last batch!
                break

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
    def decorated(*args, **kwargs):
        generator = gfunc(*args, **kwargs)
        if "_gtrampoline_active" not in dyn:  # start up the trampoline
            return _TrampolinedGenerator(generator)
        else: # avoid stacking when already running in the trampoline
              # and a generator calls a gtrampolined gfunc (incl. its own!)
            return generator
    return decorated

class _TrampolinedGenerator:
    """Wrapper to inject the gtco() call to the generator g returned by gfunc."""
    def __init__(self, g):
        self.g = g
    def __iter__(self):
        return gtco(iter(self.g))
    # no __next__, because __iter__ redirects;
    # this wrapper is never actually iterated over.

def test():
    from unpythonic.it import last, take

    # basic usage:
    def gen():
        yield 1
        yield 2
        return gen()  # tail-chain to gen itself
    assert tuple(take(6, gtco(gen()))) == (1, 2, 1, 2, 1, 2)
    last(take(10000, gtco(gen())))  # no crash

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
