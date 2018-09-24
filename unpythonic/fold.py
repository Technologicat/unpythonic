#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Folds, scans (lazy partial folds), and unfold."""

__all__ = ["scanl", "scanr", "scanl1", "scanr1",
           "foldl", "foldr", "reducel", "reducer",
           "rscanl", "rscanl1", "rfoldl", "rreducel",  # reverse each input, then left-scan/fold
           "unfold", "unfold1"]

from functools import partial
from itertools import zip_longest
from collections import deque

from unpythonic.it import first, last, rev

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
        assert tuple(scanr(add, 0, range(1, 5))) == (10, 9, 7, 4, 0)

    The ordering of the output matches Haskell's ``scanr``.

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
    # Linear process: sync left ends; reverse; scanl into a deque.
    # (Flat is better than nested; applied to the call stack.)
    #
    # The implicit tuple(...) in rev(...) may seem inelegant, but it doesn't
    # really matter whether we keep the data in stack frames (like in the
    # recursive-process variant) or read it into a tuple (like here); we must
    # read and store all elements of the input before the actual scanning can begin.
    init_from_lastx = init is _uselast and not iterables
    z = zip if not longest else partial(zip_longest, fillvalue=fillvalue)
    xss = rev(z(iterable0, *iterables))
    if init_from_lastx:
        init = next(xss)[0]  # let StopIteration propagate
    acc = init
    que = deque()
    que.appendleft(acc)  # left-append to get same output order as in Haskell
    for xs in xss:
        acc = proc(*(xs + (acc,)))
        que.appendleft(acc)
    yield from que

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
    if not init:
        try:
            init = next(it)
        except StopIteration:
            return None  # empty input iterable
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
    return first(scanr(proc, init, iterable0, *iterables,
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
    return first(scanr1(proc, iterable, init))

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

        assert tuple(take(10, unfold1(step2, 10))) == \\
               (10, 12, 14, 16, 18, 20, 22, 24, 26, 28)
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

        assert tuple(take(10, unfold(fibo, 1, 1))) == \\
               (1, 1, 2, 3, 5, 8, 13, 21, 34, 55)
    """
    states = inits
    while True:
        result = proc(*states)
        if result is None:
            break
        value, *states = result
        yield value

## This is **not** how to make a right map; the result is exactly the same
## as for the ordinary (left) map and zip, but unnecessarily using a
## recursive process for something that can be done using a linear one.
## For documentation only. For working mapr, zipr, see unpythonic.it.
## The trick is in the order in which the recurser yields its results.
#def testme():
#    squaretwo = lambda a, b: (a**2, b**2)
#    print(tuple(mapr(squaretwo, (1, 2, 3), (4, 5))))
#    print(tuple(map(squaretwo, (1, 2, 3), (4, 5))))
#
#def mapr(proc, *iterables):
#    """Like map, but starting from the right. Recursive process.
#
#    See ``rmap`` for the linear process that works by reversing each input.
#    """
#    def scanproc(*args):
#        *elts, _ = args  # discard acc
#        return proc(*elts)
#    # discard the init value with butlast
#    return butlast(scanr(scanproc, None, *iterables))
#
#def zipr(*iterables):
#    """Like zip, but starting from the right. Recursive process.
#
#    See ``rzip`` for the linear process that works by reversing each input.
#    """
#    def identity(*args):  # unpythonic.fun.identity, but dependency loop
#        return args
#    return mapr(identity, *iterables)

def test():
    from operator import add, mul
    from unpythonic.fun import curry, composer, composerc, composel, to1st, rotate
    from unpythonic.llist import cons, nil, ll, lreverse
    from unpythonic.it import take, tail, rzip

    # scan/accumulate: lazy fold that yields intermediate results.
    assert tuple(scanl(add, 0, range(1, 5))) == (0, 1, 3, 6, 10)
    assert tuple(scanr(add, 0, range(1, 5))) == (10, 9, 7, 4, 0)
    assert tuple(scanl(mul, 1, range(2, 6))) == (1, 2, 6, 24, 120)
    assert tuple(scanr(mul, 1, range(2, 6))) == (120, 60, 20, 5, 1)

    assert tuple(scanl(cons, nil, ll(1, 2, 3))) == (nil, ll(1), ll(2, 1), ll(3, 2, 1))
    assert tuple(scanr(cons, nil, ll(1, 2, 3))) == (ll(1, 2, 3), ll(2, 3), ll(3), nil)

    # in contrast, fold just returns the final result.
    assert foldl(cons, nil, ll(1, 2, 3)) == ll(3, 2, 1)
    assert foldr(cons, nil, ll(1, 2, 3)) == ll(1, 2, 3)

    # reduce is a fold with a single input, with init optional.
    assert reducel(add, (1, 2, 3)) == 6
    assert reducer(add, (1, 2, 3)) == 6

    # scanl1, scanr1 are a scan with a single input, with init optional.
    assert tuple(scanl1(add, (1, 2, 3))) == (1, 3, 6)
    assert tuple(scanr1(add, (1, 2, 3))) == (6, 5, 3)

    psums = composer(tail, curry(scanl, add, 0))  # tail to drop the init value
    pprods = composer(tail, curry(scanl, mul, 1))
    data = range(1, 5)
    assert tuple(psums(data)) == (1, 3, 6, 10)
    assert tuple(pprods(data)) == (1, 2, 6, 24)

    psums = curry(scanl1, add)  # or use the fact the 1-input variant needs no init
    pprods = curry(scanl1, mul)
    data = range(1, 5)
    assert tuple(psums(data)) == (1, 3, 6, 10)
    assert tuple(pprods(data)) == (1, 2, 6, 24)

    def append_tuple(a, b, acc):
        return acc + ((a, b),)
    assert foldl(append_tuple, (), (1, 2, 3), (4, 5)) == ((1, 4), (2, 5))
    assert foldr(append_tuple, (), (1, 2, 3), (4, 5)) == ((2, 5), (1, 4))
    assert rfoldl(append_tuple, (), (1, 2, 3), (4, 5)) == ((3, 5), (2, 4))
    assert tuple(rscanl(append_tuple, (), (1, 2, 3), (4, 5))) == ((), ((3, 5),), ((3, 5), (2, 4)))

    def mymap_one(f, iterable):
        f_then_cons = composer(cons, to1st(f))  # args: elt, acc
        return foldr(f_then_cons, nil, iterable)
    double = lambda x: 2 * x
    assert mymap_one(double, ll(1, 2, 3)) == ll(2, 4, 6)
    def mymap_one2(f, iterable):
        f_then_cons = composel(to1st(f), cons)  # args: elt, acc
        return foldr(f_then_cons, nil, iterable)
    assert mymap_one2(double, ll(1, 2, 3)) == ll(2, 4, 6)

    # point-free-ish style
    mymap_one3 = lambda f: partial(foldr, composer(cons, to1st(f)), nil)
    doubler = mymap_one3(double)
    assert doubler(ll(1, 2, 3)) == ll(2, 4, 6)

    try:
        doubler(ll(1, 2, 3), ll(4, 5, 6))
    except TypeError:
        pass
    else:
        assert False  # one arg too many; cons in the compose chain expects 2 args (acc is one)

    # minimum arity of fold functions is 3, to allow use with curry:
    mymap_one4 = lambda f: curry(foldr, composer(cons, to1st(f)), nil)
    doubler = mymap_one4(double)
    assert doubler(ll(1, 2, 3)) == ll(2, 4, 6)

    # curry supports passing through on the right any args over the max arity.
    assert curry(double, 2, "foo") == (4, "foo")   # arity of double is 1

    # In passthrough, if an intermediate result is a callable,
    # it is invoked on the remaining positional args:
    assert curry(mymap_one4, double, ll(1, 2, 3)) == ll(2, 4, 6)

    # This also works; curried f takes one argument and the second one is passed
    # through on the right; this two-tuple then ends up as the arguments to cons.
    mymap_one5 = lambda f: curry(foldr, composer(cons, curry(f)), nil)
    assert curry(mymap_one5, double, ll(1, 2, 3)) == ll(2, 4, 6)

    # Finally, we can drop the inner curry by using a currying compose.
    # This is as close to "(define (map f) (foldr (compose cons f) empty)"
    # (#lang spicy) as we're gonna get in Python.
    mymap = lambda f: curry(foldr, composerc(cons, f), nil)
    assert curry(mymap, double, ll(1, 2, 3)) == ll(2, 4, 6)

    # The currying has actually made it not just map one, but general map that
    # accepts multiple inputs.
    #
    # The iterables are taken by the processing function. acc, being the last
    # argument, is passed through on the right. The output from the processing
    # function - one new item - and acc then become a two-tuple, which gets
    # passed into cons.
    myadd = lambda x, y: x + y  # can't inspect signature of builtin add
    assert curry(mymap, myadd, ll(1, 2, 3), ll(2, 4, 6)) == ll(3, 6, 9)

    # map_longest. foldr would walk the inputs from the right; use foldl.
    mymap_longestrev = lambda f: curry(foldl, composerc(cons, f), nil, longest=True)
    mymap_longest = composerc(lreverse, mymap_longestrev)
    def noneadd(a, b):
        if all(x is not None for x in (a, b)):
            return a + b
    assert curry(mymap_longest, noneadd, ll(1, 2, 3), ll(2, 4)) == ll(3, 6, None)

    reverse_one = curry(foldl, cons, nil)
    assert reverse_one(ll(1, 2, 3)) == ll(3, 2, 1)

    append_two = lambda a, b: foldr(cons, b, a)  # a, b: linked lists
    assert append_two(ll(1, 2, 3), ll(4, 5, 6)) == ll(1, 2, 3, 4, 5, 6)

    # see upythonic.llist.lappend
    append_many = lambda *lsts: foldr(append_two, nil, lsts)
    assert append_many(ll(1, 2), ll(3, 4), ll(5, 6)) == ll(1, 2, 3, 4, 5, 6)

    mysum = curry(foldl, add, 0)
    myprod = curry(foldl, mul, 1)
    a = ll(1, 2)
    b = ll(3, 4)
    assert mysum(append_two(a, b)) == 10
    assert myprod(b) == 12

    packtwo = lambda a, b: ll(a, b)  # using a tuple return value here would confuse curry.
    assert foldl(composerc(cons, packtwo), nil, (1, 2, 3), (4, 5), longest=True) == \
           ll(ll(3, None), ll(2, 5), ll(1, 4))

    @rotate(1)
    def zipper(acc, *rest):   # so that we can use the *args syntax to declare this
        return acc + (rest,)  # even though the input is (e1, ..., en, acc).
#    def zipper(*args):  # straightforward version
#        *rest, acc = args
#        return acc + (tuple(rest),)
    lzip1 = curry(foldl, zipper, ())
    rzip1 = curry(foldr, zipper, ())
    assert lzip1((1, 2, 3), (4, 5, 6), (7, 8)) == ((1, 4, 7), (2, 5, 8))
    assert rzip1((1, 2, 3), (4, 5, 6), (7, 8)) == ((2, 5, 8), (1, 4, 7))
    # But:
    assert tuple(rzip((1, 2, 3), (4, 5, 6), (7, 8))) == ((3, 6, 8), (2, 5, 7))
    # This is because rzip1 above *walks* from the left even though the *fold*
    # is performed from the right. Hence the inputs are synced by their
    # *left* ends. But the rzip function perform a reverse and then walks;
    # the inputs are synced by their *right* ends.

    # Unfold.
    #
    def step2(k):  # x0, x0 + 2, x0 + 4, ...
        return (k, k + 2)

    def fibo(a, b):
        return (a, b, a + b)

    def myiterate(f, x):  # x0, f(x0), f(f(x0)), ...
        return (x, f, f(x))

    def zip_two(As, Bs):
        if len(As) and len(Bs):
            (A0, *moreAs), (B0, *moreBs) = As, Bs
            return ((A0, B0), moreAs, moreBs)

    assert tuple(take(10, unfold1(step2, 10))) == (10, 12, 14, 16, 18, 20, 22, 24, 26, 28)
    assert tuple(take(10, unfold(fibo, 1, 1))) == (1, 1, 2, 3, 5, 8, 13, 21, 34, 55)
    assert tuple(take(5, unfold(myiterate, lambda x: x**2, 2))) == (2, 4, 16, 256, 65536)
    assert tuple(unfold(zip_two, (1, 2, 3, 4), (5, 6, 7))) == ((1, 5), (2, 6), (3, 7))

    print("All tests PASSED")

if __name__ == '__main__':
    test()
