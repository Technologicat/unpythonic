#!/usr/bin/env python3
# -*- coding: utf-8 -*
"""Unpythonic constructs that change the rules.

See dir(unpythonic) and submodule docstrings for more info.
"""

from .assignonce import *
from .dynscope import *
#from .lispy_let import *  # guaranteed evaluation order, clunky syntax
from .pythonic_let import *  # no guarantees on evaluation order, nice syntax
from .misc import *
