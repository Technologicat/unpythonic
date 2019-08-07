# -*- coding: utf-8; -*-
"""Break recursion cycles.

Implemented as a parametric decorator.

Original implementation by Per Vognsen 2012, from:

    https://gist.github.com/pervognsen/8dafe21038f3b513693e

In this version, some variable names have been changed to better correspond to
Matthew Might's original Racket version (calling -> visited, values -> cache).

The name `fix` comes from the *least fixed point* with respect to the
definedness relation, which is related to Haskell's `fix` function.
However, these are not the same function.

Our `fix` breaks recursion cycles in strict functions, whereas in Haskell,
`fix f = ⊥` for any strict `f`, quite simply because that's the least-defined
fixed point for any strict function. Obviously, if `f` is strict, `f(⊥) = ⊥`,
so it's a fixed point. On the other hand, ⊥ is `undefined`, describing a value
about which nothing is known. So it's the least fixed point in this sense.

Haskell's `fix` is also related to the Y combinator; it's essentially recursion
packaged into a function. The `unpythonic` name for the Y combinator idea is
`withself`, allowing a lambda to refer to itself by passing in the self-reference
from the outside.

A simple way to explain Haskell's `fix` is::

    fix f = let x = f x in x

so anywhere the argument is referred to in f's definition, it's replaced by
another application of `f`, recursively. This obviously yields a notation
useful for corecursively defining infinite lazy lists.

For what **our** `fix` does, see the docstring.

Related reading:

    https://www.parsonsmatt.org/2016/10/26/grokking_fix.html
    https://www.vex.net/~trebla/haskell/fix.xhtml
    https://stackoverflow.com/questions/4787421/how-do-i-use-fix-and-how-does-it-work
    https://medium.com/@cdsmithus/fixpoints-in-haskell-294096a9fc10
    https://en.wikibooks.org/wiki/Haskell/Fix_and_recursion
"""

__all__ = ["fix"]

# Just to use typing.NoReturn as a special value at runtime. It has the right semantics.
import typing
from functools import wraps

from unpythonic.fun import identity, const

# - TODO: Add support for kwargs in f.
#
# - TODO: Make this thread-safe. Thread-local "visited" and "cache" should be sufficient.
#
# - TODO: Can we make this call bottom at most once?
#
# - TODO: Figure out how to make this play together with unpythonic's TCO, to
#   bypass Python's call stack depth limit. We probably need a monolithic @fixtco
#   decorator that does both, since these features interact.
#
# - TODO: Pass the function object to bottom instead of the function name. Locating the
#   actual entrypoint in user code may require some trickery due to the decorator wrappers.
#
infinity = float("+inf")
def fix(bottom=typing.NoReturn, n=infinity, unwrap=identity):
    """Break recursion cycles. Parametric decorator.

    This is sometimes useful for recursive pattern-matching definitions. For an
    example, see Matthew Might's article on parsing with Brzozowski's derivatives:

        http://matt.might.net/articles/parsing-with-derivatives/

    Usage::

        from unpythonic import fix, identity

        @fix()
        def f(...):
            ...
        result = f(23, 42)  # start a computation with some args

        @fix(bottom=identity)
        def f(...):
            ...
        result = f(23, 42)

    If no recursion cycle occurs, `f` returns normally. If a cycle occurs,
    the call to `f` is aborted (dynamically, when the cycle is detected), and:

      - In the first example, the special value `typing.NoReturn` is returned.

      - In the latter example, the name "f" and the offending args are returned.

    Notes:

      - `f` must be pure for this to make sense.

      - All args of `f` must be hashable, for technical reasons.

      - The return value of `f` must support comparison with `!=`.

      - The `bottom` parameter (named after the empty type ⊥) specifies the
        final return value to be returned when a recursion cycle is detected
        in a call to `f`.

        The default is the special value `typing.NoReturn`, which represents ⊥
        in Python. If you just want to detect that a cycle occurred, this is
        usually fine.

        When bottom is returned, it means the collected evidence shows that if
        we were to let `f` continue forever, the call would not return.

      - `bottom` can be a callable, in which case the function name and args
        at the point where the cycle was detected are passed to it, and its
        return value becomes the final return value.

        Note it may be called twice; first, to initialize the cache with the
        initial args of `f`, and (if the args at that point are different)
        for a second time when a recursion cycle is detected.

      - `unwrap` can be used e.g. for internally forcing promises, if the
        return type of `f` is a promise. This is needed, because a promise
        cannot be meaningfully inspected.

      - `n` is the maximum number of times recursion is allowed to occur,
        before the algorithm aborts. Default is no limit.

    **CAUTION**: Worded differently, this function solves a small subset of the
    halting problem. This should be hint enough that it will only work for the
    advertised class of special cases - i.e., recursion cycles.

    **CAUTION**: Currently not compatible with TCO. It'll work, but the TCO
    won't take effect, and the call stack will actually blow up faster due to
    bad interaction between `@fix` and `@trampolined`.

    **CAUTION**: Currently not thread-safe.
    """
    if not callable(bottom):
        bottom = const(bottom)
    def decorator(f):
        @wraps(f)
        def f_fix(*args):
            me = (f_fix, args)
            if not fix.visited:
                value, fix.cache[me] = None, bottom(f_fix.__name__, *args)
                count = 0
                while count < n and value != fix.cache[me]:
                    fix.visited.add(me)
                    value, fix.cache[me] = fix.cache[me], unwrap(f(*args))
                    fix.visited.clear()
                    count += 1
                return value
            if me in fix.visited:
                # return fix.cache.get(me, bottom(f_fix.__name__, *args)
                # same effect, except don't compute bottom again if we don't need to.
                return fix.cache[me] if me in fix.cache else bottom(f_fix.__name__, *args)
            fix.visited.add(me)
            value = fix.cache[me] = unwrap(f(*args))
            fix.visited.remove(me)
            return value
        f_fix.entrypoint = f  # just for information
        return f_fix
    return decorator
