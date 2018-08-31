#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Missing batteries for functools.

Some features modelled after Racket's builtins for handling procedures.
  https://docs.racket-lang.org/reference/procedures.html

foldl and foldr based on
  https://docs.racket-lang.org/reference/pairs.html

Memoize is typical FP (Racket has it in mischief), and flip comes from Haskell.
"""

__all__ = ["memoize", "curry", "flip", "rotate",
           "apply", "identity", "const", "negate", "conjoin", "disjoin",
           "foldl", "foldr", "reducel", "reducer",
           "composer1", "composel1",
           "composer", "composel", "to1st", "to2nd", "tokth", "tolast", "to"]

from functools import wraps, partial
from operator import itemgetter

from unpythonic.arity import arities

def memoize(f):
    """Decorator: memoize the function f.

    All of the args and kwargs of ``f`` must be hashable.

    Any exceptions raised by ``f`` are also memoized. If the memoized function
    is invoked again with arguments with which ``f`` originally raised an
    exception, *the same exception instance* is raised again.

    **CAUTION**: ``f`` must be pure (no side effects, no internal state
    preserved between invocations) for this to make any sense.
    """
    success, fail = [object() for _ in range(2)]  # sentinels
    memo = {}
    @wraps(f)
    def memoized(*args, **kwargs):
        k = (args, tuple(sorted(kwargs.items(), key=itemgetter(0))))
        if k not in memo:
            try:
                result = (success, f(*args, **kwargs))
            except BaseException as err:
                result = (fail, err)
            memo[k] = result  # should yell separately if k is not a valid key
        sentinel, value = memo[k]
        if sentinel is fail:
            raise value
        else:
            return value
    return memoized

def curry(f):
    """Decorator: curry the function f.

    Essentially, the resulting function automatically chains partial application
    until the minimum positional arity of ``f`` is satisfied, at which point
    ``f``is called.

    Also more kwargs can be passed at each step, but they do not affect the
    decision when the function is called.

    Examples::

        @curry
        def add3(a, b, c):
            return a + b + c
        assert add3(1)(2)(3) == 6

        @curry
        def lispyadd(*args):
            return sum(args)
        assert lispyadd() == 0  # no args is a valid arity here

        @curry
        def foo(a, b, *, c, d):
            return a, b, c, d
        assert foo(5, c=23)(17, d=42) == (5, 17, 23, 42)
    """
    # TODO: improve: all required name-only args should be present before calling f.
    # Difficult, partial() doesn't remove an already-set kwarg from the signature.
    min_arity, _ = arities(f)
    @wraps(f)
    def curried(*args, **kwargs):
        if len(args) < min_arity:
            return curry(partial(f, *args, **kwargs))
        return f(*args, **kwargs)
    return curried

def flip(f):
    """Decorator: flip (reverse) the positional arguments of f."""
    @wraps(f)
    def flipped(*args, **kwargs):
        return f(*reversed(args), **kwargs)
    return flipped

def rotate(k):
    """Decorator (factory): cycle positional args of f to the right by k places.

    Negative values cycle to the left.
    """
    def rotate_k(f):
        @wraps(f)
        def rotated(*args, **kwargs):
            nonlocal k
            n = len(args)
            if not n:
                raise TypeError("Expected at least one argument")
            k = k % n  # handle also negative values
            rargs = args[-k:] + args[:-k]
            return f(*rargs, **kwargs)
        return rotated
    return rotate_k

def apply(f, arg0, *more):
    """Scheme/Racket-like apply.

    Not really needed since Python has *, but included for completeness.

    ``f`` is a function.

    ``arg0``, if alone, is the list to unpack.

    Otherwise the last item of ``more`` is the list to unpack. Any earlier
    arguments (starting from ``arg0``) are concatenated at the front.
    """
    if not more:
        return f(*arg0)
    elif len(more) == 1:
        return f(arg0, *more[0])  # more[0] is the list to unpack
    else:
        args = (arg0,) + more[:-1] + more[-1]
        return f(*args)

def identity(*args):
    """Identity function.

    Accepts any positional arguments, and returns them as a tuple.

    Example::

        assert identity(1, 2, 3) == (1, 2, 3)
    """
    return args

def const(*args):
    """Constant function.

    Returns a function that accepts any arguments (also kwargs)
    and returns the args given here, as a tuple.

    Example::

        c = const(1, 2, 3)
        assert c(42, "foo") == (1, 2, 3)
    """
    def constant(*a, **kw):
        return args
    return constant

def negate(f):
    """Return a function that returns the logical not of the result of f.

    Examples::

        assert negate(lambda x: 2*x)(3) is False
        assert negate(lambda x: 2*x)(0) is True
    """
    @wraps(f)
    def negated(*args, **kwargs):
        return not f(*args, **kwargs)
    return negated

def conjoin(*fs):
    """Return a function that conjoins calls to fs with "and".

    Each function in ``fs`` is called with the same ``args`` and ``kwargs``,
    provided when the conjoined function is called.

    Evaluation short-circuits at the first falsey term, if any, returning ``False``.
    If all terms are truthy, the final return value (from the last function in
    ``fs``) is returned.

    Examples::

        assert conjoin(lambda x: isinstance(x, int), lambda x: x % 2 == 0)(42) is True
        assert conjoin(lambda x: isinstance(x, int), lambda x: x % 2 == 0)(43) is False
    """
    def conjoined(*args, **kwargs):
        b = True
        for f in fs:
            b = b and f(*args, **kwargs)
            if not b:
                return False
        return b
    return conjoined

def disjoin(*fs):
    """Return a function that disjoins calls to fs with "or".

    Each function in ``fs`` is called with the same ``args`` and ``kwargs``,
    provided when the disjoined function is called.

    Evaluation short-circuits at the first truthy term, if any, and it is returned.
    If all terms are falsey, the return value is False.

    Examples::

        isstr  = lambda s: isinstance(s, str)
        iseven = lambda x: isinstance(x, int) and x % 2 == 0
        assert disjoin(isstr, iseven)(42) is True
        assert disjoin(isstr, iseven)("foo") is True
        assert disjoin(isstr, iseven)(None) is False  # neither condition holds
    """
    def disjoined(*args, **kwargs):
        b = False
        for f in fs:
            b = b or f(*args, **kwargs)
            if b:
                return b
        return False
    return disjoined

def foldl(proc, init, iterable0, *iterables):  # minimum arity 3, for curry
    """Racket-like foldl that supports multiple input iterables.

    At least one iterable (``iterable0``) is required. More are optional.

    Terminates when the shortest input runs out.

    Initial value is mandatory; there is no sane default for the case with
    multiple inputs.

    Note order: ``proc(elt, acc)``, which is the opposite order of arguments
    compared to ``functools.reduce``. General case ``proc(e1, ..., en, acc)``.
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
        hs = heads(iters)
        if hs is StopIteration:
            return acc
        acc = proc(*(hs + (acc,)))

