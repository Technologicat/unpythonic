#!/usr/bin/env python3
# -*- coding: utf-8 -*
"""Unpythonic constructs that change the rules.

See dir(unpythonic) and submodule docstrings for more info.
"""

from .dynscope import *
from .let_lispy import *  # guaranteed evaluation order, clunky syntax
#from .let_pythonic import *  # no guarantees on evaluation order, nice syntax
from .misc import *
from .norebind import *
