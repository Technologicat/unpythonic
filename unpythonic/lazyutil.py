# -*- coding: utf-8 -*-
"""Utilities to support unpythonic.syntax.lazify.

This is a separate module for dependency reasons; this is regular code,
upon which other regular code is allowed to depend.
"""

__all__ = ["mark_lazy", "maybe_force_args", "force1", "force"]

from .regutil import register_decorator
from .dynassign import make_dynvar

# HACK: break dependency loop llist -> fun -> lazyutil -> collections -> llist
#from .collections import mogrify
_init_done = False
jump = object()  # gensym, nothing else "is" this
def _init_module():  # called by unpythonic.__init__ when otherwise done
    global mogrify, jump, _init_done
    from .collections import mogrify
    from .tco import jump
    _init_done = True

try:  # MacroPy is optional for unpythonic
    from macropy.quick_lambda import Lazy
except ImportError:
    class Lazy:
        pass

make_dynvar(_build_lazy_trampoline=False)  # interaction with TCO

# -----------------------------------------------------------------------------

@register_decorator(priority=95)
def mark_lazy(f):
    """Internal. Helps calling lazy functions from outside a ``with lazify`` block."""
    f._lazy = True
    return f

def islazy(f):
    """Internal. Return whether the function f is marked as lazy.

    When a function is marked as lazy, its arguments won't be forced by
    ``maybe_force_args``. This is the only effect the mark has.
    """
    # special-case "_let" for lazify/curry combo when let[] expressions are present
    return hasattr(f, "_lazy") or (hasattr(f, "__name__") and f.__name__ == "_let")

def maybe_force_args(f, *thunks, **kwthunks):
    """Internal. Helps calling strict functions from inside a ``with lazify`` block."""
    if f is jump:  # special case to avoid drastic performance hit in strict code
        target, *argthunks = thunks
        return jump(force1(target), *argthunks, **kwthunks)
    if islazy(f):
        return f(*thunks, **kwthunks)
    return f(*force(thunks), **force(kwthunks))

# Because force(x) is more explicit than x() and MacroPy itself doesn't define this.
def force1(x):
    """Force a MacroPy lazy[] promise.

    For a promise ``x``, the effect of ``force1(x)`` is the same as ``x()``,
    except that ``force1 `` first checks that ``x`` is a promise.

    If ``x`` is not a promise, it is returned as-is (à la Racket).
    """
    return x() if isinstance(x, Lazy) else x

def force(x):
    """Like force1, but recurse into containers.

    This recurses on any containers with the appropriate ``collections.abc``
    abstract base classes (virtuals ok too). Mutable containers are updated
    in-place, for immutables a new instance is created. For details, see
    ``unpythonic.collections.mogrify``.
    """
    if not _init_done:
        return x
    return mogrify(force1, x)  # in-place update to allow lazy functions to have writable list arguments
