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

# TODO: Move `where` from letdoutil to letdo, make it a @namemacro, and declare it public.

# TODO: Emit a `do[]` in `multilambda`.

# TODO: Consider reversing the MRO of @generic (to latest first), since the point is to be extensible.

# TODO: Add docs navigation to all documentation files, like `mcpyrate` has.

# TODO: Have a common base class for all `unpythonic` `ASTMarker`s?

# TODO: With `mcpyrate` we could start looking at values, not names, when the aim is to detect hygienically captured `unpythonic` constructs. See use sites of `isx`; refer to `mcpyrate.quotes.is_captured_value` and `mcpyrate.quotes.lookup_value`.

# TODO: macro docs: "first pass" -> "outside in"; "second pass" -> "inside out"

# TODO: something like `unpythonic.syntax.nameutil` should probably live in `mcpyrate` instead

# TODO: Consider using run-time compiler access in macro tests, like `mcpyrate` itself does. This compartmentalizes testing so that the whole test module won't crash on a macro-expansion error.

# TODO: Change decorator macro invocations to use [] instead of () to pass macro arguments. Requires Python 3.9.

# TODO: Check expansion order of several macros in the same `with` statement

# TODO: AST pattern matching for `mcpyrate`? Would make destructuring easier. A writable representation (auto-viewify) is a pain to build, though...

# TODO: 0.16: move `scoped_transform` to `mcpyrate` as `ScopedASTTransformer` and `ScopedASTVisitor`.

from .autocurry import *  # noqa: F401, F403
from .autoref import *  # noqa: F401, F403
from .dbg import *  # noqa: F401, F403
from .forall import *  # noqa: F401, F403
from .ifexprs import *  # noqa: F401, F403
from .lambdatools import *  # noqa: F401, F403
from .lazify import *  # noqa: F401, F403
from .letdo import *  # noqa: F401, F403
from .letdoutil import where  # noqa: F401
from .letsyntax import *  # noqa: F401, F403
from .nb import *  # noqa: F401, F403
from .prefix import *  # noqa: F401, F403
from .tailtools import *  # noqa: F401, F403
from .testingtools import *  # noqa: F401, F403

# We use `dyn` to pass the `expander` parameter to the macro implementations.
class _NoExpander:
    def __getattr__(self, k):  # Make the dummy error out whenever we attempt to do anything with it.
        raise NotImplementedError("Macro expander instance has not been set in `dyn`.")
make_dynvar(_macro_expander=_NoExpander())
