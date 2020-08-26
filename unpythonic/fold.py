# -*- coding: utf-8 -*-
"""Folds, scans (lazy partial folds), and unfold.

For more batteries for itertools, see also the ``unpythonic.it`` module.

Racket-like multi-input ``foldl`` and ``foldr`` based on
  https://docs.racket-lang.org/reference/pairs.html

``scanl`  and ``scanr`` inspired by ``itertools.accumulate``, Haskell,
and (stream-scan) in SRFI-41.
  https://srfi.schemers.org/srfi-41/srfi-41.html
"""

__all__ = ["scanl", "scanr", "scanl1", "scanr1",
           "foldl", "foldr", "reducel", "reducer",
           "rscanl", "rscanl1", "rfoldl", "rreducel",  # reverse each input, then left-scan/fold
           "unfold", "unfold1",
           "prod",
           "running_minmax", "minmax"]

from functools import partial
from itertools import zip_longest
from operator import mul
#from collections import deque

#from .it import first, last, rev
from .it import last, rev

# Require at least one iterable to make this work seamlessly with curry. We take
# this approach with any new function families the standard library doesn't provide.
def scanl(proc, init, iterable0, *iterables, longest=False, fillvalue=None):
    """Scan (a.k.a. accumulate).

    Like ``itertools.accumulate``, but supports multiple input iterables.
    At least one iterable (``iterable0``) is required.

    Initial value is mandatory; there is no sane default for the case with
    multiple inputs.

    By default, terminate when the shortest input runs out. To terminate on
    longest input, use ``longest=True`` and optionally provide a ``fillvalue``.

    If the inputs are iterators, this is essentially a lazy ``foldl`` that
    yields the intermediate result at each step. Hence, useful for partially
    folding infinite sequences (in the mathematical sense of "sequence").

    Returns a generator, which (roughly)::

        acc = init
        yield acc
        for elts in zip(iterable0, *iterables):  # or zip_longest as appropriate
            acc = proc(*elts, acc)  # if this was legal syntax
            yield acc

    Example - partial sums and products::

        from operator import add, mul
        psums = composer(tail, curry(scanl, add, 0))  # tail to drop the init value
        pprods = composer(tail, curry(scanl, mul, 1))
        data = range(1, 5)
        assert tuple(psums(data)) == (1, 3, 6, 10)
        assert tuple(pprods(data)) == (1, 2, 6, 24)
    """
    z = zip if not longest else partial(zip_longest, fillvalue=fillvalue)
    acc = init
    yield acc
    for xs in z(iterable0, *iterables):
        acc = proc(*(xs + (acc,)))
        yield acc

def scanr(proc, init, iterable0, *iterables, longest=False, fillvalue=None):
    """Dual of scanl; scan from the right.

    Example::

        from operator import add
        assert tuple(scanl(add, 0, range(1, 5))) == (0, 1, 3, 6, 10)
        assert tuple(scanr(add, 0, range(1, 5))) == (0, 4, 7, 9, 10)

    **CAUTION**: The ordering of the output is different from Haskell's ``scanr``;
    we yield the results in the order they are computed (via a linear process).

    For multiple input iterables, the notion of *corresponding elements*
    is based on syncing the **left** ends.

    Note difference between *l, *r and r*l where * = fold, scan::

        def append_tuple(a, b, acc):
            return acc + ((a, b),)

        # foldl: left-fold
        assert foldl(append_tuple, (), (1, 2, 3), (4, 5)) == ((1, 4), (2, 5))

        # foldr: right-fold
        assert foldr(append_tuple, (), (1, 2, 3), (4, 5)) == ((2, 5), (1, 4))

        # rfoldl: reverse each input, then left-fold
        assert rfoldl(append_tuple, (), (1, 2, 3), (4, 5)) == ((3, 5), (2, 4))
    """
    # Linear process: sync left ends; reverse; scanl.
    # (Flat is better than nested, also for the call stack.)
    #
    # The implicit tuple(...) in rev(...) may seem inelegant, but it doesn't
    # really matter whether we keep the data in stack frames (like in the
    # recursive-process variant) or read it into a tuple (like here); we must
    # read and store all elements of the input before the actual scanning can begin.
    init_from_lastx = init is _uselast and not iterables
    z = zip if not longest else partial(zip_longest, fillvalue=fillvalue)
    xss = rev(z(iterable0, *iterables))
    if init_from_lastx:
        try:
            init = next(xss)[0]
        except StopIteration:
            return

