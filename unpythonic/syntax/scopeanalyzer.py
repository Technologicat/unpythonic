# -*- coding: utf-8 -*-
"""Lexical scope analysis tools.

This is used to support interaction of the ``let[]`` and ``do[]`` macros
(which use ``env`` to simulate a lexical environment, with static name lookup
at macro-expansion time) with Python's built-in lexical scoping system.

This module cares only about Python's standard scoping rules, but with a
small twist: assignments (creation of local variables) and local deletes
are considered to take effect **from the next statement onward**, for the
**lexically remaining part** of the current scope. (This is how Python
behaves at run time, anyway; trying to delete a local that hasn't yet
been assigned to raises `UnboundLocalError`.)

This is mainly for symmetry with how ``do[]`` handles ``local[...]``, but it also
allows the RHS of an assignment to see the old bindings. This may be important
if the RHS uses some ``env`` variables, so that things like "x = x" work (create
new local x, assign value from an x that lives in a lexically surrounding ``env``,
such as that created by the "let" decorator macro ``@dlet``).

Deletions of nonlocals and globals are ignored, because those are too dynamic
for static analysis to make sense.


**CAUTION**:

What we do currently (before v0.15.0) doesn't fully make sense.

Scope - in the sense of controlling lexical name resolution - is a static
(purely lexical) concept, but whether a particular name (once lexically
resolved) has been initialized (or, say, whether it has been deleted) is a
dynamic (run-time) feature. (I would say "property", if that word didn't
have an entirely different technical meaning in Python.)

Consider deleting a name in one branch of an `if`/`else`. After that
`if`/`else`, is the name still defined or not? Of course, with very few
exceptional trivial cases such as `if 1`, this depends on the condition
part of the `if` at run time, and thus can't be statically determined.

In order to make more sense, in v0.15.0, we will migrate to a fully static analysis.
This will make the analyzer consistent with how Python itself handles scoping,
at the cost of slightly (but backward-incompatibly) changing the semantics of
some corner cases in the usage of `let` and `do`.

As of v0.14.3, a fully lexical mode has been added to `get_lexical_variables`
(which, up to v0.14.2, used to be called `getshadowers`), and is enabled by default.

It is disabled when `scoped_transform` calls `get_lexical_variables`, to preserve
old behavior until the next opportunity for a public interface change.
In v0.15.0, we will make `scoped_transform` use the fully lexical mode.


**NOTE**:

Relevant part of the Python language reference:

    https://docs.python.org/3/reference/executionmodel.html#naming-and-binding

Scope analysis for Python is complicated, because the language's syntax
conflates definition and rebinding. In any language that keeps these separate,
the `global` and `nonlocal` keywords aren't needed. For discussion on this
point, and on the need for an "uninitialized" special value (called ☠), see:

    Joe Gibbs Politz, Alejandro Martinez, Matthew Milano, Sumner Warren,
    Daniel Patterson, Junsong Li, Anand Chitipothu, Shriram Krishnamurthi, 2013,
    Python: The Full Monty - A Tested Semantics for the Python Programming Language.
    OOPSLA '13. http://dx.doi.org/10.1145/2509136.2509536
"""

from ast import (Name, Tuple, Lambda, FunctionDef, AsyncFunctionDef, ClassDef,
                 Import, ImportFrom, Try, ListComp, SetComp, GeneratorExp,
                 DictComp, Store, Del, Global, Nonlocal)

from mcpyrate.walkers import ASTTransformer, ASTVisitor

from ..it import uniqify

def isnewscope(tree):
    """Return whether tree introduces a new lexical scope.

    (According to Python's scoping rules.)
    """
    return type(tree) in (Lambda, FunctionDef, AsyncFunctionDef, ClassDef, ListComp, SetComp, GeneratorExp, DictComp)

