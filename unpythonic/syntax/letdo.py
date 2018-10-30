# -*- coding: utf-8 -*-
"""Local bindings (let), imperative code in expression position (do)."""

# Let constructs are implemented as sugar around unpythonic.lispylet.
#
# We take this approach because letrec needs assignment (must create
# placeholder bindings, then update them with the real values)...
# but in Python, assignment is a statement. As a bonus, we get
# assignment support for let and letseq, too.

from functools import partial

from ast import Call, Name, Attribute, \
                Tuple, List, \
                BinOp, LShift, \
                FunctionDef, Return, \
                arguments, arg, \
                Load, \
                copy_location
from unpythonic.syntax.astcompat import AsyncFunctionDef

from macropy.core.quotes import macros, q, u, ast_literal, name
from macropy.core.hquotes import macros, hq
from macropy.core.walkers import Walker

from unpythonic.lispylet import let as letf, letrec as letrecf, _dlet as dletf, _blet as bletf
from unpythonic.seq import begin as beginf, do as dof

from unpythonic.syntax.util import isx
from unpythonic.syntax.scoping import scoped_walker

def let(bindings, body, gen_sym):
    return _letimpl(bindings, body, gen_sym, "let")

def letseq(bindings, body, gen_sym):
    if not bindings:
        return body
    first, *rest = bindings
    return let([first], letseq(rest, body, gen_sym), gen_sym)

def letrec(bindings, body, gen_sym):
    return _letimpl(bindings, body, gen_sym, "letrec")

def _letimpl(bindings, body, gen_sym, mode):
    """bindings: sequence of ast.Tuple: (k1, v1), (k2, v2), ..., (kn, vn)"""
    assert mode in ("let", "letrec")

    body = implicit_do(body, gen_sym)
    if not bindings:
        return body
    names, values = zip(*[b.elts for b in bindings])  # --> (k1, ..., kn), (v1, ..., vn)
    names = [k.id for k in names]  # any duplicates will be caught by env at run-time

    e = gen_sym("e")
    envset = Attribute(value=q[name[e]], attr="set", ctx=Load())

    t = partial(letlike_transform, envname=e, lhsnames=names, rhsnames=names, setter=envset)
    if mode == "letrec":
        values = [t(rhs) for rhs in values]  # RHSs of bindings
    body = t(body)

    letter = letf if mode == "let" else letrecf
    bindings = [q[(u[k], ast_literal[v])] for k, v in zip(names, values)]
    newtree = hq[letter((ast_literal[bindings],), ast_literal[body])]
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

def isenvassign(tree):
    """Detect ``name << value`` syntax to assign variables in an unpythonic ``env``."""
    return type(tree) is BinOp and type(tree.op) is LShift and type(tree.left) is Name
def envassign_name(tree):  # rackety accessors
    """Get the name part of an envassign, as ``str``."""
    return tree.left.id
def envassign_value(tree):
    """Get the value part of an envassign, as an AST."""
    return tree.right

def transform_envassignment(tree, lhsnames, envset):
    """x << val --> e.set('x', val)  (for names bound in this environment)"""
    def t(tree, shadowed):
        if isenvassign(tree):
            varname = envassign_name(tree)
            if varname in lhsnames and varname not in shadowed:
                value = envassign_value(tree)
                return q[ast_literal[envset](u[varname], ast_literal[value])]
        return tree
    return scoped_walker.recurse(tree, callback=t)

def transform_name(tree, rhsnames, envname):
    """x --> e.x  (in load context; for names bound in this environment)"""
    def t(tree, shadowed):
        # e.anything is already ok, but x.foo (Attribute that contains a Name "x")
        # should transform to e.x.foo.
        if type(tree) is Attribute and type(tree.value) is Name and tree.value.id == envname:
            pass
        # nested lets work, because once x --> e.x, the final "x" is no longer a Name,
        # but an attr="x" of an Attribute node.
        elif type(tree) is Name and tree.id in rhsnames and tree.id not in shadowed:
            hasctx = hasattr(tree, "ctx")  # macro-created nodes might not have a ctx.
            if hasctx and type(tree.ctx) is not Load:
                return tree
            ctx = tree.ctx if hasctx else None  # let MacroPy fix it if needed
            return Attribute(value=q[name[envname]], attr=tree.id, ctx=ctx)
        return tree
    return scoped_walker.recurse(tree, callback=t)

