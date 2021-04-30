# -*- coding: utf-8 -*-
"""Utilities for writing tests.

See also `unpythonic.test.fixtures` for the high-level machinery.
"""

__all__ = ["isunexpandedtestmacro", "isexpandedtestmacro", "istestmacro",
           "fail_expr", "error_expr", "warn_expr",
           "the",
           "test_expr", "test_expr_signals", "test_expr_raises",
           "test_block", "test_block_signals", "test_block_raises"]

from mcpyrate.quotes import macros, q, u, n, a, h  # noqa: F401

from mcpyrate import gensym, unparse
from mcpyrate.quotes import is_captured_value
from mcpyrate.walkers import ASTTransformer

from ast import Tuple, Subscript, Name, Call, copy_location, Compare, arg, Return, parse, Expr, AST
import sys

from ..dynassign import dyn
from ..env import env
from ..misc import callsite_filename, namelambda
from ..conditions import cerror, handlers, restarts, invoke
from ..collections import unbox
from ..symbol import sym

from .util import isx

from ..test import fixtures

# -----------------------------------------------------------------------------
# Helper for other macros to detect uses of the ones we define here.

# TODO: Detect asserters only? Now this breaks the handling of the[] in a prefix block.
# TODO: It should be handled like any expr, but currently it's skipped because it's listed here.

# Note the unexpanded `error[]` macro is distinguishable from a call to
# the function `unpythonic.conditions.error`, because a macro invocation
# is an `ast.Subscript`, whereas a function call is an `ast.Call`.
_test_asserter_names = ["test", "test_signals", "test_raises", "error", "fail", "warn"]
_test_function_names = ["unpythonic_assert",
                        "unpythonic_assert_signals",
                        "unpythonic_assert_raises"]
def isunexpandedtestmacro(tree):
    """Return whether `tree` is an invocation of a test asserter, unexpanded."""
    return (type(tree) is Subscript and
            type(tree.value) is Name and
            tree.value.id in _test_asserter_names)
def isexpandedtestmacro(tree):
    """Return whether `tree` is an invocation of a test asserter, expanded."""
    return (type(tree) is Call and
            any(isx(tree.func, fname, accept_attr=False)
                for fname in _test_function_names))
