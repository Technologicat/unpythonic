# -*- coding: utf-8 -*-
"""Local bindings (let), imperative code in expression position (do)."""

__all__ = ["where",
           "let", "letseq", "letrec",
           "dlet", "dletseq", "dletrec",
           "blet", "bletseq", "bletrec",
           "local", "delete", "do", "do0"]

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

from ast import (Name,
                 Tuple, List,
                 FunctionDef, Return,
                 AsyncFunctionDef,
                 arguments, arg,
                 Load)
import sys

from mcpyrate.quotes import macros, q, u, n, a, t, h  # noqa: F401

from mcpyrate import gensym, namemacro, parametricmacro
from mcpyrate.quotes import capture_as_macro, is_captured_value
from mcpyrate.walkers import ASTTransformer, ASTVisitor

from ..dynassign import dyn
from ..lispylet import _let as letf, _dlet as dletf, _blet as bletf
from ..misc import namelambda
from ..seq import do as dof

from .letdoutil import (isdo, isenvassign, UnexpandedEnvAssignView,
                        UnexpandedLetView, canonize_bindings)
from .nameutil import getname, is_unexpanded_expr_macro
from .scopeanalyzer import scoped_transform

# --------------------------------------------------------------------------------
# Macro interface internal helper

# NOTE: At the macro interface, the invocations `let()[...]` (empty args)
# and `let[...]` (no args) were indistinguishable in MacroPy. This was a
# problem, because it might be that the user wrote the body but simply
# forgot to put anything in the parentheses. (There's `do[]` if you need
# a `let` without making any bindings.)
#
# In `mcpyrate`, `let()[...]` is a syntax error. The preferred syntax,
# when using macro arguments, is `let[...][...]`. When this is not
# possible (in decorator position up to Python 3.8), then `let(...)[...]`
# is acceptable. But empty brackets/parentheses are not accepted. Thus,
# we will have an empty `args` list only when there are no brackets/parentheses
# for the macro arguments part.
#
# So when `args` is empty, this function assumes haskelly let syntax
# `let[(...) in ...]` or `let[..., where(...)]`. In these cases,
# both the bindings and the body reside inside the brackets (i.e.,
# in the AST contained in the `tree` argument).
#
# Since the brackets/parentheses must be deleted when no macro arguments
# are given, this is now the correct assumption to make.
#
# But note that if needed elsewhere, `mcpyrate` has the `invocation` kwarg
# in the macro interface that gives a copy of the whole macro invocation
# node (so we could see the exact original syntax).
#
# letsyntax_mode: used by let_syntax to allow template definitions.
def _destructure_and_apply_let(tree, args, macro_expander, let_transformer, letsyntax_mode=False):
    with dyn.let(_macro_expander=macro_expander):  # implicit do (extra bracket notation) needs this.
        if args:
            bs = canonize_bindings(args, letsyntax_mode=letsyntax_mode)
            return let_transformer(bindings=bs, body=tree)
        # haskelly syntax, let[(...) in ...], let[..., where(...)]
        view = UnexpandedLetView(tree)  # note "tree" here is only the part inside the brackets
        return let_transformer(bindings=view.bindings, body=view.body)

# --------------------------------------------------------------------------------
# Macro interface - expr macros

@namemacro
def where(tree, *, syntax, **kw):
    """[syntax, special] `where` operator for let.

    Usage::

        let[body, where((k0, v0), ...)]

    Only meaningful for declaring the bindings in a let-where, for all
    expression-form let constructs: `let`, `letseq`, `letrec`, `let_syntax`,
    `abbrev`.
    """
    if syntax != "name":
        raise SyntaxError("where (unpythonic.syntax.letdo.where) is a name macro only")  # pragma: no cover
    raise SyntaxError("where() is only meaningful in a let[body, where((k0, v0), ...)]")  # pragma: no cover

