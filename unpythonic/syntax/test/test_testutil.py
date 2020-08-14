# -*- coding: utf-8 -*-
"""Utilities for testing.

The `test[]` macro allows to write unit tests for macro-enabled code, in a
compact assert-like syntax, while letting the rest of the tests run even if
some tests fail.
"""

from ...syntax import (macros, test, test_signals, test_raises,  # noqa: F401
                       tests_run, tests_failed, tests_errored,
                       TestFailure, TestError)

from functools import partial

from ...test.fixtures import session, testset, terminate  # noqa: F401

from ...conditions import invoke, handlers, restarts, cerror  # noqa: F401
from ...misc import raisef

def runtests():
    # Low-level machinery.

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

    # High-level machinery: unpythonic.test.fixtures, a testing framework.
    #
    #   - Automatically resume testing upon failure or error, if possible
    #   - Automatically count passes, fails and errors, summarize totals
    #   - Print nicely colored ANSI terminal output into `sys.stderr`
    #   - Don't need to care that it's implemented with conditions and restarts
    #
    # Still, be sure to run all `test[]` invocations in the same thread,
    # because the counters (managed by `test[]` itself) are global.

    # # The session construct provides an exit point for test session
    # # termination, and an implicit top-level testset.
    # # A session can be started only when not already inside a testset.
    # with session("framework demo"):
    #     # A session may contain bare tests. They are implicitly part of the
    #     # top-level testset.
    #     test[2 + 2 == 4]
    #     test[2 + 2 == 5]
    #
    #     # Tests can be further grouped into testsets, if desired.
    #     with testset():
    #         test[2 + 2 == 4]
    #         test[2 + 2 == 5]
    #
    #     # Testsets can be named. The name is printed in the output.
    #     with testset("my fancy tests"):
    #         test[2 + 2 == 4]
    #         test[raisef(RuntimeError)]  # exceptions are caught.
    #         test[cerror(RuntimeError)]  # signals are caught, too.
    #         test[2 + 2 == 6]
    #
    #         # A testset reports also any stray signals or exceptions it receives
    #         # from outside a `test[]` construct.
    #         #
    #         # - When a signal arrives via `cerror`, the testset resumes.
    #         # - When some other signal protocol is used (no "proceed" restart
    #         #   is in scope), the handler returns normally; what then happens
    #         #   depends on which signal protocol it is.
    #         # - When an exception is caught, the testset terminates, because
    #         #   exceptions do not support resuming.
    #         cerror(RuntimeError("blargh"))
    #         raise RuntimeError("gargle")
    #
    #     # Testsets can be nested.
    #     with testset("outer"):
    #         with testset("inner 1"):
    #             test[2 + 2 == 4]
    #         with testset("inner 2"):
    #             test[2 + 2 == 4]
    #         with testset("inner 3"):
    #             pass
    #
    #     with testset("test_raises"):
    #         test_raises[RuntimeError, raisef(RuntimeError)]
    #         test_raises[RuntimeError, 2 + 2 == 4]
    #         test_raises[RuntimeError, raisef(ValueError)]
    #
    #     with testset("test_signals"):
    #         test_signals[RuntimeError, cerror(RuntimeError)]
    #         test_signals[RuntimeError, 2 + 2 == 4]
    #         test_signals[RuntimeError, cerror(ValueError)]
    #
    #     with testset("nested exceptions"):
    #         with testset("raise from"):
    #             try:
    #                 raise ValueError
    #             except ValueError as e:
    #                 raise RuntimeError from e
    #
    #         with testset("just chain them"):
    #             try:
    #                 raise ValueError
    #             except ValueError:
    #                 raise RuntimeError
    #
    #     # # The session can be terminated early by calling terminate()
    #     # # at any point inside the dynamic extent of `with session`.
    #     # # This causes the `with session` to exit immediately.
    #     # terminate()
    #
    #     # The session can also be terminated by the first failure in a
    #     # particular testset by using `terminate` as the `postproc`:
    #     with testset(postproc=terminate):
    #         test[2 + 2 == 5]
    #         test[2 + 2 == 4]

    print("All tests PASSED")

if __name__ == '__main__':
    runtests()
