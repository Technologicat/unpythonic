# -*- coding: utf-8 -*-
"""Utilities for working with identifiers in macros."""

import re

from ast import Name, Attribute

from macropy.core import Captured

def isx(tree, x, accept_attr=True):
    """Test whether tree is a reference to the name ``x`` (str).

    Alternatively, ``x`` may be a predicate that accepts a ``str``
    and returns whether it matches, to support more complex matching
    (e.g. ``lambda s: s.startswith("foo")``).

    Both bare names and attributes can be recognized, to support
    both from-imports and regular imports of ``somemodule.x``.

    We support:

        - bare name ``x``

        - ``x`` inside a ``macropy.core.Captured`` node, which may be inserted
          during macro expansion

        - ``x`` as an attribute (if ``accept_attr=True``)
    """
    # WTF, so sometimes there **is** a Captured node, while sometimes there isn't (letdoutil.islet)? At which point are these removed?
    # Captured nodes only come from unpythonic.syntax, and we use from-imports
    # and bare names for anything hq[]'d; but any references that appear
    # explicitly in the user code may use either bare names or somemodule.f.
    ismatch = x if callable(x) else lambda s: s == x
    return ((type(tree) is Name and ismatch(tree.id)) or
            (type(tree) is Captured and ismatch(tree.name)) or
            (accept_attr and type(tree) is Attribute and ismatch(tree.attr)))

def make_isxpred(x):
    """Make a predicate for isx.

    Here ``x`` is an ``str``; the resulting function will match the names
    x, x1, x2, ..., so that it works also with captured identifiers renamed
    by MacroPy's ``hq[]``.
    """
    rematch = re.match
    pat = re.compile(r"^{}\d*$".format(x))
    return lambda s: rematch(pat, s)

def getname(tree, accept_attr=True):
    """The cousin of ``isx``.

    From the same types of trees, extract the name as str.

    If no match on ``tree``, return ``None``.
    """
    if type(tree) is Name:
        return tree.id
    if type(tree) is Captured:
        return tree.name
    if accept_attr and type(tree) is Attribute:
        return tree.attr
    return None
