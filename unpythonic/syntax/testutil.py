# -*- coding: utf-8 -*-
"""Utilities for writing tests."""

from macropy.core.quotes import macros, q, u, ast_literal, name
from macropy.core.hquotes import macros, hq  # noqa: F811, F401
from macropy.core import unparse

from ast import Tuple, Str

from ..dynassign import dyn  # for MacroPy's gen_sym
from ..misc import callsite_filename
from ..conditions import cerror, handlers, restarts, invoke
from ..collections import box, unbox
from ..symbol import sym
from ..test.fixtures import describe_exception

# -----------------------------------------------------------------------------
# Regular code, no macros yet.

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

_completed = sym("_completed")  # returned normally
_signaled = sym("_signaled")  # via unpythonic.conditions.signal and its sisters
_raised = sym("_raised")  # via raise
def _observe(thunk):
    """Run `thunk` and report how it fared.

    Internal helper for implementing assert functions.

    The return value is:

      - `(_completed, return_value)` if the thunk completed normally
      - `(_signaled, condition_instance)` if a signal from inside
        the dynamic extent of thunk propagated to this level.
      - `(_raised, exception_instance)` if an exception from inside
        the dynamic extent of thunk propagated to this level.
    """
    try:
        with restarts(_got_signal=lambda exc: exc) as sig:
            with handlers((Exception, lambda exc: invoke("_got_signal", exc))):
                ret = thunk()
            # We only reach this point if the restart was not invoked,
            # i.e. if thunk() completed normally.
            return _completed, ret
        return _signaled, unbox(sig)
    except Exception as err:  # including ControlError raised by an unhandled `unpythonic.conditions.error`
        return _raised, err

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
    mode, result = _observe(thunk)
    tests_run << unbox(tests_run) + 1

    title = "Test" if myname is None else "Named test '{}'".format(myname)
    if mode is _completed:
        if result:
            return
        tests_failed << unbox(tests_failed) + 1
        conditiontype = TestFailure
        error_msg = "{} failed: {}".format(title, sourcecode)
    elif mode is _signaled:
        tests_errored << unbox(tests_errored) + 1
        conditiontype = TestError
        desc = describe_exception(result)
        error_msg = "{} errored: {}, due to unexpected signal: {}".format(title, sourcecode, desc)
    else:  # mode is _raised:
        tests_errored << unbox(tests_errored) + 1
        conditiontype = TestError
        desc = describe_exception(result)
        error_msg = "{} errored: {}, due to unexpected exception: {}".format(title, sourcecode, desc)

    complete_msg = "[{}:{}] {}".format(filename, lineno, error_msg)

    # We use cerror() to signal a failed/errored test, instead of raising an
    # exception, so the client code can resume (after logging the failure and
    # such).
    #
    # If the client code does not install a handler, then a `ControlError`
    # exception is raised by the condition system; leaving a cerror unhandled
    # is an error.
    cerror(conditiontype(complete_msg))

def unpythonic_assert_signals(exctype, sourcecode, thunk, filename, lineno, myname=None):
    """Like `unpythonic_assert`, but assert that running `sourcecode` signals `exctype`.

    "Signal" as in `unpythonic.conditions.signal` and its sisters `error`, `cerror`, `warn`.
    """
    mode, result = _observe(thunk)
    tests_run << unbox(tests_run) + 1

    title = "Test" if myname is None else "Named test '{}'".format(myname)
    if mode is _completed:
        tests_failed << unbox(tests_failed) + 1
        conditiontype = TestFailure
        error_msg = "{} failed: {}, expected signal: {}, nothing was signaled.".format(title, sourcecode, describe_exception(exctype))
    elif mode is _signaled:
        # allow both "signal(SomeError())" and "signal(SomeError)"
        if isinstance(result, exctype) or issubclass(result, exctype):
            return
        tests_errored << unbox(tests_errored) + 1
        conditiontype = TestError
        desc = describe_exception(result)
        error_msg = "{} errored: {}, expected signal: {}, got unexpected signal: {}".format(title, sourcecode, describe_exception(exctype), desc)
    else:  # mode is _raised:
        tests_errored << unbox(tests_errored) + 1
        conditiontype = TestError
        desc = describe_exception(result)
        error_msg = "{} errored: {}, expected signal: {}, got unexpected exception: {}".format(title, sourcecode, describe_exception(exctype), desc)

    complete_msg = "[{}:{}] {}".format(filename, lineno, error_msg)
    cerror(conditiontype(complete_msg))

