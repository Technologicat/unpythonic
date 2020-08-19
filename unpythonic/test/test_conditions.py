# -*- coding: utf-8 -*-

# **CAUTION**: To test the condition system, using a test framework that uses
# that condition system (`unpythonic.test.fixtures`), leads to circular logic.
# In my defense, the different parts of `unpythonic` have co-evolved, so what
# we have here is a Hartree-Fock equilibrium.
#
# If you don't trust this, see commit d87019e or earlier for a version that
# tests the condition system (up to 0.14.2.1) using plain asserts.
#
# The really problematic part in a monolithic language extension like
# `unpythonic` is to write tests that test the testing framework. Currently we
# don't do that. The test framework is considered to change at most slowly, so
# for that, manual testing is sufficient (see commented-out example session in
# `unpythonic.syntax.test.test_testutil`).

from ..syntax import macros, test, test_raises, test_signals, fail  # noqa: F401
from .fixtures import session, testset, catch_signals, returns_normally

from ..conditions import (signal, find_restart, invoke, invoker, use_value,
                          restarts, with_restarts, handlers,
                          available_restarts, available_handlers,
                          error, cerror, proceed,
                          warn, muffle,
                          ControlError)
from ..misc import raisef, slurp
from ..collections import box, unbox
from ..it import subset

import threading
from queue import Queue

