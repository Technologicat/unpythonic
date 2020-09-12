# -*- coding: utf-8 -*-
"""Lisp-like prefix function call syntax for Python.

Experimental, not for use in production code.
"""

from ast import Name, Call, Tuple, Load, Index, Subscript
import sys

# Python 3.4 expects a Call node to have `starargs` and `kwargs` attributes.
# These are gone in Python 3.5+, because the AST representation of function
# calls was changed in 3.5.
#     https://greentreesnakes.readthedocs.io/en/latest/nodes.html#Call
#
# Well, more exactly, `macropy.core.unparse` expects to find those attributes,
# and our testing framework just happens to unparse the input to a test macro,
# so it can show the expr if the test happens to go south.
#
# So we have to be careful to generate well-formed nodes.
PYTHON34 = sys.version_info >= (3, 4) and sys.version_info < (3, 5)

from macropy.core.quotes import macros, q, u, ast_literal  # noqa: F811, F401
from macropy.core.walkers import Walker

from .letdoutil import islet, isdo, UnexpandedLetView, UnexpandedDoView

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
                    assert False, "prefix: expected a tuple in let binding position"  # pragma: no cover
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

        # Integration with other macros, including the testing framework.
        # Macros may take a tuple as the top-level expr, but typically don't take slice syntax.
        #
        # A top-level tuple is packed into an Index, not into an ExtSlice:
        #     ast.parse("a[1, 2]").body[0].value.slice        # --> <_ast.Index at 0x7fd57505f208>
        #     ast.parse("a[1, 2]").body[0].value.slice.value  # --> <_ast.Tuple at 0x7fd590962ef0>
        # The structure is for this example is
        #     Module
        #       Expr
        #         Subscript
        if type(tree) is Subscript and type(tree.slice) is Index:
            body = tree.slice.value
            if type(body) is Tuple:
                stop()
                # skip the transformation of the argument tuple itself, but transform its elements
                body.elts = [transform.recurse(expr, quotelevel=quotelevel) for expr in body.elts]
                return tree
            # in any other case, continue processing normally

        # general case
        # macro-created nodes might not have a ctx, but we run in the first pass.
        if not (type(tree) is Tuple and type(tree.ctx) is Load):
            return tree
        op, *data = tree.elts
        while True:
            if isunquote(op):
                if quotelevel < 1:
                    assert False, "unquote while not in quote"  # pragma: no cover
                quotelevel -= 1
            elif isquote(op):
                quotelevel += 1
            else:
                break
            set_ctx(quotelevel=quotelevel)
            if not len(data):
                assert False, "a prefix tuple cannot contain only quote/unquote operators"  # pragma: no cover
            op, *data = data
        if quotelevel > 0:
            quoted = [op] + data
            if any(iskwargs(x) for x in quoted):
                assert False, "kw(...) may only appear in a prefix tuple representing a function call"  # pragma: no cover
            return q[(ast_literal[quoted],)]
        # (f, a1, ..., an) --> f(a1, ..., an)
        posargs = [x for x in data if not iskwargs(x)]
        # TODO: tag *args and **kwargs in a kw() as invalid, too (currently just ignored)
        invalids = list(flatmap(lambda x: x.args, filter(iskwargs, data)))
        if invalids:
            assert False, "kw(...) may only specify named args"  # pragma: no cover
        kwargs = flatmap(lambda x: x.keywords, filter(iskwargs, data))
        kwargs = list(rev(uniqify(rev(kwargs), key=lambda x: x.arg)))  # latest wins, but keep original ordering
        thecall = Call(func=op, args=posargs, keywords=list(kwargs))
        if PYTHON34:  # pragma: no cover, Python 3.4 only
            thecall.starargs = None
            thecall.kwargs = None
        return thecall
    # This is a first-pass macro. Any nested macros should get clean standard Python,
    # not having to worry about tuples possibly denoting function calls.
    yield transform.recurse(block_body, quotelevel=0)

# Note the exported "q" and "u" are ours, but the "q" and "u" we use in this
# module are macros. The "q" and "u" we define here are regular run-time objects,
# namely the stubs for the "q" and "u" markers used within a `prefix` block.
class q:  # noqa: F811
    """[syntax] Quote operator. Only meaningful in a tuple in a prefix block."""
    def __repr__(self):  # in case one of these ends up somewhere at runtime  # pragma: no cover
        return "<quote>"
q = q()

class u:  # noqa: F811
    """[syntax] Unquote operator. Only meaningful in a tuple in a prefix block."""
    def __repr__(self):  # in case one of these ends up somewhere at runtime  # pragma: no cover
        return "<unquote>"
u = u()

# not a @macro_stub; it only raises a run-time error on foo[...], not foo(...)
def kw(**kwargs):
    """[syntax] Pass-named-args operator. Only meaningful in a tuple in a prefix block."""
    raise RuntimeError("kw only meaningful inside a tuple in a prefix block")  # pragma: no cover
