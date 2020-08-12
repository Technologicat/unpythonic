# -*- coding: utf-8 -*-
"""Utilities for testing.

The `test[]` macro allows to write unit tests for macro-enabled code, in a
compact assert-like syntax, while letting the rest of the tests run even if
some tests fail.
"""

from ...syntax import (macros, test,  # noqa: F401
                       tests_run, tests_failed, tests_errored,
                       TestFailure, TestError)

from functools import partial

from ...test.fixtures import start, testset, summary  # noqa: F401

from ...conditions import invoke, handlers, restarts
from ...misc import raisef

def runtests():
    # Simple error reporter, just for a demonstration.
    #
    # If we don't need to configure which restart to invoke after the error has
    # been reported, `report` could take just the `err` argument.
    def report(the_restart, err):
        # print(err, file=sys.stderr)  # or log or whatever
        invoke(the_restart)
    report_and_proceed = partial(report, "proceed")

    # Basic usage.
    #
    # A `with handlers` block around the tests is mandatory. Without it,
    # `test[]` will raise `ControlError` when the condition system detects that
    # the cerror (correctable error, signaled by `test[]`) was not handled.
    #
    # (Only the client code can know what to do with the error, so `test[]`
    #  cannot automatically write the `with handlers` block for us.)
    with handlers((TestFailure, report_and_proceed)):
        test[2 + 2 == 5]  # fails, but allows further tests to continue
        test[2 + 2 == 4]
        test[17 + 23 == 40, "my named test"]
    # One wouldn't normally use `assert` in a test module that uses `test[]`,
    # but we have to test `test[]` itself somehow.
    assert tests_run == 3  # we use the type pun that a box is equal to its content.
    assert tests_failed == 1
    assert tests_errored == 0

    # By setting up our own restart, we can skip the rest of a block of tests.
    #
    # The handler can be overridden locally. This works, because the
    # dynamically most recently bound handler for the same signal type wins
    # (see `unpythonic.conditions`).
    #
    # We can reset the counters by sending a new value into the box.
    tests_failed << 0
    tests_errored << 0
    tests_run << 0
    report_and_skip = partial(report, "skip")
    with handlers(((TestFailure, TestError), report_and_proceed)):
        test[2 + 2 == 5]  # fails, but allows further tests to continue

        with restarts(skip=(lambda: None)):  # just for control, no return value
            with handlers(((TestFailure, TestError), report_and_skip)):
                test[2 + 2 == 6]  # --> fails, skips the rest of this block
                test[2 + 2 == 7]  # not reached

        test[2 + 2 == 8]  # fails, but allows further tests to continue
        test[2 + 2 == 9]
    assert tests_run == 4
    assert tests_failed == 4
    assert tests_errored == 0

    # The test machinery counts an uncaught exception inside a test expr as an error
    # (i.e. the test did not run to completion), not a failure.
    tests_failed << 0
    tests_errored << 0
    tests_run << 0
    with handlers(((TestFailure, TestError), report_and_proceed)):
        test[raisef(RuntimeError)]  # errors out, but allows further tests to continue
        test[2 + 2 == 4]
        test[17 + 23 == 40, "my named test"]
    assert tests_run == 3
    assert tests_failed == 0
    assert tests_errored == 1

    # # Syntactic sugar for creating testsets.
    # # Testsets resume upon failure automatically, and also count passes,
    # # fails and errors automatically (no need to reset counters).
    # #
    # # Just be sure to run all `test[]` invocations in the same thread,
    # # because the counters (managed by `test[]` itself) are global.
    # #
    # # Testing can begin with a banner.
    # start()
    #
    # with testset():
    #     test[2 + 2 == 4]
    #     test[2 + 2 == 5]
    #
    # # Testsets can be named.
    # with testset("my fancy tests"):
    #     test[2 + 2 == 4]
    #     test[raisef(RuntimeError)]
    #     test[2 + 2 == 6]
    #
    # # A final summary for all tests can also be printed.
    # # (This counts also tests that did not participate in a testset.)
    # summary()

    print("All tests PASSED")

if __name__ == '__main__':
    runtests()
