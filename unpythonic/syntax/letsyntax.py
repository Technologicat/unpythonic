# -*- coding: utf-8 -*-

# This is for introducing **syntactic** local bindings, i.e. simple code splicing
# at macro expansion time. If you're looking for regular run-time let et al. macros,
# see letdo.py.

from mcpyrate.quotes import macros, q, a  # noqa: F401

from ast import (Name, Call, Starred, Expr, With,
                 FunctionDef, AsyncFunctionDef, ClassDef, Attribute)
from copy import deepcopy

from mcpyrate.quotes import is_captured_value
from mcpyrate.walkers import ASTTransformer

from .letdo import implicit_do
from .util import eliminate_ifones

def let_syntax_expr(bindings, body):  # bindings: sequence of ast.Tuple: (k1, v1), (k2, v2), ..., (kn, vn)
    body = implicit_do(body)  # support the extra bracket syntax
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

# -----------------------------------------------------------------------------

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
def let_syntax_block(block_body):
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

# TODO: convert to mcpyrate magic variable
class block:
    """[syntax] Magic identifier for ``with block:`` inside a ``with let_syntax:``."""
    def __repr__(self):  # in case one of these ends up somewhere at runtime
        return "<let_syntax 'with block:'>"  # pragma: no cover
    def __call__(self, tree, **kw):  # make `block` look like a macro
        pass
block = block()

# TODO: convert to mcpyrate magic variable
class expr:
    """[syntax] Magic identifier for ``with expr:`` inside a ``with let_syntax:``."""
    def __repr__(self):  # in case one of these ends up somewhere at runtime
        return "<let syntax 'with expr:'>"  # pragma: no cover
    def __call__(self, tree, **kw):  # make `expr` look like a macro
        pass
expr = expr()

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
