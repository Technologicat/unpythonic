# -*- coding: utf-8 -*-
"""Utilities for writing tests.

See also `unpythonic.test.fixtures` for the high-level machinery.
"""

from macropy.core.quotes import macros, q, u, ast_literal, name
from macropy.core.hquotes import macros, hq  # noqa: F811, F401
from macropy.core.walkers import Walker
from macropy.core.macros import macro_stub
from macropy.core import unparse

from ast import Tuple, Str, Subscript, Name, Call, copy_location, Compare, arg, Return

from ..dynassign import dyn  # for MacroPy's gen_sym
from ..env import env
from ..misc import callsite_filename
from ..conditions import cerror, handlers, restarts, invoke
from ..collections import unbox
from ..symbol import sym, gensym

from .util import isx

from ..test import fixtures

# -----------------------------------------------------------------------------
# Helper for other macros to detect uses of the ones we define here.

# Note the unexpanded `error[]` macro is distinguishable from a call to
# the function `unpythonic.conditions.error`, because a macro invocation
# is an `ast.Subscript`, whereas a function call is an `ast.Call`.
_test_macro_names = ["test", "test_signals", "test_raises", "error", "fail", "warn", "the"]
_test_function_names = ["unpythonic_assert",
                        "unpythonic_assert_signals",
                        "unpythonic_assert_raises"]
def isunexpandedtestmacro(tree):
    """Return whether `tree` is an invocation of a testing macro, unexpanded."""
    return (type(tree) is Subscript and
            type(tree.value) is Name and
            tree.value.id in _test_macro_names)
def isexpandedtestmacro(tree):
    """Return whether `tree` is an invocation of a testing macro, expanded."""
    return (type(tree) is Call and
            any(isx(tree.func, fname, accept_attr=False)
                for fname in _test_function_names))
def istestmacro(tree):
    """Return whether `tree` is an invocation of a testing macro.

    Expanded or unexpanded doesn't matter.
    """
    return isunexpandedtestmacro(tree) or isexpandedtestmacro(tree)

# -----------------------------------------------------------------------------
# Regular code, no macros yet.

_fail = sym("_fail")  # used by the fail[] macro
_error = sym("_error")  # used by the error[] macro
_warn = sym("_warn")  # used by the warn[] macro

def _observe(thunk):
    """Run `thunk` and report how it fared.

    Internal helper for implementing assert functions.

    The return value is:

      - `(completed, return_value)` if the thunk completed normally
      - `(signaled, condition_instance)` if a signal from inside
        the dynamic extent of thunk propagated to this level.
      - `(raised, exception_instance)` if an exception from inside
        the dynamic extent of thunk propagated to this level.
    """
    def intercept(condition):
        if not fixtures._catch_uncaught_signals[0]:
            return  # cancel and delegate to the next outer handler

        # If we get an internal signal from this test framework itself, ignore
        # it and let it fall through to the nearest enclosing `testset`, for
        # reporting. This can happen if a `test[]` is nested within a `with
        # test:` block, or if `test[]` expressions are nested.
        if issubclass(type(condition), fixtures.TestingException):
            return  # cancel and delegate to the next outer handler
        invoke("_got_signal", condition)

    try:
        with restarts(_got_signal=lambda exc: exc) as sig:
            with handlers((Exception, intercept)):
                ret = thunk()
            # We only reach this point if the restart was not invoked,
            # i.e. if thunk() completed normally.
            return fixtures.completed, ret
        return fixtures.signaled, unbox(sig)
    # This testing framework always signals, never raises, so we don't need any
    # special handling here.
    except Exception as err:  # including ControlError raised by an unhandled `unpythonic.conditions.error`
        return fixtures.raised, err


