# -*- coding: utf-8 -*-
"""Utilities for writing tests."""

from macropy.core.quotes import macros, q, u, ast_literal
from macropy.core.hquotes import macros, hq  # noqa: F811, F401
from macropy.core import unparse

from ast import Tuple, Str

from ..misc import callsite_filename, raisef
from ..conditions import cerror, handlers, restarts, invoker
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

class TestingException(Exception):
    """Base type for testing-related exceptions."""
class TestFailure(TestingException):
    """Exception type indicating that a test failed."""
class TestError(TestingException):
    """Exception type indicating that a test did not run to completion.

    This can happen due to an unexpected exception, or an unhandled
    `error` (or `cerror`) condition.
    """

# Regular functions.
def describe_exception(e):
    assert isinstance(e, BaseException)
    msg = str(e)
    if msg:
        desc = "{} with message '{}'".format(type(e), msg)
    else:
        desc = "{}".format(type(e))
    if e.__cause__ is not None:  # raise ... from ...
        return desc + ", directly caused by {}".format(describe_exception(e.__cause__))
    return desc

def unpythonic_assert(sourcecode, thunk, filename, lineno, myname=None):
    """Custom assert function, for building test frameworks.

    Upon a failing assertion, this will *signal* a `TestFailure` as a
    *cerror* (correctable error), via unpythonic's condition system (see
    `unpythonic.conditions.cerror`).

    If a test fails to run to completion due to an unexpected exception or an
    unhandled `error` (or `cerror`) condition, `TestError` is signaled,
    so the caller can easily tell apart which case occurred.

    Using conditions allows the surrounding code to install a handler that
    invokes the `proceed` restart, so upon a test failure, any further tests
    still continue to run::

        from unpythonic.syntax import (macros, test,
                                       tests_run, tests_failed, tests_errored,
                                       TestFailure, TestError)

        import sys
        from unpythonic import invoke, handlers

        def report(err):
            print(err, file=sys.stderr)  # or log or whatever
            invoke("proceed")

        with handlers(((TestFailure, TestError), report)):
            test[2 + 2 == 5]  # fails, but allows further tests to continue
            test[2 + 2 == 4]
            test[17 + 23 == 40, "my named test"]

        # One wouldn't normally use `assert` in a test module that uses `test[]`.
        # This is just to state that in this example, we expect these to hold.
        assert tests_failed == 1  # we use the type pun that a box is equal to its content.
        assert tests_errored == 0
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
    title = "Test" if myname is None else "Named test '{}'".format(myname)
    try:
        if thunk():
            return
    except Exception as err:  # including ControlError raised by an unhandled `unpythonic.conditions.error`
        tests_errored << tests_errored.get() + 1
        conditiontype = TestError
        desc = describe_exception(err)
        error_msg = "{} errored: {}, due to unexpected exception {}".format(title, sourcecode, desc)
    else:
        tests_failed << tests_failed.get() + 1
        conditiontype = TestFailure
        error_msg = "{} failed: {}".format(title, sourcecode)

    complete_msg = "[{}:{}] {}".format(filename, lineno, error_msg)

    # We use cerror() to signal a failed/errored test, instead of raising an
    # exception, so the client code can resume (after logging the failure and
    # such).
    #
    # If the client code does not install a handler, then a `ControlError`
    # exception is raised by the condition system; leaving a cerror unhandled
    # is an error.
    cerror(conditiontype(complete_msg))

def unpythonic_assert_raises(exctype, sourcecode, thunk, filename, lineno, myname=None):
    """Like `unpythonic_assert`, but assert that running `sourcecode` raises `exctype`."""
    tests_run << tests_run.get() + 1
    title = "Test" if myname is None else "Named test '{}'".format(myname)
    try:
        thunk()
        tests_failed << tests_failed.get() + 1
        conditiontype = TestFailure
        error_msg = "{} failed: did not raise expected exception {}: {}".format(title, exctype, sourcecode)
    except Exception as err:  # including ControlError raised by an unhandled `unpythonic.conditions.error`
        if isinstance(err, exctype):
            return  # the expected exception, all ok!
        tests_errored << tests_errored.get() + 1
        conditiontype = TestError
        desc = describe_exception(err)
        error_msg = "{} errored: {}, due to unexpected exception {}".format(title, sourcecode, desc)

    complete_msg = "[{}:{}] {}".format(filename, lineno, error_msg)
    cerror(conditiontype(complete_msg))

def unpythonic_assert_signals(exctype, sourcecode, thunk, filename, lineno, myname=None):
    """Like `unpythonic_assert`, but assert that running `sourcecode` signals `exctype`.

    "Signal" as in `unpythonic.conditions.signal` and its sisters `error`, `cerror`, `warn`.
    """
    class UnexpectedSignal(Exception):
        def __init__(self, exc):
            self.exc = exc
    tests_run << tests_run.get() + 1
    title = "Test" if myname is None else "Named test '{}'".format(myname)
    try:
        with restarts(_unpythonic_assert_signals_success=lambda: None,  # no value, for control only
                      _unpythonic_assert_signals_error=lambda exc: raisef(UnexpectedSignal(exc))):
            with handlers((exctype, invoker("_unpythonic_assert_signals_success")),
                          (Exception, invoker("_unpythonic_assert_signals_error"))):
                thunk()
            # We only reach this point if the success restart was not invoked,
            # i.e. if thunk() completed normally.
            tests_failed << tests_failed.get() + 1
            conditiontype = TestFailure
            error_msg = "{} failed: did not signal expected condition {}: {}".format(title, exctype, sourcecode)
            complete_msg = "[{}:{}] {}".format(filename, lineno, error_msg)
            cerror(conditiontype(complete_msg))
        return  # expected condition signaled, all ok!
    # some other condition signaled
    except UnexpectedSignal as err:
        tests_errored << tests_errored.get() + 1
        conditiontype = TestError
        desc = describe_exception(err)
        error_msg = "{} errored: {}, due to unexpected signal {}".format(title, sourcecode, desc)
        complete_msg = "[{}:{}] {}".format(filename, lineno, error_msg)
        cerror(conditiontype(complete_msg))
    # unexpected exception raised
    except Exception as err:  # including ControlError raised by an unhandled `unpythonic.conditions.error`
        tests_errored << tests_errored.get() + 1
        conditiontype = TestError
        desc = describe_exception(err)
        error_msg = "{} errored: {}, due to unexpected exception {}".format(title, sourcecode, desc)
        complete_msg = "[{}:{}] {}".format(filename, lineno, error_msg)
        cerror(conditiontype(complete_msg))

# TODO: add test_raises, test_signals

# Syntax transformers.
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
