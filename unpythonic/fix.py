# -*- coding: utf-8; -*-
"""Break infinite recursion cycles in pure functions.

The name `fix` comes from the *least fixed point* with respect to the
definedness relation, which is related to Haskell's `fix` function.

However, this `fix` is not that function.

Our `fix` breaks recursion cycles in strict functions - thus causing some
non-terminating strict functions to return. (Here *strict* means that the
arguments are evaluated eagerly.)

**Haskell's fix?**

In Haskell, the function named `fix` computes the *least fixed point* with
respect to the definedness ordering. For any strict `f`, we have `fix f = ⊥`.
Why? If `f` is strict, `f(⊥) = ⊥` (does not terminate), so `⊥` is a fixed
point. On the other hand, `⊥` means also `undefined`, describing a value about
which nothing is known. So it is the least fixed point in this sense.

Haskell's `fix` is related to the Y combinator; it is essentially the idea of
recursion packaged into a higher-order function. The name in `unpythonic` for
the Y combinator idea is `withself`, allowing a lambda to refer to itself by
passing in the self-reference from the outside.

A simple way to explain Haskell's `fix` is::

    fix f = let x = f x in x

so anywhere the argument is referred to in f's definition, it's replaced by
another application of `f`, recursively. This obviously yields a notation
useful for corecursively defining infinite lazy lists.

Related reading:

    https://www.parsonsmatt.org/2016/10/26/grokking_fix.html
    https://www.vex.net/~trebla/haskell/fix.xhtml
    https://stackoverflow.com/questions/4787421/how-do-i-use-fix-and-how-does-it-work
    https://medium.com/@cdsmithus/fixpoints-in-haskell-294096a9fc10
    https://en.wikibooks.org/wiki/Haskell/Fix_and_recursion

**Historical note**

The idea comes from Matthew Might's article on parsing with (Brzozowski's)
derivatives, where it was a utility implemented in Racket as the `define/fix`
form. It was originally ported to Python by Per Vognsen (linked from the article).
Our version is a redesign with kwargs support, thread safety, and TCO support.

    http://matt.might.net/articles/parsing-with-derivatives/
    https://gist.github.com/pervognsen/8dafe21038f3b513693e
"""

__all__ = ["fix", "fixtco"]

import typing  # we use typing.NoReturn as a special value at runtime
import threading
from functools import wraps

from .fun import const, memoize
from .tco import trampolined, _jump
from .env import env
from .arity import resolve_bindings, tuplify_bindings
from .regutil import register_decorator

_L = threading.local()
def _get_threadlocals():
    if not hasattr(_L, "_data"):
        # TCO info forms a stack to support nested TCO chains (during a
        # TCO chain, regular call, which then calls another TCO chain).
        _L._data = env(visited=set(), tco_stack=[])
    return _L._data

@register_decorator(priority=40, istco=False)  # same priority as @fixtco
def fix(bottom=typing.NoReturn, memo=True):
    """Break recursion cycles. Parametric decorator.

    This is sometimes useful for recursive pattern-matching definitions. For an
    example, see Matthew Might's article on parsing with Brzozowski's derivatives:

        http://matt.might.net/articles/parsing-with-derivatives/

    Usage::

        from unpythonic import fix, identity

        @fix()  # <-- parentheses important!
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

      - `bottom` can be any non-callable value, in which case it is simply
        returned upon detection of a cycle.

      - `bottom` can be a callable, in which case the function name and args
        at the point where the cycle was detected are passed to it, and its
        return value becomes the final return value.

      - The `memo` flag controls whether to memoize also intermediate results.
        It adds some additional function call layers between function entries
        from recursive calls; if that is a problem (due to causing Python's
        call stack to blow up faster), use `memo=False`. You can still memoize
        the final result if you want; just put `@memoize` on the outside.

        (This is also currently less than perfect; the internal memo lives in
        the closure of the decorator instance, so in the case of mutually
        recursive fix-instrumented functions, each entrypoint memoizes its
        results separately.)

    **NOTE**: If you need `fix` for code that uses TCO, use `fixtco` instead.

    The implementations of recursion cycle breaking and TCO must interact in a
    very particular way to work properly; this is done by `fixtco`.

    **CAUTION**: Worded differently, this function solves a small subset of the
    halting problem. This should be hint enough that it will only work for the
    advertised class of special cases - i.e., a specific kind of recursion cycles.
    """
    return _fix(bottom, memo, tco=False)

