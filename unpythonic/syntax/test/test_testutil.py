# -*- coding: utf-8 -*-
"""Utilities for testing.

The `test[]` macro allows to write unit tests for macro-enabled code, in a
compact assert-like syntax, while letting the rest of the tests run even if
some tests fail.
"""

from ...syntax import macros, test  # noqa: F401

from functools import partial

from ...dynassign import dyn
from ...conditions import handlers, invoke, restarts

def runtests():
    # Simple error reporter, just for a demonstration.
    #
    # If we don't need to configure which restart to invoke after the error has
    # been reported, `report` could take just the `err` argument.
    errors = 0
    def report(the_restart, err):
        nonlocal errors
        errors += 1
        # print(err, file=sys.stderr)  # or log or whatever
        invoke(the_restart)
    report_and_proceed = partial(report, "proceed")

    # Basic usage.
    with dyn.let(test_signal_errors=True):  # use conditions instead of exceptions
        with handlers((AssertionError, report_and_proceed)):
            test[2 + 2 == 5]  # fails, but allows further tests to continue
            test[2 + 2 == 4]
            test[17 + 23 == 40, "my named test"]
    assert errors == 1

    # By setting up our own restart, we can skip the rest of a block of tests.
    #
    # The handler can be overridden locally. This works, because the
    # dynamically most recently bound handler for the same signal type wins
    # (see `unpythonic.conditions`).
    errors = 0
    report_and_skip = partial(report, "skip")
    with dyn.let(test_signal_errors=True):  # use conditions instead of exceptions
        with handlers((AssertionError, report_and_proceed)):
            test[2 + 2 == 5]  # fails, but allows further tests to continue

            with restarts(skip=(lambda: None)):  # just for control, no return value
                with handlers((AssertionError, report_and_skip)):
                    test[2 + 2 == 6]  # --> fails, skips the rest of this block
                    test[2 + 2 == 7]  # not reached

            test[2 + 2 == 8]  # fails, but allows further tests to continue
            test[2 + 2 == 9]
    assert errors == 4

    print("All tests PASSED")

if __name__ == '__main__':
    runtests()
