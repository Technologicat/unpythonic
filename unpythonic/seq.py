#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Sequencing constructs - for multi-expression lambdas."""

__all__ = ["begin", "begin0", "lazy_begin", "lazy_begin0",
           "pipe1", "piped1", "lazy_piped1",
           "pipe", "piped", "getvalue", "lazy_piped", "runpipe",
           "pipec",  # w/ curry
           "do", "do0", "assign"]

from collections import namedtuple
from unpythonic.env import env
from unpythonic.misc import call
from unpythonic.fun import curry
from unpythonic.arity import arity_includes, UnknownArity

# sequence side effects in a lambda
def begin(*vals):
    """Racket-like begin: return the last value.

    Eager; bodys already evaluated by Python when this is called.

        f = lambda x: begin(print("hi"),
                            42*x)
        print(f(1))  # 42
    """
    return vals[-1] if len(vals) else None

def begin0(*vals):  # eager, bodys already evaluated when this is called
    """Racket-like begin0: return the first value.

    Eager; bodys already evaluated by Python when this is called.

        g = lambda x: begin0(23*x,
                             print("hi"))
        print(g(1))  # 23
    """
    return vals[0] if len(vals) else None

def lazy_begin(*bodys):
    """Racket-like begin: run bodys in sequence, return the last return value.

    Lazy; each body must be a thunk (0-argument function), to delay its evaluation
    until begin() runs.

        f = lambda x: lazy_begin(lambda: print("hi"),
                                 lambda: 42*x)
        print(f(1))  # 42
    """
    l = len(bodys)
    if not l:
        return None
    if l == 1:
        b = bodys[0]
        return b()
    *rest, last = bodys
    for body in rest:
        body()
    return last()

def lazy_begin0(*bodys):
    """Racket-like begin0: run bodys in sequence, return the first return value.

    Lazy; each body must be a thunk (0-argument function), to delay its evaluation
    until begin0() runs.

        g = lambda x: lazy_begin0(lambda: 23*x,
                                  lambda: print("hi"))
        print(g(1))  # 23
    """
    l = len(bodys)
    if not l:
        return None
    if l == 1:
        b = bodys[0]
        return b()
    first, *rest = bodys
    out = first()
    for body in rest:
        body()
    return out

# sequence one-input, one-output functions
def pipe1(value0, *bodys):
    """Perform a sequence of operations on an initial value.

    Bodys are applied left to right.

    Each body must be a 1-argument function. It takes the current value,
    and it must return the next value (the last body, the final value).

    Examples. Given::

        double = lambda x: 2 * x
        inc    = lambda x: x + 1

    these lines are equivalent::

        x = inc(double(42))  # --> 85

        x = pipe1(42, double, inc)  # --> 85

    but now we don't need to read the source code backwards. This is essentially::

        f = composel(bodys)
        x = f(42)

    Perhaps the most common alternative in Python is this imperative code::

        x = 42
        x = double(x)
        x = inc(x)
        assert x == 85

    but now ``x`` no longer has a single definition. This is confusing, because
    mutation is not an essential feature of the algorithm, but instead is used
    as an implementation detail to avoid introducing extra temporaries.

    The definition issue can be avoided by::

        x0 = 42
        x1 = double(x0)
        x  = inc(x1)
        assert x == 85

    at the cost of namespace pollution.
    """
    # Ideally we should use fploop, but we choose to cheat imperatively to avoid
    # the added complexity of supporting the runtime-switchable TCO implementation.
#    @looped_over(bodys, acc=value0)
#    def x(loop, update, acc):
#        return loop(update(acc))
#    return x
    # Since "x" is a local, the imperative damage won't spread to the call site.
    x = value0
    for update in bodys:
        x = update(x)
    return x

@call  # make a singleton
class getvalue:  # sentinel with a nice repr
    """Sentinel; pipe into this to exit a shell-like pipe and return the current value."""
    def __repr__(self):
        return "<sentinel for pipe exit>"
runpipe = getvalue  # same thing, but semantically better name for lazy pipes