def foldr(proc, init, sequence0, *sequences):
    """Like foldl, but fold from the right (walk each sequence backwards)."""
    return foldl(proc, init, reversed(sequence0), *(reversed(s) for s in sequences))

def reducel(proc, iterable, init=None):
    """Foldl for a single iterable.

    Like functools.reduce, but uses ``proc(elt, acc)`` like Racket."""
    it = iter(iterable)
    if not init:
        try:
            init = next(it)
        except StopIteration:
            return None  # empty input sequence
    return foldl(proc, init, it)

def reducer(proc, sequence, init=None):
    """Like reducel, but fold from the right (walk backwards)."""
    return reducel(proc, reversed(sequence), init)

def composer1(*fs):
    """Like composer, but limited to one-argument functions. Faster.

    Example::

        double = lambda x: 2*x
        inc    = lambda x: x+1
        inc_then_double = composer1(double, inc)
        assert inc_then_double(3) == 8
    """
    def compose1_two(f, g):
        return lambda x: f(g(x))
    return reducer(compose1_two, fs)  # op(elt, acc)

def composel1(*fs):
    """Like composel, but limited to one-argument functions. Faster.

    Example::

        double = lambda x: 2*x
        inc    = lambda x: x+1
        double_then_inc = composel(double, inc)
        assert double_then_inc(3) == 7
    """
    return composer1(*reversed(fs))

def composer(*fs):
    """Compose functions accepting only positional args. Right to left.

    This mirrors the standard mathematical convention (f ∘ g)(x) ≡ f(g(x)).

    The output from the previous function is unpacked to the argument list
    of the next one. If the duck test fails, the output is assumed to be
    a single value, and is fed in to the next function as-is.
    """
    def unpack_ctx(*args): pass  # just a context where we can use * to unpack
    def compose_two(f, g):
        def composed(*args):
            a = g(*args)
            try:
                unpack_ctx(*a)
            except TypeError:
                return f(a)
            else:
                return f(*a)
        return composed
    return reducer(compose_two, fs)  # op(elt, acc)

