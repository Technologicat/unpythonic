# -*- coding: utf-8 -*-
"""Miscellaneous lispy constructs."""

__all__ = ["call", "callwith", "raisef", "pack", "namelambda", "timer", "getattrrec", "setattrrec"]

from types import LambdaType, FunctionType, CodeType
from time import time

from .regutil import register_decorator
from .lazyutil import mark_lazy, lazycall, force

# Only the single-argument form (just f) is supported by unpythonic.syntax.util.sort_lambda_decorators.
#
# This is as it should be; if given any arguments beside f, the call doesn't conform
# to the decorator API, but is a normal function call. See "callwith" if you need to
# pass arguments and then call f from a decorator position.
@register_decorator(priority=80)
@mark_lazy
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
    return lazycall(force(f), *args, **kwargs)  # support unpythonic.syntax.lazify

@register_decorator(priority=80)
@mark_lazy
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
        return lazycall(force(f), *args, **kwargs)
    return applyfrozenargsto

def raisef(exctype, *args, **kwargs):
    """``raise`` as a function, to make it possible for lambdas to raise exceptions.

    Example::

        raisef(ValueError, "message")

    is (almost) equivalent to::

        raise ValueError("message")

    Parameters:
        exctype: type
            The object type to raise as an exception.

        *args: anything
            Passed on to the constructor of exctype.

        **kwargs: anything
            Passed on to the constructor of exctype.
    """
    raise exctype(*args, **kwargs)

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

    The original function object is modified in-place; for convenience,
    the object is returned.

    This can be used to give a lambda a meaningful name, which is especially
    useful for debugging in cases where a lambda is returned as a closure,
    and the actual call into it occurs much later (so that if the call crashes,
    the stack trace will report a meaningful name, not just ``"<lambda>"``).

    To support reordering by ``unpythonic.syntax.util.sort_lambda_decorators``,
    this is a standard parametric decorator, called like::

        foo = namelambda("foo")(lambda ...: ...)

    The first call returns a *foo-renamer*, and supplying the lambda to that
    actually modifies the lambda to have the name *foo*.

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
            return f
        # __name__ for tools like pydoc; __qualname__ for repr(); __code__.co_name for stack traces
        #     https://stackoverflow.com/questions/40661758/name-of-a-python-function-in-a-stack-trace
        #     https://stackoverflow.com/questions/16064409/how-to-create-a-code-object-in-python
        f.__name__ = name
        j = f.__qualname__.rfind('.')
        f.__qualname__ = "{}.{}".format(f.__qualname__[:j], name) if j != -1 else name
        # __code__.co_name is read-only, but there's a types.CodeType constructor
        # that we can use to re-create the code object with the new name.
        # (This is no worse than what the stdlib's Lib/modulefinder.py already does.)
        co = f.__code__
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
        self.t0 = time()
        return self
    def __exit__(self, exctype, excvalue, traceback):
        self.dt = time() - self.t0
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
