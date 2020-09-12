# -*- coding: utf-8 -*-
"""unpythonic.syntax: Toto, I've a feeling we're not in Python anymore.

Requires MacroPy (package ``macropy3`` on PyPI).
"""

from ..dynassign import dyn, make_dynvar

# This module contains the macro interface and docstrings; the submodules
# contain the actual syntax transformers (regular functions that process ASTs)
# that implement the macros.

# Syntax transformers and internal utilities
from .autoref import autoref as _autoref
from .curry import curry as _curry
from .dbg import dbg_block as _dbg_block, dbg_expr as _dbg_expr
from .forall import forall as _forall
from .ifexprs import aif as _aif, cond as _cond
from .lambdatools import (multilambda as _multilambda,
                          namedlambda as _namedlambda,
                          quicklambda as _quicklambda,
                          envify as _envify)
from .lazify import lazify as _lazify, lazyrec as _lazyrec
from .letdo import (do as _do, do0 as _do0,
                    let as _let, letseq as _letseq, letrec as _letrec,
                    dlet as _dlet, dletseq as _dletseq, dletrec as _dletrec,
                    blet as _blet, bletseq as _bletseq, bletrec as _bletrec)
from .letdoutil import (UnexpandedLetView as _UnexpandedLetView,
                        canonize_bindings as _canonize_bindings)
from .letsyntax import (let_syntax_expr as _let_syntax_expr,
                        let_syntax_block as _let_syntax_block)
from .nb import nb as _nb
from .prefix import prefix as _prefix
from .tailtools import (autoreturn as _autoreturn, tco as _tco,
                        continuations as _continuations)
from .testingtools import (test_expr as _test_expr,
                           test_expr_signals as _test_expr_signals,
                           test_expr_raises as _test_expr_raises,
                           test_block as _test_block,
                           test_block_signals as _test_block_signals,
                           test_block_raises as _test_block_raises,
                           fail_expr as _fail_expr,
                           error_expr as _error_expr,
                           warn_expr as _warn_expr)

# Re-exports (for client code that uses us)
from .dbg import dbgprint_block, dbgprint_expr  # noqa: F401
from .forall import insist, deny  # noqa: F401
from .ifexprs import it  # noqa: F401
from .lambdatools import f, _  # noqa: F401
from .letdoutil import where  # noqa: F401
from .lazify import force, force1  # noqa: F401
from .letdo import local, delete  # noqa: F401
from .letsyntax import block, expr  # noqa: F401
from .prefix import q, u, kw  # noqa: F401  # TODO: bad names, MacroPy uses them too.
from .tailtools import call_cc  # noqa: F401
from .testingtools import the  # noqa: F401

# Initialize the macro interface
from macropy.core.macros import Macros
macros = Macros()

# Inject default debug printer for expressions.
#
# All the macro interface stuff must happen in this module, so we can't
# decorate the original directly in the implementation module.
dbgprint_expr = macros.expose_unhygienic(dbgprint_expr)

# We pass gen_sym as a dynvar so it doesn't need to appear in the
# formal parameter lists of the underlying syntax transformers.
#
# If you add new macros, use ``with dyn.let(gen_sym=gen_sym):`` if your
# syntax transformer (or any syntax transformers it calls) needs gen_sym.
# This default is here to yell if it's needed and missing; the traceback
# will tell exactly which syntax transformer needed it.
def nogensym(*args, **kwargs):
    raise RuntimeError("No gen_sym function set")  # pragma: no cover
make_dynvar(gen_sym=nogensym)

# -----------------------------------------------------------------------------

# The "kw" we have here is the parameter from MacroPy; the "kw" we export (that
# flake8 thinks conflicts with this) is the runtime stub for our `prefix` macro.
@macros.block
def autoref(tree, args, *, target, gen_sym, **kw):  # noqa: F811
    """Implicitly reference attributes of an object.

    Example::

        e = env(a=1, b=2)
        c = 3
        with autoref(e):
            a
            b
            c

    The transformation is applied in ``Load`` context only. ``Store`` and ``Del``
    are not redirected.

    Useful e.g. with the ``.mat`` file loader of SciPy.

    **CAUTION**: `autoref` is essentially the `with` construct of JavaScript
    (which is completely different from Python's meaning of `with`), which is
    nowadays deprecated. See:

        https://www.ecma-international.org/ecma-262/6.0/#sec-with-statement
        https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Statements/with
        https://2ality.com/2011/06/with-statement.html

    **CAUTION**: The auto-reference `with` construct was deprecated in JavaScript
    **for security reasons**. Since the autoref'd object **will hijack all name
    lookups**, use `with autoref` only with an object you trust!

    **CAUTION**: `with autoref` also complicates static code analysis or makes it
    outright infeasible, for the same reason. It is impossible to statically know
    whether something that looks like a bare name in the source code is actually
    a true bare name, or a reference to an attribute of the autoref'd object.
    That status can also change at any time, since the lookup is dynamic, and
    attributes can be added and removed dynamically.
    """
    with dyn.let(gen_sym=gen_sym):
        return _autoref(block_body=tree, args=args, asname=target)

# -----------------------------------------------------------------------------

@macros.expr
def aif(tree, *, gen_sym, **kw):  # noqa: F811
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
    with dyn.let(gen_sym=gen_sym):
        return _aif(tree)

@macros.expr
def cond(tree, *, gen_sym, **kw):  # noqa: F811
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
    with dyn.let(gen_sym=gen_sym):
        return _cond(tree)

# -----------------------------------------------------------------------------

@macros.block
def curry(tree, **kw):  # technically a list of trees, the body of the with block  # noqa: F811
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

    Lexically inside a ``with curry`` block, the auto-curried function calls
    will skip the curry if the function is uninspectable, instead of raising
    ``TypeError`` as usual.

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
        assert add3(1)(2)(3) == 6
    """
    return _curry(block_body=tree)

# -----------------------------------------------------------------------------

@macros.expr
def let(tree, args, *, gen_sym, **kw):  # noqa: F811
    """[syntax, expr] Introduce local bindings.

    This is sugar on top of ``unpythonic.lispylet.let``.

    Usage::

        let((k0, v0), ...)[body]
        let((k0, v0), ...)[[body0, ...]]

    where ``body`` is an expression. The names bound by ``let`` are local;
    they are available in ``body``, and do not exist outside ``body``.

    Alternative haskelly syntax is also available::

        let[((k0, v0), ...) in body]
        let[((k0, v0), ...) in [body0, ...]]
        let[body, where((k0, v0), ...)]
        let[[body0, ...], where((k0, v0), ...)]

    For a body with multiple expressions, use an extra set of brackets,
    as shown above. This inserts a ``do``. Only the outermost extra brackets
    are interpreted specially; all others in the bodies are interpreted
    as usual, as lists.

    Note that in the haskelly syntax, the extra brackets for a multi-expression
    body should enclose only the ``body`` part.

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

        - For all ``x`` in bindings, the macro transforms lookups ``x --> e.x``.

        - Lexical scoping is respected (so ``let`` constructs can be nested)
          by actually using a unique name (gensym) instead of just ``e``.

        - In the case of a multiple-expression body, the ``do`` transformation
          is applied first to ``[body0, ...]``, and the result becomes ``body``.
    """
    with dyn.let(gen_sym=gen_sym):
        return _destructure_and_apply_let(tree, args, _let)

@macros.expr
def letseq(tree, args, *, gen_sym, **kw):  # noqa: F811
    """[syntax, expr] Let with sequential binding (like Scheme/Racket let*).

    Like ``let``, but bindings take effect sequentially. Later bindings
    shadow earlier ones if the same name is used multiple times.

    Expands to nested ``let`` expressions.
    """
    with dyn.let(gen_sym=gen_sym):
        return _destructure_and_apply_let(tree, args, _letseq)

@macros.expr
def letrec(tree, args, *, gen_sym, **kw):  # noqa: F811
    """[syntax, expr] Let with mutually recursive binding.

    Like ``let``, but bindings can see other bindings in the same ``letrec``.

    Each ``name`` in the same ``letrec`` must be unique.

    The definitions are processed sequentially, left to right. A definition
    may refer to any previous definition. If ``value`` is callable (lambda),
    it may refer to any definition, including later ones.

    This is useful for locally defining mutually recursive functions.
    """
    with dyn.let(gen_sym=gen_sym):
        return _destructure_and_apply_let(tree, args, _letrec)

# NOTE: Unfortunately, at the macro interface, the invocations `let()[...]`
# (Call, empty args) and `let[...]` (just a Name) are indistinguishable,
# because MacroPy does too much automatically, sending us `args = ()`
# in both cases.
#
# So when `args = ()`, this function assumes haskelly let syntax
# `let[(...) in ...]` or `let[..., where(...)]`. In these cases,
# both the bindings and the body reside inside the brackets (i.e.,
# in the AST contained in the `tree` argument).
#
# allow_call_in_name_position: used by let_syntax to allow template definitions.
def _destructure_and_apply_let(tree, args, expander, allow_call_in_name_position=False):
    if args:
        bs = _canonize_bindings(args, locref=tree, allow_call_in_name_position=allow_call_in_name_position)
        return expander(bindings=bs, body=tree)
    # haskelly syntax, let[(...) in ...], let[..., where(...)]
    view = _UnexpandedLetView(tree)  # note "tree" here is only the part inside the brackets
    return expander(bindings=view.bindings, body=view.body)

# -----------------------------------------------------------------------------
# Decorator versions, for "let over def".

@macros.decorator
def dlet(tree, args, *, gen_sym, **kw):  # noqa: F811
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
    the regular syntax ``name = value`` creates a local variable in the
    lexical scope of the ``def``.
    """
    with dyn.let(gen_sym=gen_sym):
        return _destructure_and_apply_let(tree, args, _dlet)

