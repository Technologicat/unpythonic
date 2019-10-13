# -*- coding: utf-8 -*-

from ..conditions import signal, find_restart, invoke_restart, invoker, \
    restarts, with_restarts, handlers, \
    available_restarts, available_handlers, \
    error, cerror, proceed, \
    warn, muffle, \
    Condition, ControlError
from ..misc import raisef, slurp
from ..collections import box, unbox

import threading
from queue import Queue

def test():
    # TODO: three-level example (both low-level and mid-level restarts available, decision made at high level)
    # TODO: test a common handler for several condition types (using a tuple of types, like in `except`)
    # TODO: test coverage (see unused imports at top)

    # basic usage
    class OddNumberError(Condition):
        def __init__(self, x):
            self.x = x

    # Low-level logic - define here what actions are available when
    # stuff goes wrong. When the block aborts due to a signaled
    # condition, the return value of the restart chosen (by a handler
    # defined in higher-level code) becomes the result of the block.
    def lowlevel():
        _drop = object()  # gensym/nonce
        out = []
        for k in range(10):
            with restarts(use_value=(lambda x: x),
                          double=(lambda x: 2 * x),
                          drop=(lambda x: _drop),
                          bail=(lambda x: raisef(ValueError, x))) as result:
                # Let's pretend we only want to deal with even numbers.
                # Realistic errors would be something like nonexistent file, disk full, network down, ...
                if k % 2 == 1:
                    cerror(OddNumberError(k))
                # This is reached when no condition is signaled.
                # `result` is a box, send k into it.
                result << k
            # The result is boxed, because the `with` must already bind the
            # name `result`, but the value only becomes available later (and
            # can come either from an explicit `result << ...`, or as the
            # return value from a restart).
            r = unbox(result)
            if r is not _drop:
                out.append(r)
        return out

    # High-level logic. Choose here which action the low-level logic should take
    # for each named signal. Here we only have one signal, named "odd_number".
    def highlevel():
        with handlers((OddNumberError, lambda c: invoke_restart("use_value", c.x))):
            assert lowlevel() == list(range(10))

        with handlers((OddNumberError, lambda c: invoke_restart("double", c.x))):
            assert lowlevel() == [0, 2 * 1, 2, 2 * 3, 4, 2 * 5, 6, 2 * 7, 8, 2 * 9]

        with handlers((OddNumberError, lambda c: invoke_restart("drop", c.x))):
            assert lowlevel() == [0, 2, 4, 6, 8]

        try:
            with handlers((OddNumberError, lambda c: invoke_restart("bail", c.x))):
                lowlevel()
        except ValueError as err:
            assert str(err) == "1"

        # When using error() or cerror() to signal, not handling the condition
        # is a fatal error (like an uncaught exception). The `error` function
        # actually **raises** `ControlError` (note raise, not signal) on an
        # unhandled condition.
        try:
            lowlevel()
        except ControlError:
            pass
        else:
            assert False, "error() should raise on unhandled condition"

        # When using cerror() - short for "continuable error" - it automatically
        # makes available a restart named "proceed" that takes no arguments, which
        # vetoes the error.
        #
        # When the "proceed" restart is invoked, it causes the `cerror()` call in
        # the low-level code to return normally. So execution resumes from where it
        # left off, never mind that a condition occurred.
        with handlers((OddNumberError, proceed)):
            assert lowlevel() == list(range(10))
    highlevel()

    # find_restart can be used to look for a restart before committing to
    # actually invoking it.
    class JustACondition(Condition):
        pass
    class NoItDidntExist(Exception):
        pass
    def invoke_if_exists(restart_name):
        r = find_restart(restart_name)
        if r:
            invoke_restart(r)
        # just a convenient way to tell the test code that it wasn't found.
        raise NoItDidntExist()
    # The condition instance parameter for a hanlder is optional - not needed
    # if you don't need data from the instance.
    with handlers((JustACondition, lambda: invoke_if_exists("myrestart"))):
        # Let's set up "myrestart".
        with restarts(myrestart=(lambda: 42)) as result:
            signal(JustACondition())
            result << 21
        assert unbox(result) == 42  # should be the return value of the restart.

        # Now there is no "myrestart" in scope.
        try:
            signal(JustACondition())
        except NoItDidntExist:
            pass
        else:
            assert False, "find_restart should have not found a nonexistent restart"

    # The signal() low-level function does not require the condition to be handled.
    # If unhandled, signal() just returns normally.
    try:
        signal(RuntimeError("woo"))  # actually any exception is ok, it doesn't have to be a Condition...
    except Exception as err:
        assert False, str(err)

    # error: invoke_restart outside the dynamic extent of any `with restarts`
    try:
        invoke_restart("woo")
    except ControlError:
        pass
    else:
        assert False, "should not be able to invoke_restart when no restarts in scope"

    # error: invoke_restart of undefined restart
    try:
        with restarts(foo=(lambda x: x)):
            invoke_restart("bar")
    except ControlError:
        pass
    else:
        assert False, "should not be able to invoke_restart a nonexistent restart"

    # name shadowing: dynamically the most recent binding of the same restart name wins
    class HelpMe(Condition):
        def __init__(self, value):
            self.value = value
    def lowlevel2():
        with restarts(r=(lambda x: x)) as a:
            signal(HelpMe(21))
            a << False
        with restarts(r=(lambda x: x)):
            # here this is lexically nested, but could be in another function as well.
            with restarts(r=(lambda x: 2 * x)) as b:
                signal(HelpMe(21))
                b << False
        return a, b
    with handlers((HelpMe, lambda c: invoke_restart("r", c.value))):
        assert lowlevel2() == (21, 42)

    # cancel-and-delegate
    def lowlevel3():
        with restarts(use_value=(lambda x: x)) as a:
            signal(HelpMe(42))
            a << False
        return unbox(a)

    # If an inner handler returns normally, the next outer handler (if any) for
    # the same condition takes over. Note any side effects of the inner handler
    # remain in effect.
    inner_handler_ran = box(False)  # use a box so we can rebind the value from inside a lambda
    outer_handler_ran = box(False)
    with handlers((HelpMe, lambda c: [outer_handler_ran << True,
                                      invoke_restart("use_value", c.value)])):
        with handlers((HelpMe, lambda: [inner_handler_ran << True,
                                        None])):  # return normally from handler to cancel-and-delegate
            assert lowlevel3() == 42
            assert unbox(inner_handler_ran) is True
            assert unbox(outer_handler_ran) is True

    # If the inner handler invokes a restart, the outer handler doesn't run.
    inner_handler_ran = box(False)
    outer_handler_ran = box(False)
    with handlers((HelpMe, lambda c: [outer_handler_ran << True,
                                      invoke_restart("use_value", c.value)])):
        with handlers((HelpMe, lambda c: [inner_handler_ran << True,
                                          invoke_restart("use_value", c.value)])):
            assert lowlevel3() == 42
            assert unbox(inner_handler_ran) is True
            assert unbox(outer_handler_ran) is False

    # Multithreading. Threads behave independently.
    comm = Queue()
    def lowlevel4(tag):
        with restarts(use_value=(lambda x: x)) as result:
            signal(HelpMe((tag, 42)))
            result << (tag, 21)  # if the signal is not handled, the box will hold (tag, 21)
        return unbox(result)
    def worker(comm, tid):
        with handlers((HelpMe, lambda c: invoke_restart("use_value", c.value))):
            comm.put(lowlevel4(tid))
    n = 1000
    threads = [threading.Thread(target=worker, args=(comm, tid), kwargs={}) for tid in range(n)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    results = slurp(comm)
    assert len(results) == n
    assert all(x == 42 for tag, x in results)
    assert tuple(sorted(tag for tag, x in results)) == tuple(range(n))

    print("All tests PASSED")

if __name__ == '__main__':
    test()
