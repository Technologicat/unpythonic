#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""A simple variant of nondeterministic evaluation for Python.

This is essentially a toy that has no more power than list comprehensions
or nested for loops. An important feature of McCarthy's amb operator is its
nonlocality - being able to jump back to a choice point, even after the
dynamic extent of the function where it resides. (Sounds a lot like call/cc;
which is how amb is usually implemented in Scheme.)

Instead, what we have here is essentially a tuple comprehension that:

  - Can have multiple body expressions (side effects welcome!), by simply
    listing them (and making sure each returns exactly one output).

  - Presents the source code in the same order as it actually runs.

The implementation is based on the List monad. This is a hack with the bare
minimum of components to make it work, complete with a semi-usable syntax.

If you need more monads, look into OSlash.

Or if you want to roll your own, the parts of this module come from:
    https://github.com/Technologicat/python-3-scicomp-intro/blob/master/examples/monads.py
"""

__all__ = ["forall", "choice", "insist", "deny"]

from collections import namedtuple

from unpythonic.arity import arity_includes, UnknownArity
from unpythonic.llist import nil  # we need a sentinel, let's recycle the existing one

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

          - The last line describes one item of the return value.

        - If a line returns an iterable, it is implicitly converted into a List
          monad containing the same items.

          - This applies also to the RHS of a ``choice``.

        - If a line returns a single item, it is wrapped into a singleton List.

        - The final result is **not** unpacked. This allows easily returning
          a tuple from the computation.

          - The final result is converted from List monad to tuple for output.

        - The variables currently picked by the choices live in the environment.
          To access it, use a ``lambda e: ...`` like in ``unpythonic.letrec``.

        - The List monad is internal to this module.


    Quick vocabulary for haskellers:
        - ``forall(...)`` = ``do ...``
        - ``choice(x=foo)`` = ``x <- foo``, where ``foo`` is an iterable
        - ``insist x`` = ``guard x``
        - ``deny x`` = ``guard (not x)``
    """
    # Notation used by the monad implementation for the bind and sequence
    # operators, with any relevant whitespace.
    bind = " >> "
    seq  = ".then"

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
    def mklist(value, unpack_iterable=True):  # pack value into a List if not already
        if isinstance(value, List):
            return value
        elif unpack_iterable:
            try:
                return List.from_iterable(value)
            except TypeError:  # not iterable
                return List(value)
        return List(value)

    allcode = ""
    names = set()  # names seen so far (working line by line, so textually!)
    bodys = []
    begin_is_open = False
    for j, item in enumerate(lines):
        is_first = (j == 0)
        is_last  = (j == len(lines) - 1)

        if isinstance(item, Assignment):
            name, body = item
        else:
            name, body = None, item
        if name and not name.isidentifier():
            raise ValueError("name must be valid identifier, got '{}'".format(name))
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
                    raise ValueError("Arity mismatch; callable body must allow arity 1, to take in the environment.")
            except UnknownArity:
                pass
            code = "mklist(bodys[{j:d}](e), {flag:s})".format(flag=unpack_flag, j=j)
        else:  # doesn't need the environment
            code = "mklist(bodys[{j:d}], {flag:s})".format(flag=unpack_flag, j=j)

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

    # The eval'd code doesn't close over the current lexical scope,
    # so provide the necessary names as its globals.
    mlst = eval(allcode, {"e": e, "bodys": bodys, "begin": begin, "mklist": mklist})
    return tuple(mlst)

