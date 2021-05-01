# -*- coding: utf-8 -*-
"""unpythonic.syntax: Toto, I've a feeling we're not in Python anymore.

Requires `mcpyrate`.
"""

from ..dynassign import make_dynvar

# --------------------------------------------------------------------------------
# This module only re-exports the macro interfaces so the macros can be imported
# by `from unpythonic.syntax import macros, ...`. The submodules contain the actual
# macro interfaces (and their docstrings), as well as the syntax transformers
# (i.e. regular functions that process ASTs) that implement the macros.
# --------------------------------------------------------------------------------

# --------------------------------------------------------------------------------
# **Historical NOTE**:
#
# These macros were originally written years before `mcpyrate` even existed, and were designed to run on
# MacroPy. It was a pioneering product, and an excellent choice at the time. Particularly, it can't have
# been easy to be the first to implement quasiquotes for Python, up to and including hygienic captures!
# So, my hat is off for the MacroPy team - without MacroPy, there would be no `mcpyrate`.
#
# Now, let's get technical:
#
# MacroPy 1.1.0b2 expands macros using a two-pass system: first pass outside in, then second pass inside
# out. By default, a macro expands in the inside-out pass. By making the macro interface function into a
# generator (instead of a regular function), it can opt in to two-pass processing. It then `yield`s the
# first-pass (outside in) output, and optionally `return`s the second-pass (inside out) output, if any.
# The MacroPy interface is thus similar to how `contextlib.contextmanager` treats the enter and exit code.
#
# Following MacroPy's default mode, most of the macros in `unpythonic.syntax` are designed to expand
# inside-out. This seemed a good idea at the time, particularly regarding the lexical scoping of `let`
# constructs, which were one of the first features of `unpythonic.syntax`. However, with `mcpyrate`
# that's not such a bright idea. First, the default is outside-in (because less magic). Secondly,
# because I followed the `mcpy` design and didn't want to use generators to define macros, this means
# that expanding inside-out requires an explicit recursion call (very pythonic!) - but this has the
# implication that the debug expansion stepper (see macro `mcpyrate.debug.step_expansion`) will not get
# control back until after all the inner macros have expanded. So inside-out expansions are harder to
# debug. As of `mcpyrate` 3.2.2, the expansion stepper has gained the `"detailed"` option, which will
# show individual inner macro expansions, but there's no way to get an overview of the whole tree
# before control returns to the stepper.
#
# (`mcpyrate`'s expansion stepper is a logical extension of the idea of MacroPy's `show_expanded`, and
# was inspired by Racket's macro stepper. Beside the final AST, it also shows the intermediate steps of
# the expansion, and outputs the unparsed code with syntax highlighting.)
#
# A better way would be to expand outside-in, because many of our macros work together; using the
# outside-in order would reduce the need to analyze macro-expanded ASTs. Lexical scoping for `let` could
# be achieved in this system by detecting boundaries of nested `let` (et al.) invocations, recursing
# into that invocation first, and then processing the resulting tree normally. (So the order would be
# outside-in except for those inner invocations that absolutely need to expand first, e.g. to respect
# lexical scoping for lexically nested `unpythonic` envs.)
#
# (No sensible person works directly with macro-expanded ASTs if that can be avoided. It goes against
# the grain of the macro abstraction. It's a bit like decompiling to see what's going on.)
#
# Finally, be aware that in `mcpyrate`, an inside-out expansion order is achieved by recursing explicitly:
#
# def mymacrointerface(tree, *, expander, *kw):
#    # perform your outside-in processing here
#
#    tree = expander.visit(tree)  # recurse explicitly
#
#    # perform your inside-out processing here
#
#    return tree
#
# If the line `tree = expander.visit(tree)` is omitted, the macro expands outside-in.
# Note this default is different from MacroPy's!
#
# There are further cleanups of the macro layer possible with `mcpyrate`. For example:
#
#  - Quasiquotes no longer auto-expand macros in the quoted code. `letseq` could use hygienic *macro*
#    capture and just return an unexpanded `let` and another `letseq` (with one fewer binding),
#    similarly to how Racket implements `let*`. See `unpythonic.syntax.simplelet` for a demo.
#
#  - Many macros could perhaps run in the outside-in pass. Some need a redesign for their AST analysis,
#    but much of that has been sufficiently abstracted (e.g. `unpythonic.syntax.letdoutil`) so that this
#    is mainly a case of carefully changing the analysis mode at all appropriate use sites.
#
# However, 0.15.0 is the initial version that runs on `mcpyrate`, and the focus is to just get this running.
# Cleanups can be done in a future release.

# TODO: debugging:
#   TODO: The HasThon test (grep for it), when putting the macros in the wrong order on purpose,
#   TODO: confuses the call site filename detector of the test framework. Investigate.

# TODO: Consistent naming for syntax transformers? `_macroname_transform`? `_macroname_stx`?

