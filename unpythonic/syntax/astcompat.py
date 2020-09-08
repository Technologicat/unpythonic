# -*- coding: utf-8 -*-
"""Conditionally import AST node types only supported by Python 3.5+ or 3.6+."""

from ..symbol import gensym

_NoSuchNodeType = gensym("_NoSuchNodeType")

try:  # Python 3.5+
    from ast import AsyncFor, AsyncFunctionDef, AsyncWith, Await, MatMult
except ImportError:  # pragma: no cover
    AsyncFor = AsyncFunctionDef = AsyncWith = Await = MatMult = _NoSuchNodeType

try:  # Python 3.6+
    from ast import AnnAssign, FormattedValue, JoinedStr
except ImportError:  # pragma: no cover
    AnnAssign = FormattedValue = JoinedStr = _NoSuchNodeType

# TODO: Python 3.8 support: Constant (replaces many node types!), NamedExpr (a.k.a. walrus operator ":=")
