# -*- coding: utf-8; -*-
"""unpythonic.test.fixtures, a testing framework for macro-enabled Python code.

This is an 80% solution. Hopefully it's the 80% you need.

We provide just enough of the very basics of a testing framework to get
rudimentary test reports for macro-enabled Python code, particularly
`unpythonic` itself (see issue #5).

This also demonstrates how to build a simple testing framework on top of the
`test[]` macro and its sisters. (NOTE: hence MacroPy required!)

**Why**:

We can't use `unittest` to test `unpythonic`, due to some constructs having the
same name as the module hosting the construct. This is an issue in `unpythonic`
specifically, see issue #44.

We can't use the otherwise excellent `pytest`, because in order to get the nice
syntax that redefines `assert`, it has to install an import hook, and in doing
so disables the macro expander. (This is a problem shared by all macro-enabled
Python code.)

As for why a `test[]` macro, MacroPy macros only exist in expr, block and
decorator variants, so we can't just hijack any AST node type like `pytest`'s
custom import hook does. So we solve this the MacroPy way - by providing an
expr macro that can be used instead of `assert` when writing test cases.

**Usage**, a.k.a. unpythonic testing 101::

    from unpythonic.syntax import macros, test
    from unpythonic.test.fixtures import session, testset, terminate

    # The session construct provides an exit point for test session
    # termination, and an implicit top-level testset.
    # A session can be started only when not already inside a testset.
    with session("framework demo"):
        # A session may contain bare tests. They are implicitly part of the
        # top-level testset.
        test[2 + 2 == 4]
        # Tests can have a human-readable failure message.
        test[2 + 2 == 5, "should be five, no?"]

        # Tests can be further grouped into testsets, if desired.
        with testset():
            test[2 + 2 == 4]
            test[2 + 2 == 5]

        # Testsets can be named. The name is printed in the output.
        from unpythonic.misc import raisef
        from unpythonic.conditions import cerror
        with testset("my fancy tests"):
            test[2 + 2 == 4]
            test[raisef(RuntimeError)]  # exceptions are caught.
            test[cerror(RuntimeError)]  # signals are caught, too.
            test[2 + 2 == 6]

            # A testset reports also any stray signals or exceptions it receives
            # from outside a `test[]` construct.
            #
            # - When a signal arrives via `cerror`, the testset resumes.
            # - When some other signal protocol is used (no "proceed" restart
            #   is in scope), the handler returns normally; what then happens
            #   depends on which signal protocol it is.
            # - When an exception is caught, the testset terminates, because
            #   exceptions do not support resuming.
            cerror(RuntimeError("blargh"))
            raise RuntimeError("gargle")

        # Testsets can be nested.
        with testset("outer"):
            with testset("inner 1"):
                test[2 + 2 == 4]
            with testset("inner 2"):
                test[2 + 2 == 4]

        # Unconditional errors can be emitted with `error[]`.
        # Useful e.g. if an optional dependency is missing:
        with testset("integration"):
            try:
                import blargly
            except ImportError:
                error["blargly not installed, cannot test integration with it."]
            else:
                ... # blargly integration tests go here

        # Similarly, unconditional errors can be emitted with `fail[]`.
        # Useful for marking a testing TODO, or for marking a line
        # that should be unreachable in a code example.
        with testset("really fancy tests"):
            fail["really fancy tests not implemented yet!"]

        # # The session can be terminated early by calling terminate()
        # # at any point inside the dynamic extent of `with session`.
        # # This causes the `with session` to exit immediately.
        # terminate()

        # The session can also be terminated by the first failure in a
        # particular testset by using `terminate` as the `postproc`:
        with testset(postproc=terminate):
            test[2 + 2 == 5]
            test[2 + 2 == 4]  # not reached

If you want to customize, look at the `postproc` parameter of `testset`,
and the `TestConfig` bunch of constants.

See:
    https://github.com/Technologicat/unpythonic/issues/5
    https://github.com/Technologicat/unpythonic/issues/44
"""