def unpythonic_assert_raises(exctype, sourcecode, thunk, filename, lineno, myname=None):
    """Like `unpythonic_assert`, but assert that running `sourcecode` raises `exctype`."""
    mode, result = _observe(thunk)
    tests_run << unbox(tests_run) + 1

    title = "Test" if myname is None else "Named test '{}'".format(myname)
    if mode is _completed:
        tests_failed << unbox(tests_failed) + 1
        conditiontype = TestFailure
        error_msg = "{} failed: {}, expected exception: {}, nothing was raised.".format(title, sourcecode, describe_exception(exctype))
    elif mode is _signaled:
        tests_errored << unbox(tests_errored) + 1
        conditiontype = TestError
        desc = describe_exception(result)
        error_msg = "{} errored: {}, expected exception: {}, got unexpected signal: {}".format(title, sourcecode, describe_exception(exctype), desc)
    else:  # mode is _raised:
        # allow both "raise SomeError()" and "raise SomeError"
        if isinstance(result, exctype):
            return
        tests_errored << unbox(tests_errored) + 1
        conditiontype = TestError
        desc = describe_exception(result)
        error_msg = "{} errored: {}, expected exception: {}, got unexpected exception: {}".format(title, sourcecode, describe_exception(exctype), desc)

    complete_msg = "[{}:{}] {}".format(filename, lineno, error_msg)
    cerror(conditiontype(complete_msg))


# -----------------------------------------------------------------------------
# Syntax transformers for the macros.

# -----------------------------------------------------------------------------
# Expr variants.

def test_expr(tree):
    ln = q[u[tree.lineno]] if hasattr(tree, "lineno") else q[None]
    filename = hq[callsite_filename()]
    asserter = hq[unpythonic_assert]

    # test[expr, name]  (like assert expr, name)
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

def _test_expr_signals_or_raises(tree, syntaxname, asserter):
    ln = q[u[tree.lineno]] if hasattr(tree, "lineno") else q[None]
    filename = hq[callsite_filename()]

    # test_signals[exctype, expr, name]
    # TODO: Python 3.8+: ast.Constant, no ast.Str
    if type(tree) is Tuple and len(tree.elts) == 3 and type(tree.elts[2]) is Str:
        exctype, tree, myname = tree.elts
    # test_signals[exctype, expr]
    elif type(tree) is Tuple and len(tree.elts) == 2:
        exctype, tree = tree.elts
        myname = q[None]
    else:
        assert False, "Expected one of {stx}[exctype, expr], {stx}[exctype, expr, name]".format(stx=syntaxname)

    return q[(ast_literal[asserter])(ast_literal[exctype],
                                     u[unparse(tree)],
                                     lambda: ast_literal[tree],
                                     filename=ast_literal[filename],
                                     lineno=ast_literal[ln],
                                     myname=ast_literal[myname])]

def test_expr_signals(tree):
    return _test_expr_signals_or_raises(tree, "test_signals", hq[unpythonic_assert_signals])
def test_expr_raises(tree):
    return _test_expr_signals_or_raises(tree, "test_raises", hq[unpythonic_assert_raises])

# -----------------------------------------------------------------------------
# Block variants.

# The strategy is we capture the block body into a new function definition,
# and then apply `test_expr` to a call to that function.
#
# The function is named with a MacroPy gen_sym; if the test is named,
# that name is mangled into a function name if reasonably possible.
# When no name is given or mangling would be nontrivial, we treat the
# test as an anonymous test block.
#
def test_block(block_body, args):
    # with test["my test name"]:
    # TODO: Python 3.8+: ast.Constant, no ast.Str
    function_name = "anonymous_test_block"
    if len(args) == 1 and type(args[0]) is Str:
        myname = args[0]
        # Name the generated function using the test name when possible.
        maybe_fname = myname.s.replace(" ", "_")
        # Lowercase just the first letter to follow Python function naming conventions.
        maybe_fname = maybe_fname[0].lower() + maybe_fname[1:]
        if maybe_fname.isidentifier():
            function_name = maybe_fname
    # with test:
    elif len(args) == 0:
        myname = None
    else:
        assert False, 'Expected `with test:` or `with test("my test name"):`'

    gen_sym = dyn.gen_sym
    final_function_name = gen_sym(function_name)

    if myname is not None:
        thetest = test_expr(q[(name[final_function_name](), ast_literal[myname])])
    else:
        thetest = test_expr(q[name[final_function_name]()])

    with q as newbody:
        def _():
            ...
        ast_literal[thetest]
    thefunc = newbody[0]
    thefunc.name = final_function_name
    thefunc.body = block_body
    return newbody

# args: exctype, myname
def test_block_signals(block_body, args):
    assert False, "Not implemented yet"
def test_block_raises(block_body, args):
    assert False, "Not implemented yet"