# TODO: Have a common base class for all `unpythonic` `ASTMarker`s?

# TODO: `let` constructs: document difference to Python 3.8 walrus operator (`let` creates a scope, `:=` doesn't)

# TODO: `make_dynvar` needs to be better advertised in the docs. A workflow example would also be nice.

# TODO: Drop `# pragma: no cover` from macro tests as appropriate, since `mcpyrate` reports coverage correctly.
# TODO: Test the q[t[...]] implementation in do0[]

# TODO: With `mcpyrate` we could start looking at values, not names, when the aim is to detect hygienically captured `unpythonic` constructs. See use sites of `isx`; refer to `mcpyrate.quotes.is_captured_value` and `mcpyrate.quotes.lookup_value`.

# TODO: macro docs: "first pass" -> "outside in"; "second pass" -> "inside out"

# TODO: Some macros look up others; convert lookups to mcpyrate style (accounting for as-imports)
# TODO: or hygienic macro references (`h[...]`), as appropriate.

# TODO: `isx` and `getname` from `unpythonic.syntax.nameutil` should probably live in `mcpyrate` instead

# TODO: `mcpyrate` does not auto-expand macros in quasiquoted code.
#  - Consider when we should expand macros in quoted code and when not
#  - Consider what changes this implies for other macros that read the partially expanded output
#    (some things may change from expanded to unexpanded, facilitating easier analysis but requiring
#     code changes)

# TODO: Consider using run-time compiler access in macro tests, like `mcpyrate` itself does. This compartmentalizes testing so that the whole test module won't crash on a macro-expansion error.

# TODO: Change decorator macro invocations to use [] instead of () to pass macro arguments. Requires Python 3.9.

# TODO: Check expansion order of several macros in the same `with` statement

# TODO: grep for any remaining mentions of "macropy"

# TODO: Upgrade anaphoric if's `it` into a `mcpyrate` magic variable that errors out at compile time when it appears in an invalid position (i.e. outside any `aif`). Basically, take the `aif` from `mcpyrate`.
# TODO: also let_syntax block, expr
# TODO: also kw() in unpythonic.syntax.prefix

# TODO: let_syntax block, expr: syntactic consistency: change parentheses to brackets

# TODO: grep codebase for "0.15", may have some pending interface changes that don't have their own GitHub issue (e.g. parameter ordering of `unpythonic.it.window`)

# TODO: ansicolor: `mcpyrate` already depends on Colorama anyway (and has a *nix-only fallback capability).
# TODO: `unpythonic` only needs the colorizer in the *macro-enabled* test framework; so we don't really need
# TODO: to provide our own colorizer; we can use the one from `mcpyrate`. (It would be different if regular code needed it.)

# TODO: with mcpyrate, do we really need to set `ctx` in our macros? (does our macro code need it?)

# TODO: Move dialect examples from `pydialect` into a new package, `unpythonic.dialects`.
# TODO: `mcpyrate` now provides the necessary infrastructure, while `unpythonic` has the macros
# TODO: needed to make interesting things happen. Update docs accordingly for both projects.

# TODO: AST pattern matching for `mcpyrate`? Would make destructuring easier. A writable representation (auto-viewify) is a pain to build, though...

# Re-exports - macro interfaces
from .autocurry import autocurry  # noqa: F401
from .autoref import autoref  # noqa: F401
from .dbg import dbg  # noqa: F401
from .forall import forall  # noqa: F401
from .ifexprs import aif, cond  # noqa: F401
from .lambdatools import multilambda, namedlambda, f, quicklambda, envify  # noqa: F401
from .lazify import lazy, lazyrec, lazify  # noqa: F401
from .letdo import (let, letseq, letrec,  # noqa: F401
                    dlet, dletseq, dletrec,
                    blet, bletseq, bletrec,
                    local, delete, do, do0)
from .letsyntax import let_syntax, abbrev  # noqa: F401
from .nb import nb  # noqa: F401
from .prefix import prefix  # noqa: F401
from .tailtools import (autoreturn,  # noqa: F401
                        tco,
                        continuations, call_cc)
from .testingtools import (the, test,  # noqa: F401
                           test_signals, test_raises,
                           fail, error, warn)

# Re-exports - regular code
from .dbg import dbgprint_block, dbgprint_expr  # noqa: F401, re-export for re-use in a decorated variant.
from .forall import insist, deny  # noqa: F401
from .ifexprs import it  # noqa: F401
from .letdoutil import where  # noqa: F401
from .lazify import force, force1  # noqa: F401
from .letsyntax import block, expr  # noqa: F401
from .prefix import q, u, kw  # noqa: F401  # TODO: bad names, `mcpyrate` uses them too.

# We use `dyn` to pass the `expander` parameter to the macro implementations.
class _NoExpander:
    def visit(self, tree):
        raise NotImplementedError("Macro expander instance has not been set in `dyn`.")
make_dynvar(_macro_expander=_NoExpander())
