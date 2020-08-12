# -*- coding: utf-8; -*-
"""Unit test utilities for general use.

This is, by necessity, only an 80% solution. Hope it's the 80% you need.

We provide just enough of the very basics of a testing framework to get
rudimentary test reports for macro-enabled Python code, particularly
`unpythonic` itself.

We can't use `unittest` due to some of `unpythonic`'s constructs having the
same name as the module hosting the construct. (This is an issue in `unpythonic`
specifically, see issue #44.)

We can't use the otherwise excellent `pytest`, because in order to get the nice
syntax that redefines `assert`, it has to install an import hook, and doing so
disables the macro expander.

So just like everything else in this project, we roll our own.

See:
    https://github.com/Technologicat/unpythonic/issues/5
    https://github.com/Technologicat/unpythonic/issues/44
"""

from contextlib import contextmanager
import sys

from ..syntax.testutil import tests_run, tests_failed, tests_errored
from ..conditions import handlers, invoke

__all__ = ["testset", "summary"]

# TODO: Move the color stuff to another module, it could be generally useful.
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

def colorize(s, *colors):
    """Colorize string `s` for ANSI terminal display.

    Usage::

        colorize("I'm new here", TC.GREEN)
        colorize("I'm bold and bluetiful", TC.BOLD, TC.BLUE)
    """
    start_sequence = "".join(colors)
    return "{}{}{}".format(start_sequence, s, TC.END)

# TODO: Colors are currently hardcoded to fit the "Solarized" theme of
# TODO: `gnome-terminal`, with "Show bold text in bright colors" OFF.
# TODO: Abstract this a bit to define a heading color, pass color,
# TODO: fail color, error color, inactive color...
def summarize(runs, fails, errors, color=False):
    """Return a human-readable summary of passes, fails, errors, and the total number of tests run.

    `runs`, `fails`, `errors` are nonnegative integers that report the count
    of what it says on the tin.

    If `color` is truthy, use ANSI terminal colors and bolding.
    """
    passes = runs - fails - errors
    if runs:
        fail_ratio = fails / runs
        error_ratio = errors / runs
    else:
        fail_ratio = error_ratio = 0.0
    pass_ratio = 1 - fail_ratio - error_ratio
    pass_percentage = 100 * pass_ratio

    if not color:
        return "Pass {}, Fail {}, Error {}, Total {} ({:0.2g}% pass)".format(passes,
                                                                             pass_percentage,
                                                                             fails,
                                                                             errors,
                                                                             runs)
    # The same in techni... ANSI color:
    snippets = []
    thecolor = TC.GREEN if passes else TC.YELLOW2
    snippets.extend([colorize("Pass", TC.BOLD, thecolor),
                     " ",
                     colorize("{}".format(passes), thecolor),
                     colorize(", ", TC.BLUE2)])
    thecolor = TC.RED2 if fails else TC.YELLOW2
    snippets.extend([colorize("Fail", TC.BOLD, thecolor),
                     " ",
                     colorize("{}".format(fails), thecolor),
                     colorize(", ", TC.BLUE2)])
    thecolor = TC.YELLOW if errors else TC.YELLOW2
    snippets.extend([colorize("Error", TC.BOLD, thecolor),
                     " ",
                     colorize("{}".format(errors), thecolor),
                     colorize(", ", TC.BLUE2)])
    thecolor = TC.BLUE2 if runs else TC.YELLOW2
    snippets.extend([colorize("Total", TC.BOLD, thecolor),
                     " ",
                     colorize("{}".format(runs), thecolor)])
    thecolor = TC.GREEN if passes == runs else TC.YELLOW
    snippets.extend([" ",
                     colorize("({:0.2g}% pass)".format(pass_percentage), TC.BOLD, thecolor)])
    return "".join(snippets)

@contextmanager
def testset(name=None, reporter=None):
    """Context manager representing a test set.

    Automatically computes passes, fails, errors, total, and the pass percentage.

    `name` is an optional string specifying a human-readable name for the testset.
    If not given, the testset is not named.

    The optional `reporter` specifies a custom *condition handler*. It receives
    one argument, which is an `AssertionError` instance that was signaled by a
    failed or errored test. It should print or log the error (whatever is
    appropriate), and then `invoke("proceed")` to continue running the
    remaining tests. (See `unpythonic.conditions.invoke`.)

    If you want a failure in this testset to abort the whole unit, you can
    `sys.exit` from the reporter function.

    If not specified, a default reporter is used. The default reporter just
    prints `str(condition)` to `sys.stderr`.

    Usage::

        from unpythonic.syntax import macros, test
        from unpythonic.test.fixtures import testset

        with testset():
            test[...]
            test[...]

        with testset("my fancy tests"):
            test[...]
            test[...]

    **CAUTION**: Not thread-safe. The `test[...]` invocations should be made from
    a single thread, because `test[]` uses a global counter to track runs/fails.

    """
    r1 = tests_run.get()
    f1 = tests_failed.get()
    e1 = tests_errored.get()

    title = "**** Testset"
    if name is not None:
        title += colorize(" '{}'".format(name), TC.ITALIC)
    print(colorize("{} ".format(title), TC.BLUE2) +
          colorize("BEGIN", TC.BLUE2, TC.BOLD),
          file=sys.stderr)

    def report_and_proceed(condition):
        print(str(condition), file=sys.stderr)
        invoke("proceed")

    # The test[] macro signals a condition (using `cerror`), does not raise an
    # exception. That gives it the superpower to resume the rest of the tests.
    with handlers((AssertionError, report_and_proceed)):
        yield

    r2 = tests_run.get()
    f2 = tests_failed.get()
    e2 = tests_errored.get()

    runs = r2 - r1
    fails = f2 - f1
    errors = e2 - e1
    print(colorize("{} ".format(title), TC.BLUE2) +
          colorize("END", TC.BLUE2, TC.BOLD) +
          colorize(": ", TC.BLUE2) +
          summarize(runs, fails, errors, color=True),
          file=sys.stderr)

def summary():
    """Print a final summary of test results.

    **CAUTION**: This also counts tests that did not participate in any `testset`.

    To make your summaries intuitively understandable, consider either placing
    all of your tests into some `testset`, or not using testsets at all.
    """
    runs = tests_run.get()
    fails = tests_failed.get()
    errors = tests_errored.get()
    print(colorize("**** TOTAL: ", TC.BLUE2, TC.BOLD) +
          summarize(runs, fails, errors, color=True),
          file=sys.stderr)
