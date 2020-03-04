# -*- coding: utf-8; -*-
"""A lispy symbol type for Python."""

__all__ = ["Symbol"]

_symbols = {}

class Symbol:
    def __new__(cls, name):  # This covers unpickling, too.
        if name not in _symbols:
            _symbols[name] = super().__new__(cls)
        return _symbols[name]
    def __init__(self, name):
        self.name = name

    # pickle support
    def __getnewargs__(self):
        return (self.name,)

    def __str__(self):
        return self.name
    def __repr__(self):
        return 'Symbol("{}")'.format(self.name)
