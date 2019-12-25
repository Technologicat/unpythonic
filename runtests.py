#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import re
import subprocess

# https://en.wikipedia.org/wiki/ANSI_escape_code#SGR_(Select_Graphic_Rendition)_parameters
# https://stackoverflow.com/questions/287871/print-in-terminal-with-colors
CHEAD = "\033[32m"  # dark green
CPASS = "\033[92m"  # light green
CFAIL = "\033[91m"  # light red
CEND = "\033[39m"   # reset FG color to default

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

def runtests(testsetname, modules, command_prefix):
    print(CHEAD + "*** Testing {} ***".format(testsetname) + CEND)
    fails = 0
    for mod in modules:
        print(CHEAD + "*** Running {} ***".format(mod) + CEND)
        # TODO: migrate to subprocess.run (Python 3.5+)
        ret = subprocess.call(command_prefix + [mod])
        if ret == 0:
            print(CPASS + "*** PASS ***" + CEND)
        else:
            fails += 1
            print(CFAIL + "*** FAIL ***" + CEND)
    if not fails:
        print(CPASS + "*** ALL OK in {} ***".format(testsetname) + CEND)
    else:
        print(CFAIL + "*** AT LEAST ONE FAIL in {} ***".format(testsetname))
    return fails

def main():
    totalfails = 0
    totalfails += runtests("regular code",
                           (listtestmodules(os.path.join("unpythonic", "test")) +
                            listtestmodules(os.path.join("unpythonic", "net", "test"))),
                           ["python3", "-m"])

    try:
        import macropy.activate  # noqa: F401
    except ImportError:
        print(CHEAD + "*** Could not initialize MacroPy, skipping macro tests. ***" + CEND)
    else:
        totalfails += runtests("macros",
                               listtestmodules(os.path.join("unpythonic", "syntax", "test")),
                               ["macropy3", "-m"])

    if not totalfails:
        print(CPASS + "*** ALL OK ***" + CEND)
    else:
        print(CFAIL + "*** AT LEAST ONE FAIL ***" + CEND)

if __name__ == '__main__':
    main()