class piped1:
    """Shell-like piping syntax.

    Eager; apply each function immediately and store the new value.
    """
    def __init__(self, x):
        """Set up a pipe and load the initial value x into it."""
        self._x = x
    def __or__(self, f):
        """Pipe the value through the one-argument function f.

        Return a ``piped`` object, for chainability.

        As the only exception, if ``f`` is the sentinel ``getvalue``,
        return the current value (useful for exiting the pipe).

        A new ``piped`` object is created at each step of piping; the "update"
        is purely functional, nothing is overwritten.

        Examples::

            x = piped1(42) | double | inc | getvalue

            y = piped1(42) | double
            assert y | inc | getvalue == 85
            assert y | getvalue == 84  # y is not modified
        """
        if f is getvalue:
            return self._x
        cls = self.__class__
        return cls(f(self._x))  # functional update
    def __repr__(self):
        return "<piped1 at 0x{:x}; value {}>".format(id(self), self._x)

class lazy_piped1:
    """Like piped, but apply the functions later.

    This matters if the initial value is mutable:

        - ``piped`` computes immediately and stores a copy of the new result
          at each step. Any updates to the initial value are not seen by
          the pipeline.

        - ``lazy_piped`` just sets up a computation, and performs it when eventually
          piped into ``runpipe``. The computation always looks up the latest state
          of the initial value.

    Another way to say this is that ``lazy_piped`` looks up the initial value
    dynamically, at get time.
    """
    def __init__(self, x, *, _funcs=None):
        """Set up a lazy pipe and load the initial value x into it.

        The ``_funcs`` parameter is for internal use.
        """
        self._x = x
        self._funcs = _funcs or ()
    def __or__(self, f):
        """Pipe the value into f; but just plan to do so, don't perform it yet.

        To run the stored computation, pipe into ``runpipe``.

        Examples::

            lst = [1]
            def append_succ(l):
                l.append(l[-1] + 1)
                return l  # important, handed to the next function in the pipe
            p = lazy_piped1(lst) | append_succ | append_succ  # plan a computation
            assert lst == [1]        # nothing done yet
            p | runpipe              # run the computation
            assert lst == [1, 2, 3]  # now the side effect has updated lst.

            # lazy pipe as an unfold
            fibos = []
            def nextfibo(state):
                a, b = state
                fibos.append(a)      # store result by side effect
                return (b, a + b)    # new state, handed to next function in the pipe
            p = lazy_piped1((1, 1))  # load initial state into a lazy pipe
            for _ in range(10):      # set up pipeline
                p = p | nextfibo
            p | runpipe
            print(fibos)
        """
        if f is runpipe:  # compute now
            v = self._x
            for g in self._funcs:
                v = g(v)
            return v
        # just pass on the reference to the original x.
        cls = self.__class__
        return cls(x=self._x, _funcs=self._funcs + (f,))
    def __repr__(self):
        return "<lazy_piped1 at 0x{:x}; initial value now {}, functions {}>".format(id(self), self._x, self._funcs)

def pipe(values0, *bodys):
    """Like pipe1, but with arbitrary number of inputs/outputs at each step.

    The only restriction is that each function must take as many positional
    arguments as the previous one returns.

    At each step, if the output from a function is a list or a tuple,
    it is unpacked to the argument list of the next function. Otherwise,
    we assume the output is intended to be fed to the next function as-is.

    If you only need a one-in-one-out chain, ``pipe1`` is faster.

    Examples::

        a, b = pipe((2, 3),
                    lambda x, y: (x + 1, 2 * y),
                    lambda x, y: (x * 2, y + 1))
        assert (a, b) == (6, 7)

        a, b, c = pipe((2, 3),
                       lambda x, y: (x + 1, 2 * y, "foo"),
                       lambda x, y, s: (x * 2, y + 1, "got {}".format(s)))
        assert (a, b, c) == (6, 7, "got foo")

        a, b = pipe((2, 3),
                    lambda x, y: (x + 1, 2 * y, "foo"),
                    lambda x, y, s: (x * 2, y + 1, "got {}".format(s)),
                    lambda x, y, s: (x + y, s))
        assert (a, b) == (13, "got foo")
    """
    xs = values0
    for update in bodys:
        if isinstance(xs, (list, tuple)):
            xs = update(*xs)
        else:
            xs = update(xs)
    if isinstance(xs, (list, tuple)):
        return xs if len(xs) > 1 else xs[0]
    return xs

def pipec(values0, *bodys):
    """Like pipe, but curry each function before piping.

    Useful with the passthrough in ``curry``. Each function only needs to
    declare as many of the (leftmost) arguments as it needs to access or modify::

        a, b = pipec((1, 2),
                     lambda x: x + 1,  # extra args passed through on the right
                     lambda x, y: (x * 2, y + 1))
        assert (a, b) == (4, 3)
    """
    return pipe(values0, *map(curry, bodys))

