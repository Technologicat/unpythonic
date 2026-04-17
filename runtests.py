# -*- coding: utf-8 -*-
"""Run all tests for ``unpythonic``.

The test framework uses macros, but this top-level script does not. This can be
run under regular ``python3`` (i.e. does not need the ``macropython`` wrapper
from ``mcpyrate``).
"""

import os
import sys

from unpythonic.test.runner import discover_testmodules, run

import mcpyrate.activate  # noqa: F401

def main():
    # All folders containing unit tests are named `tests` (plural).
    #
    # The testing framework is called `unpythonic.test.fixtures`,
    # so it lives in the only subfolder in the project that is named
    # `test` (singular).
    testsets = [("regular code", (discover_testmodules(os.path.join("unpythonic", "tests")) +
                                  discover_testmodules(os.path.join("unpythonic", "net", "tests")) +
                                  discover_testmodules(os.path.join("unpythonic", "monads", "tests")))),
                ("macros", discover_testmodules(os.path.join("unpythonic", "syntax", "tests"))),
                ("dialects", discover_testmodules(os.path.join("unpythonic", "dialects", "tests")))]
    return run(testsets)

if __name__ == '__main__':
    if not main():
        sys.exit(1)  # pragma: no cover, this only runs when the tests fail.
