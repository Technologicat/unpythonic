# -*- coding: utf-8 -*-

# This is for introducing **syntactic** local bindings, i.e. simple code splicing
# at macro expansion time. If you're looking for regular run-time let et al. macros,
# see letdo.py.

__all__ = ["let_syntax", "abbrev", "expr", "block"]

from mcpyrate.quotes import macros, q, a  # noqa: F401

from ast import Name, Call, Subscript, Tuple, Starred, Expr, With
from copy import deepcopy
from functools import partial
import sys

from mcpyrate import parametricmacro
from mcpyrate.quotes import is_captured_value
from mcpyrate.utils import rename
from mcpyrate.walkers import ASTTransformer, ASTVisitor

from .letdo import _implicit_do, _destructure_and_apply_let
from .nameutil import is_unexpanded_block_macro
from .util import eliminate_ifones

from ..dynassign import dyn

# --------------------------------------------------------------------------------
# Macro interface

@parametricmacro
def let_syntax(tree, *, args, syntax, expander, **kw):
    """[syntax, expr/block] Introduce local **syntactic** bindings.

    **Expression variant**::

        let_syntax[lhs << rhs, ...][body]
        let_syntax[lhs << rhs, ...][[body0, ...]]

    Alternative haskelly syntax::

        let_syntax[[lhs << rhs, ...] in body]
        let_syntax[[lhs << rhs, ...] in [body0, ...]]

        let_syntax[body, where[lhs << rhs, ...]]
        let_syntax[[body0, ...], where[lhs << rhs, ...]]

    **Block variant**::

        with let_syntax:
            with block as xs:          # capture a block of statements - bare name
                ...
            with block[a, ...] as xs:  # capture a block of statements - template
                ...
            with expr as x:            # capture a single expression - bare name
                ...
            with expr[a, ...] as x:    # capture a single expression - template
                ...
            body0
            ...

    A single expression can be a ``do[]`` if multiple expressions are needed.

    The bindings are applied **at macro expansion time**, substituting
    the expression on the RHS for each instance of the corresponding LHS.
    Each substitution gets a fresh copy.

    This is useful to e.g. locally abbreviate long function names at macro
    expansion time (with zero run-time overhead), or to splice in several
    (possibly parametric) instances of a common pattern.

    In the expression variant, ``lhs`` may be:

      - A bare name (e.g. ``x``), or

      - A simple template of the form ``f(x, ...)``. The names inside the
        parentheses declare the formal parameters of the template (that can
        then be used in the body).

    In the block variant:

      - The **as-part** specifies the name of the LHS.

      - If a template, the formal parameters are declared on the ``block``
        or ``expr``, not on the as-part (due to syntactic limitations).

    **Templates**

    To make parametric substitutions, use templates.

    Templates support only positional arguments, with no default values.

    Even in block templates, parameters are always expressions (because they
    use the subscript syntax at the use site).

    In the body of the ``let_syntax``, a template is used like an expr macro.
    Just like in an actual macro invocation, when the template is substituted,
    any instances of its formal parameters on its RHS get replaced by the
    argument values from the invocation site.

    Note each instance of the same formal parameter gets a fresh copy of the
    corresponding argument value.

    **Substitution order**

    This is a two-step process. In the first step, we apply template substitutions.
    In the second step, we apply bare name substitutions to the result of the
    first step. (So RHSs of templates may use any of the bare-name definitions.)

    Within each step, the substitutions are applied **in the order specified**.
    So if the bindings are ``((x, y), (y, z))``, then ``x`` transforms to ``z``.
    But if the bindings are ``((y, z), (x, y))``, then ``x`` transforms to ``y``,
    and only an explicit ``y`` at the use site transforms to ``z``.

    **Notes**

    Inspired by Racket's ``let-syntax`` and ``with-syntax``, see:
        https://docs.racket-lang.org/reference/let.html
        https://docs.racket-lang.org/reference/stx-patterns.html

    **CAUTION**: This is essentially a toy macro system inside the real
    macro system, implemented with the real macro system.

    The usual caveats of macro systems apply. Especially, we support absolutely
    no form of hygiene. Be very, very careful to avoid name conflicts.

    ``let_syntax`` is meant only for simple local substitutions where the
    elimination of repetition can shorten the code and improve readability.

    If you need to do something complex, prefer writing a real macro directly
    in `mcpyrate`.
    """
    if syntax not in ("expr", "block"):
        raise SyntaxError("let_syntax is an expr and block macro only")  # pragma: no cover
    if syntax == "block" and kw['optional_vars'] is not None:
        raise SyntaxError("let_syntax (block mode) does not take an as-part")  # pragma: no cover

    if syntax == "expr":
        _let_syntax_expr_inside_out = partial(_let_syntax_expr, expand_inside=True)
        return _destructure_and_apply_let(tree, args, expander, _let_syntax_expr_inside_out, letsyntax_mode=True)
    else:  # syntax == "block":
        with dyn.let(_macro_expander=expander):
            return _let_syntax_block(block_body=tree, expand_inside=True)

