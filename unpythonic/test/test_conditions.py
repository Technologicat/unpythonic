# -*- coding: utf-8 -*-

from ..conditions import signal, find_restart, invoke_restart, invoker, use_value, \
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
    # basic usage
    def basic_usage():
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
    basic_usage()

    # It is also valid to place the `with restarts` in the error branch only.
    # In fact, it can go at any level where you want a restartable block.
    #
    # ("Restartable", in the context of the condition system, means that
    #  instead of the usual result of the block, it may have as its result the
    #  return value of a restart, if a signal/handler/restart combination ran.)
    def basic_usage2():
        class OddNumberError(Condition):
            def __init__(self, x):
                self.x = x
        def lowlevel():
            out = []
            for k in range(10):
                if k % 2 == 1:
                    with restarts(use_value=(lambda x: x)) as result:
                        error(OddNumberError(k))
                    out.append(unbox(result))
                else:
                    out.append(k)
            return out
        def highlevel():
            with handlers((OddNumberError, lambda c: invoke_restart("use_value", 42))):
                assert lowlevel() == [0, 42, 2, 42, 4, 42, 6, 42, 8, 42]
        highlevel()
    basic_usage2()

    # More elaborate error handling scenarios can be constructed by defining
    # restarts at multiple levels, as appropriate.
    #
    # The details of *how to recover* from an error - i.e. the restart
    # definitions - live at the level that is semantically appropriate for each
    # specific recovery strategy. The high-level code gets to *choose which
    # strategy to use* when a particular condition type is signaled.
    #
    # In the next examples, the code resumes execution either after the
    # lowlevel `with restarts` block, or after the midlevel `with restarts`
    # block, depending on the handler assigned for the `JustTesting` signal.
    #
    # Here we show only how to organize code to make this happen. For a
    # possible practical use, see Seibel's book for a detailed example
    # concerning a log file parser.
    #
    # For teaching purposes, as the return value, we construct a string
    # describing the execution path that was taken.
    def threelevel():
        # The low and mid-level parts are shared between the use cases.
        class TellMeHowToRecover(Condition):
            pass

        def lowlevel():
            with restarts(resume_low=(lambda x: x)) as result:
                signal(TellMeHowToRecover())
                result << "low level ran to completion"  # value for normal exit from the `with restarts` block
            return unbox(result) + " > normal exit from low level"

        def midlevel():
            with restarts(resume_mid=(lambda x: x)) as result:
                result << lowlevel()
            return unbox(result) + " > normal exit from mid level"

        # Trivial use case where we want to just ignore the condition.
        # (An uncaught signal() is just a no-op; see warn(), error(), cerror() for other standard options.)
        def highlevel1():
            assert midlevel() == "low level ran to completion > normal exit from low level > normal exit from mid level"
        highlevel1()

        # Use case where we want to resume at the low level (in a real-world application, repairing the error).
        # Note we need new code only at the high level; the mid and low levels remain as-is.
        def highlevel2():
            with handlers((TellMeHowToRecover, lambda c: invoke_restart("resume_low", "resumed at low level"))):
                assert midlevel() == "resumed at low level > normal exit from low level > normal exit from mid level"
        highlevel2()

        # Use case where we want to resume at the mid level (in a real-world application, skipping the failed part).
        def highlevel3():
            with handlers((TellMeHowToRecover, lambda c: invoke_restart("resume_mid", "resumed at mid level"))):
                assert midlevel() == "resumed at mid level > normal exit from mid level"
        highlevel3()
    threelevel()

    class JustTesting(Condition):
        pass

    # Handler clauses can also take a tuple of types (instead of a single type).
    def test_multiple_signal_types():
        # For testing, create a handler that just sends the condition instance to `use_value`,
        # so we can see the handler actually catches both intended signal types.
        with handlers(((JustTesting, RuntimeError), lambda c: invoke_restart("use_value", c))):
            # no "result << some_normal_exit_value", so here result is None if the signal is not handled.
            with restarts(use_value=(lambda x: x)) as result:
                signal(JustTesting())
            assert isinstance(unbox(result), JustTesting)

            with restarts(use_value=(lambda x: x)) as result:
                signal(RuntimeError())
            assert isinstance(unbox(result), RuntimeError)
    test_multiple_signal_types()

    def test_invoker():
        # invoker(restart_name) creates a handler callable that just invokes
        # the given restart (passing through args and kwargs to it, if any are given).
        with handlers((JustTesting, invoker("hello"))):
            with restarts(hello=(lambda: "hello")) as result:
                warn(JustTesting())
                result << 21
            assert unbox(result) == "hello"
    test_invoker()

    def test_usevalue():
        # The creation of a `use_value` handler:
        with handlers((JustTesting, (lambda c: invoke_restart("use_value", 42)))):
            with restarts(use_value=(lambda x: x)) as result:
                signal(JustTesting())
                result << 21
            assert unbox(result) == 42

        # can be shortened using `invoker` (if it doesn't need data from the
        # condition instance, `c` in the above example):
        with handlers((JustTesting, invoker("use_value", 42))):
            with restarts(use_value=(lambda x: x)) as result:
                signal(JustTesting())
                result << 21
            assert unbox(result) == 42

        # and further, using the predefined `use_value` handler factory that
        # specifically creates a handler to invoke `use_value`:
        with handlers((JustTesting, use_value(42))):
            with restarts(use_value=(lambda x: x)) as result:
                signal(JustTesting())
                result << 21
            assert unbox(result) == 42
    test_usevalue()

    def inspection():
        with handlers((JustTesting, invoker("hello")),
                      (RuntimeError, (lambda c: invoke_restart("use_value", 42)))):
            with restarts(hello=(lambda: "hello"),
                          use_value=(lambda x: x)):
                assert [name for name, _callable in available_restarts()] == ["hello", "use_value"]
                assert [t for t, _callable in available_handlers()] == [JustTesting, RuntimeError]
    inspection()

    def alternate_syntax():
        # normal usage
        with handlers((JustTesting, (lambda c: invoke_restart("use_value", 42)))):
            # The decorator "with_restarts" and "def result()" pair can be used
            # instead of "with restarts(...) as result":
            @with_restarts(use_value=(lambda x: x))
            def result():
                error(JustTesting())
                return 21
            assert result == 42

            # hifi usage
            with_usevalue = with_restarts(use_value=(lambda x: x))
            # Now we can, at any time later, call any thunk in the context of the
            # restarts that were given as arguments to `with_restarts`:
            def dostuff():
                error(JustTesting())
                return 21
            result = with_usevalue(dostuff)
            assert result == 42
    alternate_syntax()

    def error_protocol():
        with handlers((RuntimeError, (lambda c: invoke_restart("use_value", 42)))):
            with restarts(use_value=(lambda x: x)) as result:
                error(RuntimeError("foo"))
                result << 21
            assert unbox(result) == 42
    error_protocol()

    def warn_protocol():
        with handlers():
            with restarts() as result:
                print("Testing warn() - this should print a warning:")
                warn(JustTesting("unhandled warn() prints a warning, but allows execution to continue"))
                result << 21
            assert unbox(result) == 21

        with handlers((JustTesting, muffle)):  # canonical way to muffle a warning
            with restarts() as result:
                warn(JustTesting("unhandled warn() does not print a warning when it is muffled"))
                result << 21
            assert unbox(result) == 21

        with handlers((JustTesting, (lambda c: invoke_restart("use_value", 42)))):
            with restarts(use_value=(lambda x: x)) as result:
                warn(JustTesting("handled warn() does not print a warning"))
                result << 21  # not reached, because the restart takes over
            assert unbox(result) == 42
    warn_protocol()

    # find_restart can be used to look for a restart before committing to
    # actually invoking it.
    def finding():
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
    finding()

    def errorcases():
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
    errorcases()

    # name shadowing: dynamically the most recent binding of the same restart name wins
    class HelpMe(Condition):
        def __init__(self, value):
            self.value = value
    def name_shadowing():
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
    name_shadowing()

    # cancel-and-delegate
    def cancel_and_delegate():
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
    cancel_and_delegate()

    # Multithreading. Threads behave independently.
    def multithreading():
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
    multithreading()

    print("All tests PASSED")

if __name__ == '__main__':
    test()
