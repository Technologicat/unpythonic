# -*- coding: utf-8 -*-
"""Lisp-like prefix function call syntax for Python.

Experimental, not for use in production code.
"""

__all__ = ["prefix", "q", "u", "kw"]

from ast import Call, Starred, Tuple, Load, Subscript
import sys

from mcpyrate.quotes import macros, q, u, a, t  # noqa: F811, F401

from mcpyrate import namemacro
from mcpyrate.quotes import is_captured_value
from mcpyrate.walkers import ASTTransformer

from .letdoutil import islet, isdo, UnexpandedLetView, UnexpandedDoView
from .nameutil import getname

from ..it import flatmap, rev, uniqify

# --------------------------------------------------------------------------------

def prefix(tree, *, syntax, **kw):  # noqa: F811
    """[syntax, block] Write Python like Lisp: the first item is the operator.

    Example::

        with prefix:
            (print, "hello world")
            t1 = (q, 1, 2, (3, 4), 5)
            x = 42
            t2 = (q, 17, 23, x)
            (print, t1, t2)

    Lexically inside a ``with prefix``:

        - A bare ``q`` at the head of a tuple is the quote operator. It increases
          the quote level by one.

          It actually just tells the macro that this tuple (and everything in it,
          recursively) is not a function call.

          Variables can be used as usual, there is no need to unquote them.

        - A bare ``u`` at the head of a tuple is the unquote operator, which
          decreases the quote level by one. In other words, in::

              with prefix:
                  t = (q, 1, 2, (u, print, 3), (print, 4), 5)
                  (print, t)

          the third item will call ``print(3)`` and evaluate to its return value
          (in this case ``None``, since it's ``print``), whereas the fourth item
          is a tuple with the two items ``(<built-in function print>, 4)``.

        - Quote/unquote operators are parsed from the start of the tuple until
          no more remain. Then any remaining items are either returned quoted
          (if quote level > 0), or evaluated as a function call and replaced
          by the return value.

        - How to pass named args::

              from unpythonic.misc import call

              with prefix:
                  (f, kw(myarg=3))  # ``kw(...)`` (syntax, not really a function!)
                  call(f, myarg=3)  # in a call(), kwargs are ok
                  f(myarg=3)        # or just use Python's usual function call syntax

          One ``kw`` operator may include any number of named args (and **only**
          named args). The tuple may have any number of ``kw`` operators.

          All named args are collected from ``kw`` operators in the tuple
          when writing the final function call. If the same kwarg has been
          specified by multiple ``kw`` operators, the rightmost definition wins.

          **Note**: Python itself prohibits having repeated named args in the **same**
          ``kw`` operator, because it uses the function call syntax. If you try to pass
          the same named arg multiple times, as of 0.15, you should get a
          `SyntaxError: keyword argument repeated` with a traceback.

          A ``kw(...)`` operator in a quoted tuple (i.e. a tuple that does not not
          represent a function call) is an error.

    Current limitations:

        - passing ``*args`` and ``**kwargs`` not supported.

          Workarounds: ``call(...)``; Python's usual function call syntax.

        - For ``*args``, to keep it lispy, maybe you want ``unpythonic.fun.apply``;
          this allows syntax such as ``(apply, f, 1, 2, lst)``.

    **CAUTION**: This macro is experimental, not intended for production use.
    """
    if syntax != "block":
        raise SyntaxError("prefix is a block macro only")  # pragma: no cover
    if syntax == "block" and kw['optional_vars'] is not None:
        raise SyntaxError("prefix does not take an as-part")  # pragma: no cover

    # Expand outside in. Any nested macros should get clean standard Python,
    # not having to worry about tuples possibly denoting function calls.
    return _prefix(block_body=tree)

# Note the exported "q" and "u" are ours (namely the stubs for the "q" and "u"
# operators compiled away by `prefix`), but the "q[]" we use as a macro in
# this module is the quasiquote operator from `mcpyrate.quotes`.
#
# This `def` doesn't overwrite the macro `q`, because the `def` runs at run time.
# The expander does not try to expand this `q` as a macro, because `def q(...)`
# is not a valid macro invocation even when the name `q` has been imported as a macro.
@namemacro
def q(tree, *, syntax, **kw):  # noqa: F811
    """[syntax, name] Quote operator. Only meaningful in a tuple inside a prefix block."""
    if syntax != "name":
        raise SyntaxError("q (unpythonic.syntax.prefix.q) is a name macro only")  # pragma: no cover
    raise SyntaxError("q (unpythonic.syntax.prefix.q) is only valid in a tuple inside a `with prefix` block")  # pragma: no cover, not meant to hit the expander

@namemacro
def u(tree, *, syntax, **kw):  # noqa: F811
    """[syntax, name] Unquote operator. Only meaningful in a tuple inside a prefix block."""
    if syntax != "name":
        raise SyntaxError("q (unpythonic.syntax.prefix.q) is a name macro only")  # pragma: no cover
    raise SyntaxError("q (unpythonic.syntax.prefix.q) is only valid in a tuple inside a `with prefix` block")  # pragma: no cover, not meant to hit the expander

# TODO: This isn't a perfect solution, because there is no "call" macro kind.
# TODO: We currently trigger the error on any appearance of the name `kw` outside a valid context.
@namemacro
def kw(tree, *, syntax, **kw):  # noqa: F811
    """[syntax, special] Pass-named-args operator for `with prefix`.

    Usage::

        (f, a0, ..., kw(k0=v0, ...))

    Only meaningful in a tuple inside a prefix block.
    """
    if syntax != "name":
        raise SyntaxError("kw (unpythonic.syntax.prefix.kw) is a name macro only")  # pragma: no cover
    raise SyntaxError("kw (unpythonic.syntax.prefix.kw) is only valid in a tuple inside a `with prefix` block")  # pragma: no cover, not meant to hit the expander

# --------------------------------------------------------------------------------

def _prefix(block_body):
    isquote = lambda tree: getname(tree, accept_attr=False) == "q"
    isunquote = lambda tree: getname(tree, accept_attr=False) == "u"
    iskwargs = lambda tree: type(tree) is Call and getname(tree.func, accept_attr=False) == "kw"

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

    # This is a outside-in macro. Any nested macros should get clean standard Python,
    # not having to worry about tuples possibly denoting function calls.
    return PrefixTransformer(quotelevel=0).visit(block_body)
