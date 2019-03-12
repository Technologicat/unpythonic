# -*- coding: utf-8 -*-
"""Lispython: the love child of Python and Scheme.

Powered by Pydialect and unpythonic.

**Features**

In terms of ``unpythonic.syntax``, we implicitly enable ``tco``, ``autoreturn``,
``multilambda``, ``namedlambda``, and ``quicklambda`` for the whole module, and
import some macros and functions to serve as dialect builtins.

    - TCO in both ``def`` and ``lambda``, fully automatic

    - Omit ``return`` in any tail position, like in Lisps

    - Multiple-expression lambdas, ``lambda x: [expr0, ...]``

    - Named lambdas (whenever the machinery can figure out a name)

    - The underscore: ``f[_*3] --> lambda x: x*3`` (name ``f`` is **reserved**)

Builtins:

    - All ``let[]`` and ``do[]`` constructs from ``unpythonic.syntax``

    - Functions ``cons``, ``car``, ``cdr``, ``ll``, ``llist``, ``prod``

For detailed documentation of the language features, see the module
``unpythonic.syntax`` and the macros ``tco``, ``autoreturn``, ``multilambda``,
``namedlambda``, ``quicklambda``, ``let`` and ``do`` therein.

The multi-expression lambda syntax uses ``do[]``, so it also allows lambdas
to manage local variables using ``local[name << value]`` and ``delete[name]``.
See the documentation of ``do[]`` for details.

The builtin ``let[]`` constructs are ``let``, ``letseq``, ``letrec``, the
decorator versions ``dlet``, ``dletseq``, ``dletrec``, the block
versions (decorator, call immediately, replace def'd name with result)
``blet``, ``bletseq``, ``bletrec``, and the code-splicing variants
``let_syntax`` and ``abbrev``. Bindings may be made using any syntax variant
supported by ``unpythonic.syntax``.

The builtin ``do[]`` constructs are ``do`` and ``do0``.

For more, import from  ``unpythonic``, the standard library of Lispython
(on top of what Python itself already provides).

``quicklambda`` is powered by ``macropy.quick_lambda``.

**What Lispython is**

Lispython is a dialect of Python implemented in MacroPy. The dialect aims at
production quality.

This module is the dialect definition, invoked by ``dialects.DialectFinder``
when it detects a lang-import that matches our module name.

The goal of the Lispython dialect is to fix some glaring issues that hamper
Python when viewed from a Lisp/Scheme perspective, as well as make the popular
almost-Lisp, Python, feel slightly more lispy.

We take the approach of a relatively thin layer of macros (and underlying
functions that implement the actual functionality), minimizing magic as far as
reasonably possible.

Performance is only a secondary concern; performance-critical parts fare better
at the other end of the wide spectrum, with Cython. Lispython is for the
remaining 80% of the code, where the bottleneck is human developer time.

    https://en.wikipedia.org/wiki/Wide-spectrum_language
    https://en.wikipedia.org/wiki/Pareto_principle
    http://cython.org/

**Comboability**

The aforementioned block macros are enabled implicitly for the whole module;
this is the essence of the Lispython dialect. Other block macros can still be
invoked manually in the user code.

Of the other block macros in ``unpythonic.syntax``, code written in Lispython
supports only ``continuations``. ``autoref`` should also be harmless enough
(will expand too early, but shouldn't matter).

``prefix``, ``curry``, ``lazify`` and ``envify`` are **not compatible** with
the ordering of block macros implicit in the Lispython dialect.

``prefix`` is a first-pass (outside-in) macro that should expand first, so
it should be placed in a lexically outer position with respect to the ones
Lispython invokes implicitly; but nothing can be more outer than the
dialect template.

The other three are second-pass (inside-out) macros that should expand later,
so similarly, also they should be placed in a lexically outer position.

Basically, any block macro that can be invoked *lexically inside* a ``with tco``
block will work, the rest will not.

If you need e.g. a lazy Lispython, the way to do that is to make a copy of the
dialect module, change the dialect template to import the ``lazify`` macro, and
then include a ``with lazify`` in the appropriate position, outside the
``with namedlambda`` block. Other customizations can be made similarly.

**Lispython and continuations (call/cc)**

Just use ``with continuations`` from ``unpythonic.syntax`` where needed.
See its documentation for usage.

Lispython works with ``with continuations``, because:

  - Nesting ``with continuations`` within a ``with tco`` block is allowed,
    for the specific reason of supporting continuations in Lispython.

    The dialect's implicit ``with tco`` will just skip the ``with continuations``
    block (``continuations`` implies TCO).

  - ``autoreturn``, ``quicklambda`` and ``multilambda`` are first-pass macros,
    so although they will be in a lexically outer position with respect to the
    manually invoked ``with continuations`` in the user code, this is correct
    because first-pass macros expand outside-in (so they run before
    ``continuations``, as they should).

  - The same applies to the first pass of ``namedlambda``. Its second pass,
    on the other hand, must come after ``continuations``, which it does, since
    the dialect's implicit ``with namedlambda`` is in a lexically outer position
    with respect to the ``with continuations``.

Be aware, though, that the combination of the ``autoreturn`` implicit in the
dialect and ``with continuations`` might have suboptimal usability, because
``continuations`` handles tail calls specially (the target of a tail-call in a
``continuations`` block must be continuation-enabled; see the documentation of
``continuations``), and ``autoreturn`` makes it visually slightly less clear
which positions are in fact tail calls (since no explicit ``return``).

**Why extend Python?**

Racket is an excellent Lisp, especially with sweet, sweet expressions, not to
mention extremely pythonic. The word is *rackety*; the syntax of the language
comes with an air of Zen minimalism (as perhaps expected of a descendant of
Scheme), but the focus on *batteries included* and understandability are
remarkably similar to the pythonic ideal. Racket even has an IDE (DrRacket)
and an equivalent of PyPI, and the documentation is simply stellar.

    https://docs.racket-lang.org/sweet/
    https://sourceforge.net/projects/readable/
    https://srfi.schemers.org/srfi-110/srfi-110.html
    https://srfi.schemers.org/srfi-105/srfi-105.html
    https://racket-lang.org/

Python, on the other hand, has a slight edge in usability to the end-user
programmer, and importantly, a huge ecosystem of libraries, second to ``None``.
Python is where science happens (unless you're in CS). Python is an almost-Lisp
that has delivered on the productivity promise of Lisp.

    http://paulgraham.com/icad.html

Python also gets many things right, such as well developed support for lazy
sequences, and decorators.

However, in certain other respects, Python the base language leaves something
to be desired, if you have been exposed to Racket (or Haskell, but that's a
different story). Writing macros is harder due to the irregular syntax, but
thankfully MacroPy already exists, and any set of macros only needs to be
created once.

Practicality beats purity: hence, fix the minor annoyances that would otherwise
quickly add up, and reap the benefits of both worlds. If Python is software
glue, Lispython is an additive that makes it flow better.

**Note**

For PG's accumulator puzzle even Lispython can do no better than this
let-over-lambda (here using the haskelly let-in syntax for bindings)::

    foo = lambda n0: let[(n, n0) in
                         (lambda i: n << n + i)]

Testing it::

    f = foo(10)
    assert f(1) == 11
    assert f(1) == 12

This still sets up a separate place for the accumulator. The modern pure Python
solution avoids that, but needs many lines::

    def foo(n):
        def accumulate(i):
            nonlocal n
            n += i
            return n
        return accumulate

The problem is that assignment to a lexical variable (including formals) is a
statement in Python. If we abbreviate ``accumulate`` as a lambda, it needs a
``let`` environment to write in (to use unpythonic's expression-assignment).

But see ``envify`` in ``unpythonic.syntax``, which allows this::

    from unpythonic.syntax import macros, envify

    with envify:
        def foo(n):
            return lambda i: n << n + i

or as a one-liner::

    with envify:
        foo = lambda n: lambda i: n << n + i

``envify`` may be made part of the Lispython dialect definition later, but
first it needs testing to decide whether this particular, perhaps rarely used,
feature is worth a performance hit.

**CAUTION**

No instrumentation exists (or is even planned) for the Lispython layer; you'll
have to use regular Python tooling to profile, debug, and such. The layer
should be thin enough for this not to be a major problem in practice.
"""

from macropy.core.quotes import macros, q, name

# TODO: The dialect finder imports us, so do not from-import to avoid dependency loop.
import dialects  # TODO: a proper pydialect package

def ast_transformer(module_body):
    with q as template:
        from unpythonic.syntax import macros, tco, autoreturn, \
                                      multilambda, quicklambda, namedlambda, \
                                      let, letseq, letrec, do, do0, \
                                      dlet, dletseq, dletrec, \
                                      blet, bletseq, bletrec, \
                                      let_syntax, abbrev, \
                                      cond
        # auxiliary syntax elements for the macros
        from unpythonic.syntax import local, where, block, expr, f, _
        from unpythonic import cons, car, cdr, ll, llist, prod
        with namedlambda:  # MacroPy #21 (nontrivial two-pass macro; seems I didn't get the fix right)
            with autoreturn, quicklambda, multilambda, tco:
                name["__paste_here__"]
    return dialects.splice_ast(module_body, template, "__paste_here__")

def rejoice():
    s = \
"""**Schemers rejoice!**::

    Multiple musings mix in a lambda,
    Lament no longer the lack of let.
    Languish no longer labelless, lambda,
    Linked lists cons and fold.
    Tail-call into recursion divine,
    The final value always provide."""
    print(s)
    return s