@parametricmacro
def let(tree, *, args, syntax, expander, **kw):
    """[syntax, expr] Introduce expression-local variables.

    This is sugar on top of ``unpythonic.lispylet.let``.

    Usage::

        let[(k0, v0), ...][body]
        let[(k0, v0), ...][[body0, ...]]

    where ``body`` is an expression. The names bound by ``let`` are local;
    they are available in ``body``, and do not exist outside ``body``.

    Alternative haskelly syntax is also available::

        let[((k0, v0), ...) in body]
        let[((k0, v0), ...) in [body0, ...]]
        let[body, where((k0, v0), ...)]
        let[[body0, ...], where((k0, v0), ...)]

    For a body with multiple expressions, use an extra set of brackets,
    as shown above. This inserts a ``do``. Only the outermost extra brackets
    are interpreted specially; all others in the bodies are interpreted
    as usual, as lists.

    Note that in the haskelly syntax, the extra brackets for a multi-expression
    body should enclose only the ``body`` part.

    Each ``name`` in the same ``let`` must be unique.

    Assignment to let-bound variables is supported with syntax such as ``x << 42``.
    This is an expression, performing the assignment, and returning the new value.

    In a multiple-expression body, also an internal definition context exists
    for local variables that are not part of the ``let``; see ``do`` for details.

    Technical points:

        - In reality, the let-bound variables live in an ``unpythonic.env``.
          This macro performs the magic to make them look (and pretty much behave)
          like lexical variables.

        - Compared to ``unpythonic.lispylet.let``, the macro version needs no quotes
          around variable names in bindings.

        - The body is automatically wrapped in a ``lambda e: ...``.

        - For all ``x`` in bindings, the macro transforms lookups ``x --> e.x``.

        - Lexical scoping is respected (so ``let`` constructs can be nested)
          by actually using a unique name (gensym) instead of just ``e``.

        - In the case of a multiple-expression body, the ``do`` transformation
          is applied first to ``[body0, ...]``, and the result becomes ``body``.
    """
    if syntax != "expr":
        raise SyntaxError("let is an expr macro only")  # pragma: no cover

    # The `let[]` family of macros expands inside out.
    with dyn.let(_macro_expander=expander):
        return _destructure_and_apply_let(tree, args, expander, _let)

@parametricmacro
def letseq(tree, *, args, syntax, expander, **kw):
    """[syntax, expr] Let with sequential binding (like Scheme/Racket let*).

    Like ``let``, but bindings take effect sequentially. Later bindings
    shadow earlier ones if the same name is used multiple times.

    Expands to nested ``let`` expressions.
    """
    if syntax != "expr":
        raise SyntaxError("letseq is an expr macro only")  # pragma: no cover

    with dyn.let(_macro_expander=expander):
        return _destructure_and_apply_let(tree, args, expander, _letseq)

@parametricmacro
def letrec(tree, *, args, syntax, expander, **kw):
    """[syntax, expr] Let with mutually recursive binding.

    Like ``let``, but bindings can see other bindings in the same ``letrec``.

    Each ``name`` in the same ``letrec`` must be unique.

    The definitions are processed sequentially, left to right. A definition
    may refer to any previous definition. If ``value`` is callable (lambda),
    it may refer to any definition, including later ones.

    This is useful for locally defining mutually recursive functions.
    """
    if syntax != "expr":
        raise SyntaxError("letrec is an expr macro only")  # pragma: no cover

    with dyn.let(_macro_expander=expander):
        return _destructure_and_apply_let(tree, args, expander, _letrec)

# -----------------------------------------------------------------------------
# Macro interface - decorator versions, for "let over def".

@parametricmacro
def dlet(tree, *, args, syntax, expander, **kw):
    """[syntax, decorator] Decorator version of let, for 'let over def'.

    Example::

        @dlet[(x, 0)]
        def count():
            x << x + 1
            return x
        assert count() == 1
        assert count() == 2

    **CAUTION**: function arguments, local variables, and names declared as
    ``global`` or ``nonlocal`` in a given lexical scope shadow names from the
    ``let`` environment *for the entirety of that lexical scope*. (This is
    modeled after Python's standard scoping rules.)

    **CAUTION**: assignment to the let environment is ``name << value``;
    the regular syntax ``name = value`` creates a local variable in the
    lexical scope of the ``def``.
    """
    if syntax != "decorator":
        raise SyntaxError("dlet is a decorator macro only")  # pragma: no cover

    with dyn.let(_macro_expander=expander):
        return _destructure_and_apply_let(tree, args, expander, _dlet)

