# -*- coding: utf-8 -*
"""Supercharge your Python with parts of Lisp and Haskell.

See ``dir(unpythonic)`` and submodule docstrings for more.

If you have MacroPy installed, see also ``unpythonic.syntax``.
"""

__version__ = '0.14.3'

from .amb import *  # noqa: F401, F403
from .arity import *  # noqa: F401, F403
from .assignonce import *  # noqa: F401, F403
from .collections import *  # noqa: F401, F403
from .conditions import *  # noqa: F401, F403
from .dispatch import *  # noqa: F401, F403
from .dynassign import *  # noqa: F401, F403
from .ec import *  # noqa: F401, F403
from .fix import *  # noqa: F401, F403
from .fold import *  # noqa: F401, F403
from .fploop import *  # noqa: F401, F403
from .fun import *  # noqa: F401, F403
from .fup import *  # noqa: F401, F403
from .gmemo import *  # noqa: F401, F403
from .gtco import *  # noqa: F401, F403
from .it import *  # noqa: F401, F403
from .let import *  # no guarantees on evaluation order (before Python 3.6), nice syntax # noqa: F401, F403

# guaranteed evaluation order, clunky syntax
from .lispylet import (let as ordered_let, letrec as ordered_letrec,  # noqa: F401
                       dlet as ordered_dlet, dletrec as ordered_dletrec,
                       blet as ordered_blet, bletrec as ordered_bletrec)

from .llist import *  # noqa: F401, F403
from .mathseq import *  # noqa: F401, F403
from .misc import *  # noqa: F401, F403
from .seq import *  # noqa: F401, F403
from .singleton import *  # noqa: F401, F403
from .slicing import *  # noqa: F401, F403
from .symbol import *  # noqa: F401, F403
from .tco import *  # noqa: F401, F403
from .typecheck import *  # noqa: F401, F403

# HACK: break dependency loop
from .lazyutil import _init_module
_init_module()
del _init_module
