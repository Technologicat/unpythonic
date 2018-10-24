#!/usr/bin/env python3
# -*- coding: utf-8 -*
"""Lispy missing batteries for Python.

See ``dir(unpythonic)`` and submodule docstrings for more.
"""

__version__ = '0.10.3'

from .amb import *
from .arity import *
from .assignonce import *
from .dynscope import *
from .ec import *
from .fold import *
from .fploop import *
from .fun import *
from .fup import *
from .gmemo import *
from .gtco import *
from .it import *
from .let import *  # no guarantees on evaluation order (before Python 3.6), nice syntax

# guaranteed evaluation order, clunky syntax
from .lispylet import let as ordered_let, letrec as ordered_letrec, \
                      dlet as ordered_dlet, dletrec as ordered_dletrec, \
                      blet as ordered_blet, bletrec as ordered_bletrec

from .llist import *
from .misc import *
from .seq import *
from .tco import *
