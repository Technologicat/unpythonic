#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Write Python like Lisp: the first item is the operator.

Example::

    with prefix:
        (print, "hello world")
        t1 = (q, 1, 2, (3, 4), 5)
        x = 42
        t2 = (q, 17, 23, x)
        (print, t1, t2)

Lexically inside a ``with prefix``:

    - A bare ``q`` at the head of a tuple is the quote operator. It increases
      the quote level by one.

      It actually just tells the macro that this tuple (and everything in it,
      recursively) is not a function call. Variables can be used as usual,
      there is no need to unquote them.

    - A bare ``u`` at the head of a tuple is the unquote operator, which
      decreases the quote level by one. In other words, in::

          with prefix:
              t = (q, 1, 2, (u, print, 3), (print, 4), 5)
              (print, t)

      the third item will call ``print(3)`` and evaluate to its return value
      (in this case ``None``, since it's ``print``), whereas the fourth item
      is a tuple with the two items ``(<built-in function print>, 4)``.

    - Quote/unquote operators are parsed from the start of the tuple until
      no more remain. Then any remaining items are either returned quoted
      (if quote level > 0), or evaluated as a function call and replaced
      by the return value.

Currently, no kwarg support. Workarounds::

    from unpythonic import call

    with prefix:
        call(f, myarg=3)  # in a call(), kwargs are ok
        f(myarg=3)        # or just use Python's usual function call syntax
"""

from macropy.core.macros import Macros
from macropy.core.walkers import Walker
from macropy.core.quotes import macros, q, ast_literal

from ast import Tuple, Name

macros = Macros()

@macros.block
def prefix(tree, **kw):
    isquote = lambda tree: type(tree) is Name and tree.id == "q"
    isunquote = lambda tree: type(tree) is Name and tree.id == "u"
    @Walker
    def transform(tree, *, quotelevel, set_ctx, **kw):
        if type(tree) is not Tuple:
            return tree
        op, *data = tree.elts
        while True:
            if isunquote(op):
                if quotelevel < 1:
                    assert False, "Prefix syntax error: unquote while not in quote"
                quotelevel -= 1
            elif isquote(op):
                quotelevel += 1
            else:
                break
            set_ctx(quotelevel=quotelevel)
            if not len(data):
                assert False, "Prefix syntax error: a tuple cannot contain only quote/unquote operators"
            op, *data = data
        if quotelevel > 0:
            quoted = [op] + data
            return q[(ast_literal[quoted],)]
        # (f, a1, ..., an) --> f(a1, ..., an)
        return q[ast_literal[op](ast_literal[data])]
    return transform.recurse(tree, quotelevel=0)