def envwrap(tree, envname):
    """... -> lambda e: ..."""
    lam = q[lambda: ast_literal[tree]]
    lam.args.args = [arg(arg=envname)]  # lambda e44: ...
    return lam

# -----------------------------------------------------------------------------
# Decorator versions, for "let over def".

def dlet(bindings, fdef, gen_sym):
    return _dletimpl(bindings, fdef, gen_sym, "let", "decorate")

def dletseq(bindings, fdef, gen_sym):
    return _dletseqimpl(bindings, fdef, gen_sym, "decorate")

def dletrec(bindings, fdef, gen_sym):
    return _dletimpl(bindings, fdef, gen_sym, "letrec", "decorate")

def blet(bindings, fdef, gen_sym):
    return _dletimpl(bindings, fdef, gen_sym, "let", "call")

def bletseq(bindings, fdef, gen_sym):
    return _dletseqimpl(bindings, fdef, gen_sym, "call")

def bletrec(bindings, fdef, gen_sym):
    return _dletimpl(bindings, fdef, gen_sym, "letrec", "call")

# Very similar to _letimpl, but perhaps more readable to keep these separate.
def _dletimpl(bindings, fdef, gen_sym, mode, kind):
    assert mode in ("let", "letrec")
    assert kind in ("decorate", "call")
    if type(fdef) not in (FunctionDef, AsyncFunctionDef):
        assert False, "Expected a function definition to decorate"
    if not bindings:
        return fdef

    names, values = zip(*[b.elts for b in bindings])  # --> (k1, ..., kn), (v1, ..., vn)
    names = [k.id for k in names]  # any duplicates will be caught by env at run-time

    e = gen_sym("e")
    envset = Attribute(value=q[name[e]], attr="set", ctx=Load())

    t1 = partial(letlike_transform, envname=e, lhsnames=names, rhsnames=names, setter=envset)
    t2 = partial(t1, dowrap=False)
    if mode == "letrec":
        values = [t1(rhs) for rhs in values]
    fdef = t2(fdef)

    letter = dletf if kind == "decorate" else bletf
    bindings = [q[(u[k], ast_literal[v])] for k, v in zip(names, values)]
    fdef.decorator_list = fdef.decorator_list + [hq[letter((ast_literal[bindings],), mode=u[mode], _envname=u[e])]]
    fdef.args.kwonlyargs = fdef.args.kwonlyargs + [arg(arg=e)]
    fdef.args.kw_defaults = fdef.args.kw_defaults + [None]
    return fdef

def _dletseqimpl(bindings, fdef, gen_sym, kind):
    # What we want:
    #
    # @dletseq((x, 1),
    #          (x, x+1),
    #          (x, x+2))
    # def g(*args, **kwargs):
    #     return x
    # assert g() == 4
    #
    # -->
    #
    # @dlet((x, 1))
    # def g(*args, **kwargs, e1):  # original args from tree go to the outermost def
    #   @dlet((x, x+1))
    #   def g2(*, e2):
    #       @dlet((x, x+2))
    #       def g3(*, e3):         # expansion proceeds from inside out
    #           return e3.x
    #       return g3()
    #   return g2()
    # assert g() == 4
    #
    assert kind in ("decorate", "call")
    if type(fdef) not in (FunctionDef, AsyncFunctionDef):
        assert False, "Expected a function definition to decorate"
    if not bindings:
        return fdef

    userargs = fdef.args  # original arguments to the def
    fname = fdef.name
    noargs = arguments(args=[], kwonlyargs=[], vararg=None, kwarg=None,
                       defaults=[], kw_defaults=[])
    iname = gen_sym("{}_inner".format(fname))
    fdef.args = noargs
    fdef.name = iname

    *rest, last = bindings
    dletter = dlet if kind == "decorate" else blet
    innerdef = dletter([last], fdef, gen_sym)

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
    ret = Return(value=q[name[iname]()]) if kind == "decorate" else Return(value=q[name[iname]])
    outer = FunctionDef(name=fname, args=userargs,
                        body=[innerdef, ret],
                        decorator_list=[],
                        returns=None)  # no return type annotation
    return _dletseqimpl(rest, outer, gen_sym, kind)

