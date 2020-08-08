# -*- coding: utf-8 -*-
"""Lexical scoping support.

This is used to support interaction of the ``let[]`` and ``do[]`` macros
(which use ``env`` to simulate a lexical environment, with static name lookup
at macro-expansion time) with Python's standard lexical scoping system.

This module cares only about Python's standard scoping rules, but with a
small twist: assignments (creation of local variables) and local deletes
are considered to take effect **from the next statement onward**, for the
**lexically remaining part** of the current scope.

This is mainly for symmetry with how ``do[]`` handles ``local[...]``, but it also
allows the RHS of an assignment to see the old bindings. This may be important
if the RHS uses some ``env`` variables, so that things like "x = x" work (create
new local x, assign value from an x that lives in a lexically surrounding ``env``,
such as that created by the "let" decorator macro ``@dlet``).
"""

from ast import (Name, Tuple,
                 Lambda, FunctionDef, ClassDef,
                 List, For, Import, Try, With,
                 ListComp, SetComp, GeneratorExp, DictComp,
                 Store, Del,
                 Global, Nonlocal)
from .astcompat import AsyncFunctionDef, AsyncFor, AsyncWith

from macropy.core.walkers import Walker

from ..it import uniqify

def isnewscope(tree):
    """Return whether tree introduces a new lexical scope.

    (According to Python's standard scoping rules.)
    """
    return type(tree) in (Lambda, FunctionDef, AsyncFunctionDef, ClassDef, ListComp, SetComp, GeneratorExp, DictComp)

@Walker
def scoped_walker(tree, *, localvars=[], args=[], nonlocals=[], callback, set_ctx, stop, **kw):
    """Walk and process a tree, keeping track of which names are shadowed.

    Names in an unpythonic env can be shadowed by e.g. real lexical variables,
    formal parameters of function definitions, or names declared ``nonlocal``
    or ``global``. See ``getshadowers``.

    callback: function, (tree, shadowed_names) --> tree
    """
    # TODO: think about proper handling of ClassDef
    if type(tree) in (Lambda, ListComp, SetComp, GeneratorExp, DictComp, ClassDef):
        moreargs, _ = getshadowers(tree)
        set_ctx(args=(args + moreargs))
    elif type(tree) in (FunctionDef, AsyncFunctionDef):
        stop()
        moreargs, newnonlocals = getshadowers(tree)
        args = args + moreargs
        for expr in (tree.args, tree.decorator_list):
            scoped_walker.recurse(expr, localvars=localvars, args=args, nonlocals=nonlocals, callback=callback)
        nonlocals = newnonlocals
        localvars = []
        for stmt in tree.body:
            scoped_walker.recurse(stmt, localvars=localvars, args=args, nonlocals=nonlocals, callback=callback)
            # new local variables come into scope at the next statement (not yet on the RHS of the assignment).
            newlocalvars = uniqify(get_names_in_store_context.collect(stmt))
            newlocalvars = [x for x in newlocalvars if x not in nonlocals]
            if newlocalvars:
                localvars = localvars + newlocalvars
            # deletions of local vars also take effect from the next statement
            deletedlocalvars = uniqify(get_names_in_del_context.collect(stmt))
            # ignore deletion of nonlocals (too dynamic for a static analysis to make sense)
            deletedlocalvars = [x for x in deletedlocalvars if x not in nonlocals]
            if deletedlocalvars:
                localvars = [x for x in localvars if x not in deletedlocalvars]
        return tree
    shadowed = args + localvars + nonlocals
    return callback(tree, shadowed)

