# -*- coding: utf-8; -*-
"""unpythonic.test.fixtures, a testing framework for macro-enabled Python code.

This is an 80% solution. Hopefully it's the 80% you need.

We provide just enough of the very basics of a testing framework to get
rudimentary test reports for macro-enabled Python code, particularly
`unpythonic` itself (see issue #5).

This also demonstrates how to build a simple testing framework on top of the
`test[]` macro and its sisters. (NOTE: hence `mcpyrate` required!)

**Why**:

We can't use `unittest` to test `unpythonic`, due to some constructs having the
same name as the module hosting the construct. This is an issue in `unpythonic`
specifically, see issue #44.

We can't use the otherwise excellent `pytest`, because in order to get the nice
syntax that redefines `assert`, it has to install an import hook, and in doing
so disables the macro expander. (This is a problem shared by all macro-enabled
Python code.)

As for why a `test[]` macro, `mcpyrate` macros only exist in expr, block, decorator
and name variants, so we can't just hijack any AST node type like `pytest`'s
custom import hook does. So we solve this the macropythonic way - by providing
an expr macro that can be used instead of `assert` when writing test cases.

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
        from unpythonic.excutil import raisef
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
import threading
import sys

# The testing framework depends on `mcpyrate` anyway, because the test
# constructs are macros.
#
# This regular-code module depends on `mcpyrate`'s colorizer, but since
# `unpythonic.test` is not auto-loaded, it's fine.
#
# Using `Bunch` is debatable, since we have `env`, and `Bunch` is essentially
# just a stripped-down version of that. But `mcpyrate` uses `Bunch` for storing
# config constants, so meh - let's just use the same approach here for consistency.
from mcpyrate.bunch import Bunch
from mcpyrate.colorizer import Fore, Style, colorize

from ..conditions import handlers, find_restart, invoke
from ..collections import box, unbox
from ..symbol import sym

__all__ = ["session", "testset",
           "terminate",
           "returns_normally", "catch_signals",
           "TestConfig",
           "tests_run", "tests_failed", "tests_errored", "tests_warned",
           "TestingException", "TestFailure", "TestError", "TestWarning",
           "completed", "signaled", "raised",
           "describe_exception"]

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
tests_warned = box(0)
tests_run.__doc__ = "How many tests have run, in total. Boxed global counter."
tests_failed.__doc__ = "How many tests have failed, in total. Boxed global counter."
tests_errored.__doc__ = "How many tests have errored, in total. Boxed global counter."
tests_warned.__doc__ = """How many tests emitted a warning. Boxed global counter.

Warnings don't count toward the total number of tests run, and are not
considered essential (i.e. the test suite will succeed even with warnings).

The `+ N Warnings` message will be shown at the end of the nearest enclosing testset,
and any testsets enclosing that one, up to the top level.
"""
_counter_update_lock = threading.Lock()
def _update(counter, delta):
    """Update a global test counter in a thread-safe way.

    `counter`: object; one of `tests_run`, `tests_failed`,
               `tests_errored` or `tests_warned`.
    `delta`: amount to update by (additive).
    """
    with _counter_update_lock:
        counter << unbox(counter) + delta
def _reset(counter):
    """Reset a global test counter in a thread-safe way.

    `counter`: object; one of `tests_run`, `tests_failed`,
               `tests_errored` or `tests_warned`.
    """
    with _counter_update_lock:
        counter << 0

completed = sym("completed")
completed.__doc__ = """TestingException `mode`: the test ran to completion normally.

This does not mean that the test assertion succeeded, but only that
it exited normally (i.e. did not signal or raise).
"""
signaled = sym("signaled")
signaled.__doc__ = """TestingException `mode`: the test signaled a condition.

The signal was not caught inside the test.

See `unpythonic.conditions.signal` and its sisters `error`, `cerror`, `warn`.
"""
raised = sym("raised")
raised.__doc__ = """TestingException `mode`: the test raised an exception.

