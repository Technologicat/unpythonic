# -*- coding: utf-8 -*-
"""Conditionally import AST node types only supported by recent enough Python versions (3.7+)."""

from ..symbol import gensym

_NoSuchNodeType = gensym("_NoSuchNodeType")

# no new AST node types in Python 3.7

try:  # Python 3.8+
    from ast import NamedExpr  # a.k.a. walrus operator ":="
except ImportError:  # pragma: no cover
    NamedExpr = _NoSuchNodeType

# TODO: any new AST node types in Python 3.9?
# TODO: any new AST node types in Python 3.10?
