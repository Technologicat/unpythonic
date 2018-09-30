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
      recursively) is not a function call.

      Variables can be used as usual, there is no need to unquote them.

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

    - How to pass named args::

          from unpythonic.misc import call

          with prefix:
              (f, kw(myarg=3))  # ``kw(...)`` (syntax, not really a function!)
              call(f, myarg=3)  # in a call(), kwargs are ok
              f(myarg=3)        # or just use Python's usual function call syntax

      One ``kw`` operator may include any number of named args (and **only**
      named args). The tuple may have any number of ``kw`` operators.

      All named args are collected from ``kw`` operators in the tuple
      when writing the final function call. If the same kwarg has been
      specified by multiple ``kw`` operators, the rightmost one wins.

      **Note**: Python itself prohibits having repeated named args in the **same**
      ``kw`` operator, because it uses the function call syntax. If you get a
      `SyntaxError: keyword argument repeated` with no useful traceback,
      check any recent ``kw`` operators you have added in prefix blocks.

      A ``kw(...)`` operator in a quoted tuple (not a function call) is an error.

Current limitations:

    - passing ``*args`` and ``**kwargs`` not supported
      (workarounds: ``call(...)``; Python's usual function call syntax)
"""

from macropy.core.macros import Macros
from macropy.core.walkers import Walker
from macropy.core.quotes import macros, q, ast_literal

from ast import Tuple, Name, Call

from unpythonic import flatmap, uniqify, rev

from astpp import dump

macros = Macros()

@macros.block
def prefix(tree, **kw):
    isquote = lambda tree: type(tree) is Name and tree.id == "q"
    isunquote = lambda tree: type(tree) is Name and tree.id == "u"
    def iskwargs(tree):
        if type(tree) is not Call: return False
        if type(tree.func) is not Name: return False
        return tree.func.id == "kw"
    @Walker
    def transform(tree, *, quotelevel, set_ctx, **kw):
        if type(tree) is not Tuple:
            return tree
        op, *data = tree.elts
        while True:
            if isunquote(op):
                if quotelevel < 1:
                    assert False, "unquote while not in quote"
                quotelevel -= 1
            elif isquote(op):
                quotelevel += 1
            else:
                break
            set_ctx(quotelevel=quotelevel)
            if not len(data):
                assert False, "a prefix tuple cannot contain only quote/unquote operators"
            op, *data = data
        if quotelevel > 0:
            quoted = [op] + data
            if any(iskwargs(x) for x in quoted):
                assert False, "kw(...) may only appear in a prefix tuple representing a function call"
            return q[(ast_literal[quoted],)]
        # (f, a1, ..., an) --> f(a1, ..., an)
        posargs = [x for x in data if not iskwargs(x)]
        # TODO: tag *args and **kwargs in a kw() as invalid, too (currently just ignored)
        invalids = list(flatmap(lambda x: x.args, filter(iskwargs, data)))
        if invalids:
            assert False, "kw(...) may only specify named args"
        kwargs = flatmap(lambda x: x.keywords, filter(iskwargs, data))
        kwargs = list(uniqify(rev(kwargs), key=lambda x: x.arg))  # latest wins
        return Call(func=op, args=posargs, keywords=list(kwargs))
    return transform.recurse(tree, quotelevel=0)

# note the exported "q" is ours, but the q we use in this module is a macro.
class q:
    """[syntax] Quote operator. Only meaningful in a tuple in a prefix block."""
    def __repr__(self):  # in case one of these ends up somewhere at runtime
        return "<quote>"
q = q()

class u:
    """[syntax] Unquote operator. Only meaningful in a tuple in a prefix block."""
    def __repr__(self):  # in case one of these ends up somewhere at runtime
        return "<unquote>"
u = u()

def kw(**kwargs):
    """[syntax] Pass-named-args operator. Only meaningful in a tuple in a prefix block."""
    raise RuntimeError("kw only meaningful inside a tuple in a prefix block")
