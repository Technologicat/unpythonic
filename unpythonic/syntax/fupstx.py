# -*- coding: utf-8 -*-
"""Functionally update sequences - macro wrapper for slice syntax."""

from ast import BinOp, LShift, Subscript, Index, Slice, ExtSlice

from macropy.core.quotes import macros, q, ast_literal
from macropy.core.hquotes import macros, hq

from ..fup import fupdate

# TODO: improve: multiple fupdate specs?
def fup(tree):
    valid = type(tree) is BinOp and type(tree.op) is LShift and type(tree.left) is Subscript
    if not valid:
        assert False, "fup: expected seq[idx_or_slice] << val"
    seq, idx, val = tree.left.value, tree.left.slice, tree.right

    if type(idx) is ExtSlice:
        assert False, "fup: multidimensional indexing not supported"
    elif type(idx) is Slice:
        start, stop, step = [x or q[None] for x in (idx.lower, idx.upper, idx.step)]
        idxspec = hq[slice(ast_literal[start], ast_literal[stop], ast_literal[step])]
    elif type(idx) is Index:
        idxspec = idx.value
        if idxspec is None:
            assert False, "indices must be integers, not NoneType"

    return hq[fupdate(ast_literal[seq], ast_literal[idxspec], ast_literal[val])]
