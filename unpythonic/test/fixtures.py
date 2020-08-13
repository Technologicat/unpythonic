# -*- coding: utf-8; -*-
"""A simplistic testing framework for macro-enabled Python code.

This is an 80% solution. Hopefully it's the 80% you need.

We provide just enough of the very basics of a testing framework to get
rudimentary test reports for macro-enabled Python code, particularly
`unpythonic` itself (see issue #5).

This also demonstrates how to build a simple testing framework on top of the
`test[]` macro.

We can't use `unittest` due to some of `unpythonic`'s constructs having the
same name as the module hosting the construct. (This is an issue in `unpythonic`
specifically, see issue #44.)

We can't use the otherwise excellent `pytest`, because in order to get the nice
syntax that redefines `assert`, it has to install an import hook, and in doing
so disables the macro expander. (This is a problem shared by all macro-enabled
Python code.)

So just like everything else in this project, we roll our own. What's a testing
framework or two among friends?

See:
    https://github.com/Technologicat/unpythonic/issues/5
    https://github.com/Technologicat/unpythonic/issues/44
"""

from contextlib import contextmanager
from functools import partial
import sys

from ..syntax.testutil import tests_run, tests_failed, tests_errored, TestFailure, TestError, describe_exception
from ..conditions import handlers, find_restart, invoke

__all__ = ["testset", "terminate", "TestConfig"]

# TODO: Move the general color stuff (TC, colorize) to another module, it could be useful.
# TODO: Consider implementing the \x1b variant that comes with 256 colors
# TODO: and does not rely on a palette.
class TC:
    """Terminal colors, via ANSI escape sequences.

    This uses the terminal app palette (16 colors), so e.g. GREEN2 may actually
    be blue, depending on the user's color scheme.

    The colors are listed in palette order.

    See:
        https://en.wikipedia.org/wiki/ANSI_escape_code#SGR_(Select_Graphic_Rendition)_parameters
        https://stackoverflow.com/questions/287871/print-in-terminal-with-colors
    """
    END = '\33[0m'  # return to normal state, ending colorization
    BOLD = '\33[1m'
    ITALIC = '\33[3m'
    URL = '\33[4m'  # underline plus possibly a special color (depends on terminal app)
    BLINK = '\33[5m'
    BLINK2 = '\33[6m'  # same effect as BLINK?
    SELECTED = '\33[7m'

    BLACK = '\33[30m'
    RED = '\33[31m'
    GREEN = '\33[32m'
    YELLOW = '\33[33m'
    BLUE = '\33[34m'
    VIOLET = '\33[35m'
    BEIGE = '\33[36m'
    WHITE = '\33[37m'

    GREY = '\33[90m'
    RED2 = '\33[91m'
    GREEN2 = '\33[92m'
    YELLOW2 = '\33[93m'
    BLUE2 = '\33[94m'
    VIOLET2 = '\33[95m'
    BEIGE2 = '\33[96m'
    WHITE2 = '\33[97m'

    BLACKBG = '\33[40m'
    REDBG = '\33[41m'
    GREENBG = '\33[42m'
    YELLOWBG = '\33[43m'
    BLUEBG = '\33[44m'
    VIOLETBG = '\33[45m'
    BEIGEBG = '\33[46m'
    WHITEBG = '\33[47m'

