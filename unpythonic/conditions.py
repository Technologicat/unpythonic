"""A minimal implementation of the Common Lisp conditions system for Python.

To keep this simple, no debugger support. And no implicit "no such function,
what would you like to do?" hook on function calls. To use conditions, you have
to explicitly ask for them.

This module exports the core forms `signal`, `invoke_restart`, `with restarts`,
and `with handlers`, which interlock in a very particular way (see examples).

The form `find_restart` can be used for querying for the presence of a given
restart name before committing to actually invoking it.

Each of the forms `error`, `cerror` (continuable error) and `warn` implements
its own error-handling protocol on top of the core `signal` form. Although
these three cover the most common use cases, they might not cover all
conceivable use cases. In such a situation just create a custom protocol;
see the existing protocols as examples.

**Acknowledgements**:

Big thanks to Alexander Artemenko (@svetlyak40wt) for the original library this
module is based on:

    https://github.com/svetlyak40wt/python-cl-conditions/

To understand conditions, see *Chapter 19: Beyond Exception Handling:
Conditions and Restarts* in *Practical Common Lisp* by Peter Seibel (2005):

    http://www.gigamonkeys.com/book/beyond-exception-handling-conditions-and-restarts.html
"""

__all__ = ["signal", "error", "cerror", "warn",
           "find_restart", "invoke_restart",
           "restarts", "handlers",
           "Condition", "ControlError"]

import threading
from collections import deque, namedtuple
import contextlib
from sys import stderr

from .collections import box
from .arity import arity_includes, UnknownArity

_stacks = threading.local()
def _ensure_stacks():  # per-thread init
    for x in ("restarts", "handlers"):
        if not hasattr(_stacks, x):
            setattr(_stacks, x, deque())

class Condition(Exception):
    """Base class for conditions.

    To signal a condition, pass a `Condition` or subclass instance to `signal`,
    do not `raise` it.
    """

class ControlError(Condition):
    """Condition indicating incorrect use of the conditions system.

    Known in Common Lisp as `CONTROL-ERROR`. This is signaled internally by the
    conditions system e.g. when trying to invoke a nonexistent restart.
    """

def signal(condition):
    """Signal a condition.

    Signaling a condition works like raising an exception (pass a `Condition`
    or subclass instance to `signal`), but the act of signaling itself does
    **not** yet unwind the call stack.

    The `signal` control construct gives a chance for a condition handler (see
    `with handlers`) to wrest control if it wants to, by giving it a chance to
    invoke a restart (see `with restarts`).

    Handlers bound to the type of the given condition instance run from
    dynamically innermost to dynamically outermost (with the same condition
    instance as argument), until one of them (if any) invokes a restart.

    When a restart is invoked, the caller of `signal` exits nonlocally, as if
    an exception occurred. Execution resumes from after the `with restarts`
    block containing the invoked restart.

    The critical difference between exceptions and conditions is that the
    decision of which restart to invoke may be made further out on the call
    stack than where the applicable restarts are defined. In other words, a
    condition is somewhat like an exception that consults handlers on any outer
    levels - but without unwinding the call stack - allowing the inner level to
    perform the restart and continue.

    If none of the matching handlers invokes a restart, `signal` returns
    normally. There is no meaningful return value, it is always `None`.

    If you want to error out on unhandled conditions, see `error`, which is
    otherwise the same as `signal`, except it raises if `signal` would have
    returned normally.

    **Notes**

    This condition system is implemented on top of exceptions. The magic trick
    is that when a condition is signaled, we defer unwinding the call stack
    until the last possible moment.

    Once it has been determined which restart will be invoked, *then* it is
    safe to unwind (using a plain old exception), because then it's guaranteed
    that the stack frames between the `with restarts` block that will be
    handling the restart and the `signal` call will not be needed any more.

    You can actually signal any exception, not only subclasses of `Condition`.
    This is useful when one of Python's existing exception types already covers
    the use case.
    """
    # Since the handler is called normally, we don't unwind the call stack,
    # remaining inside the `signal()` call in the low-level code.
    #
    # The unwinding, when it occurs, is performed when `invoke_restart` is
    # called from inside the condition handler in the user code.
    for handler in _find_handlers(type(condition)):
        try:
            accepts_arg = arity_includes(handler, 1)
        except UnknownArity:
            accepts_arg = True  # just assume it
        if accepts_arg:
            handler(condition)
        else:
            handler()