# TODO: make this fit `mcpyrate`'s `ASTTransformer` paradigm better.
# TODO: maybe allow passing initial args, localvars, nonlocals?
def scoped_transform(tree, *, callback):
    """Walk and process a tree, keeping track of which names are in scope.

    This essentially equips a custom AST transformer with scope analysis.

    `callback`: callable, (tree, names_in_scope) --> tree
                Called for each AST node of the input `tree`, to perform the
                real work. It may edit the tree in-place.

    **CAUTION**: `scoped_transform` handles recursion; the `callback` should
                 only treat the top level of the `tree` it gets.

                 Also, there is currently no way for `callback` to prevent
                 further recursion into the child nodes.
    """
    class ScopedTransformer(ASTTransformer):
        def transform(self, tree):
            args = self.state.args
            localvars = self.state.localvars
            nonlocals = self.state.nonlocals
            if type(tree) in (Lambda, ListComp, SetComp, GeneratorExp, DictComp, ClassDef):
                moreargs, _ = get_lexical_variables(tree, collect_locals=False)
                self.generic_withstate(tree, args=(args + moreargs))
            elif type(tree) in (FunctionDef, AsyncFunctionDef):
                # Decorator list is processed in the surrounding scope
                new_decorator_list = self.visit(tree.decorator_list)
                tree.decorator_list = new_decorator_list if new_decorator_list is not None else []

                moreargs, newnonlocals = get_lexical_variables(tree, collect_locals=False)

                # The function parameters see each other (TODO: check if this is right)
                self.withstate(tree.args, args=(args + moreargs))
                tree.args = self.visit(tree.args)

                # The body sees the parameters and any new nonlocals
                args += moreargs
                nonlocals = newnonlocals
                newbody = []
                for stmt in tree.body:
                    self.withstate(stmt, args=args, localvars=localvars, nonlocals=nonlocals)
                    stmt = self.visit(stmt)
                    # TODO: should we allow the custom transformer to return a list of statements, too?
                    if stmt:  # allow deletions by the custom transformer
                        newbody.append(stmt)
                    # new local variables come into scope at the next statement (not yet on the RHS of the assignment).
                    # TODO: Nonsense, scoping is a purely lexical thing. Fix this.
                    newlocalvars = uniqify(get_names_in_store_context(stmt))
                    newlocalvars = [x for x in newlocalvars if x not in nonlocals]
                    if newlocalvars:
                        localvars = localvars + newlocalvars
                    # deletions of local vars also take effect from the next statement
                    deletedlocalvars = uniqify(get_names_in_del_context(stmt))
                    # ignore deletion of nonlocals (too dynamic for a static analysis to make sense)
                    deletedlocalvars = [x for x in deletedlocalvars if x not in nonlocals]
                    if deletedlocalvars:
                        localvars = [x for x in localvars if x not in deletedlocalvars]
                tree.body[:] = newbody  # avoid changing the id()
                return tree
            names_in_scope = args + localvars + nonlocals
            tree = callback(tree, names_in_scope)
            if tree:  # allow deletions by the custom transformer
                return self.generic_visit(tree)
    return ScopedTransformer(args=[], localvars=[], nonlocals=[]).visit(tree)