def runtests():
    with testset("basic usage"):
        def basic_usage():
            class OddNumberError(Exception):
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
                # When using error() or cerror() to signal, not handling the condition
                # is a fatal error (like an uncaught exception). The `error` function
                # actually **raises** `ControlError` (note raise, not signal) on an
                # unhandled condition.
                #
                # Testing note: by default, `test[]` and its sisters implicitly insert a signal handler
                # that catches everything, making the `OddNumberError` signal no longer unhandled -
                # but (in the testing framework's opinion) still very much unexpected.
                #
                # So to avoid spurious "unexpected signal" errors, we use `with catch_signals(False)`
                # to tell the testing framework that any uncaught signals within the dynamic extent
                # of the "with" block are none of its business. This way we can test that the condition
                # system raises on uncaught `cerror` signals.
                with catch_signals(False):
                    test_raises[ControlError, lowlevel()]

                # When using cerror() - short for "correctable error" - it automatically
                # makes available a restart named "proceed" that takes no arguments, which
                # vetoes the error.
                #
                # When the "proceed" restart is invoked, it causes the `cerror()` call in
                # the low-level code to return normally. So execution resumes from where it
                # left off, never mind that a condition occurred.
                with test("basic usage proceed"):  # barrier against stray exceptions/signals
                    with handlers((OddNumberError, proceed)):
                        # We would like to:
                        #     `test[lowlevel() == list(range(10))]`
                        #
                        # But we need to catch the signal in the above
                        # `with handlers`, but the handler implicitly installed
                        # by `test[]` becomes the most recently installed
                        # (dynamically innermost) handler when the expression
                        # `test[lowlevel() == list(range(10))]` runs.
                        #
                        # So it catches the signal first, and reports it
                        # as unexpected, erroring the test, and thus
                        # preventing the signal from ever reaching our
                        # handler.
                        #
                        # We can either `with catch_signals(False):`
                        # (but that solution obviously fails to report
                        # any stray signals of other types), or `test[]`
                        # just an expression that shouldn't signal.
                        result = lowlevel()
                        test[result == list(range(10))]

                # The restart name "use_value" is commonly used for the use case "resume with this value",
                # so the library has a eponymous function to invoke it.
                with test("basic usage use_value"):
                    with handlers((OddNumberError, lambda c: use_value(c.x))):
                        result = lowlevel()
                        test[result == list(range(10))]

                with test("basic usage double"):
                    with handlers((OddNumberError, lambda c: invoke("double", c.x))):
                        result = lowlevel()
                        test[result == [0, 2 * 1, 2, 2 * 3, 4, 2 * 5, 6, 2 * 7, 8, 2 * 9]]

                with test("basic usage drop"):
                    with handlers((OddNumberError, lambda c: invoke("drop", c.x))):
                        result = lowlevel()
                        test[result == [0, 2, 4, 6, 8]]

                with test("basic usage bail"):
                    try:
                        with handlers((OddNumberError, lambda c: invoke("bail", c.x))):
                            lowlevel()
                    except ValueError as err:
                        test[str(err) == "1"]
            highlevel()
        basic_usage()

        # It is also valid to place the `with restarts` in the error branch only.
        # In fact, it can go at any level where you want a restartable block.
        #
        # ("Restartable", in the context of the condition system, means that
        #  instead of the usual result of the block, it may have as its result the
        #  return value of a restart, if a signal/handler/restart combination ran.)
        def basic_usage2():
            class OddNumberError(Exception):
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
                with test("basic usage use_value 2"):
                    with handlers((OddNumberError, lambda c: use_value(42))):
                        result = lowlevel()
                        test[result == [0, 42, 2, 42, 4, 42, 6, 42, 8, 42]]
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
    with testset("three levels"):
        def threelevel():
            # The low and mid-level parts are shared between the use cases.
            class TellMeHowToRecover(Exception):
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
            # We simply don't even install a handler.
            #
            # An uncaught `signal()` is just a no-op; see `warn()`, `error()`, `cerror()`
            # for other standard options.
            #
            def highlevel1():
                with catch_signals(False):  # tell the testing framework not to mind the uncaught signal
                    test[midlevel() == "low level ran to completion > normal exit from low level > normal exit from mid level"]
            highlevel1()

            # Use case where we want to resume at the low level (in a real-world application, repairing the error).
            # Note we need new code only at the high level; the mid and low levels remain as-is.
            def highlevel2():
                with test("resume at low level"):
                    with handlers((TellMeHowToRecover, lambda c: invoke("resume_low", "resumed at low level"))):
                        result = midlevel()
                        test[result == "resumed at low level > normal exit from low level > normal exit from mid level"]
            highlevel2()

            # Use case where we want to resume at the mid level (in a real-world application, skipping the failed part).
            def highlevel3():
                with test("resume at mid level"):
                    with handlers((TellMeHowToRecover, lambda c: invoke("resume_mid", "resumed at mid level"))):
                        result = midlevel()
                        test[result == "resumed at mid level > normal exit from mid level"]
            highlevel3()
        threelevel()

    class JustTesting(Exception):
        pass

    # Handler clauses can also take a tuple of types (instead of a single type).
    with testset("catch multiple signal types with the same handler"):
        def test_multiple_signal_types():
            # For testing, just send the condition instance to the `use_value` restart,
            # so we can see the handler actually catches both intended signal types.
            with handlers(((JustTesting, RuntimeError), lambda c: use_value(c))):
                # no "result << some_normal_exit_value", so here result is None if the signal is not handled.
                with restarts(use_value=(lambda x: x)) as result:
                    signal(JustTesting())
                test[isinstance(unbox(result), JustTesting)]

                with restarts(use_value=(lambda x: x)) as result:
                    signal(RuntimeError())
                test[isinstance(unbox(result), RuntimeError)]
        test_multiple_signal_types()

    # invoker(restart_name) creates a handler callable that just invokes
