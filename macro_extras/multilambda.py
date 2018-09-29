#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Lambda with implicit begin.

Usage::

  λ(arg0, ...)[body0, ...]

Limitations:

  - No *args or **kwargs.
  - No default values for arguments.
"""

from macropy.core.macros import Macros
from macropy.core.quotes import macros, ast_literal
from macropy.core.hquotes import macros, hq

from ast import arg

from unpythonic.seq import begin

macros = Macros()

# TODO: support default values for arguments. Requires support in MacroPy for named arguments?
@macros.expr
def λ(tree, args, **kw):
    names  = [k.id for k in (a.elts for a in args)]
    lam = hq[lambda: begin(ast_literal[tree.elts])]   # inject begin(...)
    lam.args.args = [arg(arg=x) for x in names]  # inject args
    return lam