#    # left-append into a deque to get same output order as in Haskell
#    acc = init
#    que = deque()
#    que.appendleft(acc)
#    for xs in xss:
#        acc = proc(*(xs + (acc,)))
#        que.appendleft(acc)
#    yield from que

    # to be more rackety/pythonic: yield results in the order they're computed
    acc = init
    yield acc
    for xs in xss:
        acc = proc(*(xs + (acc,)))
        yield acc


# Equivalent recursive process:
#def scanr(proc, init, iterable0, *iterables, longest=False, fillvalue=None):
#    z = zip if not longest else partial(zip_longest, fillvalue=fillvalue)
#    xss = z(iterable0, *iterables)
#    pending_init_from_lastx = init is _uselast and not iterables
#    def _scanr_recurser():
#        try:
#            xs = next(xss)
#        except StopIteration:
#            yield init               # base case for recursion
#            return
#        subgen = _scanr_recurser()
#        acc = next(subgen)           # final result of previous step
#
#        # The other base case: one iterable, no init given.
#        # If pending_init_from_lastx is still True, we are the second-to-last subgen.
#        nonlocal pending_init_from_lastx
#        if pending_init_from_lastx:
#            pending_init_from_lastx = False
#            yield xs[0]              # init value = last element from iterable0
#            return
#
#        # In case of all but the outermost generator, their final result has already
#        # been read by the next(subgen), so they have only the last two yields remaining.
#        yield proc(*(xs + (acc,)))   # final result
#        yield acc                    # previous result
#        yield from subgen            # sustain the chain
#    return _scanr_recurser()

def scanl1(proc, iterable, init=None):
    """scanl for a single iterable, with optional init.

    If ``init is None``, use the first element from the iterable.

    If the iterable is empty, return ``None``.

    Example - partial sums and products::

        from operator import add, mul
        psums = curry(scanl1, add)
        pprods = curry(scanl1, mul)
        data = range(1, 5)
        assert tuple(psums(data)) == (1, 3, 6, 10)
        assert tuple(pprods(data)) == (1, 2, 6, 24)
    """
    it = iter(iterable)
    if init is None:
        try:
            init = next(it)
        except StopIteration:
            def empty_iterable():
                yield from ()
            return empty_iterable()
    return scanl(proc, init, it)

_uselast = object()  # sentinel
def scanr1(proc, iterable, init=None):
    """Dual of scanl1.

    If ``init is None``, use the last element from the iterable.
    """
    return scanr(proc, _uselast if init is None else init, iterable)

def foldl(proc, init, iterable0, *iterables, longest=False, fillvalue=None):
    """Racket-like foldl that supports multiple input iterables.

    At least one iterable (``iterable0``) is required. More are optional.

    Initial value is mandatory; there is no sane default for the case with
    multiple inputs.

    By default, terminate when the shortest input runs out. To terminate on
    longest input, use ``longest=True`` and optionally provide a ``fillvalue``.

    Note order: ``proc(elt, acc)``, which is the opposite order of arguments
    compared to ``functools.reduce``. General case ``proc(e1, ..., en, acc)``.
    """
    return last(scanl(proc, init, iterable0, *iterables,
                      longest=longest, fillvalue=fillvalue))

def foldr(proc, init, iterable0, *iterables, longest=False, fillvalue=None):
    """Dual of foldl; fold from the right."""
    # if using the haskelly result ordering in scanr, then first(...);
    # if ordering results as they are computed, then last(...)
    return last(scanr(proc, init, iterable0, *iterables,
                      longest=longest, fillvalue=fillvalue))

def reducel(proc, iterable, init=None):
    """Foldl for a single iterable, with optional init.

    If ``init is None``, use the first element from the iterable.

    Like ``functools.reduce``, but uses ``proc(elt, acc)`` like Racket."""
    return last(scanl1(proc, iterable, init))

def reducer(proc, iterable, init=None):
    """Dual of reducel.

    If ``init is None``, use the last element from the iterable.
    """
    # if using the haskelly result ordering in scanr, then first(...);
    # if ordering results as they are computed, then last(...)
    return last(scanr1(proc, iterable, init))

def rscanl(proc, init, iterable0, *iterables, longest=False, fillvalue=None):
    """Reverse each input, then scanl.

    For multiple input iterables, the notion of *corresponding elements*
    is based on syncing the **right** ends.

    ``rev`` is applied to the inputs. Note this forces any generators.
    """
    return scanl(proc, init, rev(iterable0), *(rev(s) for s in iterables),
                 longest=longest, fillvalue=fillvalue)

def rscanl1(proc, iterable, init=None):
    """Reverse the input, then scanl1."""
    return scanl1(proc, rev(iterable), init)

