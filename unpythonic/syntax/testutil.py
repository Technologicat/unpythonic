# -*- coding: utf-8 -*-
"""Utilities for writing tests."""

from macropy.core.quotes import macros, q, u, ast_literal
from macropy.core.hquotes import macros, hq  # noqa: F811, F401
from macropy.core import unparse

from ast import Tuple, Str

from ..misc import callsite_filename
from ..conditions import cerror
from ..collections import box

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

# Just a regular function.
def unpythonic_assert(sourcecode, thunk, filename, lineno, myname=None):
    """Custom assert function, for building test frameworks.

    Upon a failing assertion, this will *signal* the `AssertionError` as a
    *cerror* (correctable error), via unpythonic's condition system (see
    `unpythonic.conditions.cerror`).

    This allows the surrounding code to install a handler that invokes
    the `proceed` restart, so upon a test failure, any further tests
    still continue to run::

        from unpythonic.syntax import macros, test, tests_run, tests_failed

        import sys
        from unpythonic import invoke, handlers

        def report(err):
            print(err, file=sys.stderr)  # or log or whatever
            invoke("proceed")

        with handlers((AssertionError, report)):
            test[2 + 2 == 5]  # fails, but allows further tests to continue
            test[2 + 2 == 4]
            test[17 + 23 == 40, "my named test"]

        # One wouldn't normally use `assert` in a test module that uses `test[]`.
        # This is just to state that in this example, we expect these to hold.
        assert tests_failed == 1  # we use the type pun that a box is equal to its content.
        assert tests_run == 3

    Parameters:

        `sourcecode` is a string representation of the source code expression
        that is being asserted.

        `thunk` is the expression itself, delayed by a lambda, so that this
        function can run the expression at its leisure. If the result of
        running the lambda is falsey, the assertion fails.

        `filename` is the filename at the call site, if applicable. (If called
        from the REPL, there is no file.)

        `lineno` is the line number at the call site.

        These are best extracted automatically using the `test[]` macro.

        `myname` is an optional string, a name for the assertion being performed.
        It can be used for naming individual tests. The assertion error message
        is either "Named assertion 'foo bar' failed" or "Assertion failed",
        depending on whether `myname` was provided or not.

    No return value.
    """
    tests_run << tests_run.get() + 1

    def describe_exception(e):
        assert isinstance(e, BaseException)
        msg = str(e)
        if msg:
            desc = "{} with message '{}'".format(type(e), msg)
        else:
            desc = "{}".format(type(e))
        if e.__cause__ is not None:  # raise ... from ...
            return desc + ", directly caused by earlier exception {}".format(describe_exception(e.__cause__))
        return desc

    title = "Assertion" if myname is None else "Named assertion '{}'".format(myname)
    try:
        if thunk():
            return
    except Exception as err:  # including ControlError raised by an unhandled `unpythonic.conditions.error`
        tests_errored << tests_errored.get() + 1
        desc = describe_exception(err)
        error_msg = "{} errored: {}, due to uncaught exception {}".format(title, sourcecode, desc)
    else:
        tests_failed << tests_failed.get() + 1
        error_msg = "{} failed: {}".format(title, sourcecode)

    complete_msg = "[{}:{}] {}".format(filename, lineno, error_msg)

    # TODO: Signal some other condition type when a test errors, so the caller
    # TODO: can easily tell it apart from a test failure. RuntimeError?

    # We use cerror() to signal a failed/errored test, instead of raising an
    # exception, so the client code can resume (after logging the failure and
    # such).
    #
    # If the client code does not install a handler, then a `ControlError`
    # exception is raised by the condition system; leaving a cerror unhandled
    # is an error.
    cerror(AssertionError(complete_msg))

# The syntax transformer.
def test(tree):
    ln = q[u[tree.lineno]] if hasattr(tree, "lineno") else q[None]
    filename = hq[callsite_filename()]
    asserter = hq[unpythonic_assert]

    # test[expr, "name of this test"]  (like assert expr, name)
    # TODO: Python 3.8+: ast.Constant, no ast.Str
    if type(tree) is Tuple and len(tree.elts) == 2 and type(tree.elts[1]) is Str:
        tree, myname = tree.elts
    # test[expr]  (like assert expr)
    else:
        myname = q[None]

    # The lambda delays the execution of the test expr until `unpythonic_assert` gets control.
    return q[(ast_literal[asserter])(u[unparse(tree)],
                                     lambda: ast_literal[tree],
                                     filename=ast_literal[filename],
                                     lineno=ast_literal[ln],
                                     myname=ast_literal[myname])]
