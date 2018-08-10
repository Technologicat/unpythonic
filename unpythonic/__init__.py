#!/usr/bin/env python3
# -*- coding: utf-8 -*
"""Lispy missing batteries for Python.

See ``dir(unpythonic)`` and submodule docstrings for more.
"""

__version__ = '0.5.0'

from . import rc

from .arity import *
from .assignonce import *
from .dynscope import *
from .ec import *
from .let import *  # no guarantees on evaluation order (before Python 3.6), nice syntax

# guaranteed evaluation order, clunky syntax
from .lispylet import let as ordered_let, letrec as ordered_letrec, \
                      dlet as ordered_dlet, dletrec as ordered_dletrec, \
                      blet as ordered_blet, bletrec as ordered_bletrec

from .misc import *

# Jump through hoops to get a runtime-switchable TCO implementation.
#
# We manually emulate:
#   - making the submodule visible like __init__.py usually does
#   - from submod import *
#
def _init_tco():
    global tco
    if rc._tco_impl == "exc":
        from . import tco
    elif rc._tco_impl == "fast":
        from . import fasttco as tco
    else:
        raise ValueError("Unknown TCO implementation '{}'".format(rc._tco_impl))
    g = globals()
    for name in tco.__all__:
        g[name] = getattr(tco, name)

def _init_fploop(reload=False):
    global fploop
    from . import fploop
    # We must reload fploop, because its module-level initialization
    # performs some imports from the TCO module.
    if reload:
        from importlib import reload
        fploop = reload(fploop)
    g = globals()
    for name in fploop.__all__:
        g[name] = getattr(fploop, name)

_init_tco()
_init_fploop()

def enable_fasttco():
    """Switch to the fast TCO implementation.

    It is 2-5x faster, but pickier about its syntax, hence not the default.
    See ``unpythonic.fasttco`` for details.
    """
    rc._tco_impl = "fast"

    _init_tco()
    _init_fploop(reload=True)
