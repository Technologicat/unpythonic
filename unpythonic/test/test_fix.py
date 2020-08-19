# -*- coding: utf-8; -*-

from ..syntax import macros, test  # noqa: F401
from .fixtures import session, testset

from typing import NoReturn
import threading
from queue import Queue
from math import cos

from ..fix import fix, fixtco
from ..fun import identity
from ..it import chunked
from ..misc import slurp
from ..tco import jump

# def _logentryexit(f):  # TODO: complete this (kwargs support), move to unpythonic.misc, and make public.
#     """Decorator. Print a message when f is entered/exited."""
#     @wraps(f)
#     def log_f(*args, **kwargs):
#         print("-entry-> {}, args = {}, kwargs = {}".format(f, args, kwargs))
#         ret = f(*args, **kwargs)
#         print("<-exit-- {}, args = {}, kwargs = {}, ret = '{}'".format(f, args, kwargs, ret))
#         return ret
#     return log_f
_logentryexit = lambda f: f  # disabled  # noqa: E731

def runtests():
    def debug(funcname, *args, **kwargs):
        # print("bottom called, funcname = {}, args = {}".format(funcname, args))
        # If we return something that depends on args, then fix may have to run
        # the whole chain twice, because at the point where the cycle occurs,
        # the return value of bottom (which has some args from somewhere along
        # the chain) may differ from the initial value of bottom (which has the
        # initial args).
        return NoReturn

    with testset("basic usage"):
        # Simple example of infinite recursion.
        # f(0) -> f(1) -> f(2) -> f(0) -> ...
        @fix(debug)
        @_logentryexit
        def f(k):
            return f((k + 1) % 3)
        test[f(0) is NoReturn]

        # In this version we pass k by name, to test kwargs handling in @fix.
        @fix(debug)
        @_logentryexit
        def f(k):
            return f(k=(k + 1) % 3)
        test[f(k=0) is NoReturn]

        # fix with no args - default no-return return value
        @fix()
        def f(k):
            return f((k + 1) % 3)
        test[f(0) is NoReturn]

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
        test[g(0) is NoReturn]

    # Infinite mutual recursion is detected too, at the point where any
    # fix-instrumented function is entered again with args already seen during
    # the chain.
    with testset("detect infinite mutual recursion"):
        # a(0) -> b(1) -> a(2) -> b(0) -> a(1) -> b(2) -> a(0) -> ...
        @fix(debug)
        @_logentryexit
        def a(k):
            return b((k + 1) % 3)
        @fix(debug)
        @_logentryexit
        def b(k):
            return a((k + 1) % 3)
        test[a(0) is NoReturn]

    # Another use for this: find the fixed point of cosine.
    # Floats have finite precision. The iteration will converge down to the last bit.
    with testset("find fixed point"):
        def justargs(funcname, *args):  # bottom doesn't need to accept kwargs if we don't send it any.
            return identity(*args)  # identity unpacks if just one
        @fix(justargs)
        def cosser(x):
            return cosser(cos(x))
        c = cosser(1)
        test[c == cos(c)]  # 0.7390851332151607

        # General pattern to find a fixed point with this strategy:
        from functools import partial
        @fix(justargs)
        def iterate1_rec(f, x):
            return iterate1_rec(f, f(x))
        cosser2 = partial(iterate1_rec, cos)
        f, c = cosser2(1)  # f ends up in the return value because it's in the args of iterate1_rec.
        test[c == cos(c)]

    with testset("multithreading"):
        def threadtest():
            a_calls = []
            @fix()
            def a(tid, k):
                a_calls.append(tid)
                return b(tid, (k + 1) % 3)
            b_calls = []
            @fix()
            def b(tid, k):
                b_calls.append(tid)
                return a(tid, (k + 1) % 3)

            comm = Queue()
            def worker(q):
                r = a(id(threading.current_thread()), 0)
                q.put(r is NoReturn)

            n = 1000
            threads = [threading.Thread(target=worker, args=(comm,), kwargs={}) for _ in range(n)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()

            # Test that all threads finished, and each thread got the return value NoReturn.
            results = slurp(comm)
            test[len(results) == n]
            test[sum(results) == n]

            # Test that in each thread, both a and b were called exactly 3 times.
            len_ok = 0
            tid_ok = 0
            n_chunks = 0
            for call_data in (a_calls, b_calls):
                for chunk in chunked(3, sorted(call_data)):
                    tpl = tuple(chunk)
                    n_chunks += 1
                    # there should always be a whole length-3 chunk (also during the final iteration).
                    if len(tpl) == 3:
                        len_ok += 1
                    # all thread ids recorded in a given chunk should be from the same thread,
                    # because we sorted them.
                    tid0 = tpl[0]
                    if all(tid == tid0 for tid in tpl):
                        tid_ok += 1
            test[len_ok == n_chunks]
            test[tid_ok == n_chunks]

        threadtest()

    with testset("integration with TCO"):
        @fixtco()  # <-- only change; this enables the trampoline
        def f(k):
            return jump(f, (k + 1) % 5000)  # <-- now `return jump(...)` is available
        test[f(0) is NoReturn]

        # edge case: TCO chain in progress, regular call from it invokes another
        # TCO chain (so we need a stack to handle them correctly)
        @fixtco()
        def g(k):
            if k < 1000:
                return jump(g, k + 1)
            return f(k)
        test[g(0) is NoReturn]

if __name__ == '__main__':
    with session(__file__):
        runtests()
