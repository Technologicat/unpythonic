"""A minimal implementation of the Common Lisp conditions system for Python.

To keep this simple, no debugger support. And no implicit "no such function,
what would you like to do?" hook on every function call in the language. To use
conditions, you have to explicitly ask for them.

No separate base class for conditions; you can signal any exception or warning.

This module exports the core forms `signal`, `invoke`, `with restarts`,
and `with handlers`, which interlock in a very particular way (see examples).

The form `with_restarts` is an alternate syntax using a parametric decorator
and a `def` instead of a `with`. It returns a `call_with_restarts` function,
so it can also be useful if you want to set up a common restart context and
re-use instances of it for several body thunks later.

The function `find_restart` can be used for querying for the presence of a
given restart name before committing to actually invoking it. Other introspection
utilities are `available_restarts` and `available_handlers`.

The `invoker` function creates a simple *restart function* (Common Lisp term)
that just invokes the specified restart. When the restart function is created,
any extra args and kwargs given to `invoker` are frozen (by closure) to the
created function. When the created function is called, it will then pass on
its frozen args and kwargs to the restart. This can be used for creating
restart functions that send constants.

See also the `use_value` function, which invokes the eponymous restart.
The docstring gives the pattern to define similar shorthand for custom restarts.

Each of the forms `error`, `cerror` (correctable error) and `warn` implements
its own error-handling protocol on top of the core `signal` form. For the forms
`cerror` and `warn`, we also provide the ready-made invokers `proceed` and
`muffle`, respectively.

Although these three protocols cover the most common use cases, they might not
cover all conceivable uses. In such a situation just create a custom protocol;
see the existing protocols as examples.

**Acknowledgements**:

Big thanks to Alexander Artemenko (@svetlyak40wt) for the original library this
module is based on:

    https://github.com/svetlyak40wt/python-cl-conditions/

To understand conditions, see *Chapter 19: Beyond Exception Handling:
Conditions and Restarts* in *Practical Common Lisp* by Peter Seibel (2005):

    http://www.gigamonkeys.com/book/beyond-exception-handling-conditions-and-restarts.html
"""

__all__ = ["signal", "error",
           "cerror", "proceed",
           "warn", "muffle",
           "find_restart", "invoke", "use_value", "invoker",
           "available_restarts", "available_handlers",
           "restarts", "with_restarts",
           "handlers",
           "ControlError"]

import threading
from collections import deque, namedtuple
from functools import partial
from operator import itemgetter
import contextlib
import warnings

from .collections import box, unbox
from .arity import arity_includes, UnknownArity
from .misc import namelambda, equip_with_traceback, safeissubclass

_stacks = threading.local()
def _ensure_stacks():  # per-thread init
    for x in ("restarts", "handlers"):
        if not hasattr(_stacks, x):
            setattr(_stacks, x, deque())

class ControlError(Exception):
    """A condition for errors detected by the conditions system.

    Known in Common Lisp as `CONTROL-ERROR`. This is signaled by the condition
    system e.g. when trying to invoke a nonexistent restart.

    The `error` protocol **raises** `ControlError` to the user as a last resort
    when no handler handles the signal.
    """

