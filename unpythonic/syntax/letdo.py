# -*- coding: utf-8 -*-
"""Local bindings (let), imperative code in expression position (do)."""

__all__ = ["let", "letseq", "letrec",
           "dlet", "dletseq", "dletrec",
           "blet", "bletseq", "bletrec",
           "local", "delete", "do", "do0",
           "implicit_do"]  # used by some other unpythonic.syntax constructs

# Let constructs are implemented as sugar around unpythonic.lispylet.
#
# We take this approach because letrec needs assignment (must create
# placeholder bindings, then update them with the real values)...
# but in Python, assignment is a statement. As a bonus, we get
# assignment support for let and letseq, too.
#
# Note do[] supports local variable deletion, but the ``let[]`` constructs
# don't, by design. The existence of env.pop() poses no problem since the
# user code has no explicit reference to the let env (with which the code
# could bypass the syntax machinery and directly access the env's methods).

from functools import partial

from ast import (Name, Attribute,
                 Tuple, List,
                 FunctionDef, Return,
                 AsyncFunctionDef,
                 arguments, arg,
                 Load)
import sys

from mcpyrate.quotes import macros, q, u, n, a, t, h  # noqa: F401

from mcpyrate import gensym
from mcpyrate.markers import ASTMarker
from mcpyrate.quotes import is_captured_value
from mcpyrate.utils import NestingLevelTracker
from mcpyrate.walkers import ASTTransformer

from ..dynassign import dyn
from ..lispylet import _let as letf, _dlet as dletf, _blet as bletf
from ..seq import do as dof
from ..misc import namelambda

from .scopeanalyzer import scoped_transform
from .letdoutil import isenvassign, UnexpandedEnvAssignView

def let(bindings, body):
    return _letimpl(bindings, body, "let")

def letseq(bindings, body):
    if not bindings:
        return body
    first, *rest = bindings
    # TODO: Could just return hygienic macro invocations, but that needs to be done
    # TODO: where the macro interfaces are visible. See `unpythonic.syntax.simplelet`
    # TODO: for how to do it.
    return let([first], letseq(rest, body))

def letrec(bindings, body):
    return _letimpl(bindings, body, "letrec")

def _letimpl(bindings, body, mode):
    """bindings: sequence of ast.Tuple: (k1, v1), (k2, v2), ..., (kn, vn)"""
    assert mode in ("let", "letrec")

    # The let constructs are currently inside-out macros; expand other macro
    # invocations in both bindings and body.
    #
    # But apply the implicit `do` (extra bracket syntax) first.
    body = implicit_do(body)
    body = dyn._macro_expander.visit(body)
    if not bindings:
        # Optimize out a `let` with no bindings. The macro layer cannot trigger
        # this case, because our syntaxes always require at least one binding.
        # So this check is here just to protect against use with no bindings directly
        # from other syntax transformers, which in theory could attempt anything.
        #
        # TODO: update this comment for mcpyrate
        # The reason the macro layer never calls us with no bindings is technical.
        # In the macro interface, with no bindings, the macro's `args` are `()`
        # whether it was invoked as `let()[...]` or just `let[...]`. Thus,
        # there is no way to distinguish, in the macro layer, between these
        # two. We can't use `UnexpandedLetView` to do the dirty work of AST
        # analysis, because MacroPy does too much automatically: in the macro
        # layer, `tree` is only the part inside the brackets. So we really
        # can't see whether the part outside the brackets was a Call with no
        # arguments, or just a Name - both cases get treated exactly the same,
        # as a macro invocation with empty `args`.
        #
        # The latter form, `let[...]`, is used by the haskelly syntax
        # `let[(...) in ...]`, `let[..., where(...)]` - and in these cases,
        # both the bindings and the body reside inside the brackets.
        return body  # pragma: no cover
    bindings = dyn._macro_expander.visit(bindings)

    names, values = zip(*[b.elts for b in bindings])  # --> (k1, ..., kn), (v1, ..., vn)
    names = [k.id for k in names]  # any duplicates will be caught by env at run-time

    e = gensym("e")
    envset = Attribute(value=q[n[e]], attr="set", ctx=Load())

    transform = partial(letlike_transform, envname=e, lhsnames=names, rhsnames=names, setter=envset)
    if mode == "letrec":
        values = [transform(rhs) for rhs in values]  # RHSs of bindings
        values = [q[h[namelambda](u[f"letrec_binding{j}_{lhs}"])(a[rhs])]
                    for j, (lhs, rhs) in enumerate(zip(names, values), start=1)]
    body = transform(body)
    body = q[h[namelambda](u[f"{mode}_body"])(a[body])]

    # CAUTION: letdoutil.py relies on:
    #  - the literal name "letter" to detect expanded let forms
    #  - the "mode" kwarg to detect let/letrec mode
    #  - the absence of an "_envname" kwarg to detect this tree represents a let-expr (vs. a let-decorator),
    #    seeing only the Call node
    #  - the exact AST structure, for the views
    letter = letf
    bindings = [q[(u[k], a[v])] for k, v in zip(names, values)]
    newtree = q[h[letter](t[bindings], a[body], mode=u[mode])]
    return newtree

