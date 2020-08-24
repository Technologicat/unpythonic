# -*- coding: utf-8 -*-
"""Utilities to support unpythonic.syntax.lazify.

This is a separate module for dependency reasons; this is regular code,
upon which other regular code is allowed to depend.
"""

__all__ = ["passthrough_lazy_args", "maybe_force_args", "force1", "force"]

from .regutil import register_decorator
from .dynassign import make_dynvar
from .symbol import gensym

# HACK: break dependency loop llist -> fun -> lazyutil -> collections -> llist
#from .collections import mogrify
_init_done = False
jump = gensym("jump")
def _init_module():  # called by unpythonic.__init__ when otherwise done
    global mogrify, jump, _init_done
    from .collections import mogrify
    from .tco import jump
    _init_done = True

try:  # MacroPy is optional for unpythonic
    # This bug was REALLY hard to track down, so let's document:
    #  - In MacroPy, there's a thing called `macropy.core.macros.injected_vars`, which holds
    #    constructors for `self.file_vars` for an `ExpansionContext`.
    #  - Constructors are registered to it using the decorator `macropy.util.register(injected_vars)`.
    #  - Registrations occur in the order the constructor function definitions are encountered.
    #  - Some constructors may depend on having others available via the **kw mechanism (at least
    #    some of the **kws actually come from the `self.file_vars` of the expansion context).
    #  - Specifically, `interned_name` (from quick_lambda) requires `gen_sym` to have been defined first.
    #  - But if we import `quick_lambda` before other MacroPy modules, `interned_name` will get
    #    registered before `gen_sym`, raising a mysterious error:
    #        TypeError: interned_name() missing 1 required positional argument: 'gen_sym'
    #  - This occurs when MacroPy tries to instantiate `interned_name` for a `ModuleExpansionContext`.
    #  - That happens implicitly when we `import macropy.activate` (somewhere much later),
    #    because `activate` itself imports `failure`, which uses `hquotes`, which happens to use macros.
    #  - So to be safe, **always import macropy.activate first**, before other MacroPy modules.
    import macropy.activate  # noqa: F401, we only import it first so MacroPy boots up correctly.
    from macropy.quick_lambda import Lazy  # This is what we actually need here.
except ImportError:  # pragma: no cover, only triggered if MacroPy is not installed, but running the test suite needs MacroPy.
    class Lazy:
        pass

make_dynvar(_build_lazy_trampoline=False)  # interaction with TCO

# -----------------------------------------------------------------------------

@register_decorator(priority=95)
def passthrough_lazy_args(f):
    """Mark a function for passthrough of lazy args.

    When a function has this mark, its arguments won't be forced by
    ``maybe_force_args``. This is the only effect the mark has.

    This is useful for decorating "infrastructure" functions that are strict
    (i.e. not lazy; defined outside any `with lazify` block), but do not need
    to access the values of all of their arguments. Usually the reason is that
    those arguments are just passed through for actual access elsewhere.

    If needed, it's still possible to force individual arguments inside the
    body of a function decorated with this, using `force` or `force1`.

    For example, `curry` uses this strategy to find out which function it
    should call (by forcing only its argument `f`), but it does not need to
    access the values of any of its other arguments. Those other arguments are
    just passed on to the function in question, so that's the correct place to
    make the lazy/strict distinction for those arguments. (`curry` then uses
    `maybe_force_args` to make the actual call, so that the call target is
    also checked for this mark.)

    **CAUTION**: The mark is implemented as an attribute on the function
    object. Hence, if the result is wrapped by another decorator, the mark
    won't be active on the final decorated function.

    The exact position where you want this in the decorator list depends
    on what exactly you're doing - the priority is set to `95` to make this
    apply before `curry`, so that `curry` will see the mark.

    **NOTE**: Conceptually, an argument having the passthrough-only property
    is closely related to parametric polymorphism. A function that just passes
    through an argument to another function, without accessing it, usually is
    parametric (in the polymorphism sense) in that argument. See the
    introduction of:

        Arjun Guha, Jacob Matthews, Robert Bruce Findler, Shriram Krishnamurthi 2007:
        Relationally-Parametric Polymorphic Contracts
            http://cs.brown.edu/~sk/Publications/Papers/Published/gmfk-rel-par-poly-cont/

    For simplicity, this decorator assumes blanket parametricity - i.e. the
    decorated function *could* be parametric in *all* of its arguments. however,
    it is not the role of this decorator to guarantee anything about parametricity.
    This is an implementation detail that says "treat this function as if it could
    be parametric in any or all of its arguments".

    It is then the responsibility of the decorated function to force those arguments
    it actually needs to access (i.e., not just pass through).
    """
    f._passthrough_lazy_args = True
    return f

def islazy(f):
    """Return whether the function f is marked for passthrough of lazy args.

    This is mainly used internally by `unpythonic.syntax.lazify`, but is
    provided as part of the public API, so that also user code can inspect
    the mark if it needs to.
    """
    # special-case "_let" for lazify/curry combo when let[] expressions are present
    return hasattr(f, "_passthrough_lazy_args") or (hasattr(f, "__name__") and f.__name__ == "_let")

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
