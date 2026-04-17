# -*- coding: utf-8 -*-
"""Monads for unpythonic.

Seven monads plus the two base classes:

- ``Monad``, ``LiftableMonad`` — the base classes
- ``Identity`` — pedagogical no-op
- ``Maybe`` — simple short-circuiting on "nothing"
- ``Either``, ``Left``, ``Right`` — short-circuiting with a carried error
- ``List`` — non-deterministic / multivalued computation
- ``Writer`` — pure-functional audit log
- ``State`` — threading a state value through a pure chain
- ``Reader`` — reading from a shared immutable environment

plus:

- ``liftm``, ``liftm2``, ``liftm3`` — lift regular functions into monadic ones

The subpackage is **not** re-exported at the top level of ``unpythonic`` —
import directly as ``from unpythonic.monads import Maybe``, etc. This matches
the pattern of ``from unpythonic.env import env``.

For do-notation syntax over any of these monads, see the macro
``from unpythonic.syntax import monadic_do``.
"""

from .abc import *  # noqa: F401, F403
from .core import *  # noqa: F401, F403

from .identity import *  # noqa: F401, F403
from .maybe import *  # noqa: F401, F403
from .either import *  # noqa: F401, F403
from .list import *  # noqa: F401, F403
from .writer import *  # noqa: F401, F403
from .state import *  # noqa: F401, F403
from .reader import *  # noqa: F401, F403