def signal(condition, *, cause=None):
    """Signal a condition.

    Signaling a condition works similarly to raising an exception (pass an
    `Exception` or subclass instance to `signal`), but the act of signaling
    itself does **not** yet unwind the call stack.

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

    The optional `cause` argument is as in `unpythonic.misc.raisef`.
    In other words, if we pretend for a moment that `signal` is a Python
    keyword, it essentially performs a `signal ... from ...`. The default
    `cause=None` performs a plain `signal ...`.

    **Notes**

    This condition system is implemented on top of exceptions. The magic trick
    is that when a condition is signaled, we defer unwinding the call stack
    until the last possible moment.

    Once it has been determined which restart will be invoked, *then* it is
    safe to unwind (by raising a plain old exception), because then it's
    guaranteed that the stack frames between the `with restarts` block that
    will be handling the restart and the `signal` call will not be needed any
    more.

    You can signal any exception or warning object, both builtins and any
    custom ones.

    On Python 3.7 and later, the exception object representing the signaled
    condition is equipped with a traceback, just like a raised exception.
    On Python 3.6 this is not possible, so the traceback is `None`.
    """
    # Since the handler is called normally, we don't unwind the call stack,
    # remaining inside the `signal()` call in the low-level code.
    #
    # The unwinding, when it occurs, is performed when `invoke` is
    # called from inside the condition handler in the user code.

    def accepts_arg(f):
        try:
            if arity_includes(f, 1):
                return True
        except UnknownArity:  # pragma: no cover
            return True  # just assume it
        return False

    # Consistency with behavior of exceptions in Python:
    #   Even if a class is raised, as in `raise StopIteration`, the `raise` statement
    #   converts it into an instance by instantiating with no args. So we need no
    #   special handling for the "class raised" case.
    #     https://docs.python.org/3/reference/simple_stmts.html#the-raise-statement
    #     https://stackoverflow.com/questions/19768515/is-there-a-difference-between-raising-exception-class-and-exception-instance/19768732
    def canonize(exc, err_reason):
        if exc is None:
            return None
        if isinstance(exc, BaseException):  # "signal(SomeError())"
            return exc
        try:
            if issubclass(exc, BaseException):  # "signal(SomeError)"
                return exc()  # instantiate with no args, like `raise` does
        except TypeError:  # "issubclass() arg 1 must be a class"
            pass
        error(ControlError("Only exceptions and subclasses of Exception can {}; got {} with value {}.".format(err_reason, type(condition), repr(condition))))

    condition = canonize(condition, "be signaled")
    cause = canonize(cause, "act as the cause of another signal")
    condition.__cause__ = cause

    # Embed a stack trace in the signal, like Python does for raised exceptions.
    # This only works on Python 3.7 and later, because we need to create a traceback object in pure Python code.
    try:
        # In the result, omit equip_with_traceback() and signal().
        condition = equip_with_traceback(condition, stacklevel=2)
    except NotImplementedError:  # pragma: no cover
        pass  # well, we tried!

    for handler in _find_handlers(type(condition)):
        if accepts_arg(handler):
            handler(condition)
        else:
            handler()

def invoke(name_or_restart, *args, **kwargs):
    """Invoke a restart currently in scope. Known as `INVOKE-RESTART` in Common Lisp.

    `name_or_restart` can be the name of a restart, or a restart object returned
    by `find_restart`.

    If it is a name, that name will be looked up with `find_restart`. If there
    is no restart in scope matching the given name, `ControlError` is signaled
    using the `error` function.

    (If you want, you can catch the `ControlError` with another handler, and
    from there invoke some other restart. But if you really need your handler
    to shop around, maybe consider `find_restart` and a `for` loop.)

    Any args and kwargs are passed through to the restart. Refer to the particular
    restart's documentation (or source code) for what arguments it expects.

    To *handle* a condition, call `invoke` from inside your condition
    handler. The call immediately terminates the handler, transferring control
    to the restart.

    To cancel, and delegate to the next (outer) handler for the same condition
    type, return normally from the handler without calling `invoke()`.
    The return value of the handler does not matter. Any side effects the
    canceled handler performed (such as logging), up to the point where it
    returned, still occur.

    This function never returns normally.
    """
    if isinstance(name_or_restart, str):
        restart = find_restart(name_or_restart)
        if not restart:
            error(ControlError("No such restart: {}; available restarts: {}".format(repr(name_or_restart), available_restarts())))
    elif isinstance(name_or_restart, BoundRestart):
        restart = name_or_restart
    else:
        error(TypeError("Expected str or a return value of find_restart, got {} with value {}".format(type(name_or_restart), repr(name_or_restart))))
    # Found it - now we are guaranteed to unwind only up to the matching "with restarts".
    raise InvokeRestart(restart, *args, **kwargs)