fix.visited = set()
fix.cache = {}


# --- unit tests ---
# TODO: refactor into a test module

def _logentryexit(f):  # TODO: complete this (kwargs support), move to unpythonic.misc, and make public.
    """Decorator. Print a message when f is entered/exited."""
    @wraps(f)
    def log_f(*args):
        print("-entry-> {}, args = {}".format(f, args))
        ret = f(*args)
        print("<-exit-- {}, args = {}, ret = '{}'".format(f, args, ret))
        return ret
    return log_f

def test():
    def debug(funcname, *args):
        print("bottom called, funcname = {}, args = {}".format(funcname, args))
        # If we return something that depends on args, then fix may have to run
        # the whole chain twice, because at the point where the cycle occurs,
        # the return value of bottom (which has some args from somewhere along
        # the chain) may differ from the initial value of bottom (which has the
        # initial args).
        return typing.NoReturn

    # Simple example of infinite recursion.
    # f(0) -> f(1) -> f(2) -> f(0) -> ...
    @fix(debug)
    @_logentryexit
    def f(k):
        return f((k + 1) % 3)
    print("Starting example f")
    print("Final return value: '{}'".format(f(0)))

    # This example enters the infinite loop at a value of k different from the
    # initial one. Note that debug() gets called twice.
    # g(0) -> g(1) -> g(2) -> g(1) -> ...
    @fix(debug)
    @_logentryexit
    def g(k):
        if k == 0:
            return g(1)
        elif k == 1:
            return g(2)
        return g(1)
    print("Starting example g")
    print("Final return value: '{}'".format(g(0)))

    # Infinite mutual recursion is detected too, at the point where any
    # fix-instrumented function is entered again with args already seen during
    # the chain.
    # a(0) -> b(1) -> a(2) -> b(0) -> a(1) -> b(2) -> a(0) -> ...
    @fix(debug)
    @_logentryexit
    def a(k):
        return b((k + 1) % 3)
    @fix(debug)
    @_logentryexit
    def b(k):
        return a((k + 1) % 3)
    print("Starting example a/b")
    print("Final return value: '{}'".format(a(0)))

    # Another use for this: find the fixed point of cosine.
    # Floats have finite precision. The iteration will converge down to the last bit.
    from math import cos
    def justargs(funcname, *args):
        return identity(*args)  # identity unpacks if just one
    @fix(justargs)
    def cosser(x):
        return cosser(cos(x))
    print("Starting example cosser")
    c = cosser(1)
    print("Final return value: '{}'".format(c))
    assert c == cos(c)

    # General pattern to find a fixed point with this strategy:
    from functools import partial
    @fix(justargs)
    def iterate1_rec(f, x):
        return iterate1_rec(f, f(x))
    cosser2 = partial(iterate1_rec, cos)
    print("Starting example cosser2")
    f, c = cosser2(1)  # f ends up in the return value because it's in the args of iterate1_rec.
    print("Final return value: '{}'".format(c))
    assert c == cos(c)

    # A more pythonic strategy (iteration, no recursion).
    # This also allows setting a tolerance, if equality down to the last bit is not important.
    # from unpythonic import last, within, iterate1
    # c = last(within(iterate1(cos, 1), 0))
    # assert c == cos(c)

if __name__ == '__main__':
    test()