class TestConfig:
    """Global settings for the testing utilities.

    If you want to change the settings, just assign new values to the attributes
    at any point in your test script (the new values will take effect from that
    point forward). Probably the least confusing if done before calling `start()`.

    `printer`:   str -> None; side effect should be to display the string somehow.
                 Default is to `print` to `sys.stderr`.
    `use_color`: bool; use ANSI color escape sequences to colorize `printer` output.
                 Default is `True`.
    `postproc`:  Exception -> None; optional.
    `CS`:        The color scheme.

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

    class CS:
        """The color scheme.

        See the constants in the class `TC` for valid values.

        The defaults are designed to fit the "Solarized" theme of `gnome-terminal`,
        with "Show bold text in bright colors" set to OFF.
        """
        HEADING = TC.BLUE2
        PASS = TC.GREEN
        FAIL = TC.RED2
        ERROR = TC.YELLOW
        GREYED_OUT = TC.YELLOW2  # in that theme, actually grey
        # These colors are used for the pass percentage.
        SUMMARY_OK = TC.GREEN
        SUMMARY_NOTOK = TC.YELLOW  # more readable than red on a dark background, yet stands out.

def colorize(s, *colors):
    """Colorize string `s` for ANSI terminal display.

    No-op (return `s`) if `TestConfig.use_color` is falsey.

    Usage::

        colorize("I'm new here", TC.GREEN)
        colorize("I'm bold and bluetiful", TC.BOLD, TC.BLUE)
    """
    if not TestConfig.use_color:
        return s
    COMMANDS = "".join(colors)
    return "{}{}{}".format(COMMANDS, s, TC.END)

def summarize(runs, fails, errors):
    """Return a human-readable summary of passes, fails, errors, and the total number of tests run.

    `runs`, `fails`, `errors` are nonnegative integers that report the count
    of what it says on the tin.

    If `use_color` is truthy, use ANSI terminal colors and bolding.
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
    snippets.extend([colorize("Pass", TC.BOLD, color),
                     " ",
                     colorize("{}".format(passes), color),
                     colorize(", ", TestConfig.CS.HEADING)])
    color = TestConfig.CS.FAIL if fails else TestConfig.CS.GREYED_OUT
    snippets.extend([colorize("Fail", TC.BOLD, color),
                     " ",
                     colorize("{}".format(fails), color),
                     colorize(", ", TestConfig.CS.HEADING)])
    color = TestConfig.CS.ERROR if errors else TestConfig.CS.GREYED_OUT
    snippets.extend([colorize("Error", TC.BOLD, color),
                     " ",
                     colorize("{}".format(errors), color),
                     colorize(", ", TestConfig.CS.HEADING)])
    color = TestConfig.CS.HEADING if runs else TestConfig.CS.GREYED_OUT
    snippets.extend([colorize("Total", TC.BOLD, color),
                     " ",
                     colorize("{}".format(runs), color)])
    color = TestConfig.CS.SUMMARY_OK if passes == runs else TestConfig.CS.SUMMARY_NOTOK
    snippets.extend([" ",
                     colorize("({}% pass)".format(int(pass_percentage)), TC.BOLD, color)])
    return "".join(snippets)

class TestSessionExit(Exception):
    """Exception, raising which terminates the current test session."""
def terminate(exc):  # the parameter is ignored
    """Terminate the test session.

    This will shut down the program, with an exit code of 255.

    This can be used as a `postproc`, if you want a failure in a particular
    testset to abort the whole unit.
    """
    TestConfig.printer(colorize("** TERMINATING SESSION", TC.BOLD, TestConfig.CS.HEADING))
    raise TestSessionExit

_nesting_level = 0
@contextmanager
def session(name=None):
    """Context manager representing a test session."""
    if _nesting_level > 0:
        raise RuntimeError("A test `session` cannot be nested inside a `testset`.")

    r1 = tests_run.get()
    f1 = tests_failed.get()
    e1 = tests_errored.get()

    title = colorize("** SESSION", TC.BOLD, TestConfig.CS.HEADING)
    if name is not None:
        title += colorize(" '{}'".format(name), TC.ITALIC, TestConfig.CS.HEADING)
    TestConfig.printer(colorize("{} ".format(title), TestConfig.CS.HEADING) +
                       colorize("BEGIN", TC.BOLD, TestConfig.CS.HEADING))

    # We are paused when the user triggers the exception; `contextlib` detects the
    # exception and re-raises it into us.
    try:
        yield
    except TestSessionExit:
        pass

    r2 = tests_run.get()
    f2 = tests_failed.get()
    e2 = tests_errored.get()

    runs = r2 - r1
    fails = f2 - f1
    errors = e2 - e1
    TestConfig.printer(colorize("{} ".format(title), TestConfig.CS.HEADING) +
                       colorize("END", TC.BOLD, TestConfig.CS.HEADING) +
                       colorize(": ", TestConfig.CS.HEADING) +
                       summarize(runs, fails, errors))

