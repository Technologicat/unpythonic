# -*- coding: utf-8; -*-
"""Lispy symbols for Python."""

__all__ = ["sym", "gensym"]

from itertools import count
from weakref import WeakValueDictionary
import threading

_symbols = WeakValueDictionary()  # registry
_symbols_update_lock = threading.Lock()

class sym:
    """A lispy symbol type for Python.

    In plain English: a lightweight, human-readable, process-wide unique marker,
    that can be quickly compared to another such marker by object identity::

        cat = sym("cat")
        assert cat is sym("cat")
        assert cat is not sym("dog")

    Supports `pickle`. Unpickling a `sym` gives the same `sym` instance
    as constructing another one with the same name.

    CAUTION: If you're familiar with JavaScript's `Symbol`, that actually
    performs the job of Lisp's `gensym`, which always returns a unique value,
    even when called again with the same argument. See `gensym`.

    name: str
        The human-readable name of the symbol; maps to object identity.
    """
    def __new__(cls, name):  # This covers unpickling, too.
        # What we want to do:
        #   if name not in _symbols:
        #       _symbols[name] = super().__new__(cls)
        #   return _symbols[name]
        #
        # But because weakref and thread-safety, we must:
        try:  # EAFP to eliminate TOCTTOU.
            return _symbols[name]
        except KeyError:
            # But we still need to be careful to avoid race conditions.
            with _symbols_update_lock:
                if name not in _symbols:
                    # We were the first thread to acquire the lock.
                    # Make a strong reference to keep the new instance alive until construction is done.
                    instance = _symbols[name] = super().__new__(cls)
                else:
                    # Some other thread acquired the lock before us, and created the instance.
                    instance = _symbols[name]
            return instance

    def __init__(self, name):
        self.name = name

    # Pickle support. The default `__setstate__` is fine,
    # but we must pass args to `__new__`.
    def __getnewargs__(self):
        return (self.name,)

    def __str__(self):
        return self.name
    def __repr__(self):
        return 'sym("{}")'.format(self.name)

# TODO: store gensyms in a separate registry so that they're not accessible by name.
def gensym(name):
    """Create a new unique symbol whose name begins with `name`.

    The return value is the only time you'll see that `sym` object
    (without guessing the name, which goes against the purpose of this
    function); take good care of it!

    The point of `gensym` is to create a unique nonce/sentinel value;
    nothing else `is` that value. The equivalent pythonic idiom, without
    the human-readable description, is `nonce = object()`.

    If you're familiar with MacroPy's `gen_sym`, that's different; its purpose
    is to create a lexical identifier that is not previously in use, whereas
    this `gensym` creates an `unpythonic.sym` object for run-time use.

    If you're familiar with JavaScript's `Symbol`, this performs the same job.

    Example::

        tabby = gensym("cat")
        scottishfold = gensym("cat")
        assert tabby is not scottishfold
        print(tabby)         # cat-gensym0
        print(scottishfold)  # cat-gensym1
    """
    # TODO: Gensymming repeatedly with the same `name` is currently O(n**2).
    # TODO: I'm tempted to keep this simple. If performance becomes a real issue,
    # TODO: we can add a cache that maps `name` to the last used `k` for that name
    # TODO: (and then still count until we actually get an unused name).
    for k in count():
        maybe_unique_name = "{}-gensym{}".format(name, k)
        if maybe_unique_name not in _symbols:
            return sym(maybe_unique_name)  # this will auto-insert it to the symbol registry
