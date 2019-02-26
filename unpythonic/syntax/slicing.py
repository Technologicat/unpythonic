# -*- coding: utf-8 -*-
"""Functionally update sequences - macro wrapper for slice syntax."""

from ast import BinOp, LShift, Subscript, Index, Slice, ExtSlice

from macropy.core.quotes import macros, q, ast_literal
from macropy.core.hquotes import macros, hq

from ..fup import fupdate
from ..collections import SequenceView

def makeidxspec(tree):
    if type(tree) is ExtSlice:
        assert False, "makeidxspec: multidimensional indexing not supported"
    elif type(tree) is Slice:
        start, stop, step = [x or q[None] for x in (tree.lower, tree.upper, tree.step)]
        idxspec = hq[slice(ast_literal[start], ast_literal[stop], ast_literal[step])]
    elif type(tree) is Index:
        idxspec = tree.value
        if idxspec is None:
            assert False, "makeidxspec: indices must be integers, not NoneType"
    else:
        assert False, "makeidxspec: expected an index expression for a subscript, got {}".format(tree)
    return idxspec

# TODO: improve: multiple fupdate specs?
def fup(tree):
    valid = type(tree) is BinOp and type(tree.op) is LShift and type(tree.left) is Subscript
    if not valid:
        assert False, "fup: expected seq[idx_or_slice] << val"
    seq, idx, val = tree.left.value, tree.left.slice, tree.right
    idxspec = makeidxspec(idx)
    return hq[fupdate(ast_literal[seq], ast_literal[idxspec], ast_literal[val])]

def view(tree):
    if type(tree) is Subscript:  # view[seq[slicestx]]
        seq, idx = tree.value, tree.slice
        idxspec = makeidxspec(idx)
        return hq[SequenceView(ast_literal[seq], ast_literal[idxspec])]
    else:  # view[seq]
        return hq[SequenceView(ast_literal[tree])]