def invoke_restart(name_or_restart, *args, **kwargs):
    """Invoke a restart currently in scope.

    `name_or_restart` can be the name of a restart, or a restart object returned
    by `find_restart`.

    If it is a name, that name will be looked up with `find_restart`. If there
    is no restart in scope matching the given name, `ControlError` is raised.

    Any args and kwargs are passed through to the restart.

    To handle the condition, call `invoke_restart` from inside your condition
    handler. The call immediately terminates the handler, transferring control
    to the restart.

    To instead cancel, and delegate to the next (outer) handler for the same
    condition type, a handler may return normally without calling
    `invoke_restart()`.
    """
    r = find_restart(name_or_restart) if isinstance(name_or_restart, str) else name_or_restart
    if not r:
        # TODO: If we want to support the debugger at some point in the future,
        # TODO: this is the appropriate point to ask the user what to do,
        # TODO: before the call stack unwinds.
        raise ControlError("No such restart: '{}'".format(name_or_restart))
    # Now we are guaranteed to unwind only up to the matching "with restarts".
    raise InvokeRestart(r, *args, **kwargs)

class _Stacked:  # boilerplate
    def __init__(self, bindings):
        _ensure_stacks()
        self.e = bindings
    def __enter__(self):
        self.dq.appendleft(self.e)
        return self
    def __exit__(self, exctype, excvalue, traceback):
        self.dq.popleft()

class Restarts(_Stacked):
    # We must be very, very careful not to copy the environment dictionary
    # because `with restarts` tells apart instances by their `id`.
    # The `with restarts` form packs the arguments once, then we pass
    # through that dictionary instance as-is.
    def __init__(self, bindings):
        """bindings: dictionary of name (str) -> callable"""
        super().__init__(bindings)
        self.dq = _stacks.restarts

class handlers(_Stacked):
    """Set up condition handlers. Known as `HANDLER-BIND` in Common Lisp.

    Usage::

        with handlers((cls, callable), ...):
            ...

    where `cls` is a condition type (class), or a `tuple` of such types,
    just like in `except`.

    The `callable` may optionally accept one positional argument, the condition
    instance (like an `except ... as ...` clause). If you don't need data from
    the condition object (just using its type for control purposes, like an
    `except ...` clause), the handler doesn't need to accept any arguments.

    To handle the condition, a handler must call `invoke_restart()` for one of
    the restarts currently in scope. This immediately terminates the handler,
    transferring control to the restart.

    To instead cancel, and delegate to the next (outer) handler for the same
    condition type, a handler may return normally without calling
    `invoke_restart()`. The return value of the handler is ignored.

    **Notes**

    If you use only `with handlers` and `error` (no restarts), the conditions
    system reduces into an exceptions system. The `error` function plays the
    role of `raise`, and `with handlers` plays the role of `try/except`.

    If that's all you need, just use exceptions - the purpose of the conditions
    system is to allow customizing the semantics.

    Also, the condition system does not have a `finally` form. For that, use
    the usual `try/finally`, it will work fine also with conditions. Just keep
    in mind that the call stack unwinding actually occurs later than usual.
    The `finally` block will fire at unwind time, as usual.

    (Exception systems often perform double duty, providing both a throw/catch
    mechanism and an `unwind-protect` mechanism. This conditions system provides
    only a resumable throw/catch/restart mechanism.)
    """
    # This thin wrapper around `_Stacked` is all we need to provide
    # the `with handlers` form.
    def __init__(self, *bindings):
        """binding: (cls, callable)"""
        for t, _ in bindings:
            if not (isinstance(t, tuple) or issubclass(t, Exception)):
                raise ControlError("Each binding must be of the form (type, callable) or ((t0, ..., tn), callable)")
        super().__init__(bindings)
        self.dq = _stacks.handlers

class InvokeRestart(Exception):
    def __init__(self, restart, *args, **kwargs):  # e is the context
        self.restart, self.a, self.kw = restart, args, kwargs
        # message when uncaught
        self.args = ("invoke_restart() is only meaningful inside the dynamic extent of a 'with restarts'.",)
    def __call__(self):
        return self.restart.function(*self.a, **self.kw)

def _find_handlers(cls):  # 0..n (though 0 is an error, handled at the calling end)
    for e in _stacks.handlers:
        for t, handler in e:  # t: tuple or type
            if isinstance(t, tuple):
                if cls in t:
                    yield handler
            else:
                if cls is t:
                    yield handler

