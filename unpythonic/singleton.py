# -*- coding: utf-8; -*-
"""A pickle-aware singleton abstraction.

To use it, inherit your class from `Singleton`. Can be used as a mixin.


**Behavior**

- If you have instantiated a singleton, and then unpickle an instance of that same
  singleton type, the object identity will not change. When the unpickling procedure
  attempts to create the instance, it will get redirected to the existing instance.

  This allows object identity checks to identify the singletons across pickle dumps
  (e.g. there is only one linked list terminator `nil` in the process, whether or not
  some linked lists were loaded from a pickle dump).


- Upon unpickling, by default, any existing instance data the singleton instance has
  is overwritten with the instance data from the pickle dump.

  This is due to the behavior of the default `__setstate__`, but it is also the
  solution of least surprise. Arguably this is exactly the expected behavior:
  there's only one instance of the singleton, and its state is restored upon
  unpickling.

  If you want something else, what happens to the pickled instance data can
  be customized in the standard pythonic way, with custom `__getstate__` and
  `__setstate__` methods in your class definition.

  https://docs.python.org/3/library/pickle.html#object.__getstate__
  https://docs.python.org/3/library/pickle.html#object.__setstate__

- We expect you to manage references to singleton instances manually, just like
  for regular objects. Calling the constructor of a singleton type again while
  an instance still exists is considered a `TypeError` (since it's a type that
  doesn't support that operation).

  This break from the tradition of the classical singleton design pattern allows us
  to better adhere to the principles of fail-fast and least surprise, as well as
  separate the concerns of enforcing singleton-ness and obtaining the instance
  reference, all of which arguably makes this solution more pythonic.


Note this is a true singleton, not a Borg; there is really only one instance.
"""

# **Technical details**
#
# To make this work:
#
# 1) We store the references to the singleton instances in a variable outside
#    any class, at the module top level.
#
#    If the `_instances` dictionary was stored in the class or in the metaclass,
#    it would get clobbered at unpickle time, leading to a situation where the
#    existing singleton instance (if someone has kept a reference to it) and the
#    unpickled instance are different. Obviously, for singletons we don't want
#    that - it should be the same instance whether or not it came from a pickle dump.
#
#    Keeping the `_instances` dictionary external to the singletons themselves,
#    the currently existing singleton instance will prevail even when a singleton
#    is unpickled into a process that already has an instance of that particular
#    singleton.
#
#    This module only keeps weak references to the singleton instances, so when
#    your last reference to a singleton instance is deleted, that singleton
#    instance becomes eligible for garbage collection.
#
#    (Once the instance is actually destroyed, the machinery will know it, so
#     you can then create a new instance (again, exactly one!) of that type of
#     singleton, if you want. Leaving aside the question whether there are valid
#     use cases for this behavior, it is arguably what is expected.)
#
# 2) Instance creation is customized in two layers:
#
#    - Metaclass, which intercepts constructor invocations, and arranges things
#      so that if the singleton instance for a particular class already exists,
#      invoking the constructor again raises `TypeError`.
#
#    - Base class, which customizes **instance creation** proper, with a custom
#      `__new__`. This actually manages the single instance.
#
#    This separation is necessary, because pickle does not call the class at
#    unpickling time. Hence, when unpickling, our custom metaclass has no
#    chance to act; only `__new__` (of the instance's class) and `__setstate__`
#    (of the instance) are called.
#
# There is an inherent impedance mismatch between singleton semantics and
# the language allowing to express the creation of multiple instances of
# the same class (which, with the exception of singletons, is always The
# Right Thing).
#
# This leads to a design choice, with three options as to what to do when
# the constructor of a singleton is called second and further times:
#
#   a) Let `__init__` re-run each time, overwriting the state. Surprising,
#      and particularly bad, because an innocent-looking constructor call
#      will magically mutate existing state. Good luck tracking down any bugs.
#
#   b) Let `__init__` run only once, but allow using the constructor call as
#      a shorthand to get the singleton instance, also when it already exists.
#      This perhaps best mimics the classical singleton design pattern. But this
#      behavior can still lead to surprises, because the new state provided to
#      the second and later constructor calls doesn't take. Probably slightly
#      easier to debug than the first option, though.
#
#   c) Make second and further constructor calls raise `TypeError`, triggering
#      an explicit error as early as possible.
#
# We have chosen c).

__all__ = ["Singleton"]

import threading
from weakref import WeakValueDictionary

_instances = WeakValueDictionary()
_instances_update_lock = threading.RLock()

