# -*- coding: utf-8 -*-
"""A simple variant of nondeterministic evaluation for Python.

This is essentially a toy that has no more power than list comprehensions
or nested for loops. An important feature of McCarthy's amb operator is its
nonlocality - being able to jump back to a choice point, even after the
dynamic extent of the function where it resides. (Sounds a lot like
``call/cc``; which is how ``amb`` is usually implemented in Scheme.)

Instead, what we have here is essentially a tuple comprehension that:

  - Can have multiple body expressions (side effects welcome!), by simply
    listing them (and making sure each returns exactly one output).

  - Presents the source code in the same order as it actually runs.

The implementation is based on the List monad. This is a hack with the bare
minimum of components to make it work, complete with a semi-usable syntax.

If you use MacroPy:

  - For a friendlier syntax for this, see ``unpythonic.syntax.forall``.

  - If you need the full(-ish) power of ``call/cc``, see
    ``unpythonic.syntax.continuations`` (which can implement ``amb``).

If you need more monads, look into the ``OSlash`` library.

If you want to roll your own monads, the parts for this module come from:
    https://github.com/Technologicat/python-3-scicomp-intro/blob/master/examples/monads.py
"""

__all__ = ["forall", "choice", "insist", "deny"]

from collections import namedtuple

from .arity import arity_includes, UnknownArity
from .llist import nil  # we need a sentinel, let's recycle the existing one

Assignment = namedtuple("Assignment", "k v")

def choice(**binding):
    """Make a nondeterministic choice.

    Example::

        forall(choice(x=range(5)),
               lambda e: e.x)
    """
    if len(binding) != 1:
        raise ValueError("Expected exactly one name=iterable pair, got {:d} with values {}".format(len(binding), binding))
    for k, v in binding.items():  # just one but we don't know its name
        return Assignment(k, v)