use_value = partial(invoke, "use_value")
use_value.__doc__ = """Invoke the 'use_value' restart immediately with given args and kwargs.

Known as the `USE-VALUE` restart function in Common Lisp.

A handler that just invokes the `use_value` restart is such a common use case
that it is useful to have an abbreviation for it. This::

    with handlers((OhNoes, lambda c: invoke("use_value", 42))):
        ...

can be abbreviated to::

    with handlers((OhNoes, lambda c: use_value(42))):
        ...

The `lambda c:` is still required, for consistency with Common Lisp, as well as
to allow the user code to access the condition instance if needed.

(A common use case is to embed, in the condition instance, the data needed
for constructing the actual value to be sent to the `use_value` restart. In
Seibel's log file parser example, when the parser sees a corrupt log entry,
it embeds that data into the condition instance, and sends it to the handler,
which then can in principle repair the log entry, and then invoke `use_value`
with the repaired log entry.)

**Notes**:

The `use_value` function is essentially just shorthand::

    use_value = partial(invoke, "use_value")
    with handlers((OhNoes, lambda c: use_value(3.14 * c.args[0]))):
        ...

This pattern can be useful for defining similar shorthands for your own
restarts.

(Note that restarts are looked up by name, so a single module-level definition
of a shorthand for each uniquely named restart is enough. You can re-use the
same shorthand for any restart that has the same name - just like there is
just one `use_value` function, even though the `use_value` restart itself is
defined separately at each `with restarts` site that provides it (since only
each site itself knows how to "use a value").)

If you want a version for use cases where the condition instance argument is
not needed, so you could in those cases omit the `lambda c:`, you can write
that as::

    use_constant = partial(invoker, "use_value")
    with handlers((OhNoes, use_constant(42))):
        ...

Note `invoker`, not `invoke`, and we are still left with a factory (since
`invoker` itself is a factory and `partial` defers the call until it gets
more arguments). You then call the factory function with your desired
constant args/kwargs, to instantiate a handler that sends that specific
set of args/kwargs.
"""

def invoker(restart_name, *args, **kwargs):
    """Create a handler that just invokes the named restart.

    The args and kwargs are "frozen" into the created handler by closure, and
    passed through to the restart whenever the created handler triggers. This
    is useful for passing constants (i.e. any call site specific data that
    does not depend on the value of the condition instance).

    The name `invoker` is both short for *invoke restart* (but do it later)
    and describes the return value, which is an invoker.

    The returned function has the same name as the restart it invokes,
    to ease debugging, and a docstring.

    The returned function takes in a condition instance argument (so it is
    applicable as a handler), but ignores it. If you need to use that argument,
    then instead of `invoker`, see the pattern suggested in the docstring of
    `use_value`.

    If the restart cannot be found when the invoker fires, it signals
    `ControlError`.

    This is a convenience function. Using `invoker`, this::

        with handlers((OhNoes, lambda c: invoke("proceed"))):
            ...  # calling some code that may cerror(OhNoes("ouch"))

    can be shortened to::

        with handlers((OhNoes, invoker("proceed"))):
            ...

    In the specific case of the `proceed` restart, you can also use the
    ready-made function `proceed`, which is a handler that just invokes
    the eponymous restart::

        with handlers((OhNoes, proceed)):
            ...

    The `args` and `kwargs`, if any are given, are passed through to the
    restart. So, for example, if you want to send a constant to `use_value`::

        with handlers((OhNoes, lambda c: invoke("use_value", 42))):
            ...

    you can shorten this to::

        with handlers((OhNoes, invoker("use_value", 42))):
            ...  # calling some code that may cerror(OhNoes("ouch"))

    For the specific case of the `use_value` restart, you can also use the
    ready-made function `use_value`, which immediately invokes the eponymous
    restart with the args and kwargs given to it::

        with handlers((OhNoes, lambda c: use_value(42))):
            ...  # calling some code that may cerror(OhNoes("ouch"))

    (The `use_value` function is convenient especially when the value being sent
    is not a constant, but depends on data in the condition instance `c`.)

    **Notes**

    Invokers and functions like `use_value` are termed *restart functions* in
    Common Lisp.

    This function is meant for building custom simple invokers. The standard
    protocols `cerror` and `warn` come with the predefined invokers `proceed`
    and `muffle`, respectively.
    """
    rename = namelambda(restart_name)
    the_invoker = rename(lambda c: invoke(restart_name, *args, **kwargs))
    the_invoker.__doc__ = "Invoke the '{}' restart.".format(restart_name)
    return the_invoker

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
        for n, c in bindings.items():
            if not (isinstance(n, str) and callable(c)):
                error(TypeError("Each binding must be of the form name=callable"))
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

    To *handle* the condition, a handler must call `invoke()` for one
    of the restarts currently in scope. This immediately terminates the handler,
    transferring control to the restart.

    To cancel, and delegate to the next (outer) handler for the same condition
    type, a handler may return normally without calling `invoke()`. The
    return value of the handler is ignored. Any side effects the canceled
    handler performed (such as logging), up to the point where it returned,
    still occur.

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
        for t, c in bindings:
            if not (((isinstance(t, tuple) and all(safeissubclass(x, BaseException) for x in t)) or
                     safeissubclass(t, BaseException)) and
                    callable(c)):
                error(TypeError("Each binding must be of the form (type, callable) or ((t0, ..., tn), callable)"))
        super().__init__(bindings)
        self.dq = _stacks.handlers