def rfoldl(proc, init, iterable0, *iterables, longest=False, fillvalue=None):
    """Reverse each input, then foldl.

    For multiple input iterables, the notion of *corresponding elements*
    is based on syncing the **right** ends.

    ``rev`` is applied to the inputs. Note this forces any generators.
    """
    return foldl(proc, init, rev(iterable0), *(rev(s) for s in iterables),
                 longest=longest, fillvalue=fillvalue)

def rreducel(proc, iterable, init=None):
    """Reverse the input, then reducel."""
    return reducel(proc, rev(iterable), init)

def unfold1(proc, init):
    """Generate a sequence corecursively. The counterpart of foldl.

    Returns a generator.

    State starts from the value ``init``.

    ``proc`` must accept one argument, the state. If you have a complex,
    multi-component state and would like to unpack it automatically,
    see ``unfold``.

    ``proc`` must return either ``(value, newstate)``, or ``None`` to signify
    that the sequence ends (if the sequence is finite).

    ("Sequence" is here meant in the mathematical sense; in the Python sense,
    the output is an iterable.)

    Example::

        def step2(k):  # x0, x0 + 2, x0 + 4, ...
            return (k, k + 2)

        assert (tuple(take(10, unfold1(step2, 10))) ==
                (10, 12, 14, 16, 18, 20, 22, 24, 26, 28))
    """
    state = init
    while True:
        result = proc(state)
        if result is None:
            break
        value, state = result
        yield value

def unfold(proc, *inits):
    """Like unfold1, but for n-in-(1+n)-out proc.

    The current state is unpacked to the argument list of ``proc``.
    It must return either ``(value, *newstates)``, or ``None`` to signify
    that the sequence ends.

    If your state is something simple such as one number, see ``unfold1``.

    Example::

        def fibo(a, b):
            return (a, b, a + b)

        assert (tuple(take(10, unfold(fibo, 1, 1))) ==
                (1, 1, 2, 3, 5, 8, 13, 21, 34, 55))
    """
    states = inits
    while True:
        result = proc(*states)
        if result is None:
            break
        value, *states = result
        yield value

# This is **not** how to make a right map; the result is exactly the same
# as for the ordinary (left) map and zip, but unnecessarily using a
# recursive process for something that can be done using a linear one.
# For documentation only. For working mapr, zipr, see unpythonic.it.
# The trick is in the order in which the recurser yields its results.
#
# def testme():
#     squaretwo = lambda a, b: (a**2, b**2)
#     print(tuple(mapr(squaretwo, (1, 2, 3), (4, 5))))
#     print(tuple(map(squaretwo, (1, 2, 3), (4, 5))))
#
# def mapr(proc, *iterables):
#     """Like map, but starting from the right. Recursive process.
#
#     See ``rmap`` for the linear process that works by reversing each input.
#     """
#     def scanproc(*args):
#         *elts, _ = args  # discard acc
#         return proc(*elts)
#     # discard the init value with butlast
#     return butlast(scanr(scanproc, None, *iterables))
#
# def zipr(*iterables):
#     """Like zip, but starting from the right. Recursive process.
#
#     See ``rzip`` for the linear process that works by reversing each input.
#     """
#     def identity(*args):  # unpythonic.fun.identity, but dependency loop
#         return args
#     return mapr(identity, *iterables)

def prod(iterable, start=1):
    """Like the builtin sum, but compute the product.

    This is a fold operation.
    """
    return reducel(mul, iterable, init=start)

def running_minmax(iterable):
    """Return a generator extracting a running `(min, max)` from `iterable`.

    The iterable is iterated just once.

    If `iterable` is empty, an empty iterator is returned.

    We assume iterable contains no NaNs, and that all elements in `iterable`
    are comparable using `<` and `>`. Suggest filtering accordingly before
    calling this.

    This is a scan operation.
    """
    it = iter(iterable)
    try:
        first = next(it)
    except StopIteration:  # behave like `unpack` and `window` on empty input
        def empty_iterable():
            yield from ()
        return empty_iterable()
    def mm(elt, acc):
        a, b = acc
        if elt < a:
            a = elt
        if elt > b:
            b = elt
        return a, b
    return scanl(mm, (first, first), it)

def minmax(iterable):
    """Extract `(min, max)` from `iterable`, iterating it just once.

    If `iterable` is empty, return `(None, None)`.

    We assume iterable contains no NaNs, and that all elements in `iterable`
    are comparable using `<` and `>`. Suggest filtering accordingly before
    calling this.

    This is a fold operation.
    """
    return last(running_minmax(iterable), default=(None, None))
