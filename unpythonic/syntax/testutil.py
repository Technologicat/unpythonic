# -*- coding: utf-8 -*-
"""Utilities for writing tests."""

from macropy.core.quotes import macros, q, u, ast_literal
from macropy.core.hquotes import macros, hq  # noqa: F811, F401
from macropy.core import unparse

from ast import Tuple, Str

from ..misc import callsite_filename
from ..conditions import cerror
from ..dynassign import make_dynvar, dyn

make_dynvar(test_signal_errors=False)  # if True, use conditions instead of exceptions to signal failed tests.

# TODO: make it possible to automatically count invocations of `test[]`, to get the total number of tests

def unpythonic_assert(sourcecode, value, filename, lineno, myname=None):
    """Custom assert function, for building test frameworks.

    If the dynvar `test_signal_errors` is truthy, then, upon a failing
    assertion, this will signal the `AssertionError` as a correctable error,
    via unpythonic's condition system (see `unpythonic.conditions.cerror`).

    If that dynvar is falsey (default), the `AssertionError` is raised.

    The idea is that `cerror` allows surrounding code to install a handler that
    invokes the `proceed` restart, so that further tests may continue to run::

        from unpythonic.syntax import macros, test

        import sys
        from unpythonic import dyn, handlers, invoke

        errors = 0
        def report(err):
            global errors
            errors += 1
            print(err, file=sys.stderr)  # or log or whatever
            invoke("proceed")

        with dyn.let(test_signal_errors=True):  # use conditions instead of exceptions
            with handlers((AssertionError, report)):
                test[2 + 2 == 5]  # fails, but allows further tests to continue
                test[2 + 2 == 4]
                test[17 + 23 == 40, "my named test"]

        assert errors == 1

    Parameters:

        `sourcecode` is a string representation of the source code expression
        that is being asserted.

        `value` is the result of running that piece source code, at the call site.
        If `value` is falsey, the assertion fails.

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
    if value:
        return

    if myname is not None:
        error_msg = "Named assertion '{}' failed".format(myname)
    else:
        error_msg = "Assertion failed"

    msg = "[{}:{}] {}: {}".format(filename, lineno, error_msg, sourcecode)
    if dyn.test_signal_errors:
        cerror(AssertionError(msg))  # use cerror() so the client code can resume (after logging and such).
    else:
        raise AssertionError(msg)

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

    return q[(ast_literal[asserter])(u[unparse(tree)],
                                     ast_literal[tree],
                                     filename=ast_literal[filename],
                                     lineno=ast_literal[ln],
                                     myname=ast_literal[myname])]
