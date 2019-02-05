# -*- coding: utf-8 -*
"""Supercharge your Python with parts of Lisp and Haskell.

See ``dir(unpythonic)`` and submodule docstrings for more.

If you have MacroPy installed, see also ``unpythonic.syntax``.
"""

__version__ = '0.12.1'

from .amb import *
from .arity import *
from .assignonce import *
from .collections import *
from .dynassign import *
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
