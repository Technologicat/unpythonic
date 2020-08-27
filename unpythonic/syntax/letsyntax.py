# -*- coding: utf-8 -*-

# This is for introducing **syntactic** local bindings, i.e. simple code splicing
# at macro expansion time. If you're looking for regular run-time let et al. macros,
# see letdo.py.

from copy import deepcopy
from ast import (Name, Call, Starred, If, Num, Expr, With,
                 FunctionDef, ClassDef, Attribute)
from .astcompat import AsyncFunctionDef

from macropy.core.walkers import Walker

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
        # The reason the macro layer never calls us with no bindings is technical.
        # In the macro interface, with no bindings, the macro's `args` are `()`
        # whether it was invoked as `let_syntax()[...]` or just `let_syntax[...]`.
        # Thus, there is no way to distinguish, in the macro layer, between these
        # two. We can't use `UnexpandedLetView` to do the dirty work of AST
        # analysis, because MacroPy does too much automatically: in the macro
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
                assert False, "duplicate '{}'; names defined in the same let_syntax expr must be unique".format(name)  # pragma: no cover
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
            assert False, "'with {}:': expected an as-part".format(mode)  # pragma: no cover
        if type(optvars) is not Name:
            assert False, "'with {}:': expected exactly one name in the as-part".format(mode)  # pragma: no cover

        name = optvars.id
        if name in names_seen:
            assert False, "duplicate '{}'; as-parts in the same let_syntax block must be unique".format(name)  # pragma: no cover

        if kind == "template":
            _, args = _analyze_lhs(ctxmanager)  # syntactic limitation, can't place formal parameter list on the as-part
        else:  # kind == "barename":
            args = []

        if mode == "block":
            value = If(test=Num(n=1),  # TODO: Python 3.8+: ast.Constant, no ast.Num
                       body=withstmt.body,
                       orelse=[],
                       lineno=stmt.lineno, col_offset=stmt.col_offset)
        else:  # mode == "expr":
            if len(withstmt.body) != 1:
                assert False, "'with expr:' expected a one-item body (use a do[] if need more)"  # pragma: no cover
            theexpr = withstmt.body[0]
            if type(theexpr) is not Expr:
                assert False, "'with expr:' expected an expression body, got a statement"  # pragma: no cover
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
        assert False, "let_syntax: expected at least one statement beside definitions"  # pragma: no cover
    return new_block_body

class block:
    """[syntax] Magic identifier for ``with block:`` inside a ``with let_syntax:``."""
    def __repr__(self):  # in case one of these ends up somewhere at runtime
        return "<let_syntax 'with block:'>"  # pragma: no cover
block = block()

class expr:
    """[syntax] Magic identifier for ``with expr:`` inside a ``with let_syntax:``."""
    def __repr__(self):  # in case one of these ends up somewhere at runtime
        return "<let syntax 'with expr:'>"  # pragma: no cover
expr = expr()

# -----------------------------------------------------------------------------

def _analyze_lhs(tree):
    if type(tree) is Name:  # bare name
        name = tree.id
        args = []
    elif type(tree) is Call and type(tree.func) is Name:  # template f(x, ...)
        name = tree.func.id
        if any(type(a) is Starred for a in tree.args):  # *args (Python 3.5+)
            assert False, "in template, only positional parameters supported (no *args)"  # pragma: no cover
        args = [a.id for a in tree.args]
        if tree.keywords:
            assert False, "in template, only positional parameters supported (no named args or **kwargs)"  # pragma: no cover
        # Python 3.4
        if hasattr(tree, "starargs") and tree.starargs is not None:
            assert False, "in template, only positional parameters supported (no *args)"  # pragma: no cover
        if hasattr(tree, "kwargs") and tree.kwargs is not None:
            assert False, "in template, only positional parameters supported (no named args or **kwargs)"  # pragma: no cover
    else:
        assert False, "expected a name (e.g. x) or a template (e.g. f(x, ...)) on the LHS"  # pragma: no cover
    return name, args

def _substitute_barename(name, value, tree, mode):
    def isthisname(tree):
        return type(tree) is Name and tree.id == name
    @Walker
    def splice(tree, *, stop, **kw):
        def subst():
            # Copy just to be on the safe side. Different instances may be
            # edited differently by other macros expanded later.
            return deepcopy(value)
        # discard Expr wrapper (identifying a statement position) at use site
        # when performing a block substitution
        if mode == "block" and type(tree) is Expr and isthisname(tree.value):
            stop()
            tree = subst()
        elif isthisname(tree):
            if mode == "block":
                assert False, "cannot substitute a block into expression position"  # pragma: no cover
            tree = subst()
        return tree

    # if the new value is also bare name, perform the substitution (now as a string)
    # also in the name part of def and similar, to support human intuition of "renaming"
    if type(value) is Name:
        newname = value.id
        @Walker
        def splice_barestring(tree, *, stop, **kw):
            if type(tree) in (FunctionDef, AsyncFunctionDef, ClassDef):
                if tree.name == name:
                    tree.name = newname
            elif type(tree) is Attribute:
                if tree.attr == name:
                    tree.attr = newname
            return tree
        postproc = splice_barestring.recurse
    else:
        postproc = lambda x: x

    return postproc(splice.recurse(tree))

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
                assert False, "let_syntax template '{}' expected {} arguments, got {}".format(name,  # pragma: no cover
                                                                                              len(formalparams),
                                                                                              len(theargs))
            # make a fresh deep copy of the RHS to avoid destroying the template.
            tree = deepcopy(value)  # expand the f itself in f(x, ...)
            for k, v in zip(formalparams, theargs):  # expand the x, ... in the expanded form of f
                # can't put statements in a Call, so always treat args as expressions.
                tree = _substitute_barename(k, v, tree, "expr")
            return tree
        @Walker
        def splice(tree, *, stop, **kw):
            # discard Expr wrapper (identifying a statement position) at use site
            # when performing a block substitution
            if mode == "block" and type(tree) is Expr and isthisfunc(tree.value):
                stop()
                tree = subst(tree.value)
            elif isthisfunc(tree):
                if mode == "block":
                    assert False, "cannot substitute a block into expression position"  # pragma: no cover
                tree = subst(tree)
            return tree
        tree = splice.recurse(tree)
    return tree
