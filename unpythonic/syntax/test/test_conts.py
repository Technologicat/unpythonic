# -*- coding: utf-8 -*-
"""Continuations (call/cc for Python)."""

from ...syntax import macros, continuations, call_cc, multilambda, autoreturn, curry

from ...ec import call_ec
from ...fploop import looped

def test():
    # basic testing
    with continuations:
        def add1(x):
            return 1 + x
        assert add1(2) == 3

        def message(cc):
            return ("hello", "there")
        def baz():
            m, n = call_cc[message()]  # The cc arg is passed implicitly.
            return [m, n]
        assert baz() == ["hello", "there"]

        # The cc arg must be declared as the last one that has no default value,
        # or declared as by-name-only. It's always passed by name.
        def f(a, b, cc):
            return 2*a, 3*b
        assert f(3, 4) == (6, 12)
        x, y = f(3, 4)
        assert x == 6 and y == 12

        def g(a, b):
            x, y = call_cc[f(a, b)]
            return x, y
            assert False, "never reached"
        assert g(3, 4) == (6, 12)

        xs, *a = call_cc[f(1, 2)]
        print(xs, a)

    # an "and" or "or" return value may have a tail-call in the last item
    with continuations:
        # "or"
        def h1(a, b):
            x, y = call_cc[f(a, b)]
            return None or f(3, 4)  # the f from the previous "with continuations" block
        assert h1(3, 4) == (6, 12)

        def h2(a, b):
            x, y = call_cc[f(a, b)]
            return True or f(3, 4)
        assert h2(3, 4) is True

        # "or" with 3 or more items (testing; handled differently internally)
        def h3(a, b):
            x, y = call_cc[f(a, b)]
            return None or False or f(3, 4)
        assert h3(3, 4) == (6, 12)

        def h4(a, b):
            x, y = call_cc[f(a, b)]
            return None or True or f(3, 4)
        assert h4(3, 4) is True

        def h5(a, b):
            x, y = call_cc[f(a, b)]
            return 42 or None or f(3, 4)
        assert h5(3, 4) == 42

        # "and"
        def i1(a, b):
            x, y = call_cc[f(a, b)]
            return True and f(3, 4)
        assert i1(3, 4) == (6, 12)

        def i2(a, b):
            x, y = call_cc[f(a, b)]
            return False and f(3, 4)
        assert i2(3, 4) is False

        # "and" with 3 or more items
        def i3(a, b):
            x, y = call_cc[f(a, b)]
            return True and 42 and f(3, 4)
        assert i3(3, 4) == (6, 12)

        def i4(a, b):
            x, y = call_cc[f(a, b)]
            return True and False and f(3, 4)
        assert i4(3, 4) is False

        def i5(a, b):
            x, y = call_cc[f(a, b)]
            return None and False and f(3, 4)
        assert i5(3, 4) is False

        # combination of "and" and "or"
        def j1(a, b):
            x, y = call_cc[f(a, b)]
            return None or True and f(3, 4)
        assert j1(3, 4) == (6, 12)

    # call_ec combo
    with continuations:
        def g(x, cc):
            return 2*x

        @call_ec
        def result(ec):
            ec(g(21))
        assert result == 42

#        # ec doesn't work from inside a continuation, because the function
#        # containing the "call_cc" actually tail-calls the continuation and exits.
#        @call_ec
#        def doit(ec):
#            x = call_cc[g(21)]
#            ec(x)  # we're actually outside doit(); ec no longer valid

