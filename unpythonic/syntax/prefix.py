# -*- coding: utf-8 -*-
"""Lisp-like prefix function call syntax for Python.

Experimental, not for use in production code.
"""

from ast import Name, Call, Tuple, Load, Subscript, Index

from macropy.core.quotes import macros, q, u, ast_literal
from macropy.core.walkers import Walker

from unpythonic.it import flatmap, rev, uniqify

def prefix(block_body):
    isquote = lambda tree: type(tree) is Name and tree.id == "q"
    isunquote = lambda tree: type(tree) is Name and tree.id == "u"
    iskwargs = lambda tree: type(tree) is Call and type(tree.func) is Name and tree.func.id == "kw"
    @Walker
    def transform(tree, *, quotelevel, set_ctx, stop, **kw):
        # Not tuples but syntax: leave alone the:
        #  - bindings blocks of let, letseq, letrec, and the d*, b* variants
        #  - subscript part of an explicit do[]
        # but recurse inside them.
        #
        # let and do have not expanded yet when prefix runs (better that way!),
        # so we can't use the (expanded-form) detectors islet, isdo.
        if type(tree) is Call and type(tree.func) is Name and \
           any(tree.func.id == x for x in ("let", "letseq", "letrec",
                                           "dlet", "dletseq", "dletrec",
                                           "blet", "bletseq", "bletrec")):
            # let((x, 42))[...] appears as Subscript(value=Call(...), ...)
            stop()
            for binding in tree.args:  # TODO: kwargs support for let(x=42)[...] if implemented later
                _, value = binding.elts  # leave name alone, recurse into value
                binding.elts[1] = transform.recurse(value, quotelevel=quotelevel)
            return tree
        elif type(tree) is Subscript and type(tree.value) is Name and \
           any(tree.value.id == x for x in ("do", "do0")) and \
           type(tree.slice) is Index and type(tree.slice.value) is Tuple:
            stop()
            newelts = []
            for expr in tree.slice.value.elts:
                newelts.append(transform.recurse(expr, quotelevel=quotelevel))
            tree.slice.value.elts = newelts
            return tree
        # general case
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

def kw(**kwargs):
    """[syntax] Pass-named-args operator. Only meaningful in a tuple in a prefix block."""
    raise RuntimeError("kw only meaningful inside a tuple in a prefix block")
