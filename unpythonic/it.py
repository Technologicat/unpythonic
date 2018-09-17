#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Missing batteries for itertools.

Racket-like multi-input ``foldl`` and ``foldr`` based on
  https://docs.racket-lang.org/reference/pairs.html

``scanl`  and ``scanr`` inspired by ``itertools.accumulate``, Haskell,
and (stream-scan) in SRFI-41.
  https://srfi.schemers.org/srfi-41/srfi-41.html

``take`` and ``drop`` based on Haskell.

``flatten`` based on Danny Yoo's version:
  http://rightfootin.blogspot.fi/2006/09/more-on-python-flatten.html
"""

__all__ = ["scanl", "scanr", "scanl1", "scanr1",
           "foldl", "foldr", "reducel", "reducer",
           "flatmap", "mapr", "zipr", "uniqify", "uniq",
           "take", "drop", "split_at", "unpack",
           "tail", "first", "second", "nth", "last",
           "flatten", "flatten1", "flatten_in",
           "iterate", "iterate1"]

from itertools import tee, islice
from collections import deque
from inspect import isgenerator

# require at least one iterable to make this work seamlessly with curry.
def scanl(proc, init, iterable0, *iterables):
    """Scan (accumulate), optionally with multiple input iterables.

    Similar to ``itertools.accumulate``. If the inputs are generators, this is
    essentially a lazy ``foldl`` that yields the intermediate result at each step.
    Hence, useful for partially folding infinite sequences.

    At least one iterable (``iterable0``) is required. More are optional.

    Terminates when the shortest input runs out.

    Initial value is mandatory; there is no sane default for the case with
    multiple inputs.

    Returns a generator, which (roughly, in pseudocode)::

        acc = init
        for elts in zip(iterable0, *iterables):
            yield proc(*elts, acc)  # if this was legal syntax
    """
    iterables = (iterable0,) + iterables
    def heads(its):
        hs = []
        for it in its:
            try:
                h = next(it)
            except StopIteration:  # shortest sequence ran out
                return StopIteration
            hs.append(h)
        return tuple(hs)
    iters = tuple(iter(x) for x in iterables)
    acc = init
    while True:
        yield acc
        hs = heads(iters)
        if hs is StopIteration:
            break
        acc = proc(*(hs + (acc,)))

def scanr(proc, init, sequence0, *sequences):
    """Like scanl, but scan from the right (walk each sequence backwards)."""
    return scanl(proc, init, reversed(sequence0), *(reversed(s) for s in sequences))

def scanl1(proc, iterable, init=None):
    """scanl for a single iterable, with optional init.

    If ``init is None``, use the first element from the iterable.

    If the iterable is empty, return ``None``.
    """
    it = iter(iterable)
    if not init:
        try:
            init = next(it)
        except StopIteration:
            return None  # empty input sequence
    return scanl(proc, init, it)

def scanr1(proc, sequence, init=None):
    """Like scanl1, but scan from the right (walk backwards).

    If ``init is None``, use the first element from the reversed sequence
    (i.e. the last element of the original sequence).
    """
    return scanl1(proc, reversed(sequence), init)

def foldl(proc, init, iterable0, *iterables):
    """Racket-like foldl that supports multiple input iterables.

    At least one iterable (``iterable0``) is required. More are optional.

    Terminates when the shortest input runs out.

    Initial value is mandatory; there is no sane default for the case with
    multiple inputs.

    Note order: ``proc(elt, acc)``, which is the opposite order of arguments
    compared to ``functools.reduce``. General case ``proc(e1, ..., en, acc)``.
    """
    return last(scanl(proc, init, iterable0, *iterables))

def foldr(proc, init, sequence0, *sequences):
    """Like foldl, but fold from the right (walk each sequence backwards)."""
    # Reverse, then left-fold gives us a linear process.
    return foldl(proc, init, reversed(sequence0), *(reversed(s) for s in sequences))

def reducel(proc, iterable, init=None):
    """Foldl for a single iterable, with optional init.

    If ``init is None``, use the first element from the iterable.

    Like ``functools.reduce``, but uses ``proc(elt, acc)`` like Racket."""
    return last(scanl1(proc, iterable, init))

def reducer(proc, sequence, init=None):
    """Like reducel, but fold from the right (walk backwards).

    If ``init is None``, use the first element from the reversed sequence
    (i.e. the last element of the original sequence).
    """
    return reducel(proc, reversed(sequence), init)

def flatmap(f, iterable0, *iterables):
    """Map, then concatenate results.

    At least one iterable (``iterable0``) is required. More are optional.

    ``f`` should accept as many arguments as iterables given (each argument
    drawn from one of the iterables), and return an iterable.

    Returns a generator that yields the flatmapped result.

    Example::

        def msqrt(x):  # multivalued sqrt
            if x == 0.:
                return (0.,)
            else:
                s = x**0.5
                return (s, -s)
        assert tuple(flatmap(msqrt, (0, 1, 4, 9))) == \\
               (0., 1., -1., 2., -2., 3., -3.)

        def add_and_tuplify(a, b):
            return (a + b,)
        assert tuple(flatmap(add_and_tuplify, (10, 20, 30), (1, 2, 3))) == \\
               (11, 22, 33)

        def sum_and_diff(a, b):
            return (a + b, a - b)
        assert tuple(flatmap(sum_and_diff, (10, 20, 30), (1, 2, 3))) == \\
               (11, 9, 22, 18, 33, 27)
    """
#    def concat(elt, acc):
#        return tuple(acc) + tuple(elt)
#    return foldl(concat, (), map(f, *lsts))  # eager, bad
    iterables = (iterable0,) + iterables
    for xs in map(f, *iterables):
        for x in xs:
            yield x

def mapr(func, *sequences):
    """Like map, but walk each sequence from the right."""
    return map(func, *(reversed(s) for s in sequences))

def zipr(*sequences):
    """Like zip, but walk each sequence from the right."""
    return zip(*(reversed(s) for s in sequences))

def uniqify(iterable, key=None):
    """Skip duplicates in iterable.

    Returns a generator that yields unique items from iterable, preserving
    their original ordering.

    If ``key`` is provided, the return value of ``key(elt)`` is tested instead
    of ``elt`` itself to determine uniqueness.
    """
    key = key or (lambda x: x)
    it = iter(iterable)
    seen = set()
    for e in it:
        k = key(e)
        if k not in seen:
            seen.add(k)
            yield e

def uniq(iterable, key=None):
    """Like uniqify, but for consecutive duplicates only.

    Named after the *nix utility.
    """
    key = key or (lambda x: x)
    it = iter(iterable)
    lasthash = object()  # essentially gensym
    for e in it:
        h = hash(key(e))
        if h != lasthash:  # no guarantees on singleton-ness
            lasthash = h
            yield e

def _makegen(iterable):  # ensure iterable is a generator
    if isgenerator(iterable):
        return iterable
    def gen():
        yield from iterable
    return gen()

def take(n, iterable):
    """Return a generator that yields the first n items of iterable, then stops.

    Stops earlier if ``iterable`` has fewer than ``n`` items.

    This is essentially ``take`` from ``itertools`` recipes,
    but returns a generator.
    """
    if n < 0:
        raise ValueError("expected n >= 0, got {}".format(n))
    it = iter(iterable)
    it = islice(it, n)
    return _makegen(it)

def drop(n, iterable):
    """Skip the first n elements of iterable, then yield the rest.

    If ``n`` is ``None``, consume the iterable until it runs out.

    This is essentially ``consume`` from ``itertools`` recipes,
    but returns a generator.
    """
    if n < 0:
        raise ValueError("expected n >= 0, got {}".format(n))
    elif n == 0:
        return iterable
    it = iter(iterable)
    if n is None:
        deque(it, maxlen=0)
    else:
        next(islice(it, n, n), None)  # advance it to empty slice starting at n
    return _makegen(it)

def split_at(n, iterable):
    """Split iterable at position n.

    Returns a pair of generators ``(first_part, second_part)``.

    Examples::

        a, b = split_at(5, range(10))
        assert tuple(a) == tuple(range(5))
        assert tuple(b) == tuple(range(5, 10))

        a, b = map(tuple, split_at(5, range(3)))
        assert a == tuple(range(3))
        assert b == ()
    """
    if n < 0:
        raise ValueError("expected n >= 0, got {}".format(n))
    ia, ib = tee(iter(iterable))
    return take(n, ia), drop(n, ib)

# FIXME: difficult to make unpack curryable.
def unpack(iterable, n, k=None, fillvalue=None):
    """From iterable, return the first n elements, and the kth tail.

    This is a lazy generalization of sequence unpacking that works also for
    infinite iterables.

    The return value is a tuple containing the ``n`` first elements, and as its
    last item, the tail of the iterable from item ``k`` onwards.

    Default ``k=None`` means ``k = n``, i.e. return the tail that begins
    right after the extracted items. Other values are occasionally useful,
    e.g. to peek into the tail, while not permanently extracting an item.

    If there are fewer than ``n`` items in the iterable, the missing items
    are returned as ``fillvalue``. The ``rest`` part is then a generator
    that just raises ``StopIteration``.

    If ``k < n`` (tail overlaps with the extracted items), the tail
    is formed by calling ``itertools.tee`` at the appropriate point
    during the extraction.

    If ``k == n`` (tail begins right after the extracted items), the tail
    is formed from the original iterator at the end of the extraction.

    If ``k > n`` (skip some items after the first n), then after extraction,
    the tail is formed by fast-forwarding the iterator using ``drop``.
    """
    if n < 0:
        raise ValueError("expected n >= 0, got {}".format(n))
    k = k or n
    if k < 0:
        raise ValueError("expected k >= 0, got {}".format(k))
    out = []
    rest = None
    it = iter(iterable)
    for j in range(n):
        try:
            if j == k:  # tail is desired to overlap with the extracted items
                it, rest = tee(it)
            out.append(next(it))
        except StopIteration:  # fewer than n items
            out += [fillvalue] * (n - len(out))
            def empty():
                yield from ()
            rest = empty()
    if not rest:  # avoid replacing empty()
        if k == n:
            rest = _makegen(it)
        elif k > n:
            rest = drop(k - n, it)
    out.append(rest)
    return tuple(out)

def tail(iterable):
    """Return the tail of an iterable, as a generator.

    Same as ```drop(1, iterable)```.
    """
    return drop(1, iterable)

def first(iterable, default=None):
    """Like nth, but return the first item."""
    return nth(0, iterable, default=default)

def second(iterable, default=None):
    """Like nth, but return the second item."""
    return nth(1, iterable, default=default)

def nth(n, iterable, *, default=None):
    """Return the item at position n from an iterable.

    The ``default`` is returned if there are fewer than ``n + 1`` items.
    """
    if n < 0:
        raise ValueError("expected n >= 0, got {}".format(n))
    if n == 0:
        it = iter(iterable)
    else:
        it = drop(n - 1, iterable)
    try:
        return next(it)
    except StopIteration:
        return default

def last(iterable, default=None):
    """Return the last item from an iterable.

    We consume the iterable until it runs out of items, then return the
    last item seen.

    The default value is returned if the iterable contained no items.

    **Caution**: Will not terminate for infinite inputs.
    """
    d = deque(iterable, maxlen=1)  # C speed
    return d.pop() if d else default
#    # slow (Python speed), otherwise fine
#    item = default
#    for item in iterable:
#        pass
#    return item

def flatten(iterable, pred=None):
    """Recursively remove nested structure from iterable.

    Process tuples and lists inside the iterable; pass everything else through
    (including any generators stored in the iterable).

    Returns a generator that yields the flattened output.

    ``pred`` is an optional predicate for filtering. It should accept a tuple
    (or list), and return ``True`` if that tuple/list should be flattened.
    When ``pred`` returns False, that tuple/list is passed through as-is.

    E.g. to flatten only those items that contain only tuples::

        is_nested = lambda e: all(isinstance(x, (tuple, list)) for x in e)
        data = (((1, 2), (3, 4)), (5, 6))
        assert tuple(flatten(data, is_nested)) == ((1, 2), (3, 4), (5, 6))
    """
    return _flatten(iterable, pred, recursive=True)

def flatten1(iterable, pred=None):
    """Like flatten, but process outermost level only."""
    return _flatten(iterable, pred, recursive=False)

def _flatten(iterable, pred=None, recursive=True):
    pred = pred or (lambda x: True)
    it = iter(iterable)
    for e in it:
        if isinstance(e, (list, tuple)) and pred(e):
            items = _flatten(e, pred) if recursive else e
            for f in items:
                yield f
        else:
            yield e

def flatten_in(iterable, pred=None):
    """Like flatten, but recurse also into tuples/lists not matching pred.

    This makes also those items get the same flattening applied inside them.

    Example::

        is_nested = lambda e: all(isinstance(x, (tuple, list)) for x in e)
        data = (((1, 2), ((3, 4), (5, 6)), 7), ((8, 9), (10, 11)))
        assert tuple(flatten(data, is_nested))    == \\
               (((1, 2), ((3, 4), (5, 6)), 7), (8, 9), (10, 11))
        assert tuple(flatten_in(data, is_nested)) == \\
               (((1, 2), (3, 4), (5, 6), 7), (8, 9), (10, 11))
    """
    pred = pred or (lambda x: True)
    it = iter(iterable)
    for e in it:
        if isinstance(e, (list, tuple)):
            if pred(e):
                for f in flatten_in(e, pred):
                    yield f
            else:
                t = type(e)
                new_e = t(flatten_in(e, pred))
                yield new_e
        else:
            yield e

def iterate1(f, x):
    """Return an infinite generator yielding x, f(x), f(f(x)), ..."""
#    # elegant FP def, but prone to eventual stack overflow in Python
#    yield x
#    yield from iterate1(f, f(x))
    while True:
        yield x
        x = f(x)

def iterate(f, *args):
    """Multiple-argument version of iterate1.

    The function ``f`` should return a tuple or list of as many elements as it
    takes positional arguments; this will be unpacked to the argument list in
    the next call.

    The yielded values are the tuples returned from the calls.
    """
    while True:
        yield args
        args = f(*args)

def test():
    from operator import add, mul, itemgetter
    from functools import partial
    from unpythonic.fun import curry, composer, composerc, composel, to1st, rotate, identity
    from unpythonic.llist import cons, nil, ll

    # scan/accumulate: lazy fold that yields intermediate results.
    assert tuple(scanl(add, 0, range(1, 5))) == (0, 1, 3, 6, 10)
    assert tuple(scanr(add, 0, range(1, 5))) == (0, 4, 7, 9, 10)
    assert tuple(scanl(mul, 1, range(2, 6))) == (1, 2, 6, 24, 120)
    assert tuple(scanr(mul, 1, range(2, 6))) == (1, 5, 20, 60, 120)

    assert tuple(scanl(cons, nil, ll(1, 2, 3))) == (nil, ll(1), ll(2, 1), ll(3, 2, 1))
    assert tuple(scanr(cons, nil, ll(1, 2, 3))) == (nil, ll(3), ll(2, 3), ll(1, 2, 3))

    # in contrast, fold just returns the final result.
    assert foldl(cons, nil, ll(1, 2, 3)) == ll(3, 2, 1)
    assert foldr(cons, nil, ll(1, 2, 3)) == ll(1, 2, 3)

    # reduce is a fold with a single input sequence, with init optional.
    assert reducel(add, (1, 2, 3)) == 6
    assert reducer(add, (1, 2, 3)) == 6

    # scanl1, scanr1 are a scan with a single input sequence, with init optional.
    assert tuple(scanl1(add, (1, 2, 3))) == (1, 3, 6)
    assert tuple(scanr1(add, (1, 2, 3))) == (3, 5, 6)

    def foo(a, b, acc):
        return acc + ((a, b),)
    assert foldl(foo, (), (1, 2, 3), (4, 5)) == ((1, 4), (2, 5))
    assert foldr(foo, (), (1, 2, 3), (4, 5)) == ((3, 5), (2, 4))

    def mymap_one(f, sequence):
        f_then_cons = composer(cons, to1st(f))  # args: elt, acc
        return foldr(f_then_cons, nil, sequence)
    double = lambda x: 2 * x
    assert mymap_one(double, ll(1, 2, 3)) == ll(2, 4, 6)
    def mymap_one2(f, sequence):
        f_then_cons = composel(to1st(f), cons)  # args: elt, acc
        return foldr(f_then_cons, nil, sequence)
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
    # accepts multiple input sequences.
    #
    # The sequences are taken by the processing function. acc, being the last
    # argument, is passed through on the right. The output from the processing
    # function - one new item - and acc then become a two-tuple, which gets
    # passed into cons.
    myadd = lambda x, y: x + y  # can't inspect signature of builtin add
    assert curry(mymap, myadd, ll(1, 2, 3), ll(2, 4, 6)) == ll(3, 6, 9)

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

    def msqrt(x):  # multivalued sqrt
        if x == 0.:
            return (0.,)
        else:
            s = x**0.5
            return (s, -s)
    assert tuple(flatmap(msqrt, (0, 1, 4, 9))) == (0., 1., -1., 2., -2., 3., -3.)

    def add_and_tuplify(a, b):
        return (a + b,)
    assert tuple(flatmap(add_and_tuplify, (10, 20, 30), (1, 2, 3))) == (11, 22, 33)

    def sum_and_diff(a, b):
        return (a + b, a - b)
    assert tuple(flatmap(sum_and_diff, (10, 20, 30), (1, 2, 3))) == (11, 9, 22, 18, 33, 27)

    assert tuple(take(10, range(100))) == tuple(range(10))
    assert tuple(take(10, range(3))) == tuple(range(3))

    assert tuple(drop(5, range(10))) == tuple(range(5, 10))
    assert tuple(drop(5, range(3))) == ()
    p = composel(partial(drop, 5), partial(take, 5))
    assert tuple(p(range(20))) == tuple(range(5, 10))

    with_same_n = lambda n, fs: (partial(f, n) for f in fs)
#    with_same_n = lambda n, fs: map((lambda f: partial(f, n)), fs)
    p = composel(*with_same_n(5, (drop, take)))
    assert tuple(p(range(20))) == tuple(range(5, 10))

    with_n = lambda *args: (partial(f, n) for n, f in args)
    p = composel(*with_n((5, drop), (10, take)))
    assert tuple(p(range(20))) == tuple(range(5, 15))

    a, b = map(tuple, split_at(5, range(10)))
    assert a == tuple(range(5))
    assert b == tuple(range(5, 10))

    a, b = map(tuple, split_at(5, range(3)))
    assert a == tuple(range(3))
    assert b == ()

    assert tuple(zipr((1, 2, 3), (4, 5, 6), (7, 8))) == ((3, 6, 8), (2, 5, 7))

    @rotate(1)
    def zipper(acc, *rest):   # so that we can use the *args syntax to declare this
        return acc + (rest,)  # even though the input is (e1, ..., en, acc).
#    def zipper(*args):  # straightforward version
#        *rest, acc = args
#        return acc + (tuple(rest),)
    zipl1 = curry(foldl, zipper, ())
    zipr1 = curry(foldr, zipper, ())
    assert zipl1((1, 2, 3), (4, 5, 6), (7, 8)) == ((1, 4, 7), (2, 5, 8))
    assert zipr1((1, 2, 3), (4, 5, 6), (7, 8)) == ((3, 6, 8), (2, 5, 7))

    # Python's builtin map is not curry-friendly; it accepts arity 1,
    # but actually requires 2. Solution: use partial.
    zipl2 = partial(map, identity)
    zipr2 = lambda *sequences: map(identity, *(reversed(s) for s in sequences))
    assert tuple(zipl2((1, 2, 3), (4, 5, 6), (7, 8))) == ((1, 4, 7), (2, 5, 8))
    assert tuple(zipr2((1, 2, 3), (4, 5, 6), (7, 8))) == ((3, 6, 8), (2, 5, 7))

    zipr3 = partial(mapr, identity)
    assert tuple(zipr3((1, 2, 3), (4, 5, 6), (7, 8))) == ((3, 6, 8), (2, 5, 7))

    assert tuple(uniqify((1, 1, 2, 2, 2, 2, 4, 3, 3, 3))) == (1, 2, 4, 3)
    data = (('foo', 1), ('bar', 1), ('foo', 2), ('baz', 2), ('qux', 4), ('foo', 3))
    assert tuple(uniqify(data, key=itemgetter(0))) == (('foo', 1), ('bar', 1), ('baz', 2), ('qux', 4))
    assert tuple(uniqify(data, key=itemgetter(1))) == (('foo', 1), ('foo', 2), ('qux', 4), ('foo', 3))

    assert tuple(uniq((1, 1, 2, 2, 2, 1, 2, 2, 4, 3, 4, 3, 3))) == (1, 2, 1, 2, 4, 3, 4, 3)

    assert tuple(flatten(((1, 2), (3, (4, 5), 6), (7, 8, 9)))) == (1, 2, 3, 4, 5, 6, 7, 8, 9)
    assert tuple(flatten1(((1, 2), (3, (4, 5), 6), (7, 8, 9)))) == (1, 2, 3, (4, 5), 6, 7, 8, 9)

    is_nested = lambda e: all(isinstance(x, (tuple, list)) for x in e)
    assert tuple(flatten((((1, 2), (3, 4)), (5, 6)), is_nested)) == ((1, 2), (3, 4), (5, 6))

    data = (((1, 2), ((3, 4), (5, 6)), 7), ((8, 9), (10, 11)))
    assert tuple(flatten(data, is_nested))    == (((1, 2), ((3, 4), (5, 6)), 7), (8, 9), (10, 11))
    assert tuple(flatten_in(data, is_nested)) == (((1, 2), (3, 4), (5, 6), 7),   (8, 9), (10, 11))

    # http://learnyouahaskell.com/higher-order-functions
    def collatz(n):
        if n < 1:
            raise ValueError()
        while True:
            yield n
            if n == 1:
                break
            n = n // 2 if n % 2 == 0 else 3 * n + 1
    assert tuple(collatz(13)) == (13, 40, 20, 10, 5, 16, 8, 4, 2, 1)
    assert tuple(collatz(10)) == (10, 5, 16, 8, 4, 2, 1)
    assert tuple(collatz(30)) == (30, 15, 46, 23, 70, 35, 106, 53, 160, 80, 40, 20, 10, 5, 16, 8, 4, 2, 1)
    def len_gt(k, s):
        a, _ = unpack(drop(k, s), 1)
        return a  # None if no item
    islong = curry(len_gt, 15)
    assert sum(1 for n in range(1, 101) if islong(collatz(n))) == 66

    # Implicitly defined infinite streams, using generators.
    #
    def adds(s1, s2):
        """Add two infinite streams (elementwise)."""
        yield from map(add, s1, s2)
    def muls(s, c):
        """Multiply an infinite stream by a constant."""
        yield from map(lambda x: c * x, s)

    # will eventually crash (stack overflow, no TCO'd yield)
    def ones_fp():
        yield 1
        yield from ones_fp()
    def nats_fp(start=0):
        yield start
        yield from adds(nats_fp(start), ones_fp())
    def fibos_fp():
        yield 1
        yield 1
        yield from adds(fibos_fp(), tail(fibos_fp()))
    def powers_of_2():
        yield 2
        yield from muls(powers_of_2(), 2)
    assert tuple(take(10, ones_fp())) == (1,) * 10
    assert tuple(take(10, nats_fp())) == tuple(range(10))
    assert tuple(take(10, fibos_fp())) == (1, 1, 2, 3, 5, 8, 13, 21, 34, 55)
    assert tuple(take(10, powers_of_2())) == (2, 4, 8, 16, 32, 64, 128, 256, 512, 1024)

    # not as FP as the above, but better Python
    def ones_python():
        while True:
            yield 1
    def nats_python(start=0):
        return scanl(add, start, ones_python())
    def fibos_python():
        a, b = 1, 1
        while True:
            yield a
            a, b = b, a + b
    assert tuple(take(10, ones_python())) == (1,) * 10
    assert tuple(take(10, nats_python())) == tuple(range(10))
    assert tuple(take(10, fibos_python())) == (1, 1, 2, 3, 5, 8, 13, 21, 34, 55)

    # How to improve accuracy of numeric differentiation with FP tricks.
    #
    # See:
    #   Hughes, 1984: Why Functional Programming Matters, p. 11 ff.
    #   http://www.cse.chalmers.se/~rjmh/Papers/whyfp.html
    #
    from math import sin, pi, log2
    def easydiff(f, x, h):  # as well known, wildly inaccurate
        return (f(x + h) - f(x)) / h
    def halve(x):
        return x / 2
    def differentiate(h0, f, x):
        return map(curry(easydiff, f, x), iterate1(halve, h0))
    def within(eps, s):
#        # FP
#        a, b, b_and_rest = unpack(s, 2, 1)  # unpack with peek
#        return b if abs(a - b) < eps else within(eps, b_and_rest)
        # not as elegant but better Python
        while True:
            a, b, s = unpack(s, 2, 1)
            if abs(a - b) < eps:
                return b
    def differentiate_with_tol(h0, f, x, eps):
        return within(eps, differentiate(h0, f, x))
    assert abs(differentiate_with_tol(0.1, sin, pi/2, 1e-8)) < 1e-7

    def order(s):
        """Estimate asymptotic order of s, using the first three terms."""
        a, b, c, _ = unpack(s, 3)
        return round(log2(abs((a - c) / (b - c)) - 1))
    def eliminate_error(n, s):
        """Eliminate error term of given asymptotic order n.

        The stream s must be based on halving h at each step
        for the formula used here to work."""
#        # FP
#        a, b, b_and_rest = unpack(s, 2, 1)
#        yield (b*2**n - a) / (2**(n - 1))
#        yield from eliminate_error(n, b_and_rest)
        # better Python
        while True:
            a, b, s = unpack(s, 2, 1)
            yield (b*2**n - a) / (2**(n - 1))
    def improve(s):
        """Eliminate asymptotically dominant error term from s."""
        return eliminate_error(order(s), s)
    def better_differentiate_with_tol(h0, f, x, eps):
        return within(eps, improve(differentiate(h0, f, x)))
    assert abs(better_differentiate_with_tol(0.1, sin, pi/2, 1e-8)) < 1e-9

    def super_improve(s):
        return map(second, iterate1(improve, s))
    def best_differentiate_with_tol(h0, f, x, eps):
        return within(eps, super_improve(differentiate(h0, f, x)))
    assert abs(best_differentiate_with_tol(0.1, sin, pi/2, 1e-8)) < 1e-12

    # pi approximation with Euler series acceleration
    #
    # See SICP, 2nd ed., sec. 3.5.3.
    #
    # This implementation originally by Jim Hoover, in Racket, from:
    # https://sites.ualberta.ca/~jhoover/325/CourseNotes/section/Streams.htm
    #
    partial_sums = curry(scanl1, add)
    def pi_summands(n):  # π/4 = 1 - 1/3 + 1/5 - 1/7 + ...
#        # The looming stack overflow is not a major problem; the rest of the algorithm
#        # will run into floating-point issues long before that (unless using mpmath).
#        yield 1 / n
#        yield from map(neg, pi_summands(n + 2))
        # But let's write better Python anyway.
        sign = +1
        while True:
            yield sign / n
            n += 2
            sign *= -1
    pi_stream = muls(partial_sums(pi_summands(1)), 4)

    # http://mathworld.wolfram.com/EulerTransform.html
    # https://en.wikipedia.org/wiki/Series_acceleration#Euler%27s_transform
    def euler_transform(s):
#        # FP
#        a, b, c, b_c_and_rest = unpack(s, 3, 1)
#        yield c - ((c - b)**2 / (a - 2*b + c))
#        yield from euler_transform(b_c_and_rest)
        # better Python
        while True:
            a, b, c, s = unpack(s, 3, 1)
            yield c - ((c - b)**2 / (a - 2*b + c))
    faster_pi_stream = euler_transform(pi_stream)

    def super_accelerate(transform, s):
        return map(first, iterate1(transform, s))
    fastest_pi_stream = super_accelerate(euler_transform, pi_stream)

    assert abs(last(take(6, pi_stream)) - pi) < 0.2
    assert abs(last(take(6, faster_pi_stream)) - pi) < 1e-3
    assert abs(last(take(6, fastest_pi_stream)) - pi) < 1e-15

    print("All tests PASSED")

if __name__ == '__main__':
    test()
