# -*- coding: utf-8 -*-
"""Decorator registry for the syntax machinery.

This is used to support decorated lambdas (chains of ``Call`` nodes terminating
in a ``Lambda``), since some decorators must be applied in a particular order.

Note it is **not** compulsory to register all decorators, but only those that
should be available for decorating lambdas, so that the lambda decorator
sorting logic in ``unpythonic.syntax.util`` will know in which order
to place them.

Especially the ``tco`` and ``continuations`` macros use this.
See ``unpythonic.syntax.tailtools``.
"""

# This module is kept separate from unpythonic.syntax.util simply to make
# the MacroPy dependency optional. If the user code doesn't use macros,
# the decorator registry gets populated at startup as usual, and then sits idle.
#
# This module can't be inside unpythonic.syntax for dependency reasons; that
# would require its __init__.py to run first, but it in turn expects pretty
# much all of the regular code to be already initialized.

# These names must be bound exactly once, as anyone may from-import them.
decorator_registry = []
all_decorators = set()
tco_decorators = set()

# Basic idea shamelessly stolen from MacroPy's macro registry.
def register_decorator(priority=0.0, istco=False):
    """Decorator that registers a custom decorator for the syntax machinery.

    Unknown decorators cannot be reordered robustly, hence ``sort_lambda_decorators``
    only sorts known decorators, i.e. those registered via this function.

    Usage::

        @register_decorator(priority=100)
        def mydeco(f):
            ...

    The final result is still ``mydeco``, with the side effect that it is
    registered as a known decorator with the given priority value.

    priority: number (float is ok; nominal range 0..100). The smallest number
    is the outermost decorator, largest the innermost.

    tco: set this to True when registering a decorator that applies TCO.

    The TCO flag is basically only needed by the ``tco`` and ``fploop`` modules.
    It exists because the ``tco`` macro needs to know whether a given function
    already has TCO applied to it (so that it won't be applied twice).
    """
    def register(f):
        name = f.__name__
        decorator_registry.append((priority, name))
        decorator_registry.sort()
        all_decorators.add(name)
        if istco:
            tco_decorators.add(name)
        return f
    return register