_unassigned = gensym("_unassigned")  # runtime gensym / nonce value.
def unpythonic_assert(sourcecode, func, *, filename, lineno, message=None):
    """Custom assert function, for building test frameworks.

    Upon a failing assertion, this will *signal* a `fixtures.TestFailure`
    as a *cerror* (correctable error), via unpythonic's condition system,
    see `unpythonic.conditions.cerror`.

    If a test fails to run to completion due to an unexpected exception or an
    unhandled `error` (or `cerror`) condition, `fixtures.TestError` is signaled,
    so the caller can easily tell apart which case occurred.

    Using conditions allows the surrounding code to install a handler that
    invokes the `proceed` restart, so upon a test failure, any further tests
    still continue to run.

    Parameters:

        `sourcecode` is a string representation of the source code expression
        that is being asserted.

        `func` is the test itself, as a 1-argument function that accepts
        as its only argument an `unpythonic.env`. The `the[]` mechanism
        uses this `env` to store the value of the captured subexpression.
        (It is also perfectly fine to not store anything there; the presence
         or absence of a captured value is detected automatically.)

        The function should compute the desired test expression and return
        its value. If the result is falsey, the assertion fails.

        `filename` is the filename at the call site, if applicable. (If called
        from the REPL, there is no file.)

        `lineno` is the line number at the call site.

        These are best extracted automatically using the test macros.

        `message` is an optional string, included in the generated error message
        if the assertion fails.

    No return value.
    """
    # The the[] marker, if any, inside a test[], injects code to record the
    # value of the interesting subexpression as `captured_value` in the env
    # we send to `func` as its argument.
    e = env(captured_value=_unassigned)
    mode, test_result = _observe(lambda: func(e))  # <-- run the actual expr being asserted
    if e.captured_value is not _unassigned:
        value = e.captured_value
    else:
        # It's legal to omit capturing the value of any subexpr.
        # In that case, we capture the value of the whole expression.
        value = test_result
    fixtures._update(fixtures.tests_run, +1)

    if message is not None:
        custom_msg = ", with message '{}'".format(message)
    else:
        custom_msg = ""

    # special cases for unconditional failures
    origin = "test"
    if mode is fixtures.completed and test_result is _fail:  # fail[...], e.g. unreachable line reached
        fixtures._update(fixtures.tests_failed, +1)
        conditiontype = fixtures.TestFailure
        origin = "fail"
        if message is not None:
            # If a user-given message is specified for `fail[]`, it is all
            # that should be displayed. We don't want confusing noise such as
            # "Test failed"; the intent of signaling an unconditional failure
            # is something different from actually testing the value of an
            # expression.
            error_msg = message
        else:
            error_msg = "Unconditional failure requested, no message."
    elif mode is fixtures.completed and test_result is _error:  # error[...], e.g. dependency not installed
        fixtures._update(fixtures.tests_errored, +1)
        conditiontype = fixtures.TestError
        origin = "error"
        if message is not None:
            error_msg = message
        else:
            error_msg = "Unconditional error requested, no message."
    elif mode is fixtures.completed and test_result is _warn:  # warn[...], e.g. some test disabled for now
        fixtures._update(fixtures.tests_warned, +1)
        # HACK: warnings don't count into the test total
        fixtures._update(fixtures.tests_run, -1)
        conditiontype = fixtures.TestWarning
        origin = "warn"
        if message is not None:
            error_msg = message
        else:
            error_msg = "Warning requested, no message."
        # We need to use the `cerror` protocol, so that the handler
        # will invoke "proceed", thus handling the signal and preventing
        # any outer handlers from running. This is important to prevent
        # the warning being printed multiple times (once per testset level).
        #
        # So we may as well use the same code path as the fail and error cases.
    # general cases
    elif mode is fixtures.completed:
        if test_result:
            return
        fixtures._update(fixtures.tests_failed, +1)
        conditiontype = fixtures.TestFailure
        error_msg = "Test failed: {}, due to result = {}{}".format(sourcecode, value, custom_msg)
    elif mode is fixtures.signaled:
        fixtures._update(fixtures.tests_errored, +1)
        conditiontype = fixtures.TestError
        desc = fixtures.describe_exception(test_result)
        error_msg = "Test errored: {}{}, due to unexpected signal: {}".format(sourcecode, custom_msg, desc)
    else:  # mode is fixtures.raised:
        fixtures._update(fixtures.tests_errored, +1)
        conditiontype = fixtures.TestError
        desc = fixtures.describe_exception(test_result)
        error_msg = "Test errored: {}{}, due to unexpected exception: {}".format(sourcecode, custom_msg, desc)

    complete_msg = "[{}:{}] {}".format(filename, lineno, error_msg)

    # We use cerror() to signal a failed/errored test, instead of raising an
    # exception, so the client code can resume (after logging the failure and
    # such).
    #
    # If the client code does not install a handler, then a `ControlError`
    # exception is raised by the condition system; leaving a cerror unhandled
    # is an error.
    #
    # As well as forming an error message for humans, we provide the data
    # in a machine-readable format for run-time inspection.
    cerror(conditiontype(complete_msg, origin=origin, custom_message=message,
                         filename=filename, lineno=lineno, sourcecode=sourcecode,
                         mode=mode, result=test_result, captured_value=value))