from contextlib import contextmanager
from collections import deque
from functools import partial
from traceback import format_tb
import sys

from ..conditions import handlers, find_restart, invoke
from ..collections import box, unbox

from .ansicolor import TC, colorize

__all__ = ["session", "testset",
           "terminate",
           "returns_normally", "catch_signals",
           "TestConfig",
           "tests_run", "tests_failed", "tests_errored",
           "TestingException", "TestFailure", "TestError"]

# Keep a global count (since Python last started) of how many unpythonic_asserts
# have run and how many have failed, so that the client code can easily calculate
# the percentage of tests passed.
#
# We use `box` to keep this simple; its API supports querying and resetting,
# so we don't need to build yet another single-purpose API for these particular
# counters.
tests_run = box(0)
tests_failed = box(0)
tests_errored = box(0)
tests_run.__doc__ = "How many tests have run, in total. Boxed global counter."
tests_failed.__doc__ = "How many tests have failed, in total. Boxed global counter."
tests_errored.__doc__ = "How many tests have errored, in total. Boxed global counter."

class TestingException(Exception):
    """Base type for testing-related exceptions."""
class TestFailure(TestingException):
    """Exception type indicating that a test failed."""
class TestError(TestingException):
    """Exception type indicating that a test did not run to completion.

    This can happen due to an unexpected exception, or an unhandled
    `error` (or `cerror`) condition.
    """

def maybe_colorize(s, *colors):
    """Colorize `s` with ANSI color escapes if enabled in the global `TestConfig`.

    If color is disabled (`TestConfig.use_color` is falsey), then no-op, i.e.
    return the original `s` as-is.

    See `unpythonic.test.ansicolor.colorize` for details.
    """
    if not TestConfig.use_color:
        return s
    return colorize(s, *colors)

class TestConfig:
    """Global settings for the testing utilities.

    This is just a bunch of constants.

    If you want to change the settings, just assign new values to the attributes
    at any point in your test script (the new values will take effect from that
    point forward). Probably the least confusing if done before the `with session`.

    `printer`:          str -> None; side effect should be to display the string in some
                        appropriate way. Default is to `print` to `sys.stderr`.
    `use_color`:        bool; use ANSI color escape sequences to colorize `printer` output.
                        Default is `True`.
    `postproc`:         Exception -> None; optional. Default None (no postproc).
    `indent_per_level`: How many indent to indent per nesting level of `testset`.
    `CS`:               The color scheme.

    The optional `postproc` is a custom callback for examining failures and
    errors. `TestConfig.postproc` sets the default that is used when no other
    (more local) `postproc` is in effect.

    It receives one argument, which is a `TestFailure` or `TestError` instance
    that was signaled by a failed or errored test (respectively).

    `postproc` is called after sending the error to `printer`, just before
    resuming with the remaining tests. To continue processing, the `postproc`
    should just return normally.

    If you want a failure in a particular testset to abort the whole unit, you
    can use `terminate` as your `postproc`.
    """
    printer = partial(print, file=sys.stderr)
    use_color = True
    postproc = None
    indent_per_level = 2

    class CS:
        """The color scheme.

        See the `unpythonic.test.ansicolor.TC` enum for valid values. To make a
        compound style, place the values into a tuple.

        The defaults are designed to fit the "Solarized" (Zenburn-like) theme
        of `gnome-terminal`, with "Show bold text in bright colors" set to OFF.
        But they should work with most color schemes.
        """
        HEADING = TC.LIGHTBLUE
        PASS = TC.GREEN
        FAIL = TC.LIGHTRED
        ERROR = TC.YELLOW
        GREYED_OUT = (TC.DIM, HEADING)
        # These colors are used for the pass percentage.
        SUMMARY_OK = TC.GREEN
        SUMMARY_NOTOK = TC.YELLOW  # more readable than red on a dark background, yet stands out.

