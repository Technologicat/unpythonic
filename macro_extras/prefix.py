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

Lexically inside a ``with prefix``, a bare ``q`` at the head of a tuple is the
quote operator. It actually just tells the macro that this tuple (and everything
in it, recursively) is data, not a function call. Variables can be used as usual,
there is no need for quasiquote/unquote.

Current limitations:

  - no kwarg support
"""

from macropy.core.macros import Macros
from macropy.core.walkers import Walker
from macropy.core.quotes import macros, q, ast_literal

from ast import Tuple, Name, Str, Attribute, Subscript

from macropy.core import unparse
from astpp import dump

macros = Macros()

@macros.block
def prefix(tree, **kw):
    @Walker
    def transform(tree, *, in_quote, set_ctx, **kw):
        if in_quote or type(tree) is not Tuple:
            return tree
        first, *rest = tree.elts
        if type(first) is Name and first.id == "q":
            set_ctx(in_quote=True)
            return q[(ast_literal[rest],)]
        # (f, a1, ..., an) --> f(a1, ..., an)
        return q[ast_literal[first](ast_literal[rest])]
    return transform.recurse(tree, in_quote=False)

# experimental more lispy version: with quasiquotes
@macros.block
def prefix2(tree, **kw):
    def as_str(a, acc=""):
        if type(a) is Name:
            return Str(s="{}{}".format(a.id, acc))
        if type(a) is Attribute:
            return as_str(a.value, ".{}{}".format(a.attr, acc))
        # TODO: at least Call is also a possible type here
        assert False, "not implemented"

    @Walker
    def transform(tree, *, in_q, in_qq, set_ctx, **kw):
        if type(tree) is Subscript and type(tree.value) is Name and tree.value.id == "u":
            if not in_qq:
                assert False, "u[] is only meaningful inside a quasiquote"
            new_in_qq = in_qq[:-1]
            set_ctx(in_qq=new_in_qq)
            if new_in_qq and (type(tree.slice.value) is Name or type(tree.slice.value) is Attribute):
                return as_str(tree.slice.value)
            else:
                return tree.slice.value
        if in_q or in_qq:
            if type(tree) is Name or type(tree) is Attribute:
                return as_str(tree)
        if type(tree) is not Tuple:
            return tree
        first, *rest = tree.elts
        if type(first) is Name:
            if first.id == "q":
                set_ctx(in_q=True)
                return q[(ast_literal[rest],)]
            elif first.id == "qq":
                set_ctx(in_qq=in_qq + (True,))
                return q[(ast_literal[rest],)]
        # (f, a1, ..., an) --> f(a1, ..., an)
        return q[ast_literal[first](ast_literal[rest])]
    return transform.recurse(tree, in_q=False, in_qq=())
