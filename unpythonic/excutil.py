# -*- coding: utf-8 -*-
"""Exception-related utilities."""

__all__ = ["raisef", "tryf",
           "equip_with_traceback",
           "async_raise",
           "reraise_in", "reraise"]

from contextlib import contextmanager
import sys
import threading
from types import TracebackType

# For async_raise only. Note `ctypes.pythonapi` is not an actual module;
# you'll get a `ModuleNotFoundError` if you try to import it.
#
# TODO: The "pycapi" PyPI package would allow us to regularly import the C API,
# but right now we don't want introduce dependencies, especially for a minor feature.
#     https://github.com/brandtbucher/pycapi
if sys.implementation.name == "cpython":
    import ctypes
    PyThreadState_SetAsyncExc = ctypes.pythonapi.PyThreadState_SetAsyncExc
else:  # pragma: no cover, coverage is measured on CPython.
    ctypes = None
    PyThreadState_SetAsyncExc = None

from .arity import arity_includes, UnknownArity


def raisef(exc, *, cause=None):
    """``raise`` as a function, to make it possible for lambdas to raise exceptions.

    Example::

        raisef(ValueError("message"))

    is (almost) equivalent to::

        raise ValueError("message")

    Parameters:
        exc: exception instance, or exception class
            The object to raise. This is whatever you would give as the argument to `raise`.
            Both instances (e.g. `ValueError("oof")`) and classes (e.g. `StopIteration`)
            can be used as `exc`.

        cause: exception instance, or `None`
            If `exc` was triggered as a direct consequence of another exception,
            and you would like to `raise ... from ...`, pass that other exception
            instance as `cause`. The default `None` performs a plain `raise ...`.
    """
    if cause:
        raise exc from cause
    else:
        raise exc

def tryf(body, *handlers, elsef=None, finallyf=None):
    """``try``/``except``/``finally`` as a function.

    This allows lambdas to handle exceptions.

    ``body`` is a thunk (0-argument function) that represents
    the body of the ``try`` block.

    ``handlers`` is ``(excspec, handler), ...``, where
                 ``excspec`` is either an exception type,
                             or a tuple of exception types.
                 ``handler`` is a 0-argument or 1-argument
                             function. If it takes an
                             argument, it gets the exception
                             instance.

                 Handlers are tried in the order specified.

    ``elsef`` is a thunk that represents the ``else`` block.

    ``finallyf`` is a thunk that represents the ``finally`` block.

    Upon normal completion, the return value of ``tryf`` is
    the return value of ``elsef`` if that was specified, otherwise
    the return value of ``body``.

    If an exception was caught by one of the handlers, the return
    value of ``tryf`` is the return value of the exception handler
    that ran.

    If you need to share variables between ``body`` and ``finallyf``
    (which is likely, given what a ``finally`` block is intended
    to do), consider wrapping the ``tryf`` in a ``let`` and storing
    your variables there. If you want them to leak out of the ``tryf``,
    you can also just create an ``env`` at an appropriate point,
    and store them there.
    """
    def accepts_arg(f):
        try:
            if arity_includes(f, 1):
                return True
        except UnknownArity:  # pragma: no cover
            return True  # just assume it
        return False

    def isexceptiontype(exc):
        try:
            if issubclass(exc, BaseException):
                return True
        except TypeError:  # "issubclass() arg 1 must be a class"
            pass
        return False

    # validate handlers
    for excspec, handler in handlers:
        if isinstance(excspec, tuple):  # tuple of exception types
            if not all(isexceptiontype(t) for t in excspec):
                raise TypeError(f"All elements of a tuple excspec must be exception types, got {excspec}")
        elif not isexceptiontype(excspec):  # single exception type
            raise TypeError(f"excspec must be an exception type or tuple of exception types, got {excspec}")

    # run
    try:
        ret = body()
    except BaseException as exception:
        # Even if a class is raised, as in `raise StopIteration`, the `raise` statement
        # converts it into an instance by instantiating with no args. So we need no
        # special handling for the "class raised" case.
        #   https://docs.python.org/3/reference/simple_stmts.html#the-raise-statement
        #   https://stackoverflow.com/questions/19768515/is-there-a-difference-between-raising-exception-class-and-exception-instance/19768732
        exctype = type(exception)
        for excspec, handler in handlers:
            if isinstance(excspec, tuple):  # tuple of exception types
                # this is safe, exctype is always a class at this point.
                if any(issubclass(exctype, t) for t in excspec):
                    if accepts_arg(handler):
                        return handler(exception)
                    else:
                        return handler()
            else:  # single exception type
                if issubclass(exctype, excspec):
                    if accepts_arg(handler):
                        return handler(exception)
                    else:
                        return handler()
    else:
        if elsef is not None:
            return elsef()
        return ret
    finally:
        if finallyf is not None:
            finallyf()