The exception was not caught inside the test.
"""
class TestingException(Exception):
    """Base type for testing-related exceptions."""
    def __init__(self, *args, origin=None, custom_message=None,
                 filename=None, lineno=None, sourcecode=None,
                 mode=None, result=None, captured_values=None):
        """Parameters:

        `*args`: like in Exception. Usually just one, a human-readable
                 error message as str.

        Additionally, the test macros automatically fill in the following
        optional parameters, for runtime inspection. These are stored in
        instance attributes with the same name as the corresponding parameter:

        `origin`: str, which of the test asserters produced this exception.
                  One of "test", "test_signals", "test_raises", "fail", "error", "warn".

        `custom_message`: str or None. The optional, user-provided human-readable
                          custom failure message, if any.

                          Test blocks that just assert that the block returns normally
                          (default behavior if no `return` used) are encouraged to carry
                          a clarifying message, provided by the user, to explain what was
                          expected to happen, if it turns out that the test fails or errors.

                          (Often, in such cases, the context alone is insufficient for a
                           human not intimately familiar with the code to judge why the test
                           block should or should not exit normally, so a message is useful.)

                          Any invocation of `fail[]`, `error[]` and `warn[]` will also
                          typically carry such a message, since that's the whole point
                          of using those constructs.

                          For any other use case though, the details are often clear enough
                          from the code of the test assertion (or test block) itself, so
                          there is no need for the user to include a custom failure message.

        `filename`: str, the full path of the file containing the test in which
                    the exception occurred.
        `lineno`: int, line number in `filename` (1-based, as usual).
        `sourcecode`: str, captured (actually unparsed from AST) source code of the test
                      assertion (or test block). If a block, may have multiple lines.

        `mode`: sym, how the test exited. One of `completed`, `signaled`, `raised` (which see).

        `result`: If `mode is completed`, then the value of the test assertion (or the return
                  value of a test block, respectively). Note test blocks that just assert
                  that the block completes normally always return `True` when they complete
                  normally.

                  If `mode is signaled`, the signal instance (an `Exception` object).

                  If `mode is raised`, the exception instance (an `Exception` object).

                  If you need to format an exception (and its chained exceptions, if any)
                  for human consumption, in a notation as close as possible to what Python
                  itself uses for reporting uncaught exceptions, see `describe_exception`.

        `captured_values`: list, may be empty. Each item is of the form `(sourcecode_str, value)`.
                If any `the[]` were used, an item is created for each `the[]` subexpression,
                in the order the subexpressions were evaluated.

                Else if the top level of the test assertion (or the return value of a test block,
                respectively) was a comparison, an item is created for the leftmost term.

                Else empty.

                Note that `test_signals` and `test_raises` do not support capturing;
                for them `captured_values` is always empty.
        """
        super().__init__(*args)
        self.origin = origin
        self.custom_message = custom_message
        self.filename = filename
        self.lineno = lineno
        self.sourcecode = sourcecode
        self.mode = mode
        self.result = result
        self.captured_values = captured_values
class TestFailure(TestingException):
    """Exception: a test ran to completion normally, but the test assertion failed.

    May also mean that a test was expected to signal or raise, but it didn't.
    """
class TestError(TestingException):
    """Exception: a test did not run to completion normally.

    It was also not expected to signal or raise, at least not the
    exception type that was observed.

    This can happen due to an unexpected exception, or an unhandled
    `error` (or `cerror`) condition.
    """
class TestWarning(TestingException):
    """Exception: a human-initiated test warning.

    Warnings (see the `warn[]` macro) can be used e.g. to mark tests that
    are temporarily disabled due to external factors, such as language-level
    compatibility issues, or a bug in a library yours depends on.
    """

def maybe_colorize(s, *colors):
    """Colorize `s` with ANSI color escapes if enabled in the global `TestConfig`.

    If color is disabled (`TestConfig.use_color` is falsey), then no-op, i.e.
    return the original `s` as-is.

    See `mcpyrate.colorizer.colorize` for details.
    """
    if not TestConfig.use_color:
        return s
    return colorize(s, *colors)

# We instantiate this later, since the instance lives inside `TestConfig` anyway.
class ColorScheme(Bunch):
    """The color scheme for terminal output in `unpythonic`'s testing framework.

    This is just a bunch of constants. To change the colors, simply assign new
    values to them. Changes take effect immediately for any new output.

    To replace the whole color scheme at once, fill in a suitable `Bunch`, and
    then use the `replace` method. If you need to get the names of all settings
    programmatically, call the `keys` method.

    Don't replace the color scheme object itself.

    See `Fore`, `Back` and `Style` in `mcpyrate.colorizer` for valid values.
    To make a compound style, place the values into a tuple.

    The defaults are designed to fit the "Solarized" (Zenburn-like) theme
    of `gnome-terminal`, with "Show bold text in bright colors" set to OFF.
    But they work also with "Tango", and indeed with most themes.
    """
    def __init__(self):
        super().__init__()

        self.HEADING = Fore.LIGHTBLUE_EX
        self.PASS = Fore.GREEN
        self.FAIL = Fore.LIGHTRED_EX
        self.ERROR = Fore.YELLOW
        self.WARNING = Fore.YELLOW
        self.GREYED_OUT = (Style.DIM, self.HEADING)
        # These colors are used for the pass percentage.
        self.SUMMARY_OK = Fore.GREEN
        self.SUMMARY_NOTOK = Fore.YELLOW  # more readable than red on a dark background, yet stands out.

class TestConfig(Bunch):
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
    `ColorScheme`:      The color scheme.

    The optional `postproc` is a custom callback for examining failures and
    errors. `TestConfig.postproc` sets the default that is used when no other
    (more local) `postproc` is in effect.

    It receives one argument, which is a `TestFailure`, `TestError` or `TestWarning`
    instance that was signaled by a failed, errored or warned test (respectively).

    `postproc` is called after sending the error to `printer`, just before
    resuming with the remaining tests. To continue processing, the `postproc`
    should just return normally.

    If you want a failure in a particular testset to abort the whole unit, you
    can use `terminate` as your `postproc`.
    """
    def __init__(self):
        super().__init__()

        # It is overwhelmingly common that tests are invoked from a single thread,
        # so by default, all threads share the same printer. (It is not worth
        # complicating the common use case here to cater for the rare use case.)
        #
        # However, if you want different printers in different threads, that can
        # be done. As `printer`, use a `Shim` that contains a `ThreadLocalBox`.
        # In each thread, place in that box a custom object that has a `__call__`
        # method that takes the same args `print` does. Because `Shim` redirects
        # all attribute accesses, it will redirect the lookup of `__call__`
        # (it doesn't have its own `__call__`, so it assumes the client wants to
        # call the thing that is inside the box), and hence that method will then
        # be used for printing.
        #
        # TODO: This is subject to change later if I figure out a better design
        # TODO: that conveniently caters for *both* the common and rare use cases.
        self.printer = partial(print, file=sys.stderr)
        self.use_color = True
        self.postproc = None
        self.indent_per_level = 2
        self.ColorScheme = ColorScheme()