@macros.decorator
def dletseq(tree, args, *, gen_sym, **kw):  # noqa: F811
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
    with dyn.let(gen_sym=gen_sym):
        return _destructure_and_apply_let(tree, args, _dletseq)

@macros.decorator
def dletrec(tree, args, *, gen_sym, **kw):  # noqa: F811
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
    with dyn.let(gen_sym=gen_sym):
        return _destructure_and_apply_let(tree, args, _dletrec)

@macros.decorator
def blet(tree, args, *, gen_sym, **kw):  # noqa: F811
    """[syntax, decorator] def --> let block.

    Example::

        @blet((x, 21))
        def result():
            return 2*x
        assert result == 42
    """
    with dyn.let(gen_sym=gen_sym):
        return _destructure_and_apply_let(tree, args, _blet)

@macros.decorator
def bletseq(tree, args, *, gen_sym, **kw):  # noqa: F811
    """[syntax, decorator] def --> letseq block.

    Example::

        @bletseq((x, 1),
                 (x, x+1),
                 (x, x+2))
        def result():
            return x
        assert result == 4
    """
    with dyn.let(gen_sym=gen_sym):
        return _destructure_and_apply_let(tree, args, _bletseq)

@macros.decorator
def bletrec(tree, args, *, gen_sym, **kw):  # noqa: F811
    """[syntax, decorator] def --> letrec block.

    Example::

        @bletrec((evenp, lambda x: (x == 0) or oddp(x - 1)),
                 (oddp,  lambda x: (x != 0) and evenp(x - 1)))
        def result():
            return evenp(42)
        assert result is True

    Because names inside a ``def`` have mutually recursive scope,
    an almost equivalent pure Python solution (no macros) is::

        from unpythonic.misc import call

        @call
        def result():
            evenp = lambda x: (x == 0) or oddp(x - 1)
            oddp = lambda x: (x != 0) and evenp(x - 1)
            return evenp(42)
        assert result is True
    """
    with dyn.let(gen_sym=gen_sym):
        return _destructure_and_apply_let(tree, args, _bletrec)

# -----------------------------------------------------------------------------
# Imperative code in expression position.

@macros.expr
def do(tree, *, gen_sym, **kw):  # noqa: F811
    """[syntax, expr] Stuff imperative code into an expression position.

    Return value is the value of the last expression inside the ``do``.
    See also ``do0``.

    Usage::

        do[body0, ...]

    Example::

        do[local[x << 42],
           print(x),
           x << 23,
           x]

    This is sugar on top of ``unpythonic.seq.do``, but with some extra features.

        - To declare and initialize a local name, use ``local[name << value]``.

          The operator ``local`` is syntax, not really a function, and it
          only exists inside a ``do``.

        - By design, there is no way to create an uninitialized variable;
          a value must be given at declaration time. Just use ``None``
          as an explicit "no value" if needed.

        - Names declared within the same ``do`` must be unique. Re-declaring
          the same name is an expansion-time error.

        - To assign to an already declared local name, use ``name << value``.

    **local name declarations**

    A ``local`` declaration comes into effect in the expression following
    the one where it appears. Thus::

        result = []
        let((lst, []))[do[result.append(lst),       # the let "lst"
                          local[lst << lst + [1]],  # LHS: do "lst", RHS: let "lst"
                          result.append(lst)]]      # the do "lst"
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

        do[local[x << 17],
           let((x, 23))[
             print(x)],  # 23, the "x" of the "let"
           print(x)]     # 17, the "x" of the "do"

    The reason we require local names to be declared is to allow write access
    to lexically outer environments from inside a ``do``::

        let((x, 17))[
              do[x << 23,         # no "local[...]"; update the "x" of the "let"
                 local[y << 42],  # "y" is local to the "do"
                 print(x, y)]]

    With the extra bracket syntax, the latter example can be written as::

        let((x, 17))[[
              x << 23,
              local[y << 42],
              print(x, y)]]

    It's subtly different in that the first version has the do-items in a tuple,
    whereas this one has them in a list, but the behavior is exactly the same.

    Python does it the other way around, requiring a ``nonlocal`` statement
    to re-bind a name owned by an outer scope.

    The ``let`` constructs solve this problem by having the local bindings
    declared in a separate block, which plays the role of ``local``.
    """
    with dyn.let(gen_sym=gen_sym):
        return _do(tree)

@macros.expr
def do0(tree, *, gen_sym, **kw):  # noqa: F811
    """[syntax, expr] Like do, but return the value of the first expression."""
    with dyn.let(gen_sym=gen_sym):
        return _do0(tree)

# -----------------------------------------------------------------------------

@macros.expr
def let_syntax(tree, args, *, gen_sym, **kw):  # noqa: F811
    with dyn.let(gen_sym=gen_sym):  # gen_sym is only needed by the implicit do.
        return _destructure_and_apply_let(tree, args, _let_syntax_expr, allow_call_in_name_position=True)

