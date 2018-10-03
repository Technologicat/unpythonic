#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""unpythonic.syntax: Toto, I've a feeling we're not in Python anymore.

Requires MacroPy (package ``macropy3`` on PyPI).
"""

# TODO:  All macros are defined in this module, because MacroPy (as of 1.1.0)
# does not have a mechanism for re-exporting macros defined in another module.

# Naming convention:
#   - mymac is the macro, for use in normal run-time code.
#   - _mymac, if available, is the syntax transformer function that does the
#     actual work. Can be directly called from inside macros, to delegate
#     some work to another macro.

from macropy.core.macros import Macros
from macropy.core.walkers import Walker
from macropy.core.quotes import macros, q, u, ast_literal, name
from macropy.core.hquotes import macros, hq

from functools import partial
from ast import Call, arg, keyword, With, withitem, Tuple, \
                Name, Attribute, Load, BinOp, LShift

from unpythonic.it import flatmap, uniqify, rev
from unpythonic.fun import curry as curryf
from unpythonic.dynscope import dyn
from unpythonic.lispylet import letrec as letrecf, let as letf
from unpythonic.seq import do as dof, begin as beginf

# insist, deny are just for passing through to the using module that imports us.
from unpythonic.amb import forall as forallf, choice as choicef, insist, deny

macros = Macros()

# functions that do the work


# -----------------------------------------------------------------------------

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
def aif(tree, gen_sym, **kw):
    """[syntax, expr] Anaphoric if.

    Usage::

        from unpythonic.syntax import macros, aif, it

        aif[test, then, otherwise]

    Inside the ``then`` and ``otherwise`` branches, the magic identifier ``it``
    refers to the value of ``test``.

    This expands into a ``let`` and an expression-form ``if``.
    """
    return _aif(tree, gen_sym)

def _aif(tree, gen_sym):
    test, then, otherwise = tree.elts
    body = q[ast_literal[then] if it else ast_literal[otherwise]]
    bindings = [q[(it, ast_literal[test])]]
    return _let(body, bindings, gen_sym)

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
            newargs = []
            newargs.append(tree.func)
            newargs.extend(tree.args)
            tree.args = newargs
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

    This allows human-readable multi-branch conditionals in a lambda.
    """
    return _cond(tree)

def _cond(tree):
    if type(tree) is not Tuple:
        assert False, "Expected cond[test1, then1, test2, then2, ..., otherwise]"
    def build(elts):
        if len(elts) == 1:  # final "otherwise" branch
            return elts[0]
        if not elts:
            assert False, "Expected cond[test1, then1, test2, then2, ..., otherwise]"
        test, then, *more = elts
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
    return _simple_let(tree, args)

def _simple_let(tree, args):
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
    return _simple_letseq(tree, args)

