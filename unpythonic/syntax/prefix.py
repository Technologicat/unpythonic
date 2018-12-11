# -*- coding: utf-8 -*-
"""Lisp-like prefix function call syntax for Python.

Experimental, not for use in production code.
"""

from ast import Name, Call, Tuple, Load

from macropy.core.quotes import macros, q, u, ast_literal
from macropy.core.walkers import Walker

from .util import islet, isdo, UnexpandedLetView, UnexpandedDoView

from ..it import flatmap, rev, uniqify

def prefix(block_body):
    isquote = lambda tree: type(tree) is Name and tree.id == "q"
    isunquote = lambda tree: type(tree) is Name and tree.id == "u"
    iskwargs = lambda tree: type(tree) is Call and type(tree.func) is Name and tree.func.id == "kw"
    @Walker
    def transform(tree, *, quotelevel, set_ctx, stop, **kw):
        # Not tuples but syntax: leave alone the:
        #  - binding pair "tuples" of let, letseq, letrec, their d*, b* variants,
        #    and let_syntax, abbrev
        #  - subscript part of an explicit do[], do0[]
        # but recurse inside them.
        #
        # let and do have not expanded yet when prefix runs (better that way!).
        if islet(tree, expanded=False):
            stop()
            view = UnexpandedLetView(tree)
            for binding in view.bindings:
                if type(binding) is not Tuple:
                    assert False, "prefix: expected a tuple in let binding position"
                _, value = binding.elts  # leave name alone, recurse into value
                binding.elts[1] = transform.recurse(value, quotelevel=quotelevel)
            if view.body:
                view.body = transform.recurse(view.body, quotelevel=quotelevel)
            return tree
        elif isdo(tree, expanded=False):
            stop()
            view = UnexpandedDoView(tree)
            view.body = [transform.recurse(expr, quotelevel=quotelevel) for expr in view.body]
            return tree
        # general case
        # macro-created nodes might not have a ctx, but we run in the first pass.
        if not (type(tree) is Tuple and type(tree.ctx) is Load):
            return tree
        op, *data = tree.elts
        while True:
            if isunquote(op):
                if quotelevel < 1:
                    assert False, "unquote while not in quote"
                quotelevel -= 1
            elif isquote(op):
                quotelevel += 1
            else:
                break
            set_ctx(quotelevel=quotelevel)
            if not len(data):
                assert False, "a prefix tuple cannot contain only quote/unquote operators"
            op, *data = data
        if quotelevel > 0:
            quoted = [op] + data
            if any(iskwargs(x) for x in quoted):
                assert False, "kw(...) may only appear in a prefix tuple representing a function call"
            return q[(ast_literal[quoted],)]
        # (f, a1, ..., an) --> f(a1, ..., an)
        posargs = [x for x in data if not iskwargs(x)]
        # TODO: tag *args and **kwargs in a kw() as invalid, too (currently just ignored)
        invalids = list(flatmap(lambda x: x.args, filter(iskwargs, data)))
        if invalids:
            assert False, "kw(...) may only specify named args"
        kwargs = flatmap(lambda x: x.keywords, filter(iskwargs, data))
        kwargs = list(rev(uniqify(rev(kwargs), key=lambda x: x.arg)))  # latest wins, but keep original ordering
        return Call(func=op, args=posargs, keywords=list(kwargs))
    # This is a first-pass macro. Any nested macros should get clean standard Python,
    # not having to worry about tuples possibly denoting function calls.
    yield transform.recurse(block_body, quotelevel=0)

# note the exported "q" is ours, but the q we use in this module is a macro.
class q:
    """[syntax] Quote operator. Only meaningful in a tuple in a prefix block."""
    def __repr__(self):  # in case one of these ends up somewhere at runtime
        return "<quote>"
q = q()

class u:
    """[syntax] Unquote operator. Only meaningful in a tuple in a prefix block."""
    def __repr__(self):  # in case one of these ends up somewhere at runtime
        return "<unquote>"
u = u()

# not a @macro_stub; it only raises a run-time error on foo[...], not foo(...)
def kw(**kwargs):
    """[syntax] Pass-named-args operator. Only meaningful in a tuple in a prefix block."""
    raise RuntimeError("kw only meaningful inside a tuple in a prefix block")