def describe_exception(exc):
    """Return a human-readable (possibly multi-line) description of exception `exc`.

    The output is as close as possible to how Python itself formats exceptions,
    but the tracebacks are dimmed using ANSI color to better separate headings
    from details.

    See:
        https://docs.python.org/3/library/exceptions.html
        https://stackoverflow.com/questions/16414744/python-exception-chaining
    """
    def describe_instance(instance):
        snippets = []

        if instance.__traceback__ is not None:
            snippets.append(maybe_colorize("\nTraceback (most recent call last):\n" +
                                           "".join(format_tb(instance.__traceback__)), TC.DIM))

        msg = str(instance)
        if msg:
            snippets.append("{}: {}".format(type(instance), msg))
        else:
            snippets.append("{}".format(type(instance)))

        return snippets

    def describe_recursive(exc):
        if isinstance(exc, BaseException):  # "raise SomeError()"
            snippets = []

            if exc.__cause__ is not None:  # raise ... from ...
                snippets.extend(describe_recursive(exc.__cause__))
                snippets.append("\n\nThe above exception was the direct cause of the following exception:\n")
            elif not exc.__suppress_context__ and exc.__context__ is not None:
                snippets.extend(describe_recursive(exc.__context__))
                snippets.append("\n\nDuring handling of the above exception, another exception occurred:\n")

            snippets.extend(describe_instance(exc))

            return snippets
        else:  # "raise SomeError"
            return [str(exc)]

    return "".join(describe_recursive(exc))

def summarize(runs, fails, errors):
    """Return a human-readable summary of passes, fails, errors, and the total number of tests run.

    `runs`, `fails`, `errors` are nonnegative integers containing the count
    of what it says on the tin.
    """
    assert isinstance(runs, int) and runs >= 0
    assert isinstance(fails, int) and fails >= 0
    assert isinstance(errors, int) and errors >= 0

    passes = runs - fails - errors
    if runs:
        fail_ratio = fails / runs
        error_ratio = errors / runs
    else:
        fail_ratio = error_ratio = 0.0
    pass_ratio = 1 - fail_ratio - error_ratio
    pass_percentage = 100 * pass_ratio

    # In techni... ANSI color:
    snippets = []
    color = TestConfig.CS.PASS if passes else TestConfig.CS.GREYED_OUT
    snippets.extend([maybe_colorize("Pass", TC.BRIGHT, color),
                     " ",
                     maybe_colorize("{}".format(passes), color),
                     maybe_colorize(", ", TestConfig.CS.HEADING)])
    color = TestConfig.CS.FAIL if fails else TestConfig.CS.GREYED_OUT
    snippets.extend([maybe_colorize("Fail", TC.BRIGHT, color),
                     " ",
                     maybe_colorize("{}".format(fails), color),
                     maybe_colorize(", ", TestConfig.CS.HEADING)])
    color = TestConfig.CS.ERROR if errors else TestConfig.CS.GREYED_OUT
    snippets.extend([maybe_colorize("Error", TC.BRIGHT, color),
                     " ",
                     maybe_colorize("{}".format(errors), color),
                     maybe_colorize(", ", TestConfig.CS.HEADING)])
    color = TestConfig.CS.HEADING if runs else TestConfig.CS.GREYED_OUT
    snippets.extend([maybe_colorize("Total", TC.BRIGHT, color),
                     " ",
                     maybe_colorize("{}".format(runs), color)])
    color = TestConfig.CS.SUMMARY_OK if passes == runs else TestConfig.CS.SUMMARY_NOTOK
    snippets.extend([" ",
                     maybe_colorize("({}% pass)".format(int(pass_percentage)), TC.BRIGHT, color)])
    return "".join(snippets)

class TestSessionExit(Exception):
    """Exception, raising which terminates the current test session."""
