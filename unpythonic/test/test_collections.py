# -*- coding: utf-8 -*-

from ..syntax import macros, test, test_raises  # noqa: F401
from .fixtures import session, testset

from collections.abc import Mapping, MutableMapping, Hashable, Container, Iterable, Sized
from pickle import dumps, loads
import threading

from ..collections import (box, ThreadLocalBox, Some, Shim, unbox,
                           frozendict, view, roview, ShadowedSequence, mogrify,
                           in_slice, index_in_slice)
from ..fold import foldr
from ..llist import cons, ll

def runtests():
    # These are useful for building sequence-handling tools that work with slices.
    with testset("slice index queries"):
        test[in_slice(5, slice(10))]
        test[in_slice(5, 5)]  # convenience: int instead of a slice
        test[in_slice(5, slice(1, 10, 2))]
        test[not in_slice(5, slice(0, 10, 2))]

        test[index_in_slice(5, slice(10)) == 5]
        test[index_in_slice(5, slice(1, 10, 2)) == 2]

        # - sequence length parameter
        # - default start and stop
        test[in_slice(5, slice(None, 10, 1))]
        test[in_slice(5, slice(0, None, 1), 10)]
        test[in_slice(5, slice(None, None, 1), 10)]
        # - negative indices (allowed when sequence length is known)
        test[in_slice(8, slice(0, None, 1), 10)]
        test[in_slice(-2, slice(0, None, 1), 10)]
        test[in_slice(9, 9, 10)]  # convenience
        test[in_slice(-1, -1, 10)]
        # Just like in regular slice syntax in Python, to walk a sequence
        # backwards until we reach its first element requires using `None`
        # as `stop`. Trying `slice(-1, -1, -1)` gives an empty slice,
        # because -1 refers to the last element also when it appears
        # in the `stop` position.
        test[not in_slice(0, slice(9, -1, -1), 10)]  # empty slice
        test[in_slice(0, slice(9, None, -1), 10)]  # stop=None; ok!
        test[in_slice(7, slice(None, None, -1), 10)]
        test[in_slice(-3, slice(None, None, -1), 10)]
        test[in_slice(7, slice(9, None, -1), 10)]
        test[in_slice(-3, slice(9, None, -1), 10)]

        # Given an index to the original sequence, convert it to the
        # corresponding index inside the given slice. Return `None` if the
        # given index is not in the slice.
        test[index_in_slice(-1, slice(10), 10) == 9]
        test[index_in_slice(-1, slice(None, None, -1), 10) == 0]
        test[index_in_slice(7, slice(None, None, -2), 10) == 1]
        test[index_in_slice(-3, slice(None, None, -2), 10) == 1]
        test[index_in_slice(6, slice(None, None, -2), 10) is None]  # original index 6 not in this slice

        test_raises[TypeError, in_slice("not an index", slice(10))]
        test_raises[TypeError, in_slice(5, "not a slice or int")]
        test_raises[TypeError, in_slice(1, slice(10), "not a length")]
        test_raises[IndexError, in_slice(5, slice(0, None, 1), 3)]  # out of range when length = 3
        test_raises[ValueError, in_slice(1, slice(10), -3)]  # negative sequence length

        test_raises[ValueError, in_slice(1, slice(0, None, 0))]  # zero step
        test_raises[ValueError, in_slice(1, slice(0, None, 1))]  # missing length for default stop with positive step
        test_raises[ValueError, in_slice(1, slice(None, None, -1))]  # missing length for default start with negative step
        test_raises[ValueError, in_slice(-1, slice(10))]  # missing length to interpret negative indices

    # box: mutable single-item container à la Racket
    with testset("box"):
        b = box(17)
        def f(b):
            b.x = 23
        test[b.x == 17]
        f(b)
        test[b.x == 23]

        b2 = box(17)
        test[17 in b2]
        test[23 not in b2]
        test[[x for x in b2] == [17]]
        test[b2 == 17]  # for convenience, a box is considered equal to the item it contains
        test[len(b2) == 1]
        test[b2 != b]

        b3 = box(17)
        test[b3 == b2]  # boxes are considered equal if their contents are

        # pretty API: unbox(b) is the same as reading b.x
        cat = object()
        b4 = box(cat)
        test[b4 is not cat]  # the box is not the cat
        test[unbox(b4) is cat]  # but when you look inside the box, you find the cat

        test_raises[TypeError, unbox(42)]  # unbox should accept only boxes

        # b.set(newvalue) is the same as assigning b.x = newvalue
        # (but like env.set, it's an expression, so you can use it anywhere)
        dog = object()
        b4.set(dog)
        test[unbox(b4) is dog]

        # syntactic sugar for assignment
        b4 << cat  # same as b4.set(cat)
        test[unbox(b4) is cat]

        with test_raises(TypeError, "box is mutable, should not be hashable"):
            d = {}
            d[b] = "foo"

        # ABCs
        test[not issubclass(box, Hashable)]
        test[issubclass(box, Container)]
        test[issubclass(box, Iterable)]
        test[issubclass(box, Sized)]

        b1 = box("abcdefghijklmnopqrstuvwxyzåäö")
        b2 = loads(dumps(b1))  # pickling
        test[b2 == b1]

    # ThreadLocalBox: like box, but with thread-local contents
    with testset("ThreadLocalBox"):
        tlb = ThreadLocalBox(42)
        test[unbox(tlb) == 42]
        def test_threadlocalbox_worker():
            tlb << 17  # Send an object to the box *for this thread*.
            test[unbox(tlb) == 17]
        t = threading.Thread(target=test_threadlocalbox_worker)
        t.start()
        t.join()
        test[unbox(tlb) == 42]  # In the main thread, this box still has the original value.

        test[42 in tlb]
        test[[x for x in tlb] == [42]]
        test[tlb == 42]
        test[len(tlb) == 1]

        tlb2 = ThreadLocalBox(42)
        test[tlb2 is not tlb]
        test[tlb2 == tlb]

        # The default object can be changed.
        tlb = ThreadLocalBox(42)
        # We haven't sent any object to the box, so we see the default object.
        test[unbox(tlb) == 42]
        tlb.setdefault(23)  # change the default
        test[unbox(tlb) == 23]
        tlb << 5                # Send an object to the box *for this thread*.
        test[unbox(tlb) == 5]  # Now we see the object we sent. The default is shadowed.
        def test_threadlocalbox_worker():
            # Since this thread hasn't sent anything into the box yet,
            # we get the current default object.
            test[unbox(tlb) == 23]
            tlb << 17                # But after we send an object into the box...
            test[unbox(tlb) == 17]  # ...that's the object this thread sees.
        t = threading.Thread(target=test_threadlocalbox_worker)
        t.start()
        t.join()
        # In the main thread, this box still has the value the main thread sent there.
        test[unbox(tlb) == 5]
        # But we can still see the default, if we want, by explicitly requesting it.
        test[tlb.getdefault() == 23]
        tlb.clear()              # When we clear the box in this thread...
        test[unbox(tlb) == 23]  # ...this thread sees the current default object again.

    # Some: tell apart thing-ness from nothingness. This container is immutable.
    #
    # The point is being able to tell apart the presence of a `None` value from
    # the absence of a value.
    with testset("Some"):
        s = Some(None)
        test[s is not None]
        test[unbox(s) is None]
        test[None in s]

        s = Some(42)
        test[unbox(s) == 42]
        test[42 in s]
        test_raises[TypeError, s << 23]  # immutable
        test_raises[AttributeError, s.set(23)]

        test[[x for x in s] == [42]]
        test[len(s) == 1]

    # Shim (a.k.a. attribute proxy): redirect attribute accesses.
    #
    # The shim holds a box. Attribute accesses on the shim are redirected
    # to whatever object currently happens to be inside the box.
    with testset("Shim"):
        class TestTarget:
            def __init__(self, x):
                self.x = x
            def getme(self):
                return self.x
        b5 = box(TestTarget(21))
        s = Shim(b5)  # This is modular so we could use a ThreadLocalBox just as well.
        test[hasattr(s, "x")]
        test[hasattr(s, "getme")]
        test[s.x == 21]
        test[s.getme() == 21]
        s.y = "hi from injected attribute"  # We can also add or rebind attributes through the shim.
        test[unbox(b5).y == "hi from injected attribute"]
        s.y = "hi again"
        test[unbox(b5).y == "hi again"]
        b5 << TestTarget(42)  # After we send a different object into the box held by the shim...
        test[s.x == 42]      # ...the shim accesses the new object.
        test[s.getme() == 42]
        test[not hasattr(s, "y")]  # The new TestTarget instance doesn't have "y".

        # Shim can optionally have a fallback object (also boxed).
        #
        # It is used for **read accesses** (`__getattr__`) on attributes that
        # don't exist on the object that is in the primary box.
        def test_fallback():
            class Ex:
                x = "hi from Ex"
            class Wai:
                y = "hi from Wai"
            x, y = [box(obj) for obj in (Ex(), Wai())]
            s = Shim(x, fallback=y)
            test[s.x == "hi from Ex"]
            test[s.y == "hi from Wai"]  # no such attribute on Ex, fallback tried.
            test_raises[AttributeError, s.nonexistent_attribute]  # should error out, this attribute exists neither on Ex nor Wai
            # Attribute writes (binding) always take place on the object in the primary box.
            s.z = "hi from Ex again"
            test[unbox(x).z == "hi from Ex again"]
            test[not hasattr(unbox(y), "z")]
        test_fallback()

        # Shims can be chained using foldr:
        def test_chaining():
            class Ex:
                x = "hi from Ex"
            class Wai:
                x = "hi from Wai"
                y = "hi from Wai"
            class Zee:
                x = "hi from Zee"
                y = "hi from Zee"
                z = "hi from Zee"
            # These will be tried from left to right.
            boxes = [box(obj) for obj in (Ex(), Wai(), Zee())]
            *others, final_fallback = boxes
            s = foldr(Shim, final_fallback, others)  # Shim(box, fallback) <-> op(elt, acc)
            test[s.x == "hi from Ex"]
            test[s.y == "hi from Wai"]
            test[s.z == "hi from Zee"]
        test_chaining()

        test_raises[TypeError, Shim("la la la")]  # not a box, shouldn't be able to Shim it

    # frozendict: immutable dictionary (like frozenset, but for dictionaries)
    with testset("frozendict"):
        d3 = frozendict({'a': 1, 'b': 2})
        test[d3['a'] == 1]
        with test_raises(TypeError, "frozendict is immutable, should not be writable"):
            d3['c'] = 42

        d4 = frozendict(d3, a=42)  # functional update
        test[d4['a'] == 42 and d4['b'] == 2]
        test[d3['a'] == 1]  # original not mutated

        d5 = frozendict({'a': 1, 'b': 2}, {'a': 42})  # rightmost definition of each key wins
        test[d5['a'] == 42 and d5['b'] == 2]

        test[frozendict() is frozendict()]  # empty-frozendict singleton property

        d7 = frozendict({1: 2, 3: 4})
        test[3 in d7]
        test[len(d7) == 2]
        test[set(d7.keys()) == {1, 3}]
        test[set(d7.values()) == {2, 4}]
        test[set(d7.items()) == {(1, 2), (3, 4)}]
        test[d7 == frozendict({1: 2, 3: 4})]
        test[d7 != frozendict({1: 2})]
        test[d7 == {1: 2, 3: 4}]  # like frozenset, __eq__ doesn't care whether mutable or not
        test[d7 != {1: 2}]
        test[{k for k in d7} == {1, 3}]
        test[d7.get(3) == 4]
        test[d7.get(5, 0) == 0]
        test[d7.get(5) is None]

        # ABCs
        test[issubclass(frozendict, Mapping)]
        test[not issubclass(frozendict, MutableMapping)]

        test[issubclass(frozendict, Hashable)]
        test[hash(d7) == hash(frozendict({1: 2, 3: 4}))]
        test[hash(d7) != hash(frozendict({1: 2}))]

        test[issubclass(frozendict, Container)]
        test[issubclass(frozendict, Iterable)]
        test[issubclass(frozendict, Sized)]

        # Pickling tests
        d1 = frozendict({1: 2, 3: 4, "somekey": "somevalue"})
        d2 = loads(dumps(d1))
        test[d2 == d1]

        # We need a test case which has *several* frozendict instances,
        # and also an empty one, to be certain __new__ isn't just returning
        # the global supposed-to-be-empty instance.
        fd1 = frozendict({'a': 1, 'b': 2})
        fd2 = frozendict({'c': 3, 'd': 4})
        fd3 = frozendict()
        data = [fd1, fd2, fd3]
        s = dumps(data)
        o = loads(s)
        test[o == data]

    # writable live view for sequences
    # (when you want to be more imperative than Python allows)
    with testset("view"):
        lst = list(range(5))
        v = view(lst)
        lst[2] = 10
        test[v == [0, 1, 10, 3, 4]]
        test[v[2:] == [10, 3, 4]]
        test[v[2] == 10]
        test[v[::-1] == [4, 3, 10, 1, 0]]
        test[tuple(reversed(v)) == (4, 3, 10, 1, 0)]
        test[10 in v]
        test[42 not in v]
        test[[x for x in v] == [0, 1, 10, 3, 4]]
        test[len(v) == 5]
        test[v.index(10) == 2]
        test[v.count(10) == 1]
        test[v[:] is v]

        # views may be created also of slices (note the syntax: the subscripting is curried)
        lst = list(range(10))
        v = view(lst)[2:]
        test[v == [2, 3, 4, 5, 6, 7, 8, 9]]
        v2 = v[:-2]  # slicing a view returns a new view
        test[v2 == [2, 3, 4, 5, 6, 7]]
        v[3] = 20
        v2[2] = 10
        test[lst == [0, 1, 2, 3, 10, 20, 6, 7, 8, 9]]

        lst = list(range(10))
        v = view(lst)[::2]
        test[v == [0, 2, 4, 6, 8]]
        v2 = v[1:-1]
        test[v2 == [2, 4, 6]]
        v2[1:] = (10, 20)
        test[lst == [0, 1, 2, 3, 10, 5, 20, 7, 8, 9]]

        lst[2] = 42
        test[v == [0, 42, 10, 20, 8]]
        test[v2 == [42, 10, 20]]

        # supports in-place reverse
        lst = list(range(5))
        v = view(lst)
        v.reverse()
        test[lst == [4, 3, 2, 1, 0]]

        lst = list(range(5))
        v = view(lst)
        v[2] = 10
        test[lst == [0, 1, 10, 3, 4]]

        lst = list(range(5))
        v = view(lst)
        v[2:4] = (10, 20)
        test[lst == [0, 1, 10, 20, 4]]

        lst = list(range(5))
        v = view(lst)[2:4]
        v[:] = (10, 20)
        test[lst == [0, 1, 10, 20, 4]]
        test[v[-1] == 20]

        # writing a scalar value into a slice broadcasts it, à la NumPy
        lst = list(range(5))
        v = view(lst)[2:4]
        v[:] = 42
        test[lst == [0, 1, 42, 42, 4]]

        # we store slice specs, not actual indices, so it doesn't matter if the
        # underlying sequence undergoes length changes
        lst = list(range(5))
        v = view(lst)[2:]
        test[v == [2, 3, 4]]
        lst.append(5)
        test[v == [2, 3, 4, 5]]
        lst.insert(0, 42)
        test[v == [1, 2, 3, 4, 5]]
        test[lst == [42, 0, 1, 2, 3, 4, 5]]

        tup = (1, 2, 3, 4, 5)
        test_raises[TypeError, view(tup)]  # tuple is read-only, view is read/write

        lst = list(range(5))
        v = view(lst)[2:]
        with test_raises(TypeError):
            v[2, 3] = 42  # multidimensional indexing not supported
        with test_raises(IndexError):
            v[9001] = 42
        with test_raises(IndexError):
            v[-9001] = 42

    # read-only live view for sequences
    # useful to give read access to a sequence that is an internal detail
    with testset("roview"):
        lst = list(range(5))
        v = roview(lst)[2:]
        test[v == [2, 3, 4]]
        lst.append(5)
        test[v == [2, 3, 4, 5]]  # it's live
        test[type(v[1:]) is roview]  # slicing a read-only view gives another read-only view
        test[v[1:] == [3, 4, 5]]
        test_raises[TypeError, view(v[1:])]  # cannot create a writable view into a read-only view
        with test_raises(TypeError, "read-only view should not support item assignment"):
            v[2] = 3
        test_raises[AttributeError, v.reverse()]  # read-only view does not support in-place reverse

        tup = tuple(range(5))
        v1 = roview(tup)[2:]
        test[v1 == v1]
        v2 = roview(tup)[2:]
        test[v2 is not v1]
        test[v2 == v1]
        v3 = roview(tup)[3:]
        test[v3 != v1]
        v4 = roview(tup)[0:2]
        v5 = roview(tup)[1:3]
        test[v5 != v4]

        tup = tuple(range(5))
        v1 = roview(tup)[2:]
        test_raises[TypeError, v1[2, 3]]  # multidimensional indexing not supported
        test_raises[IndexError, v1[9001]]
        test_raises[IndexError, v1[-9001]]

    # sequence shadowing (like ChainMap, but only two levels, and for sequences, not mappings)
    with testset("ShadowedSequence"):
        tpl = (1, 2, 3, 4, 5)
        s = ShadowedSequence(tpl, 2, 42)
        test[s == (1, 2, 42, 4, 5)]
        test[tpl == (1, 2, 3, 4, 5)]
        test[s[2:] == (42, 4, 5)]

        test_raises[TypeError, s[2, 3]]  # multidimensional indexing not supported
        test_raises[IndexError, s[9001]]
        test_raises[IndexError, s[-9001]]

        s2 = ShadowedSequence(tpl, slice(2, 4), (23, 42))
        test[s2 == (1, 2, 23, 42, 5)]
        test[tpl == (1, 2, 3, 4, 5)]
        test[s2[2:] == (23, 42, 5)]
        test[s2[::-1] == (5, 42, 23, 2, 1)]

        s3 = ShadowedSequence(tpl)
        test[s3 == tpl]

        s4 = ShadowedSequence(s2, slice(3, 5), (100, 200))
        test[s4 == (1, 2, 23, 100, 200)]
        test[s2 == (1, 2, 23, 42, 5)]
        test[tpl == (1, 2, 3, 4, 5)]

        with test_raises(TypeError):
            ShadowedSequence(s4, "la la la", "new value")  # not a valid index specification

        # no-op ShadowedSequence is allowed
        s5 = ShadowedSequence(tpl)
        test[s5[3] == 4]

        s6 = ShadowedSequence(tpl, slice(2, 4), (23,))  # replacement too short...
        test_raises[IndexError, s6[3]]  # ...which is detected here

    # mogrify: in-place map for various data structures (see docstring for details)
    with testset("mogrify"):
        double = lambda x: 2 * x
        lst = [1, 2, 3]
        lst2 = mogrify(double, lst)
        test[lst2 == [2, 4, 6]]
        test[lst2 is lst]

        s = {1, 2, 3}
        s2 = mogrify(double, s)
        test[s2 == {2, 4, 6}]
        test[s2 is s]

        # mogrifying a dict mutates its values in-place, leaving keys untouched
        d = {1: 2, 3: 4, 5: 6}
        d2 = mogrify(double, d)
        test[set(d2.items()) == {(1, 4), (3, 8), (5, 12)}]
        test[d2 is d]

        # dict keys/items/values types cannot be instantiated, and support only
        # iteration (not in-place modification), so in those cases mogrify()
        # returns a new set without mutating the dict's bindings.
        # (But any side effects of func will be applied to each item, as usual,
        #  so the items themselves may change if they are mutable.)
        d = {1: 2, 3: 4, 5: 6}
        test[mogrify(double, d.items()) == {(2, 4), (6, 8), (10, 12)}]  # both keys and values get mogrified!
        test[mogrify(double, d.keys()) == {2, 6, 10}]
        test[mogrify(double, d.values()) == {4, 8, 12}]
        test[d == {1: 2, 3: 4, 5: 6}]

        test[mogrify(double, cons(1, 2)) == cons(2, 4)]
        test[mogrify(double, ll(1, 2, 3)) == ll(2, 4, 6)]

        b = box(17)
        b2 = mogrify(double, b)
        test[b2 == 34]
        test[b2 is b]

        test[mogrify(double, Some(21)) == Some(42)]

        tup = (1, 2, 3)
        tup2 = mogrify(double, tup)
        test[tup2 == (2, 4, 6)]
        test[tup2 is not tup]  # immutable, cannot be updated in-place

        fs = frozenset({1, 2, 3})
        fs2 = mogrify(double, fs)
        test[fs2 == {2, 4, 6}]
        test[fs2 is not fs]

        fd = frozendict({1: 2, 3: 4})
        fd2 = mogrify(double, fd)
        test[set(fd2.items()) == {(1, 4), (3, 8)}]
        test[fd2 is not fd]

        atom = 17
        atom2 = mogrify(double, atom)
        test[atom2 == 34]
        test[atom2 is not atom]

        # mogrify a sequence through a mutable view
        lst = [1, 2, 3]
        v = view(lst)[1:]
        v2 = mogrify(double, v)
        test[v2 == [4, 6]]
        test[lst == [1, 4, 6]]

        # mogrify a copy of a sequence through a read-only view
        lst = [1, 2, 3]
        v = roview(lst)[1:]
        v2 = mogrify(double, v)
        test[v2 == [4, 6]]
        test[lst == [1, 2, 3]]

        # mogrify a thread-local box
        def runtest():
            b = ThreadLocalBox(17)
            def threadtest1():
                mogrify(double, b)
                test[unbox(b) == 34]  # thread-local value affected
            t1 = threading.Thread(target=threadtest1, args=(), kwargs={})
            t1.start()
            t1.join()
            test[unbox(b) == 17]  # value in main thread not affected

            b << 42  # set new contents in main thread only; default value (given at construction time) not changed
            def threadtest2():
                test[unbox(b) == 17]
            t2 = threading.Thread(target=threadtest2, args=(), kwargs={})
            t2.start()
            t2.join()
            test[unbox(b) == 42]
        runtest()

if __name__ == '__main__':  # pragma: no cover
    with session(__file__):
        runtests()