# Hacky code generator, because Python has ``eval`` but no syntactic macros.
# For a cleaner solution based on AST transformation with MacroPy,
# see unpythonic.syntax.forall.
def forall(*lines):
    """Nondeterministically evaluate lines.

    This is essentially a bastardized variant of Haskell's do-notation,
    specialized for the List monad.

    Examples::

        out = forall(choice(y=range(3)),
                     choice(x=range(3)),
                     lambda e: insist(e.x % 2 == 0),
                     lambda e: (e.x, e.y))
        assert out == ((0, 0), (2, 0), (0, 1), (2, 1), (0, 2), (2, 2))

        # pythagorean triples
        pt = forall(choice(z=range(1, 21)),                 # hypotenuse
                    choice(x=lambda e: range(1, e.z+1)),    # shorter leg
                    choice(y=lambda e: range(e.x, e.z+1)),  # longer leg
                    lambda e: insist(e.x*e.x + e.y*e.y == e.z*e.z),
                    lambda e: (e.x, e.y, e.z))
        assert tuple(sorted(pt)) == ((3, 4, 5), (5, 12, 13), (6, 8, 10),
                                     (8, 15, 17), (9, 12, 15), (12, 16, 20))

    Notes:

        - All choices are evaluated, depth first, and set of results is
          returned as a tuple.

        - If a line returns an iterable, it is implicitly converted into a List
          monad containing the same items.

          - This applies also to the RHS of a ``choice``.

          - As the only exception, the last line describes one item of the return
            value; there the implicit conversion is skipped.

            This allows easily returning a tuple (as one result item) from the
            computation, as in the above pythagorean triples example.

        - If a line returns a single item, it is wrapped into a singleton List
          (a List containing that one item).

        - The final result (containing all the results) is converted from
          List monad to tuple for output.

        - The values currently picked by the choices are bound to names in
          the environment. To access it, use a ``lambda e: ...`` like in
          ``unpythonic.letrec``.

    Quick vocabulary for haskellers:
        - ``forall(...)`` = ``do ...``
        - ``choice(x=foo)`` = ``x <- foo``, where ``foo`` is an iterable
        - ``insist x`` = ``guard x``
        - ``deny x`` = ``guard (not x)``
    """
    # Notation used by the monad implementation for the bind and sequence
    # operators, with any relevant whitespace.
    bind = " >> "
    seq = ".then"

    class env:
        def __init__(self):
            self.names = set()
        def assign(self, k, v):
            self.names.add(k)
            setattr(self, k, v)
        # simulate lexical closure property for env attrs
        #   - freevars: set of names that "fall in" from a surrounding lexical scope
        def close_over(self, freevars):
            names_to_clear = {k for k in self.names if k not in freevars}
            for k in names_to_clear:
                delattr(self, k)
            self.names = freevars.copy()

    # stuff used inside the eval
    e = env()
    def begin(*exprs):  # args eagerly evaluated by Python
        # begin(e1, e2, ..., en):
        #   perform side effects e1, e2, ..., e[n-1], return the value of en.
        return exprs[-1]

    allcode = ""
    names = set()  # names seen so far (working line by line, so textually!)
    bodys = []
    begin_is_open = False
    for j, item in enumerate(lines):
        is_first = (j == 0)
        is_last = (j == len(lines) - 1)

        if isinstance(item, Assignment):
            name, body = item
        else:
            name, body = None, item
        if name and not name.isidentifier():
            raise ValueError("name must be valid identifier, got {}".format(repr(name)))
        bodys.append(body)

        freevars = names.copy()  # names from the surrounding scopes
        if name:
            names.add(name)

        # on the last line, don't auto-unpack iterables,
        # to allow easily returning a tuple from the computation
        unpack_flag = "True" if not is_last else "False"

        if callable(body):
            try:
                if not arity_includes(body, 1):
                    raise TypeError("Arity mismatch; callable body must allow arity 1, to take in the environment.")
            except UnknownArity:  # pragma: no cover
                pass
            code = "monadify(bodys[{j:d}](e), {flag:s})".format(flag=unpack_flag, j=j)
        else:  # doesn't need the environment
            code = "monadify(bodys[{j:d}], {flag:s})".format(flag=unpack_flag, j=j)

        if begin_is_open:
            code += ")"
            begin_is_open = False

        # monadic-bind or sequence to the next item, leaving only the appropriate
        # names defined in the env (so that we get proper lexical scoping
        # even though we use an imperative stateful object to implement it)
        if not is_last:
            if name:
                code += "{bind:s}(lambda {n:s}:\nbegin(e.close_over({fvs}), e.assign('{n:s}', {n:s}), ".format(bind=bind, n=name, fvs=freevars)
                begin_is_open = True
            else:
                if is_first:
                    code += "{bind:s}(lambda _:\nbegin(e.close_over(set()), ".format(bind=bind)
                    begin_is_open = True
                else:
                    code += "{seq:s}(\n".format(seq=seq)

        allcode += code
    allcode += ")" * (len(lines) - 1)

#    print(allcode)  # DEBUG

    # The eval'd code doesn't close over the current lexical scope at the site
    # of the eval call, but runs in its own initially blank environment,
    # so provide the necessary names as its globals.
    mlst = eval(allcode, {"e": e, "bodys": bodys, "begin": begin, "monadify": monadify})
    return tuple(mlst)

def monadify(value, unpack=True):
    """Pack value into a monadic list if it is not already.

    If ``unpack=True``, an iterable ``value`` is unpacked into the created
    monadic list instance; if ``False``, the whole iterable is packed as one item.
    """
    if isinstance(value, MonadicList):
        return value
    elif unpack:
        try:
            return MonadicList.from_iterable(value)
        except TypeError:
            pass  # fall through
    return MonadicList(value)  # unit(List, value)

