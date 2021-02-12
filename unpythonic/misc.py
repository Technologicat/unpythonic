# -*- coding: utf-8 -*-
"""Miscellaneous constructs."""

__all__ = ["call", "callwith", "raisef", "tryf", "equip_with_traceback",
           "pack", "namelambda", "timer",
           "getattrrec", "setattrrec",
           "Popper", "CountingIterator",
           "ulp",
           "slurp", "async_raise", "callsite_filename", "safeissubclass"]

from types import LambdaType, FunctionType, CodeType, TracebackType
from time import monotonic
from copy import copy
from functools import partial
from sys import version_info, float_info
from math import floor, log2
from queue import Empty
import threading
import inspect

# For async_raise only. Note `ctypes.pythonapi` is not an actual module;
# you'll get a `ModuleNotFoundError` if you try to import it.
#
# TODO: The "pycapi" PyPI package would allow us to regularly import the C API,
# but right now we don't want introduce dependencies, especially for a minor feature.
#     https://github.com/brandtbucher/pycapi
import sys
if sys.implementation.name == "cpython":
    import ctypes
    PyThreadState_SetAsyncExc = ctypes.pythonapi.PyThreadState_SetAsyncExc
else:  # pragma: no cover, coverage is measured on CPython.
    ctypes = None
    PyThreadState_SetAsyncExc = None

from .regutil import register_decorator
from .lazyutil import passthrough_lazy_args, maybe_force_args, force
from .arity import arity_includes, UnknownArity

# Only the single-argument form (just f) of the "call" decorator is supported by unpythonic.syntax.util.sort_lambda_decorators.
#
# This is as it should be; if given any arguments beside f, the call doesn't conform
# to the decorator API, but is a normal function call. See "callwith" if you need to
# pass arguments and then call f from a decorator position.
@register_decorator(priority=80)
@passthrough_lazy_args
def call(f, *args, **kwargs):
    """Call the function f.

    **When used as a decorator**:

        Run the function immediately, then overwrite the definition by its
        return value.

        Useful for making lispy not-quite-functions where the def just delimits
        a block of code that runs immediately (think call-with-something in Lisps).

        The function will be called with no arguments. If you need to pass
        arguments when using ``call`` as a decorator, see ``callwith``.

    **When called normally**:

        ``call(f, *a, **kw)`` is the same as ``f(*a, **kw)``.

    *Why ever use call() normally?*

      - Readability and aesthetics in cases like ``makef(dostuffwith(args))()``,
        where ``makef`` is a function factory, and we want to immediately
        call its result.

        Rewriting this as ``call(makef(dostuffwith(args)))`` relocates the
        odd one out from the mass of parentheses at the end. (A real FP example
        would likely have more levels of nesting.)

      - Notational uniformity with ``curry(f, *args, **kwargs)`` for cases
        without currying. See ``unpythonic.fun.curry``.

      - For fans of S-expressions. Write Python almost like Lisp!

    Name inspired by "call-with-something", but since here we're calling
    without any specific thing, it's just "call".

    Examples::

        @call
        def result():  # this block of code runs immediately
            return "hello"
        print(result)  # "hello"

        # if the return value is of no interest:
        @call
        def _():
            ...  # code with cheeky side effects goes here

        @call
        def x():
            a = 2  #    many temporaries that help readability...
            b = 3  # ...of this calculation, but would just pollute locals...
            c = 5  # ...after the block exits
            return a * b * c

        @call
        def _():
            for x in range(10):
                for y in range(10):
                    if x * y == 42:
                        return  # "multi-break" out of both loops!
                    ...

    Note that in the multi-break case, ``x`` and ``y`` are no longer in scope
    outside the block, since the block is a function.
    """
#    return f(*args, **kwargs)
    return maybe_force_args(force(f), *args, **kwargs)  # support unpythonic.syntax.lazify

