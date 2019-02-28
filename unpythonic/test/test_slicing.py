# -*- coding: utf-8 -*-
"""Operations on sequences, with native slice syntax. Syntactic sugar, pure Python."""

from itertools import repeat

from ..slicing import fup, view, islice
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

    # writable view for sequences
    # (when you want to be more imperative than Python allows)
    lst = [1, 2, 3, 4, 5]
    v = view(lst)[2:4]
    v[:] = [10, 20]
    assert lst == [1, 2, 10, 20, 5]

    lst = [1, 2, 3, 4, 5]
    v = view(lst)
    v[2:4] = [10, 20]
    assert lst == [1, 2, 10, 20, 5]

    # slice syntax wrapper for itertools.islice
    p = primes()
    assert tuple(islice(p)[10:15]) == (31, 37, 41, 43, 47)

    assert tuple(islice(primes())[10:15]) == (31, 37, 41, 43, 47)

    p = primes()
    assert islice(p)[10] == 31

    odds = islice(s(1, 2, ...))[::2]
    assert tuple(islice(odds)[:5]) == (1, 3, 5, 7, 9)
    assert tuple(islice(odds)[:5]) == (11, 13, 15, 17, 19)  # five more

    print("All tests PASSED")

if __name__ == '__main__':
    test()
