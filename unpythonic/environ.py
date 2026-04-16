# -*- coding: utf-8 -*-
"""Utilities for working with OS environment variables."""

__all__ = ["override"]

from collections.abc import Iterator
import contextlib
import os
import threading

_lock = threading.RLock()

@contextlib.contextmanager
def override(**bindings: str) -> Iterator[None]:
    """Context manager: temporarily override OS environment variable(s).

    When the ``with`` block exits, the previous state of the environment
    is restored.  If a variable was unset before entry, it is removed
    again on exit.

    Thread-safe: concurrent overrides from different threads are serialised
    by a module-level ``RLock``, so only one set of overrides is active at
    a time.  Same-thread nesting is supported (the lock is reentrant).

    Example::

        import os
        from unpythonic import environ_override
        os.environ["MY_VAR"] = "original"
        with environ_override(MY_VAR="temporary", OTHER="added"):
            print(os.environ["MY_VAR"])   # "temporary"
            print(os.environ["OTHER"])     # "added"
        print(os.environ["MY_VAR"])       # "original"
        print("OTHER" in os.environ)       # False
    """
    with _lock:
        old = {k: os.environ[k] for k in bindings if k in os.environ}
        try:
            os.environ.update(bindings)
            yield
        finally:
            for k in bindings:
                if k in old:
                    os.environ[k] = old[k]
                else:
                    os.environ.pop(k, None)
