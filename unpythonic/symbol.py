# -*- coding: utf-8; -*-
"""Lispy symbols for Python."""

__all__ = ["Symbol", "gensym"]

from itertools import count

_symbols = {}  # registry

class Symbol:
    """A lispy symbol type for Python.

    In plain English: a lightweight, human-readable, process-wide unique marker,
    that can be quickly compared to another such marker by object identity::

        cat = Symbol("cat")
        assert cat is Symbol("cat")
        assert cat is not Symbol("dog")

    Supports `pickle`. Unpickling a `Symbol` gives the same `Symbol` instance
    as constructing another one with the same name.

    CAUTION: If you're familiar with JavaScript's `Symbol`, that actually
    performs the job of Lisp's `gensym`, which always returns a unique value,
    even when called again with the same argument. See `gensym`.

    name: str
        The human-readable name of the symbol; maps to object identity.
    """
    def __new__(cls, name):  # This covers unpickling, too.
        if name not in _symbols:
            _symbols[name] = super().__new__(cls)
        return _symbols[name]
    def __init__(self, name):
        self.name = name

    # Pickle support. The default `__setstate__` is fine,
    # but we must pass args to `__new__`.
    def __getnewargs__(self):
        return (self.name,)

    def __str__(self):
        return self.name
    def __repr__(self):
        return 'Symbol("{}")'.format(self.name)

def gensym(name):
    """Create a new unique `Symbol` whose name begins with `name`.

    The return value is the only time you'll see that `Symbol` object
    (without guessing the name, which goes against the purpose of this
    function); take good care of it!

    The point of `gensym` is to create a unique nonce/sentinel value;
    nothing else `is` that value. The equivalent pythonic idiom, without
    the human-readable description, is `nonce = object()`.

    If you're familiar with MacroPy's `gen_sym`, that's different; its purpose
    is to create a lexical identifier that is not previously in use, whereas
    this `gensym` creates an `unpythonic.Symbol` object for run-time use.

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
            return Symbol(maybe_unique_name)  # this will auto-insert it to the symbol registry
