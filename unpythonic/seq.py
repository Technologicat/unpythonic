# -*- coding: utf-8 -*-
"""Sequencing constructs - for multi-expression lambdas."""

__all__ = ["begin", "begin0", "lazy_begin", "lazy_begin0",
           "pipe1", "piped1", "lazy_piped1",
           "pipe", "piped", "lazy_piped", "exitpipe",
           "pipec",  # w/ curry
           "do", "do0", "assign"]

from collections import namedtuple

from .arity import arity_includes, UnknownArity
from .collections import Values
from .dynassign import dyn
from .env import env
from .fun import curry, iscurried
from .lazyutil import force1, force, maybe_force_args, passthrough_lazy_args
from .symbol import sym

# sequence side effects in a lambda
def begin(*vals):
    """Racket-like begin: return the last value.

    Eager; bodys already evaluated by Python when this is called.

        f = lambda x: begin(print("hi"),
                            42*x)
        print(f(1))  # 42

    **CAUTION**: For regular code only. If you use macros, prefer `do[]`;
    the macro layer of `unpythonic` recognizes only the `do` constructs
    as a sequencing abstraction.
    """
    return vals[-1] if len(vals) else None

def begin0(*vals):  # eager, bodys already evaluated when this is called
    """Racket-like begin0: return the first value.

    Eager; bodys already evaluated by Python when this is called.

        g = lambda x: begin0(23*x,
                             print("hi"))
        print(g(1))  # 23

    **CAUTION**: For regular code only. If you use macros, prefer `do0[]`;
    the macro layer of `unpythonic` recognizes only the `do` constructs
    as a sequencing abstraction.
    """
    return vals[0] if len(vals) else None

def lazy_begin(*bodys):
    """Racket-like begin: run bodys in sequence, return the last return value.

    Lazy; each body must be a thunk (0-argument function), to delay its evaluation
    until begin() runs.

        f = lambda x: lazy_begin(lambda: print("hi"),
                                 lambda: 42*x)
        print(f(1))  # 42

    **CAUTION**: For regular code only. If you use macros, prefer `do[]`;
    the macro layer of `unpythonic` recognizes only the `do` constructs
    as a sequencing abstraction.
    """
    n = len(bodys)
    if not n:
        return None
    if n == 1:
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

    **CAUTION**: For regular code only. If you use macros, prefer `do0[]`;
    the macro layer of `unpythonic` recognizes only the `do` constructs
    as a sequencing abstraction.
    """
    n = len(bodys)
    if not n:
        return None
    if n == 1:
        b = bodys[0]
        return b()
    first, *rest = bodys
    out = first()
    for body in rest:
        body()
    return out

# TODO: test the new lazify support in piping constructs
# TODO: test `Values` handling in `with lazify`
#  - The `Values` container itself should always be eager (so it can be inspected without forcing the return value; important for symmetry with case of one positional return value)
#  - Anything we place into it should get the regular treatment, because return values are never implicitly lazy
# TODO: test multiple-return-values support in all function composition utilities
# TODO: expand tests of `continuations` to cases with named return values
# TODO: update code examples

# sequence one-input, one-output functions
@passthrough_lazy_args
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
    # Ideally we should use fploop, but we choose to cheat imperatively.
    # This used to be to avoid the added complexity of supporting the
    # runtime-switchable TCO implementation, but ever since we got rid of that
    # misfeature all the way back in v0.10, there's been really no reason to
    # avoid @looped_over, except performance.
    #
    # Since "x" is a local, the imperative damage won't spread to the call
    # site. So we can just as well use the builtin imperative for loop, and
    # reap the performance benefit.
    # @looped_over(bodys, acc=value0)
    # def x(loop, update, acc):
    #     return loop(update(acc))
    # return x
    x = value0
    for update in bodys:
        update = force1(update)
        x = maybe_force_args(update, x)
    return x

# Singleton value for exiting the pipe abstraction.
exitpipe = sym("exitpipe")

@passthrough_lazy_args
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

        As the only exception, if ``f`` is the sentinel ``exitpipe``,
        return the current value (thus exiting the pipe).

        A new ``piped`` object is created at each step of piping;
        the "update" is purely functional, nothing is overwritten.

        Examples::

            x = piped1(42) | double | inc | exitpipe

            y = piped1(42) | double
            assert y | inc | exitpipe == 85
            assert y | exitpipe == 84  # y is not modified
        """
        f = force1(f)
        if f is exitpipe:
            return self._x
        cls = self.__class__
        return cls(maybe_force_args(f, self._x))  # functional update
    def __repr__(self):  # pragma: no cover
        return f"<piped1 at 0x{id(self):x}; value {self._x}>"

