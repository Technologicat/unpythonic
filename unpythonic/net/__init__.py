# -*- coding: utf-8; -*-
"""Networking and REPL-related utilities.

Symbols recommended for library use are imported directly to this namespace.

The hot-patching REPL implementation is contained in the submodules `server`,
`client` and `common`; if you need any of that, feel free to import it
directly (and consult the corresponding docstrings).
"""

from .msg import *
from .ptyproxy import *
from .util import *
