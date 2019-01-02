# -*- coding: utf-8 -*-
"""Miscellaneous lispy constructs."""

__all__ = ["call", "callwith", "raisef", "pack", "namelambda", "Box"]

from types import LambdaType
import re

from .regutil import register_decorator

@register_decorator(priority=80)
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

      - Readability and aesthetics in cases like ``makef(mogrify(args))()``,
        where ``makef`` is a function factory, and we want to immediately
        call its result.

        Rewriting this as ``call(makef(mogrify(args)))`` relocates the odd one out
        from the mass of parentheses at the end. (A real FP example would likely
        have more levels of nesting.)

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
    return f(*args, **kwargs)

@register_decorator(priority=80)
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
        return f(*args, **kwargs)
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

def namelambda(function, name):
    """Name a lambda function.

    To avoid spurious renaming, names only once per object. If the original name
    is something other than ``<lambda>``, this has no effect.

    The original function object is modified in-place; for convenience,
    the object is returned.

    This is used by ``env``, and by the ``namedlambda`` macro.
    """
    if isinstance(function, LambdaType) and function.__name__ == "<lambda>":
        myname = "{}".format(name)
        function.__name__ = myname
        function.__qualname__ = re.sub("<lambda>$", myname, function.__qualname__)
    return function

class Box:
    """Minimalistic, mutable single-item container à la Racket.

    Motivation::

        v = 17
        def f(v):
            v = 23  # no!
        f(v)
        print(v)  # still 17

    Solution - box it, to keep the actual data in an attribute::

        b = Box(17)
        def f(b):
            b.value = 23  # yes!
        f(b)
        print(b.value)  # 23

    **Disclaimer**: maybe silly. The standard pythonic solutions are to use
    a single-item list, or the ``nonlocal`` or ``global`` statements as
    appropriate for the particular situation.
    """
    def __init__(self, value=None):
        self.value = value
    def __repr__(self):
        return "<Box at 0x{:x}, value={}>".format(id(self), self.value)