def composel(*fs):
    """Like composer, but from left to right.

    The sequence ``fs`` is applied in the order given; no need
    to read the source code backwards.
    """
    return composer(*reversed(fs))

# Helpers for multi-arg compose chains
def tokth(k, f):
    """Return a function to apply f to args[k], pass the rest through.

    Negative indices also supported.

    Especially useful in multi-arg compose chains. See ``test()`` for examples.
    """
    def applicator(*args):
        n = len(args)
        if not n:
            raise TypeError("Expected at least one argument")
        nonlocal k
        k = k % n  # handle also negative values
        m = k + 1
        if n < m:
            raise TypeError("Expected at least {:d} arguments, got {:d}".format(m, n))
        out = list(args[:k])
        out.append(f(args[k]))  # mth argument
        if n > m:
            out.extend(args[m:])
        return tuple(out)
    return applicator

def to1st(f):
    """Return a function to apply f to first item in args, pass the rest through.

    Example::

        nil = ()
        def cons(x, l):  # elt, acc
            return (x,) + l
        def mymap_one(f, sequence):
            f_then_cons = composer(cons, to1st(f))  # args: elt, acc
            return foldr(f_then_cons, nil, sequence)
        double = lambda x: 2*x
        assert mymap_one(double, (1, 2, 3)) == (2, 4, 6)
    """
    return tokth(0, f)  # this is just a partial() but we want to provide a docstring.

def to2nd(f):
    """Return a function to apply f to second item in args, pass the rest through."""
    return tokth(1, f)

def tolast(f):
    """Return a function to apply f to last item in args, pass the rest through."""
    return tokth(-1, f)

def to(*specs):
    """Return a function to apply f1, ..., fn to items in args, pass the rest through.

    The specs are processed sequentially in the given order (allowing also
    multiple updates to the same item).

    Parameters:
        specs: tuple of `(k, f)`, where:
            k: int
              index (also negative supported)
            f: function
              One-argument function to apply to `args[k]`.

    Returns:
        Function to (functionally) update args with the specs applied.
    """
    return composel(*(tokth(k, f) for k, f in specs))