class piped:
    """Like piped1, but for any number of inputs/outputs at each step."""
    def __init__(self, *xs):
        """Set up a pipe and load the initial values xs into it."""
        self._xs = xs
    def __or__(self, f):
        """Pipe the values through the function f.

        Example::

            f = lambda x, y: (2*x, y+1)
            g = lambda x, y: (x+1, 2*y)
            x = piped(2, 3) | f | g | getvalue  # --> (5, 8)
        """
        xs = self._xs
        if f is getvalue:
            return xs if len(xs) > 1 else xs[0]
        cls = self.__class__
        if isinstance(xs, (list, tuple)):
            newxs = f(*xs)
        else:
            newxs = f(xs)
        if isinstance(newxs, (list, tuple)):
            return cls(*newxs)
        return cls(newxs)
    def __repr__(self):
        return "<piped at 0x{:x}; values {}>".format(id(self), self._xs)

class lazy_piped:
    """Like lazy_piped1, but for any number of inputs/outputs at each step.

    Examples::

        p1 = lazy_piped(2, 3)
        p2 = p1 | (lambda x, y: (x + 1, 2 * y, "foo"))
        p3 = p2 | (lambda x, y, s: (x * 2, y + 1, "got {}".format(s)))
        p4 = p3 | (lambda x, y, s: (x + y, s))
        # nothing done yet!
        assert (p4 | runpipe) == (13, "got foo")

        # lazy pipe as an unfold
        fibos = []
        def nextfibo(a, b):    # now two arguments
            fibos.append(a)
            return (b, a + b)  # two return values, still expressed as a tuple
        p = lazy_piped(1, 1)
        for _ in range(10):
            p = p | nextfibo
        p | runpipe
        print(fibos)
    """
    def __init__(self, *xs, _funcs=None):
        """Set up a lazy pipe and load the initial values xs into it.

        The ``_funcs`` parameter is for internal use.
        """
        self._xs = xs
        self._funcs = _funcs or ()
    def __or__(self, f):
        """Pipe the values into f; but just plan to do so, don't perform it yet."""
        if f is runpipe:  # compute now
            vs = self._xs
            for g in self._funcs:
                if isinstance(vs, (list, tuple)):
                    vs = g(*vs)
                else:
                    vs = g(vs)
            return vs if len(vs) > 1 else vs[0]
        # just pass on the references to the original xs.
        cls = self.__class__
        return cls(*self._xs, _funcs=self._funcs + (f,))
    def __repr__(self):
        return "<lazy_piped at 0x{:x}; initial values now {}, functions {}>".format(id(self), self._xs, self._funcs)

# do(): improved begin() that can name intermediate results and refer to them
DoAssign = namedtuple("DoAssign", "name value")
def assign(**binding):
    """Bind a name to a value inside a do().

    Re-using a previous name overwrites.

    Usage:

        do(...,
           assign(x=42),
           ...)
    """
    if len(binding) != 1:
        raise ValueError("Expected exactly one binding, got {:d} with values {}".format(len(binding), binding))
    for k, v in binding.items():
        return DoAssign(k, v)

