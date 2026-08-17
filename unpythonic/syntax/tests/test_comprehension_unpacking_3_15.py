# -*- coding: utf-8 -*-
"""The macros pass through Python 3.15's new comprehension unpacking (PEP 798).

These tests require Python 3.15+ because the unpacking syntax won't parse on
earlier versions.

`lazify`, `autocurry` and `tco` have no comprehension-specific handling, so the
new forms reach their generic paths. Two shapes are new there: a `Starred` in the
element position of a list/set/generator comprehension, and a `DictComp` whose
`value` is `None` because the mapping expression sits in `key` instead.

The hazard worth guarding against is specific to `lazify`: if it wrapped the
starred value in a promise, `*promise` would fail at unpacking. It does not, and
these tests are here to keep it that way — the existing suite cannot catch a
regression here, since nothing else in it contains this syntax.

TODO: Merge into the per-macro test modules when the floor bumps to Python 3.15+.
"""

from ...syntax import macros, test, the  # noqa: F401
from ...test.fixtures import session, testset

from ...syntax import macros, lazify, autocurry, tco  # noqa: F401, F811


def _items(k):
    return [k, k]


def _mapping(k):
    return {k: k}


with lazify:
    def lazy_starred_list(ks):
        return [*_items(k) for k in ks]

    def lazy_starred_set(ks):
        return {*_items(k) for k in ks}

    def lazy_starred_genexpr(ks):
        return list((*_items(k) for k in ks))

    def lazy_dict_unpacking(ks):
        return {**_mapping(k) for k in ks}

    def lazy_ordinary_dictcomp(ks):
        return {k: _items(k) for k in ks}


with autocurry:
    def curried_starred_list(ks):
        return [*_items(k) for k in ks]

    def curried_dict_unpacking(ks):
        return {**_mapping(k) for k in ks}


with tco:
    def tco_starred_list(ks):
        return [*_items(k) for k in ks]

    def tco_dict_unpacking(ks):
        return {**_mapping(k) for k in ks}


def runtests():
    with testset("lazify: starred comprehension elements"):
        test[lazy_starred_list([1, 2]) == [1, 1, 2, 2]]
        test[lazy_starred_set([1, 2]) == {1, 2}]
        test[lazy_starred_genexpr([1, 2]) == [1, 1, 2, 2]]

    with testset("lazify: dict-unpacking comprehension"):
        test[lazy_dict_unpacking([1, 2]) == {1: 1, 2: 2}]
        # Control: the `k: v` form goes through the `value` field the unpacking
        # form leaves empty, so this catches a fix that skipped that field.
        test[lazy_ordinary_dictcomp([1, 2]) == {1: [1, 1], 2: [2, 2]}]

    with testset("autocurry: new comprehension forms"):
        test[curried_starred_list([1, 2]) == [1, 1, 2, 2]]
        test[curried_dict_unpacking([1, 2]) == {1: 1, 2: 2}]

    with testset("tco: new comprehension forms"):
        test[tco_starred_list([1, 2]) == [1, 1, 2, 2]]
        test[tco_dict_unpacking([1, 2]) == {1: 1, 2: 2}]


if __name__ == '__main__':  # pragma: no cover
    with session(__file__):
        runtests()
