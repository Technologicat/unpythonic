#!/usr/bin/env python3
# -*- coding: utf-8 -*
"""Lispy missing batteries for Python.

See ``dir(unpythonic)`` and submodule docstrings for more.
"""

__version__ = '0.8.8'

from . import rc

from .amb import *
from .arity import *
from .assignonce import *
from .dynscope import *
from .ec import *
from .fold import *
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

# Jump through hoops to get a runtime-switchable TCO implementation.
#
# We manually emulate:
#   - making the submodule visible like __init__.py usually does
#   - from submod import *

def _starimport(module):  # same effect as "from module import *"
    g = globals()
    for name in module.__all__:
        g[name] = getattr(module, name)

def _init_tco():
    global tco
    if rc._tco_impl == "exc":
        from . import tco
    elif rc._tco_impl == "fast":
        from . import fasttco as tco
    else:
        raise ValueError("Unknown TCO implementation '{}'".format(rc._tco_impl))
    _starimport(tco)

# Modules that require reloading because their module-level initialization
# performs some from-imports from the TCO module.
def _init_fploop(reload=False):
    global fploop
    from . import fploop
    if reload:
        from importlib import reload
        fploop = reload(fploop)
    _starimport(fploop)

_init_tco()
_init_fploop()

def enable_fasttco(b=True):
    """Switch the fast TCO implementation on/off.

    It is 2-5x faster, but pickier about its syntax, hence not the default.
    See ``unpythonic.fasttco`` for details.
    """
    rc._tco_impl = "fast" if b else "exc"

    _init_tco()
    _init_fploop(reload=True)
