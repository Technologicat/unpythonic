#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""unpythonic.syntax: Toto, I've a feeling we're not in Python anymore.

Requires MacroPy (package ``macropy3`` on PyPI).
"""

# TODO:  All macros are defined in this module, because MacroPy (as of 1.1.0b2)
# does not have a mechanism for re-exporting macros defined in another module.

# TODO: avoid mutating original tree in implementations

from macropy.core.macros import Macros
from macropy.core.walkers import Walker
from macropy.core.quotes import macros, q, u, ast_literal, name
from macropy.core.hquotes import macros, hq

from functools import partial
from ast import Call, arg, keyword, With, withitem, Tuple, \
                Name, Attribute, Load, BinOp, LShift, \
                Subscript, Index, Slice, ExtSlice, Lambda, List, \
                copy_location, Assign, FunctionDef, \
                ListComp, SetComp, GeneratorExp, DictComp, \
                arguments, If, Num, Return

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
    return do.transform(newtree)

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

# TODO: use TCO in continuations. See what MacroPy's @tco can do.
@macros.block
def continuations(tree, gen_sym, **kw):
    """[syntax, block] Semi-implicit continuations.

    Roughly, this allows saving the control state and then jumping back later
    (at any time, while still within the block). Example use cases:

      - Tree traversal (possibly multiple trees simultaneously, with the
        current position in each tracked automatically)
      - McCarthy's amb operator

    This is a loose pythonification of Paul Graham's continuation-passing macros,
    which implement continuations by chaining closures and passing the continuation
    semi-implicitly. For details, see chapter 20 in On Lisp:

        http://paulgraham.com/onlisp.html

    The motivation is that continuations are most readily implemented when the
    program is written in continuation-passing style (CPS), but that is unreadable
    for humans.

    This macro partly automates the CPS transformation, so that at the use site,
    we can write CPS code in a much more readable fashion.

    There are certain restrictions that the code in the ``with continuations``
    block must conform to:

      - Functions which make use of continuations, or call other functions that do,
        must be defined within the ``with continuations`` block, using ``def``.
        (For simplicity, we do not support continuations for lambdas.)

      - The ``with continuations`` block will automatically transform all ``def``
        function definitions and ``return`` statements to use the continuation
        machinery.

        Hence, functions that **don't** use continuations **must** be defined
        **outside** the block.

      - The creation of a continuation point is a tail call; it will cause the
        original function to return. After the ``with cc``, any remaining
        statements in the original function body are **ignored**.

        Or paraphrasing PG: any code to be evaluated after a ``with cc``
        should be put in its body. If we want to have several ``with cc``
        blocks one after another, they must be nested.

    **Creating a continuation point**::

        with cc[func(arg0, ..., k0=v0, ...)] as r:
            body0
            ...

        with cc[func(arg0, ..., k0=v0, ...)] as (r0, ...):
            body0
            ...

    In the second variant, **note the parentheses**. Syntactically, these names
    are fed into the same context manager, so they **must** be given as a tuple.

    The abbreviation *cc* means *call with continuation*, also being short to type.
    This marks a continuation point, calling ``func`` with continuations enabled.
    The body is the continuation.

    A ``with cc`` is only meaningful inside a function definition. At the top
    level of the ``with continuations`` block, it is possible to call a function
    using continuations normally, without creating a continuation point.

    Semantically, this captures the result of continuation-enabled ``func``, and
    locally binds it to ``r``, or if multiple-values (represented by a tuple),
    to ``r0, ...``. (To bind a tuple result to a single name, just use the first
    variant.) Then it runs the body, with the captured values available.

    **How it works**:

    Internally, ``with cc`` writes a function definition for the continuation,
    moving the provided body into the body of the function, and setting its
    formal parameter list as ``(r0, ..., *, _cont)``.

    Then it calls ``func`` with ``_cont`` set to that new function, and
    returns the result. This ``return`` terminates the original function.
    """
    # We don't have analogs of PG's "=lambda" and "=apply"; we don't currently
    # support continuations for lambdas, and Python doesn't need "apply"
    # to pass in varargs.

    # Add _cont as a keyword-only parameter to FunctionDef.
    # This corresponds to PG's "=defun", but we don't need to generate a macro.
    @Walker
    def transform_def(tree, **kw):
        if type(tree) is FunctionDef:
            tree.args.kwonlyargs = [arg(arg="_cont")] + tree.args.kwonlyargs
            # default cont is whatever _cont is in lexical scope *at the def site*
            # (so for top-level functions it is identity; for nested functions
            #  it is the outer function's current continuation)
            # TODO: is this a good idea? Should we always default to top-level cont?
            tree.args.kw_defaults = [q[name["_cont"]]] + tree.args.kw_defaults
        return tree
    # return value --> return _cont(value)
    # return v1, ..., vn --> return _cont(*(v1, ..., vn))
    # This corresponds to PG's "=values".
    # Ours is applied automatically to all return statements in the block.
    @Walker
    def transform_return(tree, **kw):
        if type(tree) is Return:
            # TODO: support Return with Ifexp
            # return --> return None  (bare return has value=None in the AST)
            value = tree.value or q[None]
            # handle multiple-return-values like the rest of unpythonic does
            # (returning a tuple means multiple return values)
            if type(value) is Tuple:
                # unpack the values to _cont's arglist
                thecall = q[name["_cont"](*ast_literal[value])]
            else:
                thecall = q[name["_cont"](ast_literal[value])]
            return Return(value=thecall)
        return tree
    # cc[func(arg0, ..., k0=v0, ...)] --> func(arg0, ..., _cont=_cont, k0=v0, ...)
    # This roughly corresponds to PG's "=funcall".
    def iscc(tree):
        return type(tree) is Subscript and type(tree.value) is Name and tree.value.id == "cc"
    @Walker
    def transform_cc(tree, *, contname, **kw):  # contname: name of function (as bare str) to use as continuation
        if iscc(tree):
            if not (type(tree.slice) is Index and type(tree.slice.value) is Call):
                assert False, "cc: expected a single function call as subscript"
            thecall = tree.slice.value
            thecall.keywords = [keyword(arg="_cont", value=q[name[contname]])] + thecall.keywords
            return thecall  # discard the cc[] wrapper
        return tree
    # Inside FunctionDef nodes:
    #     with cc[...] as ...: --> CPS transformation
    # This corresponds to PG's "=bind".
    def iswithcc(tree):
        if type(tree) is With and len(tree.items) == 1:
            if iscc(tree.items[0].context_expr):
                return True
        return False
    @Walker
    def transform_withcc(tree, *, toplevel, set_ctx, **kw):
        if type(tree) is FunctionDef:
            set_ctx(toplevel=False)
        if not iswithcc(tree):
            return tree
        if toplevel:
            assert False, "with cc[...] as ... may only appear inside a function definition"
        ctxmanager = tree.items[0].context_expr
        optvars = tree.items[0].optional_vars
        if optvars:
            if type(optvars) is Name:
                posargs = [optvars.id]
            elif type(optvars) in (List, Tuple):
                if not all(type(x) is Name for x in optvars.elts):
                    assert False, "with cc[...] as ... expected only names in as-part tuple/list"
                posargs = list(x.id for x in optvars.elts)
            else:
                assert False, "with cc[...] as ... expected a name, list or tuple in as-part"
        else:
            posargs = []
        # Create the continuation function, set our body as its body.
        # Any return statements in the body have already been transformed,
        # because they appear literally in the code at the use site.
        thename = gen_sym("cont")
        funcdef = FunctionDef(name=thename,
                              args=arguments(args=[arg(arg=x) for x in posargs],
                                             kwonlyargs=[],  # patched later by transform_def
                                             vararg=None,
                                             kwarg=None,
                                             defaults=[],
                                             kw_defaults=[]),
                              body=tree.body,
                              decorator_list=[],
                              returns=None)  # return annotation not used here
        # Set up the call to func, specifying our new function as its continuation
        thecall = transform_cc.recurse(ctxmanager, contname=thename)
        # output a block that makes the function definition and
        # then calls func, **as a tail call**
#        with q as newtree:
#            if 1:
#                ast_literal[funcdef]  # TODO: doesn't work, why?
#                return ast_literal[thecall]
#        return newtree[0]  # the if statement
        newtree = If(test=Num(n=1),
                     body=[q[ast_literal[funcdef]],
                           Return(value=q[ast_literal[thecall]])],
                     orelse=[])
        return newtree
    # set up the default continuation that just returns its args
    newtree = [Assign(targets=[q[name["_cont"]]], value=hq[identity])]
    # CPS conversion
    for stmt in tree:
        # transform "return" statements before withcc's tail calls generate new ones.
        stmt = transform_return.recurse(stmt)
        stmt = transform_withcc.recurse(stmt, toplevel=True)  # transform "with cc[]" calls
        stmt = transform_cc.recurse(stmt, contname="_cont")   # transform "cc[]" calls
        # transform all defs, including those added by withcc.
        stmt = transform_def.recurse(stmt)
        newtree.append(stmt)
    return newtree

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