def get_lexical_variables(tree, collect_locals=True):
    """In a tree representing a lexical scope, get names currently in scope.

    An AST node represents a scope if ``isnewscope(tree)`` returns ``True``.

    `collect_locals` affects how this analyzes ``FunctionDef`` and
    ``AsyncFunctionDef`` nodes.

    We collect:

        - formal parameter names of ``Lambda``, ``FunctionDef``, ``AsyncFunctionDef``,
          plus:

            - function name of ``FunctionDef``, ``AsyncFunctionDef``

            - any names declared ``nonlocal`` or ``global`` in a ``FunctionDef``
              or ``AsyncFunctionDef``

            - For ``FunctionDef``, ``AsyncFunctionDef``: if `collect_locals` is `True`,
              any names from assignment LHSs in the function body.

              This means that the `collect_locals=True` mode leads to a purely static
              (i.e. purely lexical) analysis. Any local name defined anywhere in the
              function body is considered to be in scope. (In parts of the scope,
              the name may still be unbound; see Python's `UnboundLocalError`.)

              If `collect_locals` is `False`, assignment LHSs are ignored. It is then
              the caller's responsibility to perform the appropriate dynamic analysis,
              although doing so doesn't fully make sense. See `scoped_transform` for an
              example of how to do that.

        - names of comprehension targets in ``ListComp``, ``SetComp``,
          ``GeneratorExp``, ``DictComp``

        - class name and base class names of ``ClassDef``

            - **CAUTION**: base class scan currently only supports bare ``Name`` nodes

    Return value is (``args``, ``nonlocals``), where each component is a ``list``
    of ``str``. The list ``nonlocals`` contains names declared ``nonlocal`` or
    ``global`` in (precisely) this scope; the list ``args`` contains everything
    else.

    In the context of `unpythonic`, the names returned by this function are
    exactly those that shadow names in an `unpythonic.env.env` in the `let`
    and `do` constructs. They be shadowed by e.g. real lexical variables
    (created by assignment), formal parameters of function definitions,
    or names declared ``nonlocal`` or ``global``.
    """
    if not isnewscope(tree):
        raise TypeError(f"Expected a tree representing a lexical scope, got {type(tree)}")

    if type(tree) in (Lambda, FunctionDef, AsyncFunctionDef):
        a = tree.args
        allargs = a.args + a.kwonlyargs
        if hasattr(a, "posonlyargs"):  # Python 3.8+: positional-only arguments
            allargs += a.posonlyargs
        argnames = [x.arg for x in allargs]
        if a.vararg:
            argnames.append(a.vararg.arg)
        if a.kwarg:
            argnames.append(a.kwarg.arg)

        fname = []
        localvars = []
        nonlocals = []
        if type(tree) in (FunctionDef, AsyncFunctionDef):
            fname = [tree.name]

            if collect_locals:
                localvars = list(uniqify(get_names_in_store_context(tree.body)))

            class NonlocalsCollector(ASTVisitor):
                def examine(self, tree):
                    if type(tree) in (Global, Nonlocal):
                        for x in tree.names:
                            self.collect(x)
                    if not isnewscope(tree):
                        self.generic_visit(tree)
            nc = NonlocalsCollector()
            nc.visit(tree.body)
            nonlocals = nc.collected

        return list(uniqify(fname + argnames + localvars)), list(uniqify(nonlocals))

    elif type(tree) is ClassDef:
        cname = [tree.name]
        # TODO: Base class scan currently only supports bare ``Name`` nodes.
        # TODO: Not clear what we should do if a base is an ``Attribute``
        # TODO: (``mymod.myclass``) or a ``Subscript`` (``my_list_of_classes[0]``).
        bases = [b.id for b in tree.bases if type(b) is Name]
        # these are referred to via self.foo, not by bare names.
#        classattrs = get_names_in_store_context(tree.body)
#        methods = [f.name for f in tree.body if type(f) is FunctionDef]
        return list(uniqify(cname + bases)), []

    elif type(tree) in (ListComp, SetComp, GeneratorExp, DictComp):
        # In the scoping of the generators in a comprehension in Python,
        # there is an important subtlety. Quoting from `analyze_comprehension`
        # in `pyan3/pyan/analyzer.py`:
        #
        #   The outermost iterator is evaluated in the current scope;
        #   everything else in the new inner scope.
        #
        #   See function symtable_handle_comprehension() in
        #     https://github.com/python/cpython/blob/master/Python/symtable.c
        #   For how it works, see
        #     https://stackoverflow.com/questions/48753060/what-are-these-extra-symbols-in-a-comprehensions-symtable
        #   For related discussion, see
        #     https://bugs.python.org/issue10544
        #
        # This doesn't affect us in this particular function, though,
        # because we're only interested in collecting the names of
        # targets defined at the level of this particular `tree`.
        #
        # So, for example, if we're analyzing a `ListComp`, the
        # targets *at that level* will be in scope *for that ListComp*
        # (and any nested listcomps, which is why we provide the
        # `scoped_transform`.)
        targetnames = []
        for g in tree.generators:
            if type(g.target) is Name:
                targetnames.append(g.target.id)
            elif type(g.target) is Tuple:
                class NamesCollector(ASTVisitor):
                    def examine(self, tree):
                        if type(tree) is Name:
                            self.collect(tree.id)
                        self.generic_visit(tree)
                nc = NamesCollector()
                nc.visit(g.target)
                targetnames.extend(nc.collected)
            else:  # pragma: no cover
                raise SyntaxError(f"Scope analyzer: unimplemented: comprehension target of type {type(g.target)}")

        return list(uniqify(targetnames)), []

    assert False  # cannot happen  # pragma: no cover