BoundRestart = namedtuple("BoundRestart", ["name", "function", "context"])
def find_restart(name):  # exactly 1 (most recently bound wins)
    """Look up a restart.

    If the named restart is currently in (dynamic) scope, return an opaque
    object (accepted by `invoke_restart`) that represents that restart. The
    most recently bound restart matching the name wins.

    If no match, return `None`.

    This allows optional condition handling. You can check for the presence of
    a specific restart with `find_restart` before you commit to invoking it via
    `invoke_restart`.
    """
    for e in _stacks.restarts:
        if name in e:
            return BoundRestart(name, e[name], e)

@contextlib.contextmanager
def restarts(**bindings):
    """Provide restarts. Known as `RESTART-CASE` in Common Lisp.

    Roughly, restarts can be thought of as canned error recovery strategies.
    That's the most common use case, although not the only possible one. You
    can use restarts whenever you'd like to define a set of actions to handle a
    specific condition (both in the everyday and technical senses of the word),
    while allowing code higher up the call stack to decide which of those
    actions to take in any particular use case. This improves modularity.

    Note that restarts may be defined at any level of the call stack,
    so they don't all have to be at the same level.

    Example::

        with restarts(use_value=(lambda x: x)) as result:
            ...
            result << 42

    The `with restarts` form binds an `unpythonic.collections.box` to hold the
    return value of the block. Use `unbox(result)` to access the value. The
    default value the box holds, if nothing is set into it, is `None`.

    If the code inside the `with` block invokes one of the restarts defined in
    this `with restarts`, the contents of the box are automatically set to the
    value returned by the restart. Then execution continues from immediately
    after the block.

    The manual result assignment via `<<` at the end of the block is an
    `unpythonic` idiom; it sets the return value of the block for a normal
    return, i.e. when no restart was invoked.

    We (ab)use the `with ... as ...` form, because in Python `with` is a
    statement and thus cannot return a value directly. Also, it is idiomatic
    enough to convey the meaning that `with restarts` introduces a binding.

    If your restarts don't need to return a value, you can omit the as-binding.
    """
    b = box(None)
    with Restarts(bindings):
        try:
            yield b
        except InvokeRestart as invoke:
            if invoke.restart.context is bindings:  # if it's ours
                b << invoke()
            else:
                raise  # unwind this level of call stack, propagate outwards

# Common Lisp standard error handling protocols, building on the `signal` function.

def error(condition):
    """Like `signal`, but raise `ControlError` if the condition is not handled."""
    signal(condition)
    raise ControlError("error: Unhandled condition {}".format(condition))

def cerror(condition):
    """Like `error`, but allow a handler to instruct the caller to ignore the error.

    `cerror` internally establishes a restart named `proceed`, which can be
    invoked to make `cerror` return normally.

    We use the name "proceed" instead of Common Lisp's "continue", because in
    Python `continue` is a reserved word.

    Example::

        # If your condition needs data, it can be passed to __init__.
        # Here this is just to illustrate - the data is unused.
        class OddNumberError(Condition):
            def __init__(self, value):
                self.value = value

        with handlers=((OddNumberError, lambda c: invoke_restart("proceed"))):
            out = []
            for x in range(10):
                if x % 2 == 1:
                    cerror(OddNumberError(x))  # if unhandled, raises ControlError
                out.append(x)
        assert out == [0, 2, 4, 6, 8]
    """
    with restarts(proceed=(lambda: None)):  # just for control, no return value
        error(condition)

def warn(condition):
    """Like `signal`, but emit a warning to stderr if the condition is not handled.

    Example::

        class HelpMe(Condition):
            def __init__(self, value):
                self.value = value
        with handlers((HelpMe, lambda c: invoke_restart("use_value", c.value))):
            with restarts(use_value=(lambda x: x)) as result:
                warn(RuntimeError("hello"))  # not handled; prints a warning
                ... # execution continues normally
                warn(HelpMe(21))             # handled; no warning
                result << 42                 # not reached, because...
            assert unbox(result) == 21       # ...HelpMe was handled with use_value

    `warn` internally establishes a restart `muffle_warning`, which can be
    invoked to override the printing of the warning message. This restart
    takes no arguments::

        with handlers((HelpMe, lambda c: invoke_restart("muffle_warning"))):
            warn(HelpMe(42))  # not handled; no warning
            ... # execution continues normally
    """
    with restarts(muffle_warning=(lambda: None)):  # just for control, no return value
        signal(condition)
        print("warn: {}".format(condition), file=stderr)
