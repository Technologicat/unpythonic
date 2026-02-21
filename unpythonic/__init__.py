# -*- coding: utf-8 -*
"""Supercharge your Python with parts of Lisp and Haskell.

See ``dir(unpythonic)`` and submodule docstrings for more.

If you have ``mcpyrate`` installed, see also ``unpythonic.syntax``
for a trip down the rabbit hole.
"""

__version__ = '1.0.0'

from .amb import *  # noqa: F401, F403
from .arity import *  # noqa: F401, F403
from .assignonce import *  # noqa: F401, F403
from .collections import *  # noqa: F401, F403
from .conditions import *  # noqa: F401, F403
from .dispatch import *  # noqa: F401, F403
from .dynassign import *  # noqa: F401, F403
from .ec import *  # noqa: F401, F403
from .excutil import *  # noqa: F401, F403
from .fix import *  # noqa: F401, F403
from .fold import *  # noqa: F401, F403
from .fploop import *  # noqa: F401, F403
from .fun import *  # noqa: F401, F403
from .fup import *  # noqa: F401, F403
from .gmemo import *  # noqa: F401, F403
from .gtco import *  # noqa: F401, F403
from .it import *  # noqa: F401, F403
from .let import *  # # noqa: F401, F403

# As of 0.15.0, lispylet is nowadays primarily a code generation target API for macros.
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
from .timeutil import *  # noqa: F401, F403
from .typecheck import *  # noqa: F401, F403

# --------------------------------------------------------------------------------
# HACK: break dependency loops for circular imports

from .lazyutil import _init_module
_init_module()
del _init_module
# We're slightly selective here, because user code likely doesn't need `islazy`, `passthrough_lazy_args`,
# or `maybe_force_args`, although strictly speaking those functions are part of the public API.
from .lazyutil import Lazy, force1, force  # noqa: F401

from .funutil import _init_module
_init_module()
del _init_module
from .funutil import *  # noqa: F401, F403

from .numutil import _init_module
_init_module()
del _init_module
from .numutil import *  # noqa: F401, F403