TestConfig = TestConfig()  # type: ignore[assignment, misc]

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
                                           "".join(format_tb(instance.__traceback__)), Style.DIM))

        msg = str(instance)
        if msg:
            snippets.append(f"{type(instance)}: {msg}")
        else:
            snippets.append(f"{type(instance)}")

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

def summarize(runs, fails, errors, warns):
    """Return a human-readable summary.

    How many tests ran, passed, failed, errored, or warned.

    `runs`, `fails`, `errors`, `warns` are nonnegative integers containing the
    count of what it says on the tin.
    """
    assert isinstance(runs, int) and runs >= 0
    assert isinstance(fails, int) and fails >= 0
    assert isinstance(errors, int) and errors >= 0
    assert isinstance(warns, int) and warns >= 0

    # TODO: Currently we don't count warnings in the total number of tests.
    # TODO: Think about if this is good or if it should be changed.
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
    color = TestConfig.ColorScheme.PASS if passes else TestConfig.ColorScheme.GREYED_OUT
    snippets.extend([maybe_colorize("Pass", Style.BRIGHT, color),
                     " ",
                     maybe_colorize(f"{passes}", color),
                     maybe_colorize(", ", TestConfig.ColorScheme.HEADING)])
    color = TestConfig.ColorScheme.FAIL if fails else TestConfig.ColorScheme.GREYED_OUT
    snippets.extend([maybe_colorize("Fail", Style.BRIGHT, color),
                     " ",
                     maybe_colorize(f"{fails}", color),
                     maybe_colorize(", ", TestConfig.ColorScheme.HEADING)])
    color = TestConfig.ColorScheme.ERROR if errors else TestConfig.ColorScheme.GREYED_OUT
    snippets.extend([maybe_colorize("Error", Style.BRIGHT, color),
                     " ",
                     maybe_colorize(f"{errors}", color),
                     maybe_colorize(", ", TestConfig.ColorScheme.HEADING)])
    color = TestConfig.ColorScheme.HEADING if runs else TestConfig.ColorScheme.GREYED_OUT
    snippets.extend([maybe_colorize("Total", Style.BRIGHT, color),
                     " ",
                     maybe_colorize(f"{runs}", color)])
    color = TestConfig.ColorScheme.SUMMARY_OK if passes == runs else TestConfig.ColorScheme.SUMMARY_NOTOK
    snippets.extend([" ",
                     maybe_colorize(f"({int(pass_percentage)}% pass)", Style.BRIGHT, color)])
    if warns > 0:
        color = TestConfig.ColorScheme.WARNING
        snippets.extend([" ",
                         maybe_colorize(f"+ {warns} Warn", Style.BRIGHT, color)])
    return "".join(snippets)

