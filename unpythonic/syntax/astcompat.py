# -*- coding: utf-8 -*-
"""Conditionally import AST node types only supported by Python 3.5+ or 3.6+."""

from ..symbol import gensym

_NoSuchNodeType = gensym("_NoSuchNodeType")

try:  # Python 3.5+
    from ast import AsyncFor, AsyncFunctionDef, AsyncWith, Await, MatMult
except ImportError:
    AsyncFor = AsyncFunctionDef = AsyncWith = Await = MatMult = _NoSuchNodeType

try:  # Python 3.6+
    from ast import AnnAssign, FormattedValue, JoinedStr
except ImportError:
    AnnAssign = FormattedValue = JoinedStr = _NoSuchNodeType