def unpythonic_assert_signals(exctype, sourcecode, thunk, *, filename, lineno, message=None):
    """Like `unpythonic_assert`, but assert that running `sourcecode` signals `exctype`.

    "Signal" as in `unpythonic.conditions.signal` and its sisters `error`, `cerror`, `warn`.
    """
    mode, test_result = _observe(thunk)
    fixtures._update(fixtures.tests_run, +1)

    if message is not None:
        custom_msg = ", with message '{}'".format(message)
    else:
        custom_msg = ""

    if mode is fixtures.completed:
        fixtures._update(fixtures.tests_failed, +1)
        conditiontype = fixtures.TestFailure
        error_msg = "Test failed: {}{}, expected signal: {}, nothing was signaled.".format(sourcecode, custom_msg, fixtures.describe_exception(exctype))
    elif mode is fixtures.signaled:
        if isinstance(test_result, exctype):
            return
        fixtures._update(fixtures.tests_errored, +1)
        conditiontype = fixtures.TestError
        desc = fixtures.describe_exception(test_result)
        error_msg = "Test errored: {}{}, expected signal: {}, got unexpected signal: {}".format(sourcecode, custom_msg, fixtures.describe_exception(exctype), desc)
    else:  # mode is fixtures.raised:
        fixtures._update(fixtures.tests_errored, +1)
        conditiontype = fixtures.TestError
        desc = fixtures.describe_exception(test_result)
        error_msg = "Test errored: {}{}, expected signal: {}, got unexpected exception: {}".format(sourcecode, custom_msg, fixtures.describe_exception(exctype), desc)

    complete_msg = "[{}:{}] {}".format(filename, lineno, error_msg)
    cerror(conditiontype(complete_msg, origin="test_signals", custom_message=message,
                         filename=filename, lineno=lineno, sourcecode=sourcecode,
                         mode=mode, result=test_result, captured_value=test_result))

def unpythonic_assert_raises(exctype, sourcecode, thunk, *, filename, lineno, message=None):
    """Like `unpythonic_assert`, but assert that running `sourcecode` raises `exctype`."""
    mode, test_result = _observe(thunk)
    fixtures._update(fixtures.tests_run, +1)

    if message is not None:
        custom_msg = ", with message '{}'".format(message)
    else:
        custom_msg = ""

    if mode is fixtures.completed:
        fixtures._update(fixtures.tests_failed, +1)
        conditiontype = fixtures.TestFailure
        error_msg = "Test failed: {}{}, expected exception: {}, nothing was raised.".format(sourcecode, custom_msg, fixtures.describe_exception(exctype))
    elif mode is fixtures.signaled:
        fixtures._update(fixtures.tests_errored, +1)
        conditiontype = fixtures.TestError
        desc = fixtures.describe_exception(test_result)
        error_msg = "Test errored: {}{}, expected exception: {}, got unexpected signal: {}".format(sourcecode, custom_msg, fixtures.describe_exception(exctype), desc)
    else:  # mode is fixtures.raised:
        if isinstance(test_result, exctype):
            return
        fixtures._update(fixtures.tests_errored, +1)
        conditiontype = fixtures.TestError
        desc = fixtures.describe_exception(test_result)
        error_msg = "Test errored: {}{}, expected exception: {}, got unexpected exception: {}".format(sourcecode, custom_msg, fixtures.describe_exception(exctype), desc)

    complete_msg = "[{}:{}] {}".format(filename, lineno, error_msg)
    cerror(conditiontype(complete_msg, origin="test_raises", custom_message=message,
                         filename=filename, lineno=lineno, sourcecode=sourcecode,
                         mode=mode, result=test_result, captured_value=test_result))