@passthrough_lazy_args
class lazy_piped1:
    """Like piped, but apply the functions later.

    This matters if the initial value is mutable:

        - ``piped`` computes immediately and stores a copy of the new result
          at each step. Any updates to the initial value are not seen by
          the pipeline.

        - ``lazy_piped`` just sets up a computation, and performs it when eventually
          piped into ``exitpipe``. The computation always looks up the latest state
          of the initial value.

    Another way to say this is that ``lazy_piped`` looks up the initial value
    dynamically, at get time.
    """
    def __init__(self, x, *, _funcs=None):
        """Set up a lazy pipe and load the initial value x into it.

        The ``_funcs`` parameter is for internal use.
        """
        self._x = x
        self._funcs = force(_funcs or ())
    def __or__(self, f):
        """Pipe the value into f; but just plan to do so, don't perform it yet.

        To run the stored computation, pipe into ``exitpipe``.

        Examples::

            lst = [1]
            def append_succ(lis):
                lis.append(lis[-1] + 1)
                return lis  # important, handed to the next function in the pipe
            p = lazy_piped1(lst) | append_succ | append_succ  # plan a computation
            assert lst == [1]        # nothing done yet
            p | exitpipe              # run the computation
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
            p | exitpipe
            print(fibos)
        """
        f = force1(f)
        if f is exitpipe:  # compute now
            v = self._x
            for g in self._funcs:
                v = maybe_force_args(g, v)
            return v
        # just pass on the reference to the original x.
        cls = self.__class__
        return cls(x=self._x, _funcs=self._funcs + (force1(f),))
    def __repr__(self):  # pragma: no cover
        return f"<lazy_piped1 at 0x{id(self):x}; initial value now {self._x}, functions {self._funcs}>"

@passthrough_lazy_args
def pipe(values0, *bodys):
    """Like pipe1, but with arbitrary number of inputs/outputs at each step.

    The only restriction is that the call and return signatures must match:
    each function must take those positional/named arguments the previous one
    returns. Use a `Values` object to denote multiple-return-values, and/or
    named return values.

    At each step, if the output from a function is a `Values`, it is unpacked
    to the args and kwargs of the next function. Otherwise, we feed the output
    to the next function as a single positional argument.

    At the beginning of the pipe, `values0` is treated the same way; so to
    feed multiple args/kwargs to the first function, use a `Values`.

    If the final return value is a `Values`, and contains only one positional
    return value, we unwrap it. Otherwise the `Values` object is returned as-is.

    If you only need a one-in-one-out chain, ``pipe1`` is faster.

    Examples::

        a, b = pipe(Values(2, 3),
                    lambda x, y: Values(x + 1, 2 * y),
                    lambda x, y: Values(x * 2, y + 1))
        # If a `Values` object has only positional values,
        # it can be unpacked like a tuple. Hence we don't
        # see a `Values` wrapper here.
        assert (a, b) == (6, 7)

        a, b, c = pipe(Values(2, 3),
                       lambda x, y: Values(x + 1, 2 * y, "foo"),
                       lambda x, y, s: Values(x * 2, y + 1, f"got {s}"))
        assert (a, b, c) == (6, 7, "got foo")

        # Can bind arguments of the next step by name, too
        a, b, c = pipe(Values(2, 3),
                       lambda x, y: Values(x + 1, 2 * y, s="foo"),
                       lambda x, y, s: Values(x * 2, y + 1, f"got {s}"))
        assert (a, b, c) == (6, 7, "got foo")

        a, b = pipe(Values(2, 3),
                    lambda x, y: Values(x + 1, 2 * y, "foo"),
                    lambda x, y, s: Values(x * 2, y + 1, f"got {s}"),
                    lambda x, y, s: Values(x + y, s))
        assert (a, b) == (13, "got foo")
    """
    xs = values0
    n = len(bodys)
    for k, update in enumerate(bodys):
        islast = (k == n - 1)
        bindings = {}
        update = force1(update)
        if iscurried(update) and not islast:
            # co-operate with curry: provide a top-level curry context
            # to allow passthrough from a pipelined function to the next
            # (except the last one, since it exits the curry context).
            bindings = {"curry_context": dyn.curry_context + [update]}
        with dyn.let(**bindings):
            if isinstance(xs, Values):
                xs = maybe_force_args(update, *xs.rets, **xs.kwrets)
            else:
                xs = maybe_force_args(update, xs)
    if isinstance(xs, Values):
        return xs if xs.kwrets or len(xs.rets) > 1 else xs[0]
    return xs

@passthrough_lazy_args
def pipec(values0, *bodys):
    """Like pipe, but curry each function before piping.

    Useful with the passthrough in ``curry``. Each function only needs to
    declare as many of the (leftmost) arguments as it needs to access or modify::

        a, b = pipec(Values(1, 2),
                     # extra values passed through by curry, positionals on the right
                     lambda x: x + 1,
                     lambda x, y: Values(x * 2, y + 1))
        assert (a, b) == (4, 3)
    """
    return pipe(values0, *map(curry, bodys))