@parametricmacro
def dletseq(tree, *, args, syntax, expander, **kw):
    """[syntax, decorator] Decorator version of letseq, for 'letseq over def'.

    Expands to nested function definitions, each with one ``dlet`` decorator.

    Example::

        @dletseq[(x, 1),
                 (x, x+1),
                 (x, x+2)]
        def g(a):
            return a + x
        assert g(10) == 14
    """
    if syntax != "decorator":
        raise SyntaxError("dletseq is a decorator macro only")  # pragma: no cover

    with dyn.let(_macro_expander=expander):
        return _destructure_and_apply_let(tree, args, expander, _dletseq)

@parametricmacro
def dletrec(tree, *, args, syntax, expander, **kw):
    """[syntax, decorator] Decorator version of letrec, for 'letrec over def'.

    Example::

        @dletrec[(evenp, lambda x: (x == 0) or oddp(x - 1)),
                 (oddp,  lambda x: (x != 0) and evenp(x - 1))]
        def f(x):
            return evenp(x)
        assert f(42) is True
        assert f(23) is False

    Same cautions apply as to ``dlet``.
    """
    if syntax != "decorator":
        raise SyntaxError("dletrec is a decorator macro only")  # pragma: no cover

    with dyn.let(_macro_expander=expander):
        return _destructure_and_apply_let(tree, args, expander, _dletrec)

@parametricmacro
def blet(tree, *, args, syntax, expander, **kw):
    """[syntax, decorator] def --> let block.

    Example::

        @blet[(x, 21)]
        def result():
            return 2*x
        assert result == 42
    """
    if syntax != "decorator":
        raise SyntaxError("blet is a decorator macro only")  # pragma: no cover

    with dyn.let(_macro_expander=expander):
        return _destructure_and_apply_let(tree, args, expander, _blet)

@parametricmacro
def bletseq(tree, *, args, syntax, expander, **kw):
    """[syntax, decorator] def --> letseq block.

    Example::

        @bletseq[(x, 1),
                 (x, x+1),
                 (x, x+2)]
        def result():
            return x
        assert result == 4
    """
    if syntax != "decorator":
        raise SyntaxError("bletseq is a decorator macro only")  # pragma: no cover

    with dyn.let(_macro_expander=expander):
        return _destructure_and_apply_let(tree, args, expander, _bletseq)

@parametricmacro
def bletrec(tree, *, args, syntax, expander, **kw):
    """[syntax, decorator] def --> letrec block.

    Example::

        @bletrec[(evenp, lambda x: (x == 0) or oddp(x - 1)),
                 (oddp,  lambda x: (x != 0) and evenp(x - 1))]
        def result():
            return evenp(42)
        assert result is True

    Because names inside a ``def`` have mutually recursive scope,
    an almost equivalent pure Python solution (no macros) is::

        from unpythonic.misc import call

        @call
        def result():
            evenp = lambda x: (x == 0) or oddp(x - 1)
            oddp = lambda x: (x != 0) and evenp(x - 1)
            return evenp(42)
        assert result is True
    """
    if syntax != "decorator":
        raise SyntaxError("bletrec is a decorator macro only")  # pragma: no cover

    with dyn.let(_macro_expander=expander):
        return _destructure_and_apply_let(tree, args, expander, _bletrec)

# --------------------------------------------------------------------------------
# Syntax transformers

def _let(bindings, body):
    return _let_expr_impl(bindings, body, "let")

_our_let = capture_as_macro(let)
_our_letseq = capture_as_macro(letseq)
def _letseq(bindings, body):
    if not bindings:
        return body
    first, *rest = bindings
    # We use hygienic macro references in the output,
    # so that the expander can expand them later.
    if rest:
        nested_letseq = q[a[_our_letseq][t[rest]][a[body]]]
        return q[a[_our_let][a[first]][a[nested_letseq]]]
    else:
        # We must do this optimization (no letseq with empty bindings)
        # because empty bindings confuse `_destructure_and_apply_let`.
        return q[a[_our_let][a[first]][a[body]]]

def _letrec(bindings, body):
    return _let_expr_impl(bindings, body, "letrec")