@register_decorator(priority=40, istco=True)  # same priority as @trampolined
def fixtco(bottom=typing.NoReturn, memo=True):
    """TCO-enabled version of @fix.

    On top of performing the duties of `fix`, this parametric decorator applies
    TCO, so you can `return jump(f, ...)` in the client code, and infinitely
    recursive tail call chains will be broken too (under the same assumptions
    and semantics as in `fix`).

    Example::

        @fixtco()
        def f(k):
            return jump(f, (k + 1) % 5000)
        assert f(0) is NoReturn

    **NOTE**: `fix` and `fixtco` are separate API functions due to the
    decorator registry (used by macros in `unpythonic.syntax`) requiring to
    declare a decorator as either enabling TCO or not - there is no "sometimes"
    option.

    The TCO switch itself exists because TCO support adds additional function
    call layers between regular function entries from normal recursive calls.
    For functions that do not use TCO, having those additional layers is bad,
    because that causes Python's call stack to blow up faster.

    Also, having a switch makes the TCO support pay-as-you-go; there's no need
    for that additional machinery to slow things down when TCO support is not
    required.
    """
    return _fix(bottom, memo, tco=True)

# Without TCO support the idea is as simple as:
# def fix(bottom=typing.NoReturn, memo=True):
#     if bottom is typing.NoReturn or not callable(bottom):
#         bottom = const(bottom)
#     def decorator(f):
#         f_memo = memoize(f) if memo else f
#         @wraps(f)
#         def f_fix(*args, **kwargs):
#             e = _get_threadlocals()
#             me = (f_fix, tuplify_bindings(resolve_bindings(f, *args, **kwargs)))
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

# - TODO: Pass the function object to bottom instead of the function name. Locating the
#   actual entrypoint in user code may require some trickery due to the decorator wrappers.
#   OTOH, maybe that's not needed, since by definition, a decorator overwrites the name.
#   So returning the decorated version would be just fine.
#
def _fix(bottom=typing.NoReturn, memo=True, *, tco):
    # Being a class, typing.NoReturn is technically callable (to construct an
    # instance), but because it's an abstract class, the call raises TypeError.
    # We want to use the class itself as a data value, so we special-case it.
    if bottom is typing.NoReturn or not callable(bottom):
        bottom = const(bottom)
    def decorator(f):
        @wraps(f)
        def f_fix(*args, **kwargs):
            e = _get_threadlocals()
            me = (f_fix, tuplify_bindings(resolve_bindings(f, *args, **kwargs)))
            mrproper = not e.visited  # on outermost call, scrub visited clean at exit
            if me not in e.visited:
                try:
                    e.visited.add(me)
                    e.tco_stack.append(env(target=f, cleanup=set()))  # harmless if no TCO
                    return f_memo(*args, **kwargs)
                finally:
                    e.tco_stack.pop()
                    e.visited.clear() if mrproper else e.visited.remove(me)
            else:  # cycle detected
                return bottom(f_fix.__name__, *args, **kwargs)
        f_fix._entrypoint = f  # for information and for co-operation with TCO

        # TCO trampoline interception.
        #
        # The first call occurs normally, by setting up the TCO target on
        # tco_stack and calling `spy`. For TCO-chained calls, `spy` then
        # re-instates itself each time to stay in the loop (both figuratively
        # and literally).
        #
        # TCO call chains must be handled separately from normal recursive
        # calls, because when we call a trampolined `f`, the trampoline takes
        # control. The next time we get control back is when the TCO chain has
        # ended, if it ever does.
        #
        # To be able to inspect the jump targets during the TCO chain, we
        # intercept each call when execution returns from `f`, before it hits
        # the surrounding trampoline.
        #
        # We intercept when *coming out* of `f`, because when *going in*, `me`
        # is already in `visited` - so it being there at that point doesn't yet
        # indicate an infinite loop. Instead of `me`, we inspect `you`, i.e.
        # the target we're going to jump to next. (There's a Soviet Russia joke
        # there somewhere.)
        #
        def spy(*args, **kwargs):
            e = _get_threadlocals()
            t = e.tco_stack[-1]
            v = t.target(*args, **kwargs)
            if isinstance(v, _jump):
                you = (v.target, tuplify_bindings(resolve_bindings(v.target, *v.args, **v.kwargs)))
                if you in e.visited:  # cycle detected
                    for target in t.cleanup:
                        e.visited.remove(target)
                    v._claimed = True  # we have handled the jump, by terminating the infinite cycle.
                    return bottom(v.target.__name__, *args, **kwargs)
                # Just like the f_fix loop adds `f` to `visited` before calling it,
                # we add the target to `visited` before we let the trampoline jump
                # into it.
                e.visited.add(you)
                t.cleanup.add(you)
                t.target, v.target = v.target, spy  # re-instate the spy
            else:  # TCO chain ended
                for target in t.cleanup:
                    e.visited.remove(target)
            return v

        # Putting the memoizer on the outside, TCO call chains do not get
        # memoization of intermediate results, but maybe we don't need that.
        #
        # `spy` has side effects (on `t` and `e`), so I don't want to think about
        # how to memoize it correctly.
        f_tramp = trampolined(spy) if tco else f  # spies always get the coolest gadgets (if TCO enabled).
        f_memo = memoize(f_tramp) if memo else f_tramp
        return f_fix
    return decorator
