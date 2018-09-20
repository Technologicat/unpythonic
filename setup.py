# -*- coding: utf-8 -*-
#
"""setuptools-based setup.py for unpythonic.

Tested on Python 3.4.

Usage as usual with setuptools:
    python3 setup.py build
    python3 setup.py sdist
    python3 setup.py bdist_wheel --universal
    python3 setup.py install

For details, see
    http://setuptools.readthedocs.io/en/latest/setuptools.html#command-reference
or
    python3 setup.py --help
    python3 setup.py --help-commands
    python3 setup.py --help bdist_wheel  # or any command
"""

#########################################################
# General config
#########################################################

# Name of the top-level package of your library.
#
# This is also the top level of its source tree, relative to the top-level project directory setup.py resides in.
#
libname="unpythonic"

# Short description for package list on PyPI
#
SHORTDESC="Lispy (and some haskelly) missing batteries for Python."

# Long description for package homepage on PyPI
#
DESC="""Python clearly wants to be an impure-FP language. A decorator with arguments
is a curried closure - how much more FP can you get?

We provide some missing features for Python from the list processing tradition,
plus a few bonus haskellisms.

We place a special emphasis on clear, pythonic syntax, as far as possible without MacroPy.

Other design considerations are simplicity, robustness, and minimal dependencies (currently none).

Tail call optimization (TCO), TCO'd loops in FP style, call/ec, let & letrec,
assign-once, multi-expression lambdas, def as a code block, dynamic assignment,
memoize (also for generators and iterables), compose, folds and scans
(left and right), unfold, lazy partial unpacking of iterables,
functional sequence updates, pythonic lispy linked lists.

We also provide a curry that passes extra arguments through on the right,
and calls a callable return value on the remaining arguments. This is now
valid Python:

    mymap = lambda f: curry(foldr, composerc(cons, f), nil)
    myadd = lambda a, b: a + b
    assert curry(mymap, myadd, ll(1, 2, 3), ll(2, 4, 6)) == ll(3, 6, 9)

For documentation and examples, see the project's GitHub homepage.
"""

# Set up data files for packaging.
#
# Directories (relative to the top-level directory where setup.py resides) in which to look for data files.
datadirs  = ()

# File extensions to be considered as data files. (Literal, no wildcards.)
dataexts  = (".py", ".ipynb",  ".sh",  ".lyx", ".tex", ".txt", ".pdf")

# Standard documentation to detect (and package if it exists).
#
standard_docs     = ["README", "LICENSE", "TODO", "CHANGELOG", "AUTHORS"]  # just the basename without file extension
standard_doc_exts = [".md", ".rst", ".txt", ""]  # commonly .md for GitHub projects, but other projects may use .rst or .txt (or even blank).

#########################################################
# Init
#########################################################

import os
from setuptools import setup

# Gather user-defined data files
#
# http://stackoverflow.com/questions/13628979/setuptools-how-to-make-package-contain-extra-data-folder-and-all-folders-inside
#
datafiles = []
#getext = lambda filename: os.path.splitext(filename)[1]
#for datadir in datadirs:
#    datafiles.extend( [(root, [os.path.join(root, f) for f in files if getext(f) in dataexts])
#                       for root, dirs, files in os.walk(datadir)] )

# Add standard documentation (README et al.), if any, to data files
#
detected_docs = []
for docname in standard_docs:
    for ext in standard_doc_exts:
        filename = "".join( (docname, ext) )  # relative to the directory in which setup.py resides
        if os.path.isfile(filename):
            detected_docs.append(filename)
datafiles.append( ('.', detected_docs) )

# Extract __version__ from the package __init__.py
# (since it's not a good idea to actually run __init__.py during the build process).
#
# http://stackoverflow.com/questions/2058802/how-can-i-get-the-version-defined-in-setup-py-setuptools-in-my-package
#
import ast
init_py_path = os.path.join(libname, '__init__.py')
version = '0.0.unknown'
try:
    with open(init_py_path) as f:
        for line in f:
            if line.startswith('__version__'):
                version = ast.parse(line).body[0].value.s
                break
        else:
            print( "WARNING: Version information not found in '%s', using placeholder '%s'" % (init_py_path, version), file=sys.stderr )
except FileNotFoundError:
    print( "WARNING: Could not find file '%s', using placeholder version information '%s'" % (init_py_path, version), file=sys.stderr )

#########################################################
# Call setup()
#########################################################

setup(
    name = "unpythonic",
    version = version,
    author = "Juha Jeronen",
    author_email = "juha.jeronen@tut.fi",
    url = "https://github.com/Technologicat/unpythonic",

    description = SHORTDESC,
    long_description = DESC,

    license = "BSD",

    # free-form text field; http://stackoverflow.com/questions/34994130/what-platforms-argument-to-setup-in-setup-py-does
    platforms = ["Linux"],

    # See
    #    https://pypi.python.org/pypi?%3Aaction=list_classifiers
    #
    # for the standard classifiers.
    #
    classifiers = [ "Development Status :: 4 - Beta",
                    "Environment :: Console",
                    "Intended Audience :: Developers",
                    "License :: OSI Approved :: BSD License",
                    "Operating System :: POSIX :: Linux",
                    "Programming Language :: Python",
                    "Programming Language :: Python :: 3",
                    "Programming Language :: Python :: 3.4",
                    "Topic :: Software Development :: Libraries",
                    "Topic :: Software Development :: Libraries :: Python Modules"
                  ],

    # See
    #    http://setuptools.readthedocs.io/en/latest/setuptools.html
    #
    setup_requires = [],
    install_requires = [],
    provides = ["unpythonic"],

    # keywords for PyPI (in case you upload your project)
    #
    # e.g. the keywords your project uses as topics on GitHub, minus "python" (if there)
    #
    keywords = ["functional-programming", "lisp"],

    # Declare packages so that  python -m setup build  will copy .py files (especially __init__.py).
    #
    # This **does not** automatically recurse into subpackages, so they must also be declared.
    #
    packages = ["unpythonic"],

    zip_safe = True,  # no Cython extensions

    # Custom data files not inside a Python package
    data_files = datafiles
)

