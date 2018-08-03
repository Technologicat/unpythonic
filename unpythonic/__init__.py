#!/usr/bin/env python3
# -*- coding: utf-8 -*
"""Lispy missing batteries for Python.

We provide two submodules which implement the ``let`` construct:

    - ``unpythonic.let``:
        Pythonic syntax, but no guarantees on evaluation order of the bindings
        (until Python 3.6; see https://www.python.org/dev/peps/pep-0468/ ).
        Bindings are declared using kwargs.

    - ``unpythonic.lispylet``:
        Guaranteed left-to-right evaluation of bindings, but clunky syntax.
        Bindings are declared as ``(("name", value), ...)``.

With ``import unpythonic``, the default ``let`` construct is ``unpythonic.let``.
To override, just import the other one; they define the same names.

See ``dir(unpythonic)`` and submodule docstrings for more.
"""

from .arity import *
from .assignonce import *
from .dynscope import *
from .ec import *
from .fploop import *
from .let import *        # no guarantees on evaluation order (before Python 3.6), nice syntax

# guaranteed evaluation order, clunky syntax
from .lispylet import let as ordered_let, letrec as ordered_letrec, \
                      dlet as ordered_dlet, dletrec as ordered_dletrec, \
                      blet as ordered_blet, bletrec as ordered_bletrec

from .misc import *
from .tco import *

__version__ = '0.3.0'
