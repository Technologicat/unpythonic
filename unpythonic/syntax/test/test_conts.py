# -*- coding: utf-8 -*-
"""Continuations (essentially call/cc for Python)."""

from ...syntax import macros, continuations, bind, multilambda, autoreturn, curry

from ...ec import call_ec

def test():
    # basic testing
    with continuations:
        def add1(x, *, cc):
            return 1 + x
        assert add1(2) == 3

        def message(*, cc):
            return ("hello", "there")
        def baz(*, cc):
            with bind[message()] as (m, n):
                return [m, n]
        assert baz() == ["hello", "there"]

        def f(a, b, *, cc):
            return 2*a, 3*b
        assert f(3, 4) == (6, 12)
        x, y = f(3, 4)
        assert x == 6 and y == 12

        def g(a, b, *, cc):
            with bind[f(a, b)] as (x, y):
                return x, y
            print("never reached")
        assert g(3, 4) == (6, 12)

    # an "and" or "or" return value may have a tail-call in the last item
    with continuations:
        # "or"
        def h1(a, b, *, cc):
            with bind[f(a, b)] as (x, y):
                return None or f(3, 4)  # the f from the previous "with continuations" block
        assert h1(3, 4) == (6, 12)

        def h2(a, b, *, cc):
            with bind[f(a, b)] as (x, y):
                return True or f(3, 4)
        assert h2(3, 4) is True

        # "or" with 3 or more items (testing; handled differently internally)
        def h3(a, b, *, cc):
            with bind[f(a, b)] as (x, y):
                return None or False or f(3, 4)
        assert h3(3, 4) == (6, 12)

        def h4(a, b, *, cc):
            with bind[f(a, b)] as (x, y):
                return None or True or f(3, 4)
        assert h4(3, 4) is True

        def h5(a, b, *, cc):
            with bind[f(a, b)] as (x, y):
                return 42 or None or f(3, 4)
        assert h5(3, 4) == 42

        # "and"
        def i1(a, b, *, cc):
            with bind[f(a, b)] as (x, y):
                return True and f(3, 4)
        assert i1(3, 4) == (6, 12)

        def i2(a, b, *, cc):
            with bind[f(a, b)] as (x, y):
                return False and f(3, 4)
        assert i2(3, 4) is False

        # "and" with 3 or more items
        def i3(a, b, *, cc):
            with bind[f(a, b)] as (x, y):
                return True and 42 and f(3, 4)
        assert i3(3, 4) == (6, 12)

        def i4(a, b, *, cc):
            with bind[f(a, b)] as (x, y):
                return True and False and f(3, 4)
        assert i4(3, 4) is False

        def i5(a, b, *, cc):
            with bind[f(a, b)] as (x, y):
                return None and False and f(3, 4)
        assert i5(3, 4) is False

        # combination of "and" and "or"
        def j1(a, b, *, cc):
            with bind[f(a, b)] as (x, y):
                return None or True and f(3, 4)
        assert j1(3, 4) == (6, 12)

    # call_ec combo
    with continuations:
        def g(x, *, cc):
            return 2*x

        @call_ec
        def result(ec, *, cc):
            ec(g(21))
        assert result == 42

#        # ec doesn't work from inside a "with bind", because the function
#        # containing the "with bind" actually tail-calls the bind and exits.
#        @call_ec
#        def doit(ec, *, cc):
#            with bind[g(21)] as x:
#                ec(x)  # we're actually outside doit(); ec no longer valid

