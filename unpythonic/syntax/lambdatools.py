# -*- coding: utf-8 -*-
"""Lambdas with multiple expressions, local variables, and a name."""

__all__ = ["multilambda",
           "namedlambda",
           "f",
           "quicklambda",
           "envify"]

from ast import (Lambda, Name, Assign, Subscript, Call, FunctionDef,
                 AsyncFunctionDef, Attribute, keyword, Dict, Constant, arg)
from copy import deepcopy

from mcpyrate.quotes import macros, q, u, n, a, h  # noqa: F401

from mcpyrate import gensym
from mcpyrate.expander import MacroExpander
from mcpyrate.quotes import is_captured_value
from mcpyrate.splicing import splice_expression
from mcpyrate.utils import extract_bindings
from mcpyrate.walkers import ASTTransformer

from ..dynassign import dyn
from ..misc import namelambda
from ..env import env

from .astcompat import getconstant, Str, NamedExpr
from .letdo import _implicit_do, _do
from .letdoutil import islet, isenvassign, UnexpandedLetView, UnexpandedEnvAssignView, ExpandedDoView
from .nameutil import getname
from .util import (is_decorated_lambda, isx, has_deco,
                   destructure_decorated_lambda, detect_lambda)

# --------------------------------------------------------------------------------
# Macro interface

def multilambda(tree, *, syntax, expander, **kw):
    """[syntax, block] Supercharge your lambdas: multiple expressions, local variables.

    For all ``lambda`` lexically inside the ``with multilambda`` block,
    ``[...]`` denotes a multiple-expression body with an implicit ``do``::

        lambda ...: [expr0, ...] --> lambda ...: do[expr0, ...]

    Only the outermost set of brackets around the body of a ``lambda`` denotes
    a multi-expression body; the rest are interpreted as lists, as usual.

    Examples::

        with multilambda:
            echo = lambda x: [print(x), x]
            assert echo("hi there") == "hi there"

            count = let[x << 0][
                      lambda: [x << x + 1,
                               x]]
            assert count() == 1
            assert count() == 2

            mk12 = lambda: [[1, 2]]
            assert mk12() == [1, 2]

    For local variables, see ``do``.
    """
    if syntax != "block":
        raise SyntaxError("multilambda is a block macro only")  # pragma: no cover
    if syntax == "block" and kw['optional_vars'] is not None:
        raise SyntaxError("multilambda does not take an as-part")  # pragma: no cover

    # Expand outside in.
    # multilambda should expand first before any let[], do[] et al. that happen
    # to be inside the block, to avoid misinterpreting implicit lambdas
    # generated by those constructs.
    with dyn.let(_macro_expander=expander):  # implicit do (extra bracket notation) needs this.
        return _multilambda(block_body=tree)

def namedlambda(tree, *, syntax, expander, **kw):
    """[syntax, block] Name lambdas implicitly.

    Lexically inside a ``with namedlambda`` block, any literal ``lambda``
    that is assigned to a name using one of the supported assignment forms
    is named to have the name of the LHS of the assignment. The name is
    captured at macro expansion time.

    Naming modifies the original function object.

    We support:

        - Single-item assignments to a local name, ``f = lambda ...: ...``

        - Named expressions (a.k.a. walrus operator, Python 3.8+),
          ``f := lambda ...: ...``

        - Assignments to unpythonic environments, ``f << (lambda ...: ...)``

        - Let bindings, ``let[[f << (lambda ...: ...)] in ...]``, using any
          let syntax supported by unpythonic (here using the haskelly let-in
          just as an example).

    Support for other forms of assignment might or might not be added in a
    future version.

    Example::

        with namedlambda:
            f = lambda x: x**3        # assignment: name as "f"

            let[x << 42, g << None, h << None][[
              g << (lambda x: x**2),  # env-assignment: name as "g"
              h << f,                 # still "f" (no literal lambda on RHS)
              (g(x), h(x))]]

            foo = let[[f7 << (lambda x: x)] in f7]  # let-binding: name as "f7"

    The naming is performed using the function ``unpythonic.misc.namelambda``,
    which will update ``__name__``, ``__qualname__`` and ``__code__.co_name``.
    """
    if syntax != "block":
        raise SyntaxError("namedlambda is a block macro only")  # pragma: no cover
    if syntax == "block" and kw['optional_vars'] is not None:
        raise SyntaxError("namedlambda does not take an as-part")  # pragma: no cover

    # Two-pass macro. We pass in the expander to allow the macro to decide when to recurse.
    with dyn.let(_macro_expander=expander):
        return _namedlambda(block_body=tree)

