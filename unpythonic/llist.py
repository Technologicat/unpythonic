#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Cons and friends."""

from abc import ABCMeta, abstractmethod
from itertools import zip_longest

from unpythonic.fun import composer1
from unpythonic.it import foldr, foldl

# explicit list better for tooling support
_exports = ["cons", "nil",
            "LinkedListIterator", "TailIterator", "BinaryTreeIterator", "ConsIterator",
            "car", "cdr",
            "caar", "cadr", "cdar", "cddr",
            "caaar", "caadr", "cadar", "caddr", "cdaar", "cdadr", "cddar", "cdddr",
            "caaaar", "caaadr", "caadar", "caaddr", "cadaar", "cadadr", "caddar", "cadddr",
            "cdaaar", "cdaadr", "cdadar", "cdaddr", "cddaar", "cddadr", "cdddar", "cddddr",
            "ll", "ll_from_sequence", "lreverse", "lappend", "lzip"]
#from itertools import product, repeat
#_ads = lambda n: product(*repeat("ad", n))
#_c2r = ["c{}{}r".format(*x) for x in _ads(2)]
#_c3r = ["c{}{}{}r".format(*x) for x in _ads(3)]
#_c4r = ["c{}{}{}{}r".format(*x) for x in _ads(4)]
#_exports.extend(_c2r)
#_exports.extend(_c3r)
#_exports.extend(_c4r)
__all__ = _exports

# Singleton, but we need the class and instance name to be separate so that we
# can correctly unpickle cons structures, which use a different nil instance
# (from an earlier session).
class Nil:
    # support the iterator protocol so we can say tuple(nil) --> ()
    def __iter__(self):
        return self
    def __next__(self):
        raise StopIteration()
    def __repr__(self):
        return "nil"
nil = Nil()

class ConsIterator(metaclass=ABCMeta):
    """Abstract base class for iterators operating on cons cells.

    Can be used to define your own walking strategies for custom structures
    built out of cons cells.

    ``startcell`` is the cons cell to start in (will be checked it is a cons),
    and ``walker`` is a generator function (i.e. not started yet) that yields
    the data in the desired order.

    Basically all a derived class needs to do is define a walker and then call
    ``super().__init__(startcell, walker)``.

    For usage examples see the predefined iterators in ``unpythonic.llist``.
    """
    @abstractmethod
    def __init__(self, startcell, walker):
        if not isinstance(startcell, cons):
            raise TypeError("Expected a cons, got {} with value {}".format(type(startcell), startcell))
        self.walker = walker(startcell)
    def __iter__(self):
        return self
    def __next__(self):
        return next(self.walker)

class LinkedListIterator(ConsIterator):
    """Iterator for linked lists built from cons cells."""
    def __init__(self, head, _fullerror=True):
        def walker(head):
            cell = head
            while cell is not nil:
                yield cell.car
                if isinstance(cell.cdr, cons) or cell.cdr is nil:
                    cell = cell.cdr
                elif cell is head:
                    yield cell.cdr
                    break
                else:
                    if _fullerror:
                        raise TypeError("Not a linked list or a single cons cell: {}".format(head))
                    else:  # avoid infinite loop in cons.__repr__
                        raise TypeError("Not a linked list or a single cons cell")
        super().__init__(head, walker)

class TailIterator(ConsIterator):  # for member()
    """Like LinkedListIterator, but yield successive tails (cdr, cddr, ...).

    Example::

        TailIterator(ll(1, 2, 3)) --> ll(1, 2, 3), ll(2, 3), ll(3)
    """
    def __init__(self, head):
        def walker(head):
            cell = head
            while cell is not nil:
                yield cell  # tail of list from this cell on
                if isinstance(cell.cdr, cons) or cell.cdr is nil:
                    cell = cell.cdr
                else:
                    raise TypeError("Not a linked list or a single cons cell: {}".format(head))
        super().__init__(head, walker)

