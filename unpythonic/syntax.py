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
#from macropy.core.cleanup import fill_line_numbers

from functools import partial
from ast import Call, arg, keyword, With, withitem, Tuple, \
                Name, Attribute, Load, BinOp, LShift, \
                Subscript, Index, Slice, ExtSlice, Lambda, List, \
                copy_location, Assign, FunctionDef, \
                ListComp, SetComp, GeneratorExp, DictComp, \
                arguments, If, Num, Return, Expr, IfExp, BoolOp, And, Or

from unpythonic.it import flatmap, uniqify, rev
from unpythonic.fun import curry as curryf, identity
from unpythonic.dynscope import dyn
from unpythonic.lispylet import letrec as letrecf, let as letf
from unpythonic.seq import do as dof, begin as beginf
from unpythonic.fup import fupdate
from unpythonic.misc import namelambda

# insist, deny are just for passing through to the using module that imports us.
from unpythonic.amb import forall as forallf, choice as choicef, insist, deny
from unpythonic.amb import List as MList  # list monad

# TODO: remove the exception-based TCO implementation
from unpythonic.fasttco import trampolined, jump

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

@macros.block
def curry(tree, **kw):  # technically a list of trees, the body of the with block
    """[syntax, block] Automatic currying.

    Usage::

        from unpythonic.syntax import macros, curry

        with curry:
            ... # all function calls here are auto-curried, except builtins

    Example::

        from unpythonic.syntax import macros, curry
        from unpythonic import foldr, composerc as compose, cons, nil

        with curry:
            mymap = lambda f: foldr(compose(cons, f), nil)
            double = lambda x: 2 * x
            print(mymap(double, (1, 2, 3)))

            def myadd(a, b):
                return a + b
            add2 = myadd(2)
            assert add2(3) == 5
    """
    @Walker
    def transform_call(tree, **kw):  # technically a node containing the current subtree
        if type(tree) is Call:
            tree.args = [tree.func] + tree.args
            tree.func = hq[curryf]
        return tree
    body = transform_call.recurse(tree)
    # Wrap the body in "with dyn.let(_curry_allow_uninspectable=True):"
    # to avoid crash with builtins (uninspectable)
    item = hq[dyn.let(_curry_allow_uninspectable=True)]
    wrapped = With(items=[withitem(context_expr=item)],
                   body=body)
    return [wrapped]  # block macro: got a list, must return a list.

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

# This simple classical lambda-based let works, but does not support assignment,
# so it can't be used for things like let-over-lambda, or indeed letrec.
# But it's simple, and creates real lexical variables.

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

def _letimpl(tree, args, mode, gen_sym):  # args; sequence of ast.Tuple: (k1, v1), (k2, v2), ..., (kn, vn)
    newtree = _implicit_do(tree)
    if not args:
        return newtree
    names, values = zip(*[a.elts for a in args])  # --> (k1, ..., kn), (v1, ..., vn)
    names = [k.id for k in names]  # any duplicates will be caught by env at run-time

    e = gen_sym("e")
    envset = Attribute(value=q[name[e]], attr="set", ctx=Load())

    t = partial(_letlike_transform, envname=e, varnames=names, setter=envset)
    if mode == "letrec":
        values = [t(b) for b in values]  # RHSs of bindings
    newtree = t(newtree)  # body

    letter = letf if mode == "let" else letrecf
    binding_pairs = [q[(u[k], ast_literal[v])] for k, v in zip(names, values)]
    return hq[letter((ast_literal[binding_pairs],), ast_literal[newtree])]

def _letlike_transform(subtree, envname, varnames, setter):
    # x << val --> e.set('x', val)
    subtree = _transform_assignment.recurse(subtree, names=varnames, setter=setter, fargs=[])
    # x --> e.x
    subtree = _transform_name.recurse(subtree, names=varnames, envname=envname, fargs=[])
    # ... -> lambda e: ...
    return _envwrap(subtree, envname=envname)

def _isassign(tree):  # detect "x << 42" syntax to assign variables in an environment
    return type(tree) is BinOp and type(tree.op) is LShift and type(tree.left) is Name
def _assign_name(tree):  # rackety accessors
    return tree.left.id
def _assign_value(tree):
    return tree.right

def _isnewscope(tree):
    return type(tree) in (Lambda, FunctionDef, ListComp, SetComp, GeneratorExp, DictComp)