# -----------------------------------------------------------------------------
# Imperative code in expresssion position. Uses the "let" machinery.

def do(tree, gen_sym):
    if type(tree) not in (Tuple, List):
        assert False, "do body: expected a sequence of comma-separated expressions"

    e = gen_sym("e")
    # We must use env.__setattr__ to allow defining new names; env.set only rebinds.
    # But to keep assignments chainable, the assignment must return the value.
    # Use a let[] to avoid recomputing it (could be expensive and/or have side effects).
    # So we need:
    #     lambda k, expr: let((v, expr))[begin(e.__setattr__(k, v), v)]
    # ...but with gensym'd arg names to avoid spurious shadowing inside expr.
    # TODO: cache the setter in e? Or even provide a new method in env that does this?
    sa = Attribute(value=q[name[e]], attr="__setattr__", ctx=Load())
    k = gen_sym("k")
    expr = gen_sym("expr")
    envset = q[lambda: None]
    envset.args.args = [arg(arg=k), arg(arg=expr)]
    letbody = hq[beginf(ast_literal[sa](name[k], name["v"]), name["v"])]
    letbody = copy_location(letbody, tree)
    envset.body = let([q[(name["v"], name[expr])]], letbody, gen_sym)

    def islocaldef(tree):
        return type(tree) is Call and type(tree.func) is Name and tree.func.id == "localdef"
    @Walker
    def find_localdefs(tree, collect, **kw):
        if islocaldef(tree):
            if len(tree.args) != 1:
                assert False, "localdef(...) must have exactly one positional argument"
            expr = tree.args[0]
            if not isenvassign(expr):
                assert False, "localdef(...) argument must be of the form 'name << value'"
            collect(envassign_name(expr))
            return expr  # localdef(...) -> ..., the localdef has done its job
        return tree

    # a localdef starts taking effect on the line where it appears
    names = []
    lines = []
    for expr in tree.elts:
        expr, newnames = find_localdefs.recurse_collect(expr)
        if newnames:
            if any(x in names for x in newnames):
                assert False, "localdef names must be unique in the same do"
        # The envassignment transform (LHS) needs also "newnames", whereas
        # the name transform (RHS) should use the previous bindings, so that
        # the new binding takes effect starting from the **next** doitem.
        expr = letlike_transform(expr, e, names + newnames, names, envset)
        names = names + newnames
        lines.append(expr)
    return hq[dof(ast_literal[lines])]

def do0(tree, gen_sym):
    if type(tree) not in (Tuple, List):
        assert False, "do0 body: expected a sequence of comma-separated expressions"
    elts = tree.elts
    newelts = []
    newelts.append(q[name["localdef"](name["_do0_result"] << (ast_literal[elts[0]]))])
    newelts.extend(elts[1:])
    newelts.append(q[name["_do0_result"]])
#    newtree = q[(ast_literal[newelts],)]  # TODO: doesn't work, missing lineno
    newtree = Tuple(elts=newelts, lineno=tree.lineno, col_offset=tree.col_offset)
    return do(newtree, gen_sym)  # do0[] is also just a do[]

def implicit_do(tree, gen_sym):
    """Allow a sequence of expressions in expression position.

    Apply ``do[]`` if ``tree`` is a ``List``, otherwise return ``tree`` as-is.

    Hence, in client code, to represent a sequence of expressions, use brackets::

        [expr0, ...]

    To represent a single literal list where ``implicit_do`` is in use, use an
    extra set of brackets::

        [[1, 2, 3]]

    The outer brackets enable multiple-expression mode, and the inner brackets
    are then interpreted as a list.
    """
    return do(tree, gen_sym) if type(tree) is List else tree