@parametricmacro
def abbrev(tree, *, args, syntax, expander, **kw):
    """[syntax, expr/block] Exactly like ``let_syntax``, but expands outside in.

    Because this variant expands before any macros in the body, it can locally
    rename other macros, e.g.::

        abbrev[m << macrowithverylongname][
                 m[tree1] if m[tree2] else m[tree3]]

    **CAUTION**: Because ``abbrev`` expands outside-in, and does not respect
    boundaries of any nested ``abbrev`` invocations, it will not lexically scope
    the substitutions. Instead, the outermost ``abbrev`` expands first, and then
    any inner ones expand with whatever substitutions they have remaining.

    If the same name is used on the LHS in two or more nested ``abbrev``,
    any inner ones will likely raise an error (unless the outer substitution
    just replaces a name with another), because also the names on the LHS
    in the inner ``abbrev`` will undergo substitution when the outer
    ``abbrev`` expands.
    """
    if syntax not in ("expr", "block"):
        raise SyntaxError("abbrev is an expr and block macro only")  # pragma: no cover
    if syntax == "block" and kw['optional_vars'] is not None:
        raise SyntaxError("abbrev (block mode) does not take an as-part")  # pragma: no cover

    # DON'T expand inner macro invocations first - outside-in ordering is the default, so we simply do nothing.

    if syntax == "expr":
        _let_syntax_expr_outside_in = partial(_let_syntax_expr, expand_inside=False)
        return _destructure_and_apply_let(tree, args, expander, _let_syntax_expr_outside_in,
                                          letsyntax_mode=True)
    else:
        with dyn.let(_macro_expander=expander):
            return _let_syntax_block(block_body=tree, expand_inside=False)

@parametricmacro
def expr(tree, *, syntax, **kw):
    """[syntax, block] ``with expr:`` inside a ``with let_syntax:``."""
    if syntax != "block":
        raise SyntaxError("`expr` is a block macro only")  # pragma: no cover
    raise SyntaxError("`expr` is only valid at the top level of a block-mode `let_syntax` or `abbrev`")  # pragma: no cover, not intended to hit the expander

@parametricmacro
def block(tree, *, syntax, **kw):
    """[syntax, block] ``with block:`` inside a ``with let_syntax:``."""
    if syntax != "block":
        raise SyntaxError("`block` is a block macro only")  # pragma: no cover
    raise SyntaxError("`block` is only valid at the top level of a block-mode `let_syntax` or `abbrev`")  # pragma: no cover, not intended to hit the expander

# --------------------------------------------------------------------------------
# Syntax transformers

# let_syntax[lhs << rhs, ...][body]
# let_syntax[lhs << rhs, ...][[body0, ...]]
# let_syntax[[lhs << rhs, ...] in body]
# let_syntax[[lhs << rhs, ...] in [body0, ...]]
# let_syntax[body, where[lhs << rhs, ...]]
# let_syntax[[body0, ...], where[lhs << rhs, ...]]
#
# This transformer takes destructured input, with the bindings subform
# and the body already extracted, and supplied separately.
#
# bindings: sequence of ast.Tuple: (k1, v1), (k2, v2), ..., (kn, vn)
# expand_inside: if True, expand inside-out. If False, expand outside-in.
def _let_syntax_expr(bindings, body, *, expand_inside):
    body = _implicit_do(body)  # support the extra bracket syntax
    if not bindings:  # Optimize out a `let_syntax` with no bindings.
        return body  # pragma: no cover

    names_seen = set()
    templates = []
    barenames = []
    def register_bindings():
        for line in bindings:
            key, value = line.elts
            name, args = _analyze_lhs(key)
            if name in names_seen:
                raise SyntaxError(f"duplicate '{name}'; names defined in the same let_syntax expr must be unique")  # pragma: no cover
            names_seen.add(name)
            target = templates if args else barenames
            target.append((name, args, value, "expr"))

    if expand_inside:
        bindings = dyn._macro_expander.visit(bindings)
        body = dyn._macro_expander.visit(body)
    register_bindings()
    body = _substitute_templates(templates, body)
    body = _substitute_barenames(barenames, body)
    return body