def do(*items):
    """Haskell-ish do, but without any monadic magic.

    Run ``items`` sequentially. Optionally, locally bind a name to each result,
    like ``letrec`` does. Return the value of the last item.

    Basically, ``do`` is:

        - A ``let*`` (technically, ``letrec``) where making a binding is
          optional, so that some items can have only side effects if so desired.
          No separate ``body``; all items play the same role.

        - An improved ``begin`` that can bind names to intermediate
          results and then use them in later items.

    Either way, this allows stuffing imperative code into a lambda.

    Like in ``letrec``, use ``lambda e: ...`` to access the environment,
    and to wrap callable values (to prevent misunderstandings).

    Examples::

        y = do(assign(x=17),
           lambda e: print(e.x),      # 17; uses environment, needs lambda e: ...
           assign(x=23),              # overwrite e.x
           lambda e: print(e.x),      # 23
           42)                        # return value
        assert y == 42

        y = do(assign(x=17),
               assign(z=lambda e: 2*e.x),
               lambda e: e.z)
        assert y == 34

        y = do(assign(x=5),
               assign(f=lambda e: lambda x: x**2),  # callable, needs lambda e: ...
               print("hello from 'do'"),  # value is None; not callable
               lambda e: e.f(e.x))
        assert y == 25

    But beware of this pitfall::

        do(lambda e: print("hello 2 from 'do'"),  # delayed because lambda e: ...
           print("hello 1 from 'do'"),
           "foo")

    Python prints "hello 1 from 'do'" immediately, before ``do()`` gets control,
    because technically, it is **the return value** that is an argument for ``do()``.

    Similarly, escapes must be delayed::

        call_ec(
          lambda ec:
            do(assign(x=42),
               lambda e: ec(e.x),                  # IMPORTANT: must delay this!
               lambda e: print("never reached")))  # and this (as above)

    Otherwise, ``do()`` will never get control before the escape triggers.
    The print must also be delayed, just like above.

    The situation is different with ``begin``, because there no assignments
    can occur; hence there it doesn't matter whether the items are evaluated
    before or after ``begin()`` gets control, as long as this choice is kept
    consistent for all of the expressions.
    """
    e = env()
    def maybe_call(v):
        if callable(v):
            try:
                if not arity_includes(v, 1):
                    raise ValueError("Arity mismatch; callable value must allow arity 1, to take in the environment.")
            except UnknownArity:  # well, we tried!
                pass
            return v(e)
        return v
    for item in items:
        if isinstance(item, DoAssign):
            k, v = item
            item = e[k] = maybe_call(v)
        else:
            item = maybe_call(item)  # perform side effects
    return item  # return the final value

def do0(*items):
    """Like do, but return the value of the first item.

    Examples::

        y = do0(17,
                assign(x=42),
                lambda e: print(e.x),
                print("hello from 'do0'"))
        assert y == 17

        y = do0(assign(x=17),  # the first item can be an assignment, too
                lambda e: print(e.x))
        assert y == 17
    """
    first, *rest = items
    if isinstance(first, DoAssign):
        k, v = first
        do0items = [first,
                    assign(_do0_result=lambda e: e[k])]
    else:
        do0items = [assign(_do0_result=first)]
    do0items.extend(rest)
    do0items.append(lambda e: e._do0_result)  # return value
    return do(*do0items)