def _let_expr_impl(bindings, body, mode):
    """bindings: sequence of ast.Tuple: (k1, v1), (k2, v2), ..., (kn, vn)"""
    assert mode in ("let", "letrec")

    # The let constructs are currently inside-out macros; expand other macro
    # invocations in both bindings and body.
    #
    # But apply the implicit `do` (extra bracket syntax) first.
    # (It is important we expand at least that immediately after, to resolve its local variables,
    #  because those may have the same lexical names as some of the let-bindings.)
    body = _implicit_do(body)
    body = dyn._macro_expander.visit(body)
    if not bindings:
        # Optimize out a `let` with no bindings. The macro layer cannot trigger
        # this case, because our syntaxes always require at least one binding.
        # So this check is here just to protect against use with no bindings directly
        # from other syntax transformers, which in theory could attempt anything.
        return body  # pragma: no cover
    bindings = dyn._macro_expander.visit(bindings)

    names, values = zip(*[b.elts for b in bindings])  # --> (k1, ..., kn), (v1, ..., vn)
    names = [getname(k, accept_attr=False) for k in names]  # any duplicates will be caught by env at run-time

    e = gensym("e")
    envset = q[n[f"{e}.set"]]

    transform = partial(_letlike_transform, envname=e, lhsnames=names, rhsnames=names, setter=envset)
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

def _letlike_transform(tree, envname, lhsnames, rhsnames, setter, dowrap=True):
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
    tree = _transform_envassignment(tree, lhsnames, setter)
    tree = _transform_name(tree, rhsnames, envname)
    if dowrap:
        tree = _envwrap(tree, envname)
    return tree

def _transform_envassignment(tree, lhsnames, envset):
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

def _transform_name(tree, rhsnames, envname):
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
                attr_node.ctx = tree.ctx
            return attr_node
        return tree
    return scoped_transform(tree, callback=transform)

def _envwrap(tree, envname):
    """... -> lambda e: ..."""
    lam = q[lambda _: a[tree]]
    lam.args.args[0] = arg(arg=envname)  # lambda e44: ...
    return lam

# -----------------------------------------------------------------------------
# Syntax transformers for decorator versions, for "let over def".

def _dlet(bindings, body):
    return _let_decorator_impl(bindings, body, "let", "decorate")

def _dletseq(bindings, body):
    return _dletseq_impl(bindings, body, "decorate")

def _dletrec(bindings, body):
    return _let_decorator_impl(bindings, body, "letrec", "decorate")

def _blet(bindings, body):
    return _let_decorator_impl(bindings, body, "let", "call")

def _bletseq(bindings, body):
    return _dletseq_impl(bindings, body, "call")

def _bletrec(bindings, body):
    return _let_decorator_impl(bindings, body, "letrec", "call")

# Very similar to _let_expr_impl, but perhaps more readable to keep these separate.
def _let_decorator_impl(bindings, body, mode, kind):
    assert mode in ("let", "letrec")
    assert kind in ("decorate", "call")
    if type(body) not in (FunctionDef, AsyncFunctionDef):
        raise SyntaxError("Expected a function definition to decorate")  # pragma: no cover
    body = dyn._macro_expander.visit(body)
    if not bindings:
        # Similarly as above, this cannot trigger from the macro layer no
        # matter what that layer does. This is here to optimize away a `dlet`
        # with no bindings, when used directly from other syntax transformers.
        return body  # pragma: no cover
    bindings = dyn._macro_expander.visit(bindings)

    names, values = zip(*[b.elts for b in bindings])  # --> (k1, ..., kn), (v1, ..., vn)
    names = [getname(k, accept_attr=False) for k in names]  # any duplicates will be caught by env at run-time

    e = gensym("e")
    envset = q[n[f"{e}.set"]]

    transform1 = partial(_letlike_transform, envname=e, lhsnames=names, rhsnames=names, setter=envset)
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

def _dletseq_impl(bindings, body, kind):
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
    dletter = _dlet if kind == "decorate" else _blet
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
    return _dletseq_impl(rest, outer, kind)

# -----------------------------------------------------------------------------
# Imperative code in expression position. Uses the "let" machinery.
#
# Macro interface