def f(tree, *, syntax, expander, **kw):
    """[syntax, expr] Underscore notation (quick lambdas) for Python.

    Usage::

        f[body]

    The ``f[]`` macro creates a lambda. Each underscore in ``body``
    introduces a new parameter.

    Example::

        func = f[_ * _]

    expands to::

        func = lambda a0, a1: a0 * a1

    The underscore is interpreted magically by ``f[]``; but ``_`` itself
    is not a macro, and has no special meaning outside ``f[]``. The underscore
    does **not** need to be imported for ``f[]`` to recognize it.

    The macro does not descend into any nested ``f[]``.
    """
    if syntax != "expr":
        raise SyntaxError("f is an expr macro only")  # pragma: no cover

    # What's my name in the current expander? (There may be several names.)
    # https://github.com/Technologicat/mcpyrate/blob/master/doc/quasiquotes.md#hygienic-macro-recursion
    bindings = extract_bindings(expander.bindings, f)
    mynames = list(bindings.keys())

    return _f(tree, mynames)

def quicklambda(tree, *, syntax, expander, **kw):
    """[syntax, block] Make ``f`` quick lambdas expand first.

    To be able to transform correctly, the block macros in ``unpythonic.syntax``
    that transform lambdas (e.g. ``multilambda``, ``tco``) need to see all
    ``lambda`` definitions written with Python's standard ``lambda``.

    However, the ``f`` macro uses the syntax ``f[...]``, which (to the analyzer)
    does not look like a lambda definition. This macro changes the expansion
    order, forcing any ``f[...]`` lexically inside the block to expand before
    any other macros do.

    Any expression of the form ``f[...]``, where ``f`` is any name bound in the
    current macro expander to the macro `unpythonic.syntax.f`, is understood as
    a quick lambda. (In plain English, this respects as-imports of the macro ``f``.)

    Example - a quick multilambda::

        from unpythonic.syntax import macros, multilambda, quicklambda, f, local

        with quicklambda, multilambda:
            func = f[[local[x << _],
                      local[y << _],
                      x + y]]
            assert func(1, 2) == 3

    (This is of course rather silly, as an unnamed argument can only be mentioned
    once. If we're giving names to them, a regular ``lambda`` is shorter to write.
    The point is, this combo is now possible.)
    """
    if syntax != "block":
        raise SyntaxError("quicklambda is a block macro only")  # pragma: no cover
    if syntax == "block" and kw['optional_vars'] is not None:
        raise SyntaxError("quicklambda does not take an as-part")  # pragma: no cover

    # This macro expands outside in.
    #
    # In `mcpyrate`, expander instances are cheap - so we create a second expander
    # to which we register only the `f` macro, under whatever names it appears in
    # the original expander. Thus it leaves all other macros alone. This is the
    # official `mcpyrate` way to immediately expand only some particular macros
    # inside the current macro invocation.
    bindings = extract_bindings(expander.bindings, f)
    return MacroExpander(bindings, expander.filename).visit(tree)

def envify(tree, *, syntax, expander, **kw):
    """[syntax, block] Make formal parameters live in an unpythonic env.

    The purpose is to allow overwriting formals using unpythonic's
    expression-assignment ``name << value``. The price is that the references
    to the arguments are copied into an env whenever an envified function is
    entered.

    Example - PG's accumulator puzzle (http://paulgraham.com/icad.html)::

        with envify:
            def foo(n):
                return lambda i: n << n + i

    Or even shorter::

        with autoreturn, envify:
            def foo(n):
                lambda i: n << n + i
    """
    if syntax != "block":
        raise SyntaxError("envify is a block macro only")  # pragma: no cover
    if syntax == "block" and kw['optional_vars'] is not None:
        raise SyntaxError("envify does not take an as-part")  # pragma: no cover

    # Two-pass macro.
    with dyn.let(_macro_expander=expander):
        return _envify(block_body=tree)

# --------------------------------------------------------------------------------
# Syntax transformers

