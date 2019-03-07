# -*- coding: utf-8 -*-
"""Lispython: the love child of Python and Scheme.

Powered by Pydialect and unpythonic.

This module is the dialect definition, invoked by ``dialects.DialectFinder``
when it detects a lang-import that matches the module name of this module.

This dialect is implemented in MacroPy.

**What Lispython is**

The goal of the Lispython dialect is to fix some glaring issues that hamper
Python when viewed from a Lisp/Scheme perspective. We take that approach of
a relatively thin layer of macros (and underlying functions that implement
the actual functionality), minimizing magic as far as reasonably possible.

Performance is only a secondary concern; performance-critical parts fare better
at the other end of the wide spectrum, with Cython. Lispython is for the
remaining 80% of the code, where the bottleneck is human developer time.

    https://en.wikipedia.org/wiki/Wide-spectrum_language
    https://en.wikipedia.org/wiki/Pareto_principle
    http://cython.org/

The dialect aims at production quality.

**Why extend Python?**

Racket is an excellent Lisp, especially with sweet, sweet expressions, not to
mention extremely pythonic. The word is *rackety*; the philosophy comes with
an air of Zen minimalism, but the focus on *batteries included* and
understandability are remarkably similar to the pythonic ideal. Racket even
has an IDE and an equivalent of PyPI, and the documentation is simply stellar.

    https://docs.racket-lang.org/sweet/
    https://sourceforge.net/projects/readable/
    https://srfi.schemers.org/srfi-110/srfi-110.html
    https://srfi.schemers.org/srfi-105/srfi-105.html
    https://racket-lang.org/

Python, on the other hand, has a slight edge in usability to the end-user
programmer, and importantly, a huge ecosystem of libraries, second to ``None``.
Python is where science happens (unless you're in CS).

Python is an almost-Lisp that has delivered on the productivity promise of Lisp.
However, in certain other respects, Python the base language leaves something
to be desired, if you have been exposed to Racket (or Haskell, but that's a
different story). Writing macros is harder due to the irregular syntax, but
thankfully a set of macros only needs to be created once.

    http://paulgraham.com/icad.html

Practicality beats purity: hence, fix the minor annoyances that would otherwise
quickly add up, and reap the benefits of both worlds. If Python is software
glue, Lispython is an additive that makes it flow better.

**Note**

For PG's accumulator puzzle even Lispython can do no better than this
let-over-lambda::

    foo = lambda n0: let[(n, n0) in
                         (lambda i: n << n + i)]
    f = foo(10)
    f(1) # 11
    f(1) # 12

which still sets up a separate place for the accumulator. The modern pure
Python solution avoids that, but needs many lines::

    def foo(n):
        def accumulate(i):
            nonlocal n
            n += i
            return n
        return accumulate
    f = foo(10)
    f(1) # 11
    f(1) # 12

The problem is that assignment to a lexical variable (including formals) is a
statement in Python. If we abbreviate ``accumulate`` as a lambda, it needs a
``let`` environment to write in (to use unpythonic's expression-assignment).
(But see ``envify`` in ``unpythonic.syntax``.)

**CAUTION**

No instrumentation exists (or is even planned) for the Lispython layer; you'll
have to use regular Python tooling to profile, debug, and such. The layer
should be thin enough for this not to be a major problem in practice.
"""

# TODO: fix the unpythonic.syntax block macros to leave a placeholder for
# other macros; TCO needs to detect and skip "with continuations" blocks
# inside it in order for lispython to work properly when "with continuations"
# is manually used in a lispython program.

from ast import Expr, Name, If, Num, copy_location

from macropy.core.quotes import macros, q, name
from macropy.core.walkers import Walker

def ast_transformer(tree):
    # Skeleton for AST-transformed user module.
    with q as newbody:
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

    # Boilerplate.
    # TODO: make a utility for the boilerplate tasks?
    def is_paste_here(tree):
        return type(tree) is Expr and type(tree.value) is Name and tree.value.id == "__paste_here__"

    module_body = tree
    if not module_body:
        assert False, "{}: expected at least one statement or expression in module body".format(__name__)

    locref = module_body[0]
    @Walker
    def splice(tree, **kw):
        if not is_paste_here(tree):
            # XXX: MacroPy's debug logger will sometimes crash if a node is missing a source location.
            # The skeleton is fully macro-generated with no location info to start with.
            if not all(hasattr(tree, x) for x in ("lineno", "col_offset")):
                return copy_location(tree, locref)
            return tree
        return If(test=Num(n=1),
                  body=module_body,
                  orelse=[],
                  lineno=locref.lineno, col_offset=locref.col_offset)
    return splice.recurse(newbody)

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