def istestmacro(tree):
    """Return whether `tree` is an invocation of a test asserter.

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
        if not fixtures._threadlocals.catch_uncaught_signals[0]:
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
    # value of an interesting subexpression in `captured_values` in the env
    # we send to `func` as its argument. A `the[]` is also implicitly injected
    # by the comparison destructuring mechanism.
    e = env(captured_values=[])
    testexpr = func  # descriptive name for stack trace; if you change this, change also in `test_expr`.
    mode, test_result = _observe(thunk=(lambda: testexpr(e)))  # <-- run the actual expr being asserted
    if e.captured_values:
        # Convenience for testing/debugging macro code:
        #
        # For the failure message, log the value itself, except if that value
        # is an AST, unparse it to source code and log that instead. This is
        # convenient, because:
        #
        # 1) The repr of anything in the `ast` stdlib module is completely useless, and
        # 2) Python is not homoiconic, so the source code representation more closely
        #    resembles the actual source code of the test case that failed.
        #
        # This is only done for logging. In order to avoid breaking introspection,
        # the actual exception instance (if the test fails) always gets the
        # original raw values.
        logged_values = [(source, (repr(v) if not isinstance(v, AST) else f"<AST; unparsed form: '{unparse(v)}'>"))
                         for source, v in e.captured_values]

        # Canonization eliminates surface syntax differences such as
        # parenthesization, and which quote character is used for
        # string literals.
        def canonize_expr(sourcecode):
            try:
                tree = parse(sourcecode)
            except SyntaxError:  # a repr might not be valid source code
                return None
            expr_node = tree.body[0]
            assert type(expr_node) is Expr
            return unparse(expr_node.value).strip()

        # The condition filters out trivialities due to literals, such as "4 = 4" in `test[4 in (1, 2, 3)]`.
        values_strs = [f"{subexpr_sourcecode} = {subexpr_value}"
                       for subexpr_sourcecode, subexpr_value in logged_values
                       if canonize_expr(subexpr_sourcecode) != canonize_expr(repr(subexpr_value))]

        if values_strs:
            values_msg = ", due to " + ", ".join(values_strs)
        else:  # if we have no useful details to report, report the value of the whole expression.
            values_msg = f", due to result = {test_result}"
    else:
        # It's legal to omit capturing the values of any subexprs.
        # In that case, we report the value of the whole expression.
        values_msg = f", due to result = {test_result}"
    fixtures._update(fixtures.tests_run, +1)

    if message is not None:
        custom_msg = f", with message '{message}'"
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
        error_msg = f"Test failed: {sourcecode}{values_msg}{custom_msg}"
    elif mode is fixtures.signaled:
        fixtures._update(fixtures.tests_errored, +1)
        conditiontype = fixtures.TestError
        desc = fixtures.describe_exception(test_result)
        error_msg = f"Test errored: {sourcecode}{custom_msg}, due to unexpected signal: {desc}"
    else:  # mode is fixtures.raised:
        fixtures._update(fixtures.tests_errored, +1)
        conditiontype = fixtures.TestError
        desc = fixtures.describe_exception(test_result)
        error_msg = f"Test errored: {sourcecode}{custom_msg}, due to unexpected exception: {desc}"

    complete_msg = f"[{filename}:{lineno}] {error_msg}"

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
                         mode=mode, result=test_result, captured_values=e.captured_values))

def unpythonic_assert_signals(exctype, sourcecode, thunk, *, filename, lineno, message=None):
    """Like `unpythonic_assert`, but assert that running `sourcecode` signals `exctype`.

    "Signal" as in `unpythonic.conditions.signal` and its sisters `error`, `cerror`, `warn`.
    """
    mode, test_result = _observe(thunk)
    fixtures._update(fixtures.tests_run, +1)

    if message is not None:
        custom_msg = f", with message '{message}'"
    else:
        custom_msg = ""

    if mode is fixtures.completed:
        fixtures._update(fixtures.tests_failed, +1)
        conditiontype = fixtures.TestFailure
        error_msg = f"Test failed: {sourcecode}{custom_msg}, expected signal: {fixtures.describe_exception(exctype)}, nothing was signaled."
    elif mode is fixtures.signaled:
        if isinstance(test_result, exctype):
            return
        fixtures._update(fixtures.tests_errored, +1)
        conditiontype = fixtures.TestError
        desc = fixtures.describe_exception(test_result)
        error_msg = f"Test errored: {sourcecode}{custom_msg}, expected signal: {fixtures.describe_exception(exctype)}, got unexpected signal: {desc}"
    else:  # mode is fixtures.raised:
        fixtures._update(fixtures.tests_errored, +1)
        conditiontype = fixtures.TestError
        desc = fixtures.describe_exception(test_result)
        error_msg = f"Test errored: {sourcecode}{custom_msg}, expected signal: {fixtures.describe_exception(exctype)}, got unexpected exception: {desc}"

    complete_msg = f"[{filename}:{lineno}] {error_msg}"
    cerror(conditiontype(complete_msg, origin="test_signals", custom_message=message,
                         filename=filename, lineno=lineno, sourcecode=sourcecode,
                         mode=mode, result=test_result, captured_values=[]))

def unpythonic_assert_raises(exctype, sourcecode, thunk, *, filename, lineno, message=None):
    """Like `unpythonic_assert`, but assert that running `sourcecode` raises `exctype`."""
    mode, test_result = _observe(thunk)
    fixtures._update(fixtures.tests_run, +1)

    if message is not None:
        custom_msg = f", with message '{message}'"
    else:
        custom_msg = ""

    if mode is fixtures.completed:
        fixtures._update(fixtures.tests_failed, +1)
        conditiontype = fixtures.TestFailure
        error_msg = f"Test failed: {sourcecode}{custom_msg}, expected exception: {fixtures.describe_exception(exctype)}, nothing was raised."
    elif mode is fixtures.signaled:
        fixtures._update(fixtures.tests_errored, +1)
        conditiontype = fixtures.TestError
        desc = fixtures.describe_exception(test_result)
        error_msg = f"Test errored: {sourcecode}{custom_msg}, expected exception: {fixtures.describe_exception(exctype)}, got unexpected signal: {desc}"
    else:  # mode is fixtures.raised:
        if isinstance(test_result, exctype):
            return
        fixtures._update(fixtures.tests_errored, +1)
        conditiontype = fixtures.TestError
        desc = fixtures.describe_exception(test_result)
        error_msg = f"Test errored: {sourcecode}{custom_msg}, expected exception: {fixtures.describe_exception(exctype)}, got unexpected exception: {desc}"

    complete_msg = f"[{filename}:{lineno}] {error_msg}"
    cerror(conditiontype(complete_msg, origin="test_raises", custom_message=message,
                         filename=filename, lineno=lineno, sourcecode=sourcecode,
                         mode=mode, result=test_result, captured_values=[]))


# -----------------------------------------------------------------------------
# Syntax transformers for the macros.

def _unconditional_error_expr(tree, syntaxname, marker):
    thetuple = q[(a[marker], a[tree])]   # consider `test[tree, message]`
    thetuple = copy_location(thetuple, tree)
    return test_expr(thetuple)

# Here `tree` is the AST for the failure message.
def fail_expr(tree):
    return _unconditional_error_expr(tree, "fail", q[h[_fail]])  # TODO: stash a copy of the hygienic value?
def error_expr(tree):
    return _unconditional_error_expr(tree, "error", q[h[_error]])
def warn_expr(tree):
    return _unconditional_error_expr(tree, "warn", q[h[_warn]])

# -----------------------------------------------------------------------------
# Expr variants.

def the(tree, **kw):
    """[syntax, expr] In a test, mark a subexpression as the interesting one.

    Only meaningful inside a `test[]`, or inside a `with test` block.

    What `test[expr]` captures for reporting for human inspection upon
    test failure:

      - If any `the[...]` are present, the subexpressions marked as `the[...]`.

      - Else if `expr` is a comparison, the LHS (leftmost term in case of
        a chained comparison). So e.g. `test[x < 3]` needs no annotation
        to do the right thing. This is a common use case, hence automatic.

      - Else nothing is captured; the value of the whole `expr` is reported.

    So the `the[...]` mark is useful in tests involving comparisons::

        test[lower_limit < the[computeitem(...)]]
        test[lower_limit < the[computeitem(...)] < upper_limit]
        test[myconstant in the[computeset(...)]]

    especially if you need to capture several subexpressions::

        test[the[counter()] < the[counter()]]

    Note the above rules mean that if there is just one interesting
    subexpression, and it is the leftmost term of a comparison, `the[...]`
    is optional, although allowed (to explicitly document intent).
    These have the same effect::

        test[the[computeitem(...)] in myitems]
        test[computeitem(...) in myitems]

    The `the[...]` mark passes the value through, and does not affect the
    evaluation order of user code.

    A `test[...]` may have multiple `the[...]`; the captured values are
    gathered in a list that is shown upon test failure.

    In case of nested tests, each `the[...]` is understood as belonging to
    the lexically innermost surrounding test.

    For `test_raises` and `test_signals`, the `the[...]` mark is not supported.
    """
    raise SyntaxError("the[] is only meaningful inside a `test[]` or in a `with test` block")  # pragma: no cover, not meant to hit the expander

# Destructuring utilities for marking a custom part of the expr
# to be displayed upon test failure, using `the[...]`:
#   test[myconstant in the[computeset(...)]]
#   test[the[computeitem(...)] in expected_results_plus_uninteresting_items]
def _is_important_subexpr_mark(tree):
    return type(tree) is Subscript and type(tree.value) is Name and tree.value.id == "the"
def _record_value(envname, sourcecode, value):
    envname.captured_values.append((sourcecode, value))
    return value
def _inject_value_recorder(envname, tree):  # wrap tree with the the[] handler
    recorder = q[h[_record_value]]  # TODO: stash hygienic value?
    return q[a[recorder](n[envname],
                         u[unparse(tree)],
                         a[tree])]
def _transform_important_subexpr(tree, envname):
    # The the[] mark mechanism is invoked outside-in, because for reporting,
    # it needs to capture the source AST in the form the code appears in the
    # actual source file.
    class ImportantSubexprTransformer(ASTTransformer):
        def transform(self, tree):
            if is_captured_value(tree):
                return tree  # don't recurse!
            # Respect the boundaries of nested test constructs (don't recurse there).
            if isunexpandedtestmacro(tree):
                return tree
            elif _is_important_subexpr_mark(tree):
                if sys.version_info >= (3, 9, 0):  # Python 3.9+: the Index wrapper is gone.
                    thing = tree.slice
                else:
                    thing = tree.slice.value
                self.collect(thing)  # or anything really; value not used, we just count them.
                # Handle any nested the[] subexpressions
                subtree = self.visit(thing)
                return _inject_value_recorder(envname, subtree)
            else:
                return self.generic_visit(tree)  # recurse
    transformer = ImportantSubexprTransformer()
    tree = transformer.visit(tree)
    return tree, transformer.collected


def test_expr(tree):
    # Note we want the line number *before macro expansion*, so we capture it now.
    ln = q[u[tree.lineno]] if hasattr(tree, "lineno") else q[None]
    filename = q[h[callsite_filename]()]
    asserter = q[h[unpythonic_assert]]

    # test[expr, message]  (like assert expr, message)
    if type(tree) is Tuple and len(tree.elts) == 2:
        tree, message = tree.elts
    # test[expr]  (like assert expr)
    else:
        message = q[None]

    # Before we edit the tree, get the source code in its pre-transformation
    # state, so we can include that into the test failure message.
    #
    # We capture the source in the first pass, so that no macros in tree are
    # expanded yet. For the same reason, we process the `the[]` marks in the
    # first pass.
    sourcecode = unparse(tree)

    envname = gensym("e")  # for injecting the captured value

    # Handle the `the[...]` marks, if any.
    tree, the_exprs = _transform_important_subexpr(tree, envname=envname)
    if not the_exprs and type(tree) is Compare:  # inject the implicit the[] on the LHS
        tree.left = _inject_value_recorder(envname, tree.left)

    # End of first pass.
    tree = dyn._macro_expander.visit(tree)

    # We delay the execution of the test expr using a lambda, so
    # `unpythonic_assert` can get control first before the expr runs.
    #
    # Also, we need the lambda for passing in the value capture environment
    # for the `the[]` mark, anyway.
    #
    # We name it `testexpr` to make the stack trace more understandable.
    # If you change the name, change it also in `unpythonic_assert`.
    thelambda = q[lambda _: a[tree]]
    thelambda.args.args[0] = arg(arg=envname)  # inject the gensymmed parameter name
    func_tree = q[h[namelambda]("testexpr")(a[thelambda])]  # create the function that takes in the env

    return q[(a[asserter])(u[sourcecode],
                           a[func_tree],
                           filename=a[filename],
                           lineno=a[ln],
                           message=a[message])]

def _test_expr_signals_or_raises(tree, syntaxname, asserter):
    ln = q[u[tree.lineno]] if hasattr(tree, "lineno") else q[None]
    filename = q[h[callsite_filename]()]

    # test_signals[exctype, expr, message]
    if type(tree) is Tuple and len(tree.elts) == 3:
        exctype, tree, message = tree.elts
    # test_signals[exctype, expr]
    elif type(tree) is Tuple and len(tree.elts) == 2:
        exctype, tree = tree.elts
        message = q[None]
    else:
        raise SyntaxError(f"Expected one of {syntaxname}[exctype, expr], {syntaxname}[exctype, expr, message]")

    # Before we edit the tree, get the source code in its pre-transformation
    # state, so we can include that into the test failure message.
    #
    # We capture the source in the first pass, so that no macros in tree are
    # expanded yet.
    sourcecode = unparse(tree)

    # End of first pass.
    tree = dyn._macro_expander.visit(tree)

    return q[(a[asserter])(a[exctype],
                           u[sourcecode],
                           lambda: a[tree],
                           filename=a[filename],
                           lineno=a[ln],
                           message=a[message])]

def test_expr_signals(tree):
    return _test_expr_signals_or_raises(tree, "test_signals", q[h[unpythonic_assert_signals]])
def test_expr_raises(tree):
    return _test_expr_signals_or_raises(tree, "test_raises", q[h[unpythonic_assert_raises]])

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
    filename = q[h[callsite_filename]()]
    asserter = q[h[unpythonic_assert]]

    # with test(message):
    if len(args) == 1:
        message = args[0]
    # with test:
    elif len(args) == 0:
        message = q[None]
    else:
        raise SyntaxError('Expected `with test:` or `with test(message):`')

    # Before we edit the tree, get the source code in its pre-transformation
    # state, so we can include that into the test failure message.
    #
    # We capture the source in the first pass, so that no macros in tree are
    # expanded yet. For the same reason, we process the `the[]` marks in the
    # first pass.
    sourcecode = unparse(block_body)

    envname = gensym("e")  # for injecting the captured value

    # Handle the `the[...]` marks, if any.
    block_body, the_exprs = _transform_important_subexpr(block_body, envname=envname)

    # End of first pass.
    block_body = dyn._macro_expander.visit(block_body)

    testblock_function_name = gensym("test_block")
    thetest = q[(a[asserter])(u[sourcecode],
                              n[testblock_function_name],
                              filename=a[filename],
                              lineno=a[ln],
                              message=a[message])]
    with q as newbody:
        def _insert_funcname_here_(_insert_envname_here_):
            ...
        a[thetest]
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
            if not the_exprs and type(retval) is Compare:
                # inject the implicit the[] on the LHS
                retval.left = _inject_value_recorder(envname, retval.left)
    else:
        # When there is no return statement at the top level of the `with test` block,
        # we inject a `return True` to satisfy the test when the function returns normally.
        with q as thereturn:
            return True
        block_body.extend(thereturn)

    thefunc.body = block_body

    return newbody

def _test_block_signals_or_raises(block_body, args, syntaxname, asserter):
    if not block_body:
        return []  # pragma: no cover, cannot happen through the public API.
    first_stmt = block_body[0]

    # Note we want the line number *before macro expansion*, so we capture it now.
    ln = q[u[first_stmt.lineno]] if hasattr(first_stmt, "lineno") else q[None]
    filename = q[h[callsite_filename]()]

    # with test_raises(exctype, message):
    if len(args) == 2:
        exctype, message = args
    # with test_raises(exctype):
    elif len(args) == 1:
        exctype = args[0]
        message = q[None]
    else:
        raise SyntaxError(f'Expected `with {syntaxname}(exctype):` or `with {syntaxname}(exctype, message):`')

    # Before we edit the tree, get the source code in its pre-transformation
    # state, so we can include that into the test failure message.
    #
    # We capture the source in the first pass, so that no macros in tree are
    # expanded yet.
    sourcecode = unparse(block_body)

    # End of first pass.
    block_body = dyn._macro_expander.visit(block_body)

    testblock_function_name = gensym("test_block")
    thetest = q[(a[asserter])(a[exctype],
                              u[sourcecode],
                              n[testblock_function_name],
                              filename=a[filename],
                              lineno=a[ln],
                              message=a[message])]
    with q as newbody:
        def _insert_funcname_here_():  # no env needed, since `the[]` is not meaningful here.
            ...
        a[thetest]
    thefunc = newbody[0]
    thefunc.name = testblock_function_name
    thefunc.body = block_body
    return newbody

def test_block_signals(block_body, args):
    return _test_block_signals_or_raises(block_body, args, "test_signals", q[h[unpythonic_assert_signals]])
def test_block_raises(block_body, args):
    return _test_block_signals_or_raises(block_body, args, "test_raises", q[h[unpythonic_assert_raises]])