# block version:
#
# with let_syntax:
#     with block as xs:
#         ...
#     with block[a, ...] as xs:
#         ...
#     with expr as x:
#         ...
#     with expr[a, ...] as x:
#         ...
#     body0
#     ...
#
# expand_inside: if True, expand inside-out. If False, expand outside-in.
def _let_syntax_block(block_body, *, expand_inside):
    is_let_syntax = partial(is_unexpanded_block_macro, let_syntax, dyn._macro_expander)
    is_abbrev = partial(is_unexpanded_block_macro, abbrev, dyn._macro_expander)
    is_expr_declaration = partial(is_unexpanded_block_macro, expr, dyn._macro_expander)
    is_block_declaration = partial(is_unexpanded_block_macro, block, dyn._macro_expander)
    is_helper_macro = lambda tree: is_expr_declaration(tree) or is_block_declaration(tree)
    def check_strays(ismatch, tree):
        class StrayHelperMacroChecker(ASTVisitor):  # TODO: refactor this?
            def examine(self, tree):
                if is_captured_value(tree):
                    return  # don't recurse!
                elif is_let_syntax(tree) or is_abbrev(tree):
                    return  # don't recurse!
                elif ismatch(tree):
                    # Expand the stray helper macro invocation, to trigger its `SyntaxError`
                    # with a useful message, and *make the expander generate a use site traceback*.
                    #
                    # (If we just `raise` here directly, the expander won't see the use site
                    #  of the `with expr` or `with block`, but just that of the `do[]`.)
                    dyn._macro_expander.visit(tree)
                self.generic_visit(tree)
        StrayHelperMacroChecker().visit(tree)
    check_stray_blocks_and_exprs = partial(check_strays, is_helper_macro)

    names_seen = set()
    def destructure_binding(withstmt, mode, kind):
        assert mode in ("block", "expr")
        assert kind in ("barename", "template")
        ctxmanager = withstmt.items[0].context_expr
        optvars = withstmt.items[0].optional_vars
        if not optvars:
            raise SyntaxError(f"'with {mode}:': expected an as-part")  # pragma: no cover
        if type(optvars) is not Name:
            raise SyntaxError(f"'with {mode}:': expected exactly one name in the as-part")  # pragma: no cover

        name = optvars.id
        if name in names_seen:
            raise SyntaxError(f"duplicate '{name}'; as-parts in the same let_syntax block must be unique")  # pragma: no cover

        if kind == "template":
            _, args = _analyze_lhs(ctxmanager)  # syntactic limitation, can't place formal parameter list on the as-part
        else:  # kind == "barename":
            args = []

        if mode == "block":
            with q as value:
                if 1:
                    with a:
                        withstmt.body
        else:  # mode == "expr":
            if len(withstmt.body) != 1:
                raise SyntaxError("'with expr:' expected a one-item body (use a do[] if need more)")  # pragma: no cover
            theexpr = withstmt.body[0]
            if type(theexpr) is not Expr:
                raise SyntaxError("'with expr:' expected an expression body, got a statement")  # pragma: no cover
            value = theexpr.value  # discard Expr wrapper in definition
        names_seen.add(name)

        return name, args, value, mode

    def isbinding(tree):
        for mode in ("block", "expr"):
            if not (type(tree) is With and len(tree.items) == 1):
                continue
            ctxmanager = tree.items[0].context_expr
            if type(ctxmanager) is Name and ctxmanager.id == mode:
                return mode, "barename"
            # expr[...], block[...]
            if type(ctxmanager) is Subscript and type(ctxmanager.value) is Name and ctxmanager.value.id == mode:
                return mode, "template"
            # expr(...), block(...)
            # parenthesis syntax for macro arguments  TODO: Python 3.9+: remove once we bump minimum Python to 3.9
            if type(ctxmanager) is Call and type(ctxmanager.func) is Name and ctxmanager.func.id == mode:
                return mode, "template"
        return False

    templates = []
    barenames = []
    new_block_body = []
    for stmt in block_body:
        # `let_syntax` mode (expand_inside): respect lexical scoping of nested `let_syntax`/`abbrev`
        expanded = False
        if expand_inside and (is_let_syntax(stmt) or is_abbrev(stmt)):
            stmt = dyn._macro_expander.visit(stmt)
            expanded = True

        stmt = _substitute_templates(templates, stmt)
        stmt = _substitute_barenames(barenames, stmt)
        binding_data = isbinding(stmt)
        if binding_data:
            name, args, value, mode = destructure_binding(stmt, *binding_data)

            check_stray_blocks_and_exprs(value)  # before expanding it!
            if expand_inside and not expanded:
                value = dyn._macro_expander.visit(value)

            target = templates if args else barenames
            target.append((name, args, value, mode))
        else:
            check_stray_blocks_and_exprs(stmt)  # before expanding it!
            if expand_inside and not expanded:
                stmt = dyn._macro_expander.visit(stmt)

            new_block_body.append(stmt)
    new_block_body = eliminate_ifones(new_block_body)
    if not new_block_body:
        raise SyntaxError("let_syntax: expected at least one statement beside definitions")  # pragma: no cover
    return new_block_body

# -----------------------------------------------------------------------------