def letlike_transform(tree, envname, lhsnames, rhsnames, setter, dowrap=True):
    """Common transformations for let-like operations.

    Namely::
        x << val --> e.set('x', val)
        x --> e.x  (when x appears in load context)
        # ... -> lambda e: ...  (applied if dowrap=True)

    lhsnames: names to recognize on the LHS of x << val as belonging to this env
    rhsnames: names to recognize anywhere in load context as belonging to this env

    These are separate mainly for ``do[]``, so that we can have new bindings
    take effect only in following exprs.

    setter: function, (k, v) --> v, side effect to set e.k to v
    """
    tree = transform_envassignment(tree, lhsnames, setter)
    tree = transform_name(tree, rhsnames, envname)
    if dowrap:
        tree = envwrap(tree, envname)
    return tree

def transform_envassignment(tree, lhsnames, envset):
    """x << val --> e.set('x', val)  (for names bound in this environment)"""
    # names_in_scope: according to Python's standard binding rules, see scopeanalyzer.py.
    # Variables defined in let envs are thus not listed in `names_in_scope`.
    def transform(tree, names_in_scope):
        if isenvassign(tree):
            view = UnexpandedEnvAssignView(tree)
            varname = view.name
            if varname in lhsnames and varname not in names_in_scope:
                return q[a[envset](u[varname], a[view.value])]
        return tree
    return scoped_transform(tree, callback=transform)

def transform_name(tree, rhsnames, envname):
    """x --> e.x  (in load context; for names bound in this environment)"""
    # names_in_scope: according to Python's standard binding rules, see scopeanalyzer.py.
    # Variables defined in let envs are thus not listed in `names_in_scope`.
    def transform(tree, names_in_scope):
        # This transformation is deceptively simple, hence requires some comment:
        #
        # - Attributes (and Subscripts) work, because we are called again for
        #   the `value` part of the `Attribute` (or `Subscript`) node, which
        #   then gets transformed if it's a `Name` matching our rules.
        #
        # - Once we have transformed `x` --> `e.x`, the final "x" is no longer
        #   a `Name`, but an attr="x" of an `Attribute` node. Our `e`, on the
        #   other hand, is in `names_in_scope` (in the relevant part of
        #   bindings/body), because it is a parameter to a lambda. Thus, because
        #   `e` is a lexical variable that is in scope, it gets left alone.
        #
        # - The same consideration applies to nested lets; an inner (already
        #   expanded) let's `e` will be in scope (because parameter to a lambda)
        #   in those parts of code where it is used, so an outer let will
        #   leave it alone.
        if type(tree) is Name and tree.id in rhsnames and tree.id not in names_in_scope:
            hasctx = hasattr(tree, "ctx")  # macro-created nodes might not have a ctx.
            if hasctx and type(tree.ctx) is not Load:  # let variables are rebound using `<<`, not `=`.
                return tree
            attr_node = q[n[f"{envname}.{tree.id}"]]
            if hasctx:
                attr_node.ctx = tree.ctx  # let mcpyrate fix it if needed
            return attr_node
        return tree
    return scoped_transform(tree, callback=transform)