def getshadowers(tree):
    """In a tree representing a lexical scope, get names that shadow names in unpythonic envs.

    An AST node represents a scope if ``isnewscope(tree)`` returns ``True``.

    This collects:

        - formal parameter names of ``Lambda``, ``FunctionDef``, ``AsyncFunctionDef``

            - plus function name of ``FunctionDef``, ``AsyncFunctionDef``

            - any names declared ``nonlocal`` or ``global`` in a ``FunctionDef``
              or ``AsyncFunctionDef``

        - names of comprehension targets in ``ListComp``, ``SetComp``,
          ``GeneratorExp``, ``DictComp``

        - class name and base class names of ``ClassDef``

            - **CAUTION**: base class scan only supports bare ``Name`` nodes

    Return value is (``args``, ``nonlocals``), where each component is a ``list``
    of ``str``. The list ``nonlocals`` contains names declared ``nonlocal`` or
    ``global`` in (precisely) this scope; the list ``args`` contains everything
    else.
    """
    if type(tree) in (Lambda, FunctionDef, AsyncFunctionDef):
        a = tree.args
        argnames = [x.arg for x in a.args + a.kwonlyargs]
        if a.vararg:
            argnames.append(a.vararg.arg)
        if a.kwarg:
            argnames.append(a.kwarg.arg)

        fname = []
        nonlocals = []
        if type(tree) in (FunctionDef, AsyncFunctionDef):
            fname = [tree.name]
            @Walker
            def getnonlocals(tree, *, stop, collect, **kw):
                if isnewscope(tree):
                    stop()
                if type(tree) in (Global, Nonlocal):
                    for x in tree.names:
                        collect(x)
                return tree
            nonlocals = getnonlocals.collect(tree.body)

        return list(uniqify(fname + argnames)), list(uniqify(nonlocals))

    # TODO: think about proper handling of ClassDef
    elif type(tree) is ClassDef:
        cname = [tree.name]
        bases = [b.id for b in tree.bases if type(b) is Name]
        # these are referred to via self.foo, so they don't shadow bare names.
#        classattrs = _get_names_in_store_context.collect(tree.body)
#        methods = [f.name for f in tree.body if type(f) is FunctionDef]
        return list(uniqify(cname + bases)), []

    elif type(tree) in (ListComp, SetComp, GeneratorExp, DictComp):
        targetnames = []
        for g in tree.generators:
            if type(g.target) is Name:
                targetnames.append(g.target.id)
            elif type(g.target) is Tuple:
                @Walker
                def extractnames(tree, *, collect, **kw):
                    if type(tree) is Name:
                        collect(tree.id)
                    return tree
                targetnames.extend(extractnames.collect(g.target))
            else:
                assert False, "unimplemented: comprehension target of type {}".type(g.target)

        return list(uniqify(targetnames)), []

    return [], []

@Walker
def get_names_in_store_context(tree, *, stop, collect, **kw):
    """In a tree representing a statement, get names bound by that statement.

    This includes:

        - Any ``Name`` in store context

        - The name of ``FunctionDef``, ``AsyncFunctionDef`` or``ClassDef``

        - The target(s) of ``For``

        - The names (or asnames where applicable) of ``Import``

        - The exception name of any ``except`` handlers

        - The names in the as-part of ``With``

    Duplicates may be returned; use ``set(...)`` or ``list(uniqify(...))``
    on the output to remove them.

    This stops at the boundary of any nested scopes.

    To find out new local vars, exclude any names in ``nonlocals`` as returned
    by ``getshadowers``.
    """
    def collect_name_or_list(t):
        if type(t) is Name:
            collect(t.id)
        elif type(t) in (Tuple, List):
            for x in t.elts:
                collect(x.id)
        else:
            assert False, "unknown type {}".format(type(t))
    # Useful article: http://excess.org/article/2014/04/bar-foo/
    if type(tree) in (FunctionDef, AsyncFunctionDef, ClassDef):
        collect(tree.name)
    elif type(tree) is (For, AsyncFor):
        collect_name_or_list(tree.target)
    elif type(tree) is Import:
        for x in tree.names:
            collect(x.asname if x.asname is not None else x.name)
    elif type(tree) is Try:
        for h in tree.handlers:
            collect(h.name)
    elif type(tree) is (With, AsyncWith):
        for item in tree.items:
            if item.optional_vars is not None:
                collect_name_or_list(item.optional_vars)
    if isnewscope(tree):
        stop()
    # macro-created nodes might not have a ctx, but our macros don't create lexical assignments.
    if type(tree) is Name and hasattr(tree, "ctx") and type(tree.ctx) is Store:
        collect(tree.id)
    return tree

@Walker
def get_names_in_del_context(tree, *, stop, collect, **kw):
    """In a tree representing a statement, get names in del context."""
    if isnewscope(tree):
        stop()
    # We want to detect things like "del x":
    #     Delete(targets=[Name(id='x', ctx=Del()),])
    # We don't currently care about "del myobj.x" or "del mydict['x']":
    #     Delete(targets=[Attribute(value=Name(id='myobj', ctx=Load()), attr='x', ctx=Del()),])
    #     Delete(targets=[Subscript(value=Name(id='mydict', ctx=Load()), slice=Index(value=Str(s='x')), ctx=Del()),])
    elif type(tree) is Name and hasattr(tree, "ctx") and type(tree.ctx) is Del:
        collect(tree.id)
    return tree