@passthrough_lazy_args
class piped:
    """Like piped1, but for any number of inputs/outputs at each step.

    The only restriction is that the call and return signatures must match:
    each function must take those positional/named arguments the previous one
    returns. Use a `Values` object to denote multiple-return-values, and/or
    named return values.
    """
    def __init__(self, *xs, **kws):
        """Set up a pipe and load the initial values xs and kws into it.

        The inputs are automatically packed into a `Values`.
        """
        self._xs = Values(*xs, **kws)
    def __or__(self, f):
        """Pipe the values through the function f.

        If the data currently in the pipe is a `Values`, it is unpacked
        to the args and kwargs of `f`. Otherwise, we feed the data to `f`
        as a single positional argument.

        Example::

            f = lambda x, y: Values(2*x, y+1)
            g = lambda x, y: Values(x+1, 2*y)
            x = piped(2, 3) | f | g | exitpipe  # --> Values(5, 8)

        If the final return value is a `Values`, and contains only one positional
        return value, we unwrap it. Otherwise the `Values` object is returned as-is.
        """
        f = force1(f)
        xs = self._xs
        assert isinstance(xs, Values)  # __init__ ensures this
        if f is exitpipe:
            return xs if xs.kwrets or len(xs.rets) > 1 else xs[0]
        cls = self.__class__
        newxs = maybe_force_args(f, *xs.rets, **xs.kwrets)
        if isinstance(newxs, Values):
            return cls(*newxs.rets, **newxs.kwrets)
        return cls(newxs)
    def __repr__(self):  # pragma: no cover
        return f"<piped at 0x{id(self):x}; values {self._xs}>"

@passthrough_lazy_args
class lazy_piped:
    """Like lazy_piped1, but for any number of inputs/outputs at each step.

    The only restriction is that the call and return signatures must match:
    each function must take those positional/named arguments the previous one
    returns. Use a `Values` object to denote multiple-return-values, and/or
    named return values.

    Examples::

        p1 = lazy_piped(2, 3)
        p2 = p1 | (lambda x, y: Values(x + 1, 2 * y, "foo"))
        p3 = p2 | (lambda x, y, s: Values(x * 2, y + 1, f"got {s}"))
        p4 = p3 | (lambda x, y, s: Values(x + y, s))
        # nothing done yet!
        assert (p4 | exitpipe) == Values(13, "got foo")

        # lazy pipe as an unfold
        fibos = []
        def nextfibo(a, b):    # now two arguments
            fibos.append(a)
            return Values(a=b, b=(a + b))  # can return by name too
        p = lazy_piped(1, 1)
        for _ in range(10):
            p = p | nextfibo
        assert p | exitpipe == Values(a=89, b=144)  # final state
        assert fibos == [1, 1, 2, 3, 5, 8, 13, 21, 34, 55]
    """
    def __init__(self, *xs, _funcs=None, **kws):
        """Set up a lazy pipe and load the initial values xs and kws into it.

        The inputs are automatically packed into a `Values`.

        The ``_funcs`` parameter is for internal use.
        """
        self._xs = Values(*xs, **kws)
        self._funcs = force(_funcs or ())
    def __or__(self, f):
        """Pipe the values into f; but just plan to do so, don't perform it yet.

        When f is `exitpipe`, perform the planned computation.

        When the computation is performed, when this `f` is reached, if the data
        currently in the pipe is a `Values`, it is unpacked to the args and kwargs
        of `f`. Otherwise, we feed the data to `f` as a single positional argument.

        If the final return value is a `Values`, and contains only one positional
        return value, we unwrap it. Otherwise the `Values` object is returned as-is.
        """
        f = force1(f)
        if f is exitpipe:  # compute now
            vs = self._xs
            for g in self._funcs:
                if isinstance(vs, Values):
                    vs = g(*vs.rets, **vs.kwrets)
                else:
                    vs = g(vs)
            if isinstance(vs, Values):
                return vs if vs.kwrets or len(vs.rets) > 1 else vs[0]
            else:
                return vs
        # just pass on the references to the original xs.
        cls = self.__class__
        return cls(*self._xs.rets, _funcs=self._funcs + (force1(f),), **self._xs.kwrets)
    def __repr__(self):  # pragma: no cover
        return f"<lazy_piped at 0x{id(self):x}; initial values now {self._xs}, functions {self._funcs}>"

# do(): improved begin() that can name intermediate results and refer to them
DoAssign = namedtuple("DoAssign", "name value")
def assign(**binding):
    """Bind a name to a value inside a do().

    Re-using a previous name overwrites.

    The RHS of an ``assign`` may use ``lambda e: ...`` to access the environment.

    Usage:

        do(...,
           assign(x=42),
           ...)

    **Note**: ``assign(x=42)`` is an abbreviation for ``lambda e: setattr(e, 'x', 42)``.
    (``setattr`` instead of ``e.set`` because the latter only rebinds, and here
    it is allowed to create new names in the environment.)

    Whereas ``setattr(e, ...)`` works from anywhere inside the ``do`` (including
    any nested ``let`` constructs and similar), an ``assign`` works only at
    the top level of the ``do``.
    """
    if len(binding) != 1:
        raise ValueError(f"Expected exactly one binding, got {len(binding)} with values {binding}")
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
            except UnknownArity:  # well, we tried!  # pragma: no cover
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
