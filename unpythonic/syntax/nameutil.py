# -*- coding: utf-8 -*-
"""Utilities for working with identifiers in macros.

Main purpose is to be able to query both direct and hygienically captured names
with a unified API.
"""

__all__ = ["isx", "getname"]

from ast import Name, Attribute

from mcpyrate.core import Done
from mcpyrate.quotes import is_captured_value

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
    if isinstance(tree, Done):
        return isx(tree.body, x, accept_attr=accept_attr)
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
    key = is_captured_value(tree)  # AST -> (name, frozen_value) or False
    if key:
        name, frozen_value = key

    ismatch = x if callable(x) else lambda name: name == x
    return ((type(tree) is Name and ismatch(tree.id)) or
            (key and ismatch(name)) or
            (accept_attr and type(tree) is Attribute and ismatch(tree.attr)))

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
    if key:
        name, frozen_value = key
        return name
    if accept_attr and type(tree) is Attribute:
        return tree.attr
    return None