class MonadicList:  # TODO: This if anything is **the** place to use @typed.
    """A monadic list."""
    def __init__(self, *elts):
        """The unit operator. Lift value(s) into a MonadicList.

        *elts: a or [a]
        returns: M a
        """
        # Accept the sentinel nil as a special **item** that, when passed to
        # the List constructor, produces an empty list.
        if len(elts) == 1 and elts[0] is nil:
            self.x = ()
        else:
            self.x = elts

    def __rshift__(self, f):
        """Monadic bind; standard notation ">>=" in Haskell.

        self: M a
        f: a -> M b
        returns: M b

        Generally speaking, bind is defined as::
            m >> f = m.fmap(f).join()

        Specifically for `MonadicList`, bind is `flatmap`.
        """
        # bind ma f = join (fmap f ma)
        return self.fmap(f).join()
        # done manually, essentially List.from_iterable(flatmap(lambda elt: f(elt), self.x))
        #return List.from_iterable(result for elt in self.x for result in f(elt))

    def then(self, f):
        """Sequence, a.k.a. "then"; standard notation ">>" in Haskell.

        Like `bind`, but discarding the input `a`.

        self: M a
        f : M b
        returns: M b
        """
        cls = self.__class__
        if not isinstance(f, cls):
            raise TypeError("Expected a List monad, got {} with data {}".format(type(f), f))
        return self >> (lambda _: f)

    @classmethod
    def guard(cls, b):
        """Allow a branch of the computation to continue only if `b` is truthy.

        b: bool
        returns: M b

        How to use:
          - The type of `guard` is (bool -> M b). You'll want to wrap it in a function
            that takes in an `a`; then `guard` outputs the `M b`, as expected by monadic
            bind, so that you can bind your MonadicList `m` to your guard function.
          - The call to `guard` produces a dummy `MonadicList`, which will be non-blank
            (with exactly one item) if `b` is truthy, and blank if `b` is falsey.
          - Use `.then(...)` just after the `guard` to discard the dummy, and replace with
            the actual output you want. The value (that passed the guard) from the original
            `MonadicList` is still live in the current scope.
              - If you just want to filter, just `MonadicList(x)` it (recall that here the
                constructor stands for the `unit` operator).
          - When an input doesn't pass the guard, the blank output from `guard` automatically
            cancels the rest of that branch of the computation.
        """
        if b:
            return cls(True)  # List with one element; value not intended to be actually used.
        return cls()  # 0-element List; short-circuit this branch of the computation.

    # make List iterable so that "for result in f(elt)" works (when f outputs a List monad)
    def __iter__(self):
        return iter(self.x)
    def __len__(self):
        return len(self.x)
    def __getitem__(self, i):
        return self.x[i]

    def __eq__(self, other):
        if other is self:
            return True
        if len(self) != len(other):
            return False
        return other == self.x

    def __add__(self, other):
        """Concatenation of MonadicList, for convenience."""
        if not isinstance(other, MonadicList):
            raise TypeError("Expected a monadic list, got {} with value {}".format(type(other), repr(other)))
        cls = self.__class__
        return cls.from_iterable(self.x + other.x)

    def __repr__(self):  # pragma: no cover
        clsname = self.__class__.__name__
        return "{}{}".format(clsname, self.x)

    @classmethod
    def from_iterable(cls, iterable):
        """Convenience method: turn an iterable into a MonadicList.

        Eager; the input iterable will be iterated over in its entirety
        to produce the list. If it is consumable, it will be consumed.
        """
        try:
            return cls(*iterable)
        except TypeError:  # maybe a generator; try forcing it before giving up.
            return cls(*tuple(iterable))

    def copy(self):
        """Return a copy of this MonadicList."""
        cls = self.__class__
        return cls(*self.x)

    @classmethod
    def lift(cls, f):
        """Lift a regular function into a List-producing one.

        f: a -> b
        returns: a -> M b
        """
        return lambda x: cls(f(x))

    def fmap(self, f):
        """The map operator.

        self: M a
        f: a -> b
        returns: M b
        """
        cls = self.__class__
        return cls.from_iterable(f(elt) for elt in self.x)

    def join(self):
        """The join operator. Flatten nested self.

        x: M (M a)
        returns: M a
        """
        cls = self.__class__
        if not all(isinstance(elt, cls) for elt in self.x):
            raise TypeError("Expected a nested List monad, got {}".format(self.x))
        # list of lists - concat them
        return cls.from_iterable(elt for sublist in self.x for elt in sublist)

insist = MonadicList.guard  # retroactively require expr to be True
def deny(v):
    """Opposite of `insist`. End a branch of the computation if `v` is truthy."""
    return insist(not v)

# TODO: export these or not? insist and deny already cover the interesting usage.
# anything with one item (except nil), actual value is not used
ok = ("ok",)  # let the computation proceed (usually alternative to fail)
fail = ()     # end a branch of the computation
