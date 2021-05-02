# -*- coding: utf-8 -*-

# This is for introducing **syntactic** local bindings, i.e. simple code splicing
# at macro expansion time. If you're looking for regular run-time let et al. macros,
# see letdo.py.

__all__ = ["let_syntax", "abbrev", "expr", "block"]

from mcpyrate.quotes import macros, q, a  # noqa: F401

from ast import (Name, Call, Starred, Expr, With,
                 FunctionDef, AsyncFunctionDef, ClassDef, Attribute)
from copy import deepcopy

from mcpyrate import parametricmacro
from mcpyrate.quotes import is_captured_value
from mcpyrate.walkers import ASTTransformer

from .letdo import _implicit_do, _destructure_and_apply_let
from .util import eliminate_ifones

# --------------------------------------------------------------------------------
# Macro interface

# TODO: change the block() construct to block[], for syntactic consistency
@parametricmacro
def let_syntax(tree, *, args, syntax, expander, **kw):
    """[syntax, expr/block] Introduce local **syntactic** bindings.

    **Expression variant**::

        let_syntax[(lhs, rhs), ...][body]
        let_syntax[(lhs, rhs), ...][[body0, ...]]

    Alternative haskelly syntax::

        let_syntax[((lhs, rhs), ...) in body]
        let_syntax[((lhs, rhs), ...) in [body0, ...]]

        let_syntax[body, where((lhs, rhs), ...)]
        let_syntax[[body0, ...], where((lhs, rhs), ...)]

    **Block variant**::

        with let_syntax:
            with block as xs:          # capture a block of statements - bare name
                ...
            with block(a, ...) as xs:  # capture a block of statements - template
                ...
            with expr as x:            # capture a single expression - bare name
                ...
            with expr(a, ...) as x:    # capture a single expression - template
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
    use the function-call syntax at the use site).

    In the body of the ``let_syntax``, a template is used like a function call.
    Just like in an actual function call, when the template is substituted,
    any instances of its formal parameters on its RHS get replaced by the
    argument values from the "call" site; but ``let_syntax`` performs this
    at macro-expansion time.

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
        raise SyntaxError("let_syntax is an expr and block macro only")

    tree = expander.visit(tree)

    if syntax == "expr":
        return _destructure_and_apply_let(tree, args, expander, _let_syntax_expr, allow_call_in_name_position=True)
    else:  # syntax == "block":
        return _let_syntax_block(block_body=tree)

@parametricmacro
def abbrev(tree, *, args, syntax, expander, **kw):
    """[syntax, expr/block] Exactly like ``let_syntax``, but expands outside in.

    Because this variant expands before any macros in the body, it can locally
    rename other macros, e.g.::

        abbrev[(m, macrowithverylongname)][
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
        raise SyntaxError("abbrev is an expr and block macro only")

    # DON'T expand inner macro invocations first - outside-in ordering is the default, so we simply do nothing.

    if syntax == "expr":
        return _destructure_and_apply_let(tree, args, expander, _let_syntax_expr, allow_call_in_name_position=True)
    else:
        return _let_syntax_block(block_body=tree)

# TODO: convert to mcpyrate magic variable
class expr:
    """[syntax] Magic identifier for ``with expr:`` inside a ``with let_syntax:``."""
    def __repr__(self):  # in case one of these ends up somewhere at runtime
        return "<let syntax 'with expr:'>"  # pragma: no cover
    def __call__(self, tree, **kw):  # make `expr` look like a macro
        pass
expr = expr()

# TODO: convert to mcpyrate magic variable
class block:
    """[syntax] Magic identifier for ``with block:`` inside a ``with let_syntax:``."""
    def __repr__(self):  # in case one of these ends up somewhere at runtime
        return "<let_syntax 'with block:'>"  # pragma: no cover
    def __call__(self, tree, **kw):  # make `block` look like a macro
        pass
block = block()

# --------------------------------------------------------------------------------
# Syntax transformers

def _let_syntax_expr(bindings, body):  # bindings: sequence of ast.Tuple: (k1, v1), (k2, v2), ..., (kn, vn)
    body = _implicit_do(body)  # support the extra bracket syntax
    if not bindings:
        # Optimize out a `let_syntax` with no bindings. The macro layer cannot trigger
        # this case, because our syntaxes always require at least one binding.
        # So this check is here just to protect against use with no bindings directly
        # from other syntax transformers, which in theory could attempt anything.
        #
        # TODO: update this comment for mcpyrate
        # The reason the macro layer never calls us with no bindings is technical.
        # In the macro interface, with no bindings, the macro's `args` are `()`
        # whether it was invoked as `let_syntax()[...]` or just `let_syntax[...]`.
        # Thus, there is no way to distinguish, in the macro layer, between these
        # two. We can't use `UnexpandedLetView` to do the dirty work of AST
        # analysis, because the macro expander does too much automatically: in the macro
        # layer, `tree` is only the part inside the brackets. So we really
        # can't see whether the part outside the brackets was a Call with no
        # arguments, or just a Name - both cases get treated exactly the same,
        # as a macro invocation with empty `args`.
        #
        # The latter form, `let_syntax[...]`, is used by the haskelly syntax
        # `let_syntax[(...) in ...]`, `let_syntax[..., where(...)]` - and in
        # these cases, both the bindings and the body reside inside the brackets.
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

    register_bindings()
    body = _substitute_templates(templates, body)
    body = _substitute_barenames(barenames, body)
    return body

# block version:
#
# with let_syntax:
#     with block as xs:
#         ...
#     with block(a, ...) as xs:
#         ...
#     with expr as x:
#         ...
#     with expr(a, ...) as x:
#         ...
#     body0
#     ...
#
def _let_syntax_block(block_body):
    names_seen = set()
    templates = []
    barenames = []
    def register_binding(withstmt, mode, kind):
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
        target = templates if args else barenames
        target.append((name, args, value, mode))

    def isbinding(tree):
        for mode in ("block", "expr"):
            if not (type(tree) is With and len(tree.items) == 1):
                continue
            ctxmanager = tree.items[0].context_expr
            if type(ctxmanager) is Name and ctxmanager.id == mode:
                return mode, "barename"
            if type(ctxmanager) is Call and type(ctxmanager.func) is Name and ctxmanager.func.id == mode:
                return mode, "template"
        return False

    new_block_body = []
    for stmt in block_body:
        stmt = _substitute_templates(templates, stmt)
        stmt = _substitute_barenames(barenames, stmt)
        binding_data = isbinding(stmt)
        if binding_data:
            register_binding(stmt, *binding_data)
        else:
            new_block_body.append(stmt)
    new_block_body = eliminate_ifones(new_block_body)
    if not new_block_body:
        raise SyntaxError("let_syntax: expected at least one statement beside definitions")  # pragma: no cover
    return new_block_body

# -----------------------------------------------------------------------------

def _analyze_lhs(tree):
    if type(tree) is Name:  # bare name
        name = tree.id
        args = []
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
                        raise SyntaxError("cannot substitute a block into expression position")  # pragma: no cover
                    tree = subst()
                    return self.generic_visit(tree)
                return self.generic_visit(tree)
        return Splicer().visit(tree)

    # if the new value is also bare name, perform the substitution (now as a string)
    # also in the name part of def and similar, to support human intuition of "renaming"
    # TODO: use `mcpyrate.utils.rename`, it was designed for things like this?
    if type(value) is Name:
        newname = value.id
        def splice_barestring(tree):
            class BarestringSplicer(ASTTransformer):
                def transform(self, tree):
                    if is_captured_value(tree):
                        return tree  # don't recurse!
                    if type(tree) in (FunctionDef, AsyncFunctionDef, ClassDef):
                        if tree.name == name:
                            tree.name = newname
                    elif type(tree) is Attribute:
                        if tree.attr == name:
                            tree.attr = newname
                    return self.generic_visit(tree)
            return BarestringSplicer().visit(tree)
        postproc = splice_barestring
    else:
        postproc = lambda x: x

    return postproc(splice(tree))

def _substitute_barenames(barenames, tree):
    for name, _, value, mode in barenames:
        tree = _substitute_barename(name, value, tree, mode)
    return tree

def _substitute_templates(templates, tree):
    for name, formalparams, value, mode in templates:
        def isthisfunc(tree):
            return type(tree) is Call and type(tree.func) is Name and tree.func.id == name
        def subst(tree):
            theargs = tree.args
            if len(theargs) != len(formalparams):
                raise SyntaxError(f"let_syntax template '{name}' expected {len(formalparams)} arguments, got {len(theargs)}")  # pragma: no cover
            # make a fresh deep copy of the RHS to avoid destroying the template.
            tree = deepcopy(value)  # expand the f itself in f(x, ...)
            for k, v in zip(formalparams, theargs):  # expand the x, ... in the expanded form of f
                # can't put statements in a Call, so always treat args as expressions.
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
                            raise SyntaxError("cannot substitute a block into expression position")  # pragma: no cover
                        tree = subst(tree)
                        return self.generic_visit(tree)
                    return self.generic_visit(tree)
            return Splicer().visit(tree)
        tree = splice(tree)
    return tree