def test():
    # sequence side effects in a lambda
    #
    f1 = lambda x: begin(print("cheeky side effect"), 42*x)
    assert f1(2) == 84

    f2 = lambda x: begin0(42*x, print("cheeky side effect"))
    assert f2(2) == 84

    f3 = lambda x: lazy_begin(lambda: print("cheeky side effect"),
                              lambda: 42*x)
    assert f3(2) == 84

    f4 = lambda x: lazy_begin0(lambda: 42*x,
                               lambda: print("cheeky side effect"))
    assert f4(2) == 84

    # pipe: sequence functions
    #
    double = lambda x: 2 * x
    inc    = lambda x: x + 1
    assert pipe1(42, double, inc) == 85  # 1-in-1-out
    assert pipe1(42, inc, double) == 86
    assert pipe(42, double, inc) == 85   # n-in-m-out, supports also 1-in-1-out
    assert pipe(42, inc, double) == 86

    # 2-in-2-out
    a, b = pipe((2, 3),
                lambda x, y: (x + 1, 2 * y),
                lambda x, y: (x * 2, y + 1))
    assert (a, b) == (6, 7)

    # 2-in-eventually-3-out
    a, b, c = pipe((2, 3),
                   lambda x, y: (x + 1, 2 * y, "foo"),
                   lambda x, y, z: (x * 2, y + 1, "got {}".format(z)))
    assert (a, b, c) == (6, 7, "got foo")

    # 2-in-3-in-between-2-out
    a, b = pipe((2, 3),
                lambda x, y: (x + 1, 2 * y, "foo"),
                lambda x, y, s: (x * 2, y + 1, "got {}".format(s)),
                lambda x, y, s: (x + y, s))
    assert (a, b) == (13, "got foo")

    # pipec: curry the functions before running the pipeline
    a, b = pipec((1, 2),
                 lambda x: x + 1,  # extra args passed through on the right
                 lambda x, y: (x * 2, y + 1))
    assert (a, b) == (4, 3)

    # optional shell-like syntax
    assert piped1(42) | double | inc | getvalue == 85

    y = piped1(42) | double
    assert y | inc | getvalue == 85
    assert y | getvalue == 84  # y is never modified by the pipe system

    # lazy pipe: compute later
    lst = [1]
    def append_succ(l):
        l.append(l[-1] + 1)
        return l  # important, handed to the next function in the pipe
    p = lazy_piped1(lst) | append_succ | append_succ  # plan a computation
    assert lst == [1]        # nothing done yet
    p | runpipe              # run the computation
    assert lst == [1, 2, 3]  # now the side effect has updated lst.

    # lazy pipe as an unfold
    fibos = []
    def nextfibo(state):
        a, b = state
        fibos.append(a)      # store result by side effect
        return (b, a + b)    # new state, handed to next function in the pipe
    p = lazy_piped1((1, 1))  # load initial state into a lazy pipe
    for _ in range(10):      # set up pipeline
        p = p | nextfibo
    p | runpipe
    assert fibos == [1, 1, 2, 3, 5, 8, 13, 21, 34, 55]

    # multi-arg version
    f = lambda x, y: (2*x, y+1)
    g = lambda x, y: (x+1, 2*y)
    x = piped(2, 3) | f | g | getvalue  # --> (5, 8)
    assert x == (5, 8)

    # abuse multi-arg version for single-arg case
    assert piped(42) | double | inc | getvalue == 85

    # multi-arg lazy pipe
    p1 = lazy_piped(2, 3)
    p2 = p1 | (lambda x, y: (x + 1, 2 * y, "foo"))
    p3 = p2 | (lambda x, y, s: (x * 2, y + 1, "got {}".format(s)))
    p4 = p3 | (lambda x, y, s: (x + y, s))
    # nothing done yet, and all computations purely functional:
    assert (p1 | runpipe) == (2, 3)
    assert (p2 | runpipe) == (3, 6, "foo")      # runs the chain up to p2
    assert (p3 | runpipe) == (6, 7, "got foo")  # runs the chain up to p3
    assert (p4 | runpipe) == (13, "got foo")

    # multi-arg lazy pipe as an unfold
    fibos = []
    def nextfibo(a, b):    # now two arguments
        fibos.append(a)
        return (b, a + b)  # two return values, still expressed as a tuple
    p = lazy_piped(1, 1)
    for _ in range(10):
        p = p | nextfibo
    p | runpipe
    assert fibos == [1, 1, 2, 3, 5, 8, 13, 21, 34, 55]

    # do: improved begin() that can name intermediate results
    y = do(assign(x=17),
           lambda e: print(e.x),  # 17; uses environment, needs lambda e: ...
           assign(x=23),          # overwrite e.x
           lambda e: print(e.x),  # 23
           42)                    # return value
    assert y == 42

    y = do(assign(x=17),
           assign(z=lambda e: 2*e.x),
           lambda e: e.z)
    assert y == 34

    y = do(assign(x=5),
           assign(f=lambda e: lambda x: x**2),  # callable, needs lambda e: ...
           print("hello from 'do'"),  # value is None; not callable
           lambda e: e.f(e.x))
    assert y == 25

    # Beware of this pitfall:
    do(lambda e: print("hello 2 from 'do'"),  # delayed because lambda e: ...
       print("hello 1 from 'do'"),  # Python prints immediately before do()
       "foo")                       # gets control, because technically, it is
                                    # **the return value** that is an argument
                                    # for do().

    # If you need to return the first value instead, use this trick:
    y = do(assign(result=17),
           print("assigned 'result' in env"),
           lambda e: e.result)  # return value
    assert y == 17

    # or use do0, which does it for you:
    y = do0(17,
            assign(x=42),
            lambda e: print(e.x),
            print("hello from 'do0'"))
    assert y == 17

    y = do0(assign(x=17),  # the first item of do0 can be an assignment, too
            lambda e: print(e.x))
    assert y == 17

    # pitfalls!
    #
    # WRONG!
    s = set()
    z = do(lambda e: print(s),  # there is already an item...
           s.add("foo"),        # ...because already added before do() gets control.
           lambda e: s)

    # OK
    s = set()
    z = do(lambda e: print(s),      # empty, ok!
           lambda e: s.add("foo"),  # now delayed until do() hits this line
           lambda e: s)

    from unpythonic.ec import call_ec
    z = call_ec(
          lambda ec:
            do(assign(x=42),
               lambda e: ec(e.x),                  # IMPORTANT: must delay this!
               lambda e: print("never reached")))  # and this (as above)
    assert z == 42

    print("All tests PASSED")

if __name__ == '__main__':
    test()