# -----------------------------------------------------------------------------
# Syntax transformers for the macros.

def _unconditional_error_expr(tree, syntaxname, marker):
    # TODO: Python 3.8+: ast.Constant, no ast.Str
    if type(tree) is not Str:
        assert False, "expected {stx}[message]".format(stx=syntaxname)
    thetuple = q[(ast_literal[marker], ast_literal[tree])]
    thetuple = copy_location(thetuple, tree)
    return test_expr(thetuple)

def fail_expr(tree):
    return _unconditional_error_expr(tree, "fail", hq[_fail])
def error_expr(tree):
    return _unconditional_error_expr(tree, "error", hq[_error])
def warn_expr(tree):
    return _unconditional_error_expr(tree, "warn", hq[_warn])

# -----------------------------------------------------------------------------
# Expr variants.

@macro_stub
def the(*args, **kwargs):
    """[syntax, expr] In a test, mark a subexpression as the interesting one.

    Only meaningful inside a `test[]`, or inside a `with test` block.

    What `test[expr]` captures for reporting as "result" if the test fails:

      - If `the[...]` is present, the subexpression marked as `the[...]`.
      - Else if `expr` is a comparison, the LHS (leftmost term in case of
        a chained comparison). So e.g. `test[x < 3]` (or the second example
        above) needs no annotation to do the right thing. This is a common
        use case, hence automatic.
      - Else the whole `expr`.

    So the `the[...]` mark is useful in tests involving comparisons::

        test[lower_limit < the[computeitem(...)]]
        test[lower_limit < the[computeitem(...)] < upper_limit]
        test[myconstant in the[computeset(...)]]

    Note the above rules mean that if the interesting subexpression is the
    leftmost term of a comparison, `the[...]` is optional, although allowed
    (to explicitly document intent). These have the same effect::

        test[the[computeitem(...)] in myitems]
        test[computeitem(...) in myitems]

    The `the[...]` mark passes the value through, and does not affect the
    evaluation order of user code.

    A `test[...]` may have at most one `the[...]`.

    In case of nested tests, each `the[...]` is understood as belonging to
    the lexically innermost surrounding one.

    For `test_raises` and `test_signals`, the `the[...]` mark is not supported.
    """
    pass  # pragma: no cover, macro stub

# Destructuring utilities for marking a custom part of the expr
# to be displayed upon test failure, using `the[...]`:
#   test[myconstant in the[computeset(...)]]
#   test[the[computeitem(...)] in expected_results_plus_uninteresting_items]
def _is_important_subexpr_mark(tree):
    return type(tree) is Subscript and type(tree.value) is Name and tree.value.id == "the"
def _inject_value_recorder(envname, tree):  # wrap tree with the the[] handler
    return q[name[envname].set("captured_value", ast_literal[tree])]
@Walker
def _transform_important_subexpr(tree, *, collect, stop, envname, **kw):
    if _is_important_subexpr_mark(tree):
        stop()
        collect(tree.slice.value)  # or anything really; value not used, we just count them.
        return _inject_value_recorder(envname, tree.slice.value)
    return tree

