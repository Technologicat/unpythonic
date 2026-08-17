# -*- coding: utf-8 -*-
"""The macros pass through Python 3.15's new comprehension unpacking (PEP 798).

These tests require Python 3.15+ because the unpacking syntax won't parse on
earlier versions.

`lazify`, `autocurry`, `tco` and `continuations` have no comprehension-specific
handling, so the new forms reach their generic paths. Two shapes are new there: a
`Starred` in the element position of a list/set/generator comprehension, and a
`DictComp` whose `value` is `None` because the mapping expression sits in `key`.

**These test semantics, not just values.** A test that only checked results would
pass even if `lazify` had quietly gone strict inside the new forms, or `autocurry`
had stopped currying there — which is exactly the way this could break without
anyone noticing. So each macro is exercised for the property that makes it that
macro: laziness by leaving a `1 / 0` unevaluated, currying by partially applying,
TCO by recursing deeper than the stack allows, and continuations by capturing one.

TODO: Merge into the per-macro test modules when the floor bumps to Python 3.15+.
"""

from ...syntax import macros, test, test_raises, the  # noqa: F401
from ...test.fixtures import session, testset

from ...syntax import macros, lazify, autocurry, tco, continuations, call_cc  # noqa: F401, F811


def _pair(k):
    return [k, k]


def _mapping(k):
    return {k: k}


with lazify:
    def _first(a, b):
        return a

    def lazy_starred_list(ks):
        # If laziness holds, `1 / 0` is never evaluated.
        return [*_first(_pair(k), 1 / 0) for k in ks]

    def lazy_starred_set(ks):
        return {*_first(_pair(k), 1 / 0) for k in ks}

    def lazy_starred_genexpr(ks):
        return list((*_first(_pair(k), 1 / 0) for k in ks))

    def lazy_dict_unpacking(ks):
        return {**_first(_mapping(k), 1 / 0) for k in ks}

    def lazy_ordinary_dictcomp(ks):
        # Control: the `k: v` form uses the `value` field the unpacking form leaves empty.
        return {k: _first(_pair(k), 1 / 0) for k in ks}


with autocurry:
    def _add3(a, b, c):
        return a + b + c

    def curried_starred_list(ks):
        return [*[_add3(1)(2)(k)] for k in ks]

    def curried_dict_unpacking(ks):
        return {**{k: _add3(1, 2)(k)} for k in ks}


with tco:
    def tco_deep_recursion(n, acc):
        """Recurses deeper than the stack allows, so it only completes under TCO."""
        if n <= 0:
            return acc
        items = [*_pair(n) for _ in (1,)]
        return tco_deep_recursion(n - 1, acc + len(items))

    def tco_dict_unpacking(ks):
        return {**_mapping(k) for k in ks}


with continuations:
    def _ident(x):
        return x

    def cc_starred_list(ks):
        x = call_cc[_ident(ks)]
        return [*_pair(k) for k in x]

    def cc_dict_unpacking(ks):
        x = call_cc[_ident(ks)]
        return {**_mapping(k) for k in x}


def runtests():
    with testset("lazify keeps its laziness inside the new comprehension forms"):
        # Reaching a value at all means the unused `1 / 0` argument was never forced.
        test[lazy_starred_list([1, 2]) == [1, 1, 2, 2]]
        test[lazy_starred_set([1, 2]) == {1, 2}]
        test[lazy_starred_genexpr([1, 2]) == [1, 1, 2, 2]]
        test[lazy_dict_unpacking([1, 2]) == {1: 1, 2: 2}]
        test[lazy_ordinary_dictcomp([1, 2]) == {1: [1, 1], 2: [2, 2]}]

    with testset("autocurry still curries inside the new comprehension forms"):
        # Partial application, so a value comes back only if currying happened.
        test[curried_starred_list([1, 2]) == [4, 5]]
        test[curried_dict_unpacking([1, 2]) == {1: 4, 2: 5}]

    with testset("tco still optimizes a tail call whose body uses the new forms"):
        # 5000 frames deep; without TCO this is a RecursionError.
        test[tco_deep_recursion(5000, 0) == 10000]
        test[tco_dict_unpacking([1, 2]) == {1: 1, 2: 2}]

    with testset("continuations survive the new comprehension forms"):
        test[cc_starred_list([1, 2]) == [1, 1, 2, 2]]
        test[cc_dict_unpacking([1, 2]) == {1: 1, 2: 2}]


if __name__ == '__main__':  # pragma: no cover
    with session(__file__):
        runtests()
