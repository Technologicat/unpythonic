# -*- coding: utf-8 -*-
"""Conditionally import AST node types only supported by recent enough Python versions (3.7+)."""

__all__ = ["NamedExpr",
           "Num", "Str", "Bytes", "NameConstant", "Ellipsis",
           "Index", "ExtSlice",
           "getconstant"]

import ast

from ..symbol import gensym

_NoSuchNodeType = gensym("_NoSuchNodeType")

# --------------------------------------------------------------------------------
# New AST node types

# Minimum language version supported by this module is Python 3.6.

# No new AST node types in Python 3.7.

try:  # Python 3.8+
    from ast import NamedExpr  # a.k.a. walrus operator ":="
except ImportError:  # pragma: no cover
    NamedExpr = _NoSuchNodeType

# No new AST node types in Python 3.9.

# TODO: any new AST node types in Python 3.10? (release expected in October 2021)

# --------------------------------------------------------------------------------
# Deprecated AST node types

try:  # Python 3.8+, https://docs.python.org/3/whatsnew/3.8.html#deprecated
    from ast import Num, Str, Bytes, NameConstant, Ellipsis
except ImportError:  # pragma: no cover
    Num = Str = Bytes = NameConstant = Ellipsis = _NoSuchNodeType

try:  # Python 3.9+, https://docs.python.org/3/whatsnew/3.9.html#deprecated
    from ast import Index, ExtSlice
    # We ignore the internal classes Suite, Param, AugLoad, AugStore,
    # which were never used in Python 3.x.
except ImportError:  # pragma: no cover
    Index = ExtSlice = _NoSuchNodeType

# --------------------------------------------------------------------------------
# Compatibility functions

def getconstant(tree):
    """Given an AST node `tree` representing a constant, return the contained raw value.

    This encapsulates the AST differences between Python 3.8+ and older versions.

    There are no `setconstant` or `makeconstant` counterparts, because you can
    just create an `ast.Constant` in Python 3.6 and later. The parser doesn't
    emit them until Python 3.8, but Python 3.6+ compile `ast.Constant` just fine.
    """
    if type(tree) is ast.Constant:  # Python 3.8+
        return tree.value
    # up to Python 3.7
    elif type(tree) is ast.NameConstant:  # up to Python 3.7
        return tree.value
    elif type(tree) is ast.Num:
        return tree.n
    elif type(tree) in (ast.Str, ast.Bytes):
        return tree.s
    elif type(tree) is ast.Ellipsis:  # `ast.Ellipsis` is the AST node type, `builtins.Ellipsis` is `...`.
        return ...
    raise TypeError(f"Not an AST node representing a constant: {type(tree)} with value {repr(tree)}")
