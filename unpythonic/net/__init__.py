# -*- coding: utf-8; -*-
"""Networking and REPL-related utilities.

From the submodules, symbols most likely useful for developing applications
or higher-level libraries are imported directly into this namespace.

The hot-patching REPL implementation is contained in the submodules `server`,
`client` and `common`; if you need any of that, feel free to import it
directly (and consult the corresponding docstrings).
"""

from .msg import *
from .ptyproxy import *
from .util import *
