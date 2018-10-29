#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""unpythonic.syntax: Toto, I've a feeling we're not in Python anymore.

Requires MacroPy (package ``macropy3`` on PyPI).
"""

# TODO:  All macros are defined in this module, because MacroPy (as of 1.1.0b2)
# does not have a mechanism for re-exporting macros defined in another module.

from macropy.core.macros import Macros, macro_stub
from macropy.core.walkers import Walker
from macropy.core.quotes import macros, q, u, ast_literal, name
from macropy.core.hquotes import macros, hq
from macropy.core import Captured
#from macropy.core.cleanup import fill_line_numbers

from functools import partial
from ast import Call, arg, keyword, With, withitem, Tuple, \
                Name, Attribute, Load, BinOp, LShift, \
                Subscript, Index, Slice, ExtSlice, Lambda, List, \
                copy_location, Assign, FunctionDef, ClassDef, \
                ListComp, SetComp, GeneratorExp, DictComp, \
                arguments, If, Num, Return, Expr, IfExp, BoolOp, And, Or, Try, \
                Global, Nonlocal, Store, Del

try:  # Python 3.5+
    from ast import AsyncFunctionDef, AsyncWith
except ImportError:
    NoSuchNodeType = object()
    AsyncFunctionDef = AsyncWith = NoSuchNodeType

from unpythonic.it import flatmap, uniqify, rev
from unpythonic.fun import curry as curryf, _currycall as currycall, identity
from unpythonic.dynscope import dyn
from unpythonic.lispylet import letrec as letrecf, let as letf, \
                                _dlet as dletf, _blet as bletf
from unpythonic.seq import do as dof, begin as beginf
from unpythonic.fup import fupdate
from unpythonic.misc import namelambda
from unpythonic.tco import trampolined, jump

# insist, deny are just for passing through to the using module that imports us.
from unpythonic.amb import forall as forallf, choice as choicef, insist, deny
from unpythonic.amb import List as MList  # list monad

macros = Macros()

# -----------------------------------------------------------------------------

def _implicit_do(tree):
    """Allow a sequence of expressions in expression position.

    To represent a sequence of expressions, use brackets::

        [expr0, ...]

    To represent a single literal list where this is active, use an extra set
    of brackets::

        [[1, 2, 3]]

    The outer brackets enable multiple-expression mode, and the inner brackets
    are then interpreted as a list.
    """
    return do.transform(tree) if type(tree) is List else tree

def _isec(tree, known_ecs):
    """Check if tree is a call to a function known to be an escape continuation.

    known_ec: list of str, names of known escape continuations.

    Only bare-name references are supported.
    """
    return type(tree) is Call and type(tree.func) is Name and tree.func.id in known_ecs

def _isx(tree, x, allow_attr=True):
    """Check if tree is a reference to an object by the name ``x`` (str).

    ``x`` is recognized both as a bare name and as an attribute, to support
    both from-imports and regular imports of ``somemodule.x``.

    Additionally, we detect ``x`` inside ``Captured`` nodes, which may be
    inserted during macro expansion.

    allow_attr: can be set to ``False`` to disregard ``Attribute`` nodes.
    """
    # WTF, so sometimes there **is** a Captured node, while sometimes there isn't (_islet)? When are these removed?
    # Captured nodes only come from here, and here we use bare names;
    # but explicit references may use either bare names or somemodule.f.
    return (type(tree) is Name and tree.id == x) or \
           (type(tree) is Captured and tree.name == x) or \
           (allow_attr and type(tree) is Attribute and tree.attr == x)

@Walker
def _detect_callec(tree, *, collect, **kw):
    """Collect names of escape continuations from call_ec invocations in tree.

    Currently supported and unsupported cases::

        # use as decorator, supported
        @call_ec
        def result(ec):  # <-- we grab name "ec" from here
            ...

        # use directly on a literal lambda, supported
        result = call_ec(lambda ec: ...)  # <-- we grab name "ec" from here

        # use as a function, **NOT supported**
        def g(ec):           # <-- should grab from here
            ...
        ...
        result = call_ec(g)  # <-- but this is here; g could be in another module
    """
    iscallec = partial(_isx, x="call_ec")
    # TODO: add support for general use of call_ec as a function (difficult)
    if type(tree) in (FunctionDef, AsyncFunctionDef) and any(iscallec(deco) for deco in tree.decorator_list):
        fdef = tree
        collect(fdef.args.args[0].arg)  # FunctionDef.arguments.(list of arg objects).arg
    # TODO: decorated lambdas with other decorators in between
    elif type(tree) is Call and iscallec(tree.func) and type(tree.args[0]) is Lambda:
        lam = tree.args[0]
        collect(lam.args.args[0].arg)
    return tree

# TODO: currently no "syntax-parameterize" in MacroPy. Would be convenient to
# create a macro that expands to an error by default, and then override it
# inside an aif.
#
# We could just leave "it" undefined by default, but IDEs are happier if the
# name exists, and this also gives us a chance to provide a docstring.
class it:
    """[syntax] The result of the test in an aif.

    Only meaningful inside the ``then`` and ``otherwise`` branches of an aif.
    """
    def __repr__(self):  # in case one of these ends up somewhere at runtime
        return "<aif it>"
it = it()

@macros.expr
def aif(tree, **kw):
    """[syntax, expr] Anaphoric if.

    Usage::

        aif[test, then, otherwise]

        aif[[pre, ..., test],
            [post_true, ..., then],        # "then" branch
            [post_false, ..., otherwise]]  # "otherwise" branch

    Inside the ``then`` and ``otherwise`` branches, the magic identifier ``it``
    (which is always named literally ``it``) refers to the value of ``test``.

    This expands into a ``let`` and an expression-form ``if``.

    Each part may consist of multiple expressions by using brackets around it.
    To represent a single expression that is a literal list, use extra
    brackets: ``[[1, 2, 3]]``.
    """
    test, then, otherwise = [_implicit_do(x) for x in tree.elts]
    body = q[ast_literal[then] if it else ast_literal[otherwise]]
    body = copy_location(body, tree)
    bindings = [q[(it, ast_literal[test])]]
    return let.transform(body, *bindings)

# -----------------------------------------------------------------------------

@macros.expr
def cond(tree, **kw):
    """[syntax, expr] Lispy cond; like "a if p else b", but has "elif".

    Usage::

        cond[test1, then1,
             test2, then2,
             ...
             otherwise]

        cond[[pre1, ..., test1], [post1, ..., then1],
             [pre2, ..., test2], [post2, ..., then2],
             ...
             [postn, ..., otherwise]]

    This allows human-readable multi-branch conditionals in a lambda.

    Each part may consist of multiple expressions by using brackets around it.
    To represent a single expression that is a literal list, use extra
    brackets: ``[[1, 2, 3]]``.
    """
    if type(tree) is not Tuple:
        assert False, "Expected cond[test1, then1, test2, then2, ..., otherwise]"
    def build(elts):
        if len(elts) == 1:  # final "otherwise" branch
            return _implicit_do(elts[0])
        if not elts:
            assert False, "Expected cond[test1, then1, test2, then2, ..., otherwise]"
        test, then, *more = elts
        test = _implicit_do(test)
        then = _implicit_do(then)
        return hq[ast_literal[then] if ast_literal[test] else ast_literal[build(more)]]
    return build(tree.elts)

# -----------------------------------------------------------------------------

@macros.block
def curry(tree, **kw):  # technically a list of trees, the body of the with block
    """[syntax, block] Automatic currying.

    Usage::

        from unpythonic.syntax import macros, curry

        with curry:
            ...

    All **function calls** and **function definitions** (``def``, ``lambda``)
    *lexically* inside the ``with curry`` block are automatically curried.

    **CAUTION**: Some builtins are uninspectable or may report their arities
    incorrectly; in those cases, ``curry`` may fail, occasionally in mysterious
    ways.

    The function ``unpythonic.arity.arities``, which ``unpythonic.fun.curry``
    internally uses, has a workaround for the inspectability problems of all
    builtins in the top-level namespace (as of Python 3.7), but e.g. methods
    of builtin types are not handled.

    In a ``with curry`` block, ``unpythonic.fun.curry`` runs in a special mode
    that no-ops on uninspectable functions instead of raising ``TypeError``
    as usual. This special mode is enabled for the *dynamic extent* of the
    ``with curry`` block.

    Example::

        from unpythonic.syntax import macros, curry
        from unpythonic import foldr, composerc as compose, cons, nil, ll

        with curry:
            def add3(a, b, c):
                return a + b + c
            assert add3(1)(2)(3) == 6
            assert add3(1, 2)(3) == 6
            assert add3(1)(2, 3) == 6
            assert add3(1, 2, 3) == 6

            mymap = lambda f: foldr(compose(cons, f), nil)
            double = lambda x: 2 * x
            assert mymap(double, ll(1, 2, 3)) == ll(2, 4, 6)

        # The definition was auto-curried, so this works here too.
        # (Provided add3 contains no calls to uninspectable functions, since
        #  we are now outside the dynamic extent of the ``with curry`` block.)
        assert add3(1)(2)(3) == 6
    """
    @Walker
    def transform_call(tree, *, stop, **kw):  # technically a node containing the current subtree
        if type(tree) is Call:
            tree.args = [tree.func] + tree.args
            tree.func = hq[currycall]
        elif type(tree) in (FunctionDef, AsyncFunctionDef):
            # @curry must run before @trampolined, so put it on the inside
            tree.decorator_list = tree.decorator_list + [hq[curryf]]
        elif type(tree) is Lambda:
            # This inserts curry() as the innermost "decorator", and the curry
            # macro is meant to run last (after e.g. tco), so we're fine.
            tree = hq[curryf(ast_literal[tree])]
            # don't recurse on the lambda we just moved, but recurse inside it.
            stop()
            tree.args[0].body = transform_call.recurse(tree.args[0].body)
        return tree
    body = transform_call.recurse(tree)
    # Wrap the body in "with dyn.let(_curry_allow_uninspectable=True):"
    # to avoid crash with uninspectable builtins
    item = hq[dyn.let(_curry_allow_uninspectable=True)]
    wrapped = With(items=[withitem(context_expr=item, optional_vars=None)],
                   body=body)
    return [wrapped]  # block macro: got a list, must return a list.

# -----------------------------------------------------------------------------

# This simple classical lambda-based let works, but does not support assignment,
# so it can't be used for things like let-over-lambda, or indeed letrec.
# But it's simple, and creates real lexical variables.

# These are here mainly for documentation purposes; the other macros are designed
# to work together with the regular "let", "letseq", "letrec", not these ones.

@macros.expr
def simple_let(tree, args, **kw):  # args; ast.Tuple: (k1, v1), (k2, v2), ..., (kn, vn)
    """[syntax, expr] Introduce local bindings, as real lexical variables.

    Usage::

        simple_let(bindings)[body]

    where ``bindings`` is a comma-separated sequence of pairs ``(name, value)``
    and ``body`` is an expression. The names bound by ``simple_let`` are local;
    they are available in ``body``, and do not exist outside ``body``.

    Each ``name`` in the same ``simple_let`` must be unique.

    Example::

        from unpythonic.syntax import macros, simple_let

        simple_let((x, 40))[print(x+2)]

    ``simple_let`` expands into a ``lambda``::

        simple_let((x, 1), (y, 2))[print(x, y)]
        # --> (lambda x, y: print(x, y))(1, 2)
    """
    names  = [k.id for k, _ in (a.elts for a in args)]
    if len(set(names)) < len(names):
        assert False, "binding names must be unique in the same simple_let"
    values = [v for _, v in (a.elts for a in args)]
    lam = q[lambda: ast_literal[tree]]
    lam.args.args = [arg(arg=x) for x in names]  # inject args
    return q[ast_literal[lam](ast_literal[values])]

@macros.expr
def simple_letseq(tree, args, **kw):
    """[syntax, expr] Let with sequential binding (like Scheme/Racket let*).

    Like ``simple_let``, but bindings take effect sequentially. Later bindings
    shadow earlier ones if the same name is used multiple times.

    Expands to nested ``simple_let`` expressions.
    """
    if not args:
        return tree
    first, *rest = args
    return simple_let.transform(simple_letseq.transform(tree, *rest), first)

# -----------------------------------------------------------------------------

# Sugar around unpythonic.lispylet. We take this approach because letrec
# needs assignment (must create placeholder bindings, then update them
# with the real value)... but in Python, assignment is a statement.
#
# As a bonus, we get assignment for let and letseq, too.
#
@macros.expr
def let(tree, args, gen_sym, **kw):
    """[syntax, expr] Introduce local bindings.

    This is sugar on top of ``unpythonic.lispylet.let``.

    Usage::

        let(bindings)[body]
        let(bindings)[[body0, ...]]

    where ``bindings`` is a comma-separated sequence of pairs ``(name, value)``
    and ``body`` is an expression. The names bound by ``let`` are local;
    they are available in ``body``, and do not exist outside ``body``.

    For a body with multiple expressions, use an extra set of brackets.
    This inserts a ``do``. Only the outermost extra brackets are interpreted
    specially; all others in the bodies are interpreted as usual, as lists.

    Each ``name`` in the same ``let`` must be unique.

    Assignment to let-bound variables is supported with syntax such as ``x << 42``.
    This is an expression, performing the assignment, and returning the new value.

    In a multiple-expression body, also an internal definition context exists
    for local variables that are not part of the ``let``; see ``do`` for details.

    Technical points:

        - In reality, the let-bound variables live in an ``unpythonic.env``.
          This macro performs the magic to make them look (and pretty much behave)
          like lexical variables.

        - Compared to ``unpythonic.lispylet.let``, the macro version needs no quotes
          around variable names in bindings.

        - The body is automatically wrapped in a ``lambda e: ...``.

        - For all ``x`` in bindings, the macro transforms ``x --> e.x``.

        - Lexical scoping is respected (so ``let`` constructs can be nested)
          by actually using a unique name (gensym) instead of just ``e``.

        - In the case of a multiple-expression body, the ``do`` transformation
          is applied first to ``[body0, ...]``, and the result becomes ``body``.
    """
    return _letimpl(tree, args, "let", gen_sym)

@macros.expr
def letseq(tree, args, **kw):
    """[syntax, expr] Let with sequential binding (like Scheme/Racket let*).

    Like ``let``, but bindings take effect sequentially. Later bindings
    shadow earlier ones if the same name is used multiple times.

    Expands to nested ``let`` expressions.
    """
    if not args:
        return tree
    first, *rest = args
    return let.transform(letseq.transform(tree, *rest), first)

@macros.expr
def letrec(tree, args, gen_sym, **kw):
    """[syntax, expr] Let with mutually recursive binding.

    Like ``let``, but bindings can see other bindings in the same ``letrec``.

    Each ``name`` in the same ``letrec`` must be unique.

    The definitions are processed sequentially, left to right. A definition
    may refer to any previous definition. If ``value`` is callable (lambda),
    it may refer to any definition, including later ones.

    This is useful for locally defining mutually recursive functions.
    """
    return _letimpl(tree, args, "letrec", gen_sym)

def _islet(tree):
    return type(tree) is Call and _isx(tree.func, "letter", allow_attr=False)

def _letimpl(tree, args, mode, gen_sym):  # args; sequence of ast.Tuple: (k1, v1), (k2, v2), ..., (kn, vn)
    assert mode in ("let", "letrec")

    newtree = _implicit_do(tree)
    if not args:
        return newtree
    names, values = zip(*[a.elts for a in args])  # --> (k1, ..., kn), (v1, ..., vn)
    names = [k.id for k in names]  # any duplicates will be caught by env at run-time

    e = gen_sym("e")
    envset = Attribute(value=q[name[e]], attr="set", ctx=Load())

    t = partial(_letlike_transform, envname=e, lhsnames=names, rhsnames=names, setter=envset)
    if mode == "letrec":
        values = [t(b) for b in values]  # RHSs of bindings
    newtree = t(newtree)  # body

    letter = letf if mode == "let" else letrecf
    binding_pairs = [q[(u[k], ast_literal[v])] for k, v in zip(names, values)]
    return hq[letter((ast_literal[binding_pairs],), ast_literal[newtree])]

def _letlike_transform(tree, envname, lhsnames, rhsnames, setter, dowrap=True):
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
    tree = _transform_envassignment(tree, lhsnames, setter)  # x << val --> e.set('x', val)
    tree = _transform_name(tree, rhsnames, envname)  # x --> e.x  (when x appears in load context)
    if dowrap:
        tree = _envwrap(tree, envname)  # ... -> lambda e: ...
    return tree

def _isenvassign(tree):  # detect "x << 42" syntax to assign variables in an environment
    return type(tree) is BinOp and type(tree.op) is LShift and type(tree.left) is Name
def _envassign_name(tree):  # rackety accessors
    return tree.left.id
def _envassign_value(tree):
    return tree.right

def _isnewscope(tree):
    """Return whether tree introduces a new lexical scope.

    (According to Python's standard scoping rules.)
    """
    return type(tree) in (Lambda, FunctionDef, AsyncFunctionDef, ClassDef, ListComp, SetComp, GeneratorExp, DictComp)

@Walker
def _scoped_walker(tree, *, localvars=[], args=[], nonlocals=[], callback, set_ctx, stop, **kw):
    """Walk and process a tree, keeping track of which names are shadowed.

    Names in an unpythonic env can be shadowed by e.g. real lexical variables,
    formal parameters of function definitions, or names declared ``nonlocal``
    or ``global``. See ``_getshadowers``.

    callback: function, (tree, shadowed_names) --> tree
    """
    # TODO: think about proper handling of ClassDef
    if type(tree) in (Lambda, ListComp, SetComp, GeneratorExp, DictComp, ClassDef):
        moreargs, _ = _getshadowers(tree)
        set_ctx(args=(args + moreargs))
    elif type(tree) in (FunctionDef, AsyncFunctionDef):
        stop()
        moreargs, newnonlocals = _getshadowers(tree)
        args = args + moreargs
        for expr in (tree.args, tree.decorator_list):
            _scoped_walker.recurse(expr, localvars=localvars, args=args, nonlocals=nonlocals, callback=callback)
        nonlocals = newnonlocals
        localvars = []
        for stmt in tree.body:
            _scoped_walker.recurse(stmt, localvars=localvars, args=args, nonlocals=nonlocals, callback=callback)
            # new local variables come into scope at the next statement (not yet on the RHS of the assignment).
            newlocalvars = uniqify(_get_names_in_store_context.collect(stmt))
            newlocalvars = [x for x in newlocalvars if x not in nonlocals]
            if newlocalvars:
                localvars = localvars + newlocalvars
            # deletions of local vars also take effect from the next statement
            deletedlocalvars = uniqify(_get_names_in_del_context.collect(stmt))
            # ignore deletion of nonlocals (too dynamic for a static analysis to make sense)
            deletedlocalvars = [x for x in deletedlocalvars if x not in nonlocals]
            if deletedlocalvars:
                localvars = [x for x in localvars if x not in deletedlocalvars]
        return tree
    shadowed = args + localvars + nonlocals
    return callback(tree, shadowed)

def _getshadowers(tree):
    """In a tree representing a lexical scope, get names that shadow names in unpythonic envs.

    An AST node represents a scope if ``_isnewscope(tree)`` returns ``True``.

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
                if _isnewscope(tree):
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
def _get_names_in_store_context(tree, *, stop, collect, **kw):
    """In a tree representing a statement, get names in store context.

    Additionally, get the name of any ``FunctionDef``, ``AsyncFunctionDef``
    and ``ClassDef``, as these also introduce new names into the scope
    where they appear.

    Duplicates may be returned; use ``set(...)`` or ``list(uniqify(...))``
    on the output to remove them.

    This stops at the boundary of any nested scopes.

    To find out new local vars, exclude any names in ``nonlocals`` as returned
    by ``_getshadowers``.
    """
    if type(tree) in (FunctionDef, AsyncFunctionDef, ClassDef):
        collect(tree.name)
    if _isnewscope(tree):
        stop()
    # macro-created nodes might not have a ctx, but our macros don't create lexical assignments.
    if type(tree) is Name and hasattr(tree, "ctx") and type(tree.ctx) is Store:
        collect(tree.id)
    return tree

@Walker
def _get_names_in_del_context(tree, *, stop, collect, **kw):
    """In a tree representing a statement, get names in del context."""
    if _isnewscope(tree):
        stop()
    # We want to detect things like "del x":
    #     Delete(targets=[Name(id='x', ctx=Del()),])
    # We don't currently care about "del myobj.x" or "del mydict['x']":
    #     Delete(targets=[Attribute(value=Name(id='myobj', ctx=Load()), attr='x', ctx=Del()),])
    #     Delete(targets=[Subscript(value=Name(id='mydict', ctx=Load()), slice=Index(value=Str(s='x')), ctx=Del()),])
    elif type(tree) is Name and hasattr(tree, "ctx") and type(tree.ctx) is Del:
        collect(tree.id)
    return tree

# x << val --> e.set('x', val)  (for names bound in this environment)
def _transform_envassignment(tree, lhsnames, envset):
    def t(tree, shadowed):
        if _isenvassign(tree):
            varname = _envassign_name(tree)
            if varname in lhsnames and varname not in shadowed:
                value = _envassign_value(tree)
                return q[ast_literal[envset](u[varname], ast_literal[value])]
        return tree
    return _scoped_walker.recurse(tree, callback=t)

# x --> e.x  (in load context; for names bound in this environment)
def _transform_name(tree, rhsnames, envname):
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
    return _scoped_walker.recurse(tree, callback=t)

# ... -> lambda e: ...
def _envwrap(tree, envname):
    lam = q[lambda: ast_literal[tree]]
    lam.args.args = [arg(arg=envname)]  # lambda e44: ...
    return lam

# -----------------------------------------------------------------------------

# Decorator versions, for "let over def".

@macros.decorator
def dlet(tree, args, *, gen_sym, **kw):
    """[syntax, decorator] Decorator version of let, for 'let over def'.

    Example::

        @dlet((x, 0))
        def count():
            x << x + 1
            return x
        assert count() == 1
        assert count() == 2

    **CAUTION**: function arguments, local variables, and names declared as
    ``global`` or ``nonlocal`` in a given lexical scope shadow names from the
    ``let`` environment *for the entirety of that lexical scope*. (This is
    modeled after Python's standard scoping rules.)

    **CAUTION**: assignment to the let environment is ``name << value``;
    the regular syntax ``name = value`` creates a local variable.
    """
    return _dletimpl(tree, args, "let", "decorate", gen_sym)

@macros.decorator
def dletrec(tree, args, *, gen_sym, **kw):
    """[syntax, decorator] Decorator version of letrec, for 'letrec over def'.

    Example::

        @dletrec((evenp, lambda x: (x == 0) or oddp(x - 1)),
                 (oddp,  lambda x: (x != 0) and evenp(x - 1)))
        def f(x):
            return evenp(x)
        assert f(42) is True
        assert f(23) is False

    Same cautions apply as to ``dlet``.
    """
    return _dletimpl(tree, args, "letrec", "decorate", gen_sym)

@macros.decorator
def blet(tree, args, *, gen_sym, **kw):
    """[syntax, decorator] def --> let block.

    Example::

        @blet((x, 21))
        def result():
            return 2*x
        assert result == 42
    """
    return _dletimpl(tree, args, "let", "call", gen_sym)
@macros.decorator
def bletrec(tree, args, *, gen_sym, **kw):
    """[syntax, decorator] def --> letrec block.

    Example::

        @bletrec((evenp, lambda x: (x == 0) or oddp(x - 1)),
                 (oddp,  lambda x: (x != 0) and evenp(x - 1)))
        def result():
            return evenp(42)
        assert result is True
    """
    return _dletimpl(tree, args, "letrec", "call", gen_sym)

# Very similar to _letimpl, but perhaps more readable to keep these separate.
def _dletimpl(tree, args, mode, kind, gen_sym):
    assert mode in ("let", "letrec")
    assert kind in ("decorate", "call")
    if type(tree) not in (FunctionDef, AsyncFunctionDef):
        assert False, "Expected a function definition to decorate"
    if not args:
        return tree

    names, values = zip(*[a.elts for a in args])  # --> (k1, ..., kn), (v1, ..., vn)
    names = [k.id for k in names]  # any duplicates will be caught by env at run-time

    e = gen_sym("e")
    envset = Attribute(value=q[name[e]], attr="set", ctx=Load())

    t1 = partial(_letlike_transform, envname=e, lhsnames=names, rhsnames=names, setter=envset)
    t2 = partial(t1, dowrap=False)
    if mode == "letrec":
        values = [t1(b) for b in values]
    tree = t2(tree)

    letter = dletf if kind == "decorate" else bletf
    binding_pairs = [q[(u[k], ast_literal[v])] for k, v in zip(names, values)]
    tree.decorator_list = tree.decorator_list + [hq[letter((ast_literal[binding_pairs],), mode=u[mode], _envname=u[e])]]
    tree.args.kwonlyargs = tree.args.kwonlyargs + [arg(arg=e)]
    tree.args.kw_defaults = tree.args.kw_defaults + [None]
    return tree

@macros.decorator
def dletseq(tree, args, gen_sym, **kw):
    """[syntax, decorator] Decorator version of letseq, for 'letseq over def'.

    Expands to nested function definitions, each with one ``dlet`` decorator.

    Example::

        @dletseq((x, 1),
                 (x, x+1),
                 (x, x+2))
        def g(a):
            return a + x
        assert g(10) == 14
    """
    return _dletseqimpl(tree, args, "decorate", gen_sym)

@macros.decorator
def bletseq(tree, args, gen_sym, **kw):
    """[syntax, decorator] def --> letseq block.

    Example::

        @bletseq((x, 1),
                 (x, x+1),
                 (x, x+2))
        def result():
            return x
        assert result == 4
    """
    return _dletseqimpl(tree, args, "call", gen_sym)

def _dletseqimpl(tree, args, kind, gen_sym):
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
    if type(tree) not in (FunctionDef, AsyncFunctionDef):
        assert False, "Expected a function definition to decorate"
    if not args:
        return tree

    userargs = tree.args  # original arguments to the def
    fname = tree.name
    noargs = arguments(args=[], kwonlyargs=[], vararg=None, kwarg=None,
                          defaults=[], kw_defaults=[])
    iname = gen_sym("{}_inner".format(fname))
    tree.args = noargs
    tree.name = iname

    *rest, last = args
    dletter = dlet if kind == "decorate" else blet
    innerdef = dletter.transform(tree, last)

    # optimization: in the final step, no need to generate a wrapper function
    if not rest:
        tmpargs = innerdef.args
        innerdef.name = fname
        innerdef.args = userargs
        # copy the env arg
        innerdef.args.kwonlyargs += tmpargs.kwonlyargs
        innerdef.args.kw_defaults += tmpargs.kw_defaults
        return innerdef

    ret = Return(value=q[name[iname]()]) if kind == "decorate" else Return(value=q[name[iname]])
    outer = FunctionDef(name=fname, args=userargs,
                        body=[innerdef, ret],
                        decorator_list=[],
                        returns=None)  # no return type annotation
    outer = copy_location(outer, tree)
    return _dletseqimpl(outer, rest, kind, gen_sym)

# -----------------------------------------------------------------------------

# This stuff borrows some of the "let" machinery.

@macros.expr
def do(tree, gen_sym, **kw):
    """[syntax, expr] Stuff imperative code into an expression position.

    Return value is the value of the last expression inside the ``do``.
    See also ``do0``.

    Usage::

        do[body0, ...]

    Example::

        do[localdef(x << 42),
           print(x),
           x << 23,
           x]

    This is sugar on top of ``unpythonic.seq.do``, but with some extra features.

        - To declare and initialize a local name, use ``localdef(name << value)``.

          The operator ``localdef`` is syntax, not really a function, and it
          only exists inside a ``do``.

        - By design, there is no way to create an uninitialized variable;
          a value must be given at declaration time. Just use ``None``
          as an explicit "no value" if needed.

        - Names declared within the same ``do`` must be unique. Re-declaring
          the same name is an expansion-time error.

        - To assign to an already declared local name, use ``name << value``.

    **localdef declarations**

    A ``localdef`` declaration comes into effect in the expression following
    the one where it appears. Thus::

        result = []
        let((lst, []))[do[result.append(lst),          # the let "lst"
                          localdef(lst << lst + [1]),  # LHS: do "lst", RHS: let "lst"
                          result.append(lst)]]         # the do "lst"
        assert result == [[], [1]]

    **Syntactic ambiguity**

    These two cases cannot be syntactically distinguished:

        - Just one body expression, which is a literal tuple or list,

        - Multiple body expressions, represented as a literal tuple or list.

    ``do`` always uses the latter interpretation.

    Whenever there are multiple expressions in the body, the ambiguity does not
    arise, because then the distinction between the sequence of expressions itself
    and its items is clear.

    Examples::

        do[1, 2, 3]   # --> tuple, 3
        do[(1, 2, 3)] # --> tuple, 3 (since in Python, the comma creates tuples;
                      #     parentheses are only used for disambiguation)
        do[[1, 2, 3]] # --> list, 3
        do[[[1, 2, 3]]]  # --> list containing a list, [1, 2, 3]
        do[([1, 2, 3],)] # --> tuple containing a list, [1, 2, 3]
        do[[1, 2, 3],]   # --> tuple containing a list, [1, 2, 3]
        do[[(1, 2, 3)]]  # --> list containing a tuple, (1, 2, 3)
        do[((1, 2, 3),)] # --> tuple containing a tuple, (1, 2, 3)
        do[(1, 2, 3),]   # --> tuple containing a tuple, (1, 2, 3)

    It is possible to use ``unpythonic.misc.pack`` to create a tuple from
    given elements: ``do[pack(1, 2, 3)]`` is interpreted as a single-item body
    that creates a tuple (by calling a function).

    Note the outermost brackets belong to the ``do``; they don't yet create a list.

    In the *use brackets to denote a multi-expr body* syntax (e.g. ``multilambda``,
    ``let`` constructs), the extra brackets already create a list, so in those
    uses, the ambiguity does not arise. The transformation inserts not only the
    word ``do``, but also the outermost brackets. For example::

        let((x, 1),
            (y, 2))[[
              [x, y]]]

    transforms to::

        let((x, 1),
            (y, 2))[do[[  # "do[" is inserted between the two opening brackets
              [x, y]]]]   # and its closing "]" is inserted here

    which already gets rid of the ambiguity.

    **Notes**

    Macros are expanded in an inside-out order, so a nested ``let`` shadows
    names, if the same names appear in the ``do``::

        do[localdef(x << 17),
           let((x, 23))[
             print(x)],  # 23, the "x" of the "let"
           print(x)]     # 17, the "x" of the "do"

    The reason we require local names to be declared is to allow write access
    to lexically outer environments from inside a ``do``::

        let((x, 17))[
              do[x << 23,            # no localdef; update the "x" of the "let"
                 localdef(y << 42),  # "y" is local to the "do"
                 print(x, y)]]

    With the extra bracket syntax, the latter example can be written as::

        let((x, 17))[[
              x << 23,
              localdef(y << 42),
              print(x, y)]]

    It's subtly different in that the first version has the do-items in a tuple,
    whereas this one has them in a list, but the behavior is exactly the same.

    Python does it the other way around, requiring a ``nonlocal`` statement
    to re-bind a name owned by an outer scope.

    The ``let`` constructs solve this problem by having the local bindings
    declared in a separate block, which plays the role of ``localdef``.
    """
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
    envset.body = let.transform(letbody,
                                q[(name["v"], name[expr])])

    def islocaldef(tree):
        return type(tree) is Call and type(tree.func) is Name and tree.func.id == "localdef"
    @Walker
    def _find_localdefs(tree, collect, **kw):
        if islocaldef(tree):
            if len(tree.args) != 1:
                assert False, "localdef(...) must have exactly one positional argument"
            expr = tree.args[0]
            if not _isenvassign(expr):
                assert False, "localdef(...) argument must be of the form 'name << value'"
            collect(_envassign_name(expr))
            return expr  # localdef(...) -> ..., the localdef has done its job
        return tree

    # a localdef starts taking effect on the line where it appears
    names = []
    lines = []
    for expr in tree.elts:
        expr, newnames = _find_localdefs.recurse_collect(expr)
        if newnames:
            if any(x in names for x in newnames):
                assert False, "localdef names must be unique in the same do"
        # The envassignment transform (LHS) needs also "newnames", whereas
        # the name transform (RHS) should use the previous bindings, so that
        # the new binding takes effect starting from the **next** doitem.
        expr = _letlike_transform(expr, e, names + newnames, names, envset)
        names = names + newnames
        lines.append(expr)
    return hq[dof(ast_literal[lines])]

@macros.expr
def do0(tree, **kw):
    """[syntax, expr] Like do, but return the value of the first expression."""
    if type(tree) not in (Tuple, List):
        assert False, "do0 body: expected a sequence of comma-separated expressions"
    elts = tree.elts
    newelts = []  # IDE complains about _do0_result, but it's quoted, so it's ok.
    newelts.append(q[name["localdef"](name["_do0_result"] << (ast_literal[elts[0]]))])
    newelts.extend(elts[1:])
    newelts.append(q[name["_do0_result"]])
    newtree = q[(ast_literal[newelts],)]
    newtree = copy_location(newtree, tree)
    return do.transform(newtree)  # do0[] is also just a do[]

def _isdo(tree):
    # TODO: what about the fact it's a hq[dof(...)]? No Captured node?
    return type(tree) is Call and type(tree.func) is Name and tree.func.id == "dof"

# -----------------------------------------------------------------------------

# TODO: remove forall, replace with forall_simple

@macros.expr
def forall(tree, gen_sym, **kw):
    """[syntax, expr] Nondeterministic evaluation.

    Sugar on top of ``unpythonic.amb.forall``.

      - ``choice("x", iterable)`` becomes ``x << iterable``
      - ``insist``, ``deny`` work as usual
      - no need for ``lambda e: ...`` wrappers

    Example::

        # pythagorean triples
        pt = forall[z << range(1, 21),   # hypotenuse
                    x << range(1, z+1),  # shorter leg
                    y << range(x, z+1),  # longer leg
                    insist(x*x + y*y == z*z),
                    (x, y, z)]
        assert tuple(sorted(pt)) == ((3, 4, 5), (5, 12, 13), (6, 8, 10),
                                     (8, 15, 17), (9, 12, 15), (12, 16, 20))
    """
    if type(tree) is not Tuple:
        assert False, "forall body: expected a sequence of comma-separated expressions"
    body = tree.elts
    e = gen_sym("e")
    names = []  # variables bound by this forall
    lines = []
    def transform(tree):  # as _letlike_transform but no assignment conversion
        tree = _transform_name(tree, names, e)  # x --> e.x
        return _envwrap(tree, envname=e)  # ... -> lambda e: ...
    chooser = hq[choicef]
    for line in body:
        if _isenvassign(line):  # convert "<<" assignments, but only at top level
            k, v = line.left.id, transform(line.right)
            binding = keyword(arg=k, value=v)
            names.append(k)  # bind k to e.k for all following lines
            lines.append(Call(func=chooser, args=[], keywords=[binding]))
        else:
            lines.append(transform(line))
    return hq[forallf(ast_literal[lines])]

@macros.expr
def forall_simple(tree, **kw):
    """[syntax, expr] Nondeterministic evaluation.

    Fully based on AST transformation, with real lexical variables.
    Like Haskell's do-notation, but here specialized for the List monad.

    Usage is the same as ``forall``.
    """
    if type(tree) is not Tuple:
        assert False, "forall body: expected a sequence of comma-separated expressions"
    def build(lines, tree):
        if not lines:
            return tree
        line, *rest = lines
        if _isenvassign(line):
            k, v = _envassign_name(line), _envassign_value(line)
        else:
            k, v = "_ignored", line
        islast = not rest
        # don't unpack on last line to allow easily returning a tuple as a result item
        Mv = hq[_monadify(ast_literal[v], u[not islast])]
        if not islast:
            body = q[ast_literal[Mv] >> (lambda: name["_here_"])]  # monadic bind: >>
            body.right.args.args = [arg(arg=k)]
        else:
            body = Mv
        if tree:
            @Walker
            def splice(tree, *, stop, **kw):
                if type(tree) is Name and tree.id == "_here_":
                    stop()
                    return body
                return tree
            newtree = splice.recurse(tree)
        else:
            newtree = body
        return build(rest, newtree)
    return hq[tuple(ast_literal[build(tree.elts, None)])]

def _monadify(value, unpack=True):
    if isinstance(value, MList):
        return value
    elif unpack:
        try:
            return MList.from_iterable(value)
        except TypeError:
            pass  # fall through
    return MList(value)  # unit(List, value)

# -----------------------------------------------------------------------------

@macros.block
def multilambda(tree, **kw):
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

            count = let((x, 0))[
                      lambda: [x << x + 1,
                               x]]
            assert count() == 1
            assert count() == 2

            mk12 = lambda: [[1, 2]]
            assert mk12() == [1, 2]

    For local variables, see ``do``.
    """
    @Walker
    def transform(tree, *, stop, **kw):
        if type(tree) is not Lambda or type(tree.body) is not List:
            return tree
        bodys = tree.body
        # bracket magic:
        # - stop() to prevent recursing to the implicit lambdas generated
        #   by the "do" we are inserting here
        #   - for each item, "do" internally inserts a lambda to delay execution,
        #     as well as to bind the environment
        #   - we must do.transform() instead of hq[do[...]] for pickling reasons
        # - but recurse manually into each *do item*; these are explicit
        #   user-provided code so we should transform them
        stop()
        bodys = transform.recurse(bodys)
        tree.body = do.transform(bodys)  # insert the do, with the implicit lambdas
        return tree
    # multilambda should expand first before any let[], do[] et al. that happen
    # to be inside the block, to avoid misinterpreting implicit lambdas.
    yield transform.recurse(tree)

@macros.block
def namedlambda(tree, **kw):
    """[syntax, block] Implicitly named lambdas.

    Lexically inside a ``with namedlambda`` block, any literal ``lambda``
    that is assigned to a name using a simple assignment of the form
    ``f = lambda ...: ...``, is named as "f (lambda)", where the name ``f``
    is captured from the assignment statement at macro expansion time.

    For capturing the name, the assignment must be of a single ``lambda`` value
    to a single name; other forms of assignment are not supported. (This may be
    subject to change in a future version.)

    Additionally, during the dynamic extent of the ``with namedlambda`` block,
    assigning a lambda to a name in an ``unpythonic.env`` instance will cause
    that lambda to be named, capturing the name it is assigned to in the env.
    This is performed at run time.

    Naming modifies the original function object (specifically, its ``__name__``
    and ``__qualname__`` attributes). The name is set only once per object, so in::

        with namedlambda:
            f = lambda x: x**3        # lexical rule: name as "f"

            let((x, 42), (g, None), (h, None))[[
              g << (lambda x: x**2),  # dynamic rule: name as "g"
              h << f,                 # no-rename rule: still "f"
              (g(x), h(x))]]

    the name of the first lambda will be set as ``f``, and it will remain as ``f``
    even after the name ``h`` is made to point to the same object inside the
    body of the ``let``.
    """
    def issingleassign(tree):
        return type(tree) is Assign and len(tree.targets) == 1 and type(tree.targets[0]) is Name

    @Walker
    def transform(tree, *, stop, **kw):
        if issingleassign(tree) and type(tree.value) is Lambda:
            # an assignment is a statement, so in the transformed tree,
            # we are free to use all of Python's syntax.
            myname = tree.targets[0].id
            value = tree.value
            # trick from MacroPy: to replace one statement with multiple statements,
            # use an "if 1:" block; the Python compiler optimizes it away.
            with hq as newtree:
                if 1:
#                    ast_literal[tree]   # TODO: doesn't work, why?
                    name[myname] = ast_literal[value]  # do the same thing as ast_literal[tree] should
                    namelambda(name[myname], u[myname])
            stop()  # prevent infinite loop
            return newtree[0]  # the if statement
        return tree

    newtree = [transform.recurse(stmt) for stmt in tree]

#    # TODO: this syntax doesn't work due to missing line numbers?
#    with q as wrapped:  # name lambdas also in env
#        with dyn.let(env_namedlambda=True):
#            ast_literal[newtree]
#    return wrapped

    # name lambdas also in env
    item = hq[dyn.let(env_namedlambda=True)]
    wrapped = With(items=[withitem(context_expr=item, optional_vars=None)],
                   body=newtree)
    return [wrapped]

# -----------------------------------------------------------------------------

# TODO: improve: multiple fupdate specs?
@macros.expr
def fup(tree, **kw):
    """[syntax, expr] Functionally update a sequence.

    Example::

        from itertools import repeat

        lst = (1, 2, 3, 4, 5)
        assert fup[lst[3] << 42] == (1, 2, 3, 42, 5)
        assert fup[lst[0::2] << tuple(repeat(10, 3))] == (10, 2, 10, 4, 10)

    The transformation is::

        fup[seq[idx] << value] --> fupdate(seq, idx, value)
        fup[seq[slicestx] << iterable] --> fupdate(seq, slice(...), iterable)

    Limitations:

      - Currently only one update specification is supported in a single ``fup[]``.

    Named after the sound a sequence makes when it is hit by a functional update.
    """
    valid = type(tree) is BinOp and type(tree.op) is LShift and type(tree.left) is Subscript
    if not valid:
        assert False, "fup: expected seq[idx_or_slice] << val"
    seq, idx, val = tree.left.value, tree.left.slice, tree.right

    if type(idx) is ExtSlice:
        assert False, "fup: multidimensional indexing not supported"
    elif type(idx) is Slice:
        start, stop, step = [x or q[None] for x in (idx.lower, idx.upper, idx.step)]
        idxspec = hq[slice(ast_literal[start], ast_literal[stop], ast_literal[step])]
    elif type(idx) is Index:
        idxspec = idx.value
        if idxspec is None:
            assert False, "indices must be integers, not NoneType"

    return hq[fupdate(ast_literal[seq], ast_literal[idxspec], ast_literal[val])]

# -----------------------------------------------------------------------------

@macros.block
def continuations(tree, gen_sym, **kw):
    """[syntax, block] Semi-implicit continuations.

    Roughly, this allows saving the control state and then jumping back later
    (in principle, any time later). Possible use cases:

      - Tree traversal (possibly a cartesian product of multiple trees, with the
        current position in each tracked automatically).

      - McCarthy's amb operator.

    This is a loose pythonification of Paul Graham's continuation-passing macros,
    which implement continuations by chaining closures and passing the continuation
    semi-implicitly. For details, see chapter 20 in On Lisp:

        http://paulgraham.com/onlisp.html

    Continuations are most readily implemented when the program is written in
    continuation-passing style (CPS), but that is unreadable for humans.
    The purpose of this macro is to partly automate the CPS transformation,
    so that at the use site, we can write CPS code in a much more readable fashion.

    To combo with multilambda, use this ordering::

        with multilambda, continuations:
            ...

    A ``with continuations`` block implies TCO; the same rules apply as in a
    ``with tco`` block. Furthermore, ``with continuations`` introduces the
    following additional rules:

      - Functions which make use of continuations, or call other functions that do,
        must be defined within a ``with continuations`` block, using ``def``
        or ``lambda``.

      - All function definitions in a ``with continuations`` block, including
        any nested definitions, must declare a by-name-only formal parameter
        ``cc``::

            with continuations:
                def myfunc(*, cc):
                    ...

                    f = lambda *, cc: ...

      - A ``with continuations`` block will automatically transform all ``def``
        function definitions and ``return`` statements lexically contained within
        it to use the continuation machinery.

        - ``return somevalue`` actually means a tail-call to ``cc`` with the
          given ``somevalue``. Multiple values can be returned as a ``tuple``.

        - An explicit ``return somefunc(arg0, ..., k0=v0, ...)`` actually means
          a tail-call to ``somefunc``, with its ``cc`` automatically set to our
          ``cc``. Hence this inserts a call to ``somefunc`` before proceeding
          with our current continuation.

          Here ``somefunc`` **must** be a continuation-enabled function;
          otherwise the TCO chain will break and the result is immediately
          returned to the top-level caller.

          (If the call succeeds at all; the ``cc`` argument is implicitly
          filled in and passed by name, and most regular functions do not
          have a named parameter ``cc``.)

      - Calls from functions defined in one ``with continuations`` block to those
        defined in another are ok; there is no state or context associated with
        the block.

      - Much of the language works as usual.

        Any non-tail calls can be made normally. Regular functions can be called
        normally in any non-tail position.

        Continuation-enabled functions behave as regular functions when
        called normally; only tail calls implicitly set ``cc``.

      - Combo note:

        ``unpythonic.ec.call_ec`` can be used normally outside any ``with bind``;
        but in a ``with bind`` block, the ``ec`` ceases to be valid. (This is
        because the block is actually a tail call.)

        Usage of ``call_ec`` while inside a ``with continuations`` block is::

            with continuations:
                @call_ec
                def result(ec, *, cc):  # note the signature
                    print("hi")
                    ec(42)
                    print("not reached")
                assert result == 42

                result = call_ec(lambda ec, *, cc: do[print("hi"),
                                                      ec(42),
                                                      print("not reached")])

        See the ``tco`` macro for details on the ``call_ec`` combo.

    **Manipulating the continuation**:

      - Use a ``with bind`` to capture the current continuation. It is almost
        call/cc (call-with-current-continuation), but the continuation is
        explicitly made from the given body.

        To grab a first-class reference to this continuation: it's the ``cc``
        argument of the function being called by the ``with bind``.

        Basically the only case in which ``cc`` will contain something other
        than the default continuation, is while inside the function called
        by a ``with bind``. (So stash it from there.)

        A ``with bind`` works both inside a function definition, and at the
        top level of the ``with continuations`` block.

      - Once you have a captured continuation, to use it, set ``cc=...``
        manually in a tail call. Typical usage::

            def main(*, cc):
                with bind[myfunc()]:  # capture the current continuation...
                    ...               # ...which is this body here

            def myfunc(*, cc):
                ourcc = cc  # save the captured continuation (sent by bind)
                def somefunc(*, cc):
                    return dostuff(..., cc=ourcc)  # and use it here
                somestack.append(somefunc)

        In this example, when ``somefunc`` is called, it will tail-call ``dostuff``
        and then proceed with the continuation ``myfunc`` had at the time when
        that instance of the ``somefunc`` closure was created. In this case,
        that continuation points to the body of the ``with bind`` in ``main``.

      - Instead of setting ``cc``, can also just assign a captured continuation
        to ``cc`` inside a function body. That changes the continuation for the
        rest of the dynamic extent of the function, not only for a particular
        tail call::

            def myfunc(*, cc):
                ourcc = cc
                def somefunc(*, cc):
                    cc = ourcc
                    return dostuff(...)
                somestack.append(somefunc)

    **The call/cc, "with bind"**::

        with bind[func(arg0, ..., k0=v0, ...)] as r:
            body0
            ...

        with bind[func(arg0, ..., k0=v0, ...)] as (r0, ...):
            body0
            ...

    Rules:

      - ``with bind`` may only appear inside a ``with continuations`` block.

      - ``with bind`` is one construct, not two. ``bind`` alone is a syntax error.

      - The function call in the brackets is performed, with the body of the
        with block set as its continuation.

          - By stashing the ``cc`` from inside ``func``, to some place accessible
            from the outside, this allows the body to run multiple times.
            Calling the ``cc`` runs the body again.

            Just like in ``call/cc``, the values that get bound to the as-part
            on second and further calls are the arguments given to the ``cc``
            when it is called.

          - Internally, the body gets transformed into a function definition
            (named using a gensym); it implicitly gets its own ``cc``. Hence,
            the value of ``cc`` inside the body is the **body's** ``cc``.

      - The optional as-part captures the return value of ``func`` (first time),
        and whatever was sent into the continuation (second and further times).

         - To ignore the return value (useful if ``func`` was called only to
           perform its side-effects), just omit the as-part.

         - To destructure a multiple-values (from a tuple return value),
           use a tuple ``(r0, ...)``. **Parentheses are mandatory** due to
           the syntax of Python's ``with`` statement.

           Tupleness is tested at run-time. For literal tuples, the run-time
           check is omitted.

      - When ``with bind`` appears inside a function definition:

          - This is technically a tail call that inserts the call to ``func``
            and the given body before proceeding with the current continuation.

          - The return value of the function containing the ``with bind``
            is the return value of the body of the ``with bind``.

      - When ``with bind`` appears at the top level:

          - A normal call to ``func`` is made, proceeding with the body as the
            continuation.

          - In this case it is not possible to get the return value of the body
            the first time it runs, because ``with`` is a statement.

            If you stash the ``cc`` while inside ``func``, and then call it
            later from the top level, then on any further runs it is possible
            to get its return value as usual.

      - If you need to insert just a tail call (no extra body) before proceeding
        with the current continuation, no need for ``with bind``; use
        ``return func(...)`` instead.
    """
    # We don't have an analog of PG's "=apply", since Python doesn't need "apply"
    # to pass in varargs.

    # first pass, outside-in
    userlambdas = _detect_lambda.collect(tree)
    known_ecs = list(uniqify(_detect_callec.collect(tree) + ["ec", "brk"]))
    tree = yield tree

    # second pass, inside-out

    # _tco_transform_def and _tco_transform_lambda correspond to PG's
    # "=defun" and "=lambda", but we don't need to generate a macro.
    #
    # Here we define only the callback to perform the additional transformations
    # we need for the continuation machinery.
    def transform_args(tree):
        assert type(tree) in (FunctionDef, AsyncFunctionDef, Lambda)
        # require explicit by-name-only arg for continuation, "cc"
        # (by name because we need to set a default value; otherwise "cc"
        #  could be positional and be placed just after "self" or "cls", if any)
        kwonlynames = [a.arg for a in tree.args.kwonlyargs]
        hascc = any(x == "cc" for x in kwonlynames)
        if not hascc:
            assert False, "functions in a 'with continuations' block must have a by-name-only arg 'cc'"
        # we could add it implicitly like this
#            tree.args.kwonlyargs = [arg(arg="cc")] + tree.args.kwonlyargs
#            tree.args.kw_defaults = [hq[identity]] + tree.args.kw_defaults
        # Patch in the default identity continuation to allow regular
        # (non-tail) calls without explicitly passing a continuation.
        j = kwonlynames.index("cc")
        if tree.args.kw_defaults[j] is None:
            tree.args.kw_defaults[j] = hq[identity]
        return tree

    # _tco_transform_return corresponds to PG's "=values".
    # It uses _transform_retexpr to transform return-value expressions
    # and arguments of calls to escape continuations.
    #
    # Ours is applied automatically to all return statements (and calls to
    # escape continuations) in the block, and there's some extra complexity
    # to support IfExp, BoolOp, and the do and let macros in return-value expressions.
    #
    # Already performed by the TCO machinery:
    #     return f(...) --> return jump(f, ...)
    #
    # Additional transformations needed here:
    #     return f(...) --> return jump(f, cc=cc, ...)  # customize the transform to add the cc kwarg
    #     return value --> return jump(cc, value)
    #     return v1, ..., vn --> return jump(cc, *(v1, ..., vn))
    #
    # Here we only customize the transform_retexpr callback.
    def call_cb(tree):  # add the cc kwarg (this plugs into the TCO transformation)
        # Pass our current continuation (if no continuation already specified by user).
        hascc = any(kw.arg == "cc" for kw in tree.keywords)
        if not hascc:
            tree.keywords = [keyword(arg="cc", value=q[name["cc"]])] + tree.keywords
        return tree
    def data_cb(tree):  # transform an inert-data return value into a tail-call to cc.
        # Handle multiple-return-values like the rest of unpythonic does:
        # returning a tuple means returning multiple values. Unpack them
        # to cc's arglist.
        if type(tree) is Tuple:  # optimization: literal tuple, always unpack
            tree = hq[jump(name["cc"], *ast_literal[tree])]
        else:  # general case: check tupleness at run-time
            thecall_multi = hq[jump(name["cc"], *name["_retval"])]
            thecall_single = hq[jump(name["cc"], name["_retval"])]
#            tree = let.transform(q[ast_literal[thecall_multi]  # TODO: doesn't work, IfExp missing line number
#                                   if isinstance(name["_retval"], tuple)
#                                   else ast_literal[thecall_single]],
#                                 q[(name["_retval"], ast_literal[tree])])
#            tree = fill_line_numbers(newtree, tree.lineno, tree.col_offset)  # doesn't work even with this.
            tree = let.transform(IfExp(test=q[isinstance(name["_retval"], tuple)],
                                       body=thecall_multi,
                                       orelse=thecall_single,
                                       lineno=tree.lineno, col_offset=tree.col_offset),
                                 q[(name["_retval"], ast_literal[tree])])
        return tree
    transform_retexpr = partial(_transform_retexpr, call_cb=call_cb, data_cb=data_cb)

    # Helper for "with bind".
    # bind[func(arg0, ..., k0=v0, ...)] --> func(arg0, ..., cc=cc, k0=v0, ...)
    # This roughly corresponds to PG's "=funcall".
    def isbind(tree):
        return type(tree) is Subscript and type(tree.value) is Name and tree.value.id == "bind"
    @Walker
    def transform_bind(tree, *, contname, **kw):  # contname: name of function (as bare str) to use as continuation
        if isbind(tree):
            if not (type(tree.slice) is Index and type(tree.slice.value) is Call):
                assert False, "bind: expected a single function call as subscript"
            thecall = tree.slice.value
            thecall.keywords = [keyword(arg="cc", value=q[name[contname]])] + thecall.keywords
            return thecall  # discard the bind[] wrapper
        return tree
    # Inside FunctionDef nodes:
    #     with bind[...] as ...: --> CPS transformation
    # This corresponds to PG's "=bind". This is essentially the call/cc.
    def iswithbind(tree):
        if type(tree) is With:
            if len(tree.items) == 1 and isbind(tree.items[0].context_expr):
                return True
            if any(isbind(item.context_expr) for item in tree.items):
                assert False, "the 'bind' in a 'with bind' statement must be the only context manager"
        return False
    @Walker
    def transform_withbind(tree, *, deftypes, set_ctx, **kw):
        if type(tree) in (FunctionDef, AsyncFunctionDef):  # function definition **inside the "with continuations" block**
            set_ctx(deftypes=(deftypes + [type(tree)]))
        if not iswithbind(tree):
            return tree
        toplevel = not deftypes
        ctxmanager = tree.items[0].context_expr
        optvars = tree.items[0].optional_vars
        if optvars:
            if type(optvars) is Name:
                posargs = [optvars.id]
            elif type(optvars) in (List, Tuple):
                if not all(type(x) is Name for x in optvars.elts):
                    assert False, "with bind[...] as ... expected only names in as-part tuple/list"
                posargs = list(x.id for x in optvars.elts)
            else:
                assert False, "with bind[...] as ... expected a name, list or tuple in as-part"
        else:
            posargs = []

        # Create the continuation function, set our body as its body.
        #
        # Any return statements in the body have already been transformed,
        # because they appear literally in the code at the use site.
        thename = gen_sym("cont")
        FDef = deftypes[-1] if deftypes else FunctionDef  # use same type (regular/async) as parent function
        funcdef = FDef(name=thename,
                       args=arguments(args=[arg(arg=x) for x in posargs],
                                      kwonlyargs=[arg(arg="cc")],
                                      vararg=None,
                                      kwarg=None,
                                      defaults=[],
                                      kw_defaults=[None]),  # patched later by transform_def
                       body=tree.body,
                       decorator_list=[],  # patched later by transform_def
                       returns=None)  # return annotation not used here

        # Set up the call to func, specifying our new function as its continuation
        thecall = transform_bind.recurse(ctxmanager, contname=thename)
        if not toplevel:
            # apply TCO
            thecall.args = [thecall.func] + thecall.args
            thecall.func = hq[jump]
            # Inside a function definition, output a block that defines the
            # continuation function and then calls func, **as a tail call**
#            with q as newtree:
#                if 1:
#                    ast_literal[funcdef]  # TODO: doesn't work, why? (expected expr, not stmt - why?)
#                    return ast_literal[thecall]
#            return newtree[0]  # the if statement
            newtree = If(test=Num(n=1),
                         body=[q[ast_literal[funcdef]],
                               Return(value=q[ast_literal[thecall]])],
                         orelse=[])
        else:
            # At the top level, output a block that defines the
            # continuation function and then calls func normally.
            newtree = If(test=Num(n=1),
                         body=[q[ast_literal[funcdef]],
                               Expr(value=q[ast_literal[thecall]])],
                         orelse=[])
        return newtree

    # set up the default continuation that just returns its args
    newtree = [Assign(targets=[q[name["cc"]]], value=hq[identity])]
    # CPS conversion
    @Walker
    def check_for_strays(tree, **kw):
        if isbind(tree):
            assert False, "bind[...] may only appear as part of with bind[...] as ..."
        return tree
    for stmt in tree:
        # transform "return" statements before "with bind[]"'s tail calls generate new ones.
        stmt = _tco_transform_return.recurse(stmt, known_ecs=known_ecs,
                                             transform_retexpr=transform_retexpr)
        # transform "with bind[]" blocks
        stmt = transform_withbind.recurse(stmt, deftypes=[])
        check_for_strays.recurse(stmt)  # check that no stray bind[] expressions remain
        # transform all defs, including those added by "with bind[]".
        stmt = _tco_transform_def.recurse(stmt, preproc_cb=transform_args)
        stmt = _tco_transform_lambda.recurse(stmt, preproc_cb=transform_args,
                                             userlambdas=userlambdas,
                                             known_ecs=known_ecs,
                                             transform_retexpr=transform_retexpr)
        stmt = _tco_fix_lambda_decorators(stmt)
        newtree.append(stmt)
    return newtree

@macro_stub
def bind(tree, **kw):
    """[syntax] Only meaningful in a "with bind[...] as ..."."""
    pass

@macros.block
def tco(tree, **kw):
    """[syntax, block] Implicit tail-call optimization (TCO).

    Examples::

        with tco:
            evenp = lambda x: (x == 0) or oddp(x - 1)
            oddp  = lambda x: (x != 0) and evenp(x - 1)
            assert evenp(10000) is True

        with tco:
            def evenp(x):
                if x == 0:
                    return True
                return oddp(x - 1)
            def oddp(x):
                if x != 0:
                    return evenp(x - 1)
                return False
            assert evenp(10000) is True

    This is based on a strategy similar to MacroPy's tco macro, but using
    the TCO machinery from ``unpythonic.tco``.

    This recursively handles also builtins ``a if p else b``, ``and``, ``or``;
    and from ``unpythonic.syntax``, ``do[]``, ``let[]``, ``letseq[]``, ``letrec[]``,
    when used in computing a return value.

    Note only calls **in tail position** will be TCO'd. Any other calls
    are left as-is. Tail positions are:

        - The whole return value, if it is just a single call.

        - Both ``a`` and ``b`` branches of ``a if p else b`` (but not ``p``).

        - The last item in an ``and``/``or``. If these are nested, only the
          last item in the whole expression involving ``and``/``or``. E.g. in::

              (1 and 2) or 3
              1 and (2 or 3)

          in either case, only the ``3`` is in tail position.

        - The last item in a ``do[]``.

          - In a ``do0[]``, this is the implicit item that just returns the
            stored return value.

        - The argument of a call to an escape continuation. The ``ec(...)`` call
          itself does not need to be in tail position; escaping early is the
          whole point of an ec.

    All function definitions (``def`` and ``lambda``) lexically inside the block
    undergo TCO transformation. The functions are automatically ``@trampolined``,
    and any tail calls in their return values are converted to ``jump(...)``
    for the TCO machinery.

    Note in a ``def`` you still need the ``return``; it marks a return value.
    But see ``autoreturn``::

        with autoreturn, tco:
            def evenp(x):
                if x == 0:
                    True
                else:
                    oddp(x - 1)
            def oddp(x):
                if x != 0:
                    evenp(x - 1)
                else:
                    False
            assert evenp(10000) is True

    **CAUTION**: regarding escape continuations, only basic uses of ecs created
    via ``call_ec`` are currently detected as being in tail position. Any other
    custom escape mechanisms are not supported. (This is mainly of interest for
    lambdas, which have no ``return``, and for "multi-return" from a nested
    function.)

    *Basic use* is defined as either of these two cases::

        # use as decorator
        @call_ec
        def result(ec):
            ...

        # use directly on a literal lambda
        result = call_ec(lambda ec: ...)

    When macro expansion of the ``with tco`` block starts, names of escape
    continuations created **anywhere lexically within** the ``with tco`` block
    are captured. Lexically within the block, any call to a function having
    any of the captured names, or as a fallback, one of the literal names
    ``ec``, ``brk``, is interpreted as invoking an escape continuation.
    """
    # first pass, outside-in
    userlambdas = _detect_lambda.collect(tree)
    known_ecs = list(uniqify(_detect_callec.collect(tree) + ["ec", "brk"]))
    tree = yield tree

    # second pass, inside-out
    newtree = []
    for stmt in tree:
        stmt = _tco_transform_return.recurse(stmt, known_ecs=known_ecs,
                                             transform_retexpr=_transform_retexpr)
        stmt = _tco_transform_def.recurse(stmt, preproc_cb=None)
        stmt = _tco_transform_lambda.recurse(stmt, preproc_cb=None,
                                             userlambdas=userlambdas,
                                             known_ecs=known_ecs,
                                             transform_retexpr=_transform_retexpr)
        stmt = _tco_fix_lambda_decorators(stmt)
        newtree.append(stmt)
    return newtree

@Walker
def _detect_lambda(tree, *, collect, stop, **kw):
    """Find lambdas in tree. Helper for block macros.

    Run ``_detect_lambda.collect(tree)`` in the first pass, before allowing any
    nested macros to expand. (Those may generate more lambdas that your block
    macro is not interested in).

    The return value from ``.collect`` is a ``list``of ``id(lam)``, where ``lam``
    is a Lambda node that appears in ``tree``. This list is suitable as
    ``userlambdas`` for the TCO macros.

    This ignores any "lambda e: ..." added by an already expanded ``do[]``,
    to allow other block macros to better work together with ``with multilambda``
    (which expands in the first pass, to eliminate semantic surprises).
    """
    if _isdo(tree):
        stop()
        for item in tree.args:  # each arg to dof() is a lambda
            _detect_lambda.collect(item.body)
    if type(tree) is Lambda:
        collect(id(tree))
    return tree

@Walker
def _tco_transform_def(tree, *, preproc_cb, **kw):
    if type(tree) in (FunctionDef, AsyncFunctionDef):
        if preproc_cb:
            tree = preproc_cb(tree)
        # Enable TCO if not TCO'd already.
        #
        # @trampolined needs to be inside of @memoize, otherwise outermost;
        # so that it is applied **after** any call_ec; this allows also escapes
        # to return a jump object to the trampoline.
        if not any(_is_decorator(x, fname) for fname in _tco_decorators for x in tree.decorator_list):
            ismemoize = [_is_decorator(x, "memoize") for x in tree.decorator_list]
            try:
                k = ismemoize.index(True) + 1
                rest = tree.decorator_list[k:] if len(tree.decorator_list) > k else []
                tree.decorator_list = tree.decorator_list[:k] + [hq[trampolined]] + rest
            except ValueError:  # no memoize decorator in list
                tree.decorator_list = [hq[trampolined]] + tree.decorator_list
    return tree

# Transform return statements and calls to escape continuations (ec).
# known_ecs: list of names (str) of known escape continuations.
# transform_retexpr: return-value expression transformer.
@Walker
def _tco_transform_return(tree, *, known_ecs, transform_retexpr, **kw):
    isec = _isec(tree, known_ecs)
    if type(tree) is Return:
        value = tree.value or q[None]  # return --> return None  (bare return has value=None in the AST)
        if not isec:
            return Return(value=transform_retexpr(value, known_ecs))
        else:
            # An ec call already escapes, so the return is redundant.
            #
            # If someone writes "return ec(...)" in a "with continuations" block,
            # this cleans up the code, since eliminating the "return" allows us
            # to omit a redundant "let".
            return Expr(value=value)  # return ec(...) --> ec(...)
    elif isec:  # TCO the arg of an ec(...) call
        if len(tree.args) > 1:
            assert False, "expected exactly one argument for escape continuation"
        tree.args[0] = transform_retexpr(tree.args[0], known_ecs)
    return tree

# userlambdas: list of ids; the purpose is to avoid transforming lambdas implicitly added by macros (do, let).
@Walker
def _tco_transform_lambda(tree, *, preproc_cb, userlambdas, known_ecs, transform_retexpr, stop, set_ctx, hastco=False, **kw):
    # Detect a lambda which already has TCO applied.
    if _is_decorated_lambda(tree, _lambda_decorator_detectors):
        decorator_list, thelambda = _destructure_decorated_lambda(tree)
        if id(thelambda) in userlambdas:
            if any(_is_lambda_decorator(x, fname) for fname in _tco_decorators for x in decorator_list):
                set_ctx(hastco=True)  # thelambda is the next Lambda node we will descend into.
    elif type(tree) is Lambda and id(tree) in userlambdas:
        if preproc_cb:
            tree = preproc_cb(tree)
        tree.body = transform_retexpr(tree.body, known_ecs)
        lam = tree
        if not hastco:  # Enable TCO if not TCO'd already.
            tree = hq[trampolined(ast_literal[tree])]
        # don't recurse on the lambda we just moved, but recurse inside it.
        stop()
        _tco_transform_lambda.recurse(lam.body,
                                      preproc_cb=preproc_cb,
                                      userlambdas=userlambdas,
                                      known_ecs=known_ecs,
                                      transform_retexpr=transform_retexpr,
                                      hastco=False)
    return tree

# call_ec(trampolined(lambda ...: ...)) --> trampolined(call_ec(lambda ...: ...))
# call_ec(curry(trampolined(lambda ...: ...))) --> trampolined(call_ec(curry(lambda ...: ...)))
def _tco_fix_lambda_decorators(tree):
    """Fix ordering of known lambda decorators.

    Strictly, lambdas have no decorator_list, but can be decorated by explicitly
    surrounding them with calls to decorator functions.
    """
    def prioritize(tree):  # sort key for Call nodes invoking known decorators
        for k, f in enumerate(_lambda_decorator_detectors):
            if f(tree):
                return k
        assert False  # we currently support known decorators only

    @Walker
    def fixit(tree, *, stop, **kw):
        if _is_decorated_lambda(tree, _lambda_decorator_detectors):
            decorator_list, thelambda = _destructure_decorated_lambda(tree)
            # We can just swap the func attributes of the nodes.
            ordered_decorator_list = sorted(decorator_list, key=prioritize)
            ordered_funcs = [x.func for x in ordered_decorator_list]
            for thecall, newfunc in zip(decorator_list, ordered_funcs):
                thecall.func = newfunc
            # don't recurse on the tail of the decorator list, but recurse into the lambda body.
            stop()
            fixit.recurse(thelambda.body)
        return tree
    return fixit.recurse(tree)

def _is_decorator(tree, fname):
    """Test tree whether it is the decorator ``fname``.

    References of the forms ``f``, ``foo.f`` and ``hq[f]`` are supported.

     We detect:

        - ``Name``, ``Attribute`` or ``Captured`` matching the given ``fname``
          (non-parametric decorator), and

        - ``Call`` whose ``.func`` matches the above rule (parametric decorator).
    """
    return _isx(tree, fname) or \
           (type(tree) is Call and _isx(tree.func, fname))

def _is_lambda_decorator(tree, fname):
    """Test tree whether it decorates a lambda with ``fname``.

    A node is detected as a lambda decorator if it is a ``Call`` that supplies
    exactly one positional argument, and its ``.func`` is a decorator
    (``_is_decorator(tree.func)`` returns ``True``).

    This function does not know or care whether a chain of ``Call`` nodes
    terminates in a ``Lambda`` node. See ``_is_decorated_lambda``.

    Examples::

        trampolined(arg)                    # --> non-parametric decorator
        looped_over(range(10), acc=0)(arg)  # --> parametric decorator
    """
    return (type(tree) is Call and len(tree.args) == 1) and _is_decorator(tree.func, fname)

def _is_decorated_lambda(tree, detectors):
    """Detect a tree of the form f(g(h(lambda ...: ...)))

    We currently support known decorators only.

    detectors: a list of predicates to detect a known decorator.
    To build these easily, ``partial(_is_lambda_decorator, fname="whatever")``.
    """
    if type(tree) is not Call:
        return False
    if not any(f(tree) for f in detectors):
        return False
    if type(tree.args[0]) is Lambda:
        return True
    return _is_decorated_lambda(tree.args[0], detectors)

def _destructure_decorated_lambda(tree):
    """Get the AST nodes for ([f, g, h], lambda) in f(g(h(lambda ...: ...)))

    Input must be a tree for which ``is_decorated_lambda`` returns ``True``.

    This returns **the original AST nodes**, to allow in-place transformations.
    """
    def get(tree, lst):
        if type(tree) is Call:
            # collect tree itself, not tree.func, because we need to reorder the funcs later.
            return get(tree.args[0], lst + [tree])
        elif type(tree) is Lambda:
            return lst, tree
        assert False, "Expected a chain of Call nodes terminating in a Lambda node"
    return get(tree, [])

# Extensible system. List known decorators in the desired ordering,
# outermost-to-innermost.
#
# "with curry" (--> hq[curryf(...)]) is expanded later, so we don't need to
# worry about it here; we catch only explicit curry(...) in the client code,
# which is already there when "with tco" or "with continuations" is expanded.
#
_tco_decorators = ["trampolined", "looped", "breakably_looped", "looped_over", "breakably_looped_over"]
_decorator_registry = ["memoize", "fimemoize"] + _tco_decorators + ["call_ec", "call", "curry"]
_lambda_decorator_detectors = [partial(_is_lambda_decorator, fname=x) for x in _decorator_registry]

# Tail-position analysis for a return-value expression (also the body of a lambda).
# Here we need to be very, very selective about where to recurse so this is not a Walker.
def _transform_retexpr(tree, known_ecs, call_cb=None, data_cb=None):
    """Analyze and TCO a return-value expression or a lambda body.

    This performs a tail-position analysis on the given ``tree``, recursively
    handling the builtins ``a if p else b``, ``and``, ``or``; and from
    ``unpythonic.syntax``, ``do[]``, ``let[]``, ``letseq[]``, ``letrec[]``.

      - known_ecs: list of str, names of known escape continuations.

      - call_cb(tree): either None; or tree -> tree, callback for Call nodes

      - data_cb(tree): either None; or tree -> tree, callback for inert data nodes

    The callbacks (if any) may perform extra transformations; they are applied
    as postprocessing for each node of matching type, after any transformations
    performed by this macro.

    *Inert data* is defined as anything except Call, IfExp, BoolOp-with-tail-call,
    or one of the supported macros from ``unpythonic.syntax``.
    """
    transform_call = call_cb or (lambda tree: tree)
    transform_data = data_cb or (lambda tree: tree)
    def transform(tree):
        if _isdo(tree) or _islet(tree):
            # Ignore the "lambda e: ...", and descend into the ..., in:
            #   - let[] or letrec[] in tail position.
            #     - letseq[] is a nested sequence of lets, so covers that too.
            #   - do[] in tail position.
            #     - May be generated also by a "with multilambda" block
            #       that has already expanded.
            tree.args[-1].body = transform(tree.args[-1].body)
        elif type(tree) is Call:
            # Apply TCO to tail calls.
            #   - If already an explicit jump() or loop(), leave it alone.
            #   - If a call to an ec, leave it alone.
            #     - Because an ec call may appear anywhere, a tail-position
            #       analysis will not find all of them.
            #     - This function analyzes only tail positions within
            #       a return-value expression.
            #     - Hence, transform_return() calls us on the content of
            #       all ec nodes directly. ec(...) is like return; the
            #       argument is the retexpr.
            if not (_isx(tree.func, "jump") or _isx(tree.func, "loop") or _isec(tree, known_ecs)):
                tree.args = [tree.func] + tree.args
                tree.func = hq[jump]
                tree = transform_call(tree)
        elif type(tree) is IfExp:
            # Only either body or orelse runs, so both of them are in tail position.
            # test is not in tail position.
            tree.body = transform(tree.body)
            tree.orelse = transform(tree.orelse)
        elif type(tree) is BoolOp:  # and, or
            # and/or is a combined test-and-return. Any number of these may be nested.
            # Because it is in general impossible to know beforehand how many
            # items will be actually evaluated, we define only the last item
            # (in the whole expression) to be in tail position.
            if type(tree.values[-1]) in (Call, IfExp, BoolOp):  # must match above handlers
                # other items: not in tail position, compute normally
                if len(tree.values) > 2:
                    op_of_others = BoolOp(op=tree.op, values=tree.values[:-1],
                                          lineno=tree.lineno, col_offset=tree.col_offset)
                else:
                    op_of_others = tree.values[0]
                if type(tree.op) is Or:
                    # or(data1, ..., datan, tail) --> it if any(others) else tail
                    tree = aif.transform(Tuple(elts=[op_of_others,
                                                     transform_data(Name(id="it",
                                                                         lineno=tree.lineno,
                                                                         col_offset=tree.col_offset)),
                                                     transform(tree.values[-1])],
                                               lineno=tree.lineno, col_offset=tree.col_offset)) # tail-call item
                elif type(tree.op) is And:
                    # and(data1, ..., datan, tail) --> tail if all(others) else False
                    fal = q[False]
                    fal = copy_location(fal, tree)
                    tree = IfExp(test=op_of_others,
                                 body=transform(tree.values[-1]),
                                 orelse=transform_data(fal))
                else:  # cannot happen
                    assert False, "unknown BoolOp type {}".format(tree.op)
            else:  # optimization: BoolOp, no call or compound in tail position --> treat as single data item
                tree = transform_data(tree)
        else:
            tree = transform_data(tree)
        return tree
    return transform(tree)

# Tail-position analysis for a function body.
@macros.block
def autoreturn(tree, **kw):
    """[syntax, block] Implicit "return" in tail position, like in Lisps.

    Each ``def`` function definition lexically within the ``with autoreturn``
    block is examined, and if the last item within the body is an expression
    ``expr``, it is transformed into ``return expr``.

    If the last item is an if/elif/else block, the transformation is applied
    to the last item in each of its branches.

    If the last item is a ``with`` or ``async with`` block, the transformation
    is applied to the last item in its body.

    If the last item is a try/except/else/finally block, the rules are as follows.
    If an ``else`` clause is present, the transformation is applied to the last
    item in it; otherwise, to the last item in the ``try`` clause. Additionally,
    in both cases, the transformation is applied to the last item in each of the
    ``except`` clauses. The ``finally`` clause is not transformed; the intention
    is it is usually a finalizer (e.g. to release resources) that runs after the
    interesting value is already being returned by ``try``, ``else`` or ``except``.

    Example::

        with autoreturn:
            def f():
                "I'll just return this"
            assert f() == "I'll just return this"

            def g(x):
                if x == 1:
                    "one"
                elif x == 2:
                    "two"
                else:
                    "something else"
            assert g(1) == "one"
            assert g(2) == "two"
            assert g(42) == "something else"

    **CAUTION**: If the final ``else`` is omitted, as often in Python, then
    only the ``else`` item is in tail position with respect to the function
    definition - likely not what you want.

    So with ``autoreturn``, the final ``else`` should be written out explicitly,
    to make the ``else`` branch part of the same if/elif/else block.

    **CAUTION**: ``for``, ``async for``, ``while`` are currently not analyzed;
    effectively, these are defined as always returning ``None``. If the last item
    in your function body is a loop, use an explicit return.

    **CAUTION**: With ``autoreturn`` enabled, functions no longer return ``None``
    by default; the whole point of this macro is to change the default return
    value.

    The default return value is ``None`` only if the tail position contains
    a statement (because in a sense, a statement always returns ``None``).
    """
    @Walker
    def transform_tailstmt(tree, **kw):
        if type(tree) in (FunctionDef, AsyncFunctionDef):
            tree.body[-1] = transform_one(tree.body[-1])
        return tree
    def transform_one(tree):
        # TODO: For/AsyncFor/While?
        if type(tree) is If:
            tree.body[-1] = transform_one(tree.body[-1])
            if tree.orelse:
                tree.orelse[-1] = transform_one(tree.orelse[-1])
        elif type(tree) in (With, AsyncWith):
            tree.body[-1] = transform_one(tree.body[-1])
        elif type(tree) is Try:
            # We don't care about finalbody; it is typically a finalizer.
            if tree.orelse:  # tail position is in else clause if present
                tree.orelse[-1] = transform_one(tree.orelse[-1])
            else:  # tail position is in the body of the "try"
                tree.body[-1] = transform_one(tree.body[-1])
            # additionally, tail position is in each "except" handler
            for handler in tree.handlers:
                handler.body[-1] = transform_one(handler.body[-1])
        elif type(tree) is Expr:
            tree = Return(value=tree.value)
        return tree
    # This is a first-pass macro. Any nested macros should get clean standard Python,
    # not having to worry about implicit "return" statements.
    yield transform_tailstmt.recurse(tree)

# -----------------------------------------------------------------------------

@macros.block
def prefix(tree, **kw):
    """[syntax, block] Write Python like Lisp: the first item is the operator.

    Example::

        with prefix:
            (print, "hello world")
            t1 = (q, 1, 2, (3, 4), 5)
            x = 42
            t2 = (q, 17, 23, x)
            (print, t1, t2)

    Lexically inside a ``with prefix``:

        - A bare ``q`` at the head of a tuple is the quote operator. It increases
          the quote level by one.

          It actually just tells the macro that this tuple (and everything in it,
          recursively) is not a function call.

          Variables can be used as usual, there is no need to unquote them.

        - A bare ``u`` at the head of a tuple is the unquote operator, which
          decreases the quote level by one. In other words, in::

              with prefix:
                  t = (q, 1, 2, (u, print, 3), (print, 4), 5)
                  (print, t)

          the third item will call ``print(3)`` and evaluate to its return value
          (in this case ``None``, since it's ``print``), whereas the fourth item
          is a tuple with the two items ``(<built-in function print>, 4)``.

        - Quote/unquote operators are parsed from the start of the tuple until
          no more remain. Then any remaining items are either returned quoted
          (if quote level > 0), or evaluated as a function call and replaced
          by the return value.

        - How to pass named args::

              from unpythonic.misc import call

              with prefix:
                  (f, kw(myarg=3))  # ``kw(...)`` (syntax, not really a function!)
                  call(f, myarg=3)  # in a call(), kwargs are ok
                  f(myarg=3)        # or just use Python's usual function call syntax

          One ``kw`` operator may include any number of named args (and **only**
          named args). The tuple may have any number of ``kw`` operators.

          All named args are collected from ``kw`` operators in the tuple
          when writing the final function call. If the same kwarg has been
          specified by multiple ``kw`` operators, the rightmost definition wins.

          **Note**: Python itself prohibits having repeated named args in the **same**
          ``kw`` operator, because it uses the function call syntax. If you get a
          `SyntaxError: keyword argument repeated` with no useful traceback,
          check any recent ``kw`` operators you have added in prefix blocks.

          A ``kw(...)`` operator in a quoted tuple (not a function call) is an error.

    Current limitations:

        - passing ``*args`` and ``**kwargs`` not supported.

          Workarounds: ``call(...)``; Python's usual function call syntax.

        - For ``*args``, to keep it lispy, maybe you want ``unpythonic.fun.apply``;
          this allows syntax such as ``(apply, f, 1, 2, lst)``.
    """
    isquote = lambda tree: type(tree) is Name and tree.id == "q"
    isunquote = lambda tree: type(tree) is Name and tree.id == "u"
    iskwargs = lambda tree: type(tree) is Call and type(tree.func) is Name and tree.func.id == "kw"
    @Walker
    def transform(tree, *, quotelevel, set_ctx, **kw):
        if not (type(tree) is Tuple and type(tree.ctx) is Load):
            return tree
        op, *data = tree.elts
        while True:
            if isunquote(op):
                if quotelevel < 1:
                    assert False, "unquote while not in quote"
                quotelevel -= 1
            elif isquote(op):
                quotelevel += 1
            else:
                break
            set_ctx(quotelevel=quotelevel)
            if not len(data):
                assert False, "a prefix tuple cannot contain only quote/unquote operators"
            op, *data = data
        if quotelevel > 0:
            quoted = [op] + data
            if any(iskwargs(x) for x in quoted):
                assert False, "kw(...) may only appear in a prefix tuple representing a function call"
            return q[(ast_literal[quoted],)]
        # (f, a1, ..., an) --> f(a1, ..., an)
        posargs = [x for x in data if not iskwargs(x)]
        # TODO: tag *args and **kwargs in a kw() as invalid, too (currently just ignored)
        invalids = list(flatmap(lambda x: x.args, filter(iskwargs, data)))
        if invalids:
            assert False, "kw(...) may only specify named args"
        kwargs = flatmap(lambda x: x.keywords, filter(iskwargs, data))
        kwargs = list(rev(uniqify(rev(kwargs), key=lambda x: x.arg)))  # latest wins, but keep original ordering
        return Call(func=op, args=posargs, keywords=list(kwargs))
    # This is a first-pass macro. Any nested macros should get clean standard Python,
    # not having to worry about tuples possibly denoting function calls.
    yield transform.recurse(tree, quotelevel=0)

# note the exported "q" is ours, but the q we use in this module is a macro.
class q:
    """[syntax] Quote operator. Only meaningful in a tuple in a prefix block."""
    def __repr__(self):  # in case one of these ends up somewhere at runtime
        return "<quote>"
q = q()

class u:
    """[syntax] Unquote operator. Only meaningful in a tuple in a prefix block."""
    def __repr__(self):  # in case one of these ends up somewhere at runtime
        return "<unquote>"
u = u()

def kw(**kwargs):
    """[syntax] Pass-named-args operator. Only meaningful in a tuple in a prefix block."""
    raise RuntimeError("kw only meaningful inside a tuple in a prefix block")

# -----------------------------------------------------------------------------
