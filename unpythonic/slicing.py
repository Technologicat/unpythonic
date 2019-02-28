# -*- coding: utf-8 -*-
"""Operations on sequences with native slice syntax. Syntactic sugar, pure Python."""

__all__ = ["view", "islice", "fup"]

from itertools import islice as islicef

from .collections import SequenceView
from .fup import fupdate

view = SequenceView

def islice(iterable):
    """Use itertools.islice with slice syntax.

    Usage::

        islice(iterable)[idx_or_slice]

    The slicing variant calls ``itertools.islice`` with the corresponding
    slicing parameters.

    As a convenience feature: a single index is interpreted as a length-1 islice
    starting at that index. The slice is then immediately evaluated and the item
    is returned.

    Examples::

        from unpythonic import primes, s

        p = primes()
        assert tuple(islice(p)[10:15]) == (31, 37, 41, 43, 47)

        assert tuple(islice(primes())[10:15]) == (31, 37, 41, 43, 47)

        p = primes()
        assert islice(p)[10] == 31

        odds = islice(s(1, 2, ...))[::2]
        assert tuple(islice(odds)[:5]) == (1, 3, 5, 7, 9)
        assert tuple(islice(odds)[:5]) == (11, 13, 15, 17, 19)  # five more

    **CAUTION**: Keep in mind ``itertools.islice`` does not support negative
    indexing for any of ``start``, ``stop`` or ``step``, and that the slicing
    process consumes elements from the iterable.
    """
    # manually curry to take indices later, but expect them in subscript syntax to support slicing
    class islice1:
        """Subscript me to perform the slicing."""
        def __getitem__(self, k):
            if isinstance(k, tuple):
                raise TypeError("multidimensional indexing not supported, got {}".format(k))
            if isinstance(k, slice):
                return islicef(iterable, k.start, k.stop, k.step)
            return tuple(islicef(iterable, k, k + 1))[0]
    return islice1()

def fup(seq):
    """Functionally update a sequence.

    Usage::

        fup(seq)[idx_or_slice] << values

    For when you want to be more functional than Python allows. Example::

        from itertools import repeat

        lst = (1, 2, 3, 4, 5)
        assert fup(lst)[3] << 42 == (1, 2, 3, 42, 5)
        assert fup(lst)[0::2] << tuple(repeat(10, 3)) == (10, 2, 10, 4, 10)

    Limitations:

      - Currently only one update specification is supported in a single ``fup()``.
        If you need more, use ``fupdate`` directly.

    Named after the sound a sequence makes when it is hit by a functional update.
    """
    # two-phase manual curry, first expect a subscript, then an lshift.
    class fup1:
        """Subscript me to specify index or slice where to fupdate."""
        def __getitem__(self, k):
            if isinstance(k, tuple):
                raise TypeError("multidimensional indexing not supported, got {}".format(k))
            class fup2:
                """Left-shift me with values to perform the fupdate."""
                def __lshift__(self, v):
                    return fupdate(seq, k, v)
            return fup2()
    return fup1()