# Python has no function overloading, but expr and block macros go into
# different parts of MacroPy's macro registry. The registration happens
# as a side effect of the decorator.
#
# Normal run-time code sees only the dynamically latest definition,
# so the docstring goes here.
@macros.block  # noqa: F811
def let_syntax(tree, **kw):  # noqa: F811
    """[syntax] Introduce local **syntactic** bindings.

    **Expression variant**::

        let_syntax((lhs, rhs), ...)[body]
        let_syntax((lhs, rhs), ...)[[body0, ...]]

    Alternative haskelly syntax::

        let_syntax[((lhs, rhs), ...) in body]
        let_syntax[((lhs, rhs), ...) in [body0, ...]]

        let_syntax[body, where((lhs, rhs), ...)]
        let_syntax[[body0, ...], where((lhs, rhs), ...)]

    **Block variant**::

        with let_syntax:
            with block as xs:          # capture a block of statements - bare name
                ...
            with block(a, ...) as xs:  # capture a block of statements - template
                ...
            with expr as x:            # capture a single expression - bare name
                ...
            with expr(a, ...) as x:    # capture a single expression - template
                ...
            body0
            ...

    A single expression can be a ``do[]`` if multiple expressions are needed.

    The bindings are applied **at macro expansion time**, substituting
    the expression on the RHS for each instance of the corresponding LHS.
    Each substitution gets a fresh copy.

    This is useful to e.g. locally abbreviate long function names at macro
    expansion time (with zero run-time overhead), or to splice in several
    (possibly parametric) instances of a common pattern.

    In the expression variant, ``lhs`` may be:

      - A bare name (e.g. ``x``), or

      - A simple template of the form ``f(x, ...)``. The names inside the
        parentheses declare the formal parameters of the template (that can
        then be used in the body).

    In the block variant:

      - The **as-part** specifies the name of the LHS.

      - If a template, the formal parameters are declared on the ``block``
        or ``expr``, not on the as-part (due to syntactic limitations).

    **Templates**

    To make parametric substitutions, use templates.

    Templates support only positional arguments, with no default values.

    Even in block templates, parameters are always expressions (because they
    use the function-call syntax at the use site).

    In the body of the ``let_syntax``, a template is used like a function call.
    Just like in an actual function call, when the template is substituted,
    any instances of its formal parameters on its RHS get replaced by the
    argument values from the "call" site; but ``let_syntax`` performs this
    at macro-expansion time.

    Note each instance of the same formal parameter gets a fresh copy of the
    corresponding argument value.

    **Substitution order**

    This is a two-step process. In the first step, we apply template substitutions.
    In the second step, we apply bare name substitutions to the result of the
    first step. (So RHSs of templates may use any of the bare-name definitions.)

    Within each step, the substitutions are applied **in the order specified**.
    So if the bindings are ``((x, y), (y, z))``, then ``x`` transforms to ``z``.
    But if the bindings are ``((y, z), (x, y))``, then ``x`` transforms to ``y``,
    and only an explicit ``y`` at the use site transforms to ``z``.

    **Notes**

    Inspired by Racket's ``let-syntax`` and ``with-syntax``, see:
        https://docs.racket-lang.org/reference/let.html
        https://docs.racket-lang.org/reference/stx-patterns.html

    **CAUTION**: This is essentially a toy macro system inside the real
    macro system, implemented with the real macro system.

    The usual caveats of macro systems apply. Especially, we support absolutely
    no form of hygiene. Be very, very careful to avoid name conflicts.

    ``let_syntax`` is meant only for simple local substitutions where the
    elimination of repetition can shorten the code and improve readability.

    If you need to do something complex, prefer writing a real macro directly
    in MacroPy.
    """
    return _let_syntax_block(block_body=tree)

@macros.expr
def abbrev(tree, args, *, gen_sym, **kw):  # noqa: F811
    with dyn.let(gen_sym=gen_sym):  # gen_sym is only needed by the implicit do.
        yield _destructure_and_apply_let(tree, args, _let_syntax_expr, allow_call_in_name_position=True)

@macros.block  # noqa: F811
def abbrev(tree, **kw):  # noqa: F811
    """[syntax] Exactly like ``let_syntax``, but expands in the first pass, outside in.

    Because this variant expands before any macros in the body, it can locally
    rename other macros, e.g.::

        abbrev((a, ast_literal))[
                 a[tree1] if a[tree2] else a[tree3]]

    **CAUTION**: Because of the expansion order, nesting ``abbrev`` will not
    lexically scope the substitutions. Instead, the outermost ``abbrev`` expands
    first, and then any inner ones expand with whatever substitutions they have
    remaining.

    If the same name is used on the LHS in two or more nested ``abbrev``,
    any inner ones will likely raise an error (unless the outer substitution
    just replaces a name with another), because also the names on the LHS
    in the inner ``abbrev`` will undergo substitution when the outer
    ``abbrev`` expands.
    """
    yield _let_syntax_block(block_body=tree)

# -----------------------------------------------------------------------------

@macros.expr
def forall(tree, **kw):  # noqa: F811
    """[syntax, expr] Nondeterministic evaluation.

    Fully based on AST transformation, with real lexical variables.
    Like Haskell's do-notation, but here specialized for the List monad.

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
    return _forall(exprs=tree)

# -----------------------------------------------------------------------------

@macros.block
def multilambda(tree, *, gen_sym, **kw):  # noqa: F811
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
    # two-pass macro:
    #   - yield from to first yield the first-pass output
    #   - then return to return the StopIteration final value (second-pass output if any)
    with dyn.let(gen_sym=gen_sym):
        return (yield from _multilambda(block_body=tree))

@macros.block
def namedlambda(tree, **kw):  # noqa: F811
    """[syntax, block] Name lambdas implicitly.

    Lexically inside a ``with namedlambda`` block, any literal ``lambda``
    that is assigned to a name using one of the supported assignment forms
    is named to have the name of the LHS of the assignment. The name is
    captured at macro expansion time.

    Naming modifies the original function object.

    We support:

        - Single-item assignments to a local name, ``f = lambda ...: ...``

        - Assignments to unpythonic environments, ``f << (lambda ...: ...)``

        - Let bindings, ``let[(f, (lambda ...: ...)) in ...]``, using any
          let syntax supported by unpythonic (here using the haskelly let-in
          just as an example).

    Support for other forms of assignment might or might not be added in a
    future version.

    Example::

        with namedlambda:
            f = lambda x: x**3        # assignment: name as "f"

            let((x, 42), (g, None), (h, None))[[
              g << (lambda x: x**2),  # env-assignment: name as "g"
              h << f,                 # still "f" (no literal lambda on RHS)
              (g(x), h(x))]]

            foo = let[(f7, lambda x: x) in f7]  # let-binding: name as "f7"

    The naming is performed using the function ``unpythonic.misc.namelambda``,
    which will update ``__name__``, ``__qualname__`` and ``__code__.co_name``.
    """
    return (yield from _namedlambda(block_body=tree))

@macros.block
def quicklambda(tree, *, gen_sym, **kw):  # noqa: F811
    """[syntax, block] Use ``macropy.quick_lambda`` with ``unpythonic.syntax``.

    To be able to transform correctly, the block macros in ``unpythonic.syntax``
    that transform lambdas (e.g. ``multilambda``, ``tco``) need to see all
    ``lambda`` definitions written with Python's standard ``lambda``.

    However, the highly useful ``macropy.quick_lambda`` uses the syntax
    ``f[...]``, which (to the analyzer) does not look like a lambda definition.
    This macro changes the expansion order, forcing any ``f[...]`` lexically
    inside the block to expand in the first pass.

    Any expression of the form ``f[...]`` (the ``f`` is literal) is understood
    as a quick lambda, whether or not ``f`` and ``_`` are imported at the
    call site.

    Example - a quick multilambda::

        from unpythonic.syntax import macros, multilambda, quicklambda, f, _, local

        with quicklambda, multilambda:
            func = f[[local[x << _],
                      local[y << _],
                      x + y]]
            assert func(1, 2) == 3

    (This is of course rather silly, as an unnamed argument can only be mentioned
    once. If we're giving names to them, a regular ``lambda`` is shorter to write.
    The point is, this combo is now possible.)
    """
    with dyn.let(gen_sym=gen_sym):
        return (yield from _quicklambda(block_body=tree))

@macros.block
def envify(tree, *, gen_sym, **kw):  # noqa: F811
    """[syntax, block] Make formal parameters live in an unpythonic env.

    The purpose is to allow overwriting formals using unpythonic's
    expression-assignment ``name << value``. The price is that the references
    to the arguments are copied into an env whenever an envified function is
    entered.

    Example - PG's accumulator puzzle (http://paulgraham.com/icad.html)::

        with envify:
            def foo(n):
                return lambda i: n << n + i

    Of course, now we can::

        with autoreturn, envify:
            def foo(n):
                lambda i: n << n + i
    """
    with dyn.let(gen_sym=gen_sym):
        return (yield from _envify(block_body=tree))

# -----------------------------------------------------------------------------

@macros.block
def autoreturn(tree, **kw):  # noqa: F811
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
    return (yield from _autoreturn(block_body=tree))

@macros.block
def tco(tree, *, gen_sym, **kw):  # noqa: F811
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
    when used in computing a return value. (``aif[]`` and ``cond[]`` also work.)

    Note only calls **in tail position** will be TCO'd. Any other calls
    are left as-is. Tail positions are:

        - The whole return value, if it is just a single call.

        - Both ``a`` and ``b`` branches of ``a if p else b`` (but not ``p``).

        - The last item in an ``and``/``or``. If these are nested, only the
          last item in the whole expression involving ``and``/``or``. E.g. in::

              (a and b) or c
              a and (b or c)

          in either case, only ``c`` is in tail position, regardless of the
          values of ``a``, ``b``.

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
    ``ec``, ``brk``, ``throw`` is interpreted as invoking an escape
    continuation.
    """
    with dyn.let(gen_sym=gen_sym):
        return (yield from _tco(block_body=tree))