def equip_with_traceback(exc, stacklevel=1):  # Python 3.7+
    """Given an exception instance exc, equip it with a traceback.

    `stacklevel` is the starting depth below the top of the call stack,
    to cull useless detail:
      - `0` means the trace includes everything, also
            `equip_with_traceback` itself,
      - `1` means the trace includes everything up to the caller,
      - And so on.

    So typically, for direct use of this function `stacklevel` should
    be `1` (so it excludes `equip_with_traceback` itself, but shows
    all stack levels from your code), and for use in a utility function
    that itself is called from your code, it should be `2` (so it excludes
    the utility function, too).

    The return value is `exc`, with its traceback set to the produced
    traceback.

    Python 3.7 and later only.

    When not supported, raises `NotImplementedError`.

    This is useful mainly in special cases, where `raise` cannot be used for
    some reason, and a manually created exception instance needs a traceback.
    (The `signal` function in the conditions-and-restarts system uses this.)

    **CAUTION**: The `sys._getframe` function exists in CPython and in PyPy3,
    but for another arbitrary Python implementation this is not guaranteed.

    Based on solution by StackOverflow user Zbyl:
        https://stackoverflow.com/a/54653137

    See also:
        https://docs.python.org/3/library/types.html#types.TracebackType
        https://docs.python.org/3/reference/datamodel.html#traceback-objects
        https://docs.python.org/3/library/sys.html#sys._getframe
    """
    if not isinstance(exc, BaseException):
        raise TypeError(f"exc must be an exception instance; got {type(exc)} with value {repr(exc)}")
    if not isinstance(stacklevel, int):
        raise TypeError(f"stacklevel must be int, got {type(stacklevel)} with value {repr(stacklevel)}")
    if stacklevel < 0:
        raise ValueError(f"stacklevel must be >= 0, got {repr(stacklevel)}")

    try:
        getframe = sys._getframe
    except AttributeError as err:  # pragma: no cover, both CPython and PyPy3 have sys._getframe.
        raise NotImplementedError("Need a Python interpreter which has `sys._getframe`") from err

    frames = []
    depth = stacklevel
    while True:
        try:
            frames.append(getframe(depth))  # 0 = top of call stack
            depth += 1
        except ValueError:  # beyond the root level
            break

    # Python 3.7+ allows creating `types.TracebackType` objects in Python code.
    try:
        tracebacks = []
        nxt = None  # tb_next should point toward the level where the exception occurred.
        for frame in frames:  # walk from top of call stack toward the root
            tb = TracebackType(nxt, frame, frame.f_lasti, frame.f_lineno)
            tracebacks.append(tb)
            nxt = tb
        if tracebacks:
            tb = tracebacks[-1]  # root level
        else:
            tb = None
    except TypeError as err:  # Python 3.6 or earlier
        raise NotImplementedError("Need Python 3.7 or later to create traceback objects") from err
    return exc.with_traceback(tb)  # Python 3.7+