def test_expr(tree):
    # Note we want the line number *before macro expansion*, so we capture it now.
    ln = q[u[tree.lineno]] if hasattr(tree, "lineno") else q[None]
    filename = hq[callsite_filename()]
    asserter = hq[unpythonic_assert]

    # test[expr, message]  (like assert expr, message)
    # TODO: Python 3.8+: ast.Constant, no ast.Str
    if type(tree) is Tuple and len(tree.elts) == 2 and type(tree.elts[1]) is Str:
        tree, message = tree.elts
    # test[expr]  (like assert expr)
    else:
        message = q[None]

    # Before we edit the tree, get the source code in its pre-transformation
    # state, so we can include that into the test failure message.
    sourcecode = unparse(tree)

    gen_sym = dyn.gen_sym
    envname = gen_sym("e")  # for injecting the captured value

    # Handle the `the[...]` mark, if any.
    tree, the_exprs = _transform_important_subexpr.recurse_collect(tree, envname=envname)
    if len(the_exprs) > 1:
        assert False, "test[]: At most one `the[...]` may appear in expr"  # pragma: no cover
    if len(the_exprs) == 0 and type(tree) is Compare:  # inject the implicit the[] on the LHS
        tree.left = _inject_value_recorder(envname, tree.left)

    # We delay the execution of the test expr using a lambda, so
    # `unpythonic_assert` can get control first before the expr runs.
    #
    # Also, we need the lambda for passing in the value capture environment
    # for the `the[]` mark, anyway.
    func_tree = q[lambda _: ast_literal[tree]]  # create the function that takes in the env
    func_tree.args.args[0] = arg(arg=envname)  # inject the gensymmed parameter name

    return q[(ast_literal[asserter])(u[sourcecode],
                                     ast_literal[func_tree],
                                     filename=ast_literal[filename],
                                     lineno=ast_literal[ln],
                                     message=ast_literal[message])]

def _test_expr_signals_or_raises(tree, syntaxname, asserter):
    ln = q[u[tree.lineno]] if hasattr(tree, "lineno") else q[None]
    filename = hq[callsite_filename()]

    # test_signals[exctype, expr, message]
    # TODO: Python 3.8+: ast.Constant, no ast.Str
    if type(tree) is Tuple and len(tree.elts) == 3 and type(tree.elts[2]) is Str:
        exctype, tree, message = tree.elts
    # test_signals[exctype, expr]
    elif type(tree) is Tuple and len(tree.elts) == 2:
        exctype, tree = tree.elts
        message = q[None]
    else:
        assert False, "Expected one of {stx}[exctype, expr], {stx}[exctype, expr, message]".format(stx=syntaxname)

    return q[(ast_literal[asserter])(ast_literal[exctype],
                                     u[unparse(tree)],
                                     lambda: ast_literal[tree],
                                     filename=ast_literal[filename],
                                     lineno=ast_literal[ln],
                                     message=ast_literal[message])]

def test_expr_signals(tree):
    return _test_expr_signals_or_raises(tree, "test_signals", hq[unpythonic_assert_signals])
def test_expr_raises(tree):
    return _test_expr_signals_or_raises(tree, "test_raises", hq[unpythonic_assert_raises])

# -----------------------------------------------------------------------------
# Block variants.

