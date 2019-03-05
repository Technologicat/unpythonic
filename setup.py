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

# Name of the top-level package of the library.
#
# This is also the top level of its source tree, relative to the top-level project directory setup.py resides in.
#
libname="unpythonic"

# Short description for package list on PyPI
#
SHORTDESC="Supercharge your Python with parts of Lisp and Haskell."

# Long description for package homepage on PyPI
#
DESC="""We provide missing features for Python, mainly from the list processing
tradition, but with some haskellisms mixed in. We place a special emphasis on
**clear, pythonic syntax**.

Optionally, we also provide extensions to the Python language as a set of
syntactic macros that are designed to work together. Each macro adds an
orthogonal piece of functionality that can (mostly) be mixed and matched
with the others.

Design considerations are simplicity, robustness, and minimal dependencies.
Currently none required; MacroPy optional, to enable the syntactic macros.

**Without macros**, our features include tail call optimization (TCO), TCO'd
loops in FP style, call/ec, let & letrec, assign-once, multi-expression lambdas,
dynamic assignment (a.k.a. *parameterize*, *special variables*), memoization
(also for generators and iterables), currying, function composition,
folds and scans (left and right), unfold, lazy partial unpacking of iterables,
functional update for sequences, pythonic lispy linked lists (``cons``), and
compact syntax for creating mathematical sequences that support infix math.

Our curry modifies Python's reduction rules. It passes any extra arguments
through on the right, and calls a callable return value on the remaining
arguments, so that we can::

    mymap = lambda f: curry(foldr, composerc(cons, f), nil)
    myadd = lambda a, b: a + b
    assert curry(mymap, myadd, ll(1, 2, 3), ll(2, 4, 6)) == ll(3, 6, 9)

    with_n = lambda *args: (partial(f, n) for n, f in args)
    clip = lambda n1, n2: composel(*with_n((n1, drop), (n2, take)))
    assert tuple(curry(clip, 5, 10, range(20))) == tuple(range(5, 15))

If MacroPy is installed, ``unpythonic.syntax`` becomes available. It provides
macros that essentially extend the Python language, adding features that would
be either complicated or impossible to provide (and/or use) otherwise.

**With macros**, we add automatic currying, automatic tail-call optimization
(TCO), call-by-need (lazy functions), continuations (``call/cc`` for Python),
``let-syntax`` (splice code at macro expansion time), lexically scoped
``let`` and ``do`` with lean syntax, implicit return statements, and
easy-to-use multi-expression lambdas with local variables.

The TCO macro has a fairly extensive expression analyzer, so things like
``and``, ``or``, ``a if p else b`` and any uses of the ``do[]`` and ``let[]``
macros are accounted for when performing the tail-call transformation.

The continuation system is based on a semi-automated partial conversion into
continuation-passing style (CPS), with continuations represented as closures.
It also automatically applies TCO, using the same machinery as the TCO macro.
To keep the runtime overhead somewhat reasonable, the continuation is captured
only where explicitly requested with ``call_cc[]``.

Macro examples::

    # let, letseq (let*), letrec with no boilerplate
    a = let((x, 17),
            (y, 23))[
              (x, y)]

    # alternate haskelly syntax
    a = let[((x, 21),(y, 17), (z, 4)) in x + y + z]
    a = let[x + y + z, where((x, 21), (y, 17), (z, 4))]

    # cond: multi-branch "if" expression
    answer = lambda x: cond[x == 2, "two",
                            x == 3, "three",
                            "something else"]
    assert answer(42) == "something else"

    # do: imperative code in any expression position
    y = do[local[x << 17],
           print(x),
           x << 23,
           x]
    assert y == 23

    # autocurry like Haskell
    with curry:
        def add3(a, b, c):
            return a + b + c
        assert add3(1)(2)(3) == 6
        # actually partial application so these work, too
        assert add3(1, 2)(3) == 6
        assert add3(1)(2, 3) == 6
        assert add3(1, 2, 3) == 6

        mymap = lambda f: foldr(composerc(cons, f), nil)
        myadd = lambda a, b: a + b
        assert mymap(myadd, ll(1, 2, 3), ll(2, 4, 6)) == ll(3, 6, 9)

    # lazy functions (call-by-need) like Haskell
    with lazify:
        def f(a, b):
            return a
        def g(a, b):
            return f(2*a, 3*b)
        assert g(21, 1/0) == 42  # the 1/0 is never evaluated

    # automatic tail-call optimization (TCO) like Scheme, Racket
    with tco:
        assert letrec((evenp, lambda x: (x == 0) or oddp(x - 1)),
                      (oddp,  lambda x: (x != 0) and evenp(x - 1)))[
                        evenp(10000)] is True

    # lambdas with multiple expressions, local variables, and a name
    with multilambda, namedlambda:
        myadd = lambda x, y: [print("myadding", x, y),
                              local[tmp << x + y],
                              print("result is", tmp),
                              tmp]
        assert myadd(2, 3) == 5
        assert myadd.__name__ == "myadd"

    # implicit "return" in tail position, like Lisps
    with autoreturn:
        def f():
            print("hi")
            "I'll just return this"
        assert f() == "I'll just return this"

        def g(x):
            if x == 1:
                "one"
            elif x == 2:
                "two"
            else:
                "something else"
        assert g(1) == "one"
        assert g(2) == "two"
        assert g(42) == "something else"

    # splice code at macro expansion time
    with let_syntax:
        with block(a) as twice:
            a
            a
        with block(x, y, z) as appendxyz:
            lst += [x, y, z]
        lst = []
        twice(appendxyz(7, 8, 9))
        assert lst == [7, 8, 9]*2

    # lispy prefix syntax for function calls
    with prefix:
        (print, "hello world")

    # the LisThEll programming language
    with prefix, curry:
        mymap = lambda f: (foldr, (compose, cons, f), nil)
        double = lambda x: 2 * x
        (print, (mymap, double, (q, 1, 2, 3)))
        assert (mymap, double, (q, 1, 2, 3)) == ll(2, 4, 6)

    # the HasThon programming language
    with curry, lazify:
        def add2first(a, b, c):
            return a + b
        assert add2first(2)(3)(1/0) == 5

        assert letrec[((c, 42),
                       (d, 1/0),
                       (e, 2*c)) in
                      add2first(c)(e)(d)] == 126

    # call/cc for Python
    with continuations:
        stack = []
        def amb(lst, cc):  # McCarthy's amb operator
            if not lst:
                return fail()
            first, *rest = tuple(lst)
            if rest:
                ourcc = cc
                stack.append(lambda: amb(rest, cc=ourcc))
            return first
        def fail():
            if stack:
                f = stack.pop()
                return f()

        def pythagorean_triples(maxn):
            z = call_cc[amb(range(1, maxn+1))]
            y = call_cc[amb(range(1, z+1))]
            x = call_cc[amb(range(1, y+1))]
            if x*x + y*y != z*z:
                return fail()
            return x, y, z
        x = pythagorean_triples(20)
        while x:
            print(x)
            x = fail()

    # if Python didn't already have generators, we could add them with call/cc:
    with continuations:
        @dlet((k, None))  # let-over-def decorator
        def g():
            if k:
                return k()
            def my_yield(value, cc):
                k << cc        # rebind the k in the @dlet env
                cc = identity  # override current continuation
                return value
            # generator body
            call_cc[my_yield(1)]
            call_cc[my_yield(2)]
            call_cc[my_yield(3)]
        out = []
        x = g()
        while x is not None:
            out.append(x)
            x = g()
        assert out == [1, 2, 3]

For documentation and full examples, see the project's GitHub homepage,
and the docstrings of the individual features. For even more examples,
see the unit tests included in the source distribution.
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
    keywords = ["functional-programming", "language-extension", "syntactic-macros",
                "tail-call-optimization", "tco", "continuations", "currying", "lazy-evaluation",
                "dynamic-variable", "macros", "lisp", "scheme", "racket", "haskell"],

    # Declare packages so that  python -m setup build  will copy .py files (especially __init__.py).
    #
    # This **does not** automatically recurse into subpackages, so they must also be declared.
    #
    packages = ["unpythonic", "unpythonic.syntax"],

    zip_safe = False,  # macros are not zip safe, because the zip importer fails to find sources, and MacroPy needs them.

    # Custom data files not inside a Python package
    data_files = datafiles
)

