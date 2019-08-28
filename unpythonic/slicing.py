# -*- coding: utf-8 -*-
"""Operations on sequences with native slice syntax. Syntactic sugar, pure Python."""

__all__ = ["islice", "fup"]

from itertools import islice as islicef

from .fup import fupdate
from .it import first, lastn, butlastn
from .misc import CountingIterator

def islice(iterable):
    """Use itertools.islice with slice syntax, with some bonus features.

    Usage::

        islice(iterable)[idx_or_slice]

    For convenience:

      - Negative ``start``, ``stop`` are supported. **CAUTION**: using a negative
        start or stop will force the iterable, because that is the only way to
        know its length.

      - A single index (negative also allowed) is interpreted as a length-1
        islice starting at that index. The slice is then immediately evaluated
        and the item is returned.

    Once negative indices have been handled, the slicing variant calls
    ``itertools.islice`` with the corresponding slicing parameters.

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

    **CAUTION**: Keep in mind the slicing process consumes elements from the
    iterable.

    **CAUTION**: ``step``, if present, must be positive.
    """
    # manually curry to take indices later, but expect them in subscript syntax to support slicing
    class islice1:
        """Subscript me to perform the slicing."""
        def __getitem__(self, k):
            if isinstance(k, tuple):
                raise TypeError("multidimensional indexing not supported, got {}".format(k))
            if isinstance(k, slice):
                start, stop, step = k.start, k.stop, k.step
                it = iter(iterable)
                # One or both of start and stop may be negative or None.
                # Step must be positive; filter first, then slice normally.
                #
                # A general iterable doesn't know its length (might not even be
                # knowable; it may be a generator), so if we get a negative
                # start or stop, the only way to find the correct position is
                # to force the iterable until it ends (if ever).
                if start and start < 0 and stop and stop < 0:
                    it = butlastn(-stop, lastn(-start, iterable))
                    start = stop = None
                elif start and start < 0:
                    n, start = -start, None
                    if not stop:
                        it = lastn(n, iterable)
                    else:  # stop and stop > 0:
                        # to adjust stop, we must know how many items are dropped
                        cit = CountingIterator(iterable)
                        it = tuple(lastn(n, cit))  # force to actually count (note lastn stores only <= n items)
                        n_dropped = max(0, cit.count - n)  # max needed if start is past the start of iterable
                        stop -= n_dropped
                        assert stop >= 0
                elif stop and stop < 0:
                    it = butlastn(-stop, iterable)
                    stop = None
                return islicef(it, start, stop, step)
            if k < 0:
                return first(lastn(-k, iterable))
            return first(islicef(iterable, k, k + 1))
    return islice1()

# Basic idea, no negative index support:
# def islice(iterable):
#     class islice1:
#         """Subscript me to perform the slicing."""
#         def __getitem__(self, k):
#             if isinstance(k, tuple):
#                 raise TypeError("multidimensional indexing not supported, got {}".format(k))
#             if isinstance(k, slice):
#                 return islicef(iterable, k.start, k.stop, k.step)
#             return first(islicef(iterable, k, k + 1))
#     return islice1()

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