# The strategy is we capture the block body into a new function definition,
# and then `unpythonic_assert` on that function.
def test_block(block_body, args):
    if not block_body:
        return []  # pragma: no cover, cannot happen through the public API.
    first_stmt = block_body[0]

    # Note we want the line number *before macro expansion*, so we capture it now.
    ln = q[u[first_stmt.lineno]] if hasattr(first_stmt, "lineno") else q[None]
    filename = hq[callsite_filename()]
    asserter = hq[unpythonic_assert]

    # with test(message):
    # TODO: Python 3.8+: ast.Constant, no ast.Str
    if len(args) == 1 and type(args[0]) is Str:
        message = args[0]
    # with test:
    elif len(args) == 0:
        message = q[None]
    else:
        assert False, 'Expected `with test:` or `with test(message):`'

    # Before we edit the tree, get the source code in its pre-transformation
    # state, so we can include that into the test failure message.
    sourcecode = unparse(block_body)

    gen_sym = dyn.gen_sym
    envname = gen_sym("e")  # for injecting the captured value
    testblock_function_name = gen_sym("test_block")

    # Handle the `the[...]` mark, if any.
    block_body, the_exprs = _transform_important_subexpr.recurse_collect(block_body, envname=envname)
    if len(the_exprs) > 1:
        assert False, "test[]: At most one `the[...]` may appear in a `with test` block"  # pragma: no cover

    thetest = q[(ast_literal[asserter])(u[sourcecode],
                                        name[testblock_function_name],
                                        filename=ast_literal[filename],
                                        lineno=ast_literal[ln],
                                        message=ast_literal[message])]
    with q as newbody:
        def _insert_funcname_here_(_insert_envname_here_):
            ...
        ast_literal[thetest]
    thefunc = newbody[0]
    thefunc.name = testblock_function_name
    thefunc.args.args[0] = arg(arg=envname)  # inject the gensymmed parameter name

    # Handle the return statement.
    #
    # We just check if there is at least one; if so, we don't need to do
    # anything; the returned value is what the test should return to the
    # asserter.
    for stmt in block_body:
        if type(stmt) is Return:
            retval = stmt.value
            if len(the_exprs) == 0 and type(retval) is Compare:
                # inject the implicit the[] on the LHS
                retval.left = _inject_value_recorder(envname, retval.left)
    else:
        # When there is no return statement at the top level of the `with test` block,
        # we inject a `return True` to satisfy the test when the function returns normally.
        with q as thereturn:
            return True
        block_body.append(thereturn)

    thefunc.body = block_body

    return newbody

def _test_block_signals_or_raises(block_body, args, syntaxname, asserter):
    if not block_body:
        return []  # pragma: no cover, cannot happen through the public API.
    first_stmt = block_body[0]

    # Note we want the line number *before macro expansion*, so we capture it now.
    ln = q[u[first_stmt.lineno]] if hasattr(first_stmt, "lineno") else q[None]
    filename = hq[callsite_filename()]

    # with test_raises(exctype, message):
    # TODO: Python 3.8+: ast.Constant, no ast.Str
    if len(args) == 2 and type(args[1]) is Str:
        exctype, message = args
    # with test_raises(exctype):
    elif len(args) == 1:
        exctype = args[0]
        message = q[None]
    else:
        assert False, 'Expected `with {stx}(exctype):` or `with {stx}(exctype, message):`'.format(stx=syntaxname)

    # Before we edit the tree, get the source code in its pre-transformation
    # state, so we can include that into the test failure message.
    sourcecode = unparse(block_body)

    gen_sym = dyn.gen_sym
    testblock_function_name = gen_sym("test_block")
    #def unpythonic_assert_raises(exctype, sourcecode, thunk, *, filename, lineno, message=None):

    thetest = q[(ast_literal[asserter])(ast_literal[exctype],
                                        u[sourcecode],
                                        name[testblock_function_name],
                                        filename=ast_literal[filename],
                                        lineno=ast_literal[ln],
                                        message=ast_literal[message])]
    with q as newbody:
        def _insert_funcname_here_():  # no env needed, since `the[]` is not meaningful here.
            ...
        ast_literal[thetest]
    thefunc = newbody[0]
    thefunc.name = testblock_function_name
    thefunc.body = block_body
    return newbody

def test_block_signals(block_body, args):
    return _test_block_signals_or_raises(block_body, args, "test_signals", hq[unpythonic_assert_signals])
def test_block_raises(block_body, args):
    return _test_block_signals_or_raises(block_body, args, "test_raises", hq[unpythonic_assert_raises])
