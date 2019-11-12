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
import threading
from functools import wraps
from operator import itemgetter

from .fun import const, memoize
from .tco import trampolined, _jump
from .env import env
from .regutil import register_decorator

# Thread-local visited and cache.
_L = threading.local()
def _get_threadlocals():
    if not hasattr(_L, "_data"):
        _L._data = env(visited=set())
    return _L._data

# - TODO: Figure out how to make this play together with unpythonic's TCO, to
#   bypass Python's call stack depth limit. We probably need a monolithic @fixtco
#   decorator that does both, since these features interact.
#
# - TODO: Pass the function object to bottom instead of the function name. Locating the
#   actual entrypoint in user code may require some trickery due to the decorator wrappers.
#
@register_decorator(priority=40, istco=True)
def fix(bottom=typing.NoReturn, memo=True):
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

    **CAUTION**: Worded differently, this function solves a small subset of the
    halting problem. This should be hint enough that it will only work for the
    advertised class of special cases - i.e., recursion cycles.

    **CAUTION**: Currently not compatible with TCO. It'll work, but the TCO
    won't take effect, and the call stack will actually blow up faster due to
    bad interaction between `@fix` and `@trampolined`.
    """
    # Being a class, typing.NoReturn is technically callable (to construct an
    # instance), but because it's an abstract class, the call raises TypeError.
    # We want to use the class itself as a data value, so we special-case it.
    if bottom is typing.NoReturn or not callable(bottom):
        bottom = const(bottom)
    def decorator(f):
        @wraps(f)
        def f_fix(*args, **kwargs):
            e = _get_threadlocals()
            me = (f_fix, args, tuple(sorted(kwargs.items(), key=itemgetter(0))))
            mrproper = not e.visited  # on outermost call, scrub visited clean at exit
            if me not in e.visited:
                try:
                    e.visited.add(me)
                    e.target = f  # TCO jump target
                    e.toclean = set()
                    return f_memo(*args, **kwargs)
                finally:
                    e.visited.clear() if mrproper else e.visited.remove(me)
            else:  # cycle detected
                return bottom(f_fix.__name__, *args, **kwargs)
        f_fix._entrypoint = f  # for information and for co-operation with TCO

        # TCO trampoline interception.
        #
        # This must be handled separately from normal nested calls, since the
        # trampoline takes control, and the next time we see `f` is when the
        # TCO chain has ended (if it ever does).
        #
        # TODO: Call stack depth problems when the client doesn't actually use TCO; we're inserting too many helper layers
        # TODO: per call. We need options to control that (beside memoization, make TCO support switchable, and provide
        # TODO: two public decorators, @fix and @tcofix).
        def spy(*args, **kwargs):
            e = _get_threadlocals()
            v = e.target(*args, **kwargs)
            # We must intercept when coming out of `f`, because when going in,
            # `me` is already in visited. So instead of `me`, we inspect `you`,
            # i.e. the target we're going to jump to next.
            if isinstance(v, _jump):
                you = (v.target, v.args, tuple(sorted(v.kwargs.items(), key=itemgetter(0))))
                if you in e.visited:  # cycle detected
                    v._claimed = True  # mark the jump as handled, as we stop it from reaching the trampoline.
                    return bottom(v.target.__name__, *args, **kwargs)
                # Just like the f_fix loop adds f to visited before calling it,
                # add the target before we jump into it.
                e.visited.add(you)
                e.toclean.add(you)
                e.target, v.target = v.target, spy  # make spy intercept the next TCO jump target
            else:  # TCO chain ended
                for target in e.toclean:  # clean up any targets added during the TCO chain
                    e.visited.remove(target)
                e.toclean.clear()
            return v
        f_tramp = trampolined(spy)  # spies always get the coolest gadgets.
        f_memo = memoize(f_tramp) if memo else f_tramp

        return f_fix
    return decorator


# Without TCO this is as simple as:
# def fix(bottom=typing.NoReturn, memo=True):
#     if bottom is typing.NoReturn or not callable(bottom):
#         bottom = const(bottom)
#     def decorator(f):
#         f_memo = memoize(f) if memo else f
#         @wraps(f)
#         def f_fix(*args, **kwargs):
#             e = _get_threadlocals()
#             me = (f_fix, args, tuple(sorted(kwargs.items(), key=itemgetter(0))))
#             mrproper = not e.visited  # on outermost call, scrub visited clean at exit
#             if not e.visited or me not in e.visited:
#                 try:
#                     e.visited.add(me)
#                     return f_memo(*args, **kwargs)
#                 finally:
#                     e.visited.clear() if mrproper else e.visited.remove(me)
#             else:  # cycle detected
#                 return bottom(f_fix.__name__, *args, **kwargs)
#         f_fix.entrypoint = f  # just for information
#         return f_fix
#     return decorator