def local(tree, *, syntax, **kw):
    """[syntax] Declare a local name in a "do".

    Usage::

        local[name << value]

    Only meaningful in a ``do[...]``, ``do0[...]``, or an implicit ``do``
    (extra bracket syntax).

    The declaration takes effect starting from next item in the ``do``, i.e.
    the item that comes after the ``local[]``. It will not shadow nonlocal
    variables of the same name in any earlier items of the same ``do``, and
    in the item making the definition, the old bindings are still in effect
    on the RHS.

    This means that if you want, you can declare a local ``x`` that takes its
    initial value from a nonlocal ``x``, by ``local[x << x]``. Here the ``x``
    on the RHS is the nonlocal one (since the declaration has not yet taken
    effect), and the ``x`` on the LHS is the name given to the new local variable
    that only exists inside the ``do``. Any references to ``x`` in any further
    items in the same ``do`` will point to the local ``x``.
    """
    if syntax != "expr":
        raise SyntaxError("local is an expr macro only")  # pragma: no cover
    raise SyntaxError("local[] is only valid at the top level of a do[] or do0[]")  # pragma: no cover

def delete(tree, *, syntax, **kw):
    """[syntax] Delete a previously declared local name in a "do".

    Usage::

        delete[name]

    Only meaningful in a ``do[...]``, ``do0[...]``, or an implicit ``do``
    (extra bracket syntax).

    The deletion takes effect starting from the next item; hence, the
    deleted local variable will no longer shadow nonlocal variables of
    the same name in any later items of the same `do`.

    Note ``do[]`` supports local variable deletion, but the ``let[]``
    constructs don't, by design.
    """
    if syntax != "expr":
        raise SyntaxError("delete is an expr macro only")  # pragma: no cover
    raise SyntaxError("delete[] is only valid at the top level of a do[] or do0[]")  # pragma: no cover

def do(tree, *, syntax, expander, **kw):
    """[syntax, expr] Stuff imperative code into an expression position.

    Return value is the value of the last expression inside the ``do``.
    See also ``do0``.

    Usage::

        do[body0, ...]

    Example::

        do[local[x << 42],
           print(x),
           x << 23,
           x]

    This is sugar on top of ``unpythonic.seq.do``, but with some extra features.

        - To declare and initialize a local name, use ``local[name << value]``.

          The operator ``local`` is syntax, not really a function, and it
          only exists inside a ``do``. There is also an operator ``delete``
          to delete a previously declared local name in the ``do``.

          Both ``local`` and ``delete``, if used, should be imported as macros.

        - By design, there is no way to create an uninitialized variable;
          a value must be given at declaration time. Just use ``None``
          as an explicit "no value" if needed.

        - Names declared within the same ``do`` must be unique. Re-declaring
          the same name is an expansion-time error.

        - To assign to an already declared local name, use ``name << value``.

    **local name declarations**

    A ``local`` declaration comes into effect in the expression following
    the one where it appears. Thus::

        result = []
        let((lst, []))[do[result.append(lst),       # the let "lst"
                          local[lst << lst + [1]],  # LHS: do "lst", RHS: let "lst"
                          result.append(lst)]]      # the do "lst"
        assert result == [[], [1]]

    **Syntactic ambiguity**

    These two cases cannot be syntactically distinguished:

        - Just one body expression, which is a literal tuple or list,

        - Multiple body expressions, represented as a literal tuple or list.

    ``do`` always uses the latter interpretation.

    Whenever there are multiple expressions in the body, the ambiguity does not
    arise, because then the distinction between the sequence of expressions itself
    and its items is clear.

    Examples::

        do[1, 2, 3]   # --> tuple, 3
        do[(1, 2, 3)] # --> tuple, 3 (since in Python, the comma creates tuples;
                      #     parentheses are only used for disambiguation)
        do[[1, 2, 3]] # --> list, 3
        do[[[1, 2, 3]]]  # --> list containing a list, [1, 2, 3]
        do[([1, 2, 3],)] # --> tuple containing a list, [1, 2, 3]
        do[[1, 2, 3],]   # --> tuple containing a list, [1, 2, 3]
        do[[(1, 2, 3)]]  # --> list containing a tuple, (1, 2, 3)
        do[((1, 2, 3),)] # --> tuple containing a tuple, (1, 2, 3)
        do[(1, 2, 3),]   # --> tuple containing a tuple, (1, 2, 3)

    It is possible to use ``unpythonic.misc.pack`` to create a tuple from
    given elements: ``do[pack(1, 2, 3)]`` is interpreted as a single-item body
    that creates a tuple (by calling a function).

    Note the outermost brackets belong to the ``do``; they don't yet create a list.

    In the *use brackets to denote a multi-expr body* syntax (e.g. ``multilambda``,
    ``let`` constructs), the extra brackets already create a list, so in those
    uses, the ambiguity does not arise. The transformation inserts not only the
    word ``do``, but also the outermost brackets. For example::

        let[(x, 1),
            (y, 2)][[
              [x, y]]]

    transforms to::

        let[(x, 1),
            (y, 2)][do[[  # "do[" is inserted between the two opening brackets
              [x, y]]]]   # and its closing "]" is inserted here

    which already gets rid of the ambiguity.

    **Notes**

    Macros are expanded in an inside-out order, so a nested ``let`` shadows
    names, if the same names appear in the ``do``::

        do[local[x << 17],
           let[(x, 23)][
             print(x)],  # 23, the "x" of the "let"
           print(x)]     # 17, the "x" of the "do"

    The reason we require local names to be declared is to allow write access
    to lexically outer environments from inside a ``do``::

        let[(x, 17)][
              do[x << 23,         # no "local[...]"; update the "x" of the "let"
                 local[y << 42],  # "y" is local to the "do"
                 print(x, y)]]

    With the extra bracket syntax, the latter example can be written as::

        let[(x, 17)][[
              x << 23,
              local[y << 42],
              print(x, y)]]

    It's subtly different in that the first version has the do-items in a tuple,
    whereas this one has them in a list, but the behavior is exactly the same.

    Python does it the other way around, requiring a ``nonlocal`` statement
    to re-bind a name owned by an outer scope.

    The ``let`` constructs solve this problem by having the local bindings
    declared in a separate block, which plays the role of ``local``.
    """
    if syntax != "expr":
        raise SyntaxError("do is an expr macro only")  # pragma: no cover
    with dyn.let(_macro_expander=expander):
        return _do(tree)

