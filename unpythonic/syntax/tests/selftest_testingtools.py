# -*- coding: utf-8 -*-
"""Self-test of the `unpythonic.test.fixtures` testing framework.

The `test[]` macro allows writing unit tests for macro-enabled code, in a
compact assert-like syntax, while letting the rest of the tests run even
if some tests fail. This file exercises the *low-level machinery* —
the `unpythonic.conditions` plumbing under `test[]`, `test_signals[]`,
`test_raises[]`, etc. — using bare Python `assert` statements. Bare
`assert` is unavoidable here: we can't use `test[]` to verify `test[]`'s
own pass/fail dispatch (circular self-reference), and the `selftest_`
prefix keeps `runtests.py` from picking this module up via its
`test_*.py` discovery glob.

For a worked, running demonstration of the framework's user-facing
features, see the example session in `unpythonic/test/fixtures.py`'s
module docstring, the "simple framework demo" in `README.md`, and the
"Test sessions and testsets" chapter in `doc/macros.md`.

Running this self-test (uses relative macro-imports, so it must be
imported as a module rather than invoked as a script)::

    python -c "import mcpyrate.activate; from unpythonic.syntax.tests.selftest_testingtools import runtests; runtests()"
"""

from ...syntax import macros, test, test_signals, test_raises, fail, error, warn, the, expect  # noqa: F401

from functools import partial

from ...test.fixtures import (session, testset, terminate, returns_normally,  # noqa: F401
                              tests_run, tests_failed, tests_errored,
                              TestFailure, TestError)

from ...conditions import invoke, handlers, restarts, cerror  # noqa: F401
from ...excutil import raisef

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
        test[17 + 23 == 40, "my failure message"]
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
        test[17 + 23 == 40, "my failure message"]
    assert tests_run == 3
    assert tests_failed == 0
    assert tests_errored == 1

    # Test the `the[]` marker, which changes which subexpression has its value
    # captured for test failure message display purposes.
    tests_failed << 0
    tests_errored << 0
    tests_run << 0
    with handlers(((TestFailure, TestError), report_and_proceed)):
        count = 0
        def counter():
            nonlocal count
            count += 1
            return count
        test[counter() < counter()]
        test[the[counter()] < counter()]
        test[counter() < the[counter()]]  # evaluation order not affected
    assert tests_run == 3
    assert tests_failed == 0
    assert tests_errored == 0

    # `expect[]` inside a `with test:` block — the runtime dispatch path.
    # We test that the value of the expression inside `expect[expr]` is what
    # gets asserted, and that both `the[]` capture rules (implicit LHS on a
    # `Compare`, explicit) still apply, the same as they did for the
    # deprecated `return expr` form.
    tests_failed << 0
    tests_errored << 0
    tests_run << 0
    with handlers(((TestFailure, TestError), report_and_proceed)):
        with test:
            a = 21
            expect[a + a == 42]  # passes
        with test:
            b = 1
            expect[b + b == 99]  # fails
        with test:
            # No `expect[]` and no `return`: asserts the block completes normally.
            log = []
            log.append("ran")
        with test:
            # Implicit-LHS capture: no explicit `the[]` anywhere in the block,
            # and `expect[]` wraps a `Compare`, so the LHS is captured for
            # failure reporting. (Effect is only visible on failure.)
            c = 0
            expect[c == 0]
        with test:
            # Explicit `the[]` inside `expect[]` overrides implicit-LHS.
            items = ["a", "b"]
            expect["a" in the[items]]
    assert tests_run == 5
    assert tests_failed == 1
    assert tests_errored == 0

    # # If you want to proceed after most failures, but there is some particularly
    # # critical test which, if it fails, should abort the rest of the whole unit,
    # # you can override the handler locally:
    #
    # def die(err):
    #     print(err, file=sys.stderr)  # or log or whatever
    #     sys.exit(255)
    #
    # with handlers(((TestFailure, TestError), report)):
    #     test[2 + 2 == 5]  # fails, but allows further tests to continue
    #
    #     with handlers(((TestFailure, TestError), die)):
    #         test[2 + 2 == 6]  # --> die
    #         test[17 + 23 == 40, "my failure message"]  # not reached
    #
    #     # if this point was ever reached (currently it's not)...
    #     test[2 + 2 == 7]  # ...this fails, but allows further tests to continue
    #
    # # This works, because the dynamically most recently bound handler for the
    # # same signal type wins (see `unpythonic.conditions`).
    # #
    # # Similarly, if you want to skip the rest of a block of tests upon a failure:
    #
    # from unpythonic.conditions import restarts, invoker
    #
    # with handlers(((TestFailure, TestError), report)):
    #     test[2 + 2 == 5]  # fails, but allows further tests to continue
    #
    #     with restarts(skip=(lambda: None)):  # just for control, no return value
    #         with handlers(((TestFailure, TestError), invoker("skip"))):
    #             test[2 + 2 == 6]  # --> fails, skip the rest of this block
    #             test[17 + 23 == 40, "my failure message"]  # not reached
    #
    #     test[2 + 2 == 7]  # fails, but allows further tests to continue

    print("All tests PASSED")

# Note: no `if __name__ == '__main__': runtests()` — this module uses
# relative macro-imports, so running it as a script fails. Use the
# import-and-call incantation in the module docstring instead.
