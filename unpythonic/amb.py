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

The implementation is based on the list monad. This is a hack with the bare
minimum of components to make it work, complete with a semi-usable syntax.

If you use `mcpyrate`:

  - For a friendlier syntax for this, see ``unpythonic.syntax.forall``.

  - If you need the full(-ish) power of ``call/cc``, see
    ``unpythonic.syntax.continuations`` (which can implement ``amb``).

If you need more monads, look into the ``OSlash`` library.

If you want to roll your own monads, the parts for this module come from:
    https://github.com/Technologicat/python-3-scicomp-intro/blob/master/examples/monads.py
"""

__all__ = ["forall", "choice", "insist", "deny"]

from collections import namedtuple
from collections.abc import Callable, Iterable
from typing import Any

from .arity import arity_includes, UnknownArity
from .monads.list import List

Choice = namedtuple("Choice", "k v")

def choice(**binding: Iterable) -> Choice:
    """Make a nondeterministic choice.

    Example::

        forall(choice(x=range(5)),
               lambda e: e.x)
    """
    if len(binding) != 1:
        raise ValueError(f"Expected exactly one name=iterable pair, got {len(binding)} with values {binding}")
    for k, v in binding.items():  # just one but we don't know its name
        return Choice(k, v)

# Hacky code generator, because Python has ``eval`` but no syntactic macros.
# For a cleaner solution based on AST transformation with macros,
# see unpythonic.syntax.forall.
def forall(*lines: Choice | Callable) -> tuple:
    """Nondeterministically evaluate lines.

    This is essentially a bastardized variant of Haskell's do-notation,
    specialized for the list monad.

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

        - If a line returns an iterable, it is implicitly converted into a
          list monad containing the same items.

          - This applies also to the RHS of a ``choice``.

          - As the only exception, the last line describes one item of the return
            value; there the implicit conversion is skipped.

            This allows easily returning a tuple (as one result item) from the
            computation, as in the above pythagorean triples example.

        - If a line returns a single item, it is wrapped into a singleton
          list monad (a MonadicList containing that one item).

        - The final result (containing all the results) is converted from
          the list monad to tuple for output.

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

    class Scope:
        def __init__(self) -> None:
            self.names: set[str] = set()
        def assign(self, k: str, v: Any) -> None:
            """Assign value ``v`` to name ``k`` in this ``Scope``."""
            self.names.add(k)
            setattr(self, k, v)
        def close_over(self, freevars: set[str]) -> None:
            """Simulate lexical closure property for scope attrs.

            ``freevars``: set of names that "fall in" from a surrounding scope.
            """
            names_to_clear = {k for k in self.names if k not in freevars}
            for k in names_to_clear:
                delattr(self, k)
            self.names = freevars.copy()

    # stuff used inside the eval
    e = Scope()
    def begin(*exprs: Any) -> Any:  # args eagerly evaluated by Python
        """begin(e1, e2, ..., en): perform side effects e1, e2, ..., e[n-1], return the value of en."""
        return exprs[-1]

    allcode = ""
    names = set()  # names seen so far (working line by line, so textually!)
    bodys = []
    begin_is_open = False
    for j, item in enumerate(lines):
        is_first = (j == 0)
        is_last = (j == len(lines) - 1)

        if isinstance(item, Choice):
            name, body = item
        else:
            name, body = None, item
        if name and not name.isidentifier():
            raise ValueError(f"name must be valid identifier, got {repr(name)}")
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
            code = f"monadify(bodys[{j}](e), {unpack_flag})"
        else:  # doesn't need the environment
            code = f"monadify(bodys[{j}], {unpack_flag})"

        if begin_is_open:
            code += ")"
            begin_is_open = False

        # monadic-bind or sequence to the next item, leaving only the appropriate
        # names defined in the scope (so that we get proper lexical scoping
        # even though we use an imperative stateful object to implement it)
        if not is_last:
            if name:
                code += f"{bind}(lambda {name}:\nbegin(e.close_over({freevars}), e.assign('{name}', {name}), "
                begin_is_open = True
            else:
                if is_first:
                    code += f"{bind}(lambda _:\nbegin(e.close_over(set()), "
                    begin_is_open = True
                else:
                    code += f"{seq}(\n"

        allcode += code
    allcode += ")" * (len(lines) - 1)

#    print(allcode)  # DEBUG

    # The eval'd code doesn't close over the current lexical scope at the site
    # of the eval call, but runs in its own initially blank environment,
    # so provide the necessary names as its globals.
    mlst = eval(allcode, {"e": e, "bodys": bodys, "begin": begin, "monadify": monadify})
    return tuple(mlst)

# --------------------------------------------------------------------------------
# This low-level machinery is shared with the macro version, `unpythonic.syntax.forall`.

def monadify(value: Any, unpack: bool = True) -> "MonadicList":
    """Pack ``value`` into a monadic list if it is not already.

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
    return MonadicList(value)  # unit: varargs form — singleton list containing value

# TODO(3.0.0): remove this deprecated alias. Users should import `List`
# directly from `unpythonic.monads`.
MonadicList = List

insist = MonadicList.guard  # retroactively require expr to be True
def deny(v: Any) -> Any:
    """Opposite of `insist`. End a branch of the computation if `v` is truthy."""
    return insist(not v)

# TODO: export these or not? insist and deny already cover the interesting usage.
# anything with one item (except nil), actual value is not used
ok = ("ok",)  # let the computation proceed (usually alternative to fail)
fail = ()     # end a branch of the computation