def _get_subscript_args(tree):
    if sys.version_info >= (3, 9, 0):  # Python 3.9+: the Index wrapper is gone.
        theslice = tree.slice
    else:
        theslice = tree.slice.value
    if type(theslice) is Tuple:
        args = theslice.elts
    else:
        args = [theslice]
    return args

# x --> "x", []
# f[a, b, c] --> "f", ["a", "b", "c"]
# f(a, b, c) --> "f", ["a", "b", "c"]
def _analyze_lhs(tree):
    if type(tree) is Name:  # bare name
        name = tree.id
        args = []
    elif type(tree) is Subscript and type(tree.value) is Name:  # template f[x, ...]
        name = tree.value.id
        args = [a.id for a in _get_subscript_args(tree)]
    # parenthesis syntax for macro arguments  TODO: Python 3.9+: remove once we bump minimum Python to 3.9
    elif type(tree) is Call and type(tree.func) is Name:  # template f(x, ...)
        name = tree.func.id
        if any(type(a) is Starred for a in tree.args):  # *args (Python 3.5+)
            raise SyntaxError("in template, only positional parameters supported (no *args)")  # pragma: no cover
        args = [a.id for a in tree.args]
        if tree.keywords:
            raise SyntaxError("in template, only positional parameters supported (no named args or **kwargs)")  # pragma: no cover
    else:
        raise SyntaxError("expected a name (e.g. x) or a template (e.g. f(x, ...)) on the LHS")  # pragma: no cover
    return name, args

def _substitute_barename(name, value, tree, mode):
    def isthisname(tree):
        return type(tree) is Name and tree.id == name
    def splice(tree):
        class Splicer(ASTTransformer):
            def transform(self, tree):
                if is_captured_value(tree):
                    return tree  # don't recurse!
                def subst():
                    # Copy just to be on the safe side. Different instances may be
                    # edited differently by other macros expanded later.
                    return deepcopy(value)
                # discard Expr wrapper (identifying a statement position) at use site
                # when performing a block substitution
                if mode == "block" and type(tree) is Expr and isthisname(tree.value):
                    tree = subst()
                    return tree
                elif isthisname(tree):
                    if mode == "block":
                        raise SyntaxError(f"cannot substitute block '{name}' into expression position")  # pragma: no cover
                    tree = subst()
                    return self.generic_visit(tree)
                return self.generic_visit(tree)
        return Splicer().visit(tree)

    # If the new value is also bare name, perform the substitution (now as a string)
    # also in the name part of def and similar, to support human intuition of "renaming".
    if type(value) is Name:
        postproc = partial(rename, name, value.id)
    else:
        postproc = lambda x: x

    return postproc(splice(tree))

def _substitute_barenames(barenames, tree):
    for name, _noformalparams, value, mode in barenames:
        tree = _substitute_barename(name, value, tree, mode)
    return tree

def _substitute_templates(templates, tree):
    for name, formalparams, value, mode in templates:
        def isthisfunc(tree):
            if type(tree) is Subscript and type(tree.value) is Name and tree.value.id == name:
                return True
            # parenthesis syntax for macro arguments  TODO: Python 3.9+: remove once we bump minimum Python to 3.9
            if type(tree) is Call and type(tree.func) is Name and tree.func.id == name:
                return True
            return False
        def subst(tree):
            if type(tree) is Subscript:
                theargs = _get_subscript_args(tree)
            elif type(tree) is Call:
                theargs = tree.args
            else:
                assert False
            if len(theargs) != len(formalparams):
                raise SyntaxError(f"let_syntax template '{name}' expected {len(formalparams)} arguments, got {len(theargs)}")  # pragma: no cover
            # make a fresh deep copy of the RHS to avoid destroying the template.
            tree = deepcopy(value)  # expand the f itself in f[x, ...] or f(x, ...)
            for k, v in zip(formalparams, theargs):  # expand the x, ... in the expanded form of f
                # can't put statements in a Subscript or in a Call, so always treat args as expressions.
                tree = _substitute_barename(k, v, tree, "expr")
            return tree
        def splice(tree):
            class Splicer(ASTTransformer):
                def transform(self, tree):
                    if is_captured_value(tree):
                        return tree  # don't recurse!
                    # discard Expr wrapper (identifying a statement position) at use site
                    # when performing a block substitution
                    if mode == "block" and type(tree) is Expr and isthisfunc(tree.value):
                        tree = subst(tree.value)
                        return tree
                    elif isthisfunc(tree):
                        if mode == "block":
                            raise SyntaxError(f"cannot substitute block '{name}' into expression position")  # pragma: no cover
                        tree = subst(tree)
                        return self.generic_visit(tree)
                    return self.generic_visit(tree)
            return Splicer().visit(tree)
        tree = splice(tree)
    return tree
