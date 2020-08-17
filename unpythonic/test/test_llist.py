# -*- coding: utf-8 -*-

from ..syntax import macros, test, test_raises  # noqa: F401
from .fixtures import testset

from pickle import dumps, loads

from ..llist import (cons, car, cdr, nil, ll, llist,
                     caar, cdar, cadr, cddr, caddr, cdddr,
                     member, lreverse, lappend, lzip,
                     BinaryTreeIterator, JackOfAllTradesIterator)

from ..fold import foldl, foldr

def runtests():
    # TODO: extend the automatic tests for the `unpythonic.llist` module
    with testset("unpythonic.llist"):
        with testset("cons, car, cdr"):
            c = cons(1, 2)
            test[car(c) == 1]
            test[cdr(c) == 2]

            with test_raises(TypeError, "cons cells should be immutable"):
                c.car = 3

            test[cons(1, 2) == cons(1, 2)]
            test[cons(1, 2) != cons(2, 3)]

        with testset("ll"):
            test[ll(1, 2, 3) == cons(1, cons(2, cons(3, nil)))]
            # print(ll(1, 2, cons(3, 4), 5, 6))  # a list may also contain pairs as items
            # print(cons(cons(cons(nil, 3), 2), 1))  # improper list

            test[ll(1, 2, 3) == ll(1, 2, 3)]
            test[ll(1, 2) != ll(1, 2, 3)]

            # cons structures are immutable (because cons cells are),
            # but new instances based on existing ones are ok.
            l1 = ll(3, 2, 1)
            l2 = cons(4, l1)
            test[l1 == ll(3, 2, 1)]
            test[l2 == ll(4, 3, 2, 1)]
            l3 = cons(6, cdr(l1))
            test[l3 == ll(6, 2, 1)]

            thebinarytree = cons(cons(1, 2), cons(3, 4))

        with testset("repr"):
            test[repr(cons(1, 2)) == "cons(1, 2)"]
            test[repr(ll(1, 2, 3)) == "ll(1, 2, 3)"]
            test[repr(thebinarytree) == "cons(cons(1, 2), cons(3, 4))"]

            test[cons(1, 2).lispyrepr() == "(1 . 2)"]
            test[ll(1, 2, 3).lispyrepr() == "(1 2 3)"]
            test[thebinarytree.lispyrepr() == "((1 . 2) . (3 . 4))"]

        with testset("deeper accessors"):
            q = ll(cons(1, 2), cons(3, 4))  # list of pairs, not a tree!
            test[[f(q) for f in [caar, cdar, cadr, cddr]] == [1, 2, cons(3, 4), nil]]

            mylinkedlist = ll(1, 2, 3)
            test[[f(mylinkedlist) for f in [car, cadr, caddr, cdddr, cdr, cddr]] == [1, 2, 3, nil, ll(2, 3), ll(3)]]

        with testset("member (lispy membership test function)"):
            test[member(2, mylinkedlist) == ll(2, 3)]
            test[not member(5, mylinkedlist)]

        with testset("type conversions"):
            thetuple = (1, 2, 3)
            thelist = [1, 2, 3]
            thelinkedlist = ll(1, 2, 3)
            test[list(thelinkedlist) == thelist]
            test[tuple(thelinkedlist) == thetuple]
            test[llist(thetuple) == thelinkedlist]
            test[llist(thelist) == thelinkedlist]
            test[list(nil) == []]
            test[tuple(nil) == ()]

        with testset("hashability"):
            # independently constructed instances with the same data should hash the same.
            test[hash(cons(1, 2)) == hash(cons(1, 2))]
            test[hash(ll(1, 2, 3)) == hash(ll(1, 2, 3))]

            s = set()
            s.add(cons(1, 2))
            s.add(ll(1, 2, 3))
            test[cons(1, 2) in s]
            test[ll(1, 2, 3) in s]
            test[cons(3, 4) not in s]
            test[ll(1, 2) not in s]

        with testset("binary tree"):
            test[[f(thebinarytree) for f in [caar, cdar, cadr, cddr]] == [1, 2, 3, 4]]
            test[tuple(BinaryTreeIterator(thebinarytree)) == (1, 2, 3, 4)]  # non-default iteration scheme
            test_raises[TypeError, tuple(thebinarytree)]  # binary tree should not be iterable as a linked list

        # generic iterator that understands both linked lists and binary trees
        with testset("JackOfAllTradesIterator (generic)"):
            test[tuple(JackOfAllTradesIterator(ll(1, 2, 3, 4))) == (1, 2, 3, 4)]
            test[tuple(JackOfAllTradesIterator(thebinarytree)) == (1, 2, 3, 4)]
            test[tuple(JackOfAllTradesIterator(cons(1, 2))) == (1, 2)]  # a single cons is a degenerate binary tree

            nested_linked_lists = ll(ll(1, 2), ll(3, 4))
            test[tuple(JackOfAllTradesIterator(nested_linked_lists)) == (1, 2, 3, 4)]  # flattens nested lists
            test[tuple(nested_linked_lists) == (ll(1, 2), ll(3, 4))]

            c = ll(cons(1, 2), cons(3, 4))
            test[tuple(JackOfAllTradesIterator(c)) == (1, 2, 3, 4)]
            test[tuple(c) == (cons(1, 2), cons(3, 4))]

            t2 = cons(cons(1, nil), cons(2, nil))
            test[tuple(BinaryTreeIterator(t2)) == (1, nil, 2, nil)]
            test[tuple(JackOfAllTradesIterator(t2)) == (1, 2)]  # skips nil in any cdr slot for list compatibility

            t2 = cons(cons(nil, 1), cons(nil, 2))
            test[tuple(BinaryTreeIterator(t2)) == (nil, 1, nil, 2)]
            test[tuple(JackOfAllTradesIterator(t2)) == (nil, 1, nil, 2)]  # but doesn't skip nil in the car slot

        with testset("long linked list"):
            test[tuple(JackOfAllTradesIterator(llist(range(10000)))) == tuple(range(10000))]  # no crash
            test[tuple(BinaryTreeIterator(llist(range(10000)))) == tuple(range(10000)) + (nil,)]  # no crash

        with testset("sequence unpacking syntax"):
            left, right = cons(1, 2)
            test[left == 1 and right == 2]

            a, b, c = ll(1, 2, 3)
            test[a == 1 and b == 2 and c == 3]

            # unpacking a binary tree
            a, b, c, d = BinaryTreeIterator(thebinarytree)
            test[a == 1 and b == 2 and c == 3 and d == 4]

        with testset("lzip"):
            test[tuple(zip(ll(1, 2, 3), ll(4, 5, 6))) == ((1, 4), (2, 5), (3, 6))]
            test[lzip(ll(1, 2, 3), ll(4, 5, 6)) == ll(ll(1, 4), ll(2, 5), ll(3, 6))]

        with testset("lappend"):
            test[lappend(ll(1, 2, 3), ll(4, 5, 6)) == ll(1, 2, 3, 4, 5, 6)]
            test[lappend(ll(1, 2), ll(3, 4), ll(5, 6)) == ll(1, 2, 3, 4, 5, 6)]

        with testset("lreverse"):
            test[lreverse(ll(1, 2, 3)) == ll(3, 2, 1)]

        with testset("other ways to reverse a linked list"):
            test[llist(reversed(ll(1, 2, 3))) == ll(3, 2, 1)]
            test[foldl(cons, nil, ll(1, 2, 3)) == ll(3, 2, 1)]

            # implementation detail to avoid extra reverses (performance implications, so test it)
            r = reversed(ll(1, 2, 3))   # an iterator that internally builds the reversed list...
            test[llist(r) is r._data]   # ...which llist should just grab

            # foldr implicitly reverses the input
            test[foldr(cons, nil, ll(1, 2, 3)) == ll(1, 2, 3)]

        with testset("pickling"):
            mylinkedlist = ll(1, 2, 3)
            k = loads(dumps(mylinkedlist))
            # Should iterate without crashing, since upon unpickling, the pickled nil singleton
            # translates to our nil singleton.
            #
            # (Remember `pickle` doesn't save class definitions; what it saves is that there
            #  was a reference to `unpythonic.llist.nil`, which was an instance of a class named
            #  `unpythonic.llist.Nil`. Unpickling will re-create the saved `nil` instance by
            #  calling `Nil.__new__` and then loading the instance data into it. In this case,
            #  `Nil.__new__` just returns the singleton instance already created for the current
            #  session, and there's no instance data to load.)
            test[tuple(k) == (1, 2, 3)]

if __name__ == '__main__':
    runtests()
