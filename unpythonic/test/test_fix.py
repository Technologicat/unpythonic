# -*- coding: utf-8; -*-

from typing import NoReturn
from functools import wraps
import threading
from queue import Queue, Empty

from ..fix import fix
from ..fun import identity
from ..it import chunked

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

def test():
    def debug(funcname, *args, **kwargs):
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

    # kwargs test
    @fix(debug)
    @_logentryexit
    def f(k):
        # In this version we pass k by name, to test kwargs handling in @fix.
        #
        # TODO: #26: if we instead pass k positionally in the call here, the
        # recursion has to run for one extra time before the cycle is detected.
        # This is because initially (when called from the assert statement
        # below) we have args=(), kwargs={k: 0}, whereas a positional call
        # supplies arguments in the form args=(0,), kwargs={}. So the first set
        # of arguments that is part of a cycle then occurs when args=(1,),
        # kwargs={}. But now that we pass by name everywhere, we find the cycle
        # already when we arrive at args=(), kwargs={k: 0} for the second time.
        #
        # At some point, we need a better way to uniquely identify a set of arguments.
        # This also affects at least @memoize and @gmemoize (grep unpythonic for "kwargs.items").
        #
        # This gotcha is mentioned in the documentation of @wrapt:
        # https://wrapt.readthedocs.io/en/latest/decorators.html#processing-function-arguments
        # (See the paragraphs beginning "If needing to modify certain arguments..." and
        # "You should not simply attempt to extract positional arguments...")
        return f(k=(k + 1) % 3)
    assert f(k=0) is NoReturn

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
    def justargs(funcname, *args):  # bottom doesn't need to accept kwargs if we don't send it any.
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

    # fix with no args - default no-return return value
    @fix()
    def f(k):
        return f((k + 1) % 3)
    assert f(0) is NoReturn

    # Thread-safety test
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
        # Slurp the queue into a list.
        results = []
        try:
            while True:
                results.append(comm.get(block=False))
        except Empty:
            pass
        assert len(results) == n
        assert sum(results) == n

        # Test that in each thread, both a and b were called exactly 3 times.
        for call_data in (a_calls, b_calls):
            for chunk in chunked(3, sorted(call_data)):
                tpl = tuple(chunk)
                # there should always be a whole length-3 chunk (also during the final iteration).
                assert len(tpl) == 3
                # all thread ids recorded in a given chunk should be from the same thread,
                # because we sorted them.
                tid0 = tpl[0]
                assert all(tid == tid0 for tid in tpl)

    threadtest()

    print("All tests PASSED")

if __name__ == '__main__':
    test()
