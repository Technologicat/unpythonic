# -*- coding: utf-8 -*-
"""Run all tests for `unpythonic`.

The test framework uses macros, but this top-level script does not. This can be
run under regular `python3` (i.e. does not need the `macropython` wrapper from
`mcpyrate`).
"""

import os
import re
import sys
from importlib import import_module

from unpythonic.test.fixtures import session, testset, tests_errored, tests_failed
from unpythonic.collections import unbox

import mcpyrate.activate  # noqa: F401

def listtestmodules(path):
    testfiles = listtestfiles(path)
    testmodules = [modname(path, fn) for fn in testfiles]
    return list(sorted(testmodules))

def listtestfiles(path, prefix="test_", suffix=".py"):
    return [fn for fn in os.listdir(path) if fn.startswith(prefix) and fn.endswith(suffix)]

def modname(path, filename):  # some/dir/mod.py --> some.dir.mod
    modpath = re.sub(os.path.sep, r".", path)
    themod = re.sub(r"\.py$", r"", filename)
    return ".".join([modpath, themod])

def main():
    with session():
        testsets = (("regular code", (listtestmodules(os.path.join("unpythonic", "test")) +
                                      listtestmodules(os.path.join("unpythonic", "net", "test")))),
                    ("macros", listtestmodules(os.path.join("unpythonic", "syntax", "test"))))
        for tsname, modnames in testsets:
            with testset(tsname):
                for m in modnames:
                    # Wrap each module in its own testset to protect the umbrella testset
                    # against ImportError as well as any failures at macro expansion time.
                    with testset(m):
                        # TODO: We're not inside a package, so we currently can't use a relative import.
                        # TODO: So we just hope this resolves to the local `unpythonic` source code,
                        # TODO: not to an installed copy of the library.
                        mod = import_module(m)
                        mod.runtests()
    all_passed = (unbox(tests_failed) + unbox(tests_errored)) == 0
    return all_passed

if __name__ == '__main__':
    if not main():
        sys.exit(1)  # pragma: no cover, this only runs when the tests fail.