@macros.block
def continuations(tree, *, gen_sym, **kw):  # noqa: F811
    """[syntax, block] call/cc for Python.

    This allows saving the control state and then jumping back later
    (in principle, any time later). Some possible use cases:

      - Tree traversal (possibly a cartesian product of multiple trees, with the
        current position in each tracked automatically).

      - McCarthy's amb operator.

      - Generators. (Though of course, Python already has them.)

    This is a very loose pythonification of Paul Graham's continuation-passing
    macros, which implement continuations by chaining closures and passing the
    continuation semi-implicitly. For details, see chapter 20 in On Lisp:

        http://paulgraham.com/onlisp.html

    Continuations are most readily implemented when the program is written in
    continuation-passing style (CPS), but that is unreadable for humans.
    The purpose of this macro is to partly automate the CPS transformation, so
    that at the use site, we can write CPS code in a much more readable fashion.

    A ``with continuations`` block implies TCO; the same rules apply as in a
    ``with tco`` block. Furthermore, ``with continuations`` introduces the
    following additional rules:

      - Functions which make use of continuations, or call other functions that do,
        must be defined within a ``with continuations`` block, using the usual
        ``def`` or ``lambda`` forms.

      - All function definitions in a ``with continuations`` block, including
        any nested definitions, have an implicit formal parameter ``cc``,
        **even if not explicitly declared** in the formal parameter list.

        If declared explicitly, ``cc`` must be in a position that can accept a
        default value.

        This means ``cc`` must be declared either as by-name-only::

            with continuations:
                def myfunc(a, b, *, cc):
                    ...

                    f = lambda *, cc: ...

        or as the last parameter that has no default::

            with continuations:
                def myfunc(a, b, cc):
                    ...

                    f = lambda cc: ...

        Then the continuation machinery will automaticlly set the default value
        of ``cc`` to the default continuation (``identity``), which just returns
        its arguments.

        The most common use case for explicitly declaring ``cc`` is that the
        function is the target of a ``call_cc[]``; then it helps readability
        to make the ``cc`` parameter explicit.

      - A ``with continuations`` block will automatically transform all
        function definitions and ``return`` statements lexically contained
        within the block to use the continuation machinery.

        - ``return somevalue`` actually means a tail-call to ``cc`` with the
          given ``somevalue``.

          Multiple values can be returned as a ``tuple``. Tupleness is tested
          at run-time.

          Any tuple return value is automatically unpacked to the positional
          args of ``cc``. To return multiple things as one without the implicit
          unpacking, use a ``list``.

        - An explicit ``return somefunc(arg0, ..., k0=v0, ...)`` actually means
          a tail-call to ``somefunc``, with its ``cc`` automatically set to our
          ``cc``. Hence this inserts a call to ``somefunc`` before proceeding
          with our current continuation. (This is most often what we want when
          making a tail-call from a continuation-enabled function.)

          Here ``somefunc`` **must** be a continuation-enabled function;
          otherwise the TCO chain will break and the result is immediately
          returned to the top-level caller.

          (If the call succeeds at all; the ``cc`` argument is implicitly
          filled in and passed by name. Regular functions usually do not
          accept a named parameter ``cc``, let alone know what to do with it.)

        - Just like in ``with tco``, a lambda body is analyzed as one big
          return-value expression. This uses the exact same analyzer; for example,
          ``do[]`` (including any implicit ``do[]``) and the ``let[]`` expression
          family are supported.

      - Calls from functions defined in one ``with continuations`` block to those
        defined in another are ok; there is no state or context associated with
        the block.

      - Much of the language works as usual.

        Any non-tail calls can be made normally. Regular functions can be called
        normally in any non-tail position.

        Continuation-enabled functions behave as regular functions when
        called normally; only tail calls implicitly set ``cc``. A normal call
        uses ``identity`` as the default ``cc``.

      - For technical reasons, the ``return`` statement is not allowed at the
        top level of the ``with continuations:`` block. (Because a continuation
        is essentially a function, ``return`` would behave differently based on
        whether it is placed lexically before or after a ``call_cc[]``.)

        If you absolutely need to terminate the function surrounding the
        ``with continuations:`` block from inside the block, use an exception
        to escape; see ``call_ec``, ``catch``, ``throw``.

    **Capturing the continuation**:

    Inside a ``with continuations:`` block, the ``call_cc[]`` statement
    captures a continuation. (It is actually a macro, for technical reasons.)

    For various possible program topologies that continuations may introduce, see
    the clarifying pictures under ``doc/`` in the source distribution.

    Syntax::

        x = call_cc[func(...)]
        *xs = call_cc[func(...)]
        x0, ... = call_cc[func(...)]
        x0, ..., *xs = call_cc[func(...)]
        call_cc[func(...)]

    Conditional variant::

        x = call_cc[f(...) if p else g(...)]
        *xs = call_cc[f(...) if p else g(...)]
        x0, ... = call_cc[f(...) if p else g(...)]
        x0, ..., *xs = call_cc[f(...) if p else g(...)]
        call_cc[f(...) if p else g(...)]

    Assignment targets:

     - To destructure a multiple-values (from a tuple return value),
       use a tuple assignment target (comma-separated names, as usual).

     - The last assignment target may be starred. It is transformed into
       the vararg (a.k.a. ``*args``) of the continuation function.
       (It will capture a whole tuple, or any excess items, as usual.)

     - To ignore the return value (useful if ``func`` was called only to
       perform its side-effects), just omit the assignment part.

    Conditional variant:

     - ``p`` is any expression. If truthy, ``f(...)`` is called, and if falsey,
       ``g(...)`` is called.

     - Each of ``f(...)``, ``g(...)`` may be ``None``. A ``None`` skips the
       function call, proceeding directly to the continuation. Upon skipping,
       all assignment targets (if any are present) are set to ``None``.
       The starred assignment target (if present) gets the empty tuple.

     - The main use case of the conditional variant is for things like::

           with continuations:
               k = None
               def setk(cc):
                   global k
                   k = cc
               def dostuff(x):
                   call_cc[setk() if x > 10 else None]  # capture only if x > 10
                   ...

    To keep things relatively straightforward, a ``call_cc[]`` is only
    allowed to appear **at the top level** of:

      - the ``with continuations:`` block itself
      - a ``def`` or ``async def``

    Nested defs are ok; here *top level* only means the top level of the
    *currently innermost* ``def``.

    If you need to place ``call_cc[]`` inside a loop, use ``@looped`` et al.
    from ``unpythonic.fploop``; this has the loop body represented as the
    top level of a ``def``.

    Multiple ``call_cc[]`` statements in the same function body are allowed.
    These essentially create nested closures.

    **Main differences to Scheme and Racket**:

    Compared to Scheme/Racket, where ``call/cc`` will capture also expressions
    occurring further up in the call stack, our ``call_cc`` may be need to be
    placed differently (further out, depending on what needs to be captured)
    due to the delimited nature of the continuations implemented here.

    Scheme and Racket implicitly capture the continuation at every position,
    whereas we do it explicitly, only at the use sites of the ``call_cc`` macro.

    Also, since there are limitations to where a ``call_cc[]`` may appear, some
    code may need to be structured differently to do some particular thing, if
    porting code examples originally written in Scheme or Racket.

    Unlike ``call/cc`` in Scheme/Racket, ``call_cc`` takes **a function call**
    as its argument, not just a function reference. Also, there's no need for
    it to be a one-argument function; any other args can be passed in the call.
    The ``cc`` argument is filled implicitly and passed by name; any others are
    passed exactly as written in the client code.

    **Technical notes**:

    The ``call_cc[]`` statement essentially splits its use site into *before*
    and *after* parts, where the *after* part (the continuation) can be run
    a second and further times, by later calling the callable that represents
    the continuation. This makes a computation resumable from a desired point.

    The return value of the continuation is whatever the original function
    returns, for any ``return`` statement that appears lexically after the
    ``call_cc[]``.

    The effect of ``call_cc[]`` is that the function call ``func(...)`` in
    the brackets is performed, with its ``cc`` argument set to the lexically
    remaining statements of the current ``def`` (at the top level, the rest
    of the ``with continuations`` block), represented as a callable.

    The continuation itself ends there (it is *delimited* in this particular
    sense), but it will chain to the ``cc`` of the function it appears in.
    This is termed the *parent continuation* (**pcc**), stored in the internal
    variable ``_pcc`` (which defaults to ``None``).

    Via the use of the pcc, here ``f`` will maintain the illusion of being
    just one function, even though a ``call_cc`` appears there::

        def f(*, cc):
            ...
            call_cc[g(1, 2, 3)]
            ...

    The continuation is a closure. For its pcc, it will use the value the
    original function's ``cc`` had when the definition of the continuation
    was executed (for that particular instance of the closure). Hence, calling
    the original function again with its ``cc`` set to something else will
    produce a new continuation instance that chains into that new ``cc``.

    The continuation's own ``cc`` will be ``identity``, to allow its use just
    like any other function (also as argument of a ``call_cc`` or target of a
    tail call).

    When the pcc is set (not ``None``), the effect is to run the pcc first,
    and ``cc`` only after that. This preserves the whole captured tail of a
    computation also in the presence of nested ``call_cc`` invocations (in the
    above example, this would occur if also ``g`` used ``call_cc``).

    Continuations are not accessible by name (their definitions are named by
    gensym). To get a reference to a continuation instance, stash the value
    of the ``cc`` argument somewhere while inside the ``call_cc``.

    The function ``func`` called by a ``call_cc[func(...)]`` is (almost) the
    only place where the ``cc`` argument is actually set. There it is the
    captured continuation. Roughly everywhere else, ``cc`` is just ``identity``.

    Tail calls are an exception to this rule; a tail call passes along the current
    value of ``cc``, unless overridden manually (by setting the ``cc=...`` kwarg
    in the tail call).

    When the pcc is set (not ``None``) at the site of the tail call, the
    machinery will create a composed continuation that runs the pcc first,
    and ``cc`` (whether current or manually overridden) after that. This
    composed continuation is then passed to the tail call as its ``cc``.

    **Tips**:

      - Once you have a captured continuation, one way to use it is to set
        ``cc=...`` manually in a tail call, as was mentioned. Example::

            def main():
                call_cc[myfunc()]  # call myfunc, capturing the current cont...
                ...                # ...which is the rest of "main"

            def myfunc(cc):
                ourcc = cc  # save the captured continuation (sent by call_cc[])
                def somefunc():
                    return dostuff(..., cc=ourcc)  # and use it here
                somestack.append(somefunc)

        In this example, when ``somefunc`` is eventually called, it will tail-call
        ``dostuff`` and then proceed with the continuation ``myfunc`` had
        at the time when that instance of the ``somefunc`` closure was created.
        (This pattern is essentially how to build the ``amb`` operator.)

      - Instead of setting ``cc``, you can also overwrite ``cc`` with a captured
        continuation inside a function body. That overrides the continuation
        for the rest of the dynamic extent of the function, not only for a
        particular tail call::

            def myfunc(cc):
                ourcc = cc
                def somefunc():
                    cc = ourcc
                    return dostuff(...)
                somestack.append(somefunc)

      - A captured continuation can also be called manually; it's just a callable.

        The assignment targets, at the ``call_cc[]`` use site that spawned this
        particular continuation, specify its call signature. All args are
        positional, except the implicit ``cc``, which is by-name-only.

      - Just like in Scheme/Racket's ``call/cc``, the values that get bound
        to the ``call_cc[]`` assignment targets on second and further calls
        (when the continuation runs) are the arguments given to the continuation
        when it is called (whether implicitly or manually).

      - Setting ``cc`` to ``unpythonic.fun.identity``, while inside a ``call_cc``,
        will short-circuit the rest of the computation. In such a case, the
        continuation will not be invoked automatically. A useful pattern for
        suspend/resume.

      - However, it is currently not possible to prevent the rest of the tail
        of a captured continuation (the pcc) from running, apart from manually
        setting ``_pcc`` to ``None`` before executing a ``return``. Note that
        doing that is not strictly speaking supported (and may be subject to
        change in a future version).

      - When ``call_cc[]`` appears inside a function definition:

          - It tail-calls ``func``, with its ``cc`` set to the captured
            continuation.

          - The return value of the function containing one or more ``call_cc[]``
            statements is the return value of the continuation.

      - When ``call_cc[]`` appears at the top level of ``with continuations``:

          - A normal call to ``func`` is made, with its ``cc`` set to the captured
            continuation.

          - In this case, if the continuation is called later, it always
            returns ``None``, because the use site of ``call_cc[]`` is not
            inside a function definition.

      - If you need to insert just a tail call (no further statements) before
        proceeding with the current continuation, no need for ``call_cc[]``;
        use ``return func(...)`` instead.

        The purpose of ``call_cc[func(...)]`` is to capture the current
        continuation (the remaining statements), and hand it to ``func``
        as a first-class value.

      - To combo with ``multilambda``, use this ordering::

            with multilambda, continuations:
                ...

      - Some very limited comboability with ``call_ec``. May be better to plan
        ahead, using ``call_cc[]`` at the appropriate outer level, and then
        short-circuit (when needed) by setting ``cc`` to ``identity``.
        This avoids the need to have both ``call_cc`` and ``call_ec`` at the
        same time.

      - ``unpythonic.ec.call_ec`` can be used normally **lexically before any**
        ``call_cc[]``, but (in a given function) after at least one ``call_cc[]``
        has run, the ``ec`` ceases to be valid. This is because our ``call_cc[]``
        actually splits the function into *before* and *after* parts, and
        **tail-calls** the *after* part.

        (Wrapping the ``def`` in another ``def``, and placing the ``call_ec``
        on the outer ``def``, does not help either, because even the outer
        function has exited by the time *the continuation* is later called
        the second and further times.)

        Usage of ``call_ec`` while inside a ``with continuations`` block is::

            with continuations:
                @call_ec
                def result(ec):
                    print("hi")
                    ec(42)
                    print("not reached")
                assert result == 42

                result = call_ec(lambda ec: do[print("hi"),
                                               ec(42),
                                               print("not reached")])

        Note the signature of ``result``. Essentially, ``ec`` is a function
        that raises an exception (to escape to a dynamically outer context),
        whereas the implicit ``cc`` is the closure-based continuation handled
        by the continuation machinery.

        See the ``tco`` macro for details on the ``call_ec`` combo.
    """
    with dyn.let(gen_sym=gen_sym):
        return (yield from _continuations(block_body=tree))