class TestSessionExit(Exception):
    """Exception, raising which terminates the current test session."""
def terminate(exc=None):  # the parameter is ignored
    """Terminate the test session.

    The parameter is ignored. It is provided for API compatibility so that
    this can be used as a `postproc`, if you want a failure in a particular
    testset to abort the session.
    """
    TestConfig.printer(maybe_colorize("** TERMINATING SESSION", Style.BRIGHT, TestConfig.ColorScheme.HEADING))
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
    # To make the test succeed whenever `unpythonic.syntax.testingtools._observe`
    # didn't catch an unexpected signal or exception in `expr`, we just ignore
    # our arg, and:
    return True

_threadlocals = threading.local()
_threadlocals.catch_uncaught_signals = deque([True])  # on by default  # TODO: init for all threads
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
    _threadlocals.catch_uncaught_signals.appendleft(state)
    try:
        # Regarding exceptions in generators in general, there's a pitfall to be
        # aware of: if the `finally` clause of a `try`/`finally` contains a
        # `yield`, the generator must jump through a hoop to work as expected:
        #     https://amir.rachum.com/blog/2017/03/03/generator-cleanup/
        #
        # In the `try` part it's always safe to `yield`, so in this particular
        # instance this doesn't concern us. In the `finally` part it's *possible*
        # to `yield`, but then `GeneratorExit` requires special consideration.
        yield
    finally:
        _threadlocals.catch_uncaught_signals.popleft()

_threadlocals.nesting_level = 0
@contextmanager
def session(name=None):
    """Context manager representing a test session.

    Provides an exit point for terminating the test session. To terminate
    early, call `terminate` during the dynamic extent of `with session`.

    To terminate the session by the first failure in a particular testset,
    use `terminate` as `postproc` for that testset.
    """
    if _threadlocals.nesting_level > 0:
        raise RuntimeError("A test `session` cannot be nested inside a `testset`.")

    title = maybe_colorize("SESSION", Style.BRIGHT, TestConfig.ColorScheme.HEADING)
    if name is not None:
        title += maybe_colorize(f" '{name}'", Style.ITALIC, TestConfig.ColorScheme.HEADING)
    TestConfig.printer(maybe_colorize(f"{title} ", TestConfig.ColorScheme.HEADING) +
                       maybe_colorize("BEGIN", Style.BRIGHT, TestConfig.ColorScheme.HEADING))

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

    TestConfig.printer(maybe_colorize(f"{title} ", TestConfig.ColorScheme.HEADING) +
                       maybe_colorize("END", Style.BRIGHT, TestConfig.ColorScheme.HEADING))

