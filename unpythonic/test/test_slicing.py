# -*- coding: utf-8 -*-
"""Operations on sequences, with native slice syntax. Syntactic sugar, pure Python."""

from itertools import repeat

from ..slicing import fup, islice
from ..mathseq import primes, s

def test():
    # functional update for sequences
    # (when you want to be more functional than Python allows)
    lst = (1, 2, 3, 4, 5)
    assert fup(lst)[3] << 42 == (1, 2, 3, 42, 5)
    assert fup(lst)[0::2] << tuple(repeat(10, 3)) == (10, 2, 10, 4, 10)
    assert fup(lst)[1::2] << tuple(repeat(10, 3)) == (1, 10, 3, 10, 5)
    assert fup(lst)[::2] << tuple(repeat(10, 3)) == (10, 2, 10, 4, 10)
    assert fup(lst)[::-1] << tuple(range(5)) == (4, 3, 2, 1, 0)
    assert lst == (1, 2, 3, 4, 5)

    # slice syntax wrapper for itertools.islice
    p = primes()
    assert tuple(islice(p)[10:15]) == (31, 37, 41, 43, 47)

    assert tuple(islice(primes())[10:15]) == (31, 37, 41, 43, 47)

    p = primes()
    assert islice(p)[10] == 31

    odds = islice(s(1, 2, ...))[::2]
    assert tuple(islice(odds)[:5]) == (1, 3, 5, 7, 9)
    assert tuple(islice(odds)[:5]) == (11, 13, 15, 17, 19)  # five more

    # negative start, stop in islice
    #
    # !! step must be positive !!
    #
    # CAUTION: will force the iterable (at the latest at the time when the
    # first item is read from it), since that's the only way to know where it
    # ends, if at all.
    assert tuple(islice(range(10))[-3:]) == (7, 8, 9)       # start < 0, no stop
    assert tuple(islice(range(10))[-3:9]) == (7, 8)         # start < 0, stop > 0, before end
    assert tuple(islice(range(10))[-2:10]) == (8, 9)        # start < 0, stop > 0, at end
    assert tuple(islice(range(10))[-2:20]) == (8, 9)        # start < 0, stop > 0, beyond end

    assert tuple(islice(range(10))[:-8]) == (0, 1)          # no start, stop < 0
    assert tuple(islice(range(10))[6:-2]) == (6, 7)         # start > 0, stop < 0
    assert tuple(islice(range(10))[10:-2]) == ()            # start > 0, at end, stop < 0
    assert tuple(islice(range(10))[20:-2]) == ()            # start > 0, beyond end, stop < 0

    assert tuple(islice(range(10))[-8:-4]) == (2, 3, 4, 5)  # start < 0, stop < 0

    assert tuple(islice(range(10))[-6::2]) == (4, 6, 8)     # step
    assert tuple(islice(range(10))[:-2:2]) == (0, 2, 4, 6)  # step
    assert tuple(islice(range(10))[-8:-2:3]) == (2, 5)      # step

    # edge cases, should behave like list does
    assert tuple(islice(range(10))[:-20]) == ()                # stop < 0, past the start of the iterable
    assert tuple(islice(range(10))[-20:]) == tuple(range(10))  # start < 0, past the start of the iterable
    assert tuple(islice(range(10))[-20:5]) == tuple(range(5))  # same, but with stop > 0

    print("All tests PASSED")

if __name__ == '__main__':
    test()
