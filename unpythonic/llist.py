#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Cons and friends."""

#from itertools import product, repeat

from unpythonic.misc import call
from unpythonic.fun import composer1, foldr, foldl

# TODO: reload this module in init
# TCO implementation switchable at runtime
import unpythonic.rc
if unpythonic.rc._tco_impl == "exc":
    from unpythonic.tco import SELF, jump, trampolined, _jump
elif unpythonic.rc._tco_impl == "fast":
    from unpythonic.fasttco import SELF, jump, trampolined, _jump
else:
    raise ValueError("Unknown TCO implementation '{}'".format(unpythonic.rc._tco_impl))

# explicit list better for tooling support
_exports = ["cons", "nil",
            "car", "cdr",
            "caar", "cadr", "cdar", "cddr",
            "caaar", "caadr", "cadar", "caddr", "cdaar", "cdadr", "cddar", "cdddr",
            "caaaar", "caaadr", "caadar", "caaddr", "cadaar", "cadadr", "caddar", "cadddr",
            "cdaaar", "cdaadr", "cdadar", "cdaddr", "cddaar", "cddadr", "cdddar", "cddddr",
            "ll", "ll_from_sequence", "lreverse", "lappend", "lzip"]
#_ads = lambda n: product(*repeat("ad", n))
#_c2r = ["c{}{}r".format(*x) for x in _ads(2)]
#_c3r = ["c{}{}{}r".format(*x) for x in _ads(3)]
#_c4r = ["c{}{}{}{}r".format(*x) for x in _ads(4)]
#_exports.extend(_c2r)
#_exports.extend(_c3r)
#_exports.extend(_c4r)
__all__ = _exports

@call  # make a singleton
class nil:
    def tolist(self):  # for completeness, since cons cells have it
        return []
    def __repr__(self):
        return "nil"

class ConsIterator:
    """Iterator for linked lists built from cons cells."""
    def __init__(self, startcell):
        if not isinstance(startcell, cons):
            raise TypeError("Expected a cons, got {} with value {}".format(type(startcell), startcell))
        self.lastread = None
        self.cell = startcell
    def __iter__(self):
        return self
    def __next__(self):
        if not self.lastread:
            self.lastread = "car"
            return self.cell.car
        elif self.lastread == "car":
            if isinstance(self.cell.cdr, cons):  # linked list, general case
                self.cell = self.cell.cdr
                self.lastread = "car"
                return self.cell.car
            elif self.cell.cdr is nil:           # linked list, last cell
                raise StopIteration()
            else:                                # just a pair
                self.lastread = "cdr"
                return self.cell.cdr
        elif self.lastread == "cdr":
            raise StopIteration()
        else:
            assert False, "Invalid value for self.lastread '{}'".format(self.lastread)

class cons:
    """Cons cell a.k.a. pair. Immutable, like in Racket."""
    def __init__(self, v1, v2):
        self.car = v1
        self.cdr = v2
        self._immutable = True
    def __setattr__(self, k, v):
        if hasattr(self, "_immutable"):
            raise AttributeError("Assignment to immutable cons cell not allowed")
        super().__setattr__(k, v)
    def __iter__(self):
        return ConsIterator(self)
    def tolist(self):
        return [x for x in self]  # implicitly using __iter__
    def __repr__(self):
        # special lispy printing for linked lists
        # TODO: refactor this
        @trampolined
        def ll_repr(cell, acc):
            newacc = lambda: acc + [repr(cell.car)]  # delay evaluation with lambda
            if cell.cdr is nil:
                return newacc()
            elif isinstance(cell.cdr, cons):
                return jump(SELF, cell.cdr, newacc())
            else:
                return False  # not a linked list
        result = ll_repr(self, []) or [repr(self.car), ".", repr(self.cdr)]
        return "({})".format(" ".join(result))
    # TODO: trampoline this
    def __eq__(self, other):
        return car(self) == car(other) and cdr(self) == cdr(other)
    # TODO: __hash__ et al.?

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
        return foldr(cons, l2, l1.tolist())  # .tolist() because must be a sequence
    return foldr(lappend_two, nil, ls)

# TODO: refactor this
@trampolined
def member(x, l):
    """Walk linked list and check if item x is in it.

    Returns:
        The matching cons cell if x was found; False if not.
    """
    if not isinstance(l, cons):
        raise TypeError("Expected a cons, got {} with value {}".format(type(x), x))
    if not isinstance(l.cdr, cons) and l.cdr is not nil:
        raise ValueError("This cons is not a linked list; current cell {}".format(l))
    if l.car == x:      # match
        return l
    elif l.cdr is nil:  # last cell, no match
        return False
    else:
        return jump(SELF, x, l.cdr)

def lzip(*ls):
    """Zip linked lists, producing a linked list of linked lists.

    Built-in zip() works too, but produces tuples.
    """
    return ll(*map(ll, *ls))

def test():
    # TODO: extend tests

    try:
        c = cons(1, 2)
        c.car = 3  # immutable cons cell, should fail
    except AttributeError:
        pass
    else:
        assert False

    c = cons(1, 2)
    assert car(c) == 1 and cdr(c) == 2

    assert ll(1, 2, 3) == cons(1, cons(2, cons(3, nil)))
#    print(ll(1, 2, cons(3, 4), 5, 6))  # a list may also contain pairs as items
#    print(cons(cons(cons(nil, 3), 2), 1))  # improper list

    t = cons(cons(1, 2), cons(3, 4))  # binary tree
    assert [f(t) for f in [caar, cdar, cadr, cddr]] == [1, 2, 3, 4]

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

    assert ll(1, 2, 3).tolist() == [1, 2, 3]
    assert ll_from_sequence((1, 2, 3)) == ll(1, 2, 3)

    assert lreverse(ll(1, 2, 3)) == ll(3, 2, 1)

    assert lappend(ll(1, 2, 3), ll(4, 5, 6)) == ll(1, 2, 3, 4, 5, 6)
    assert lappend(ll(1, 2), ll(3, 4), ll(5, 6)) == ll(1, 2, 3, 4, 5, 6)

    assert tuple(zip(ll(1, 2, 3), ll(4, 5, 6))) == ((1, 4), (2, 5), (3, 6))
    assert lzip(ll(1, 2, 3), ll(4, 5, 6)) == ll(ll(1, 4), ll(2, 5), ll(3, 6))

    print("All tests PASSED")

if __name__ == '__main__':
    test()