def envwrap(tree, envname):
    """... -> lambda e: ..."""
    lam = q[lambda _: a[tree]]
    lam.args.args[0] = arg(arg=envname)  # lambda e44: ...
    return lam

# -----------------------------------------------------------------------------
# Decorator versions, for "let over def".

def dlet(bindings, body):
    return _dletimpl(bindings, body, "let", "decorate")

def dletseq(bindings, body):
    return _dletseqimpl(bindings, body, "decorate")

def dletrec(bindings, body):
    return _dletimpl(bindings, body, "letrec", "decorate")

def blet(bindings, body):
    return _dletimpl(bindings, body, "let", "call")

def bletseq(bindings, body):
    return _dletseqimpl(bindings, body, "call")

def bletrec(bindings, body):
    return _dletimpl(bindings, body, "letrec", "call")

# Very similar to _letimpl, but perhaps more readable to keep these separate.
def _dletimpl(bindings, body, mode, kind):
    assert mode in ("let", "letrec")
    assert kind in ("decorate", "call")
    if type(body) not in (FunctionDef, AsyncFunctionDef):
        raise SyntaxError("Expected a function definition to decorate")  # pragma: no cover
    if not bindings:
        # Similarly as above, this cannot trigger from the macro layer no
        # matter what that layer does. This is here to optimize away a `dlet`
        # with no bindings, when used directly from other syntax transformers.
        return body  # pragma: no cover

    names, values = zip(*[b.elts for b in bindings])  # --> (k1, ..., kn), (v1, ..., vn)
    names = [k.id for k in names]  # any duplicates will be caught by env at run-time

    e = gensym("e")
    envset = Attribute(value=q[n[e]], attr="set", ctx=Load())

    transform1 = partial(letlike_transform, envname=e, lhsnames=names, rhsnames=names, setter=envset)
    transform2 = partial(transform1, dowrap=False)
    if mode == "letrec":
        values = [transform1(rhs) for rhs in values]
        values = [q[h[namelambda](u[f"letrec_binding{j}_{lhs}"])(a[rhs])]
                    for j, (lhs, rhs) in enumerate(zip(names, values), start=1)]
    body = transform2(body)

    # We place the let decorator in the innermost position. Hopefully this is ok.
    # (unpythonic.syntax.util.suggest_decorator_index can't help us here,
    #  since "let" is not one of the registered decorators)
    letter = dletf if kind == "decorate" else bletf
    bindings = [q[(u[k], a[v])] for k, v in zip(names, values)]
    # CAUTION: letdoutil.py relies on:
    #  - the literal name "letter" to detect expanded let forms
    #  - the "mode" kwarg to detect let/letrec mode
    #  - the presence of an "_envname" kwarg to detect this tree represents a let-decorator (vs. a let-expr),
    #    seeing only the Call node
    #  - the exact AST structure, for the views
    body.decorator_list = body.decorator_list + [q[h[letter](a[Tuple(elts=bindings)], mode=u[mode], _envname=u[e])]]
    body.args.kwonlyargs = body.args.kwonlyargs + [arg(arg=e)]
    body.args.kw_defaults = body.args.kw_defaults + [None]
    return body