#        # Even this only works the first time; if you stash the cc and
#        # call it later (to re-run the body of the "with bind", at that time
#        # result() will already have exited so the ec no longer works.
#        # (That's just the nature of exceptions.)
#        @call_ec
#        def result(ec, *, cc):
#            def doit(*, cc):
#                with bind[g(21)] as x:
#                    ec(x)
#            r = doit()  # don't tail-call it; result() must be still running when the ec is invoked
#            return r
#        assert result == 42

    # test that ecs expand correctly
    with continuations:
        @call_ec
        def result(ec, *, cc):
            return ec(42)  # doesn't need the "return"; the macro eliminates it
        assert result == 42

        assert call_ec(lambda ec, *, cc: ec(42)) == 42

    # curry combo
    def testcurrycombo():
        with continuations:
            from ...fun import curry  # TODO: can't rename, unpythonic.syntax.util.sort_lambda_decorators won't detect it
            # Currying here makes no sense, but test that it expands correctly.
            # We should get trampolined(call_ec(curry(...))), which produces the desired result.
            assert call_ec(curry(lambda ec, *, cc: ec(42))) == 42
    testcurrycombo()
    # This version auto-inserts curry after the inner macros have expanded.
    # This should work, too.
    with curry:
        with continuations:
            assert call_ec(lambda ec, *, cc: ec(42)) == 42

    # silly call/cc example (Paul Graham: On Lisp, p. 261), pythonified
    with continuations:
        k = None  # kontinuation
        def setk(*args, cc):
            nonlocal k
            k = cc  # current continuation, i.e. where to go after setk() finishes
            xs = list(args)
            # - not "return list(args)" because that would be a tail call,
            #   and list() is a regular function, not a continuation-enabled one
            #   (so it would immediately terminate the TCO chain; besides,
            #   it takes only 1 argument and doesn't know what to do with "cc".)
            # - list instead of tuple to return it as one value
            #   (a tuple return value is interpreted as multiple-return-values)
            return xs
        def doit(*, cc):
            lst = ['the call returned']
            with bind[setk('A')] as more:  # call/cc, sort of...
                return lst + more          # ...where the body is the continuation
        print(doit())
        # We can now send stuff into k, as long as it conforms to the
        # signature of the as-part of the "with bind".
        print(k(['again']))
        print(k(['thrice', '!']))

    # A top-level "with bind" is also allowed.
    #
    # In that case there is no way to get the return value of the continuation
    # the first time it runs, because "with" is a statement.
    #
    # On further runs, it is of course possible to get the return value as usual.
    with continuations:
        k = None
        def setk(*args, cc):
            nonlocal k
            k = cc
            return args  # tuple return value (if not literal, tested at run-time) --> multiple-values
        with bind[setk(1, 2)] as (x, y):
            print(x, y)
            return x, y
        assert k(3, 4) == (3, 4)
        assert k(5, 6) == (5, 6)

    # multilambda combo
    with multilambda, continuations:
        f = lambda x, *, cc: [print(x), x**2]
        assert f(42) == 1764

    # depth-first tree traversal (Paul Graham: On Lisp, p. 271)
    def atom(x):
        return not isinstance(x, (list, tuple))
    t1 = ["a", ["b", ["d", "h"]], ["c", "e", ["f", "i"], "g"]]
    t2 = [1, [2, [3, 6, 7], 4, 5]]

    def dft(tree):  # classical, no continuations
        if not tree:
            return
        if atom(tree):
            print(tree, end='')
            return
        first, *rest = tree
        dft(first)
        dft(rest)
    print("dft")
    dft(t1)  # abdhcefig
    print()

    with continuations:
        saved = []
        def dft_node(tree, *, cc):
            if not tree:
                return restart()
            if atom(tree):
                return tree
            first, *rest = tree
            ourcc = cc  # capture our current continuation
            # override default continuation in the tail-call in the lambda
            saved.append(lambda *, cc: dft_node(rest, cc=ourcc))
            return dft_node(first)
        def restart(*, cc):
            if saved:
                f = saved.pop()
                return f()
            else:
                return "done"
        def dft2(tree, *, cc):
            nonlocal saved
            saved = []
            with bind[dft_node(tree)] as node:
                if node == "done":
                    return "done"
                print(node, end='')
                return restart()
        print("dft2")
        dft2(t1)
        print()

        # The continuation version allows to easily walk two trees simultaneously,
        # generating their cartesian product (example from On Lisp, p. 272):
        def treeprod(ta, tb, *, cc):
            with bind[dft_node(ta)] as node1:
                if node1 == "done":
                    return "done"
                with bind[dft_node(tb)] as node2:
                    return [node1, node2]
        out = []
        x = treeprod(t1, t2)
        while x != "done":
            out.append(x)
            x = restart()
        print(out)

    # maybe more pythonic to make it a generator?
    #
    # We can define and use this outside the block, since at this level
    # we don't need to manipulate cc.
    #
    # (We could as well define and use it inside the block, by adding "*, cc"
    # to the args of the def.)
    def treeprod_gen(ta, tb):
        x = treeprod(t1, t2)
        while x != "done":
            yield x
            x = restart()
    out2 = tuple(treeprod_gen(t1, t2))
    print(out2)

    # The most pythonic way, of course, is to define dft as a generator,
    # since that already provides suspend-and-resume...
    def dft3(tree):
        if not tree:
            return
        if atom(tree):
            yield tree
            return
        first, *rest = tree
        yield from dft3(first)
        yield from dft3(rest)
    print("dft3")
    print("".join(dft3(t1)))  # abdhcefig

    # McCarthy's amb operator is very similar to dft, if a bit shorter:
    with continuations:
        stack = []
        def amb(lst, *, cc):
            if not lst:
                return fail()
            first, *rest = lst
            if rest:
                ourcc = cc
                stack.append(lambda *, cc: amb(rest, cc=ourcc))
            return first
        def fail(*, cc):
            if stack:
                f = stack.pop()
                return f()

        # testing
        def doit1(*, cc):
            with bind[amb((1, 2, 3))] as c1:
                with bind[amb((10, 20))] as c2:
                    if c1 and c2:
                        return c1 + c2
        print(doit1())
        # How this differs from a comprehension is that we can fail()
        # **outside** the dynamic extent of doit1. Doing that rewinds,
        # and returns the next value. The control flow state is kept
        # on the continuation stack just like in Scheme/Racket.
        print(fail())
        print(fail())
        print(fail())
        print(fail())
        print(fail())
        print(fail())

        def doit2(*, cc):
            with bind[amb((1, 2, 3))] as c1:
                with bind[amb((10, 20))] as c2:
                    if c1 + c2 != 22:  # we can require conditions like this
                        return fail()
                    return c1, c2
        print(doit2())
        print(fail())

        # Pythagorean triples.
        count = 0
        def pt(*, cc):
            # This generates 1540 combinations, with several nested tail-calls each,
            # so we really need TCO here. (Without TCO, nothing would return until
            # the whole computation is done; it would blow the call stack very quickly.)
            with bind[amb(tuple(range(1, 21)))] as z:
                with bind[amb(tuple(range(1, z+1)))] as y:
                    with bind[amb(tuple(range(1, y+1)))] as x:
                        nonlocal count
                        count += 1
                        if x*x + y*y != z*z:
                            return fail()
                        return x, y, z
        print(pt())
        print(fail())
        print(fail())
        print(fail())
        print(fail())
        print(fail())
        print(fail())
        print("combinations tested: {:d}".format(count))

    # Pythagorean triples, pythonic way
    def pt_gen():
        for z in range(1, 21):
            for y in range(1, z+1):
                for x in range(1, y+1):
                    if x*x + y*y != z*z:
                        continue
                    yield x, y, z
    print(tuple(pt_gen()))

    # autoreturn combo
#     with curry:  # major slowdown, but works; must be in a separate "with"  # TODO: why separate?
    with autoreturn, continuations:
        stack = []
        def amb(lst, *, cc):
            if lst:
                first, *rest = lst
                if rest:
                    ourcc = cc
                    stack.append(lambda *, cc: amb(rest, cc=ourcc))
                first
            else:
                fail()
        def fail(*, cc):
            if stack:
                f = stack.pop()
                f()

        def pyth(*, cc):
            with bind[amb(tuple(range(1, 21)))] as z:
                with bind[amb(tuple(range(1, z+1)))] as y:
                    with bind[amb(tuple(range(1, y+1)))] as x:  # <-- the call/cc
                        if x*x + y*y == z*z:                    # body is the cont
                            x, y, z
                        else:
                            fail()
        x = pyth()
        while x:
            print(x)
            x = fail()

    print("All tests PASSED")

if __name__ == '__main__':
    test()
