# -*- coding: utf-8 -*-

from ..syntax import macros, test, test_raises  # noqa: F401
from .fixtures import testset, returns_normally

from ..gtco import gtco, gtrampolined

from ..it import last, take

def runtests():
    with testset("unpythonic.gtco"):
        with testset("basic usage"):
            # basic usage:
            def march():
                yield 1
                yield 2
                return march()  # tail-chain to a new instance of itself
            test[tuple(take(6, gtco(march()))) == (1, 2, 1, 2, 1, 2)]
            test[returns_normally(last(take(10000, gtco(march()))))]  # no crash

            def ones():
                yield 1
                return ones()
            test[tuple(take(10, gtco(ones()))) == (1,) * 10]
            test[returns_normally(last(take(10000, gtco(ones()))))]  # no crash

        with testset("@gtrampolined"):
            # using decorator:
            @gtrampolined
            def ones2():
                yield 1
                return ones2()
            test[tuple(take(10, ones2())) == (1,) * 10]
            test[returns_normally(last(take(10000, ones2())))]  # no crash

            @gtrampolined
            def ranges():
                yield from range(10)
                return range(10, 20)  # can tail-chain into any iterable
            test[tuple(ranges()) == tuple(range(20))]

if __name__ == '__main__':
    runtests()