class InvokeRestart(Exception):
    def __init__(self, restart, *args, **kwargs):  # e is the context
        self.restart, self.a, self.kw = restart, args, kwargs
        # message when uncaught
        self.args = ("unpythonic.conditions: internal error: uncaught InvokeRestart",)
    def __call__(self):
        return self.restart.function(*self.a, **self.kw)

def _find_handlers(cls):  # 0..n (though 0 is an error, handled at the calling end)
    _ensure_stacks()
    for e in _stacks.handlers:
        for t, handler in e:  # t: tuple or type
            if isinstance(t, tuple):
                if any(issubclass(cls, x) for x in t):
                    yield handler
            else:
                if issubclass(cls, t):
                    yield handler

BoundRestart = namedtuple("BoundRestart", ["name", "function", "context"])
def find_restart(name):  # exactly 1 (most recently bound wins)
    """Look up a restart. Known as `FIND-RESTART` in Common Lisp.

    If the named restart is currently in (dynamic) scope, return an opaque
    object (accepted by `invoke`) that represents that restart. The
    most recently bound restart matching the name wins.

    If no match, return `None`.

    This allows optional condition handling. You can check for the presence of
    a specific restart with `find_restart` before you commit to invoking it via
    `invoke`.
    """
    _ensure_stacks()
    for e in _stacks.restarts:
        if name in e:
            return BoundRestart(name, e[name], e)

def available_restarts():
    """Return a sorted list of restarts currently in scope.

    Name shadowing is respected; for each unique name, the return value
    contains only the most recently bound (dynamically innermost) restart.

    The return value format is `[(name, callable), ...]`. The callables are
    returned mainly to ease debugging; by printing such a callable object,
    the repr shows where to find its definition.
    """
    out = []
    seen = set()
    _ensure_stacks()
    for e in _stacks.restarts:
        for name, restart in e.items():
            if name not in seen:
                seen.add(name)
                out.append((name, restart))
    return list(sorted(out, key=itemgetter(0)))

