# -*- coding: utf-8 -*-

from ..llist import cons, car, cdr, nil, ll, llist, \
                    caar, cdar, cadr, cddr, caddr, cdddr, \
                    member, lreverse, lappend, lzip, \
                    BinaryTreeIterator, JackOfAllTradesIterator

from ..fold import foldl, foldr

def test():
    # TODO: extend tests

    c = cons(1, 2)
    assert car(c) == 1 and cdr(c) == 2

    assert ll(1, 2, 3) == cons(1, cons(2, cons(3, nil)))
#    print(ll(1, 2, cons(3, 4), 5, 6))  # a list may also contain pairs as items
#    print(cons(cons(cons(nil, 3), 2), 1))  # improper list

    # type conversion
    tpl = (1, 2, 3)
    lst = [1, 2, 3]
    llst = ll(1, 2, 3)
    assert list(llst) == lst
    assert tuple(llst) == tpl
    assert llist(tpl) == llst
    assert llist(lst) == llst
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

    # generic iterator that understands both linked lists and trees
    assert tuple(JackOfAllTradesIterator(ll(1, 2, 3, 4))) == (1, 2, 3, 4)
    assert tuple(JackOfAllTradesIterator(t)) == (1, 2, 3, 4)

    c = ll(cons(1, 2), cons(3, 4))
    assert tuple(JackOfAllTradesIterator(c)) == (1, 2, 3, 4)
    assert tuple(c) == (cons(1, 2), cons(3, 4))

    t2 = cons(cons(1, nil), cons(2, nil))
    assert tuple(BinaryTreeIterator(t2)) == (1, nil, 2, nil)
    assert tuple(JackOfAllTradesIterator(t2)) == (1, 2)  # skips nil in any cdr slot for list compatibility

    t2 = cons(cons(nil, 1), cons(nil, 2))
    assert tuple(BinaryTreeIterator(t2)) == (nil, 1, nil, 2)
    assert tuple(JackOfAllTradesIterator(t2)) == (nil, 1, nil, 2)  # but doesn't skip nil in the car slot

    assert tuple(JackOfAllTradesIterator(llist(range(10000)))) == tuple(range(10000))  # no crash

    # repr
    assert repr(cons(1, 2)) == "cons(1, 2)"
    assert repr(ll(1, 2, 3)) == "ll(1, 2, 3)"
    assert repr(t) == "cons(cons(1, 2), cons(3, 4))"
    assert cons(1, 2).lispyrepr() == "(1 . 2)"
    assert ll(1, 2, 3).lispyrepr() == "(1 2 3)"
    assert t.lispyrepr() == "((1 . 2) . (3 . 4))"

    q = ll(cons(1, 2), cons(3, 4))  # list of pairs, not a tree!
    assert [f(q) for f in [caar, cdar, cadr, cddr]] == [1, 2, cons(3, 4), nil]

    l = ll(1, 2, 3)
    assert [f(l) for f in [car, cadr, caddr, cdddr, cdr, cddr]] == [1, 2, 3, nil, ll(2, 3), ll(3)]
    assert member(2, l) == ll(2, 3)
    assert not member(5, l)

    # sequence unpacking syntax
    l, r = cons(1, 2)
    assert l == 1 and r == 2

    a, b, c = ll(1, 2, 3)
    assert a == 1 and b == 2 and c == 3

    # unpacking a binary tree
    a, b, c, d = BinaryTreeIterator(t)
    assert a == 1 and b == 2 and c == 3 and d == 4

    assert lreverse(ll(1, 2, 3)) == ll(3, 2, 1)

    assert lappend(ll(1, 2, 3), ll(4, 5, 6)) == ll(1, 2, 3, 4, 5, 6)
    assert lappend(ll(1, 2), ll(3, 4), ll(5, 6)) == ll(1, 2, 3, 4, 5, 6)

    assert tuple(zip(ll(1, 2, 3), ll(4, 5, 6))) == ((1, 4), (2, 5), (3, 6))
    assert lzip(ll(1, 2, 3), ll(4, 5, 6)) == ll(ll(1, 4), ll(2, 5), ll(3, 6))

    from pickle import dumps, loads
    l = ll(1, 2, 3)
    k = loads(dumps(l))
    # should iterate without crashing, since the nil is refreshed.
    assert tuple(k) == (1, 2, 3)

    # cons structures are immutable (because cons cells are),
    # but new instances based on existing ones are ok.
    l1 = ll(3, 2, 1)
    l2 = cons(4, l1)
    assert l1 == ll(3, 2, 1)
    assert l2 == ll(4, 3, 2, 1)
    l3 = cons(6, cdr(l1))
    assert l3 == ll(6, 2, 1)

    # hashability
    s = set()
    s.add(cons(1, 2))
    s.add(ll(1, 2, 3))
    assert cons(1, 2) in s
    assert ll(1, 2, 3) in s
    assert cons(3, 4) not in s
    assert ll(1, 2) not in s

    # reverse
    assert llist(reversed(ll(1, 2, 3))) == ll(3, 2, 1)
    assert foldl(cons, nil, ll(1, 2, 3)) == ll(3, 2, 1)

    # implementation detail to avoid extra reverses
    r = reversed(ll(1, 2, 3))   # an iterator that internally builds the reversed list...
    assert llist(r) is r._data  # ...which llist should just grab

    # foldr implicitly reverses the input
    assert foldr(cons, nil, ll(1, 2, 3)) == ll(1, 2, 3)

    print("All tests PASSED")

if __name__ == '__main__':
    test()