# Metaclass: override default __new__ + __init__ behavior, to allow creating
# at most one instance.
#
# Because magic methods are looked up **on the type**, not on the instance,
# we override `__call__` **in the metaclass**, in order to override calls
# of the class (i.e. constructor invocations).
class ThereCanBeOnlyOne(type):
    def __call__(cls, *args, **kwargs):
        # For consistency with single-thread behavior, don't let more than one
        # `__call__` run concurrently. This eliminates a race when many threads
        # try to instantiate the singleton, guaranteeing only one of them will
        # enter `__new__`.
        #
        # This does nothing for the case where many threads try to unpickle a singleton,
        # though, because doing that skips the metaclass's `__call__`. For that, we lock
        # also inside `Singleton.__new__`.
        with _instances_update_lock:
            # Here we can do things like call `cls.__init__` only if `cls` was not
            # already in `_instances`... or outright refuse to create a second instance:
            if cls in _instances:
                raise TypeError("Singleton instance of {} already exists".format(cls))
            # When allowed to proceed, we mimic default behavior.
            # TODO: Maybe we should just "return super().__call__(cls, *args, **kwargs)"?
            # TODO: That doesn't work in the case where we have extra arguments,
            # TODO: so for now we do this manually. Maybe investigate later.
            instance = cls.__new__(cls, *args, **kwargs)
            cls.__init__(instance, *args, **kwargs)
            return instance

# Base class: override instance creation, in a way that interacts correctly
# with pickle.
#
# A base class does that fine, a metaclass by itself doesn't. The class won't
# get called at unpickle time, so the metaclass's `__call__` has no chance to
# act. Also, since we want to customize *instance creation*, not change the
# semantics of the class definition (like sqlalchemy does), the metaclass's
# `__new__` and `__init__` are of no use to us.
#
# So a base class is really the right place to insert a custom `__new__` to
# achieve what we want.
class Singleton(metaclass=ThereCanBeOnlyOne):
    """Base class for singletons. Can be used as a mixin.

    NOTE: Unpickling a singleton will retain the current instance, if it has already
    been created (in the current process). By default, its state is overwritten
    from the pickled data, by the default `__setstate__`.
    """
    # We allow extra args so that __init__ can have them, but ignore them in the
    # super __new__ call, since our super is `object`, which takes no extra args.
    def __new__(cls, *args, **kwargs):
        # What we want to do:
        #   if cls not in _instances:
        #       _instances[cls] = super().__new__(cls)
        #   return _instances[cls]
        #
        # But because weakref and thread-safety, we must:
        try:  # EAFP to eliminate TOCTTOU.
            return _instances[cls]
        except KeyError:
            # Then be careful to avoid race conditions.
            with _instances_update_lock:
                if cls not in _instances:
                    # We were the first thread to acquire the lock.
                    # Make a strong reference to keep the new instance alive until construction is done.
                    instance = _instances[cls] = super().__new__(cls)
                else:
                    # Some other thread acquired the lock before us, and created the instance.
                    instance = _instances[cls]
            return instance


# TODO: This won't work with classes that need another custom metaclass,
# TODO: because then there's no unique most specific metaclass.
# https://docs.python.org/3/reference/datamodel.html#determining-the-appropriate-metaclass
#
# **Workaround**: define a custom metaclass inheriting from all of those
# metaclasses (including `ThereCanBeOnlyOne`). No body required; just "pass".
#
# (`ThereCanBeOnlyOne` is not officially part of the public API of this module,
#  but for this purpose, it's fine to use it directly. Hence no underscore in
#  the name, even though it's not listed in `__all__`.)
#
# Then use that as the metaclass for the class that both wants to be a singleton
# and to use another metaclass for some other reason. The combined metaclass
# will then satisfy the most-specific-metaclass constraint.

# This is of course assuming that the metaclasses are orthogonal enough not to
# interfere with each others' operation. If not, there is no general solution;
# the specific situation must be sorted out by strategically overriding and
# implementing any methods that conflict.
#
#
# Proper solutions?
#
#   - We can't drop our metaclass and enforce the don't-call-me-again
#     constraint in `Singleton.__new__`, because we need pickle to be able
#     to call `Singleton.__new__` while an instance already exists, to get
#     redirected to the existing instance.
#
#   - The other option, providing a base class `__init__` to raise `TypeError`
#     at initialization time if an instance already exists, could also work,
#     because pickle skips `__init__`.
#
#     However, this is not robust, as the derived class may easily forget to
#     call our `__init__`. In comparison, it's rare to customize `__new__`,
#     so that won't break as easily.
#
#     Even assuming no mistakes in code that uses this, that requires more code
#     at each use site, for the super call; the whole point of this abstraction
#     being to condense the idea of "make this class a singleton", at the use
#     site, (beside the import) into just a single word.