def do0(tree, *, syntax, expander, **kw):
    """[syntax, expr] Like do, but return the value of the first expression."""
    if syntax != "expr":
        raise SyntaxError("do0 is an expr macro only")  # pragma: no cover
    with dyn.let(_macro_expander=expander):
        return _do0(tree)

# --------------------------------------------------------------------------------
# Syntax transformers

def _do(tree):
    if type(tree) not in (Tuple, List):
        raise SyntaxError("do body: expected a sequence of comma-separated expressions")  # pragma: no cover, let's not test the macro expansion errors.

    e = gensym("e")
    envset = q[n[f"{e}._set"]]  # use internal _set to allow new definitions
    envdel = q[n[f"{e}.pop"]]

    islocaldef = partial(is_unexpanded_expr_macro, local, dyn._macro_expander)
    isdelete = partial(is_unexpanded_expr_macro, delete, dyn._macro_expander)

    def transform_localdefs(tree):
        class LocaldefCollector(ASTTransformer):
            def transform(self, tree):
                if is_captured_value(tree):
                    return tree  # don't recurse!
                expr = islocaldef(tree)
                if expr:
                    if not isenvassign(expr):
                        raise SyntaxError("local[...] takes exactly one expression of the form 'name << value'")  # pragma: no cover
                    view = UnexpandedEnvAssignView(expr)
                    self.collect(view.name)
                    view.value = self.visit(view.value)  # nested local[] (e.g. from `do0[local[y << 5],]`)
                    return expr  # `local[x << 21]` --> `x << 21`; compiling *that* makes the env-assignment occur.
                return tree  # don't recurse!
        c = LocaldefCollector()
        tree = c.visit(tree)
        return tree, c.collected
    def transform_deletes(tree):
        class DeleteCollector(ASTTransformer):
            def transform(self, tree):
                if is_captured_value(tree):
                    return tree  # don't recurse!
                expr = isdelete(tree)
                if expr:
                    if type(expr) is not Name:
                        raise SyntaxError("delete[...] takes exactly one name")  # pragma: no cover
                    self.collect(expr.id)
                    return q[a[envdel](u[expr.id])]  # `delete[x]` --> `e.pop('x')`
                return tree  # don't recurse!
        c = DeleteCollector()
        tree = c.visit(tree)
        return tree, c.collected

    def check_strays(ismatch, tree):
        class StrayHelperMacroChecker(ASTVisitor):  # TODO: refactor this?
            def examine(self, tree):
                if is_captured_value(tree):
                    return  # don't recurse!
                elif isdo(tree, expanded=False):
                    return  # don't recurse!
                elif ismatch(tree):
                    # Expand the stray helper macro invocation, to trigger its `SyntaxError`
                    # with a useful message, and *make the expander generate a use site traceback*.
                    #
                    # (If we just `raise` here directly, the expander won't see the use site
                    #  of the `local[]` or `delete[]`, but just that of the `do[]`.)
                    dyn._macro_expander.visit(tree)
                self.generic_visit(tree)
        StrayHelperMacroChecker().visit(tree)
    check_stray_localdefs = partial(check_strays, islocaldef)
    check_stray_deletes = partial(check_strays, isdelete)

    names = []
    lines = []
    for j, expr in enumerate(tree.elts, start=1):
        # Despite the recursion, this will not trigger false positives for nested do[] expressions,
        # because do[] is a second-pass macro, so they expand from inside out.
        expr, newnames = transform_localdefs(expr)
        expr, deletednames = transform_deletes(expr)
        if newnames and deletednames:
            raise SyntaxError("a do-item may have only local[] or delete[], not both")  # pragma: no cover
        if newnames:
            if any(x in names for x in newnames):
                raise SyntaxError("local names must be unique in the same do")  # pragma: no cover

        # Before transforming any further, check that there are no local[] or delete[] further in, where
        # they don't belong. This allows the error message to show the *untransformed* source code for
        # the erroneous invocation.
        check_stray_localdefs(expr)
        check_stray_deletes(expr)

        # The envassignment transform (LHS) needs the updated bindings, whereas
        # the name transform (RHS) should use the previous bindings, so that any
        # changes to bindings take effect starting from the **next** do-item.
        updated_names = [x for x in names + newnames if x not in deletednames]
        expr = _letlike_transform(expr, e, lhsnames=updated_names, rhsnames=names, setter=envset)
        expr = q[h[namelambda](u[f"do_line{j}"])(a[expr])]
        names = updated_names
        lines.append(expr)
    # CAUTION: letdoutil.py depends on the literal name "dof" to detect expanded do forms.
    # Also, the views depend on the exact AST structure.
    # AST-unquoting a `list` of ASTs in the arguments position of a quasiquoted call
    # unpacks it into positional arguments.
    thecall = q[h[dof](a[lines])]
    return thecall

_our_local = capture_as_macro(local)
_our_do = capture_as_macro(do)
def _do0(tree):
    if type(tree) not in (Tuple, List):
        raise SyntaxError("do0 body: expected a sequence of comma-separated expressions")  # pragma: no cover
    elts = tree.elts
    # Use `local[]` and `do[]` as hygienically captured macros.
    newelts = [q[a[_our_local][_do0_result << a[elts[0]]]],  # noqa: F821, local[] defines it inside the do[].
               *elts[1:],
               q[_do0_result]]  # noqa: F821
    return q[a[_our_do][t[newelts]]]  # do0[] is also just a do[]

def _implicit_do(tree):
    """Allow a sequence of expressions in expression position.

    Apply ``do[]`` if ``tree`` is a ``List``, otherwise return ``tree`` as-is.

    Hence, in user code, to represent a sequence of expressions, use brackets::

        [expr0, ...]

    To represent a single literal list where ``_implicit_do`` is in use, use an
    extra set of brackets::

        [[1, 2, 3]]

    The outer brackets enable multiple-expression mode, and the inner brackets
    are then interpreted as a list.
    """
    return q[a[_our_do][t[tree.elts]]] if type(tree) is List else tree
