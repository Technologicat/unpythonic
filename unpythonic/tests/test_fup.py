# -*- coding: utf-8 -*-

from ..syntax import macros, test, test_raises, the  # noqa: F401
from ..test.fixtures import session, testset

from itertools import count, repeat
from collections import namedtuple

from ..fup import fupdate, fupdate_in_to, fupdate_in_with
from ..collections import frozendict, view
from ..env import env
from ..gmemo import imemoize

def runtests():
    with testset("mutable sequence"):
        lst = [1, 2, 3]
        out = fupdate(lst, 1, 42)
        test[lst == [1, 2, 3]]
        test[out == [1, 42, 3]]
        test[type(out) is type(lst)]

    with testset("immutable sequence"):
        tup = (1, 2, 3, 4, 5)
        out = fupdate(tup, slice(1, 5, 2), tuple(repeat(10, 2)))
        test[tup == (1, 2, 3, 4, 5)]
        test[out == (1, 10, 3, 10, 5)]
        test[type(out) is type(tup)]
        test[the[fupdate(tup)] == the[tup]]  # no indices, no bindings --> copy

    with testset("namedtuple"):
        A = namedtuple("A", "p q")
        a = A(17, 23)
        out = fupdate(a, 0, 42)
        test[a == A(17, 23)]
        test[out == A(42, 23)]
        test[the[type(out)] is the[type(a)]]

    with testset("mutable mapping"):
        d1 = {'foo': 'bar', 'fruit': 'apple'}
        d2 = fupdate(d1, foo='tavern')
        test[sorted(d1.items()) == [('foo', 'bar'), ('fruit', 'apple')]]
        test[sorted(d2.items()) == [('foo', 'tavern'), ('fruit', 'apple')]]
        test[the[type(d2)] is the[type(d1)]]

    with testset("immutable mapping (unpythonic.collections.frozendict)"):
        d3 = frozendict({'a': 1, 'b': 2})
        d4 = fupdate(d3, a=23)
        test[the[d4['a']] == 23 and the[d4['b']] == 2]
        test[d3['a'] == 1]
        test[the[type(d4)] is the[type(d3)]]

    with testset("negative index"):
        lst = [1, 2, 3]
        out = fupdate(lst, -1, 42)
        test[lst == [1, 2, 3]]
        test[out == [1, 2, 42]]

    with testset("no start index"):
        tup = (1, 2, 3, 4, 5)
        out = fupdate(tup, slice(None, 5, 2), tuple(repeat(10, 3)))
        test[tup == (1, 2, 3, 4, 5)]
        test[out == (10, 2, 10, 4, 10)]

    with testset("no stop index"):
        tup = (1, 2, 3, 4, 5)
        out = fupdate(tup, slice(1, None, 2), tuple(repeat(10, 2)))
        test[tup == (1, 2, 3, 4, 5)]
        test[out == (1, 10, 3, 10, 5)]

    with testset("no start or stop index, just step"):
        tup = (1, 2, 3, 4, 5)
        out = fupdate(tup, slice(None, None, 2), tuple(repeat(10, 3)))
        test[tup == (1, 2, 3, 4, 5)]
        test[out == (10, 2, 10, 4, 10)]

    with testset("just step, backwards"):
        tup = (1, 2, 3, 4, 5)
        out = fupdate(tup, slice(None, None, -1), tuple(range(5)))
        test[tup == (1, 2, 3, 4, 5)]
        test[out == (4, 3, 2, 1, 0)]

        out = fupdate(tup, slice(None, None, -1), range(5))  # no tuple() needed
        test[out == (4, 3, 2, 1, 0)]

    with testset("multiple individual items"):
        tup = (1, 2, 3, 4, 5)
        out = fupdate(tup, (1, 2, 3), (17, 23, 42))
        test[tup == (1, 2, 3, 4, 5)]
        test[out == (1, 17, 23, 42, 5)]

    with testset("multiple slices and sequences"):
        tup = tuple(range(10))
        out = fupdate(tup, (slice(0, 10, 2), slice(1, 10, 2)),
                      (tuple(repeat(2, 5)), tuple(repeat(3, 5))))
        test[tup == tuple(range(10))]
        test[out == (2, 3, 2, 3, 2, 3, 2, 3, 2, 3)]

    with testset("infinite replacement"):
        tup = (1, 2, 3, 4, 5)
        out = fupdate(tup, slice(None, None, None), repeat(42))
        test[out == (42, 42, 42, 42, 42)]

        tup = (1, 2, 3, 4, 5)
        out = fupdate(tup, slice(None, None, None), count(start=10))
        test[out == (10, 11, 12, 13, 14)]

    with testset("memoized infinite replacement, reading its start backwards"):
        tup = (1, 2, 3, 4, 5)
        out = fupdate(tup, slice(None, None, -1), imemoize(repeat(42))())
        test[out == (42, 42, 42, 42, 42)]

        tup = (1, 2, 3, 4, 5)
        out = fupdate(tup, slice(None, None, -1), imemoize(count(start=10))())
        test[out == (14, 13, 12, 11, 10)]

    with testset("mix and match"):
        tup = tuple(range(10))
        out = fupdate(tup, (slice(0, 10, 2), slice(1, 10, 2), 6),
                      (tuple(repeat(2, 5)), tuple(repeat(3, 5)), 42))
        test[tup == tuple(range(10))]
        test[out == (2, 3, 2, 3, 2, 3, 42, 3, 2, 3)]

    with testset("error cases"):
        with test_raises[IndexError, "should detect replacement sequence too short"]:
            tup = (1, 2, 3, 4, 5)
            out = fupdate(tup, slice(1, None, 2), (10,))  # need 2 items, have 1

        # cannot specify both indices and bindings
        test_raises[ValueError, fupdate(tup, slice(1, None, 2), (10,), somename="some value")]

        # not memoized, cannot read a general iterable backwards
        tup = (1, 2, 3, 4, 5)
        test_raises[IndexError, fupdate(tup, slice(None, None, -1), count(start=10))]

    # fupdate_in_to: functional update of one item at a path. The rules for taking a step and rebuilding an
    # immutable container are shared with `mogrify_in_with`, and tested there; what is tested here is that
    # nothing is mutated, and that what is off the path is shared.
    with testset("fupdate_in_to"):
        with testset("the input is not mutated"):
            d1 = {"devices": {"tts": {"device": "cpu"}, "stt": {"device": "cpu"}}}
            d2 = fupdate_in_to(d1, ("devices", "tts", "device"), "cuda:0")
            test[d1 == {"devices": {"tts": {"device": "cpu"}, "stt": {"device": "cpu"}}}]
            test[d2 == {"devices": {"tts": {"device": "cuda:0"}, "stt": {"device": "cpu"}}}]

        with testset("containers on the path are copies, and everything off it is shared"):
            d1 = {"devices": {"tts": {"device": "cpu"}, "stt": {"device": "cpu"}}}
            d2 = fupdate_in_to(d1, ("devices", "tts", "device"), "cuda:0")
            test[the[d2] is not the[d1]]
            test[the[d2["devices"]] is not the[d1["devices"]]]
            test[the[d2["devices"]["tts"]] is not the[d1["devices"]["tts"]]]
            test[the[d2["devices"]["stt"]] is the[d1["devices"]["stt"]]]

            e1 = env(x=env(y=21), z=[1, 2])
            e2 = fupdate_in_to(e1, ("x", "y"), 42)
            test[e1.x.y == 21]
            test[e2.x.y == 42]
            test[type(e2) is env]
            test[the[e2.z] is the[e1.z]]

        with testset("immutable containers along the path"):
            A = namedtuple("A", "p q")
            lst = [A(1, 2), A(3, 4)]
            out = fupdate_in_to(lst, (1, "q"), 42)
            test[out == [A(1, 2), A(3, 42)]]
            test[lst == [A(1, 2), A(3, 4)]]

            fd = frozendict(a=(1, 2))
            out = fupdate_in_to(fd, ("a", -1), 42)
            test[out == frozendict(a=(1, 42))]
            test[fd == frozendict(a=(1, 2))]

        with testset("fupdate_in_with"):
            d1 = {"stats": {"count": 1}}
            d2 = fupdate_in_with(d1, ("stats", "count"), lambda x: x + 1)
            test[d1 == {"stats": {"count": 1}}]
            test[d2 == {"stats": {"count": 2}}]

        with testset("error cases"):
            test_raises[KeyError, fupdate_in_to({}, ("nonexistent",), 42)]
            test_raises[TypeError, fupdate_in_to({"ab": 1}, "ab", 42)]  # a string is not a path

            # A copy of a view would still write through to the sequence it views.
            lst = [1, 2, 3]
            test_raises[TypeError, fupdate_in_to(view(lst), (0,), 42)]
            test[lst == [1, 2, 3]]

if __name__ == '__main__':  # pragma: no cover
    with session(__file__):
        runtests()
