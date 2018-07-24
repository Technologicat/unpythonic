#!/usr/bin/env python3
# -*- coding: utf-8 -*
"""Unpythonic constructs that change the rules.

There are two ``let`` constructs provided:

    - ``unpythonic.let``:
        Pythonic syntax, but no guarantees on evaluation order of the bindings.
        Bindings are declared using kwargs.

    - ``unpythonic.lispylet``:
        Guaranteed left-to-right evaluation of bindings, but clunky syntax.
        Bindings are declared as ``(("name", value), ...)``.

With ``import unpythonic``, the default ``let`` construct is ``unpythonic.let``.
To override, just import the other one; they define the same names.

See ``dir(unpythonic)`` and submodule docstrings for more info.
"""

from .assignonce import *
from .dynscope import *
from .let import *        # no guarantees on evaluation order, nice syntax
#from .lispylet import *  # guaranteed evaluation order, clunky syntax
from .misc import *

__version__ = '0.1.0'