class BinaryTreeIterator(ConsIterator):
    """Iterator for binary trees built from cons cells."""
    def __init__(self, root):
        def walker(cell):
            for x in (cell.car, cell.cdr):
                if isinstance(x, cons):
                    yield from walker(x)
                else:
                    yield x
        super().__init__(root, walker)

class cons:
    """Cons cell a.k.a. pair. Immutable, like in Racket.

    Iterable. Default is to iterate as a linked list.
    """
    def __init__(self, v1, v2):
        self.car = v1
        self.cdr = v2
        self._immutable = True
    def __setattr__(self, k, v):
        if hasattr(self, "_immutable"):
            raise TypeError("'cons' object does not support item assignment")
        super().__setattr__(k, v)
    def __setstate__(self, state):  # pickle support
        # Upon unpickling, refresh any "nil" instances to point to the
        # current nil singleton, so that "c.car is nil" and "c.cdr is nil"
        # work as expected.
        for k in ("car", "cdr"):
            if isinstance(state[k], Nil):
                state[k] = nil
        self.__dict__ = state
    def __iter__(self):
        return LinkedListIterator(self)
    def __repr__(self):
        try:  # duck test linked list
            result = (str(x) for x in LinkedListIterator(self, _fullerror=False))
        except TypeError:
            result = (repr(self.car), ".", repr(self.cdr))
        return "({})".format(" ".join(result))
    def __eq__(self, other):
        if isinstance(other, cons):
            try:  # duck test linked lists
                ia, ib = (LinkedListIterator(x) for x in (self, other))
                fill = object()  # essentially gensym
                for a, b in zip_longest(ia, ib, fillvalue=fill):
                    if a != b:
                        return False
                return True
            except TypeError:
                return self.car == other.car and self.cdr == other.cdr
        return False
    def __hash__(self):
        return hash((hash(self.car), hash(self.cdr)))

def car(x):
    """Return the first half of a cons cell."""
    if not isinstance(x, cons):
        raise TypeError("Expected a cons, got {} with value {}".format(type(x), x))
    return x.car
def cdr(x):
    """Return the second half of a cons cell."""
    if not isinstance(x, cons):
        raise TypeError("Expected a cons, got {} with value {}".format(type(x), x))
    return x.cdr

caar = composer1(car, car)
cadr = composer1(car, cdr)
cdar = composer1(cdr, car)
cddr = composer1(cdr, cdr)

caaar = composer1(car, car, car)
caadr = composer1(car, car, cdr)
cadar = composer1(car, cdr, car)
caddr = composer1(car, cdr, cdr)
cdaar = composer1(cdr, car, car)
cdadr = composer1(cdr, car, cdr)
cddar = composer1(cdr, cdr, car)
cdddr = composer1(cdr, cdr, cdr)

caaaar = composer1(car, car, car, car)
caaadr = composer1(car, car, car, cdr)
caadar = composer1(car, car, cdr, car)
caaddr = composer1(car, car, cdr, cdr)
cadaar = composer1(car, cdr, car, car)
cadadr = composer1(car, cdr, car, cdr)
caddar = composer1(car, cdr, cdr, car)
cadddr = composer1(car, cdr, cdr, cdr)
cdaaar = composer1(cdr, car, car, car)
cdaadr = composer1(cdr, car, car, cdr)
cdadar = composer1(cdr, car, cdr, car)
cdaddr = composer1(cdr, car, cdr, cdr)
cddaar = composer1(cdr, cdr, car, car)
cddadr = composer1(cdr, cdr, car, cdr)
cdddar = composer1(cdr, cdr, cdr, car)
cddddr = composer1(cdr, cdr, cdr, cdr)

def ll(*elts):
    """Pack elts to a linked list."""
    return ll_from_sequence(elts)

def ll_from_sequence(sequence):
    """Convert sequence to a linked list."""
    return foldr(cons, nil, sequence)

def lreverse(l):
    """Reverse a linked list."""
    return foldl(cons, nil, l)

