# -*- coding: utf-8; -*-
"""Lispy symbols and gensym for Python. Pickle-aware.

See:
    https://stackoverflow.com/questions/8846628/what-exactly-is-a-symbol-in-lisp-scheme
    https://www.cs.cmu.edu/Groups/AI/html/cltl/clm/node27.html
"""

__all__ = ["sym", "gensym"]

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

    name: str
        The human-readable name of the symbol.

    intern: bool
        By default, symbols are *interned*.

        For **interned** symbols:
            The name maps directly to object instance. If you pass in the same
            `name` to the `sym` constructor, it gives you the same object
            instance.

            Even unpickling an interned `sym` produces the same `sym` instance
            as constructing another `sym` with the same name.

            This is like a Lisp symbol.

            (Technically, it's like a Scheme/Racket symbol, since Common Lisp
            stuffs all sorts of additional cruft in there. If you insist on
            emulating that, a `sym` is just a Python object.)

        For *uninterned* symbols:
            The return value from the constructor call is the only time you'll
            see that symbol object. Take good care of it!

            Uninterned symbols are useful as unique nonce/sentinel values,
            like the pythonic idiom `nonce = object()`, but they come with
            a human-readable label.

            This is like Lisp's `gensym` and JavaScript's `Symbol`.
    """
    def __new__(cls, name, intern=True):  # This covers unpickling, too.
        if not intern:
            return super().__new__(cls)
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

    def __init__(self, name, intern=True):
        self.name = name
        self.interned = intern

    # Pickle support. The default `__setstate__` is fine,
    # but we must pass args to `__new__`.
    #
    # Note we don't `sys.intern` the name *strings*; if we did,
    # we'd need a custom `__setstate__` to redo that upon unpickling.
    def __getnewargs__(self):
        return (self.name, self.interned)

    def __str__(self):
        if self.interned:
            return self.name
        return repr(self)
    def __repr__(self):
        if self.interned:
            return 'sym("{}")'.format(self.name)
        return '<uninterned symbol "{}" at 0x{:x}>'.format(self.name, id(self))

def gensym(name):
    """Create an uninterned symbol.

    This is just lispy shorthand for `sym(name, intern=False)`.

    The return value is the only time you'll see that symbol object; take good
    care of it!

    Uninterned symbols are useful as unique nonce/sentinel values, like the
    pythonic idiom `nonce = object()`, but they come with a human-readable label.

    If you're familiar with MacroPy's `gen_sym`, that's different; its purpose
    is to create a lexical identifier that is not in use, whereas this `gensym`
    creates an `unpythonic.sym` object for run-time use.

    Example::

        tabby = gensym("cat")
        scottishfold = gensym("cat")
        assert tabby is not scottishfold
        print(tabby)         # <uninterned symbol "cat" at 0x7fde8ec454e0>
        print(scottishfold)  # <uninterned symbol "cat" at 0x7fde8ec33cf8>
    """
    return sym(name, intern=False)
