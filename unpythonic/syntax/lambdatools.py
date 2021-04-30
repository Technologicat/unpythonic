# -*- coding: utf-8 -*-
"""Lambdas with multiple expressions, local variables, and a name."""

__all__ = ["multilambda",
           "namedlambda",
           "f",  # for quicklambda
           "envify"]

from ast import (Lambda, List, Name, Assign, Subscript, Call, FunctionDef,
                 AsyncFunctionDef, Attribute, keyword, Dict, Constant, arg,
                 copy_location)
from copy import deepcopy

from mcpyrate.quotes import macros, q, u, n, a, h  # noqa: F401

from mcpyrate import gensym
from mcpyrate.quotes import is_captured_value
from mcpyrate.splicing import splice_expression
from mcpyrate.utils import extract_bindings
from mcpyrate.walkers import ASTTransformer

from ..dynassign import dyn
from ..misc import namelambda
from ..env import env

from .astcompat import getconstant, Str, NamedExpr
from .letdo import do
from .letdoutil import islet, isenvassign, UnexpandedLetView, UnexpandedEnvAssignView, ExpandedDoView
from .util import (is_decorated_lambda, isx, has_deco,
                   destructure_decorated_lambda, detect_lambda)

def multilambda(block_body):
    class MultilambdaTransformer(ASTTransformer):
        def transform(self, tree):
            if is_captured_value(tree):
                return tree  # don't recurse!
            if not (type(tree) is Lambda and type(tree.body) is List):
                return self.generic_visit(tree)
            bodys = tree.body
            # bracket magic:
            # - don't recurse to the implicit lambdas generated by the "do" we are inserting here
            #   - for each item, "do" internally inserts a lambda to delay execution,
            #     as well as to bind the environment
            #   - we must do() instead of q[h[do][...]] for pickling reasons
            # - but recurse manually into each *do item*; these are explicit
            #   user-provided code so we should transform them
            bodys = self.visit(bodys)
            tree.body = do(bodys)  # insert the do, with the implicit lambdas
            return tree
    # multilambda should expand first before any let[], do[] et al. that happen
    # to be inside the block, to avoid misinterpreting implicit lambdas
    # generated by those constructs.
    return MultilambdaTransformer().visit(block_body)

def namedlambda(block_body):
    def issingleassign(tree):
        return type(tree) is Assign and len(tree.targets) == 1 and type(tree.targets[0]) is Name

    # detect a manual curry
    def iscurrywithfinallambda(tree):
        if not (type(tree) is Call and isx(tree.func, "curry") and tree.args):
            return False
        return type(tree.args[-1]) is Lambda

    # Detect an autocurry from an already expanded "with autocurry".
    # CAUTION: These must match what unpythonic.syntax.curry.autocurry uses in its output.
    currycall_name = "currycall"
    iscurryf = lambda name: name in ("curryf", "curry")  # auto or manual curry in a "with autocurry"
    def isautocurrywithfinallambda(tree):
        if not (type(tree) is Call and isx(tree.func, currycall_name) and tree.args and
                type(tree.args[-1]) is Call and isx(tree.args[-1].func, iscurryf)):
            return False
        return type(tree.args[-1].args[-1]) is Lambda

    def iscallwithnamedargs(tree):
        return type(tree) is Call and tree.keywords

    # If `tree` is a (bare or decorated) lambda, inject run-time code to name
    # it as `myname` (str); else return `tree` as-is.
    def nameit(myname, tree):
        match, thelambda = False, None
        # for decorated lambdas, match any chain of one-argument calls.
        d = is_decorated_lambda(tree, mode="any") and not has_deco(tree, "namelambda")
        c = iscurrywithfinallambda(tree)
        # this matches only during the second pass (after "with autocurry" has expanded)
        # so it can't have namelambda already applied
        if isautocurrywithfinallambda(tree):  # "currycall(..., curryf(lambda ...: ...))"
            match = True
            thelambda = tree.args[-1].args[-1]
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
                for b in view.bindings:
                    b.elts[1], thelambda, match = nameit(b.elts[0].id, b.elts[1])
                    if match:
                        thelambda.body = self.visit(thelambda.body)
                    else:
                        b.elts[1] = self.visit(b.elts[1])
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
                tree.value, thelambda, match = nameit(tree.targets[0].id, tree.value)
                if match:
                    thelambda.body = self.visit(thelambda.body)
                else:
                    tree.value = self.visit(tree.value)
                return tree
            elif type(tree) is NamedExpr:  # f := lambda ...: ...  (Python 3.8+, added in unpythonic 0.15)
                tree.value, thelambda, match = nameit(tree.target.id, tree.value)
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

    newbody = dyn._macro_expander.visit(newbody)

    # inside out: transform in expanded autocurry
    return NamedLambdaTransformer().visit(newbody)

# The function `f` is adapted from the `f` macro in `macropy.quick_lambda`,
# stripped into a bare syntax transformer., and then the `@Walker` inside
# converted to a `mcpyrate` `ASTTransformer`. We have also added the code
# to ignore any nested `f[]`.
#
# Used under the MIT license.
# Copyright (c) 2013-2018, Li Haoyi, Justin Holmgren, Alberto Berti and all the other contributors.
def f(tree):
    # What's my name in the current expander? (There may be several names.)
    # https://github.com/Technologicat/mcpyrate/blob/master/doc/quasiquotes.md#hygienic-macro-recursion
    # TODO: doesn't currently work because this `f` is the syntax transformer, not the `f[]` macro.
    bindings = extract_bindings(dyn._macro_expander.bindings, f)
    mynames = list(bindings.keys())

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

def envify(block_body):
    # first pass, outside-in
    userlambdas = detect_lambda(block_body)

    block_body = dyn._macro_expander.visit(block_body)

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
                        assignment = Assign(targets=[q[n[ename]]],
                                            value=theenv)
                        assignment = copy_location(assignment, tree)
                        tree.body.insert(0, assignment)
                    elif type(tree) is Lambda and id(tree) in userlambdas:
                        # We must in general inject a new do[] even if one is already there,
                        # due to scoping rules. If the user code writes to the same names in
                        # its do[] env, this shadows the formals; if it then pops one of its names,
                        # the name should revert to mean the formal parameter.
                        #
                        # inject a do[] and reuse its env
                        tree.body = do(List(elts=[q[n["_here_"]],
                                                  tree.body]))
                        view = ExpandedDoView(tree.body)  # view.body: [(lambda e14: ...), ...]
                        ename = view.body[0].args.args[0].arg  # do[] environment name
                        theupdate = Attribute(value=q[n[ename]], attr="update")
                        thecall = q[a[theupdate]()]
                        thecall.keywords = kws
                        tree.body = splice_expression(thecall, tree.body, "_here_")
                    newbindings.update({k: Attribute(value=q[n[ename]], attr=k) for k in argnames})  # "x" --> e.x
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
                        envset = Attribute(value=bindings[view.name].value, attr="set")
                        newvalue = self.visit(view.value)
                        return q[a[envset](u[view.name], a[newvalue])]
                # transform references to currently active bindings
                elif type(tree) is Name and tree.id in bindings.keys():
                    # We must be careful to preserve the Load/Store/Del context of the name.
                    # The default lets mcpyrate fix it later.
                    ctx = tree.ctx if hasattr(tree, "ctx") else None
                    out = deepcopy(bindings[tree.id])
                    out.ctx = ctx
                    return out

            return self.generic_visit(tree)

    return EnvifyTransformer(bindings={}, enames=[]).visit(block_body)
