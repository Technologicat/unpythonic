# -*- coding: utf-8 -*-

from ..gtco import gtco, gtrampolined

from ..it import last, take

def runtests():
    # basic usage:
    def march():
        yield 1
        yield 2
        return march()  # tail-chain to a new instance of itself
    assert tuple(take(6, gtco(march()))) == (1, 2, 1, 2, 1, 2)
    last(take(10000, gtco(march())))  # no crash

    def ones():
        yield 1
        return ones()
    assert tuple(take(10, gtco(ones()))) == (1,) * 10
    last(take(10000, gtco(ones())))  # no crash

    # using decorator:
    @gtrampolined
    def ones2():
        yield 1
        return ones2()
    assert tuple(take(10, ones2())) == (1,) * 10
    last(take(10000, ones2()))  # no crash

    @gtrampolined
    def ranges():
        yield from range(10)
        return range(10, 20)  # can tail-chain into any iterable
    assert tuple(ranges()) == tuple(range(20))

    print("All tests PASSED")

if __name__ == '__main__':
    runtests()