def get_names_in_store_context(tree):
    """In a tree representing a statement, get names bound by that statement.

    This includes:

        - Any ``Name`` in store context (such as on the LHS of an `Assign`
          or `NamedExpr` node)

        - The name of ``FunctionDef``, ``AsyncFunctionDef`` or``ClassDef``

        - The target(s) of ``For``

        - The names (or asnames where applicable) of ``Import``

        - The exception name of any ``except`` handlers

        - The names in the as-part of ``With``

    Duplicates may be returned; use ``set(...)`` or ``list(uniqify(...))``
    on the output to remove them.

    This stops at the boundary of any nested scopes.

    To find out new local vars, exclude any names in ``nonlocals`` as returned
    by ``get_lexical_variables`` for the nearest lexically surrounding parent
    tree that represents a scope.
    """
    class StoreNamesCollector(ASTVisitor):
        # def _collect_name_or_list(self, t):
        #     if type(t) is Name:
        #         self.collect(t.id)
        #     elif type(t) in (Tuple, List):
        #         for x in t.elts:
        #             _collect_name_or_list(x)
        #     else:
        #         raise SyntaxError(f"Scope analyzer: unimplemented: collect names from type {type(t)}")

        def examine(self, tree):
            # https://docs.python.org/3/reference/executionmodel.html#binding-of-names
            # Useful article: http://excess.org/article/2014/04/bar-foo/
            if type(tree) in (FunctionDef, AsyncFunctionDef, ClassDef):
                self.collect(tree.name)
            # We don't need to handle for loops specially; the targets are Name nodes in Store context.
            # elif type(tree) in (For, AsyncFor):
            #     self._collect_name_or_list(tree.target)
            elif type(tree) in (Import, ImportFrom):
                for x in tree.names:
                    self.collect(x.asname if x.asname is not None else x.name)
            elif type(tree) is Try:
                # https://docs.python.org/3/reference/compound_stmts.html#the-try-statement
                #
                # TODO: The `err` in  `except SomeException as err` is only bound within the `except` block,
                # TODO: not elsewhere in the parent scope. But we don't have the machinery to make that distinction,
                # TODO: so for now we pretend it's bound in the whole parent scope. Usually the same name is not
                # TODO: used for anything else in the same scope, so in practice this (although wrong) is often fine.
                #
                # TODO: We can't cheat by handling `Try` as a new scope, because any other name bound inside the
                # TODO: `try`, even inside the `except` blocks, will be bound in the whole parent scope.
                for h in tree.handlers:
                    self.collect(h.name)
            # Same note as for for loops.
            # elif type(tree) in (With, AsyncWith):
            #     for item in tree.items:
            #         if item.optional_vars is not None:
            #             self._collect_name_or_list(item.optional_vars)
            # macro-created nodes might not have a ctx, but our macros don't create lexical assignments.
            if type(tree) is Name and hasattr(tree, "ctx") and type(tree.ctx) is Store:
                self.collect(tree.id)
            if not isnewscope(tree):
                self.generic_visit(tree)
    nc = StoreNamesCollector()
    nc.visit(tree)
    return nc.collected

def get_names_in_del_context(tree):
    """In a tree representing a statement, get names in del context.

    **Note**: This is intended for static analysis of lexical variables.
    We detect `del x` only, ignoring `del o.x` and `del d['x']`, because
    those don't delete the lexical variables `o` and `d`.
    """
    class DelNamesCollector(ASTVisitor):
        def examine(self, tree):
            # We want to detect things like "del x":
            #     Delete(targets=[Name(id='x', ctx=Del()),])
            # We don't currently care about "del myobj.x" or "del mydict['x']" (these examples in Python 3.6):
            #     Delete(targets=[Attribute(value=Name(id='myobj', ctx=Load()), attr='x', ctx=Del()),])
            #     Delete(targets=[Subscript(value=Name(id='mydict', ctx=Load()), slice=Index(value=Str(s='x')), ctx=Del()),])
            if type(tree) is Name and hasattr(tree, "ctx") and type(tree.ctx) is Del:
                self.collect(tree.id)
            if not isnewscope(tree):
                self.generic_visit(tree)
    nc = DelNamesCollector()
    nc.visit(tree)
    return nc.collected