#        # Even this only works the first time; if you stash the cc and
#        # call it later (to re-run the continuation, at that time
#        # result() will already have exited so the ec no longer works.
#        # (That's just the nature of exceptions.)
#        @call_ec
#        def result(ec):
#            def doit():
#                x = call_cc[g(21)]
#                ec(x)
#            r = doit()  # don't tail-call it; result() must be still running when the ec is invoked
#            return r
#        assert result == 42

    # test that ecs expand correctly
    with continuations:
        @call_ec
        def result(ec):
            return ec(42)  # doesn't need the "return"; the macro eliminates it
        assert result == 42

        assert call_ec(lambda ec: ec(42)) == 42

    # curry combo
    def testcurrycombo():
        with continuations:
            from ...fun import curry  # TODO: can't rename, unpythonic.syntax.util.sort_lambda_decorators won't detect it
            # Currying here makes no sense, but test that it expands correctly.
            # We should get trampolined(call_ec(curry(...))), which produces the desired result.
            assert call_ec(curry(lambda ec: ec(42))) == 42
    testcurrycombo()
    # This version auto-inserts curry after the inner macros have expanded.
    # This should work, too.
    with curry:
        with continuations:
            assert call_ec(lambda ec: ec(42)) == 42

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
        def doit():
            lst = ['the call returned']
            more = call_cc[setk('A')]
            return lst + more  # The remaining stmts in the body are the continuation.
        print(doit())
        # We can now send stuff into k, as long as it conforms to the
        # signature of the assignment targets of the "call_cc".
        print(k(['again']))
        print(k(['thrice', '!']))

    # same, with multiple-return-values and a starred assignment target
    with continuations:
        k = None  # kontinuation
        def setk(*args, cc):
            nonlocal k
            k = cc  # current continuation, i.e. where to go after setk() finishes
            return args  # tuple means multiple-return-values
        def doit():
            lst = ['the call returned']
            *more = call_cc[setk('A')]
            return lst + list(more)
        print(doit())
        # We can now send stuff into k, as long as it conforms to the
        # signature of the assignment targets of the "call_cc".
        print(k('again'))
        print(k('thrice', '!'))

    # A top-level "call_cc" is also allowed.
    #
    # In that case the continuation always returns None, because the original
    # use site was not a function.
    with continuations:
        k = None
        def setk(*args, cc):
            nonlocal k
            k = cc
            return args  # tuple return value (if not literal, tested at run-time) --> multiple-values
        x, y = call_cc[setk(1, 2)]
        print(x, y)
    # end the block to end capture, and start another one to resume programming
    # in continuation-enabled mode.
    with continuations:
        assert k(3, 4) == None
        assert k(5, 6) == None

    # multilambda combo
    with multilambda, continuations:
        f = lambda x: [print(x), x**2]
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
        def dft_node(tree, cc):
            if not tree:
                return restart()
            if atom(tree):
                return tree
            first, *rest = tree
            ourcc = cc  # capture our current continuation
            # override default continuation in the tail-call in the lambda
            saved.append(lambda: dft_node(rest, cc=ourcc))
            return dft_node(first)
        def restart():
            if saved:
                f = saved.pop()
                return f()
            else:
                return "done"
        def dft2(tree):
            nonlocal saved
            saved = []
            node = call_cc[dft_node(tree)]
            if node == "done":
                return "done"
            print(node, end='')
            return restart()
        print("dft2")
        dft2(t1)
        print()

        # The continuation version allows to easily walk two trees simultaneously,
        # generating their cartesian product (example from On Lisp, p. 272):
        def treeprod(ta, tb):
            node1 = call_cc[dft_node(ta)]
            if node1 == "done":
                return "done"
            node2 = call_cc[dft_node(tb)]
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
    # (We could as well define and use it inside the block.)
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
        def amb(lst, cc):
            if not lst:
                return fail()
            first, *rest = lst
            if rest:
                ourcc = cc
                stack.append(lambda: amb(rest, cc=ourcc))
            return first
        def fail():
            if stack:
                f = stack.pop()
                return f()

        # testing
        def doit1():
            c1 = call_cc[amb((1, 2, 3))]
            c2 = call_cc[amb((10, 20))]
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

        def doit2():
            c1 = call_cc[amb((1, 2, 3))]
            c2 = call_cc[amb((10, 20))]
            if c1 + c2 != 22:  # we can require conditions like this
                return fail()
            return c1, c2
        print(doit2())
        print(fail())

        # Pythagorean triples.
        count = 0
        def pt():
            # This generates 1540 combinations, with several nested tail-calls each,
            # so we really need TCO here. (Without TCO, nothing would return until
            # the whole computation is done; it would blow the call stack very quickly.)
            z = call_cc[amb(tuple(range(1, 21)))]
            y = call_cc[amb(tuple(range(1, z+1)))]
            x = call_cc[amb(tuple(range(1, y+1)))]
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
        def amb(lst, cc):
            if lst:
                first, *rest = lst
                if rest:
                    ourcc = cc
                    stack.append(lambda: amb(rest, cc=ourcc))
                first
            else:
                fail()
        def fail():
            if stack:
                f = stack.pop()
                f()

        def pyth():
            z = call_cc[amb(tuple(range(1, 21)))]
            y = call_cc[amb(tuple(range(1, z+1)))]
            x = call_cc[amb(tuple(range(1, y+1)))]
            if x*x + y*y == z*z:
                x, y, z
            else:
                fail()
        x = pyth()
        while x:
            print(x)
            x = fail()

    # FP loop combo? Testing...
    with continuations:
        k = None
        def setk(cc):
            nonlocal k
            k = cc
        out = []
        @looped
        def s(loop, acc=0):
            call_cc[setk()]
            out.append(acc)
            if acc < 10:
                return loop(acc + 1)
            return acc
        assert tuple(out) == tuple(range(11))
        assert s == 10
        s = k()  # k is re-captured at each iteration, so now acc=10...
        assert tuple(out) == tuple(range(11)) + (10,)
        assert s == 10

    # To be able to resume from an arbitrary iteration, we need something like...
    with continuations:
        k = None
        def setk(x, cc):  # pass x through; as a side effect, set k
            nonlocal k
            k = cc
            return x
        out = []
        @looped
        def s(loop, acc=0):
            acc = call_cc[setk(acc)]
            out.append(acc)
            if acc < 10:
                return loop(acc + 1)
            return acc
        assert tuple(out) == tuple(range(11))
        assert s == 10
        s = k(5)  # send in the new initial acc
        assert tuple(out) == tuple(range(11)) + tuple(range(5, 11))
        assert s == 10

    # To always resume from the beginning, we can do something like this...
    with continuations:
        k = None
        def setk(acc, cc):
            nonlocal k
            # because call_cc[] must be at the top level of a def,
            # we refactor the "if" here (but see below).
            if acc == 0:
                k = cc
        out = []
        @looped
        def s(loop, acc=0):
            call_cc[setk(acc)]
            out.append(acc)
            if acc < 10:
                return loop(acc + 1)
            return acc
        assert tuple(out) == tuple(range(11))
        assert s == 10
        s = k()
        assert tuple(out) == 2*tuple(range(11))
        assert s == 10

    # To eliminate the passing of acc into setk, let's use a closure:
    with continuations:
        k = None
        out = []
        @looped
        def s(loop, acc=0):
            def setk(cc):
                nonlocal k
                if acc == 0:
                    k = cc
            call_cc[setk()]
            out.append(acc)
            if acc < 10:
                return loop(acc + 1)
            return acc
        assert tuple(out) == tuple(range(11))
        assert s == 10
        s = k()
        assert tuple(out) == 2*tuple(range(11))
        assert s == 10

    # conditional call_cc[f(...) if p else g(...)]
    # each of the calls f(...), g(...) may be replaced with None, which means
    # proceed directly to the cont, setting assignment targets (if any) to None.
    with continuations:
        k = None
        def setk(cc):
            nonlocal k
            k = cc
        out = []
        @looped
        def s(loop, acc=0):
            call_cc[setk() if acc == 0 else None]
            out.append(acc)
            if acc < 10:
                return loop(acc + 1)
            return acc
        assert tuple(out) == tuple(range(11))
        assert s == 10
        s = k()
        assert tuple(out) == 2*tuple(range(11))
        assert s == 10

    print("All tests PASSED")