# We use a stack for postprocs so that the local overrides can be nested.
_postproc_stack = []
@contextmanager
def testset(name=None, postproc=None):
    """Context manager representing a test set.

    Automatically computes passes, fails, errors, total, and the pass percentage.

    `name` is an optional string specifying a human-readable name for the testset.
    If not given, the testset is not named.

    `postproc` is like `TestConfig.postproc`, but overriding that for this test set
    (and any testsets contained within this one, unless they specify their own).

    **Usage**, a.k.a. unpythonic testing 101::

        from unpythonic.syntax import macros, test
        from unpythonic.test.fixtures import session, testset

        with session():
            with testset():
                test[...]
                test[...]

            with testset("my fancy tests"):
                test[...]
                test[...]

    **CAUTION**: Not thread-safe. The `test[...]` invocations should be made from
    a single thread, because `test[]` uses global counters to track runs/fails/errors.
    """
    r1 = tests_run.get()
    f1 = tests_failed.get()
    e1 = tests_errored.get()

    global _nesting_level
    _nesting_level += 1
    stars = "*" * (2 * (1 + _nesting_level))

    title = "{} Testset".format(stars)
    if name is not None:
        title += colorize(" '{}'".format(name), TC.ITALIC)
    TestConfig.printer(colorize("{} ".format(title), TestConfig.CS.HEADING) +
                       colorize("BEGIN", TC.BOLD, TestConfig.CS.HEADING))

    def report_and_proceed(condition):
        # The assert helpers in `unpythonic.syntax.testutil` signal only TestFailure and TestError,
        # no matter what happens inside the test expression.
        if isinstance(condition, TestFailure):
            msg = colorize("{}** FAIL: ".format(stars), TC.BOLD, TestConfig.CS.FAIL) + str(condition)
        elif isinstance(condition, TestError):
            msg = colorize("{}** ERROR: ".format(stars), TC.BOLD, TestConfig.CS.ERROR) + str(condition)
        # So any other signal must come from another source.
        else:
            msg = colorize("{}** Testset received signal outside test[]: ".format(stars), TC.BOLD, TestConfig.CS.ERROR) + describe_exception(condition)
        TestConfig.printer(msg)

        # the custom callback
        if _postproc_stack:
            r = _postproc_stack[-1]
        elif TestConfig.postproc is not None:
            r = TestConfig.postproc
        else:
            r = None
        if r is not None:
            r(condition)

        # We find first instead of just invoking so that we support all standard signal
        # protocols, not just `cerror` (which defines "proceed").
        p = find_restart("proceed")
        if p is not None:
            invoke(p)
        # Otherwise we just return normally.

    if postproc is not None:
        _postproc_stack.append(postproc)

    # The test[] macro signals a condition (using `cerror`), does not raise an
    # exception. That gives it the superpower to resume the rest of the tests.
    try:
        with handlers((Exception, report_and_proceed)):
            yield
    except TestSessionExit:  # pass through, it belongs to session, not us
        pass
    except Exception as err:
        msg = colorize("{}** Testset terminated by exception outside test[]: ".format(stars), TC.BOLD, TestConfig.CS.ERROR)
        msg += describe_exception(err)
        TestConfig.printer(msg)

    if postproc is not None:
        _postproc_stack.pop()

    _nesting_level -= 1
    assert _nesting_level >= 0

    r2 = tests_run.get()
    f2 = tests_failed.get()
    e2 = tests_errored.get()

    runs = r2 - r1
    fails = f2 - f1
    errors = e2 - e1
    TestConfig.printer(colorize("{} ".format(title), TestConfig.CS.HEADING) +
                       colorize("END", TC.BOLD, TestConfig.CS.HEADING) +
                       colorize(": ", TestConfig.CS.HEADING) +
                       summarize(runs, fails, errors))
