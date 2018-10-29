# -*- coding: utf-8 -*-
"""Utilities for working with syntax."""

from functools import partial

from ast import Call, Name, Attribute, Lambda, FunctionDef, copy_location, fix_missing_locations
from unpythonic.syntax.astcompat import AsyncFunctionDef

from macropy.core import Captured
from macropy.core.walkers import Walker

def fixsrcloc(newtree, tree):
    return fix_missing_locations(copy_location(newtree, tree))

def isx(tree, x, allow_attr=True):
    """Check if tree is a reference to an object by the name ``x`` (str).

    ``x`` is recognized both as a bare name and as an attribute, to support
    both from-imports and regular imports of ``somemodule.x``.

    Additionally, we detect ``x`` inside ``Captured`` nodes, which may be
    inserted during macro expansion.

    allow_attr: can be set to ``False`` to disregard ``Attribute`` nodes.
    """
    # WTF, so sometimes there **is** a Captured node, while sometimes there isn't (_islet)? At which point are these removed?
    # Captured nodes only come from unpythonic.syntax, and we use from-imports
    # and bare names for anything hq[]'d; but explicit references may use either
    # bare names or somemodule.f.
    return (type(tree) is Name and tree.id == x) or \
           (type(tree) is Captured and tree.name == x) or \
           (allow_attr and type(tree) is Attribute and tree.attr == x)

def isec(tree, known_ecs):
    """Check if tree is a call to a function known to be an escape continuation.

    known_ec: list of str, names of known escape continuations.

    Only bare-name references are supported.
    """
    return type(tree) is Call and type(tree.func) is Name and tree.func.id in known_ecs

@Walker
def detect_callec(tree, *, collect, **kw):
    """Collect names of escape continuations from call_ec invocations in tree.

    Currently supported and unsupported cases::

        # use as decorator, supported
        @call_ec
        def result(ec):  # <-- we grab name "ec" from here
            ...

        # use directly on a literal lambda, supported
        result = call_ec(lambda ec: ...)  # <-- we grab name "ec" from here

        # use as a function, **NOT supported**
        def g(ec):           # <-- should grab from here
            ...
        ...
        result = call_ec(g)  # <-- but this is here; g could be in another module
    """
    # literal function names that are always interpreted as an ec.
    # "brk" is needed to combo with unpythonic.fploop.breakably_looped.
    fallbacks = ["ec", "brk"]
    for x in fallbacks:
        collect(x)
    iscallec = partial(isx, x="call_ec")
    # TODO: add support for general use of call_ec as a function (difficult)
    if type(tree) in (FunctionDef, AsyncFunctionDef) and any(iscallec(deco) for deco in tree.decorator_list):
        fdef = tree
        collect(fdef.args.args[0].arg)  # FunctionDef.arguments.(list of arg objects).arg
    # TODO: decorated lambdas with other decorators in between
    elif type(tree) is Call and iscallec(tree.func) and type(tree.args[0]) is Lambda:
        lam = tree.args[0]
        collect(lam.args.args[0].arg)
    return tree
