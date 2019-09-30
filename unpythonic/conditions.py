"""A minimal implementation of the Common Lisp conditions system for Python.

To keep this simple, no debugger support. And no implicit "no such function,
what would you like to do?" hook on function calls. To use conditions, you have
to explicitly ask for them.

This module exports four forms: `signal`, `invoke_restart`, `with restarts`,
and `with handlers`, which interlock in a very particular way. Usage::

    def lowlevel():
        # define here what actions are available when stuff goes wrong
        # in this low-level code
        with restarts(use_value=...,
                      do_something_else=...):
            ...
            # When stuff goes wrong, ask the caller what we should do
            x = ... if our_usual_case else signal("help_me")
            ...

    # high-level code - choose here which action to take for each named signal
    with handlers(help_me=(lambda: invoke_restart("use_value"))):
        lowlevel()

This arrangement improves modularity. The high-level code may reside in a
completely different part of the application, and/or be written only much
later. The implementer of low-level code can provide a set of canned
error-recovery strategies *appropriate for that low-level code, for any future
user*, but leave to each call site the ultimate decision of which strategy to
pick in any particular use case.


**Acknowledgements**:

Big thanks to Alexander Artemenko (@svetlyak40wt) for the original library this
module is based on:

    https://github.com/svetlyak40wt/python-cl-conditions/

To understand conditions, see *Chapter 19: Beyond Exception Handling:
Conditions and Restarts* in *Practical Common Lisp* by Peter Seibel (2005):

    http://www.gigamonkeys.com/book/beyond-exception-handling-conditions-and-restarts.html
"""

__all__ = ["signal", "invoke_restart", "restarts", "handlers"]

import threading
from collections import deque

_stacks = threading.local()
def _ensure_stacks():  # per-thread init
    for x in ("restarts", "handlers"):
        if not hasattr(_stacks, x):
            setattr(_stacks, x, deque())

class ConditionError(RuntimeError):
    """Represents a runtime error detected by the conditions system."""

def signal(condition_name, *args, **kwargs):
    """Signal a condition.

    Any args and kwargs are passed through to the condition handler.

    The return value of `signal()` is the return value of the restart that was
    invoked by the handler that chose to handle the condition.

    Call `signal` in your low-level logic to indicate that something exceptional
    just occurred, and a *condition handler* defined in higher-level code now
    needs to choose which recovery strategy (out of those defined by the
    low-level code) should be taken.

    To handle the condition, a handler must call `invoke_restart()` for one of
    the restarts currently in scope. This immediately terminates the handler,
    transferring control to the restart.

    To instead cancel, and delegate to the next (outer) handler for the same
    condition type, a handler may return normally without calling
    `invoke_restart()`. The return value of the handler is ignored.
    """
    try:
        for handler in _find_handlers(condition_name):
            # Since the handler is called normally, it does not unwind the call stack.
            # We remain inside the `signal()` call in the low-level code.
            handler(*args, **kwargs)
    except _DelayedCall as invoke:
        return invoke()
    else:
        raise ConditionError("Unhandled condition '{}'".format(condition_name))

def invoke_restart(restart_name, *args, **kwargs):
    """Invoke a restart currently in scope.

    restart_name is used to look up the most recently bound restart matching
    the name.

    Any args and kwargs are passed through to the restart.

    To handle the condition, call `invoke_restart` from inside your condition
    handler in your high-level logic. The call immediately terminates the
    handler, transferring control to the restart.

    To instead cancel, and delegate to the next (outer) handler for the same
    condition type, a handler may return normally without calling
    `invoke_restart()`.
    """
    f = _find_restart(restart_name)
    raise _DelayedCall(f, *args, **kwargs)

class _Stacked:  # boilerplate
    def __init__(self, **bindings):
        _ensure_stacks()
        self.e = bindings
    def __enter__(self):
        self.dq.appendleft(self.e)
        return self
    def __exit__(self, exctype, excvalue, traceback):
        self.dq.popleft()

class restarts(_Stacked):
    """Context manager: a dynamic let for restarts."""
    def __init__(self, **bindings):
        """binding: name (str) -> callable"""
        super().__init__(**bindings)
        self.dq = _stacks.restarts

class handlers(_Stacked):
    """Context manager: a dynamic let for condition handlers."""
    def __init__(self, **bindings):
        """binding: name (str) -> callable"""
        super().__init__(**bindings)
        self.dq = _stacks.handlers

class _DelayedCall(Exception):
    def __init__(self, f, *args, **kwargs):
        self.f, self.args, self.kwargs = f, args, kwargs
    def __call__(self):
        return self.f(*self.args, **self.kwargs)

def _find_handlers(name):  # 0..n (though 0 is an error, handled at the calling end)
    for e in _stacks.handlers:
        if name in e:
            yield e[name]

def _find_restart(name):  # exactly 1 (most recently bound wins)
    for e in _stacks.restarts:
        if name in e:
            return e[name]
    raise ConditionError("Restart '{}' not found".format(name))