def _multilambda(block_body):
    class MultilambdaTransformer(ASTTransformer):
        def transform(self, tree):
            if is_captured_value(tree):
                return tree  # don't recurse!
            if type(tree) is Lambda:
                tree.body = _implicit_do(tree.body)
            return self.generic_visit(tree)
    # multilambda should expand first before any let[], do[] et al. that happen
    # to be inside the block, to avoid misinterpreting implicit lambdas
    # generated by those constructs.
    return MultilambdaTransformer().visit(block_body)

def _namedlambda(block_body):
    def issingleassign(tree):
        return type(tree) is Assign and len(tree.targets) == 1 and type(tree.targets[0]) is Name

    # detect a manual curry
    def iscurrywithfinallambda(tree):
        if not (type(tree) is Call and isx(tree.func, "curry") and tree.args):
            return False
        return type(tree.args[-1]) is Lambda

    # Detect an autocurry from an already expanded "with autocurry".
    # CAUTION: These must match what unpythonic.syntax.autocurry.autocurry uses in its output.
    currycall_name = "currycall"
    iscurryf = lambda name: name in ("curryf", "curry")  # auto or manual curry in a "with autocurry"
    def isautocurrywithfinallambda(tree):
        # "currycall(..., curryf(lambda ...: ...))"
        if not (type(tree) is Call and isx(tree.func, currycall_name) and tree.args and
                type(tree.args[-1]) is Call and isx(tree.args[-1].func, iscurryf)):
            return False
        curryf_callnode = tree.args[-1]
        lastarg = curryf_callnode.args[-1]
        return type(lastarg) is Lambda

    def iscallwithnamedargs(tree):
        return type(tree) is Call and tree.keywords

    # If `tree` is a (bare or decorated) lambda, inject run-time code to name
    # it as `myname` (str); else return `tree` as-is.
    def nameit(myname, tree):
        match, thelambda = False, None
        # For decorated lambdas, match any chain of one-argument calls.
        # The `has_deco` check ignores any already named lambdas.
        d = is_decorated_lambda(tree, mode="any") and not has_deco(["namelambda"], tree)
        c = iscurrywithfinallambda(tree)
        # This matches only during the second pass (after "with autocurry" has expanded)
        # so it can't have namelambda already applied
        if isautocurrywithfinallambda(tree):  # "currycall(..., curryf(lambda ...: ...))"
            match = True
            thelambda = tree.args[-1].args[-1]
            # --> "currycall(..., (namelambda(myname))(curryf(lambda ...: ...)))"
            tree.args[-1].args[-1] = q[h[namelambda](u[myname])(a[thelambda])]
        elif type(tree) is Lambda or d or c:
            match = True
            if d:
                decorator_list, thelambda = destructure_decorated_lambda(tree)
            elif c:
                thelambda = tree.args[-1]
            else:
                thelambda = tree
            tree = q[h[namelambda](u[myname])(a[tree])]  # plonk it as outermost and hope for the best
        return tree, thelambda, match

    class NamedLambdaTransformer(ASTTransformer):
        def transform(self, tree):
            if is_captured_value(tree):
                return tree  # don't recurse!
            if islet(tree, expanded=False):  # let bindings
                view = UnexpandedLetView(tree)
                newbindings = []
                for b in view.bindings:
                    b.elts[1], thelambda, match = nameit(getname(b.elts[0]), b.elts[1])
                    if match:
                        thelambda.body = self.visit(thelambda.body)
                    else:
                        b.elts[1] = self.visit(b.elts[1])
                    newbindings.append(b)
                view.bindings = newbindings  # write the new bindings (important!)
                view.body = self.visit(view.body)
                return tree
            # assumption: no one left-shifts by a literal lambda :)
            elif isenvassign(tree):  # f << (lambda ...: ...)
                view = UnexpandedEnvAssignView(tree)
                view.value, thelambda, match = nameit(view.name, view.value)
                if match:
                    thelambda.body = self.visit(thelambda.body)
                else:
                    view.value = self.visit(view.value)
                return tree
            elif issingleassign(tree):  # f = lambda ...: ...
                tree.value, thelambda, match = nameit(getname(tree.targets[0]), tree.value)
                if match:
                    thelambda.body = self.visit(thelambda.body)
                else:
                    tree.value = self.visit(tree.value)
                return tree
            elif type(tree) is NamedExpr:  # f := lambda ...: ...  (Python 3.8+, added in unpythonic 0.15)
                tree.value, thelambda, match = nameit(getname(tree.target), tree.value)
                if match:
                    thelambda.body = self.visit(thelambda.body)
                else:
                    tree.value = self.visit(tree.value)
                return tree
            elif iscallwithnamedargs(tree):  # foo(f=lambda: ...)
                for kw in tree.keywords:
                    if kw.arg is None:  # **kwargs in Python 3.5+
                        kw.value = self.visit(kw.value)
                        continue
                    # a single named arg
                    kw.value, thelambda, match = nameit(kw.arg, kw.value)
                    if match:
                        thelambda.body = self.visit(thelambda.body)
                    else:
                        kw.value = self.visit(kw.value)
                tree.args = self.visit(tree.args)
                return tree
            elif type(tree) is Dict:  # {"f": lambda: ..., "g": lambda: ...}
                lst = list(zip(tree.keys, tree.values))
                for j in range(len(lst)):
                    k, v = tree.keys[j], tree.values[j]
                    if k is None:  # {..., **d, ...}
                        tree.values[j] = self.visit(v)
                    else:
                        if type(k) in (Constant, Str):  # Python 3.8+: ast.Constant
                            thename = getconstant(k)
                            tree.values[j], thelambda, match = nameit(thename, v)
                            if match:
                                thelambda.body = self.visit(thelambda.body)
                            else:
                                tree.values[j] = self.visit(v)
                        else:
                            tree.keys[j] = self.visit(k)
                            tree.values[j] = self.visit(v)
                return tree
            return self.generic_visit(tree)

    # outside in: transform in unexpanded let[] forms
    newbody = NamedLambdaTransformer().visit(block_body)

    newbody = dyn._macro_expander.visit_recursively(newbody)

    # inside out: transform in expanded autocurry
    newbody = NamedLambdaTransformer().visit(newbody)

    # v0.15.0+: Finally, auto-name any still anonymous `lambda` with source location info.
    # We must perform this in a separate pass so that expanded autocurry invocations
    # are transformed correctly first.
    class NamedLambdaFinalizationTransformer(ASTTransformer):
        def transform(self, tree):
            # Recurse into the lambda body in already named lambdas.
            if is_decorated_lambda(tree, mode="any") and has_deco(["namelambda"], tree):
                decorator_list, thelambda = destructure_decorated_lambda(tree)
                thelambda.body = self.visit(thelambda.body)
                return tree
            elif type(tree) is Lambda:
                if hasattr(tree, "lineno"):
                    thename = f"<lambda at {dyn._macro_expander.filename}:{tree.lineno}>"
                    tree, thelambda, match = nameit(thename, tree)
                    if match:
                        thelambda.body = self.visit(thelambda.body)
                    else:
                        tree = self.visit(tree)
                return tree
            return self.generic_visit(tree)
    return NamedLambdaFinalizationTransformer().visit(newbody)


