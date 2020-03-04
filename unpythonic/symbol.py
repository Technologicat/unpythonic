# -*- coding: utf-8; -*-
"""Lispy symbols for Python."""

__all__ = ["Symbol"]

_symbols = {}

class Symbol:
    """A lispy symbol type for Python.

    In plain English: a lightweight, human-readable, process-wide unique marker,
    that can be quickly compared to another such marker by object identity::

        cat = Symbol("cat")
        assert cat is Symbol("cat")
        assert cat is not Symbol("dog")

    Supports `pickle`. Unpickling a `Symbol` gives the same `Symbol` instance
    as constructing another one with the same name.

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