# -----------------------------------------------------------------------------

@macros.block
def nb(tree, args, **kw):  # noqa: F811
    """[syntax, block] Ultralight math notebook.

    Auto-print top-level expressions, auto-assign last result as _.

    A custom print function can be supplied as the first positional argument.

    Example::

        with nb:
            2 + 3
            42 * _

        from sympy import *
        with nb(pprint):
            x, y = symbols("x, y")
            x * y
            3 * _
    """
    return _nb(body=tree, args=args)

# -----------------------------------------------------------------------------

@macros.expr
def dbg(tree, **kw):  # noqa: F811
    return _dbg_expr(tree)

@macros.block  # noqa: F811
def dbg(tree, args, **kw):  # noqa: F811
    """[syntax] Debug-print expressions including their source code.

    **Expression variant**:

    Example::

        dbg[25 + 17]  # --> [file.py:100] (25 + 17): 42

    The transformation is::

        dbg[expr] --> dbgprint_expr(k, v, filename=__file__, lineno=xxx)

    where ``k`` is the source code of the expression and ``v`` is its value.
    ``xxx`` is the original line number before macro expansion, if available
    in the AST node of the expression, otherwise ``None``. (Some macros might
    not care about inserting line numbers, because MacroPy fixes any missing
    line numbers at the end; this is why it might be missing at some locations
    in any specific macro-enabled program.)

    A default implementation is provided and automatically injected to the
    namespace of the module that imports anything from ``unpythonic.syntax``
    (see ``expose_unhygienic`` in MacroPy).

    To customize the debug printing, just assign another function to the name
    ``dbgprint_expr`` (locally or globally, as desired). The function (beside
    performing any printing/logging as a side effect) **must** return the value
    ``v``, so that surrounding an expression with ``dbg[...]`` does not alter
    its value.

    **CAUTION**: The default and a locally customized debug printer cannot be
    used in the same scope due to Python's scoping rules. If ``dbgprint_expr`` is
    assigned to as a local variable, then all references to this name in the local
    scope point to the local variable. The global is shadowed for the entire
    scope, regardless of whether the local has yet been initialized or not.
    (If you get an ``UnboundLocalError``, check this.)

    **Block variant**:

    Lexically within the block, any call to ``print`` (alternatively, if specified,
    the optional custom print function), prints both the expression source code
    and the corresponding value.

    A custom print function can be supplied as the first positional argument.
    To implement a custom print function, see the default implementation
    ``dbgprint_block`` for the signature.

    Examples::

        with dbg:
            x = 2
            print(x)   # --> [file.py:100] x: 2

        with dbg:
            x = 2
            y = 3
            print(x, y)   # --> [file.py:100] x: 2, y: 3
            print(x, y, sep="\n")   # --> [file.py:100] x: 2
                                    #     [file.py:100] y: 3

        prt = lambda *args, **kwargs: print(*args)
        with dbg(prt):
            x = 2
            prt(x)     # --> ('x',) (2,)
            print(x)   # --> 2

        with dbg(prt):
            x = 2
            y = 17
            prt(x, y, 1 + 2)  # --> ('x', 'y', '(1 + 2)'), (2, 17, 3))

    **CAUTION**: The source code is back-converted from the AST representation;
    hence its surface syntax may look slightly different to the original (e.g.
    extra parentheses). See ``macropy.core.unparse``.
    """
    return _dbg_block(body=tree, args=args)

