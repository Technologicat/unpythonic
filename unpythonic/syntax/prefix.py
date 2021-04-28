# -*- coding: utf-8 -*-
"""Lisp-like prefix function call syntax for Python.

Experimental, not for use in production code.
"""

from ast import Name, Call, Starred, Tuple, Load, Subscript
import sys

from mcpyrate.quotes import macros, q, u, a, t  # noqa: F811, F401

from mcpyrate.quotes import is_captured_value
from mcpyrate.walkers import ASTTransformer

from .letdoutil import islet, isdo, UnexpandedLetView, UnexpandedDoView

from ..it import flatmap, rev, uniqify

def prefix(block_body):
    isquote = lambda tree: type(tree) is Name and tree.id == "q"
    isunquote = lambda tree: type(tree) is Name and tree.id == "u"
    iskwargs = lambda tree: type(tree) is Call and type(tree.func) is Name and tree.func.id == "kw"

    class PrefixTransformer(ASTTransformer):
        def transform(self, tree):
            if is_captured_value(tree):
                return tree  # don't recurse!

            # Not tuples but syntax: leave alone the:
            #  - binding pair "tuples" of let, letseq, letrec, their d*, b* variants,
            #    and let_syntax, abbrev
            #  - subscript part of an explicit do[], do0[]
            # but recurse inside them.
            #
            # let and do have not expanded yet when prefix runs (better that way!).
            if islet(tree, expanded=False):
                view = UnexpandedLetView(tree)
                for binding in view.bindings:
                    if type(binding) is not Tuple:
                        raise SyntaxError("prefix: expected a tuple in let binding position")  # pragma: no cover
                    _, value = binding.elts  # leave name alone, recurse into value
                    binding.elts[1] = self.visit(value)
                if view.body:
                    view.body = self.visit(view.body)
                return tree
            elif isdo(tree, expanded=False):
                view = UnexpandedDoView(tree)
                view.body = self.visit(view.body)
                return tree

            # Integration with other macros, including the testing framework.
            # Macros may take a tuple as the top-level expr, but typically don't take slice syntax.
            #
            # Up to Python 3.8, a top-level tuple is packed into an Index:
            #     ast.parse("a[1, 2]").body[0].value.slice        # --> <_ast.Index at 0x7fd57505f208>
            #     ast.parse("a[1, 2]").body[0].value.slice.value  # --> <_ast.Tuple at 0x7fd590962ef0>
            # The structure is for this example is
            #     Module
            #       Expr
            #         Subscript
            if type(tree) is Subscript:
                if sys.version_info >= (3, 9, 0):  # Python 3.9+: the Index wrapper is gone.
                    body = tree.slice
                else:
                    body = tree.slice.value

                if type(body) is Tuple:
                    # Skip the transformation of the expr tuple itself, but transform its elements.
                    # This skips the transformation of the macro argument tuple, too, because
                    # that's a nested Subscript (`(macro[a0, ...])[expr]`).
                    body.elts = self.visit(body.elts)
                    tree.value = self.visit(tree.value)
                    return tree
                # in any other case, continue processing normally

            # general case
            # macro-created nodes might not have a ctx, but we run outside in.
            if not (type(tree) is Tuple and type(tree.ctx) is Load):
                return self.generic_visit(tree)
            op, *data = tree.elts
            quotelevel = self.state.quotelevel
            while True:
                if isunquote(op):
                    if quotelevel < 1:
                        raise SyntaxError("unquote while not in quote")  # pragma: no cover
                    quotelevel -= 1
                elif isquote(op):
                    quotelevel += 1
                else:
                    break

                if not len(data):
                    raise SyntaxError("a prefix tuple cannot contain only quote/unquote operators")  # pragma: no cover
                op, *data = data
            if quotelevel > 0:
                quoted = [op] + data
                if any(iskwargs(x) for x in quoted):
                    raise SyntaxError("kw(...) may only appear in a prefix tuple representing a function call")  # pragma: no cover
                self.withstate(quoted, quotelevel=quotelevel)
                return q[t[self.visit(quoted)]]
            # (f, a1, ..., an) --> f(a1, ..., an)
            posargs = [x for x in data if not iskwargs(x)]
            kwargs_calls = [x for x in data if iskwargs(x)]
            # In Python 3.5+, this tags *args as invalid, too, because those are Starred items inside `args`.
            invalids = list(flatmap(lambda tree: tree.args, kwargs_calls))  # no positional args allowed in kw()
            kwargs = list(flatmap(lambda x: x.keywords, kwargs_calls))
            invalids += [x for x in kwargs if type(x) is Starred]  # reject **kwargs
            if invalids:
                raise SyntaxError("kw(...) may only specify individual named args")  # pragma: no cover
            kwargs = list(rev(uniqify(rev(kwargs), key=lambda x: x.arg)))  # latest wins, but keep original ordering
            thecall = Call(func=op, args=posargs, keywords=list(kwargs))
            self.withstate(thecall, quotelevel=quotelevel)
            return self.visit(thecall)

    # This is a first-pass macro. Any nested macros should get clean standard Python,
    # not having to worry about tuples possibly denoting function calls.
    return PrefixTransformer(quotelevel=0).visit(block_body)

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

# TODO: Think of promoting this error to compile macro expansion time.
# TODO: Difficult to do, because we shouldn't probably hijack the name "kw" (so no name macro),
# TODO: and it can't be invoked like an expr macro, because the whole point is to pass arguments by name.
def kw(**kwargs):
    """[syntax] Pass-named-args operator. Only meaningful in a tuple in a prefix block."""
    raise RuntimeError("kw(...) only meaningful inside a tuple in a prefix block")  # pragma: no cover