def _dletseqimpl(bindings, body, kind):
    # What we want:
    #
    # @dletseq[(x, 1),
    #          (x, x+1),
    #          (x, x+2)]
    # def g(*args, **kwargs):
    #     return x
    # assert g() == 4
    #
    # -->
    #
    # @dlet[(x, 1)]
    # def g(*args, **kwargs, e1):  # original args from tree go to the outermost def
    #   @dlet[(x, x+1)]            # on RHS, important for e1.x to be in scope
    #   def g2(*, e2):
    #       @dlet[(x, x+2)]
    #       def g3(*, e3):         # expansion proceeds from inside out
    #           return e3.x        # original args travel here by the closure property
    #       return g3()
    #   return g2()
    # assert g() == 4
    #
    assert kind in ("decorate", "call")
    if type(body) not in (FunctionDef, AsyncFunctionDef):
        raise SyntaxError("Expected a function definition to decorate")  # pragma: no cover
    if not bindings:
        # Similarly as above, this cannot trigger from the macro layer no
        # matter what that layer does. This is here to optimize away a `dletseq`
        # with no bindings, when used directly from other syntax transformers.
        return body  # pragma: no cover

    userargs = body.args  # original arguments to the def
    fname = body.name
    noargs = arguments(args=[], kwonlyargs=[], vararg=None, kwarg=None,
                       defaults=[], kw_defaults=[])
    if sys.version_info >= (3, 8, 0):  # Python 3.8+: positional-only arguments
        noargs.posonlyargs = []
    iname = gensym(f"{fname}_inner")
    body.args = noargs
    body.name = iname

    *rest, last = bindings
    dletter = dlet if kind == "decorate" else blet
    innerdef = dletter([last], body)

    # optimization: in the final step, no need to generate a wrapper function
    if not rest:
        tmpargs = innerdef.args
        innerdef.name = fname
        innerdef.args = userargs
        # copy the env arg
        innerdef.args.kwonlyargs += tmpargs.kwonlyargs
        innerdef.args.kw_defaults += tmpargs.kw_defaults
        return innerdef

    # If kind=="decorate", the outer function needs to call the inner one
    # after defining it.
    # If kind=="call", then, after innerdef completes, the inner function has
    # already been replaced by its return value.
    ret = Return(value=q[n[iname]()]) if kind == "decorate" else Return(value=q[n[iname]])
    outer = FunctionDef(name=fname, args=userargs,
                        body=[innerdef, ret],
                        decorator_list=[],
                        returns=None)  # no return type annotation
    return _dletseqimpl(rest, outer, kind)

# -----------------------------------------------------------------------------
# Imperative code in expression position. Uses the "let" machinery.

_do_level = NestingLevelTracker()  # for checking validity of local[] and delete[]

# Use `mcpyrate` ASTMarkers, so that the expander can do the dirty work of
# detecting macro invocations. Our `do[]` macro then only needs to detect
# instances of the appropriate markers.
class UnpythonicLetDoMarker(ASTMarker):
    """AST marker related to unpythonic's let/do subsystem."""
class UnpythonicDoLocalMarker(UnpythonicLetDoMarker):
    """AST marker for local variable definitions in a `do` context."""
class UnpythonicDoDeleteMarker(UnpythonicLetDoMarker):
    """AST marker for local variable deletion in a `do` context."""

# TODO: fail-fast: promote `local[]`/`delete[]` usage errors to compile-time errors
# TODO: (doesn't currently work e.g. for `let` with an implicit do (extra bracket notation))
def local(tree):  # syntax transformer
    if _do_level.value < 1:
        raise SyntaxError("local[] is only valid within a do[] or do0[]")  # pragma: no cover
    return UnpythonicDoLocalMarker(tree)

def delete(tree):  # syntax transformer
    if _do_level.value < 1:
        raise SyntaxError("delete[] is only valid within a do[] or do0[]")  # pragma: no cover
    return UnpythonicDoDeleteMarker(tree)