def _getlocalnames(tree):  # get arg names of Lambda/FunctionDef, and target names of comprehensions
    if type(tree) in (Lambda, FunctionDef):
        a = tree.args
        argnames = [x.arg for x in a.args + a.kwonlyargs]
        if a.vararg:
            argnames.append(a.vararg.arg)
        if a.kwarg:
            argnames.append(a.kwarg.arg)
        return argnames
    elif type(tree) in (ListComp, SetComp, GeneratorExp, DictComp):
        argnames = []
        for g in tree.generators:
            if type(g.target) is Name:
                argnames.append(g.target.id)
            elif type(g.target) is Tuple:
                # TODO: simplistic; does this cover all cases?
                @Walker
                def extractnames(tree, *, collect, **kw):
                    if type(tree) is Name:
                        collect(tree.id)
                    return tree
                argnames.extend(extractnames.collect(g.target))
            else:
                assert False, "unimplemented: comprehension target of type {}".type(g.target)
        return argnames
    return []

# x << val --> e.set('x', val)  (for names bound in this environment)
@Walker
def _transform_assignment(tree, *, names, setter, fargs, set_ctx, **kw):
    # Function args and comprehenion targets shadow names of the surrounding env.
    if _isnewscope(tree):
        set_ctx(fargs=(fargs + _getlocalnames(tree)))
    elif _isassign(tree):
        varname = _assign_name(tree)
        # each let handles only its own varnames
        if varname in names and varname not in fargs:
            value = _assign_value(tree)
            return q[ast_literal[setter](u[varname], ast_literal[value])]
    return tree

# x --> e.x  (for names bound in this environment)
@Walker
def _transform_name(tree, *, names, envname, fargs, set_ctx, **kw):
    if _isnewscope(tree):
        set_ctx(fargs=(fargs + _getlocalnames(tree)))
    # e.anything is already ok, but x.foo (Attribute that contains a Name "x")
    # should transform to e.x.foo.
    elif type(tree) is Attribute and type(tree.value) is Name and tree.value.id == envname:
        pass
    # nested lets work, because once x --> e.x, the final "x" is no longer a Name,
    # but an attr="x" of an Attribute node.
    elif type(tree) is Name and tree.id in names and tree.id not in fargs:
        return Attribute(value=q[name[envname]], attr=tree.id, ctx=Load())
    return tree

# ... -> lambda e: ...
def _envwrap(tree, envname):
    lam = q[lambda: ast_literal[tree]]
    lam.args.args = [arg(arg=envname)]  # lambda e44: ...
    return lam

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

    All ``localdef`` declarations are collected (and the declaration part
    discarded) before any other processing, so it does not matter where each
    ``localdef`` appears inside the ``do``. Especially, in::

        do[x << 2,
           localdef(x << 3),  # DANGER: may break in a future version
           x]

    already the first ``x`` refers to the local x, because ``x`` **has a**
    ``localdef`` in this ``do``. (This subject to change in a future version.)

    For readability and future-proofness, it is recommended to place localdefs
    at or near the start of the do-block, at the first use of each local name.

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
    # Must use env.__setattr__ to allow defining new names; env.set only rebinds.
    # But to keep assignments chainable, use begin(setattr(e, 'x', val), val).
    sa = Attribute(value=q[name[e]], attr="__setattr__", ctx=Load())
    envset = hq[lambda k, v: beginf(ast_literal[sa](k, v), v)]

    def islocaldef(tree):
        return type(tree) is Call and type(tree.func) is Name and tree.func.id == "localdef"
    @Walker
    def _find_localvars(tree, collect, **kw):
        if islocaldef(tree):
            if len(tree.args) != 1:
                assert False, "localdef(...) must have exactly one positional argument"
            expr = tree.args[0]
            if not _isassign(expr):
                assert False, "localdef(...) argument must be of the form 'name << value'"
            collect(_assign_name(expr))
            return expr  # localdef(...) -> ..., the localdef has done its job
        return tree
    tree, names = _find_localvars.recurse_collect(tree)
    names = list(names)
    if len(set(names)) < len(names):
        assert False, "localdef names must be unique in the same do"

    lines = [_letlike_transform(line, e, names, envset) for line in tree.elts]
    return hq[dof(ast_literal[lines])]