def lappend(*ls):
    """Append linked lists left-to-right."""
    def lappend_two(l1, l2):
        return foldr(cons, l2, tuple(l1))  # tuple() because foldr needs a sequence
    return foldr(lappend_two, nil, ls)

def member(x, l):
    """Walk linked list and check if item x is in it.

    Returns:
        The matching cons cell (tail of list) if x was found; False if not.
    """
    it = TailIterator(l)
    for t in it:
        if t.car == x:
            return t
    return False

def lzip(*ls):
    """Zip linked lists, producing a linked list of linked lists.

    Built-in zip() works too, but produces tuples.
    """
    return ll(*map(ll, *ls))

def test():
    # TODO: extend tests

    c = cons(1, 2)
    assert car(c) == 1 and cdr(c) == 2

    assert ll(1, 2, 3) == cons(1, cons(2, cons(3, nil)))
#    print(ll(1, 2, cons(3, 4), 5, 6))  # a list may also contain pairs as items
#    print(cons(cons(cons(nil, 3), 2), 1))  # improper list

    # type conversion
    lst = ll(1, 2, 3)
    assert list(lst) == [1, 2, 3]
    assert tuple(lst) == (1, 2, 3)
    assert ll_from_sequence((1, 2, 3)) == lst
    assert tuple(nil) == ()

    # equality
    assert cons(1, 2) == cons(1, 2)
    assert cons(1, 2) != cons(2, 3)
    assert ll(1, 2, 3) == ll(1, 2, 3)
    assert ll(1, 2) != ll(1, 2, 3)

    # independently constructed instances with the same data should hash the same.
    assert hash(cons(1, 2)) == hash(cons(1, 2))
    assert hash(ll(1, 2, 3)) == hash(ll(1, 2, 3))

    try:
        c = cons(1, 2)
        c.car = 3
    except TypeError:
        pass
    else:
        assert False, "cons cells should be immutable"

    t = cons(cons(1, 2), cons(3, 4))  # binary tree
    assert [f(t) for f in [caar, cdar, cadr, cddr]] == [1, 2, 3, 4]
    assert tuple(BinaryTreeIterator(t)) == (1, 2, 3, 4)  # non-default iteration scheme
    try:
        tuple(t)
    except TypeError:
        pass
    else:
        assert False, "binary tree should not be iterable as a linked list"

    q = ll(cons(1, 2), cons(3, 4))  # list of pairs, not a tree!
    assert [f(q) for f in [caar, cdar, cadr, cddr]] == [1, 2, cons(3, 4), nil]

    l = ll(1, 2, 3)
    assert [f(l) for f in [car, cadr, caddr, cdddr, cdr, cddr]] == [1, 2, 3, nil, ll(2, 3), ll(3)]
    assert member(2, l) == ll(2, 3)
    assert not member(5, l)

    # tuple unpacking syntax
    l, r = cons(1, 2)
    assert l == 1 and r == 2

    a, b, c = ll(1, 2, 3)
    assert a == 1 and b == 2 and c == 3

    assert lreverse(ll(1, 2, 3)) == ll(3, 2, 1)

    assert lappend(ll(1, 2, 3), ll(4, 5, 6)) == ll(1, 2, 3, 4, 5, 6)
    assert lappend(ll(1, 2), ll(3, 4), ll(5, 6)) == ll(1, 2, 3, 4, 5, 6)

    assert tuple(zip(ll(1, 2, 3), ll(4, 5, 6))) == ((1, 4), (2, 5), (3, 6))
    assert lzip(ll(1, 2, 3), ll(4, 5, 6)) == ll(ll(1, 4), ll(2, 5), ll(3, 6))

    from pickle import dumps, loads
    l = ll(1, 2, 3)
    k = loads(dumps(l))
    # should iterate without crashing, since the nil is converted.
    assert tuple(k) == (1, 2, 3)

    print("All tests PASSED")

if __name__ == '__main__':
    test()