class List:
    """List monad."""
    def __init__(self, *elts):  # unit: x: a -> M a
        # Accept the sentinel nil as a special **item** that, when passed to
        # the List constructor, produces an empty list.
        if len(elts) == 1 and elts[0] is nil:
            self.x = ()
        else:
            self.x = elts

    def __rshift__(self, f):  # bind: x: (M a), f: (a -> M b)  -> (M b)
        # bind ma f = join (fmap f ma)
        return self.fmap(f).join()
        # done manually, essentially List.from_iterable(flatmap(lambda elt: f(elt), self.x))
        #return List.from_iterable(result for elt in self.x for result in f(elt))

    # Sequence a.k.a. "then"; standard notation ">>" in Haskell.
    def then(self, f):  # self: M a,  f : M b  -> M b
        cls = self.__class__
        if not isinstance(f, cls):
            raise TypeError("Expected a List monad, got {} with data {}".format(type(f), f))
        return self >> (lambda _: f)

    @classmethod
    def guard(cls, b):  # bool -> List   (for the list monad)
        if b:
            return cls(True)  # List with one element; value not intended to be actually used.
        return cls()  # 0-element List; short-circuit this branch of the computation.

    def __getitem__(self, i): # make List iterable so that "for result in f(elt)" works
        return self.x[i]      # (when f outputs a List monad)

    def __add__(self, other): # concatenation of Lists, for convenience
        cls = self.__class__
        return cls.from_iterable(self.x + other.x)

    def __str__(self):
        clsname = self.__class__.__name__
        return "<{} {}>".format(clsname, self.x)

    @classmethod
    def from_iterable(cls, iterable):  # convenience
        try:
            return cls(*iterable)
        except TypeError: # maybe a generator; try forcing it before giving up.
            return cls(*tuple(iterable))

    def copy(self):
        cls = self.__class__
        return cls(*self.x)

    # Lift a regular function into a List-producing one.
    @classmethod
    def lift(cls, f):         # lift: f: (a -> b)  -> (a -> M b)
        return lambda x: cls(f(x))

    def fmap(self, f):        # fmap: x: (M a), f: (a -> b)  -> (M b)
        cls = self.__class__
        return cls.from_iterable(f(elt) for elt in self.x)

    def join(self):           # join: x: M (M a)  -> M a
        cls = self.__class__
        if not all(isinstance(elt, cls) for elt in self.x):
            raise TypeError("Expected a nested List monad, got {}".format(self.x))
        # list of lists - concat them
        return cls.from_iterable(elt for sublist in self.x for elt in sublist)

insist = List.guard  # retroactively require expr to be True
def deny(expr):      # end a branch of the computation if expr is True
    return insist(not expr)

# TODO: export these or not? insist and deny already cover the interesting usage.
# anything with one item (except nil), actual value is not used
ok = ("ok",)         # let the computation proceed (usually alternative to fail)
fail = ()            # end a branch of the computation

def test():
    out = forall(choice(x=range(5)),
                 lambda e: e.x)
    assert out == tuple(range(5))

    # Because this is based on the List monad, a line that returns N items
    # causes the lines below it to be evaluated N times (once for each value).
    #
    # Note this happens even if the output is not assigned to a variable!
    #
    out = forall(range(2),  # do the rest twice
                 choice(x=range(1, 4)),
                 lambda e: e.x)
    assert out == (1, 2, 3, 1, 2, 3)

    # simple filtering
    out = forall(choice(y=range(3)),
                 choice(x=range(3)),
                 lambda e: (fail if e.x % 2 == 0 else ok),
                 lambda e: (e.x, e.y))
    assert out == ((1, 0), (1, 1), (1, 2))

    # same as:
    out = forall(choice(y=range(3)),
                 choice(x=range(3)),
                 lambda e: deny(e.x % 2 == 0),   # <-- here
                 lambda e: (e.x, e.y))
    assert out == ((1, 0), (1, 1), (1, 2))

    # the opposite of:
    out = forall(choice(y=range(3)),
                 choice(x=range(3)),
                 lambda e: insist(e.x % 2 == 0),  # <-- here
                 lambda e: (e.x, e.y))
    assert out == ((0, 0), (2, 0), (0, 1), (2, 1), (0, 2), (2, 2))

    # capture the "ok" flag
    out = forall(choice(y=range(3)),
                 choice(x=range(3)),
                 choice(z=lambda e: (fail if e.x % 2 == 0 else ok)),
                 lambda e: (e.x, e.y, e.z))
    assert out == ((1, 0, 'ok'), (1, 1, 'ok'), (1, 2, 'ok'))

    # pythagorean triples
    pt = forall(choice(z=range(1, 21)),                 # hypotenuse
                choice(x=lambda e: range(1, e.z+1)),    # shorter leg
                choice(y=lambda e: range(e.x, e.z+1)),  # longer leg
                lambda e: insist(e.x*e.x + e.y*e.y == e.z*e.z),
                lambda e: (e.x, e.y, e.z))
    assert tuple(sorted(pt)) == ((3, 4, 5), (5, 12, 13), (6, 8, 10),
                                 (8, 15, 17), (9, 12, 15), (12, 16, 20))

    print("All tests PASSED")

if __name__ == '__main__':
    test()