@register_decorator(priority=80)
@passthrough_lazy_args
def callwith(*args, **kwargs):
    """Freeze arguments, choose function later.

    **Used as decorator**, this is like ``@call``, but with arguments::

        @callwith(3)
        def result(x):
            return x**2
        assert result == 9

    **Called normally**, this creates a function to apply the given arguments
    to a callable to be specified later::

        def myadd(a, b):
            return a + b
        def mymul(a, b):
            return a * b
        apply23 = callwith(2, 3)
        assert apply23(myadd) == 5
        assert apply23(mymul) == 6

    When called normally, the two-step application is mandatory. The first step
    stores the given arguments. It returns a function ``f(callable)``. When
    ``f`` is called, it calls its ``callable`` argument, passing in the arguments
    stored in the first step.

    In other words, ``callwith`` is similar to ``functools.partial``, but without
    specializing to any particular function. The function to be called is
    given later, in the second step.

    Hence, ``callwith(2, 3)(myadd)`` means "make a function that passes in
    two positional arguments, with values ``2`` and ``3``. Then call this
    function for the callable ``myadd``".

    But if we instead write``callwith(2, 3, myadd)``, it means "make a function
    that passes in three positional arguments, with values ``2``, ``3`` and
    ``myadd`` - not what we want in the above example.

    Curry obviously does not help; it will happily pass in all arguments
    in one go. If you want to specialize some arguments now and some later,
    use ``partial``::

        from functools import partial

        p1 = partial(callwith, 2)
        p2 = partial(p1, 3)
        p3 = partial(p2, 4)
        apply234 = p3()  # actually call callwith, get the function
        def add3(a, b, c):
            return a + b + c
        def mul3(a, b, c):
            return a * b * c
        assert apply234(add3) == 9
        assert apply234(mul3) == 24

    If the code above feels weird, it should. Arguments are gathered first,
    and the function to which they will be passed is chosen in the last step.

    A pythonic alternative to the above examples is::

        a = [2, 3]
        def myadd(a, b):
            return a + b
        def mymul(a, b):
            return a * b
        assert myadd(*a) == 5
        assert mymul(*a) == 6

        a = [2]
        a += [3]
        a += [4]
        def add3(a, b, c):
            return a + b + c
        def mul3(a, b, c):
            return a * b * c
        assert add3(*a) == 9
        assert mul3(*a) == 24

    Another use case of ``callwith`` is ``map``, if we want to vary the function
    instead of the data::

        m = map(callwith(3), [lambda x: 2*x, lambda x: x**2, lambda x: x**(1/2)])
        assert tuple(m) == (6, 9, 3**(1/2))

    The pythonic alternative here is to use the comprehension notation,
    which can already do this::

        m = (f(3) for f in [lambda x: 2*x, lambda x: x**2, lambda x: x**(1/2)])
        assert tuple(m) == (6, 9, 3**(1/2))

    Inspiration:

        *Function application with $* in
        http://learnyouahaskell.com/higher-order-functions
    """
    def applyfrozenargsto(f):
        return maybe_force_args(force(f), *args, **kwargs)
    return applyfrozenargsto

