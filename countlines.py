#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Estimate project size in lines of code."""

# TODO: add sorting options: name, code count, SLOC count, code ratio.

import os
import re
from operator import itemgetter

def listpy(path):
    return list(sorted(filename for filename in os.listdir(path) if filename.endswith(".py")))

def count_sloc(code, *, blanks, docstrings, comments):
    """blanks et al.: include this item?"""
    if not docstrings:
        # TODO: make sure it's a docstring (and not some other """...""" string)
        code = re.sub(r'""".*?"""', r'', code, flags=(re.MULTILINE + re.DOTALL))
        code = re.sub(r"'''.*?'''", r'', code, flags=(re.MULTILINE + re.DOTALL))
    lines = code.split("\n")
    if not blanks:
        lines = [line for line in lines if line.strip()]
    if not comments:
        lines = [line for line in lines if not line.strip().startswith("#")]  # ignore whole-line comments
    return len(lines)

def report(paths):
    print(f"Code size for {os.getcwd()}")
    def format_name(s, width=25):
        return s.ljust(width)
    def format_number(n, width=5):
        return str(n).rjust(width)
    def format_path(s):  # ./subdir/something
        def label(s):
            if s == ".":
                return "top level"
            return s[2:]
        return format_name(label(s))
    codes_grandtotal = 0
    slocs_grandtotal = 0
    for path in paths:
        filenames = listpy(path)
        results = []
        for filename in filenames:
            with open(os.path.join(path, filename), "rt", encoding="utf-8") as f:
                content = f.read()
            code = count_sloc(content, blanks=False, docstrings=False, comments=False)
            sloc = count_sloc(content, blanks=True, docstrings=True, comments=True)
            results.append((code, sloc))

        if results:
            codes, slocs = zip(*results)
            codes = sum(codes)
            slocs = sum(slocs)
            print(f"\n  {format_path(path)}   {format_number(codes)} / {format_number(slocs)}  {int(codes / slocs * 100):d}% code")
            for filename, (code, sloc) in sorted(zip(filenames, results), key=itemgetter(1)):
                print(f"    {format_name(filename)} {format_number(code)} / {format_number(sloc)}  {int(code / sloc * 100):d}% code")
            codes_grandtotal += codes
            slocs_grandtotal += slocs
    print(f"\n{format_name('Total')}     {format_number(codes_grandtotal)} / {format_number(slocs_grandtotal)}  {int(codes_grandtotal / slocs_grandtotal * 100):d}% code")

def main():
    blacklist = [".git", "build", "dist", "__pycache__", "00_stuff"]
    paths = []
    for root, dirs, files in os.walk("."):
        paths.append(root)
        for x in blacklist:
            if x in dirs:
                dirs.remove(x)
    report(sorted(paths))

if __name__ == '__main__':
    main()
