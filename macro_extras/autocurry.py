#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Automatic currying for Python. Macro implementation.

Usage::

    from autocurry import macros, curry

    with curry:
        ... # all function calls here are auto-curried, except builtins
"""

from macropy.core.macros import Macros
from macropy.core.walkers import Walker
from macropy.core.hquotes import macros, hq

from ast import Call, With, withitem

from unpythonic import curry as curryf
from unpythonic import dyn

macros = Macros()

@macros.block
def curry(tree, **kw):  # technically a forest; list of trees, the body of the with block
    @Walker
    def transform_call(tree, **kw):  # technically a node containing the current subtree
        if type(tree) is Call:
            newargs = []
            newargs.append(tree.func)
            newargs.extend(tree.args)
            tree.args = newargs
            tree.func = hq[curryf]
        return tree
    body = transform_call.recurse(tree)
    # Wrap the body in "with dyn.let(_curry_allow_uninspectable=True):"
    # to avoid crash with builtins (uninspectable)
    item = hq[dyn.let(_curry_allow_uninspectable=True)]
    wrapped = With(items=[withitem(context_expr=item)],
                   body=body)
    return [wrapped]  # block macro: got a list, must return a list.