def raisef(exc, *args, cause=None, **kwargs):
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

    *Changed in v0.14.2.* The parameters have changed to match `raise` itself as closely
    as possible. Old-style parameters are still supported, but are now deprecated. Support
    for them will be dropped in v0.15.0. The old-style parameters are:

        exc: type
            The object type to raise as an exception.

        *args: anything
            Passed on to the constructor of exc.

        **kwargs: anything
            Passed on to the constructor of exc.
    """
    if args or kwargs:  # old-style parameters
        raise exc(*args, **kwargs)

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
                raise TypeError("All elements of a tuple excspec must be exception types, got {}".format(excspec))
        elif not isexceptiontype(excspec):  # single exception type
            raise TypeError("excspec must be an exception type or tuple of exception types, got {}".format(excspec))

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
        raise TypeError("exc must be an exception instance; got {} with value {}".format(type(exc), repr(exc)))
    if not isinstance(stacklevel, int):
        raise TypeError("stacklevel must be int, got {} with value {}".format(type(stacklevel), repr(stacklevel)))
    if stacklevel < 0:
        raise ValueError("stacklevel must be >= 0, got {}".format(repr(stacklevel)))

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

def pack(*args):
    """Multi-argument constructor for tuples.

    In other words, the inverse of tuple unpacking, as a function.
    E.g. ``pack(a, b, c)`` is the same as ``(a, b, c)``.

    Or, if we semantically consider a tuple as a representation for multiple
    return values, this is the identity function, returning its args.

    We provide this because the default constructor `tuple(...)` requires an
    iterable, and there are use cases (especially in Python 3.4, before PEP 448)
    where it is useful to be able to say *pack these args into a tuple*.

    See:
        https://www.python.org/dev/peps/pep-0448/

    Examples. If args naturally arrive separately::

        myzip = lambda lol: map(pack, *lol)
        lol = ((1, 2), (3, 4), (5, 6))
        for z in myzip(lol):
            print(z)

    Eliminate an ugly trailing comma::

        @looped_over(zip((1, 2, 3), ('a', 'b', 'c')), acc=())
        def p(loop, item, acc):
            numb, lett = item
            return loop(acc + pack("{:d}{:s}".format(numb, lett)))
        assert p == ('1a', '2b', '3c')
    """
    return args  # pretty much like in Lisps, (define (list . args) args)

@register_decorator(priority=5)  # allow sorting by unpythonic.syntax.sort_lambda_decorators
def namelambda(name):
    """Rename a function. Decorator.

    This can be used to give a lambda a meaningful name, which is especially
    useful for debugging in cases where a lambda is returned as a closure,
    and the actual call into it occurs much later (so that if the call crashes,
    the stack trace will report a meaningful name, not just ``"<lambda>"``).

    To support reordering by ``unpythonic.syntax.util.sort_lambda_decorators``,
    this is a standard parametric decorator, called like::

        foo = namelambda("foo")(lambda ...: ...)

    The first call returns a *foo-renamer*, and supplying the lambda to that
    actually returns a lambda that has the name *foo*.

    This is used internally by some macros (``namedlambda``, ``let``, ``do``),
    but also provided as part of unpythonic's public API in case it's useful
    elsewhere.

    **CAUTION**: When a function definition is executed, the names the parent
    scopes had at that time are baked into the function's ``__qualname__``.
    Hence renaming a function after it is defined will not affect the
    dotted names of any closures defined *inside* that function.

    This is mainly an issue for nested lambdas::

        from unpythonic import namelambda, withself
        nested = namelambda("outer")(lambda: namelambda("inner")(withself(lambda self: self)))
        print(nested.__qualname__)    # "outer"
        print(nested().__qualname__)  # "<lambda>.<locals>.inner"

    Note the inner lambda does not see the outer's new name.
    """
    def rename(f):
        if not isinstance(f, (LambdaType, FunctionType)):
            # TODO: Can't raise TypeError; @fploop et al. do-it-now-and-replace-def-with-result
            # TODO: decorators need to do this.
            return f
        f = copy(f)
        # __name__ for tools like pydoc; __qualname__ for repr(); __code__.co_name for stack traces
        #     https://stackoverflow.com/questions/40661758/name-of-a-python-function-in-a-stack-trace
        #     https://stackoverflow.com/questions/16064409/how-to-create-a-code-object-in-python
        f.__name__ = name
        idx = f.__qualname__.rfind('.')
        f.__qualname__ = "{}.{}".format(f.__qualname__[:idx], name) if idx != -1 else name
        # __code__.co_name is read-only, but there's a types.CodeType constructor
        # that we can use to re-create the code object with the new name.
        # (This is no worse than what the stdlib's Lib/modulefinder.py already does.)
        co = f.__code__
        # https://github.com/ipython/ipython/blob/master/IPython/core/interactiveshell.py
        # https://www.python.org/dev/peps/pep-0570/
        # https://docs.python.org/3/library/types.html#types.CodeType
        # https://docs.python.org/3/library/inspect.html#types-and-members
        if version_info > (3, 8, 0, 'alpha', 3):  # Python 3.8+
            f.__code__ = CodeType(co.co_argcount, co.co_posonlyargcount, co.co_kwonlyargcount,
                                  co.co_nlocals, co.co_stacksize, co.co_flags,
                                  co.co_code, co.co_consts, co.co_names,
                                  co.co_varnames, co.co_filename,
                                  name,
                                  co.co_firstlineno, co.co_lnotab, co.co_freevars,
                                  co.co_cellvars)
        else:
            f.__code__ = CodeType(co.co_argcount, co.co_kwonlyargcount,
                                  co.co_nlocals, co.co_stacksize, co.co_flags,
                                  co.co_code, co.co_consts, co.co_names,
                                  co.co_varnames, co.co_filename,
                                  name,
                                  co.co_firstlineno, co.co_lnotab, co.co_freevars,
                                  co.co_cellvars)
        return f
    return rename

class timer:
    """Simplistic context manager for performance-testing sections of code.

    Example::

        with timer() as tictoc:
            for _ in range(int(1e7)):
                pass
        print(tictoc.dt)  # elapsed time in seconds (float)

    If only interested in printing the result::

        with timer(p=True):
            for _ in range(int(1e7)):
                pass
    """
    def __init__(self, p=False):
        """p: if True, print the delta-t when done.

        Regardless of ``p``, the result is always accessible as the ``dt``.
        """
        self.p = p
    def __enter__(self):
        self.t0 = monotonic()
        return self
    def __exit__(self, exctype, excvalue, traceback):
        self.dt = monotonic() - self.t0
        if self.p:
            print(self.dt)

def getattrrec(object, name, *default):
    """Extract the underlying data from an onion of wrapper objects.

    ``r = object.name``, and then get ``r.name`` recursively, as long as
    it exists. Return the final result.

    The ``default`` parameter acts as in ``getattr``.

    See also ``setattrrec``.
    """
    o = getattr(object, name, *default)
    while hasattr(o, name):
        o = getattr(o, name, *default)
    return o

def setattrrec(object, name, value):
    """Inject data into the innermost layer in an onion of wrapper objects.

    See also ``getattrrec``.
    """
    o = object
    while hasattr(o, name) and hasattr(getattr(o, name), name):
        o = getattr(o, name)
    setattr(o, name, value)

class Popper:
    """Pop-while iterator.

    Consider this code::

        from collections import deque
        inp = deque(range(5))
        out = []
        while inp:
            x = inp.pop(0)
            out.append(x)
        assert inp == []
        assert out == list(range(5))

    ``Popper`` condenses the ``while`` and ``pop`` into a ``for``, while allowing
    the loop body to mutate the input iterable in arbitrary ways (since we never
    actually ``iter()`` it)::

        inp = deque(range(5))
        out = []
        for x in Popper(inp):
            out.append(x)
        assert inp == deque([])
        assert out == list(range(5))

        inp = deque(range(3))
        out = []
        for x in Popper(inp):
            out.append(x)
            if x < 10:
                inp.appendleft(x + 10)
        assert inp == deque([])
        assert out == [0, 10, 1, 11, 2, 12]

    (A real use case: split sequences of items, stored as lists in a deque, into
    shorter sequences where some condition is contiguously ``True`` or ``False``.
    When the condition changes state, just commit the current subsequence, and
    push the rest of that input sequence (still requiring analysis) back to the
    input deque, to be dealt with later.)

    **Notes**:

        - The argument to ``Popper`` (here ``lst``) contains the **remaining**
          items.
        - Each iteration pops an element **from the left**.
        - The loop terminates when ``lst`` is empty.
        - Per-iteration efficiency, if the input container is:

            - ``collections.deque``: ``O(1)``
            - ``list``: ``O(n)``

    Named after Karl Popper.
    """
    def __init__(self, seq):
        """seq: input container. Must support either ``popleft()`` or ``pop(0)``.

        Fully duck-typed. At least ``collections.deque`` and any
        ``collections.abc.MutableSequence`` (including ``list``) are fine.
        """
        self.seq = seq
        self._pop = seq.popleft if hasattr(seq, "popleft") else partial(seq.pop, 0)
    def __iter__(self):
        return self
    def __next__(self):
        if self.seq:
            return self._pop()
        raise StopIteration

class CountingIterator:
    """Iterator that counts how many elements it has yielded.

    The count stops updating when the original iterable raises StopIteration.
    """
    def __init__(self, iterable):
        self._it = iter(iterable)
        self.count = 0
    def __iter__(self):
        return self
    def __next__(self):
        x = next(self._it)  # let StopIteration propagate
        self.count += 1
        return x

# TODO: move to a new module unpythonic.numutil in v0.15.0.
def ulp(x):  # Unit in the Last Place
    """Given a float x, return the unit in the last place (ULP).

    This is the numerical value of the least-significant bit, as a float.
    For x = 1.0, the ULP is the machine epsilon (by definition of machine epsilon).

    See:
        https://en.wikipedia.org/wiki/Unit_in_the_last_place
    """
    eps = float_info.epsilon
    # m_min = abs. value represented by a mantissa of 1.0, with the same exponent as x has
    m_min = 2**floor(log2(abs(x)))
    return m_min * eps

def slurp(queue):
    """Slurp all items currently on a queue.Queue into a list.

    This retrieves items from the queue until it is empty, populates a list with them
    (preserving the original order), and returns that list.

    **CAUTION**: This does **not** prevent new items being added to the queue
    afterwards, or indeed by another thread while the slurping is in progress.

    This is purely a convenience function to abstract away a common operation.
    """
    out = []
    try:
        while True:
            out.append(queue.get(block=False))
    except Empty:
        pass
    return out


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
        raise TypeError("Expected a thread object, got {} with value '{}'".format(type(thread_obj), thread_obj))

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

def callsite_filename():
    """Return the filename of the call site, as a string.

    Useful as a building block for debug utilities and similar.

    The filename is grabbed from the call stack using `inspect`.
    This works also in the REPL (where `__file__` is undefined).
    """
    stack = inspect.stack()

    # Python 3.5+ have named fields here.
    #     named tuple FrameInfo(frame, filename, lineno, function, code_context, index)
    #         https://docs.python.org/3/library/inspect.html#the-interpreter-stack
    # But on 3.4:
    #     When the following functions return “frame records,” each record is a
    #     tuple of six items: the frame object, the filename, the line number of
    #     the current line, the function name, a list of lines of context from the
    #     source code, and the index of the current line within that list.
    #         https://docs.python.org/3.4/library/inspect.html#the-interpreter-stack
    # frame = stack[1].frame  # Python 3.5+
    framerecord = stack[1]
    frame = framerecord[0]

    filename = frame.f_code.co_filename
    del frame, stack
    return filename

def safeissubclass(cls, cls_or_tuple):
    """Like issubclass, but if `cls` is not a class, swallow the `TypeError` and return `False`."""
    try:
        return issubclass(cls, cls_or_tuple)
    except TypeError:  # "issubclass() arg 1 must be a class"
        pass
    return False
