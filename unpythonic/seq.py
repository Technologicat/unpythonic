#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Sequencing constructs - for multi-expression lambdas."""

__all__ = ["begin", "begin0", "lazy_begin", "lazy_begin0",
           "pipe", "piped", "lazy_piped", "get",
           "do", "do0", "assign"]

from collections import namedtuple
from unpythonic.env import env

# evil inspect dependency, used only to provide informative error messages.
from unpythonic.arity import arity_includes

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
def pipe(value0, *bodys):
    """Perform a sequence of operations on an initial value.

    Bodys are applied left to right.

    Each body must be a 1-argument function. It takes the current value,
    and it must return the next value (the last body, the final value).

    Examples. Given::

        double = lambda x: 2 * x
        inc    = lambda x: x + 1

    these lines are equivalent::

        x = inc(double(42))  # --> 85

        x = pipe(42, double, inc)  # --> 85

    but now we don't need to read the source code backwards. This is essentially::

        f = compose(reversed(bodys))
        x = f(42)

    if you have a library that provides ``compose``.

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

class get:  # sentinel singleton with a nice repr
    """Sentinel; pipe into this to exit a shell-like pipe and return the current value."""
    def __repr__(self):
        return "<sentinel for pipe exit>"
get = get()

class piped:
    """Shell-like piping syntax.

    Eager; apply each function immediately and store the new value.
    """
    def __init__(self, x):
        """Set up a pipe and load the initial value x into it."""
        self._x = x
    def __or__(self, f):
        """Pipe the value through the one-argument function f.

        Return a ``piped`` object, for chainability.

        As the only exception, if ``f`` is the sentinel ``get``, return the
        current value (useful for exiting the pipe).

        A new ``piped`` object is created at each step of piping; the "update"
        is purely functional, nothing is overwritten.

        Examples::

            x = piped(42) | double | inc | get

            y = piped(42) | double
            assert y | inc | get == 85
            assert y | get == 84  # y is not modified
        """
        if f is get:
            return self._x
        else:
            cls = self.__class__
            return cls(f(self._x))  # functional update
    def __repr__(self):
        return "<piped at 0x{:x}; value {}>".format(id(self), self._x)

class lazy_piped:
    """Like piped, but apply the functions later, at get time.

    This matters if the initial value is mutable:

        - ``piped`` computes immediately and stores a copy of the new result
          at each step. Any updates to the initial value are not seen by
          the pipeline.

        - ``lazy_piped`` just sets up a computation, and performs it when eventually
          piped into ``get``. The computation always looks up the latest state
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

        To run the stored computation, pipe into ``get``.

        Examples::

            lst = [1]
            def append_succ(l):
                l.append(l[-1] + 1)
                return l  # important, handed to the next function in the pipe
            p = lazy_piped(lst) | append_succ | append_succ  # plan a computation
            assert lst == [1]        # nothing done yet
            p | get                  # run the computation
            assert lst == [1, 2, 3]  # now the side effect has updated lst.

            # lazy pipe as an unfold
            fibos = [1, 1]
            def nextfibo(state):
                a, b = state
                fibos.append(a + b)  # store result by side effect
                return (b, a + b)    # new state, handed to next function in the pipe
            p = lazy_piped(fibos)    # load initial state into a lazy pipe
            for _ in range(10):      # set up pipeline
                p = p | nextfibo
            p | get  # run it
            print(fibos)
        """
        if f is get:  # compute now
            v = self._x
            for g in self._funcs:
                v = g(v)
            return v
        else:
            # just pass on the reference to the original x.
            cls = self.__class__
            return cls(x=self._x, _funcs=self._funcs + (f,))
    def __repr__(self):
        return "<lazy_piped at 0x{:x}; initial value now {}, functions {}>".format(id(self), self._x, self._funcs)

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
           print("hello 1 from 'do'"),  # Python prints immediately before do()
           "foo")                       # gets control, because technically, it is
                                        # **the return value** that is an argument
                                        # for do().
    """
    e = env()
    def maybe_call(v):
        if callable(v):
            if not arity_includes(v, 1):
                raise ValueError("Arity mismatch; callable value must allow arity 1, to take in the environment.")
            return v(e)
        else:
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
    f = lambda x: begin(print("hi"),
                        42*x)
    assert f(1) == 42

    g = lambda x: begin0(23*x,
                         print("hi"))
    assert g(1) == 23

    test_lazy_begin = lambda: lazy_begin(lambda: print("hi"),
                                         lambda: "the return value")
    assert test_lazy_begin() == "the return value"

    test_lazy_begin0 = lambda: lazy_begin0(lambda: "the return value",
                                           lambda: print("hi"))
    assert test_lazy_begin0() == "the return value"

    # pipe one-input one-output functions
    double = lambda x: 2 * x
    inc    = lambda x: x + 1
    assert pipe(42, double, inc) == 85
    assert pipe(42, inc, double) == 86

    # with optional shell-like syntax
    assert piped(42) | double | inc | get == 85

    y = piped(42) | double
    assert y | inc | get == 85
    assert y | get == 84  # y is never modified by the pipe system

    # lazy pipe: compute at get time
    lst = [1]
    def append_succ(l):
        l.append(l[-1] + 1)
        return l  # important, handed to the next function in the pipe
    p = lazy_piped(lst) | append_succ | append_succ  # plan a computation
    assert lst == [1]        # nothing done yet
    p | get                  # run the computation
    assert lst == [1, 2, 3]  # now the side effect has updated lst.

    # lazy pipe as an unfold
    fibos = [1, 1]
    def nextfibo(state):
        a, b = state
        fibos.append(a + b)  # store result by side effect
        return (b, a + b)    # new state, handed to next function in the pipe
    p = lazy_piped(fibos)    # load initial state into a lazy pipe
    for _ in range(10):      # set up pipeline
        p = p | nextfibo
    p | get  # run it
    print(fibos)

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

    print("All tests PASSED")

if __name__ == '__main__':
    test()
