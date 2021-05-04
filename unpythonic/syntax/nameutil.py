# -*- coding: utf-8 -*-
"""Utilities for working with identifiers in macros.

Main purpose is to be able to query both direct and hygienically captured names
with a unified API.
"""

__all__ = ["isx", "getname",
           "is_unexpanded_expr_macro", "is_unexpanded_block_macro"]

from ast import Name, Attribute, Subscript, Call
import sys

from mcpyrate.core import Done
from mcpyrate.quotes import is_captured_macro, is_captured_value, lookup_macro

# Here hygienic captures only come from `unpythonic.syntax` (unless there are
# also user-defined macros), and we use from-imports and bare names for anything
# `q[h[]]`'d; but any references that appear explicitly in the user code may use
# either bare `somename` or `unpythonic.somename`.
#
# TODO: How about `unpythonic.somemodule.somename`? Currently not detected.
#
# Note that in `mcpyrate`, a hygienic capture can contain the value of an
# arbitrary expression, which does not need to be bound to a name. In that
# case the "name" will be the unparsed source code of the expression. See
# the implementation of `mcpyrate.quotes.h`. That's harmless here since
# an expression won't produce an exact match on the name.
#
# Here we're mainly interested in the case where we have captured the value
# a name had at the use site of `h[]`, and even then, we just look at the name,
# not the actual value.
#
# TODO: Let's look at the value, not just the name. Requires changes to use sites,
# TODO: because currently `isx` doesn't know about the value the caller wants to
# TODO: check against.
#
# TODO: For our use cases, that value is usually a syntax transformer function
# TODO: defined somewhere in `unpythonic.syntax`, so we can use things like
# TODO: `q[h[letter]]` or `q[h[dof]]` in the let/do constructs to ensure that
# TODO: the workhorses resolve correctly at the use site, and still be able
# TODO: to detect the expanded forms of those constructs in the AST.
#
# TODO: The run-time value can be obtained at this end by
# TODO: `value = mcpyrate.quotes.lookup_value(key)`,
# TODO: provided that `key and (key[1] is not None)`.
# TODO: If the second element of the key is `None`, it means that
# TODO: program execution hasn't yet reached the point where the
# TODO: actual value capture triggers for that particular use of `h[]`.

def isx(tree, x, accept_attr=True):
    """Test whether tree is a reference to the name ``x`` (str).

    Alternatively, ``x`` may be a predicate that accepts a ``str``
    and returns whether it matches, to support more complex matching
    (e.g. ``lambda name: name.startswith("foo")``).

    Both bare names and attributes can be recognized, to support
    both from-imports and regular imports of ``somemodule.x``.

    We support:

        - bare name ``x``

        - the name ``x`` inside a `mcpyrate.core.Done`, which may be produced
          by expanded `@namemacro`s

        - the name ``x`` inside a `mcpyrate` hygienic capture, which may be
          inserted during macro expansion

        - ``x`` as an attribute (if ``accept_attr=True``)
    """
    ismatch = x if callable(x) else lambda name: name == x
    thename = getname(tree, accept_attr=accept_attr)
    return thename is not None and ismatch(thename)

def getname(tree, accept_attr=True):
    """The cousin of ``isx``.

    From the same types of trees, extract the name as str.

    If no match on ``tree``, return ``None``.
    """
    if isinstance(tree, Done):
        return getname(tree.body, accept_attr=accept_attr)
    if type(tree) is Name:
        return tree.id
    key = is_captured_value(tree)  # AST -> (name, frozen_value) or False
    if key:  # TODO: Python 3.8+: use walrus assignment here
        name, frozen_value = key
        return name
    if accept_attr and type(tree) is Attribute:
        return tree.attr
    return None

# TODO: This utility really wants to live in `mcpyrate`, as part of a macro destructuring subsystem.
# TODO: It needs to be made more general, to detect also macro invocations with args.
def is_unexpanded_expr_macro(macrofunction, expander, tree):
    """Check whether `tree` is an expr macro invocation bound to `macrofunction` in `expander`.

    This accounts for hygienic macro captures and as-imports.

    If there is a match, return the subscript slice, i.e. the tree that would be passed
    to the macro function by the expander if the macro was expanded normally.

    **CAUTION**: This function doesn't currently support detecting macros that
    take macro arguments.
    """
    if not type(tree) is Subscript:
        return False
    maybemacro = tree.value

    # hygienic captures and as-imports
    key = is_captured_macro(maybemacro)
    if key:  # TODO: Python 3.8+: use walrus assignment here
        name_node = lookup_macro(key)
    elif type(maybemacro) is Name:
        name_node = maybemacro
    else:
        return False

    macro = expander.isbound(name_node.id)
    if macro is macrofunction:
        if sys.version_info >= (3, 9, 0):  # Python 3.9+: the Index wrapper is gone.
            return tree.slice
        else:
            return tree.slice.value
    return False


# TODO: This utility really wants to live in `mcpyrate`, as part of a macro destructuring subsystem.
# TODO: It needs to be made more general, to detect if there are several macros in the same `with`.
def is_unexpanded_block_macro(macrofunction, expander, tree):
    """Check whether `tree` is an expr macro invocation bound to `macrofunction` in `expander`.

    This accounts for hygienic macro captures and as-imports.

    If there is a match, return the subscript slice, i.e. the tree that would be passed
    to the macro function by the expander if the macro was expanded normally.

    **CAUTION**: This function doesn't currently support detecting macros that
    take macro arguments.
    """
    if not type(tree) is Subscript:
        return False
    maybemacro = tree.value

    # discard args if any
    if type(maybemacro) is Subscript:
        maybemacro = maybemacro.value
    # parenthesis syntax for macro arguments  TODO: Python 3.9+: remove once we bump minimum Python to 3.9
    elif type(maybemacro) is Call:
        maybemacro = maybemacro.func

    # hygienic captures and as-imports
    key = is_captured_macro(maybemacro)
    if key:  # TODO: Python 3.8+: use walrus assignment here
        name_node = lookup_macro(key)
    elif type(maybemacro) is Name:
        name_node = maybemacro
    else:
        return False

    macro = expander.isbound(name_node.id)
    return macro is macrofunction