# The function `f` is adapted from the `f` macro in `macropy.quick_lambda`,
# stripped into a bare syntax transformer., and then the `@Walker` inside
# converted to a `mcpyrate` `ASTTransformer`. We have also added the code
# to ignore any nested `f[]`.
#
# Used under the MIT license.
# Copyright (c) 2013-2018, Li Haoyi, Justin Holmgren, Alberto Berti and all the other contributors.
def _f(tree, mynames=()):
    class UnderscoreTransformer(ASTTransformer):
        def transform(self, tree):
            if is_captured_value(tree):
                return tree  # don't recurse!
            # Don't recurse into nested `f[]`.
            # TODO: This would benefit from macro destructuring in the expander.
            # TODO: See https://github.com/Technologicat/mcpyrate/issues/3
            if type(tree) is Subscript and type(tree.value) is Name and tree.value.id in mynames:
                return tree
            elif type(tree) is Name and tree.id == "_":
                name = gensym("_")
                tree.id = name
                self.collect(name)
            return self.generic_visit(tree)
    ut = UnderscoreTransformer()
    tree = ut.visit(tree)
    used_names = ut.collected
    tree = q[lambda _: a[tree]]  # noqa: F811, it's a placeholder overwritten at the next line.
    tree.args.args = [arg(arg=x) for x in used_names]
    return tree