# the given restart (passing through args and kwargs to it, if any are given).
    with testset("invoker"):
        def test_invoker():
            with handlers((JustTesting, invoker("hello"))):
                with restarts(hello=(lambda: "hello")) as result:
                    warn(JustTesting())
                    result << 21
                test[unbox(result) == "hello"]
        test_invoker()

    with testset("use_value"):
        def test_usevalue():
            # A handler that just invokes the `use_value` restart:
            with handlers((JustTesting, (lambda c: invoke("use_value", 42)))):
                with restarts(use_value=(lambda x: x)) as result:
                    signal(JustTesting())
                    result << 21
                test[unbox(result) == 42]

            # can be shortened using the predefined `use_value` function, which immediately
            # invokes the eponymous restart with the args and kwargs given.
            with handlers((JustTesting, lambda c: use_value(42))):
                with restarts(use_value=(lambda x: x)) as result:
                    signal(JustTesting())
                    result << 21
                test[unbox(result) == 42]

            # The `invoker` factory is also an option here, if you're sending a constant.
            # This is applicable for invoking any restart in a use case that doesn't
            # need data from the condition instance (`c` in the above example):
            with handlers((JustTesting, invoker("use_value", 42))):
                with restarts(use_value=(lambda x: x)) as result:
                    signal(JustTesting())
                    result << 21
                test[unbox(result) == 42]
        test_usevalue()

    with testset("live inspection"):
        def inspection():
            with handlers((JustTesting, invoker("hello")),
                          (RuntimeError, lambda c: use_value(42))):
                with restarts(hello=(lambda: "hello"),
                              use_value=(lambda x: x)):
                    # The test system defines some internal restarts/handlers,
                    # so ours are not the full list - but they are a partial list.
                    test[subset(["hello", "use_value"],
                                [name for name, _callable in available_restarts()])]
                    test[subset([JustTesting, RuntimeError],
                                [t for t, _callable in available_handlers()])]
        inspection()

    with testset("alternate syntax"):
        def alternate_syntax():
            with handlers((JustTesting, lambda c: use_value(42))):
                # normal usage - as a decorator
                #
                # The decorator "with_restarts" and "def result()" pair can be used
                # instead of "with restarts(...) as result":
                @with_restarts(use_value=(lambda x: x))
                def result():
                    error(JustTesting())
                    return 21
                test[result == 42]

                # hifi usage - as a function
                with_usevalue = with_restarts(use_value=(lambda x: x))
                # Now we can, at any time later, call any thunk in the context of the
                # restarts that were given as arguments to `with_restarts`:
                def mythunk():
                    error(JustTesting())
                    return 21
                result = with_usevalue(mythunk)
                test[result == 42]
        alternate_syntax()

    with testset("error protocol"):
        def error_protocol():
            with handlers((RuntimeError, lambda c: use_value(42))):
                with restarts(use_value=(lambda x: x)) as result:
                    error(RuntimeError("foo"))
                    result << 21
                test[unbox(result) == 42]
        error_protocol()

    with testset("warn protocol"):
        def warn_protocol():
            with catch_signals(False):  # don't report the uncaught warn() as an unexpected signal in testing
                with handlers():
                    with restarts() as result:
                        print("Testing warn() - this should print a warning:")
                        warn(JustTesting("unhandled warn() prints a warning, but allows execution to continue"))
                        result << 21
                    test[unbox(result) == 21]

            with handlers((JustTesting, muffle)):  # canonical way to muffle a warning
                with restarts() as result:
                    warn(JustTesting("unhandled warn() does not print a warning when it is muffled"))
                    result << 21
                test[unbox(result) == 21]

            with handlers((JustTesting, lambda c: use_value(42))):
                with restarts(use_value=(lambda x: x)) as result:
                    warn(JustTesting("handled warn() does not print a warning"))
                    fail["This line should not be reached, because the restart takes over."]
                    result << 21  # not reached, because the restart takes over
                test[unbox(result) == 42]
        warn_protocol()

    # find_restart can be used to look for a restart before committing to
    # actually invoking it.
    with testset("find_restart"):
        def finding():
            class JustACondition(Exception):
                pass
            class NoItDidntExist(Exception):
                pass
            def invoke_if_exists(restart_name):
                r = find_restart(restart_name)
                if r:
                    invoke(r)
                # just a convenient way to tell the test code that it wasn't found.
                raise NoItDidntExist()
            # The condition instance parameter for a handler is optional - not needed
            # if you don't need data from the instance.
            with handlers((JustACondition, lambda: invoke_if_exists("myrestart"))):
                # Let's set up "myrestart".
                with restarts(myrestart=(lambda: 42)) as result:
                    signal(JustACondition())
                    result << 21
                test[unbox(result) == 42]  # should be the return value of the restart.

            # If there is no "myrestart" in scope, the above handler will *raise* NoItDidntExist.
            #
            # Note we place the `test_raises` construct on the outside, to avoid intercepting
            # the `signal(JustACondition)`.
            with test_raises(NoItDidntExist, "nonexistent restart"):
                with handlers((JustACondition, lambda: invoke_if_exists("myrestart"))):
                    signal(JustACondition())
        finding()

    with testset("error cases"):
        def errorcases():
            # The signal() low-level function does not require the condition to be handled.
            # If unhandled, signal() just returns normally.
            with catch_signals(False):
                test[returns_normally(signal(RuntimeError("woo")))]

            # error case: invoke outside the dynamic extent of any `with restarts`,
            # hence no restarts currently in scope.
            # This *signals* ControlError...
            test_signals[ControlError, invoke("woo")]
            # ...but if that is not handled, *raises* ControlError.
            with catch_signals(False):
                test_raises[ControlError, invoke("woo")]

            # error case: invoke an undefined restart
            with test_signals(ControlError, "should yell when trying to invoke a nonexistent restart"):
                with restarts(foo=(lambda x: x)):
                    invoke("bar")
        errorcases()

    # name shadowing: dynamically the most recent binding of the same restart name wins
    class HelpMe(Exception):
        def __init__(self, value):
            self.value = value

    with testset("name shadowing"):
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
            with test:
                with handlers((HelpMe, lambda c: invoke("r", c.value))):
                    result = lowlevel2()
                    test[result == (21, 42)]
        name_shadowing()

    # cancel-and-delegate: return normally to leave signal unhandled, delegating to next handler
    with testset("cancel and delegate"):
        def cancel_and_delegate():
            def lowlevel3():
                with restarts(use_value=(lambda x: x)) as a:
                    signal(HelpMe(42))
                    a << False
                return unbox(a)

            # If an inner handler returns normally, the next outer handler (if any) for
            # the same condition takes over. Note any side effects of the inner handler
            # remain in effect.
            with test:
                inner_handler_ran = box(False)  # use a box so we can rebind the value from inside a lambda
                outer_handler_ran = box(False)
                with handlers((HelpMe, lambda c: [outer_handler_ran << True,
                                                  use_value(c.value)])):
                    with handlers((HelpMe, lambda: [inner_handler_ran << True,
                                                    None])):  # return normally from handler to cancel-and-delegate
                        result = lowlevel3()
                        test[result == 42]
                        test[unbox(inner_handler_ran) is True]
                        test[unbox(outer_handler_ran) is True]

            # If the inner handler invokes a restart, the outer handler doesn't run.
            with test:
                inner_handler_ran = box(False)
                outer_handler_ran = box(False)
                with handlers((HelpMe, lambda c: [outer_handler_ran << True,
                                                  use_value(c.value)])):
                    with handlers((HelpMe, lambda c: [inner_handler_ran << True,
                                                      use_value(c.value)])):
                        result = lowlevel3()
                        test[result == 42]
                        test[unbox(inner_handler_ran) is True]
                        test[unbox(outer_handler_ran) is False]
        cancel_and_delegate()

    # Multithreading. Threads behave independently.
    with testset("multithreading"):
        def multithreading():
            comm = Queue()
            def lowlevel4(tag):
                with restarts(use_value=(lambda x: x)) as result:
                    signal(HelpMe((tag, 42)))
                    result << (tag, 21)  # if the signal is not handled, the box will hold (tag, 21)
                return unbox(result)
            def worker(comm, tid):
                with handlers((HelpMe, lambda c: use_value(c.value))):
                    comm.put(lowlevel4(tid))
            n = 1000
            threads = [threading.Thread(target=worker, args=(comm, tid), kwargs={}) for tid in range(n)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()
            results = slurp(comm)
            test[len(results) == n]
            test[all(x == 42 for tag, x in results)]
            test[tuple(sorted(tag for tag, x in results)) == tuple(range(n))]
        multithreading()

if __name__ == '__main__':
    with session(__file__):
        runtests()