def do(tree):
    if type(tree) not in (Tuple, List):
        raise SyntaxError("do body: expected a sequence of comma-separated expressions")  # pragma: no cover, let's not test the macro expansion errors.

    # Handle nested `local[]`/`delete[]`. This will also expand any other nested macro invocations.
    # TODO: If we want to make `do` an outside-in macro, instantiate another expander here and register
    # TODO: only the `local` and `delete` transformers to it - grabbing them from the current expander's
    # TODO: bindings to respect as-imports. (Expander instances are cheap in `mcpyrate`.)
    # TODO: Grep the `unpythonic` codebase (and `mcpyrate` demos) for `MacroExpander` to see how.
    with _do_level.changed_by(+1):
        tree = dyn._macro_expander.visit(tree)

    e = gensym("e")
    envset = q[n[f"{e}._set"]]  # use internal _set to allow new definitions
    envset.ctx = Load()
    envdel = q[n[f"{e}.pop"]]
    envdel.ctx = Load()

    def find_localdefs(tree):
        class LocaldefCollector(ASTTransformer):
            def transform(self, tree):
                if is_captured_value(tree):
                    return tree  # don't recurse!
                if isinstance(tree, UnpythonicDoLocalMarker):
                    expr = tree.body
                    if not isenvassign(expr):
                        raise SyntaxError("local[...] takes exactly one expression of the form 'name << value'")  # pragma: no cover
                    view = UnexpandedEnvAssignView(expr)
                    self.collect(view.name)
                    # e.g. `x << 21`; preserve the original expr to make the assignment occur.
                    return self.visit(expr)  # handle nested local[] (e.g. from `do0[local[y << 5],]`)
                return self.generic_visit(tree)
        c = LocaldefCollector()
        tree = c.visit(tree)
        return tree, c.collected
    def find_deletes(tree):
        class DeleteCollector(ASTTransformer):
            def transform(self, tree):
                if is_captured_value(tree):
                    return tree  # don't recurse!
                if isinstance(tree, UnpythonicDoDeleteMarker):
                    expr = tree.body
                    if type(expr) is not Name:
                        raise SyntaxError("delete[...] takes exactly one name")  # pragma: no cover
                    self.collect(expr.id)
                    return q[a[envdel](u[expr.id])]  # -> e.pop(...)
                return self.generic_visit(tree)
        c = DeleteCollector()
        tree = c.visit(tree)
        return tree, c.collected

    names = []
    lines = []
    for j, expr in enumerate(tree.elts, start=1):
        # Despite the recursion, this will not trigger false positives for nested do[] expressions,
        # because do[] is a second-pass macro, so they expand from inside out.
        expr, newnames = find_localdefs(expr)
        expr, deletednames = find_deletes(expr)
        if newnames and deletednames:
            raise SyntaxError("a do-item may have only local[] or delete[], not both")  # pragma: no cover
        if newnames:
            if any(x in names for x in newnames):
                raise SyntaxError("local names must be unique in the same do")  # pragma: no cover
        # The envassignment transform (LHS) needs the updated bindings, whereas
        # the name transform (RHS) should use the previous bindings, so that any
        # changes to bindings take effect starting from the **next** do-item.
        updated_names = [x for x in names + newnames if x not in deletednames]
        expr = letlike_transform(expr, e, lhsnames=updated_names, rhsnames=names, setter=envset)
        expr = q[h[namelambda](u[f"do_line{j}"])(a[expr])]
        names = updated_names
        lines.append(expr)
    # CAUTION: letdoutil.py depends on the literal name "dof" to detect expanded do forms.
    # Also, the views depend on the exact AST structure.
    thecall = q[h[dof]()]
    thecall.args = lines
    return thecall

def do0(tree):
    if type(tree) not in (Tuple, List):
        raise SyntaxError("do0 body: expected a sequence of comma-separated expressions")  # pragma: no cover
    elts = tree.elts
    newelts = []
    # TODO: Would be cleaner to use `local[]` as a hygienically captured macro.
    # Now we call the syntax transformer directly, and splice in the returned AST.
    with _do_level.changed_by(+1):  # it's alright, `local[]`, we're inside a `do0[]`.
        firstexpr = elts[0]
        firstexpr = dyn._macro_expander.visit(firstexpr)
        thelocalexpr = q[_do0_result << a[firstexpr]]  # noqa: F821, the local[] defines it inside the do[].
        newelts.append(q[a[local(thelocalexpr)]])
    newelts.extend(elts[1:])
    newelts.append(q[_do0_result])  # noqa: F821
    newtree = q[t[newelts]]
    # TODO: Would be cleaner to use `do[]` as a hygienically captured macro.
    return do(newtree)  # do0[] is also just a do[]

def implicit_do(tree):
    """Allow a sequence of expressions in expression position.

    Apply ``do[]`` if ``tree`` is a ``List``, otherwise return ``tree`` as-is.

    Hence, in user code, to represent a sequence of expressions, use brackets::

        [expr0, ...]

    To represent a single literal list where ``implicit_do`` is in use, use an
    extra set of brackets::

        [[1, 2, 3]]

    The outer brackets enable multiple-expression mode, and the inner brackets
    are then interpreted as a list.
    """
    return do(tree) if type(tree) is List else tree