@macros.expr
def do0(tree, **kw):
    """[syntax, expr] Like do, but return the value of the first expression."""
    if type(tree) not in (Tuple, List):
        assert False, "do0 body: expected a sequence of comma-separated expressions"
    elts = tree.elts
    newelts = []  # IDE complains about _do0_result, but it's quoted, so it's ok.
    newelts.append(q[localdef(_do0_result << (ast_literal[elts[0]]))])
    newelts.extend(elts[1:])
    newelts.append(q[_do0_result])
    newtree = q[(ast_literal[newelts],)]
    newtree = copy_location(newtree, tree)
    return do.transform(newtree)  # do0[] is also just a do[]

def _isdo(tree):
    # TODO: what about the fact it's a hq[dof(...)]? No Captured node?
    return type(tree) is Call and type(tree.func) is Name and tree.func.id == "dof"

# -----------------------------------------------------------------------------

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
        tree = _transform_name.recurse(tree, names=names, envname=e, fargs=[])  # x --> e.x
        return _envwrap(tree, envname=e)  # ... -> lambda e: ...
    chooser = hq[choicef]
    for line in body:
        if _isassign(line):  # convert "<<" assignments, but only at top level
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
        if _isassign(line):
            k, v = _assign_name(line), _assign_value(line)
        else:
            k, v = "_ignored", line
        islast = not rest
        # don't unpack on last line to allow easily returning a tuple as a result item
        Mv = hq[_monadify(ast_literal[v], u[not islast])]
        if not islast:
            body = q[ast_literal[Mv] >> (lambda: _here_)]  # monadic bind: >>
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
    """[syntax, block] Named lambdas.

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
    wrapped = With(items=[withitem(context_expr=item)],
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

      - Tree traversal (possibly multiple trees simultaneously, with the
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

    Rules of a ``with continuations`` block:

      - Functions which make use of continuations, or call other functions that do,
        must be defined within a ``with continuations`` block, using ``def``
        or ``lambda``.

      - All function definitions in a ``with continuations`` block, including
        any nested definitionss, must declare a by-name-only formal parameter
        ``cc``::

            with continuations:
                def myfunc(*, cc):
                    ...

                    f = lambda *, cc: ...

        The continuation machinery implicitly sets its value to the current
        continuation.

      - A ``with continuations`` block will automatically transform all ``def``
        function definitions and ``return`` statements lexically contained within
        it to use the continuation machinery.

        Hence, functions that **don't** use continuations **must** be defined
        **outside** the block.

        - ``return somevalue`` actually means a tail-call to ``cc`` with the
          given ``somevalue``. Multiple values can be returned as a ``tuple``.

        - An explicit ``return somefunc(arg0, ..., k0=v0, ...)`` actually means
          a tail-call to ``somefunc``, with its ``cc`` automatically set to our
          ``cc``.

          Hence this inserts a call to ``somefunc`` before proceeding with our
          current continuation.

          Here ``somefunc`` **must** be a continuation-enabled function;
          otherwise the TCO chain will break and the result is immediately
          returned to the top-level caller.

          (If the call succeeds at all; the ``cc`` argument is implicitly
          passed by name, and most regular functions do not have a named
          parameter ``cc``.)

      - Calls from functions defined in one ``with continuations`` block to those
        defined in another are ok.

      - Regular functions can be called normally (as any non-tail call).

        Continuation-enabled functions also behave as regular functions when
        called normally; only tail calls to continuation-enabled functions
        implicitly set ``cc``.

      - Once inside a ``with continuations`` block, nested ``with continuations``
        blocks have no additional effect, since the continuation machinery is
        already enabled.

        We could define it to be an error, but having it no-op is more convenient
        for agile prototyping. This allows to easily move around code that uses
        continuations, without caring about whether continuations are already
        enabled in some outer lexical scope.

    **Manipulating the continuation**:

      - To call a continuation-enabled function, optionally get its return value(s),
        then run some more code, and finally proceed with the original ``cc``,
        use a ``with bind``.

        This allows making a continuation-enabled call (that may return multiple
        times) in the middle of a function, or at the top level of the
        ``with continuations`` block.

        Basically the only case in which ``cc`` will contain something other than
        the default continuation, is while inside the function called by a
        ``with bind``.

        ``with bind`` is almost call/cc (call-with-current-continuation),
        but the continuation is explicitly made from the given body.
        It is of course possible to grab a first-class reference to this
        continuation; it's the ``cc`` argument of the function being called
        by the ``with bind``.

      - To override the current continuation, set ``cc=...`` manually in a
        tail call. As the replacement, use a ``cc`` captured at the appropriate
        time::

            def myfunc(*, cc):
                ourcc = cc  # capture myfunc's current continuation
                def somefunc(*, cc):
                    return dostuff(..., cc=ourcc)  # and inject it here
                somestack.append(somefunc)

            def main(*, cc):
                with bind[myfunc()]:
                    ...

        In this example, when ``somefunc`` is called, it will proceed with the
        continuation ``myfunc`` had at the time when that instance of the
        ``somefunc`` closure was created. In this case, that continuation
        points to the body of the ``with bind``.

      - Also possible to just assign a function to ``cc`` inside a function body::

            def myfunc(*, cc):
                ourcc = cc
                def somefunc(*, cc):
                    cc = ourcc
                    return dostuff(...)
                somestack.append(somefunc)

    **with bind**::

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
            from the outside, this allows the body to run multiple times
            (calling the cc runs the body again).

            Just like in ``call/cc``, the values that get bound to the as-part
            on further calls are the arguments given to the cc when it is called.

          - Internally, the body gets transformed into a function definition
            (named using a gensym); it implicitly gets its own ``cc``. Hence,
            the value of ``cc`` inside the body is the **body's** ``cc``.

      - The optional as-part captures the return value of ``func``.

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
    # We don't have an analog of PG's "=apply"; Python doesn't need "apply"
    # to pass in varargs.

    # first pass, outside-in
    # Eliminate nested "with continuations" blocks
    @Walker
    def transform_nested(tree, **kw):
        if iswithcontinuations(tree):
            return If(test=Num(n=1),  # replace the "with" by a no-op "if"
                      body=tree.body,
                      orelse=[])
        return tree
    def iswithcontinuations(tree):
        # TODO: what about combos with other top-level block macros?
        # TODO: disallow combo with tco, this includes that functionality.
        return type(tree) is With and len(tree.items) == 1 and \
               type(tree.items[0].context_expr) is Name and \
               tree.items[0].context_expr.id == "continuations"

    userlambdas = _detect_lambda.collect(tree)
    tree = yield transform_nested.recurse(tree)

    # second pass, inside-out (after any nested macros have been expanded)

    # These correspond to PG's "=defun" and "=lambda", but we don't need to generate a macro.
    @Walker
    def transform_def(tree, **kw):
        if type(tree) is FunctionDef:
            tree = transform_args(tree)
            tree.decorator_list = [hq[trampolined]] + tree.decorator_list  # enable TCO
        return tree
    # TODO: support lambdas that use call_ec
    @Walker
    def transform_lambda(tree, *, stop, **kw):
        if type(tree) is Lambda and id(tree) in userlambdas:
            tree = transform_args(tree)
            tree.body = transform_retexpr(tree.body)
            tree = hq[trampolined(ast_literal[tree])]  # enable TCO
            stop()  # avoid recursing on the lambda we just moved inside the trampolined()...
            transform_lambda.recurse(tree.args[0].body)  # ...but recurse inside it
        return tree
    def transform_args(tree):
        assert type(tree) in (FunctionDef, Lambda)
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

    # This corresponds to PG's "=values".
    # Ours is applied automatically to all return statements in the block,
    # and there's some extra complexity to support IfExp and BoolOp.
    # return value --> return jump(cc, value)
    # return v1, ..., vn --> return jump(cc, *(v1, ..., vn))
    # return f(...) --> return jump(f, cc=cc, ...)
    @Walker
    def transform_return(tree, **kw):
        if type(tree) is Return:
            # return --> return None  (bare return has value=None in the AST)
            value = tree.value or q[None]
            return Return(value=transform_retexpr(value))
        return tree
    def transform_retexpr(tree):  # input: expression in return-value position
        def call_cb(tree):
            # Pass our current continuation (if no continuation already specified by user).
            hascc = any(kw.arg == "cc" for kw in tree.keywords)
            if not hascc:
                tree.keywords = [keyword(arg="cc", value=q[name["cc"]])] + tree.keywords
            return tree
        def data_cb(tree):
            # Handle multiple-return-values like the rest of unpythonic does:
            # returning a tuple means returning multiple values. Unpack them
            # to cc's arglist.
            if type(tree) is Tuple:  # optimization: literal tuple, always unpack
                tree = hq[jump(name["cc"], *ast_literal[tree])]
            else:  # general case: check tupleness at run-time
                thecall_multi = hq[jump(name["cc"], *name["_retval"])]
                thecall_single = hq[jump(name["cc"], name["_retval"])]
#                tree = let.transform(q[ast_literal[thecall_multi]  # TODO: doesn't work, IfExp missing line number
#                                       if isinstance(name["_retval"], tuple)
#                                       else ast_literal[thecall_single]],
#                                     q[(name["_retval"], ast_literal[tree])])
#                tree = fill_line_numbers(newtree, tree.lineno, tree.col_offset)  # doesn't work even with this.
                tree = let.transform(IfExp(test=q[isinstance(name["_retval"], tuple)],
                                           body=thecall_multi,
                                           orelse=thecall_single,
                                           lineno=tree.lineno, col_offset=tree.col_offset),
                                     q[(name["_retval"], ast_literal[tree])])
            return tree
        return _transform_tailcall_retexpr(tree, call_cb, data_cb, iden="continuations")

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
    def transform_withbind(tree, *, toplevel, set_ctx, **kw):
        if type(tree) is FunctionDef:  # function definition **inside the "with continuations" block**
            set_ctx(toplevel=False)
        if not iswithbind(tree):
            return tree
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
        funcdef = FunctionDef(name=thename,
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
        stmt = transform_return.recurse(stmt)
        stmt = transform_withbind.recurse(stmt, toplevel=True)  # transform "with bind[]" blocks
        check_for_strays.recurse(stmt)  # check that no stray bind[] expressions remain
        # transform all defs, including those added by "with bind[]".
        stmt = transform_def.recurse(stmt)
        stmt = transform_lambda.recurse(stmt)
        newtree.append(stmt)
    return newtree

@macro_stub
def bind(tree, **kw):
    """[syntax] Only meaningful in a "with bind[...] as ..."."""
    pass

@macros.block
def tco(tree, **kw):
    """[syntax, block] Automatically apply tail-call optimization (TCO).

    Example::

        with tco:
            evenp = lambda x: (x == 0) or oddp(x - 1)
            oddp  = lambda x: (x != 0) and evenp(x - 1)
            assert evenp(10000) is True

    This is based on a strategy similar to MacroPy's tco macro, but using
    the TCO machinery from ``unpythonic.fasttco``.

    This recursively handles also ``a if p else b``, ``and``, ``or``, and
    ``unpythonic.syntax.do[]`` when used in computing a return value.

    **CAUTION**: when detecting tail position, ``call_ec`` is not supported.

    In a ``with tco`` block, **only tail calls** are allowed in a return value.
    To make regular calls when computing a return value, put them elsewhere
    (using ``do[]`` or ``multilambda`` if necessary).

    All function definitions (``def`` and ``lambda``) lexically inside the block
    undergo TCO transformation. The functions are automatically ``@trampolined``,
    and any tail calls in their return values are converted to ``jump(...)``
    for the TCO machinery.

    Note in a ``def`` you still need the ``return``; it marks a return value.
    """
    # first pass, outside-in
    userlambdas = _detect_lambda.collect(tree)
    tree = yield tree

    # second pass, inside-out

    # TODO: code duplication between here and continuations
    @Walker
    def transform_def(tree, **kw):
        if type(tree) is FunctionDef:
            tree.decorator_list = [hq[trampolined]] + tree.decorator_list  # enable TCO
        return tree
    @Walker
    def transform_return(tree, **kw):
        if type(tree) is Return:
            # return --> return None  (bare return has value=None in the AST)
            value = tree.value or q[None]
            return Return(value=transform_retexpr(value))
        return tree

    # TODO: support lambdas that use call_ec
    #   - maybe wrap each userlambda in a call_ec, defining "exit" or some such?
    @Walker
    def transform_lambda(tree, *, stop, **kw):
        if type(tree) is Lambda and id(tree) in userlambdas:
            tree.body = transform_retexpr(tree.body)
            tree = hq[trampolined(ast_literal[tree])]  # enable TCO
            stop()  # avoid recursing on the lambda we just moved inside the trampolined()...
            transform_lambda.recurse(tree.args[0].body)  # ...but recurse inside it
        return tree

    def transform_retexpr(tree):  # input: expression in return-value position
        return _transform_tailcall_retexpr(tree, call_cb=None, data_cb=None, iden="tco")

    newtree = []
    for stmt in tree:
        stmt = transform_return.recurse(stmt)
        stmt = transform_def.recurse(stmt)
        stmt = transform_lambda.recurse(stmt)
        newtree.append(stmt)
    return newtree

@Walker
def _detect_lambda(tree, *, collect, stop, **kw):
    """Find which lambdas appear explicitly in tree.

    Useful in block macros. Run ``_detect_lambda.collect(tree)`` before expanding
    any nested macros (which may generate more lambdas that your block macro
    is not interested in).

    This ignores any "lambda e: ..." added by an already expanded do[],
    to support a surrounding ``with multilambda`` block.

    The return value from ``.collect`` is a ``list``of ``id(l)``, where ``l``
    is a Lambda node that explicitly appears in ``tree``.
    """
    if _isdo(tree):
        stop()  # don't recurse into the "lambda e: ..." added by do[] (surrounding multilambda block)
        # but recurse inside them
        for item in tree.args:  # each arg to dof() is a lambda
            _detect_lambda.collect(item.body)
    if type(tree) is Lambda:
        collect(id(tree))
    return tree

def _transform_tailcall_retexpr(tree, call_cb, data_cb, iden):
    """Analyze an expression in return-value position and transform any tail calls to use fasttco.

    A call may only appear in tail position with respect to the whole expression.

    This recursively handles also ``a if p else b``, ``and``, ``or``, and
    ``unpythonic.syntax.do[]``.

    call_cb(tree): tree -> tree, callback for Call nodes for extra transformations
    data_cb(tree): tree -> tree, callback for inert data for extra transformations
    iden: str, name of the block macro using this, for syntax error message
    """
    transform_call = call_cb or (lambda tree: tree)
    transform_data = data_cb or (lambda tree: tree)
    # Here we need to be very, very selective so this is not a Walker.
    def transform(tree):  # input: expression in return-value position
        # TODO: support let[], letseq[], letrec[] (recurse on body)
        if _isdo(tree):
            # do[] in return-value position. May be generated also by
            # a surrounding "with multilambda" block.
            tree.args[-1].body = transform(tree.args[-1].body)
        elif type(tree) is Call:  # apply TCO
            tree.args = [tree.func] + tree.args
            tree.func = hq[jump]
            tree = transform_call(tree)  # apply possible other transforms
        elif type(tree) is IfExp:
            # only either body or orelse runs, so either (or both) of them may be a tail call.
            # test may have any code, including normal calls; these are not transformed.
            tree.body = transform(tree.body)
            tree.orelse = transform(tree.orelse)
        # TODO: what to do about "not"? "return not f(...)" is not a tail-call since
        # the "not" applies after f; maybe we should disallow it to avoid confusion?
        elif type(tree) is BoolOp:  # and, or
            # and/or is a combined test-and-return. Note any number of these may be nested.
            #
            # Since an and/or may evaluate any number of items before returning,
            # we allow a tail-call only in the last item of the topmost and/or.
            for expr in tree.values[:-1]:
                validate_nocall.recurse(expr)  # recursion checks nested BoolOps, IfExps (except tail pos)
            if iscompound(tree.values[-1]):
                # other items: inert data (unless a property, but doesn't matter if used reasonably)
                if len(tree.values) > 2:
                    op_of_others = BoolOp(op=tree.op, values=tree.values[:-1],
                                          lineno=tree.lineno, col_offset=tree.col_offset)
                else:
                    op_of_others = tree.values[0]
                if type(tree.op) is Or:
                    # or(data1, ..., datan, tail-call) --> it if any(others) else tail-call
                    tree = aif.transform(Tuple(elts=[op_of_others,
                                                     transform_data(Name(id="it",
                                                                         lineno=tree.lineno,
                                                                         col_offset=tree.col_offset)),
                                                     transform(tree.values[-1])],
                                               lineno=tree.lineno, col_offset=tree.col_offset)) # tail-call item
                elif type(tree.op) is And:
                    # and(data1, ..., datan, tail-call) --> tail-call if all(others) else False
                    fal = q[False]
                    fal = copy_location(fal, tree)
                    tree = IfExp(test=op_of_others,
                                 body=transform(tree.values[-1]),
                                 orelse=transform_data(fal))
                else:  # cannot happen
                    assert False, "unknown BoolOp type {}".format(tree.op)
            else:  # optimization: BoolOp with inert data items only
                tree = transform_data(tree)
        else:
            tree = transform_data(tree)
        return tree
    def iscompound(tree):
        # this must match the handlers in transform() (but do[] is a Call)
        return type(tree) in (Call, IfExp, BoolOp)
    @Walker
    def validate_nocall(tree, **kw):
        if type(tree) is Call:
            assert False, "in a return value in a 'with {}' block, call allowed only in tail position.".format(iden)
        return tree
    return transform(tree)

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
    return transform.recurse(tree, quotelevel=0)

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
