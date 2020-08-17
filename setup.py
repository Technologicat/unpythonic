# -*- coding: utf-8 -*-
#
"""setuptools-based setup.py for unpythonic.

Tested on Python 3.6.

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

# Name of the top-level package of the library.
#
# This is also the top level of its source tree, relative to the top-level project directory setup.py resides in.
#
libname = "unpythonic"

# Short description for package list on PyPI
#
SHORTDESC = "Supercharge your Python with parts of Lisp and Haskell."

#########################################################
# Init
#########################################################

import os
from setuptools import setup

def read(*relpath, **kwargs):  # https://blog.ionelmc.ro/2014/05/25/python-packaging/#the-setup-script
    with open(os.path.join(os.path.dirname(__file__), *relpath),
              encoding=kwargs.get('encoding', 'utf8')) as fh:
        return fh.read()

# TODO: update version detector for Python 3.8 (accept also ast.Constant beside ast.Str)
#
# Extract __version__ from the package __init__.py
# (since it's not a good idea to actually run __init__.py during the build process).
#
# http://stackoverflow.com/questions/2058802/how-can-i-get-the-version-defined-in-setup-py-setuptools-in-my-package
#
import ast
init_py_path = os.path.join(libname, '__init__.py')
version = None
try:
    with open(init_py_path) as f:
        for line in f:
            if line.startswith('__version__'):
                version = ast.parse(line).body[0].value.s
                break
except FileNotFoundError:
    pass
if not version:
    raise RuntimeError("Version information not found in '{}'".format(init_py_path))

#########################################################
# Call setup()
#########################################################

setup(
    name="unpythonic",
    version=version,
    author="Juha Jeronen",
    author_email="juha.m.jeronen@gmail.com",
    url="https://github.com/Technologicat/unpythonic",

    # https://packaging.python.org/guides/making-a-pypi-friendly-readme/
    description=SHORTDESC,
    long_description=read("README.md"),
    long_description_content_type="text/markdown",

    license="BSD",

    # free-form text field; http://stackoverflow.com/questions/34994130/what-platforms-argument-to-setup-in-setup-py-does
    platforms=["Linux"],

    # See
    #    https://pypi.python.org/pypi?%3Aaction=list_classifiers
    #
    # for the standard classifiers.
    #
    classifiers=["Development Status :: 4 - Beta",
                 "Environment :: Console",
                 "Intended Audience :: Developers",
                 "License :: OSI Approved :: BSD License",
                 "Operating System :: POSIX :: Linux",
                 "Programming Language :: Python",
                 "Programming Language :: Python :: 3",
                 "Programming Language :: Python :: 3.4",
                 "Programming Language :: Python :: 3.5",
                 "Programming Language :: Python :: 3.6",
                 "Programming Language :: Python :: 3.7",
                 "Programming Language :: Python :: Implementation :: CPython",
                 "Programming Language :: Python :: Implementation :: PyPy",
                 "Topic :: Software Development :: Libraries",
                 "Topic :: Software Development :: Libraries :: Python Modules"
                 ],

    # See
    #    http://setuptools.readthedocs.io/en/latest/setuptools.html
    #
    python_requires=">=3.4,<3.8",
    install_requires=[],  # MacroPy is optional for us, so we can't really put "macropy3" here even though we recommend it.
    # setup_requires=[],  # TODO: Using setup_requires is discouraged in favor of https://www.python.org/dev/peps/pep-0518/
    # test_requires=["macropy3"],  # TODO: not very useful, because only "python3 setup.py test" installs these, and we don't use that.
    provides=["unpythonic"],

    # keywords for PyPI (in case you upload your project)
    #
    # e.g. the keywords your project uses as topics on GitHub, minus "python" (if there)
    #
    keywords=["functional-programming", "language-extension", "syntactic-macros",
              "tail-call-optimization", "tco", "continuations", "currying", "lazy-evaluation",
              "dynamic-variable", "macros", "lisp", "scheme", "racket", "haskell"],

    # Declare packages so that  python -m setup build  will copy .py files (especially __init__.py).
    #
    # This **does not** automatically recurse into subpackages, so they must also be declared.
    #
    packages=["unpythonic", "unpythonic.syntax"],
    scripts=["macropy3"],

    zip_safe=False  # macros are not zip safe, because the zip importer fails to find sources, and MacroPy needs them.
)
