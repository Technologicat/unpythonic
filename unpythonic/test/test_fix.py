# -*- coding: utf-8; -*-

from typing import NoReturn
# from functools import wraps

from ..fix import fix
from ..fun import identity

# def _logentryexit(f):  # TODO: complete this (kwargs support), move to unpythonic.misc, and make public.
#     """Decorator. Print a message when f is entered/exited."""
#     @wraps(f)
#     def log_f(*args):
#         print("-entry-> {}, args = {}".format(f, args))
#         ret = f(*args)
#         print("<-exit-- {}, args = {}, ret = '{}'".format(f, args, ret))
#         return ret
#     return log_f
_logentryexit = lambda f: f  # disabled  # noqa: E731

def test():
    def debug(funcname, *args):
        # print("bottom called, funcname = {}, args = {}".format(funcname, args))
        # If we return something that depends on args, then fix may have to run
        # the whole chain twice, because at the point where the cycle occurs,
        # the return value of bottom (which has some args from somewhere along
        # the chain) may differ from the initial value of bottom (which has the
        # initial args).
        return NoReturn

    # Simple example of infinite recursion.
    # f(0) -> f(1) -> f(2) -> f(0) -> ...
    @fix(debug)
    @_logentryexit
    def f(k):
        return f((k + 1) % 3)
    assert f(0) is NoReturn

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
    assert g(0) is NoReturn

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
    assert a(0) is NoReturn

    # Another use for this: find the fixed point of cosine.
    # Floats have finite precision. The iteration will converge down to the last bit.
    from math import cos
    def justargs(funcname, *args):
        return identity(*args)  # identity unpacks if just one
    @fix(justargs)
    def cosser(x):
        return cosser(cos(x))
    c = cosser(1)
    assert c == cos(c)  # 0.7390851332151607

    # General pattern to find a fixed point with this strategy:
    from functools import partial
    @fix(justargs)
    def iterate1_rec(f, x):
        return iterate1_rec(f, f(x))
    cosser2 = partial(iterate1_rec, cos)
    f, c = cosser2(1)  # f ends up in the return value because it's in the args of iterate1_rec.
    assert c == cos(c)

if __name__ == '__main__':
    test()
