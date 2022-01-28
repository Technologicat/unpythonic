# -*- coding: utf-8 -*-
"""Miscellaneous constructs."""

__all__ = ["pack",
           "namelambda",
           "timer",
           "getattrrec", "setattrrec",
           "Popper", "CountingIterator",
           "slurp",
           "callsite_filename",
           "safeissubclass"]

from copy import copy
from functools import partial
from itertools import count
import inspect
from queue import Empty
from sys import version_info
from time import monotonic
from types import CodeType, FunctionType, LambdaType

from .regutil import register_decorator

def pack(*args):
    """Multi-argument constructor for tuples.

    In other words, the inverse of tuple unpacking, as a function.
    E.g. ``pack(a, b, c)`` is the same as ``(a, b, c)``.

    We provide this because the default constructor `tuple(...)` requires an
    iterable, and there are use cases where it is useful to be able to say
    *pack these args into a tuple*.

    See also:
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
            return loop(acc + pack(f"{numb:d}{lett}"))
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
        f.__qualname__ = f"{f.__qualname__[:idx]}.{name}" if idx != -1 else name
        # __code__.co_name is read-only, but there's a types.CodeType constructor
        # that we can use to re-create the code object with the new name.
        # (This is no worse than what the stdlib's Lib/modulefinder.py already does.)
        co = f.__code__
        # https://github.com/ipython/ipython/blob/master/IPython/core/interactiveshell.py
        # https://www.python.org/dev/peps/pep-0570/
        # https://docs.python.org/3/library/types.html#types.CodeType
        # https://docs.python.org/3/library/inspect.html#types-and-members
        if version_info >= (3, 8, 0):  # Python 3.8+: positional-only parameters
            # In Python 3.8+, `CodeType` has the convenient `replace()` method to functionally update it.
            # In Python 3.10, we must actually use it to avoid losing the line number info.
            f.__code__ = f.__code__.replace(co_name=name)
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

# TODO: move `Popper` to `unpythonic.it`?
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

# TODO: move `CountingIterator` to `unpythonic.it`?
class CountingIterator:
    """Iterator that counts how many elements it has yielded.

    Wraps the original iterator of `iterable`. Simply use
    `CountingIterator(iterable)` in place of `iter(iterable)`.

    The count stops updating when the original iterator raises StopIteration.
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

def callsite_filename():
    """Return the filename of the call site, as a string.

    Useful as a building block for debug utilities and similar.

    The filename is grabbed from the call stack using `inspect`.
    This works also in the REPL (where `__file__` is undefined).
    """
    stack = inspect.stack()
    for k in count(start=1):  # ignore callsite_filename() itself
        framerecord = stack[k]
        # ignore our call-helpers
        if framerecord.function not in ("maybe_force_args",  # lazify
                                        "curried", "curry", "_currycall",  # autocurry
                                        "call", "callwith"):  # manual use of misc utils
            frame = framerecord.frame
            filename = frame.f_code.co_filename
            return filename

def safeissubclass(cls, cls_or_tuple):
    """Like issubclass, but if `cls` is not a class, swallow the `TypeError` and return `False`."""
    try:
        return issubclass(cls, cls_or_tuple)
    except TypeError:  # "issubclass() arg 1 must be a class"
        pass
    return False