def test():
    from collections import Counter
    evaluations = Counter()
    @memoize
    def f(x):
        evaluations[x] += 1
        return x**2
    f(3)
    f(3)
    f(4)
    f(3)
    assert all(n == 1 for n in evaluations.values())

    # "memoize lambda": classic evaluate-at-most-once thunk
    thunk = memoize(lambda: print("hi from thunk"))
    thunk()
    thunk()

    evaluations = 0
    @memoize
    def t():
        nonlocal evaluations
        evaluations += 1
    t()
    t()
    assert evaluations == 1

    # exception storage in memoize
    class AllOkJustTesting(Exception):
        pass
    evaluations = 0
    @memoize
    def t():
        nonlocal evaluations
        evaluations += 1
        raise AllOkJustTesting()
    olderr = None
    for _ in range(3):
        try:
            t()
        except AllOkJustTesting as err:
            if olderr is not None and err is not olderr:
                assert False  # exception instance memoized, should be same every time
            olderr = err
        else:
            assert False  # memoize should not block raise
    assert evaluations == 1

    @curry
    def add3(a, b, c):
        return a + b + c
    assert add3(1)(2)(3) == 6
    # actually uses partial application so these work, too
    assert add3(1, 2)(3) == 6
    assert add3(1)(2, 3) == 6
    assert add3(1, 2, 3) == 6

    @curry
    def lispyadd(*args):
        return sum(args)
    assert lispyadd() == 0  # no args is a valid arity here

    @curry
    def foo(a, b, *, c, d):
        return a, b, c, d
    assert foo(5, c=23)(17, d=42) == (5, 17, 23, 42)

    # currying a thunk is essentially a no-op
    evaluations = 0
    @curry
    def t():
        nonlocal evaluations
        evaluations += 1
    t()
    assert evaluations == 1  # t has no args, so it should have been invoked

    # flip
    def f(a, b):
        return (a, b)
    assert f(1, 2) == (1, 2)
    assert (flip(f))(1, 2) == (2, 1)
    assert (flip(f))(1, b=2) == (1, 2)  # b -> kwargs

    nil = ()
    def cons(x, l):  # elt, acc
        return (x,) + l
    assert foldl(cons, nil, (1, 2, 3)) == (3, 2, 1)
    assert foldr(cons, nil, (1, 2, 3)) == (1, 2, 3)

    from operator import add
    assert reducel(add, (1, 2, 3)) == 6
    assert reducer(add, (1, 2, 3)) == 6

    def foo(a, b, acc):
        return acc + ((a, b),)
    assert foldl(foo, (), (1, 2, 3), (4, 5)) == ((1, 4), (2, 5))
    assert foldr(foo, (), (1, 2, 3), (4, 5)) == ((3, 5), (2, 4))

    double = lambda x: 2*x
    inc    = lambda x: x+1
    inc_then_double = composer1(double, inc)
    double_then_inc = composel1(double, inc)
    assert inc_then_double(3) == 8
    assert double_then_inc(3) == 7

    assert to1st(double)(1, 2, 3)  == (2, 2, 3)
    assert to2nd(double)(1, 2, 3)  == (1, 4, 3)
    assert tolast(double)(1, 2, 3) == (1, 2, 6)

    def mymap_one(f, sequence):
        f_then_cons = composer(cons, to1st(f))  # args: elt, acc
        return foldr(f_then_cons, nil, sequence)
    assert mymap_one(double, (1, 2, 3)) == (2, 4, 6)
    def mymap_one2(f, sequence):
        f_then_cons = composel(to1st(f), cons)  # args: elt, acc
        return foldr(f_then_cons, nil, sequence)
    assert mymap_one2(double, (1, 2, 3)) == (2, 4, 6)

    # point-free-ish style
    mymap_one3 = lambda f: partial(foldr, composer(cons, to1st(f)), nil)
    doubler = mymap_one3(double)
    assert doubler((1, 2, 3)) == (2, 4, 6)

    try:
        doubler((1, 2, 3), (4, 5, 6))
    except TypeError:
        pass
    else:
        assert False  # one arg too many; cons in the compose chain expects 2 args

    # minimum arity of fold functions is 3, to allow use with curry:
    mymap_one4 = lambda f: (curry(foldr))(composer(cons, to1st(f)), nil)
    doubler = mymap_one4(double)  # it's curried!
    assert doubler((1, 2, 3)) == (2, 4, 6)

    reverse_one = curry(foldl)(cons, nil)
    assert reverse_one((1, 2, 3)) == (3, 2, 1)

    processor = to((0, double),
                   (-1, inc),
                   (1, composer(double, double)),
                   (0, inc))
    assert processor(1, 2, 3) == (3, 8, 4)

    assert identity(1, 2, 3) == (1, 2, 3)
    assert (rotate(1)(identity))(1, 2, 3) == (3, 1, 2)
    assert (rotate(-1)(identity))(1, 2, 3) == (2, 3, 1)

    # Outer gets effectively applied first, because of the order in which
    # the decorators get their hands on the incoming, user-given arguments.
    assert flip(rotate(1)(identity))(1, 2, 3) == (1, 3, 2)

    @rotate(1)  # cycle *the incoming args* (not slots!) to the right by one place.
    def zipper(acc, *rest):   # so that we can use the *args syntax to declare this
        return acc + (rest,)  # even though the input is (e1, ..., en, acc).
#    def zipper(*args):  # straightforward version
#        *rest, acc = args
#        return acc + (tuple(rest),)
    zipl = (curry(foldl))(zipper, ())
    zipr = (curry(foldr))(zipper, ())
    assert zipl((1, 2, 3), (4, 5, 6), (7, 8)) == ((1, 4, 7), (2, 5, 8))
    assert zipr((1, 2, 3), (4, 5, 6), (7, 8)) == ((3, 6, 8), (2, 5, 7))

    def hello(*args):
        return args
    assert apply(hello, (1, 2, 3)) == (1, 2, 3)
    assert apply(hello, 1, (2, 3, 4)) == (1, 2, 3, 4)
    assert apply(hello, 1, 2, (3, 4, 5)) == (1, 2, 3, 4, 5)

    assert const(1, 2, 3)(42, "foo") == (1, 2, 3)
    assert negate(lambda x: 2*x)(3) is False
    assert negate(lambda x: 2*x)(0) is True
    assert conjoin(lambda x: isinstance(x, int), lambda x: x % 2 == 0)(42) is True
    assert conjoin(lambda x: isinstance(x, int), lambda x: x % 2 == 0)(43) is False
    isstr  = lambda s: isinstance(s, str)
    iseven = lambda x: isinstance(x, int) and x % 2 == 0
    assert disjoin(isstr, iseven)(42) is True
    assert disjoin(isstr, iseven)("foo") is True
    assert disjoin(isstr, iseven)(None) is False  # neither condition holds

    print("All tests PASSED")

if __name__ == '__main__':
    test()