def available_handlers():
    """Like available_restarts, but for handlers.

    As in `available_restarts`, shadowing is respected. In this case the most
    recently bound handler for a given signal type wins. When a handler bound
    to multiple signal types is encountered, it is as if that handler was bound
    separately to each of those signal types.

    The return value format is `[(type, callable), ...]`.
    """
    out = []
    seen = set()
    _ensure_stacks()
    for e in _stacks.handlers:
        for spec, handler in e:
            ts = spec if isinstance(spec, tuple) else (spec,)
            for t in ts:
                if t not in seen:
                    seen.add(t)
                    out.append((t, handler))
    return list(sorted(out, key=lambda x: x[0].__name__))

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

    A restart can take any number of args and kwargs; its call signature
    depends only on how it's intended to be invoked.

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

    If none of your restarts need to return a value, you can omit the as-binding.

    If you just need a jump label for skipping the rest of the block at the
    higher-level code's behest, you can use `lambda: None` as the restart
    function (`cerror` and `warn` do this internally).

    If you'd like to use a parametric decorator and a `def` instead of a `with`,
    see the alternate syntax `with_restarts`.
    """
    # Implementation notes:
    #
    # - Normally, an `__exit__` method of a context manager **must not**
    #   reraise if it gets an exception; this is the caller's responsibility.
    #   Instead, if the `__exit__` method wishes to indicate to the context
    #   manager framework (the `with` statement) that the exception should be
    #   propagated outwards, the method must return `False`.
    #     https://docs.python.org/3/library/stdtypes.html#typecontextmanager
    #     https://docs.python.org/3/reference/datamodel.html#context-managers
    #
    # - However, when a context manager is implemented using the
    #   `@contextmanager` decorator from `contextlib`, then the generator
    #   **must** reraise the exception (in the part after the `yield`,
    #   corresponding to `__exit__`) if it wishes to propagate it outwards.
    #   This is what we do here.
    #
    # - How does the `InvokeRestart` exception reach our generator in the first
    #   place, given that this generator is in the paused state at the time the
    #   exception is raised? The magic is in `contextlib`. When an exception is
    #   raised in the `with` body (whose context manager we are), the
    #   `@contextmanager` decorator throws the exception into the generator,
    #   into the position where it yielded. So if that `yield` is inside a
    #   `try`, the corresponding `except` clauses will get control.
    #     https://docs.python.org/3/library/contextlib.html#contextlib.contextmanager
    #
    # Regarding exceptions in generators in general, there's a pitfall to be
    # aware of: if the `finally` clause of a `try`/`finally` contains a
    # `yield`, the generator must jump through a hoop to work as expected:
    #     https://amir.rachum.com/blog/2017/03/03/generator-cleanup/
    #
    # In the `try` part it's always safe to `yield`, so in this particular
    # instance this doesn't concern us. In the `finally` part it's *possible*
    # to `yield`, but then `GeneratorExit` requires special consideration.
    #
    # Instead of using `@contextmanager`, we could have implemented `restarts`
    # using `__enter__` and `__exit__` methods. We would examine the exception
    # arguments in `__exit__`. If it was an `InvokeRestart`, and ours, we would
    # process the restart and return `True` to indicate to the `with` machinery
    # that the exception was handled and should not be propagated further. If
    # it wasn't, we would just return `False` to let the `with` machinery
    # propagate the exception. But using `@contextmanager`, we don't need a
    # class. This way the code is shorter, and our exception processing can use
    # the standard `try`/`except` construct.
    b = box(None)
    with Restarts(bindings):
        try:
            yield b
        except InvokeRestart as exc:
            if exc.restart.context is bindings:  # if it's ours
                b << exc()
            else:
                raise  # unwind this level of call stack, propagate outwards

def with_restarts(**bindings):
    """Alternate syntax. Use restarts with a `def` code block instead of a `with`.

    The def'd name is replaced by the unboxed result, so you can return a value
    from the block normally (using `return`), and don't need to unbox anything.

    Parametric decorator. Returns a `call_with_restarts` function that calls
    its argument with the restarts specified here.

    Normal usage - as a decorator::

        @with_restarts(use_value=(lambda x: x))
        def result():  # must take no parameters, essentially just a variable
            ...
            return 42
        # now `result` is either 42 or the return value of a restart

    Hifi usage - as a regular function::

        with_usevalue = with_restarts(use_value=(lambda x: x))

        # Now we can, at any time later, call any thunk in the context of the
        # restarts that were given as arguments to `with_restarts`.
        #
        # Invoking such a restart will terminate the thunk, and instead of its
        # normal return value, return whatever the restart returns.

        def dostuff():
            ...
            return 42
        result = with_usevalue(dostuff)

    If you'd like to use a `with` statement instead of a parametric decorator
    and a `def`, see the `restarts` form.
    """
    def call_with_restarts(f):
        """Call `f`, while providing the restarts stored in this closure.

        Invoking such a restart terminates `f`, and instead of its normal
        return value, returns whatever the restart returns.
        """
        with restarts(**bindings) as result:
            result << f()
        return unbox(result)
    return call_with_restarts

# Common Lisp standard error handling protocols, building on the `signal` function.
# Pythonified to add the `cause` argument.

def error(condition, *, cause=None):
    """Like `signal`, but raise `ControlError` if the condition is not handled.

    Note **raise**, not **signal**. Keep in mind the original Common Lisp
    `ERROR` function is wired to drop you into the debugger if the condition
    is not handled.

    This function never returns normally.

    Note *handled* means that a handler must actually invoke a restart; a
    condition does not count as handled simply because a handler was triggered.

    The optional `cause` argument is as in `unpythonic.misc.raisef`.
    In other words, if we pretend for a moment that `error` is a Python
    keyword, it essentially performs a `error ... from ...`. The default
    `cause=None` performs a plain `error ...`.
    """
    signal(condition, cause=cause)
    # TODO: If we want to support the debugger at some point in the future,
    # TODO: this is the appropriate point to ask the user what to do,
    # TODO: before the call stack unwinds.
    #
    # TODO: Do we want to give one last chance to handle the ControlError?
    # TODO: And do we want to raise ControlError, or the original condition?
    condition.__cause__ = cause  # chain the causes, since we'll add a new one next.
    raise ControlError("Unhandled error condition") from condition

def cerror(condition, *, cause=None):
    """Like `error`, but allow a handler to instruct the caller to ignore the error.

    `cerror` internally establishes a restart named `proceed`, which can be
    invoked to make `cerror` return normally to its caller. Like Common Lisp,
    as a convenience we export a restart function `proceed` that just invokes
    the eponymous restart (and raises `ControlError` if not found).

    We use the name "proceed" instead of Common Lisp's "continue", because in
    Python `continue` is a reserved word.

    The optional `cause` argument is as in `unpythonic.misc.raisef`.
    In other words, if we pretend for a moment that `cerror` is a Python
    keyword, it essentially performs a `cerror ... from ...`. The default
    `cause=None` performs a plain `cerror ...`.

    Example::

        # If your condition needs data, it can be passed to __init__.
        # Here this is just to illustrate - the data is unused.
        class OddNumberError(Exception):
            def __init__(self, value):
                self.value = value

        with handlers=((OddNumberError, proceed)):
            out = []
            for x in range(10):
                if x % 2 == 1:
                    cerror(OddNumberError(x))  # if unhandled, raises ControlError
                out.append(x)
        assert out == [0, 2, 4, 6, 8]

    """
    with restarts(proceed=(lambda: None)):  # just for control, no return value
        error(condition, cause=cause)

def warn(condition, *, cause=None):
    """Like `signal`, but emit a warning if the condition is not handled.

    For emitting the warning, we use Python's standard `warnings.warn` mechanism.
    Note that Python expects warning types to inherit from `Warning`.

    If the condition being signaled inherits from `Warning`, it is used as the
    `message` parameter of `warnings.warn`. This will automatically set up the
    object type as the warning category.

    If not (i.e. some other subclass of `Exception` is being signaled), the
    generic category `Warning` is used, with the message set to `str(condition)`.

    The optional `cause` argument is as in `unpythonic.misc.raisef`.
    In other words, if we pretend for a moment that `warn` is a Python
    keyword, it essentially performs a `warn ... from ...`. The default
    `cause=None` performs a plain `warn ...`.

    Example::

        class HelpMe(Warning):
            def __init__(self, value):
                self.value = value
        with handlers((HelpMe, lambda c: invoke("use_value", c.value))):
            with restarts(use_value=(lambda x: x)) as result:
                warn(RuntimeError("hello"))  # not handled; emits a warning
                ... # execution continues normally
                warn(HelpMe(21))             # handled; no warning emitted
                result << 42                 # not reached, because...
            assert unbox(result) == 21       # ...HelpMe was handled with use_value

    `warn` internally establishes a restart `muffle`, which can be invoked
    in a handler to suppress the emission of a particular warning.

    Like Common Lisp, as a convenience we export a restart function `muffle`
    that just invokes the eponymous restart (and raises `ControlError` if not
    found)::

        with handlers((HelpMe, muffle))):
            warn(HelpMe(42))  # not handled; no warning emitted
            ... # execution continues normally

    The combination of `warn` and `muffle` behaves somewhat like
    `contextlib.suppress`, except that execution continues normally
    in the caller of `warn` instead of unwinding to the handler.
    """
    with restarts(muffle=(lambda: None)):  # just for control, no return value
        with restarts(_proceed=(lambda: None)):  # for internal use by unpythonic.test.fixtures
            signal(condition, cause=cause)
        if isinstance(condition, Warning):
            warnings.warn(condition, stacklevel=2)  # 2 to ignore our lispy `warn` wrapper.
        else:
            warnings.warn(str(condition), category=Warning, stacklevel=2)

# Standard restart functions for the predefined protocols

proceed = invoker("proceed")
proceed.__doc__ = "Invoke the 'proceed' restart. Restart function for use with `cerror`."

muffle = invoker("muffle")
muffle.__doc__ = "Invoke the 'muffle' restart. Restart function for use with `warn`."