def terminate(exc=None):  # the parameter is ignored
    """Terminate the test session.

    The parameter is ignored. It is provided for API compatibility so that
    this can be used as a `postproc`, if you want a failure in a particular
    testset to abort the session.
    """
    TestConfig.printer(maybe_colorize("** TERMINATING SESSION", TC.BRIGHT, TestConfig.CS.HEADING))
    raise TestSessionExit

def returns_normally(expr):
    """For use inside `test[]` and its sisters.

    Assert that `expr` runs to completion without raising or signaling.

    Usage::

        test[returns_normally(myfunc())]
    """
    # The magic is, `test[]` lifts its expr into a lambda. When the test runs,
    # our arg gets evaluated first, and then its value is passed to us.
    #
    # To make the test succeed whenever `unpythonic.syntax.testutil._observe`
    # didn't catch an unexpected signal or exception in `expr`, we just ignore
    # our arg, and:
    return True

_catch_uncaught_signals = deque([True])  # on by default
@contextmanager
def catch_signals(state):
    """Context manager.

    Controls whether `test[]` and its sisters, and `with testset`,
    catch uncaught signals. (Default is `True`).

    Does not affect uncaught exceptions. Unlike signals, exceptions unwind the
    stack immediately, so for exceptions, there is no possibility to ignore the
    exceptional condition while allowing its signaler to proceed.

    For signals, that possibility is sometimes useful; the purpose of this
    construct is to explicitly document that intent in the form of automated
    tests.

    `with catch_signals` blocks can be nested; the most recent (i.e.
    dynamically innermost) one wins.
    """
    _catch_uncaught_signals.appendleft(state)
    yield
    _catch_uncaught_signals.popleft()

_nesting_level = 0
@contextmanager
def session(name=None):
    """Context manager representing a test session.

    Provides an exit point for terminating the test session. To terminate
    early, call `terminate` during the dynamic extent of `with session`.

    To terminate the session by the first failure in a particular testset,
    use `terminate` as `postproc` for that testset.
    """
    if _nesting_level > 0:
        raise RuntimeError("A test `session` cannot be nested inside a `testset`.")

    title = maybe_colorize("SESSION", TC.BRIGHT, TestConfig.CS.HEADING)
    if name is not None:
        title += maybe_colorize(" '{}'".format(name), TC.ITALIC, TestConfig.CS.HEADING)
    TestConfig.printer(maybe_colorize("{} ".format(title), TestConfig.CS.HEADING) +
                       maybe_colorize("BEGIN", TC.BRIGHT, TestConfig.CS.HEADING))

    # We are paused when the user triggers the exception; `contextlib` detects the
    # exception and re-raises it into us.
    try:
        # Wrap in a top-level testset to catch all stray signals/exceptions
        # during a session.
        #
        # This also separates concerns - this top-level testset tallies
        # the grand totals so we don't have to.
        with testset("top level"):
            yield
    except TestSessionExit:
        pass

    TestConfig.printer(maybe_colorize("{} ".format(title), TestConfig.CS.HEADING) +
                       maybe_colorize("END", TC.BRIGHT, TestConfig.CS.HEADING))

