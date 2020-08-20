# -*- coding: utf-8 -*-
"""Cons and friends.

Hashable, pickleable, hooks into the built-in reversed(), can print like in Lisps.
"""

from abc import ABCMeta, abstractmethod
from collections.abc import Iterable, Iterator
from itertools import zip_longest

from .fun import composer1i
from .fold import foldr, foldl
from .it import rev
from .singleton import Singleton
# from .symbol import gensym

# explicit list better for tooling support
_exports = ["cons", "nil",
            "LinkedListIterator", "LinkedListOrCellIterator", "TailIterator",
            "BinaryTreeIterator", "ConsIterator",
            "car", "cdr",
            "caar", "cadr", "cdar", "cddr",
            "caaar", "caadr", "cadar", "caddr", "cdaar", "cdadr", "cddar", "cdddr",
            "caaaar", "caaadr", "caadar", "caaddr", "cadaar", "cadadr", "caddar", "cadddr",
            "cdaaar", "cdaadr", "cdadar", "cdaddr", "cddaar", "cddadr", "cdddar", "cddddr",
            "ll", "llist", "lreverse", "lappend", "lzip"]
#from itertools import product, repeat
#_ads = lambda n: product(*repeat("ad", n))
#_c2r = ["c{}{}r".format(*x) for x in _ads(2)]
#_c3r = ["c{}{}{}r".format(*x) for x in _ads(3)]
#_c4r = ["c{}{}{}{}r".format(*x) for x in _ads(4)]
#_exports.extend(_c2r)
#_exports.extend(_c3r)
#_exports.extend(_c4r)
__all__ = _exports

class Nil(Singleton):
    """The empty linked list. Singleton."""
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
        self.walker = iter(walker(startcell))  # iter() needed to support gtrampolined generators
    def __iter__(self):
        return self
    def __next__(self):
        return next(self.walker)
Iterable.register(ConsIterator)
Iterator.register(ConsIterator)

class LinkedListIterator(ConsIterator):
    """Iterator for linked lists built from cons cells."""
    def __init__(self, head, _fullerror=True):
        def walker(head):
            cell = head
            while cell is not nil:
                yield cell.car
                if isinstance(cell.cdr, cons) or cell.cdr is nil:
                    cell = cell.cdr
                else:
                    if _fullerror:
                        raise TypeError("Not a linked list: {}".format(head))
                    else:  # avoid infinite loop in cons.__repr__
                        raise TypeError("Not a linked list")
        super().__init__(head, walker)

class LinkedListReverseIterator(LinkedListIterator):
    """Iterator for walking a linked list backwards.

    Computes the reversed list at init time, so it can then be walked forward.
    Cost O(n).
    """
    def __init__(self, head, _fullerror=True):
        self._data = lreverse(head)
        super().__init__(self._data, _fullerror)

class LinkedListOrCellIterator(ConsIterator):
    """Like LinkedListIterator, but allow also a single cons cell.

    Default iteration strategy. Useful for sequence unpacking of cons and ll.
    """
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
                    else:  # avoid infinite loop in cons.__repr__ (it uses LinkedListIterator, though)  # pragma: no cover
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
                    raise TypeError("Not a linked list: {}".format(head))
        super().__init__(head, walker)

class BinaryTreeIterator(ConsIterator):
    """Iterator for binary trees built from cons cells."""
    def __init__(self, root):
        #        def walker(cell):  # FP, call stack overflow for deep trees
        #            for x in (cell.car, cell.cdr):
        #                if isinstance(x, cons):
        #                    yield from walker(x)
        #                else:
        #                    yield x
        def walker(cell):  # imperative, no call stack overflow (we keep our own data stack instead)
            stack = [cell]
            while stack:
                cell = stack.pop()
                a, d = cell.car, cell.cdr
                ac, dc = isinstance(a, cons), isinstance(d, cons)
                if not ac:
                    yield a
                if not dc:
                    yield d
                if dc:
                    stack.append(d)
                if ac:
                    stack.append(a)  # LIFO
        super().__init__(root, walker)

class JackOfAllTradesIterator(ConsIterator):
    """Iterator that supports both binary trees and linked lists.

    **CAUTION**: *jack of all trades*, because:

        - To handle trees correctly, this iterator descends into any cons cell
          contained in the input, **also in the car half**. This implies that
          **nested linked lists will be flattened**.

        - To handle list termination correctly, whenever the **cdr half**
          contains a ``nil``, it will be omitted from the output. This implies
          that for a tree which contains ``nil`` entries, **some** of those
          ``nil`` may be missing from the output.

    If you want the ace for a particular trade, use the specific iterator for
    the specific kind of cons structure you have.
    """
    def __init__(self, root):
        #        @gtrampolined
        #        def walker(cell):  # FP, tail-recursive in the cdr half only
        #            if isinstance(cell.car, cons):
        #                yield from walker(cell.car)
        #            else:
        #                yield cell.car
        #            if isinstance(cell.cdr, cons):
        #                return walker(cell.cdr)  # signal gtrampolined to tail-chain
        #            elif cell.cdr is not nil:
        #                yield cell.cdr
        def walker(cell):
            stack = [cell]
            while stack:
                cell = stack.pop()
                a, d = cell.car, cell.cdr
                ac, dc = isinstance(a, cons), isinstance(d, cons)
                if not ac:
                    yield a
                if not dc and d is not nil:
                    yield d
                if dc:
                    stack.append(d)
                if ac:
                    stack.append(a)  # LIFO
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
    def __iter__(self):
        """Return iterator with default iteration scheme: single cell or list."""
        return LinkedListOrCellIterator(self)
    def __reversed__(self):
        """For lists. Caution: O(n), works by building a reversed list."""
        return LinkedListReverseIterator(self)
    def __repr__(self):
        """Representation in pythonic notation.

        Suitable for ``eval`` if all elements are."""
        try:  # duck test linked list (true list only, no single-cell pair)
            # listcomp, not genexpr, since we want to trigger any exceptions **now**.
            result = [repr(x) for x in LinkedListIterator(self, _fullerror=False)]
            return "ll({})".format(", ".join(result))
        except TypeError:
            result = (repr(self.car), repr(self.cdr))
            return "cons({})".format(", ".join(result))
    def lispyrepr(self):  # TODO: maybe rename or alias this to `__str__`?
        """Representation in Lisp-like dot notation."""
        try:
            result = [repr(x) for x in LinkedListIterator(self, _fullerror=False)]
        except TypeError:
            r = lambda obj: obj.lispyrepr() if hasattr(obj, "lispyrepr") else repr(obj)
            result = (r(self.car), ".", r(self.cdr))
        return "({})".format(" ".join(result))
    def __eq__(self, other):
        if other is self:
            return True
        if isinstance(other, cons):
            try:  # duck test linked lists
                ia, ib = (LinkedListIterator(x) for x in (self, other))
                fill = object()  # gensym("fill"), but object() is much faster, and we don't need a label, or pickle support.
                for a, b in zip_longest(ia, ib, fillvalue=fill):
                    if a != b:
                        return False
                return True
            except TypeError:
                return self.car == other.car and self.cdr == other.cdr
        return False
    def __hash__(self):
        try:  # duck test linked list
            tpl = tuple(LinkedListIterator(self))
        except TypeError:
            tpl = (self.car, self.cdr)
        return hash(tpl)