# We use a stack for postprocs so that the local overrides can be nested.
_threadlocals.postproc_stack = deque()
@contextmanager
def testset(name=None, postproc=None):
    """Context manager representing a test set.

    Automatically computes passes, fails, errors, total, and the pass percentage.

    `name` is an optional string specifying a human-readable name for the testset.
    If not given, the testset is not named.

    `postproc` is like `TestConfig.postproc`, but overriding that for this test set
    (and any testsets contained within this one, unless they specify their own).
    """
    def counters():
        return tuple(unbox(b) for b in (tests_run,
                                        tests_failed,
                                        tests_errored,
                                        tests_warned))
    r1, f1, e1, w1 = counters()

    def makeindent(level):
        indent = "*" * (TestConfig.indent_per_level * level)
        if len(indent):
            indent += " "
        return indent

    indent = makeindent(_threadlocals.nesting_level)
    errmsg_indent = makeindent(_threadlocals.nesting_level + 1)
    _threadlocals.nesting_level += 1

    title = f"{indent}Testset"
    if name is not None:
        title += maybe_colorize(f" '{name}'", Style.ITALIC, TestConfig.ColorScheme.HEADING)
    TestConfig.printer(maybe_colorize(f"{title} ", TestConfig.ColorScheme.HEADING) +
                       maybe_colorize("BEGIN", Style.BRIGHT, TestConfig.ColorScheme.HEADING))

    def print_and_proceed(condition):
        # The assert helpers in `unpythonic.syntax.testingtools` signal only
        # the descendants of `TestingException`, no matter what happens
        # inside the test expression.
        if isinstance(condition, TestFailure):
            msg = maybe_colorize(f"{errmsg_indent}FAIL: ",
                                 Style.BRIGHT, TestConfig.ColorScheme.FAIL) + str(condition)
        elif isinstance(condition, TestError):
            msg = maybe_colorize(f"{errmsg_indent}ERROR: ",
                                 Style.BRIGHT, TestConfig.ColorScheme.ERROR) + str(condition)
        elif isinstance(condition, TestWarning):
            msg = maybe_colorize(f"{errmsg_indent}WARNING: ",
                                 Style.BRIGHT, TestConfig.ColorScheme.WARNING) + str(condition)
        # So any other signal must come from another source.
        else:
            if not _threadlocals.catch_uncaught_signals[0]:
                return  # cancel and delegate to the next outer handler
            # To highlight the error in the summary, count it as an errored test.
            _update(tests_run, +1)
            _update(tests_errored, +1)
            msg = maybe_colorize(f"{errmsg_indent}Testset received signal outside test[]: ",
                                 Style.BRIGHT, TestConfig.ColorScheme.ERROR) + describe_exception(condition)
        TestConfig.printer(msg)

        # the custom callback
        if _threadlocals.postproc_stack:
            r = _threadlocals.postproc_stack[0]
        elif TestConfig.postproc is not None:  # the global default is shared across all threads.
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
        _threadlocals.postproc_stack.appendleft(postproc)

    # The test[] macro signals a condition (using `cerror`), does not raise an
    # exception. That gives it the superpower to resume the rest of the tests.
    try:
        with handlers((Exception, print_and_proceed)):
            yield
    except TestSessionExit:  # pass through, it belongs to session, not us
        pass
    except Exception as err:
        # To highlight the error in the summary, count it as an errored test.
        _update(tests_run, +1)
        _update(tests_errored, +1)
        msg = maybe_colorize(f"{errmsg_indent}Testset terminated by exception outside test[]: ",
                             Style.BRIGHT, TestConfig.ColorScheme.ERROR)
        msg += describe_exception(err)
        TestConfig.printer(msg)
    finally:
        if postproc is not None:
            _threadlocals.postproc_stack.popleft()
        _threadlocals.nesting_level -= 1
        assert _threadlocals.nesting_level >= 0

        r2, f2, e2, w2 = counters()
        runs = r2 - r1
        fails = f2 - f1
        errors = e2 - e1
        warns = w2 - w1

        msg = (maybe_colorize(f"{title} ", TestConfig.ColorScheme.HEADING) +
               maybe_colorize("END", Style.BRIGHT, TestConfig.ColorScheme.HEADING) +
               maybe_colorize(": ", TestConfig.ColorScheme.HEADING) +
               summarize(runs, fails, errors, warns))
        TestConfig.printer(msg)
