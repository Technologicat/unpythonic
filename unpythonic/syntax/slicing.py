# -*- coding: utf-8 -*-
"""Macro wrappers for operations using slice syntax."""

from ast import BinOp, LShift, Subscript, Index, Slice, ExtSlice
from copy import deepcopy
from itertools import islice as islicef

from macropy.core.quotes import macros, q, ast_literal
from macropy.core.hquotes import macros, hq

from ..fup import fupdate
from ..collections import SequenceView

def makeidxspec(tree):  # syntax transformer: slice part of subscript --> slice(...) or int
    if type(tree) is ExtSlice:
        assert False, "makeidxspec: multidimensional indexing not supported"
    elif type(tree) is Slice:
        start, stop, step = [x or q[None] for x in (tree.lower, tree.upper, tree.step)]
        idxspec = hq[slice(ast_literal[start], ast_literal[stop], ast_literal[step])]
    elif type(tree) is Index:
        idxspec = tree.value
        if idxspec is None:  # TODO: can this ever be triggered?
            assert False, "makeidxspec: missing index expression"
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

def islice(tree):
    if type(tree) is not Subscript:
        assert False, "islice macro: expected iterable[idx_or_slice]"
    s = tree.slice
    iterable = tree.value
    if type(s) is ExtSlice:
        assert False, "islice macro: multidimensional indexing not supported"
    if type(s) is Slice:
        start, stop, step = [x or q[None] for x in (s.lower, s.upper, s.step)]
        return hq[islicef(ast_literal[iterable], ast_literal[start], ast_literal[stop], ast_literal[step])]
    elif type(s) is Index:  # single index --> one-item islice, evaluated
        i = s.value
        if i is None:  # TODO: can this ever be triggered?
            assert False, "makeidxspec: missing index expression"
        i2 = deepcopy(i)
        return hq[tuple(islicef(ast_literal[iterable], ast_literal[i], ast_literal[i2] + 1))[0]]
    assert False, "islice macro: expected an index expression for a subscript, got {}".format(tree)
