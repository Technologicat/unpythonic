# -*- coding: utf-8 -*-
"""unpythonic.syntax: Toto, I've a feeling we're not in Python anymore.

Requires MacroPy (package ``macropy3`` on PyPI).
"""

# This module contains the macro interface and docstrings; the submodules
# contain the actual syntax transformers (regular functions that process ASTs)
# that implement the macros.

# insist, deny, it, f, _, local, block, expr, call_cc are just for passing through
# to the client code that imports us.
from .curry import curry as _curry
from .forall import forall as _forall, insist, deny
from .fupstx import fup as _fup
from .ifexprs import aif as _aif, it, cond as _cond
from .lambdatools import multilambda as _multilambda, \
                         namedlambda as _namedlambda, \
                         quicklambda as _quicklambda, f, _
from .lazify import lazify as _lazify
from .letdo import do as _do, do0 as _do0, local, \
                   let as _let, letseq as _letseq, letrec as _letrec, \
                   dlet as _dlet, dletseq as _dletseq, dletrec as _dletrec, \
                   blet as _blet, bletseq as _bletseq, bletrec as _bletrec
from .letsyntax import let_syntax_expr, let_syntax_block, block, expr
from .nb import nb as _nb
from .prefix import prefix as _prefix
from .tailtools import autoreturn as _autoreturn, tco as _tco, \
                       continuations as _continuations, call_cc

# "where" is only for passing through.
from .letdoutil import UnexpandedLetView, _canonize_bindings, where
from ..dynassign import dyn, make_dynvar

from macropy.core.macros import Macros

macros = Macros()

# We pass gen_sym as a dynvar so it doesn't need to appear in the
# formal parameter lists of the underlying syntax transformers.
#
# If you add new macros, use ``with dyn.let(gen_sym=gen_sym):`` if your
# syntax transformer (or any syntax transformers it calls) needs gen_sym.
# This default is here to yell if it's needed and missing; the traceback
# will tell exactly which syntax transformer needed it.
#
def nogensym(*args, **kwargs):
    raise RuntimeError("No gen_sym function set")
make_dynvar(gen_sym=nogensym)

# -----------------------------------------------------------------------------

@macros.expr
def aif(tree, *, gen_sym, **kw):
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
def cond(tree, *, gen_sym, **kw):
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
    return _curry(block_body=tree)

# -----------------------------------------------------------------------------

@macros.expr
def let(tree, args, *, gen_sym, **kw):
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
def letseq(tree, args, *, gen_sym, **kw):
    """[syntax, expr] Let with sequential binding (like Scheme/Racket let*).

    Like ``let``, but bindings take effect sequentially. Later bindings
    shadow earlier ones if the same name is used multiple times.

    Expands to nested ``let`` expressions.
    """
    with dyn.let(gen_sym=gen_sym):
        return _destructure_and_apply_let(tree, args, _letseq)

@macros.expr
def letrec(tree, args, *, gen_sym, **kw):
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

def _destructure_and_apply_let(tree, args, expander, allow_call_in_name_position=False):
    if args:
        bs = _canonize_bindings(args, locref=tree, allow_call_in_name_position=allow_call_in_name_position)
        return expander(bindings=bs, body=tree)
    # haskelly syntax
    view = UnexpandedLetView(tree)  # note this gets only the part inside the brackets
    return expander(bindings=view.bindings, body=view.body)

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
    the regular syntax ``name = value`` creates a local variable in the
    lexical scope of the ``def``.
    """
    with dyn.let(gen_sym=gen_sym):
        return _destructure_and_apply_let(tree, args, _dlet)

@macros.decorator
def dletseq(tree, args, *, gen_sym, **kw):
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
    with dyn.let(gen_sym=gen_sym):
        return _destructure_and_apply_let(tree, args, _dletrec)

@macros.decorator
def blet(tree, args, *, gen_sym, **kw):
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
def bletseq(tree, args, *, gen_sym, **kw):
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
def bletrec(tree, args, *, gen_sym, **kw):
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
def do(tree, *, gen_sym, **kw):
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
def do0(tree, *, gen_sym, **kw):
    """[syntax, expr] Like do, but return the value of the first expression."""
    with dyn.let(gen_sym=gen_sym):
        return _do0(tree)

# -----------------------------------------------------------------------------

@macros.expr
def let_syntax(tree, args, *, gen_sym, **kw):
    with dyn.let(gen_sym=gen_sym):  # gen_sym is only needed by the implicit do.
        return _destructure_and_apply_let(tree, args, let_syntax_expr, allow_call_in_name_position=True)

# Python has no function overloading, but expr and block macros go into
# different parts of MacroPy's macro registry.
#
# Normal run-time code sees only the dynamically latest definition,
# so the docstring goes here.
@macros.block
def let_syntax(tree, **kw):
    """Introduce local **syntactic** bindings.

    Usage - expression variant::

        let_syntax((lhs, rhs), ...)[body]
        let_syntax((lhs, rhs), ...)[[body0, ...]]

    Alternative haskelly syntax::

        let_syntax[((lhs, rhs), ...) in body]
        let_syntax[((lhs, rhs), ...) in [body0, ...]]

        let_syntax[body, where((lhs, rhs), ...)]
        let_syntax[[body0, ...], where((lhs, rhs), ...)]

    Usage - block variant::

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
    return let_syntax_block(block_body=tree)