def _simple_letseq(tree, args):
    if not args:
        return tree
    first, *rest = args
    return _simple_let(_simple_letseq(tree, rest), [first])

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

    where ``bindings`` is a comma-separated sequence of pairs ``(name, value)``
    and ``body`` is an expression. The names bound by ``let`` are local;
    they are available in ``body``, and do not exist outside ``body``.

    Each ``name`` in the same ``let`` must be unique.

    Assignment to let-bound variables is supported with syntax such as ``x << 42``.
    This is an expression, performing the assignment, and returning the new value.

    Technical points:

        - In reality, the let-bound variables live in an ``unpythonic.env``.
          This macro performs the magic to make them look (and pretty much behave)
          like lexical variables.

        - Over ``unpythonic.lispylet.let``, the macro version needs no quotes
          around variable names in bindings.

        - The body is automatically wrapped in a ``lambda e: ...``.

        - For all ``x`` in bindings, the macro transforms ``x --> e.x``.

        - Lexical scoping is respected (so ``let`` constructs can be nested)
          by actually using a unique name (gensym) instead of just ``e``.
    """
    return _let(tree, args, gen_sym)
def _let(tree, args, gen_sym):
    return _letimpl(tree, args, "let", gen_sym)

@macros.expr
def letseq(tree, args, gen_sym, **kw):
    """[syntax, expr] Let with sequential binding (like Scheme/Racket let*).

    Like ``let``, but bindings take effect sequentially. Later bindings
    shadow earlier ones if the same name is used multiple times.

    Expands to nested ``let`` expressions.
    """
    return _letseq(tree, args, gen_sym)
def _letseq(tree, args, gen_sym):
    if not args:
        return tree
    first, *rest = args
    return _let(_letseq(tree, rest, gen_sym), [first], gen_sym)

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
    return _letrec(tree, args, gen_sym)
def _letrec(tree, args, gen_sym):
    return _letimpl(tree, args, "letrec", gen_sym)

def _letimpl(tree, args, mode, gen_sym):  # args; ast.Tuple: (k1, v1), (k2, v2), ..., (kn, vn)
    names, values = zip(*[a.elts for a in args])  # --> (k1, ..., kn), (v1, ..., vn)
    names = [k.id for k in names]

    e = gen_sym("e")
    envset = Attribute(value=hq[name[e]], attr="set", ctx=Load())

    t = partial(_common_transform, envname=e, varnames=names, setter=envset)
    if mode == "letrec":
        values = [t(b) for b in values]  # RHSs of bindings
    tree = t(tree)  # body

    binding_pairs = [q[(u[k], ast_literal[v])] for k, v in zip(names, values)]
    func = letf if mode == "let" else letrecf
    return hq[func((ast_literal[binding_pairs],), ast_literal[tree])]

def _common_transform(subtree, envname, varnames, setter):
    subtree = _transform_assignment.recurse(subtree, names=varnames, setter=setter)  # x << val --> e.set('x', val)
    subtree = _transform_name.recurse(subtree, names=varnames, envname=envname)  # x --> e.x
    return _envwrap(subtree, envname=envname)  # ... -> lambda e: ...

def _isassign(tree):  # detect "x << 42" syntax to assign variables in an environment
    return type(tree) is BinOp and type(tree.op) is LShift and type(tree.left) is Name

# x << val --> e.set('x', val)  (for names bound in this environment)
@Walker
def _transform_assignment(tree, *, names, setter, **kw):
    if not _isassign(tree):
        return tree
    varname = tree.left.id
    if varname not in names:  # each let handles only its own varnames
        return tree
    value = tree.right
    return q[ast_literal[setter](u[varname], ast_literal[value])]

# x --> e.x  (for names bound in this environment)
@Walker
def _transform_name(tree, *, names, envname, stop, **kw):
    if type(tree) is Attribute:
        stop()
    elif type(tree) is Name and tree.id in names:
        return Attribute(value=hq[name[envname]], attr=tree.id, ctx=Load())
    return tree

# # ... -> lambda e: ...
def _envwrap(tree, envname):
    lam = q[lambda: ast_literal[tree]]
    lam.args.args = [arg(arg=envname)]
    return lam

# -----------------------------------------------------------------------------

# This stuff borrows some of the "let" machinery.

@macros.expr
def do(tree, gen_sym, **kw):
    """[syntax, expr] Stuff imperative code into a lambda.

    Return value is the value of the last expression inside the do.

    Usage::

        do[body0, ...]

    Example::

        do[x << 42,
           print(x),
           x << 23,
           x]

    This is sugar on top of ``unpythonic.seq.do``. Assignment is supported
    via syntax such as ``x << 42``.

    Note: if you nest a ``let`` inside the ``do``, the assignments to the ``let``
    variables inside the ``let`` are not affected. ``do`` only captures those
    assignments that do not belong to any nested construct.

    This is essentially thanks to MacroPy (as of 1.1.0) expanding macros in an
    inside-out order, so the nested constructs transform first.
    """
    return _do(tree, gen_sym)

def _do(tree, gen_sym):
    if type(tree) is not Tuple:
        assert False, "do body: expected a sequence of comma-separated expressions"

    e = gen_sym("e")
    # Must use env.__setattr__ to define new names; env.set only rebinds.
    # But to keep assignments chainable, use begin(setattr(e, 'x', val), val).
    sa = Attribute(value=hq[name[e]], attr="__setattr__", ctx=Load())
    envset = hq[lambda k, v: beginf(ast_literal[sa](k, v), v)]

    @Walker
    def _find_assignments(tree, collect, **kw):
        if _isassign(tree):
            collect(tree.left.id)
        return tree
    names = list(uniqify(_find_assignments.collect(tree)))

    lines = [_common_transform(line, e, names, envset) for line in tree.elts]
    return hq[dof(ast_literal[lines])]

@macros.expr
def do0(tree, gen_sym, **kw):  # unpythonic.seq.do0, with macro transformation
    """[syntax, expr] Like do, but return the value of the first expression."""
    return _do0(tree, gen_sym)

def _do0(tree, gen_sym):
    if type(tree) is not Tuple:
        assert False, "do0 body: expected a sequence of comma-separated expressions"
    elts = tree.elts
    newelts = []
    newelts.append(q[_do0_result << (ast_literal[elts[0]])])
    newelts.extend(elts[1:])
    newelts.append(q[_do0_result])
    return _do(q[(ast_literal[newelts],)], gen_sym)

# -----------------------------------------------------------------------------

@macros.expr
def forall(tree, gen_sym, **kw):
    """[syntax, expr] Nondeterministic evaluation.

    Sugar on top of ``unpythonic.amb.forall``.

      - ``choice(name, iterable)`` becomes ``name << iterable``
      - ``insist``, ``deny`` work as usual
      - no need for ``lambda e: ...`` wrappers
    """
    if type(tree) is not Tuple:
        assert False, "forall body: expected a sequence of comma-separated expressions"
    body = tree.elts
    e = gen_sym("e")
    names = []  # variables bound by this forall
    lines = []
    def transform(tree):  # like _common_transform but no assignment conversion
        tree = _transform_name.recurse(tree, names=names, envname=e)  # x --> e.x
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

# -----------------------------------------------------------------------------

# TODO: support default values for arguments. Requires support in MacroPy for named arguments.
# TODO: implicit do instead of just begin? Would give a local-definition context.
@macros.expr
def λ(tree, args, **kw):
    """[syntax, expr] Rackety lambda with implicit begin.

    Usage::

      λ(arg0, ...)[body0, ...]

    Limitations:

      - No *args or **kwargs.
      - No default values for arguments.
    """
    return _λ(tree, args)

def _λ(tree, args, **kw):
    names = [k.id for k in args]
    lam = hq[lambda: beginf(ast_literal[tree.elts])]   # inject begin(...)
    lam.args.args = [arg(arg=x) for x in names]  # inject args
    return lam

# -----------------------------------------------------------------------------

@macros.block
def prefix(tree, **kw):
    """Write Python like Lisp: the first item is the operator.

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
          specified by multiple ``kw`` operators, the rightmost one wins.

          **Note**: Python itself prohibits having repeated named args in the **same**
          ``kw`` operator, because it uses the function call syntax. If you get a
          `SyntaxError: keyword argument repeated` with no useful traceback,
          check any recent ``kw`` operators you have added in prefix blocks.

          A ``kw(...)`` operator in a quoted tuple (not a function call) is an error.

    Current limitations:

        - passing ``*args`` and ``**kwargs`` not supported
          (workarounds: ``call(...)``; Python's usual function call syntax)
    """
    return _prefix(tree)

def _prefix(tree):
    isquote = lambda tree: type(tree) is Name and tree.id == "q"
    isunquote = lambda tree: type(tree) is Name and tree.id == "u"
    def iskwargs(tree):
        if type(tree) is not Call: return False
        if type(tree.func) is not Name: return False
        return tree.func.id == "kw"
    @Walker
    def transform(tree, *, quotelevel, set_ctx, **kw):
        if type(tree) is not Tuple:
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
        kwargs = list(uniqify(rev(kwargs), key=lambda x: x.arg))  # latest wins
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
