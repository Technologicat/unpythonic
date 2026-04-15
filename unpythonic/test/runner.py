# -*- coding: utf-8 -*-
"""Generic test runner for projects using ``unpythonic.test.fixtures``.

Provides test module discovery, version-suffix gating, and a ``run``
function that wraps the standard session/testset/import_module pattern.

Usage from a project's top-level ``runtests.py``::

    import os
    from unpythonic.test.runner import discover_testmodules, run

    import mcpyrate.activate  # noqa: F401

    testsets = [("my tests", discover_testmodules(os.path.join("mypackage", "tests")))]
    if not run(testsets):
        raise SystemExit(1)

Version-suffixed test modules (e.g. ``test_foo_3_11.py``) are automatically
skipped with a warning on older Pythons.
"""

import os
import re
import sys
from importlib import import_module

from .fixtures import session, testset, emit_warning, tests_errored, tests_failed
from ..collections import unbox

__all__ = ["discover_testmodules", "run"]

def discover_testmodules(path, prefix="test_", suffix=".py"):
    """Discover test modules in a directory.

    Returns a sorted list of dotted module names (e.g.
    ``["mypackage.tests.test_foo", "mypackage.tests.test_bar"]``).

    Modules are discovered by filename convention: files matching
    ``{prefix}*{suffix}`` in the given directory.
    """
    filenames = [fn for fn in os.listdir(path) if fn.startswith(prefix) and fn.endswith(suffix)]
    modnames = [_filename_to_modulename(path, fn) for fn in filenames]
    return list(sorted(modnames))

def _filename_to_modulename(path, filename):
    """Convert a path and filename to a dotted module name.

    ``("some/dir", "mod.py")`` → ``"some.dir.mod"``
    """
    # str.replace, not re.sub: on Windows os.path.sep is a lone backslash,
    # which as a regex pattern is an incomplete escape and raises re.error.
    modpath = path.replace(os.path.sep, ".")
    themod = re.sub(r"\.py$", r"", filename)
    return ".".join([modpath, themod])

def _version_suffix(modulename):
    """Parse version suffix from module name.

    E.g. ``"mypackage.tests.test_foo_3_11"`` → ``(3, 11)``, or ``None``.
    """
    m = re.search(r"_(\d+)_(\d+)$", modulename)
    if m:
        return (int(m.group(1)), int(m.group(2)))
    return None

def run(testsets):
    """Run test modules, reporting results through ``unpythonic.test.fixtures``.

    ``testsets``: iterable of ``(name, modulenames)`` pairs, where ``name``
    is a human-readable label and ``modulenames`` is a list of dotted module
    names. Each module must export a ``runtests()`` function.

    Version-suffixed modules (e.g. ``test_foo_3_11``) are automatically
    skipped with a warning on Pythons older than the indicated version.

    Returns ``True`` if all tests passed (no failures or errors).
    """
    with session():
        for tsname, modnames in testsets:
            with testset(tsname):
                for m in modnames:
                    with testset(m):
                        ver = _version_suffix(m)
                        if ver is not None and sys.version_info < ver:
                            msg = (f"Skipping '{m}' (requires Python {ver[0]}.{ver[1]}+, "
                                   f"running {sys.version_info.major}.{sys.version_info.minor})")
                            emit_warning(msg)
                            continue
                        mod = import_module(m)
                        mod.runtests()
    return (unbox(tests_failed) + unbox(tests_errored)) == 0
