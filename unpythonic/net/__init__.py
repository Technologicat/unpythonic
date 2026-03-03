# -*- coding: utf-8; -*-
"""Networking and REPL-related utilities.

From the submodules, symbols most likely useful for developing applications
or higher-level libraries are imported directly into this namespace.

The hot-patching REPL implementation is contained in the submodules `server`,
`client` and `common`; if you need any of that, feel free to import it
directly (and consult the corresponding docstrings).
"""

from .msg import *
try:
    from .ptyproxy import *
except ModuleNotFoundError:
    import logging
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)
    logger.info("`unpythonic.net.ptyproxy` could not be loaded, the REPL server will not be available. Usually this is harmless; most applications do not need the REPL server.")
    PTYSocketProxy = None
from .util import *