def _car(x):
    return _typecheck(x).car
def _cdr(x):
    return _typecheck(x).cdr
def _typecheck(x):
    if not isinstance(x, cons):
        raise TypeError("Expected a cons, got {} with value {}".format(type(x), x))
    return x
def _build_accessor(name):
    spec = name[1:-1]
    f = {'a': _car, 'd': _cdr}
    return composer1i(f[char] for char in spec)

def car(x):
    """Return the first half of a cons cell."""
    return _car(x)
def cdr(x):
    """Return the second half of a cons cell."""
    return _cdr(x)

caar = _build_accessor("caar")
cadr = _build_accessor("cadr")
cdar = _build_accessor("cdar")
cddr = _build_accessor("cddr")

caaar = _build_accessor("caaar")
caadr = _build_accessor("caadr")
cadar = _build_accessor("cadar")  # look, it's Darth Cadar!
caddr = _build_accessor("caddr")
cdaar = _build_accessor("cdaar")
cdadr = _build_accessor("cdadr")
cddar = _build_accessor("cddar")
cdddr = _build_accessor("cdddr")

caaaar = _build_accessor("caaaar")
caaadr = _build_accessor("caaadr")
caadar = _build_accessor("caadar")
caaddr = _build_accessor("caaddr")
cadaar = _build_accessor("cadaar")
cadadr = _build_accessor("cadadr")
caddar = _build_accessor("caddar")
cadddr = _build_accessor("cadddr")
cdaaar = _build_accessor("cdaaar")
cdaadr = _build_accessor("cdaadr")
cdadar = _build_accessor("cdadar")
cdaddr = _build_accessor("cdaddr")
cddaar = _build_accessor("cddaar")
cddadr = _build_accessor("cddadr")
cdddar = _build_accessor("cdddar")
cddddr = _build_accessor("cddddr")

def ll(*elts):
    """Make a linked list with the given elements.

    ``ll(...)`` plays the same role as ``[...]`` or ``(...)`` for lists or tuples,
    respectively, but for linked lists. See also ``llist``.

    **NOTE**: The returned data type is ``cons``, there is no ``ll`` type.
    A linked list is just one kind of structure that can be built out of cons cells.

    Equivalent to ``(list ...)`` in Lisps. Since in Python the name ``list``
    refers to the builtin dynamic array type, we use the name ``ll``.
    """
    return llist(elts)

def llist(iterable):
    """Make a linked list from iterable.

    ``llist(...)`` plays the same role as ``list(...)`` or ``tuple(...)`` for
    lists or tuples, respectively, but for linked lists. See also ``ll``.

    **NOTE**: The returned data type is ``cons``, there is no ``llist`` type.
    A linked list is just one kind of structure that can be built out of cons cells.

    **Efficiency**:

    Because cons appends to the front, this is efficient for:

      - ``reversed(some_linked_list)``, by just returning the already computed
        reversed list that is internally stored by the reverse-iterator.

      - Sequences, since they can be walked backwards; a linear walk is enough.

    For a general iterable input, this costs a linear walk (forwards),
    plus an ``lreverse``.
    """
    if isinstance(iterable, LinkedListReverseIterator):
        # avoid two extra reverses by reusing the internal data.
        return iterable._data
    return lreverse(rev(iterable))

def lreverse(iterable):
    """Reverse an iterable, loading the result into a linked list.

    If you have a linked list and want an iterator instead, use ``reversed(l)``.
    The computational cost is the same in both cases, O(n).
    """
    return foldl(cons, nil, iterable)

def lappend(*ls):
    """Append the given linked lists left-to-right."""
    def lappend_two(l1, l2):
        return foldr(cons, l2, l1)
    return foldr(lappend_two, nil, ls)

def member(x, l):
    """Walk linked list l and check if item x is in it.

    Returns:
        The matching cons cell (tail of l) if x was found; False if not.
    """
    for t in TailIterator(l):
        if t.car == x:
            return t
    return False

def lzip(*ls):
    """Zip linked lists, producing a linked list of linked lists.

    Built-in zip() works too, but produces tuples.
    """
    return llist(map(ll, *ls))