# -----------------------------------------------------------------------------

@macros.block
def lazify(tree, *, gen_sym, **kw):  # noqa: F811
    """[syntax, block] Call-by-need for Python.

    In a ``with lazify`` block, function arguments are evaluated only when
    actually used, at most once each, and in the order in which they are
    actually used. Promises are automatically forced on access.

    Automatic lazification applies to arguments in function calls and to
    let-bindings, since they play a similar role. **No other binding forms
    are auto-lazified.**

    Automatic lazification uses the ``lazyrec[]`` macro, which recurses into
    certain types of container literals, so that the lazification will not
    interfere with unpacking. See its docstring for details.

    Comboing with other block macros in ``unpythonic.syntax`` is supported,
    including ``curry`` and ``continuations``.

    Silly contrived example::

        with lazify:
            def my_if(p, a, b):
                if p:
                    return a  # b never evaluated in this code path...
                else:
                    return b  # a never evaluated in this code path...

            # ...hence the divisions by zero here are never performed.
            assert my_if(True, 23, 1/0) == 23
            assert my_if(False, 1/0, 42) == 42

    Note ``my_if`` is a run-of-the-mill runtime function, not a macro. Only the
    ``with lazify`` is imbued with any magic.

    Like ``with continuations``, no state or context is associated with a
    ``with lazify`` block, so lazy functions defined in one block may call
    those defined in another. Calls between lazy and strict code are also
    supported (in both directions), without requiring any extra effort.

    Evaluation of each lazified argument is guaranteed to occur at most once;
    the value is cached. Order of evaluation of lazy arguments is determined
    by the (dynamic) order in which the lazy code actually uses them.

    Essentially, the above code expands into::

        from macropy.quick_lambda import macros, lazy
        from unpythonic.syntax import force

        def my_if(p, a, b):
            if force(p):
                return force(a)
            else:
                return force(b)
        assert my_if(lazy[True], lazy[23], lazy[1/0]) == 23
        assert my_if(lazy[False], lazy[1/0], lazy[42]) == 42

    plus some clerical details to allow lazy and strict code to be mixed.

    Just passing through a lazy argument to another lazy function will
    not trigger evaluation, even when it appears in a computation inlined
    to the argument list::

        with lazify:
            def g(a, b):
                return a
            def f(a, b):
                return g(2*a, 3*b)
            assert f(21, 1/0) == 42

    The division by zero is never performed, because the value of ``b`` is
    not needed to compute the result (worded less magically, that promise is
    never forced in the code path that produces the result). Essentially,
    the above code expands into::

        from macropy.quick_lambda import macros, lazy
        from unpythonic.syntax import force

        def g(a, b):
            return force(a)
        def f(a, b):
            return g(lazy[2*force(a)], lazy[3*force(b)])
        assert f(lazy[21], lazy[1/0]) == 42

    This relies on the magic of closures to capture f's ``a`` and ``b`` into
    the promises.

    But be careful; **assignments are not auto-lazified**, so the following does
    **not** work::

        with lazify:
            def g(a, b):
                return a
            def f(a, b):
                c = 3*b  # not in an arglist, b gets evaluated!
                return g(2*a, c)
            assert f(21, 1/0) == 42

    To avoid that, explicitly wrap the computation into a ``lazy[]``. For why
    assignment RHSs are not auto-lazified, see the section on pitfalls below.

    In calls, bare references (name, subscript, attribute) are detected and for
    them, re-thunking is skipped. For example::

        def g(a):
            return a
        def f(a):
            return g(a)
        assert f(42) == 42

    expands into::

        def g(a):
            return force(a)
        def f(a):
            return g(a)  # <-- no lazy[force(a)] since "a" is just a name
        assert f(lazy[42]) == 42

    When resolving references, subscripts and attributes are forced just enough
    to obtain the containing object from a promise, if any; for example, the
    elements of a list ``lst`` will not be evaluated just because the user code
    happens to use ``lst.append(...)``; this only forces the object ``lst``
    itself.

    A ``lst`` appearing by itself evaluates the whole list. Similarly, ``lst[0]``
    by itself evaluates only the first element, and ``lst[:-1]`` by itself
    evaluates all but the last element. The index expression in a subscript is
    fully forced, because its value is needed to determine which elements of the
    subscripted container are to be accessed.

    **Mixing lazy and strict code**

    Lazy code is allowed to call strict functions and vice versa, without
    requiring any additional effort.

    Keep in mind what this implies: when calling a strict function, any arguments
    given to it will be evaluated!

    In the other direction, when calling a lazy function from strict code, the
    arguments are evaluated by the caller before the lazy code gets control.
    The lazy code gets just the evaluated values.

    If you have, in strict code, an argument expression you want to pass lazily,
    use syntax like ``f(lazy[...], ...)``. If you accidentally do this in lazy
    code, it shouldn't break anything; ``with lazify`` detects any argument
    expressions that are already promises, and just passes them through.

    **Forcing promises manually**

    This is mainly useful if you ``lazy[]`` or ``lazyrec[]`` something explicitly,
    and want to compute its value outside a ``with lazify`` block.

    We provide the functions ``force1`` and ``force``.

    Using ``force1``, if ``x`` is a MacroPy ``lazy[]`` promise, it will be
    forced, and the resulting value is returned. If ``x`` is not a promise,
    ``x`` itself is returned, à la Racket.

    The function ``force``, in addition, descends into containers (recursively).
    When an atom ``x`` (i.e. anything that is not a container) is encountered,
    it is processed using ``force1``.

    Mutable containers are updated in-place; for immutables, a new instance is
    created. Any container with a compatible ``collections.abc`` is supported.
    (See ``unpythonic.collections.mogrify`` for details.) In addition, as
    special cases ``unpythonic.collections.box`` and ``unpythonic.llist.cons``
    are supported.

    **Tips, tricks and pitfalls**

    You can mix and match bare data values and promises, since ``force(x)``
    evaluates to ``x`` when ``x`` is not a promise.

    So this is just fine::

        with lazify:
            def f(x):
                x = 2*21  # assign a bare data value
                print(x)  # the implicit force(x) evaluates to x
            f(17)

    If you want to manually introduce a promise, use ``lazy[]`` from MacroPy::

        from macropy.quick_lambda import macros, lazy
        from unpythonic.syntax import macros, lazify

        with lazify:
            def f(x):
                x = lazy[2*21]  # assign a promise
                print(x)        # the implicit force(x) evaluates the promise
            f(17)

    If you have a container literal and want to lazify it recursively in a
    position that does not auto-lazify, use ``lazyrec[]`` (see its docstring
    for details)::

        from unpythonic.syntax import macros, lazify, lazyrec

        with lazify:
            def f(x):
                return x[:-1]
            lst = lazyrec[[1, 2, 3/0]]
            assert f(lst) == [1, 2]

    For non-literal containers, use ``lazy[]`` for each item as appropriate::

        def f(lst):
            lst.append(lazy["I'm lazy"])
            lst.append(lazy["Don't call me lazy, I'm just evaluated later!"])

    Keep in mind, though, that ``lazy[]`` will introduce a lambda, so there's
    the usual pitfall::

        from macropy.quick_lambda import macros, lazy
        from unpythonic.syntax import macros, lazify

        with lazify:
            lst = []
            for x in range(3):       # DANGER: only one "x", mutated imperatively
                lst.append(lazy[x])  # all these closures capture the same "x"
            print(lst[0])  # 2
            print(lst[1])  # 2
            print(lst[2])  # 2

    So to capture the value instead of the name, use the usual workaround,
    the wrapper lambda (here written more readably as a let, which it really is)::

        from macropy.quick_lambda import macros, lazy
        from unpythonic.syntax import macros, lazify, let

        with lazify:
            lst = []
            for x in range(3):
                lst.append(let[(y, x) in lazy[y]])
            print(lst[0])  # 0
            print(lst[1])  # 1
            print(lst[2])  # 2

    Be careful not to ``lazy[]`` or ``lazyrec[]`` too much::

        with lazify:
            a = 10
            a = lazy[2*a]  # 20, right?
            print(a)       # crash!

    Why does this example crash? The expanded code is::

        with lazify:
            a = 10
            a = lazy[2*force(a)]
            print(force(a))

    The ``lazy[]`` sets up a promise, which will force ``a`` *at the time when
    the containing promise is forced*, but at that time the name ``a`` points
    to a promise, which will force...

    The fundamental issue is that ``a = 2*a`` is an imperative update; if you
    need to do that, just let Python evaluate the RHS normally (i.e. use the
    value the name ``a`` points to *at the time when the RHS runs*).

    Assigning a lazy value to a new name evaluates it, because any read access
    triggers evaluation::

        with lazify:
            def g(x):
                y = x       # the "x" on the RHS triggers the implicit force
                print(y)    # bare data value
            f(2*21)

    Inspired by Haskell, Racket's (delay) and (force), and lazy/racket.

    **Combos**

    Introducing the *HasThon* programming language (it has 100% more Thon than
    popular brands)::

        with curry, lazify:  # or continuations, curry, lazify if you want those
            def add2first(a, b, c):
                return a + b
            assert add2first(2)(3)(1/0) == 5

            def f(a, b):
                return a
            assert let[((c, 42),
                        (d, 1/0)) in f(c)(d)] == 42
            assert letrec[((c, 42),
                           (d, 1/0),
                           (e, 2*c)) in f(e)(d)] == 84

            assert letrec[((c, 42),
                           (d, 1/0),
                           (e, 2*c)) in [local[x << f(e)(d)],
                                         x/4]] == 21

    Works also with continuations. Rules:

      - Also continuations are transformed into lazy functions.

      - ``cc`` built by chain_conts is treated as lazy, **itself**; then it's
        up to the continuations chained by it to decide whether to force their
        arguments.

      - The default continuation ``identity`` is strict, so that return values
        from a continuation-enabled computation will be forced.

    Example::

        with continuations, lazify:
            k = None
            def setk(*args, cc):
                nonlocal k
                k = cc
                return args[0]
            def doit():
                lst = ['the call returned']
                *more, = call_cc[setk('A', 1/0)]
                return lst + [more[0]]
            assert doit() == ['the call returned', 'A']
            assert k('again') == ['the call returned', 'again']
            assert k('thrice', 1/0) == ['the call returned', 'thrice']

    For a version with comments, see ``unpythonic/syntax/test/test_lazify.py``.

    **CAUTION**: Call-by-need is a low-level language feature that is difficult
    to bolt on after the fact. Some things might not work.

    **CAUTION**: The functions in ``unpythonic.fun`` are lazify-aware (so that
    e.g. curry and compose work with lazy functions), as are ``call`` and
    ``callwith`` in ``unpythonic.misc``, but the rest of ``unpythonic`` is not.

    **CAUTION**: Argument passing by function call, and let-bindings are
    currently the only binding constructs to which auto-lazification is applied.
    """
    with dyn.let(gen_sym=gen_sym):
        return (yield from _lazify(body=tree))

