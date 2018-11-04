#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# This is for introducing **syntactic** local bindings, i.e. simple code splicing
# at macro expansion time. If you're looking for regular run-time let et al. macros,
# see letdo.py.

from ast import Name, Call, Starred
from copy import deepcopy

from macropy.core.walkers import Walker

from unpythonic.syntax.letdo import implicit_do

def let_syntax_expr(bindings, body):
    body = implicit_do(body)  # support the extra bracket syntax
    if not bindings:
        return body
    templates, barenames = _split_bindings(bindings)
    def substitute_barename(name, value, tree):
        @Walker
        def splice(tree, **kw):
            if type(tree) is Name and tree.id == name:
                tree = value
            return tree
        return splice.recurse(tree)
    for name, formalparams, value in templates:
        @Walker
        def splice(tree, **kw):
            if type(tree) is Call and type(tree.func) is Name and tree.func.id == name:
                theargs = tree.args
                if len(theargs) != len(formalparams):
                    assert False, "let_syntax template '{}' expected {} arguments, got {}".format(name,
                                                                                                  len(formalparams),
                                                                                                  len(theargs))
                # make a fresh deep copy of the RHS to avoid destroying the template.
                tree = deepcopy(value)  # expand the f itself in f(x, ...)
                for k, v in zip(formalparams, theargs):  # expand the x, ... in the expanded form of f
                    tree = substitute_barename(k, v, tree)
            return tree
        body = splice.recurse(body)
    for name, _, value in barenames:
        body = substitute_barename(name, value, body)
    yield body  # first-pass macro (outside in) so that we can e.g. let_syntax((a, ast_literal))[...]

# TODO: implement a block version; should probably support some form of "with" to allow substituting statements.
#def let_syntax_block(bindings, block_body):
#    pass

# -----------------------------------------------------------------------------

def _split_bindings(bindings):  # bindings: sequence of ast.Tuple: (k1, v1), (k2, v2), ..., (kn, vn)
    names = set()
    templates = []
    barenames = []
    for line in bindings:
        k, v = line.elts
        if type(k) is Name:
            name = k.id
            args = []
        elif type(k) is Call and type(k.func) is Name:  # simple templating f(x, ...)
            name = k.func.id
            if any(type(a) is Starred for a in k.args):  # *args (Python 3.5+)
                assert False, "in template, only positional slots supported (no *args)"
            args = [a.id for a in k.args]
            if k.keywords:
                assert False, "in template, only positional slots supported (no named args or **kwargs)"
        else:
            assert False, "expected a name (e.g. x) or a template (e.g. f(x, ...)) on the LHS"
        if name in names:
            assert False, "duplicate '{}'; names defined in the same let_syntax must be unique".format(name)
        names.add(name)
        target = templates if args else barenames
        target.append((name, args, v))
    return templates, barenames
