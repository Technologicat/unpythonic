# -*- coding: utf-8 -*-
"""Dialects: Python the way you want it.

These dialects, i.e. whole-module syntax transformations, are powered by
`mcpyrate`'s dialect subsystem. The user manual is at:
    https://github.com/Technologicat/mcpyrate/blob/master/doc/dialects.md

We provide these dialects mainly to demonstrate how to use that subsystem
to customize Python beyond what a local macro expander can do.

For examples of how to use these particular dialects, see the unit tests.
"""

# re-exports
from .lispython import *  # noqa: F401, F403
from .listhell import *  # noqa: F401, F403
from .pytkell import *  # noqa: F401, F403