@macros.expr
def lazyrec(tree, **kw):  # noqa: F811
    """[syntax, expr] Delay items in a container literal, recursively.

    Essentially, this distributes ``lazy[]`` into the items inside a literal
    ``list``, ``tuple``, ``set``, ``frozenset``, ``unpythonic.collections.box``
    or ``unpythonic.llist.cons``, and into the values of a literal ``dict`` or
    ``unpythonic.collections.frozendict``.

    Because this is a macro and must work by names only, only this fixed set of
    container types is supported.

    The container itself is not lazified, only the items inside it are, to keep
    the lazification from interfering with unpacking. This allows things such as
    ``f(*lazyrec[(1*2*3, 4*5*6)])`` to work as expected.

    See also ``macropy.quick_lambda.lazy`` (the effect on each item) and
    ``unpythonic.syntax.force`` (the inverse of ``lazyrec[]``).

    For an atom, ``lazyrec[]`` has the same effect as ``lazy[]``::

        lazyrec[dostuff()] --> lazy[dostuff()]

    For a container literal, ``lazyrec[]`` descends into it::

        lazyrec[(2*21, 1/0)] --> (lazy[2*21], lazy[1/0])
        lazyrec[{'a': 2*21, 'b': 1/0}] --> {'a': lazy[2*21], 'b': lazy[1/0]}

    Constructor call syntax for container literals is also supported::

        lazyrec[list(2*21, 1/0)] --> [lazy[2*21], lazy[1/0]]

    Nested container literals (with any combination of known types) are
    processed recursively, for example::

        lazyrec[((2*21, 1/0), (1+2+3, 4+5+6))] --> ((lazy[2*21], lazy[1/0]),
                                                    (lazy[1+2+3], lazy[4+5+6]))
    """
    return _lazyrec(tree)

# -----------------------------------------------------------------------------