@macros.expr
def abbrev(tree, args, *, gen_sym, **kw):
    with dyn.let(gen_sym=gen_sym):  # gen_sym is only needed by the implicit do.
        yield _destructure_and_apply_let(tree, args, let_syntax_expr, allow_call_in_name_position=True)

@macros.block
def abbrev(tree, **kw):
    """Exactly like ``let_syntax``, but expands in the first pass, outside in.

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
    yield let_syntax_block(block_body=tree)

# -----------------------------------------------------------------------------

@macros.expr
def forall(tree, **kw):
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
def multilambda(tree, *, gen_sym, **kw):
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
def namedlambda(tree, **kw):
    """[syntax, block] Implicitly named lambdas.

    Lexically inside a ``with namedlambda`` block, any literal ``lambda``
    that is assigned to a name using a simple assignment of the form
    ``f = lambda ...: ...``, is named as "f", where the name ``f``
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
    return _namedlambda(block_body=tree)

@macros.block
def quicklambda(tree, **kw):
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
    return (yield from _quicklambda(block_body=tree))

# -----------------------------------------------------------------------------

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
    return _fup(tree)

# -----------------------------------------------------------------------------

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
    return (yield from _autoreturn(block_body=tree))

@macros.block
def tco(tree, *, gen_sym, **kw):
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
    ``ec``, ``brk``, is interpreted as invoking an escape continuation.
    """
    with dyn.let(gen_sym=gen_sym):
        return (yield from _tco(block_body=tree))

@macros.block
def continuations(tree, *, gen_sym, **kw):
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
        to escape; see ``call_ec``, ``setescape``, ``escape``.

    **Capturing the continuation**:

    Inside a ``with continuations:`` block, the ``call_cc[]`` statement
    captures a continuation. (It is actually a macro, for technical reasons.)

    For various possible program topologies that continuations may introduce, see
    the clarifying pictures under ``macro_extras/`` in the source distribution.

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
def nb(tree, **kw):
    """[syntax, block] Ultralight math notebook.

    Auto-print top-level expressions, auto-assign last result as _.

    Example::

        with nb:
            2 + 3
            42 * _

        from sympy import *
        with nb:
            x, y = symbols("x, y")
            x * y
            3 * _
    """
    return _nb(body=tree)

# -----------------------------------------------------------------------------

@macros.block
def lazify(tree, *, gen_sym, **kw):
    """[syntax, block] Automatic lazy evaluation of function arguments.

    In a ``with lazify`` block, function arguments are evaluated only when
    actually used::

        with lazify:
            def my_if(p, a, b):
                if p:
                    return a  # b never evaluated in this code path...
                else:
                    return b  # a never evaluated in this code path...

            # ...hence the divisions by zero here are never performed.
            assert my_if(True, 23, 1/0) == 23
            assert my_if(False, 1/0, 42) == 42

    Essentially, each argument is made into a promise, which is then forced
    when the function needs its value. If, in a particular code path, some
    argument is never used, then it is not evaluated, either. Evaluation of
    each argument is guaranteed to occur at most once.

    When a lazy function takes ``*args``, the whole tuple is treated as an
    atomic lazy construct; accessing any part of it causes all of its elements
    to be evaluated. The same applies to ``**kwargs``. (This is for simplicity.)

    **CAUTION**: Currently, passing ``*args`` and/or ``**kwargs`` in a call
    in a ``with lazify`` block is only supported on Python 3.4. Support for
    Python 3.5 and later is subject to a future expansion of this feature.

    At the receiving end, ``*args`` and ``**kwargs`` already work also in
    Python 3.5+.

    Some care is taken to support:

        - calls *into* lazy functions *from outside* the ``with lazify`` block,
          by automatically wrapping the already-evaluated argument values into
          promises (that just pass through the already computed value).

        - calls *from* lazy functions *to outside* the ``with lazify`` block
          (into regular functions), by evaluating the arguments in the usual
          manner whenever the target of a call is **not** a lazy function.

    Like ``with continuations``, no state or context is associated with a
    ``with lazify`` block, so lazy functions defined in one block may call
    those defined in another.

    The implementation is based on MacroPy's ``lazy[]`` expr macro.

    Inspired by Haskell.

    **CAUTION**: This is a very rough first draft; e.g. lazy ``curry`` is
    currently **not** supported, ``call`` and ``callwith`` might not be
    supported, and interaction with other macros is limited to ``let[]``
    and ``do[]``. (Intuition says this should be expanded **after**
    ``continuations``, if you want to try comboing them.)
    """
    with dyn.let(gen_sym=gen_sym):
        return (yield from _lazify(body=tree))

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
    return (yield from _prefix(block_body=tree))

# TODO: using some name other than "kw" would silence the IDE warnings.
from .prefix import q, u, kw  # for re-export only

# -----------------------------------------------------------------------------