# We use a stack for postprocs so that the local overrides can be nested.
_postproc_stack = deque()
@contextmanager
def testset(name=None, postproc=None):
    """Context manager representing a test set.

    Automatically computes passes, fails, errors, total, and the pass percentage.

    `name` is an optional string specifying a human-readable name for the testset.
    If not given, the testset is not named.

    `postproc` is like `TestConfig.postproc`, but overriding that for this test set
    (and any testsets contained within this one, unless they specify their own).

    **CAUTION**: Not thread-safe. The `test[...]` invocations should be made from
    a single thread, because `test[]` uses global counters to track runs/fails/errors.
    """
    r1 = unbox(tests_run)
    f1 = unbox(tests_failed)
    e1 = unbox(tests_errored)

    global _nesting_level
    indent = ("*" * (TestConfig.indent_per_level * _nesting_level))
    if len(indent):
        indent += " "
    errmsg_extra_indent = "*" * TestConfig.indent_per_level
    _nesting_level += 1

    title = "{}Testset".format(indent)
    if name is not None:
        title += maybe_colorize(" '{}'".format(name), TC.ITALIC)
    TestConfig.printer(maybe_colorize("{} ".format(title), TestConfig.CS.HEADING) +
                       maybe_colorize("BEGIN", TC.BRIGHT, TestConfig.CS.HEADING))

    def print_and_proceed(condition):
        # The assert helpers in `unpythonic.syntax.testutil` signal only TestFailure and TestError,
        # no matter what happens inside the test expression.
        if isinstance(condition, TestFailure):
            msg = maybe_colorize("{}{}FAIL: ".format(errmsg_extra_indent, indent),
                                 TC.BRIGHT, TestConfig.CS.FAIL) + str(condition)
        elif isinstance(condition, TestError):
            msg = maybe_colorize("{}{}ERROR: ".format(errmsg_extra_indent, indent),
                                 TC.BRIGHT, TestConfig.CS.ERROR) + str(condition)
        # So any other signal must come from another source.
        else:
            if not _catch_uncaught_signals[0]:
                return  # cancel and delegate to the next outer handler
            # To highlight the error in the summary, count it as an errored test.
            tests_run << unbox(tests_run) + 1
            tests_errored << unbox(tests_errored) + 1
            msg = maybe_colorize("{}{}Testset received signal outside test[]: ".format(errmsg_extra_indent, indent),
                                 TC.BRIGHT, TestConfig.CS.ERROR) + describe_exception(condition)
        TestConfig.printer(msg)

        # the custom callback
        if _postproc_stack:
            r = _postproc_stack[0]
        elif TestConfig.postproc is not None:
            r = TestConfig.postproc
        else:
            r = None
        if r is not None:
            r(condition)

        # We find first instead of just invoking so that we support all standard signal
        # protocols, not just `cerror` (which defines "proceed").
        p = find_restart("proceed")
        if not p:
            # HACK: unpythonic.conditions.warn defines a "_proceed" for us, so
            # we can let the warning happen, but stop it from propagating to
            # outer testsets and being displayed multiple times.
            p = find_restart("_proceed")
        if p is not None:
            invoke(p)
        # Otherwise we just return normally (cancel and delegate to the next outer handler).

    if postproc is not None:
        _postproc_stack.appendleft(postproc)

    # The test[] macro signals a condition (using `cerror`), does not raise an
    # exception. That gives it the superpower to resume the rest of the tests.
    try:
        with handlers((Exception, print_and_proceed)):
            yield
    except TestSessionExit:  # pass through, it belongs to session, not us
        pass
    except Exception as err:
        # To highlight the error in the summary, count it as an errored test.
        tests_run << unbox(tests_run) + 1
        tests_errored << unbox(tests_errored) + 1
        msg = maybe_colorize("{}{}Testset terminated by exception outside test[]: ".format(errmsg_extra_indent, indent),
                             TC.BRIGHT, TestConfig.CS.ERROR)
        msg += describe_exception(err)
        TestConfig.printer(msg)

    if postproc is not None:
        _postproc_stack.popleft()

    _nesting_level -= 1
    assert _nesting_level >= 0

    r2 = unbox(tests_run)
    f2 = unbox(tests_failed)
    e2 = unbox(tests_errored)

    runs = r2 - r1
    fails = f2 - f1
    errors = e2 - e1
    TestConfig.printer(maybe_colorize("{} ".format(title), TestConfig.CS.HEADING) +
                       maybe_colorize("END", TC.BRIGHT, TestConfig.CS.HEADING) +
                       maybe_colorize(": ", TestConfig.CS.HEADING) +
                       summarize(runs, fails, errors))
