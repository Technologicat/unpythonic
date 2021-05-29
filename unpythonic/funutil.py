# -*- coding: utf-8 -*-
"""Function call and return value related utilities."""

__all__ = ["call", "callwith",
           "Values", "valuify"]

from functools import wraps

from .lazyutil import passthrough_lazy_args, islazy, maybe_force_args, force
from .regutil import register_decorator
from .symbol import sym

# HACK: break dependency loop llist -> fun -> funutil -> collections -> llist
_init_done = False
frozendict = sym("frozendict")  # doesn't matter what the value is, will be overwritten later
def _init_module():  # called by unpythonic.__init__ when otherwise done
    global frozendict, _init_done
    from .collections import frozendict
    _init_done = True

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
        a block of code that runs immediately (think call-with-something in Lisps,
        but without the something).

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


class Values:
    """Structured multiple-return-values.

    That is, return multiple values positionally and by name. This completes
    the symmetry between passing function arguments and returning values
    from a function: Python itself allows passing arguments by name, but has
    no concept of returning values by name. This class adds that concept.

    Having a `Values` type separate from `tuple` also helps with semantic
    accuracy. In `unpythonic` 0.15.0 and later, a `tuple` return value now
    means just that - one value that is a `tuple`. It is different from a
    `Values` that contains several positional return values (that are meant
    to be treated separately e.g. by a function composition utility).

    **When to use**:

    Most of the time, returning a tuple to denote multiple-return-values
    and unpacking it is just fine, and that is exactly what `unpythonic`
    does internally in many places.

    But the distinction is critically important in function composition,
    so that positional return values can be automatically mapped into
    positional arguments to the next function in the chain, and named
    return values into named arguments.

    Accordingly, various parts of `unpythonic` that deal with function
    composition use the `Values` abstraction; particularly `curry`, and
    the `compose` and `pipe` families, and the `with continuations` macro.

    **Behavior**:

    `Values` is a duck-type with some features of both sequences and mappings,
    but not the full `collections.abc` API of either.

    Each operation that obviously and without ambiguity makes sense only
    for the positional or named part, accesses that part.

    The only exception is `__getitem__` (subscripting), which makes sense
    for both parts, unambiguously, because the key types differ. If the index
    expression is an `int` or a `slice`, it is an index/slice for the
    positional part. If it is an `str`, it is a key for the named part.

    If you need to explicitly access either part (and its full API),
    use the `rets` and `kwrets` attributes. The names are in analogy
    with `args` and `kwargs`.

    `rets` is a `tuple`, and `kwrets` is an `unpythonic.collections.frozendict`.

    `Values` objects can be compared for equality. Two `Values` objects
    are equal if both their `rets` and `kwrets` (respectively) are.

    Examples::

        def f():
            return Values(1, 2, 3)
        result = f()
        assert isinstance(result, Values)
        assert result.rets == (1, 2, 3)
        assert not result.kwrets
        assert result[0] == 1
        assert result[:-1] == (1, 2)
        a, b, c = result  # if no kwrets, can be unpacked like a tuple
        a, b, c = f()

        def g():
            return Values(x=3)  # named return value
        result = g()
        assert isinstance(result, Values)
        assert not result.rets
        assert result.kwrets == {"x": 3}  # actually a `frozendict`
        assert "x" in result  # `in` looks in the named part
        assert result["x"] == 3
        assert result.get("x", None) == 3
        assert result.get("y", None) is None
        assert tuple(result.keys()) == ("x",)  # also `values()`, `items()`

        def h():
            return Values(1, 2, x=3)
        result = h()
        assert isinstance(result, Values)
        assert result.rets == (1, 2)
        assert result.kwrets == {"x": 3}
        a, b = result.rets  # positionals can always be unpacked explicitly
        assert result[0] == 1
        assert "x" in result
        assert result["x"] == 3

        def silly_but_legal():
            return Values(42)
        result = silly_but_legal()
        assert result.rets[0] == 42
        assert result.ret == 42  # shorthand for single-value case

    The last example is silly, but legal, because it is preferable to just omit
    the `Values` if it is known that there is only one return value. (This also
    applies when that value is a `tuple`, when the intent is to return it as a
    single `tuple`, in contexts where this distinction matters.)
    """
    def __init__(self, *rets, **kwrets):
        """Create a `Values` object.

        `rets`: positional return values
        `kwrets`: named return values
        """
        self.rets = rets
        self.kwrets = frozendict(kwrets)

    # Shorthand for one-value case
    def _ret(self):
        return self.rets[0]
    ret = property(fget=_ret, doc="Shorthand for `self.rets[0]`. Read-only.")

    # Iterable
    def __iter__(self):
        """Values is iterable when there are no `kwrets`; this then iterates over `rets`.

        This is meant to minimize impact on existing code that receives a `tuple`
        as a pythonic multiple-return-values idiom. Changing the `return` to
        return a `Values` instead requires no changes at the receiving end
        (unless you change the sending end to return some named values;
        if you do, then it *should* yell, to avoid silently discarding
        those named values).

        Note that you can iterate over `rets` or `kwrets` to explicitly state
        which you mean; that always works.
        """
        if self.kwrets:
            raise ValueError(f"Named values present, cannot iterate over all values. Got: {self.kwrets}")
        return iter(self.rets)

    # Sequence (no full support: no `__len__`, `__reversed__`, `index`, `count`)
    def __getitem__(self, idx):
        """Subscripting.

        Indexing by an `int` or `slice` indexes the positional part.
        Indexing by an `str` indexes the named part.

        Indexing by any other type raises `TypeError`.
        """
        # multi-headed hydra
        if isinstance(idx, (int, slice)):
            return self.rets[idx]
        elif isinstance(idx, str):
            return self.kwrets[idx]
        raise TypeError(f"Expected either int, slice or str subscript, got {type(idx)} with value {repr(idx)}")

    # Container
    def __contains__(self, k):
        """The `in` operator, looks in the named part."""
        return k in self.kwrets

    # Mapping (no full support: no `__len__`)
    def items(self):
        """Items of the named part."""
        return self.kwrets.items()
    def keys(self):
        """Keys of the named part."""
        return self.kwrets.keys()
    def values(self):
        """Values of the named part."""
        return self.kwrets.values()
    def get(self, k, default=None):
        """Dict-like `get` for the named part."""
        return self[k] if k in self else default

    # comparison
    def __eq__(self, other):
        """Equality comparison.

        Two `Values` objects are equal if both their `rets` and `kwrets`
        (respectively) are.
        """
        if not isinstance(other, Values):
            return False
        return other.rets == self.rets and other.kwrets == self.kwrets
    def __ne__(self, other):
        """Inequality comparison."""
        return not (self == other)

    # no `__len__`, because we have two candidates

    # pretty-printing
    def __repr__(self):  # pragma: no cover
        """Pretty-printing. Eval-able if the contents are."""
        rets_list = [repr(x) for x in self.rets]
        rets_str = ", ".join(rets_list)
        kwrets_list = [f"{name}={repr(value)}" for name, value in self.kwrets.items()]
        kwrets_str = ", ".join(kwrets_list)
        sep = ", " if self.rets and self.kwrets else ""
        return f"Values({rets_str}{sep}{kwrets_str})"


@register_decorator(priority=30)
def valuify(f):
    """Decorator. Convert the pythonic tuple-as-multiple-return-values idiom into `Values`.

    If `f` returns `tuple` (exactly, no subclass), convert into `Values`, else pass through.
    """
    @wraps(f)
    def valuified(*args, **kwargs):
        result = f(*args, **kwargs)
        if type(result) is tuple:  # yes, exactly tuple
            result = Values(*result)
        return result
    if islazy(f):
        valuified = passthrough_lazy_args(valuified)
    return valuified