# TODO: To reduce the risk of spaghetti user code, we could require a non-main thread's entrypoint to declare
# via a decorator that it's willing to accept asynchronous exceptions, and check that mark here, making this
# mechanism strictly opt-in. The decorator could inject an `asyncexc_ok` attribute to the Thread object;
# that's enough to prevent accidental misuse.
# OTOH, having no such mechanism is the simpler design.
def async_raise(thread_obj, exception):
    """Raise an exception in another thread.

    thread_obj: `threading.Thread` object
        The target thread to inject the exception into. Must be running.
    exception: ``Exception``
        The exception to be raised. As with regular `raise`, this may be
        an exception instance or an exception class object.

    No return value. Normal return indicates success.

    If the specified `threading.Thread` is not active, or the thread's ident
    was not accepted by the interpreter, raises `ValueError`.

    If the raise operation failed internally, raises `SystemError`.

    If not supported for the Python implementation we're currently running on,
    raises `NotImplementedError`.

    **NOTE**: This currently works only in CPython, because there is no Python-level
    API to achieve what this function needs to do, and PyPy3's C API emulation layer
    `cpyext` doesn't currently (January 2020) implement the function required to do
    this (and the C API functions in `cpyext` are not exposed to the Python level
    anyway, unlike CPython's `ctypes.pythonapi`).

    **CAUTION**: This is **potentially dangerous**. If the async raise
    operation fails, the interpreter may be left in an inconsistent state.

    **NOTE**: The term `async` here has nothing to do with `async`/`await`;
    instead, it refers to an asynchronous exception such as `KeyboardInterrupt`.
        https://en.wikipedia.org/wiki/Exception_handling#Exception_synchronicity

    In a nutshell, a *synchronous* exception (i.e. the usual kind of exception)
    has an explicit `raise` somewhere in the code that the thread that
    encountered the exception is running. In contrast, an *asynchronous*
    exception **doesn't**, it just suddenly magically materializes from the outside.
    As such, it can in principle happen *anywhere*, with absolutely no hint about
    it in any obvious place in the code.

    **Hence, use this function very, very sparingly, if at all.**

    For example, `unpythonic` only uses this to support remotely injecting a
    `KeyboardInterrupt` into a REPL session running in another thread. So this
    may be interesting mainly if you're developing your own REPL server/client
    pair.

    (Incidentally, that's **not** how `KeyboardInterrupt` usually works.
    Rather, the OS sends a SIGINT, which is then trapped by an OS signal
    handler that runs in the main thread. At that point the magic has already
    happened: the control of the main thread is now inside the signal handler,
    as if the signal handler was called from the otherwise currently innermost
    point on the call stack. All the handler needs to do is to perform a regular
    `raise`, and the exception will propagate correctly.

    REPL sessions running in other threads can't use the standard mechanism,
    because in CPython, OS signal handlers only run in the main thread, and even
    in PyPy3, there is no guarantee *which* thread gets the signal even if you
    use `with __pypy__.thread.signals_enabled` to enable OS signal trapping in
    some of your other threads. Only one thread (including the main thread, plus
    any currently dynamically within a `signals_enabled`) will see the signal;
    which one, is essentially random and not even reproducible.)

    See also:
        https://vorpus.org/blog/control-c-handling-in-python-and-trio/

    The function necessary to perform this magic is actually mentioned right
    there in the official CPython C API docs, but it's not very well known:
        https://docs.python.org/3/c-api/init.html#c.PyThreadState_SetAsyncExc

    Original detective work by Federico Ficarelli and LIU Wei:
        https://gist.github.com/nazavode/84d1371e023bccd2301e
        https://gist.github.com/liuw/2407154
    """
    if not ctypes or not PyThreadState_SetAsyncExc:
        raise NotImplementedError("async_raise not supported on this Python interpreter.")  # pragma: no cover

    if not hasattr(thread_obj, "ident"):
        raise TypeError(f"Expected a thread object, got {type(thread_obj)} with value '{thread_obj}'")

    target_tid = thread_obj.ident
    if target_tid not in {thread.ident for thread in threading.enumerate()}:
        raise ValueError("Invalid thread object, cannot find its ident among currently active threads.")

    affected_count = PyThreadState_SetAsyncExc(ctypes.c_long(target_tid), ctypes.py_object(exception))
    if affected_count == 0:
        raise ValueError("PyThreadState_SetAsyncExc did not accept the thread ident, even though it was among the currently active threads.")  # pragma: no cover

    # TODO: check CPython source code if this case can actually ever happen.
    #
    # The API docs seem to hint that 0 or 1 are the only possible return values.
    # If so, we can remove this `SystemError` case and the "potentially dangerous" caution.
    elif affected_count > 1:  # pragma: no cover
        # Clear the async exception, targeting the same thread identity, and hope for the best.
        PyThreadState_SetAsyncExc(ctypes.c_long(target_tid), ctypes.c_long(0))
        raise SystemError("PyThreadState_SetAsyncExc failed, broke the interpreter state.")

