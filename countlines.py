#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Estimate project size in lines of code.

Ignores blank lines, docstrings, and whole-line comments."""

import os
import re
from operator import itemgetter

def listpy(path):
    return list(sorted(fn for fn in os.listdir(path) if fn.endswith(".py")))

def loc(code, blanks=False, docstrings=False, comments=False):
    if not docstrings:
        # TODO: make sure it's a docstring (and not some other """...""" string)
        code = re.sub(r'""".*?"""', r'', code, flags=(re.MULTILINE + re.DOTALL))
    lines = code.split("\n")
    if not blanks:
        lines = [line for line in lines if line.strip()]
    if not comments:
        # TODO: removes only whole-line comments.
        lines = [line for line in lines if not line.strip().startswith("#")]
    return len(lines)

def main():
    items = (("top level", ["."]),
             ("regular code", ["unpythonic"]),
             ("regular code tests", ["unpythonic", "test"]),
             ("macros", ["unpythonic", "syntax"]),
             ("macro tests", ["unpythonic", "syntax", "test"]))
    grandtotal = 0
    for name, p in items:
        path = os.path.join(*p)
        files = listpy(path)
        ns = []
        for fn in files:
            with open(os.path.join(path, fn), "rt", encoding="utf-8") as f:
                content = f.read()
            ns.append(loc(content))
        # report
        print("{}:".format(name))
        for fn, n in sorted(zip(files, ns), key=itemgetter(1)):
            print("    {} {}".format(fn, n))
        grouptotal = sum(ns)
        print("  total for {} {}".format(name, grouptotal))
        grandtotal += grouptotal
    print("grand total {}".format(grandtotal))

if __name__ == '__main__':
    main()
