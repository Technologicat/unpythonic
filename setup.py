# -*- coding: utf-8 -*-
#
"""setuptools-based setup.py for unpythonic.

Tested on Python 3.8.

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

import ast
import os

from setuptools import setup  # type: ignore[import]


def read(*relpath, **kwargs):  # https://blog.ionelmc.ro/2014/05/25/python-packaging/#the-setup-script
    with open(os.path.join(os.path.dirname(__file__), *relpath),
              encoding=kwargs.get('encoding', 'utf8')) as fh:
        return fh.read()

# Extract __version__ from the package __init__.py
# (since it's not a good idea to actually run __init__.py during the build process).
#
# http://stackoverflow.com/questions/2058802/how-can-i-get-the-version-defined-in-setup-py-setuptools-in-my-package
#
init_py_path = os.path.join("unpythonic", "__init__.py")
version = None
try:
    with open(init_py_path) as f:
        for line in f:
            if line.startswith("__version__"):
                module = ast.parse(line, filename=init_py_path)
                expr = module.body[0]
                assert isinstance(expr, ast.Assign)
                v = expr.value
                if type(v) is ast.Constant:  # Python 3.8+
                    # mypy understands `isinstance(..., ...)` but not `type(...) is ...`,
                    # and we want to match on the exact type, not any subclass that might be
                    # added in some future Python version.
                    assert isinstance(v, ast.Constant)
                    version = v.value
                elif type(v) is ast.Str:
                    assert isinstance(v, ast.Str)  # mypy
                    version = v.s
                break
except FileNotFoundError:
    pass
if not version:
    raise RuntimeError(f"Version information not found in {init_py_path}")

#########################################################
# Call setup()
#########################################################

setup(
    name="unpythonic",
    version=version,
    # `unpythonic.test` is the macro-enabled testing framework, intended for public consumption;
    # the unit tests of `unpythonic` itself in `unpythonic.tests` are NOT deployed.
    packages=["unpythonic", "unpythonic.syntax", "unpythonic.test", "unpythonic.net"],
    provides=["unpythonic"],
    keywords=["functional-programming", "language-extension", "syntactic-macros",
              "tail-call-optimization", "tco", "continuations", "currying", "lazy-evaluation",
              "dynamic-variable", "macros", "lisp", "scheme", "racket", "haskell"],
    install_requires=[],  # mcpyrate is optional for us, so we can't really put it here even though we recommend it.
    python_requires=">=3.8,<3.13",
    author="Juha Jeronen",
    author_email="juha.m.jeronen@gmail.com",
    url="https://github.com/Technologicat/unpythonic",
    description="Supercharge your Python with parts of Lisp and Haskell.",
    long_description=read("README.md"),
    long_description_content_type="text/markdown",
    license="BSD",
    platforms=["Linux"],
    classifiers=["Development Status :: 4 - Beta",
                 "Environment :: Console",
                 "Intended Audience :: Developers",
                 "License :: OSI Approved :: BSD License",
                 "Operating System :: POSIX :: Linux",
                 "Programming Language :: Python",
                 "Programming Language :: Python :: 3",
                 "Programming Language :: Python :: 3.8",
                 "Programming Language :: Python :: 3.9",
                 "Programming Language :: Python :: 3.10",
                 "Programming Language :: Python :: 3.11",
                 "Programming Language :: Python :: 3.12",
                 "Programming Language :: Python :: Implementation :: CPython",
                 "Programming Language :: Python :: Implementation :: PyPy",
                 "Topic :: Software Development :: Libraries",
                 "Topic :: Software Development :: Libraries :: Python Modules"
                 ],
    zip_safe=False  # macros are not zip safe, because the zip importer fails to find sources.
)