def _envify(block_body):
    # first pass, outside-in
    userlambdas = detect_lambda(block_body)

    block_body = dyn._macro_expander.visit_recursively(block_body)

    # second pass, inside-out
    def getargs(tree):  # tree: FunctionDef, AsyncFunctionDef, Lambda
        a = tree.args
        if hasattr(a, "posonlyargs"):  # Python 3.8+: positional-only parameters
            allargs = a.posonlyargs + a.args + a.kwonlyargs
        else:
            allargs = a.args + a.kwonlyargs
        argnames = [x.arg for x in allargs]
        if a.vararg:
            argnames.append(a.vararg.arg)
        if a.kwarg:
            argnames.append(a.kwarg.arg)
        return argnames

    def isfunctionoruserlambda(tree):
        return ((type(tree) in (FunctionDef, AsyncFunctionDef)) or
                (type(tree) is Lambda and id(tree) in userlambdas))

    # Create a renamed reference to the env() constructor to be sure the Call
    # nodes added by us have a unique .func (not used by other macros or user code)
    _envify = env

    class EnvifyTransformer(ASTTransformer):
        def transform(self, tree):
            if is_captured_value(tree):
                return tree  # don't recurse!

            bindings = self.state.bindings
            enames = self.state.enames

            def isourupdate(thecall):
                if type(thecall.func) is not Attribute:
                    return False
                return thecall.func.attr == "update" and any(isx(thecall.func.value, x) for x in enames)

            if isfunctionoruserlambda(tree):
                argnames = getargs(tree)
                if argnames:
                    # prepend env init to function body, update bindings
                    kws = [keyword(arg=k, value=q[n[k]]) for k in argnames]  # "x" --> x
                    newbindings = bindings.copy()
                    if type(tree) in (FunctionDef, AsyncFunctionDef):
                        ename = gensym("e")
                        theenv = q[h[_envify]()]
                        theenv.keywords = kws
                        with q as quoted:
                            n[ename] = a[theenv]
                        assignment = quoted[0]
                        tree.body.insert(0, assignment)
                    elif type(tree) is Lambda and id(tree) in userlambdas:
                        # We must in general inject a new do[] even if one is already there,
                        # due to scoping rules. If the user code writes to the same names in
                        # its do[] env, this shadows the formals; if it then pops one of its names,
                        # the name should revert to mean the formal parameter.
                        #
                        # inject a do[] and reuse its env
                        tree.body = _do(q[n["_here_"],
                                          a[tree.body]])
                        view = ExpandedDoView(tree.body)  # view.body: [(lambda e14: ...), ...]
                        ename = view.body[0].args.args[0].arg  # do[] environment name
                        theupdate = q[n[f"{ename}.update"]]
                        thecall = q[a[theupdate]()]
                        thecall.keywords = kws
                        tree.body = splice_expression(thecall, tree.body, "_here_")
                    newbindings.update({k: q[n[f"{ename}.{k}"]] for k in argnames})  # "x" --> e.x
                    self.generic_withstate(tree, enames=(enames + [ename]), bindings=newbindings)
            else:
                # leave alone the _envify() added by us
                if type(tree) is Call and (isx(tree.func, "_envify") or isourupdate(tree)):
                    # don't recurse
                    return tree
                # transform env-assignments into our envs
                elif isenvassign(tree):
                    view = UnexpandedEnvAssignView(tree)
                    if view.name in bindings.keys():
                        # Grab the envname from the actual binding of "varname", of the form `e.varname`
                        # (so it's the `id` of a `Name` that is the `value` of an `Attribute`).
                        envset = q[n[f"{bindings[view.name].value.id}.set"]]
                        newvalue = self.visit(view.value)
                        return q[a[envset](u[view.name], a[newvalue])]
                # transform references to currently active bindings
                elif type(tree) is Name and tree.id in bindings.keys():
                    # We must be careful to preserve the Load/Store/Del context of the name.
                    # The default lets `mcpyrate` fix it later.
                    ctx = tree.ctx if hasattr(tree, "ctx") else None
                    out = deepcopy(bindings[tree.id])
                    out.ctx = ctx
                    return out

            return self.generic_visit(tree)

    return EnvifyTransformer(bindings={}, enames=[]).visit(block_body)
