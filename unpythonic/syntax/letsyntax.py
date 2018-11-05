# -*- coding: utf-8 -*-

# This is for introducing **syntactic** local bindings, i.e. simple code splicing
# at macro expansion time. If you're looking for regular run-time let et al. macros,
# see letdo.py.

from functools import partial
from copy import deepcopy
from ast import Name, Call, Starred, If, Num, Expr

from macropy.core.walkers import Walker

from unpythonic.syntax.util import isnamedwith
from unpythonic.syntax.letdo import implicit_do

def let_syntax_expr(bindings, body):  # bindings: sequence of ast.Tuple: (k1, v1), (k2, v2), ..., (kn, vn)
    body = implicit_do(body)  # support the extra bracket syntax
    if not bindings:
        return body

    names_seen = set()
    templates = []
    barenames = []
    def register_bindings():
        for line in bindings:
            key, value = line.elts
            name, args = _analyze_lhs(key)
            if name in names_seen:
                assert False, "duplicate '{}'; names defined in the same let_syntax expr must be unique".format(name)
            names_seen.add(name)
            target = templates if args else barenames
            target.append((name, args, value, "expr"))

    register_bindings()
    body = _substitute_templates(templates, body)
    body = _substitute_barenames(barenames, body)
    yield body  # first-pass macro (outside in) so that we can e.g. let_syntax((a, ast_literal))[...]

# -----------------------------------------------------------------------------

# block version:
#
# with let_syntax:
#     with block as xs:  # capture a block of statements
#         ...
#     with block as fs(a, ...):
#         ...
#     with expr as x:    # capture a single expression
#         ...            # can explicitly use do[] here if necessary
#     with expr as f(a, ...):
#         ...
#     body0
#     ...
#
def let_syntax_block(block_body):
    names_seen = set()
    templates = []
    barenames = []
    def register_binding(withstmt, mode):  # "with block:" or "with expr:"
        optvars = withstmt.items[0].optional_vars
        if not optvars:
            assert False, "'with {}:': expected a name (e.g. x) or a template (e.g. f(x, ...)) as the as-part".format(mode)
        name, args = _analyze_lhs(optvars)
        if name in names_seen:
            assert False, "duplicate '{}'; as-parts in the same let_syntax block must be unique".format(name)
        if mode == "block":
            value = If(test=Num(n=1),
                       body=withstmt.body,
                       orelse=[],
                       lineno=stmt.lineno, col_offset=stmt.col_offset)
        else: # mode == "expr":
            if len(withstmt.body) != 1:
                assert False, "'with expr:' expected a one-item body (use a do[] if need more)"
            theexpr = withstmt.body[0]
            if type(theexpr) is not Expr:
                assert False, "'with expr:' expected an expression in body, got a statement"
            value = theexpr.value  # discard Expr wrapper in definition
        names_seen.add(name)
        target = templates if args else barenames
        target.append((name, args, value, mode))

    iswithblock = partial(isnamedwith, name="block")  # "with block as ...:"
    iswithexpr = partial(isnamedwith, name="expr")    # "with expr as ...:"
    new_block_body = []
    for stmt in block_body:
        if iswithblock(stmt):
            register_binding(stmt, "block")
        elif iswithexpr(stmt):
            register_binding(stmt, "expr")
        else:
            stmt = _substitute_templates(templates, stmt)
            stmt = _substitute_barenames(barenames, stmt)
            new_block_body.append(stmt)
    yield new_block_body

class block:
    """[syntax] Magic identifier for ``with block:`` inside a ``with let_syntax:``."""
    def __repr__(self):  # in case one of these ends up somewhere at runtime
        return "<let_syntax 'with block:'>"
block = block()

class expr:
    """[syntax] Magic identifier for ``with expr:`` inside a ``with let_syntax:``."""
    def __repr__(self):  # in case one of these ends up somewhere at runtime
        return "<let syntax 'with expr:'>"
expr = expr()

# -----------------------------------------------------------------------------

def _analyze_lhs(tree):
    if type(tree) is Name:  # bare name
        name = tree.id
        args = []
    elif type(tree) is Call and type(tree.func) is Name:  # template f(x, ...)
        name = tree.func.id
        if any(type(a) is Starred for a in tree.args):  # *args (Python 3.5+)
            assert False, "in template, only positional parameters supported (no *args)"
        args = [a.id for a in tree.args]
        if tree.keywords:
            assert False, "in template, only positional parameters supported (no named args or **kwargs)"
    else:
        assert False, "expected a name (e.g. x) or a template (e.g. f(x, ...)) on the LHS"
    return name, args

def _substitute_barename(name, value, tree, mode):
    def isthisname(tree):
        return type(tree) is Name and tree.id == name
    @Walker
    def splice(tree, *, stop, **kw):
        # discard Expr wrapper at use site for a block substitution
        if mode == "block" and type(tree) is Expr and isthisname(tree.value):
            stop()
            tree = splice.recurse(tree.value)
        elif isthisname(tree):
            # Copy just to be on the safe side. Different instances may be
            # edited differently by other macros expanded later.
            tree = deepcopy(value)
        return tree
    return splice.recurse(tree)

def _substitute_barenames(barenames, tree):
    for name, _, value, mode in barenames:
        tree = _substitute_barename(name, value, tree, mode)
    return tree

def _substitute_templates(templates, tree):
    for name, formalparams, value, mode in templates:
        def isthisfunc(tree):
            return type(tree) is Call and type(tree.func) is Name and tree.func.id == name
        @Walker
        def splice(tree, *, stop, **kw):
            # discard Expr wrapper at use site for a block substitution
            if mode == "block" and type(tree) is Expr and isthisfunc(tree.value):
                stop()
                tree = splice.recurse(tree.value)
            elif isthisfunc(tree):
                theargs = tree.args
                if len(theargs) != len(formalparams):
                    assert False, "let_syntax template '{}' expected {} arguments, got {}".format(name,
                                                                                                  len(formalparams),
                                                                                                  len(theargs))
                # make a fresh deep copy of the RHS to avoid destroying the template.
                tree = deepcopy(value)  # expand the f itself in f(x, ...)
                for k, v in zip(formalparams, theargs):  # expand the x, ... in the expanded form of f
                    # TODO: Currently all args of a block substitution are handled in block mode (as statements).
                    # TODO: Some configurability may be needed here.
                    tree = _substitute_barename(k, v, tree, mode)
            return tree
        tree = splice.recurse(tree)
    return tree