def reraise_in(body, mapping):
    """Remap exception types in an expression.

    This allows conveniently converting library exceptions to application
    exceptions that are more relevant for the operation being implemented,
    at the level of abstraction the operation represents.

    Usage::

        reraise_in(body,
                   {LibraryExc: ApplicationExc,
                   ...})

    Whenever `body` raises an exception `exc` for which it holds that
    `isinstance(exc, LibraryExc)`, that exception will be transparently
    chained into an `ApplicationExc`. The automatic conversion is in
    effect for the dynamic extent of `body`.

    ``body`` is a thunk (0-argument function).

    ``mapping`` is dict-like, ``{input0: output0, ...}``, where each
                 ``input``  is either an exception type,
                            or a tuple of exception types.
                            It will be matched using `isinstance`.
                 ``output`` is an exception type or an exception
                            instance. If an instance, then that exact
                            instance is raised as the converted
                            exception.

    Conversions are tried in the order specified; hence, just like in
    `except` clauses, place more specific types first.

    See also `reraise` for a block form.
    """
    try:
        return body()
    except BaseException as libraryexc:
        _reraise(mapping, libraryexc)

@contextmanager
def reraise(mapping):
    """Remap exception types. Context manager.

    This allows conveniently converting library exceptions to application
    exceptions that are more relevant for the operation being implemented,
    at the level of abstraction the operation represents.

    Usage::

        with reraise({LibraryExc: ApplicationExc, ...}):
            body0
            ...

    Whenever the body raises an exception `exc` for which it holds that
    `isinstance(exc, LibraryExc)`, that exception will be transparently
    chained into an `ApplicationExc`. The automatic conversion is in
    effect for the dynamic extent of the `with` block.

    ``mapping`` is dict-like, ``{input0: output0, ...}``, where each
                 ``input``  is either an exception type,
                            or a tuple of exception types.
                            It will be matched using `isinstance`.
                 ``output`` is an exception type or an exception
                            instance. If an instance, then that exact
                            instance is raised as the converted
                            exception.

    Conversions are tried in the order specified; hence, just like in
    `except` clauses, place more specific types first.

    See also `reraise_in` for an expression form.
    """
    try:
        yield
    except BaseException as libraryexc:
        _reraise(mapping, libraryexc)

def _reraise(mapping, libraryexc):
    """Remap an exception instance to another exception type.

    `mapping`: dict-like, `{LibraryExc0: ApplicationExc0, ...}`

        Each `LibraryExc` must be an exception type.

        Each `ApplicationExc` can be an exception type or an instance.
        If an instance, then that exact instance is raised as the
        converted exception.

    `libraryexc`: the exception instance to convert. It is
                  automatically chained into `ApplicationExc`.

    This function never returns normally. If no key in the mapping
    matches, the original exception `libraryexc` is re-raised.
    """
    for LibraryExc, ApplicationExc in mapping.items():
        if isinstance(libraryexc, LibraryExc):
            raise ApplicationExc from libraryexc
    raise