@macros.block
def prefix(tree, **kw):  # noqa: F811
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

    **CAUTION**: This macro is experimental, not intended for production use.
    """
    return (yield from _prefix(block_body=tree))

# -----------------------------------------------------------------------------

@macros.block
def test(tree, args, *, gen_sym, **kw):  # noqa: F811
    with dyn.let(gen_sym=gen_sym):
        return (yield from _test_block(block_body=tree, args=args))

@macros.expr  # noqa: F811
def test(tree, *, gen_sym, **kw):  # noqa: F811
    """[syntax] Make a test assertion. For writing automated tests.

    **Testing overview**:

    Use the `test[]`, `test_raises[]`, `test_signals[]`, `fail[]`, `error[]`
    and `warn[]` macros inside a `with testset()`, as appropriate.

    See `testset` and `session` in the module `unpythonic.test.fixtures`,
    as well as the docstrings of any constructs exported from that module.

    See below for tips and tricks.

    Finally, see the unit tests of `unpythonic` itself for examples.

    **Expression variant**:

    Syntax::

        test[expr]
        test[expr, message]

    The test succeeds if `expr` evaluates to truthy. The `message`
    is used in forming the error message if the test fails or errors.

    If you want to assert just that an expression runs to completion
    normally, and don't care about the return value::

        from unpythonic.test.fixtures import returns_normally

        test[returns_normally(expr)]
        test[returns_normally(expr), message]

    This can be useful for testing functions with side effects; sometimes
    what is important is that the function completes normally.

    What `test[expr]` captures for reporting as "result" in the failure
    message, if the test fails:

      - If a `the[...]` mark is present, the subexpression marked as `the[...]`.
        At most one `the[]` may appear in a single `test[...]`.
      - Else if `expr` is a comparison, the LHS (leftmost term in case of
        a chained comparison). So e.g. `test[x < 3]` needs no annotation
        to do the right thing. This is a common use case, hence automatic.
      - Else the whole `expr`.

    The `the[...]` mark is useful in tests involving comparisons::

        test[lower_limit < the[computeitem(...)]]
        test[lower_limit < the[computeitem(...)] < upper_limit]
        test[myconstant in the[computeset(...)]]

    If your interesting part is on the LHS, `the[]` is optional, although
    allowed (to explicitly document intent). These have the same effect::

        test[the[computeitem(...)] in myitems]
        test[computeitem(...) in myitems]

    The `the[...]` mark passes the value through, and does not affect the
    evaluation order of user code.

    The `the[]` mark can be imported as a macro from this module, so that
    its appearance in your source code won't confuse `flake8`.

    **Block variant**:

    A test that requires statements (e.g. assignments) can be written as a
    `with test` block::

        with test:
            body0
            ...
            return expr  # optional

        with test(message):
            body0
            ...
            return expr  # optional

    The test block is automatically lifted into a function, so it introduces
    **a local scope**. Use the `nonlocal` or `global` declarations if you need
    to mutate something defined on the outside.

    If there is a `return` at the top level of the block, that is the return
    value from the test; it is what will be asserted.

    If there is no `return`, the test asserts that the block completes normally,
    just like a `test[returns_normally(...)]` does for an expression.

    (The asymmetry in syntax reflects the asymmetry between expressions and
    statements in Python. Likewise, the fact that `with test` requires `return`
    to return a value, but `test[...]` doesn't, is similar to the difference
    between `def` and `lambda`.)

    In the block variant, the "result" capture rules apply to the return value
    designated by `return`. To override, the `the[]` mark can be used for
    capturing the value of any one expression inside the block. (It doesn't
    have to be in the `return`.)

    At most one `the[]` may appear in the same `with test` block.

    **Failure and error signaling**:

    Upon a test failure, `test[]` will *signal* a `TestFailure` using the
    *cerror* (correctable error) protocol, via unpythonic's condition
    system, which is a pythonification of Common Lisp's condition system.
    See `unpythonic.conditions`.

    If a test fails to run to completion due to an uncaught exception or an
    unhandled signal (e.g. an `error` or `cerror` condition), `TestError`
    is signaled instead, so the caller can easily tell apart which case
    occurred.

    Finally, when a `warn[]` runs, `TestWarning` is signaled.

    These condition types are defined in `unpythonic.test.fixtures`.
    They inherit from `TestingException`, defined in the same module.
    Beside the human-readable message, these exception types contain
    attributes with programmatically inspectable information about
    what happened. See the docstring of `TestingException`.

    *Signaling* a condition, instead of *raising* an exception, allows the
    surrounding code (inside the test framework) to install a handler that
    invokes the `proceed` restart (if there is such in scope), so upon a test
    failure or error, the test suite resumes.

    **Disabling the signal barrier**:

    As implied above, `test[]` (likewise `with test:`) forms a barrier that
    alerts the user about uncaught signals, and stops those signals from
    propagating further. If your `with handlers` block that needs to see
    the signal is outside the `test` invocation, or if allowing a signal to
    go uncaught is part of normal operation (e.g. `warn` signals are often
    not caught, because the only reason to do so is to muffle the warning),
    use a `with catch_signals(False):` block (from the module
    `unpythonic.test.fixtures`) to disable the signal barrier::

        from unpythonic.test.fixtures import catch_signals

        with catch_signals(False):
            test[...]

    Another way to avoid catching signals that should not be caught by the
    test framework is to rearrange the `test[]` so that the expression being
    asserted cannot result in an uncaught signal. For example, save the result
    of a computation into a variable first, and then use it in the `test[]`,
    instead of invoking that computation inside the `test[]`. See
    `unpythonic.test.test_conditions` for examples.

    Exceptions are always caught by `test[]`, because exceptions do not support
    resumption; unlike with signals, the inner level of the call stack is already
    destroyed by the time the exception is caught by the test construct.
    """
    with dyn.let(gen_sym=gen_sym):
        return (yield from _test_expr(tree))

@macros.block
def test_signals(tree, args, *, gen_sym, **kw):  # noqa: F811
    with dyn.let(gen_sym=gen_sym):
        return (yield from _test_block_signals(block_body=tree, args=args))

@macros.expr  # noqa: F811
def test_signals(tree, **kw):  # noqa: F811
    """[syntax, expr] Like `test`, but expect the expression to signal a condition.

    "Signal" as in `unpythonic.conditions.signal` and its sisters.

    Syntax::

        test_signals[exctype, expr]
        test_signals[exctype, expr, message]

        with test_signals(exctype):
            body0
            ...

        with test_signals(exctype, message):
            body0
            ...

    Example::

        test_signals[ValueError, myfunc()]
        test_signals[ValueError, myfunc(), "failure message"]

    The test succeeds, if `expr` signals a condition of type `exctype`, and the
    signal propagates into the (implicit) handler inside the `test_signals[]`
    construct.

    If `expr` returns normally, the test fails.

    If `expr` signals some other type of condition, or raises an exception, the
    test errors.

    **Differences to `test[]`, `with test`**:

    As the focus of this construct is on signaling vs. returning normally, the
    `the[]` mark is not supported. The block variant does not support `return`.
    """
    return (yield from _test_expr_signals(tree))

@macros.block
def test_raises(tree, args, *, gen_sym, **kw):  # noqa: F811
    with dyn.let(gen_sym=gen_sym):
        return (yield from _test_block_raises(block_body=tree, args=args))

@macros.expr  # noqa: F811
def test_raises(tree, **kw):  # noqa: F811
    """[syntax, expr] Like `test`, but expect the expression raise an exception.

    Syntax::

        test_raises[exctype, expr]
        test_raises[exctype, expr, message]

        with test_raises(exctype):
            body0
            ...

        with test_raises(exctype, message):
            body0
            ...

    Example::

        test_raises[TypeError, issubclass(1, int)]
        test_raises[ValueError, myfunc()]
        test_raises[ValueError, myfunc(), "failure message"]

    The test succeeds, if `expr` raises an exception of type `exctype`, and the
    exception propagates into the (implicit) handler inside the `test_raises[]`
    construct.

    If `expr` returns normally, the test fails.

    If `expr` signals a condition, or raises some other type of exception, the
    test errors.

    **Differences to `test[]`, `with test`**:

    As the focus of this construct is on raising vs. returning normally, the
    `the[]` mark is not supported. The block variant does not support `return`.
    """
    return (yield from _test_expr_raises(tree))

@macros.expr
def fail(tree, *, gen_sym, **kw):  # noqa: F811
    """[syntax, expr] Produce a test failure, unconditionally.

    Useful to e.g. mark a line of code that should not be reached in automated
    tests, reaching which is therefore a test failure.

    Usage::

        fail["human-readable reason"]

    which has the same effect as::

        test[False, "human-readable reason"]

    except in the case of `fail[]`, the error message generating machinery is
    special-cased to omit the source code expression, because it explictly
    states that the intent of the "test" is not actually to perform a test.

    See also `error[]`, `warn[]`.
    """
    with dyn.let(gen_sym=gen_sym):
        return (yield from _fail_expr(tree))

@macros.expr
def error(tree, *, gen_sym, **kw):  # noqa: F811
    """[syntax, expr] Produce a test error, unconditionally.

    Useful to e.g. indicate to the user that an optional dependency that could
    be used to run some integration test is not installed.

    Usage::

        error["human-readable reason"]

    See also `warn[]`, `fail[]`.
    """
    with dyn.let(gen_sym=gen_sym):
        return (yield from _error_expr(tree))

@macros.expr
def warn(tree, *, gen_sym, **kw):  # noqa: F811
    """[syntax, expr] Produce a test warning, unconditionally.

    Useful to e.g. indicate that the Python interpreter or version the
    tests are running on does not support a particular test, or to alert
    about a non-essential TODO.

    A warning does not increase the failure count, so it will not cause
    your CI workflow to break.

    Usage::

        warn["human-readable reason"]

    See also `error[]`, `fail[]`.
    """
    with dyn.let(gen_sym=gen_sym):
        return (yield from _warn_expr(tree))

# -----------------------------------------------------------------------------
