# -*- coding: utf-8 -*-
"""Continuations (call/cc for Python)."""

from ...syntax import macros, test, test_raises, error  # noqa: F401
from ...test.fixtures import session, testset, returns_normally

from ...syntax import macros, continuations, call_cc, multilambda, autoreturn, curry, let  # noqa: F401, F811

from ...ec import call_ec
from ...fploop import looped
from ...tco import trampolined, jump
from ...fun import withself

def runtests():
    with testset("basic usage"):
        with continuations:
            def add1(x):
                return 1 + x
            test[add1(2) == 3]

            def message(cc):
                return ("hello", "there")
            def baz():
                m, n = call_cc[message()]  # The cc arg is passed implicitly.
                return [m, n]
            test[baz() == ["hello", "there"]]

            # The cc arg must be declared as the last one that has no default value,
            # or declared as by-name-only. It's always passed by name.
            def f(a, b, cc):
                return 2 * a, 3 * b
            test[f(3, 4) == (6, 12)]
            x, y = f(3, 4)
            test[x == 6 and y == 12]

            def g(a, b):
                x, y = call_cc[f(a, b)]
                return x, y
                fail["This line should not be reached."]  # pragma: no cover
            test[g(3, 4) == (6, 12)]

            xs, *a = call_cc[f(1, 2)]
            test[xs == 2 and a == (6,)]

    # an "and" or "or" return value may have a tail-call in the last item
    with testset("tail call in logical expressions"):
        with continuations:
            # "or"
            def h1(a, b):
                x, y = call_cc[f(a, b)]
                return None or f(3, 4)  # the f from the previous "with continuations" block
            test[h1(3, 4) == (6, 12)]

            def h2(a, b):
                x, y = call_cc[f(a, b)]
                return True or f(3, 4)
            test[h2(3, 4) is True]

            # "or" with 3 or more items (testing; handled differently internally)
            def h3(a, b):
                x, y = call_cc[f(a, b)]
                return None or False or f(3, 4)
            test[h3(3, 4) == (6, 12)]

            def h4(a, b):
                x, y = call_cc[f(a, b)]
                return None or True or f(3, 4)
            test[h4(3, 4) is True]

            def h5(a, b):
                x, y = call_cc[f(a, b)]
                return 42 or None or f(3, 4)
            test[h5(3, 4) == 42]

            # "and"
            def i1(a, b):
                x, y = call_cc[f(a, b)]
                return True and f(3, 4)
            test[i1(3, 4) == (6, 12)]

            def i2(a, b):
                x, y = call_cc[f(a, b)]
                return False and f(3, 4)
            test[i2(3, 4) is False]

            # "and" with 3 or more items
            def i3(a, b):
                x, y = call_cc[f(a, b)]
                return True and 42 and f(3, 4)
            test[i3(3, 4) == (6, 12)]

            def i4(a, b):
                x, y = call_cc[f(a, b)]
                return True and False and f(3, 4)
            test[i4(3, 4) is False]

            def i5(a, b):
                x, y = call_cc[f(a, b)]
                return None and False and f(3, 4)
            test[i5(3, 4) is False]

            # combination of "and" and "or"
            def j1(a, b):
                x, y = call_cc[f(a, b)]
                return None or True and f(3, 4)
            test[j1(3, 4) == (6, 12)]

    with testset("let in tail position"):
        with continuations:
            def j2(a, b):
                x, y = call_cc[f(a, b)]
                return let[((c, a),  # noqa: F821
                            (d, b)) in f(c, d)]  # noqa: F821
            test[j2(3, 4) == (6, 12)]

    with testset("if-expression in tail position"):
        with continuations:
            def j3(a, b):
                x, y = call_cc[f(a, b)]
                return f(a, b) if True else None
            test[j3(3, 4) == (6, 12)]

            def j4(a, b):
                x, y = call_cc[f(a, b)]
                return None if False else f(a, b)
            test[j4(3, 4) == (6, 12)]

    with testset("integration with a lambda that has TCO"):
        with continuations:
            fact = trampolined(withself(lambda self, n, acc=1:
                                        acc if n == 0 else jump(self, n - 1, n * acc)))
            test[fact(5) == 120]
        test[returns_normally(fact(5000))]  # no crash

    with testset("integration with @call_ec"):
        with continuations:
            def g(x, cc):
                return 2 * x

            @call_ec
            def result(ec):
                ec(g(21))
            test[result == 42]

            @call_ec
            def result(ec):
                return ec(42)  # doesn't need the "return"; the macro eliminates it
            test[result == 42]

            test[call_ec(lambda ec: ec(42)) == 42]

            # # ec doesn't work from inside a continuation, because the function
            # # containing the "call_cc" actually tail-calls the continuation and exits.
            # @call_ec
            # def doit(ec):
            #     x = call_cc[g(21)]
            #     ec(x)  # we're actually outside doit(); ec no longer valid
            #
            # # Even this only works the first time; if you stash the cc and
            # # call it later (to re-run the continuation, at that time
            # # result() will already have exited so the ec no longer works.
            # # (That's just the nature of exceptions, used to implement ec.)
            # @call_ec
            # def result(ec):
            #     def doit():
            #         x = call_cc[g(21)]
            #         ec(x)
            #     r = doit()  # don't tail-call it; result() must be still running when the ec is invoked
            #     return r
            # test[result == 42]

    with testset("integration with curry"):
        def testcurrycombo():
            with continuations:
                from ...fun import curry  # TODO: can't rename the import, unpythonic.syntax.util.sort_lambda_decorators won't detect it
                # Currying here makes no sense, but we test that it expands correctly.
                # We should get trampolined(call_ec(curry(...))), which produces the desired result.
                test[call_ec(curry(lambda ec: ec(42))) == 42]
        testcurrycombo()
        # This version auto-inserts curry after the inner macros have expanded.
        # This should work, too.
        with curry:
            with continuations:
                test[call_ec(lambda ec: ec(42)) == 42]

    with testset("call/cc example from On Lisp, p. 261, pythonified"):
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
            test[doit() == ['the call returned', 'A']]
            # We can now send stuff into k, as long as it conforms to the
            # signature of the assignment targets of the "call_cc".
            test[k(['again']) == ['the call returned', 'again']]
            test[k(['thrice', '!']) == ['the call returned', 'thrice', '!']]

    with testset("multiple-return-values, starred assignment target"):
        with continuations:
            k = None  # kontinuation
            def setk(*args, cc):  # noqa: F811, the previous one is no longer used.
                nonlocal k
                k = cc  # current continuation, i.e. where to go after setk() finishes
                return args  # tuple means multiple-return-values
            def doit():
                lst = ['the call returned']
                *more, = call_cc[setk('A')]
                return lst + list(more)
            test[doit() == ['the call returned', 'A']]
            # We can now send stuff into k, as long as it conforms to the
            # signature of the assignment targets of the "call_cc".
            test[k('again') == ['the call returned', 'again']]
            test[k('thrice', '!') == ['the call returned', 'thrice', '!']]

    with testset("top level call_cc"):
        # A top-level "call_cc" is also allowed.
        #
        # In that case the continuation always returns None, because the original
        # use site was not a function.
        vals = 1, 2
        with continuations:
            k = None
            def setk(*args, cc):  # noqa: F811, the previous one is no longer used.
                nonlocal k
                k = cc
                return args  # tuple return value (if not literal, tested at run-time) --> multiple-values
            x, y = call_cc[setk(*vals)]
            test[x, y == vals]
        # end the block to end capture, and start another one to resume programming
        # in continuation-enabled mode.
        with continuations:
            vals = 3, 4
            test[k(*vals) is None]
            vals = 5, 6
            test[k(*vals) is None]

    with testset("conditional top-level call_cc"):
        with continuations:
            x = call_cc[setk("yes") if 42 % 2 == 0 else None]
            test[x == "yes"]

            x = call_cc[None if 42 % 2 == 0 else setk("yes")]
            test[x is None]

    with testset("integration with multilambda"):
        with multilambda, continuations:
            out = []
            f = lambda x: [out.append(x), x**2]
            test[f(42) == 1764 and out == [42]]

    with testset("depth-first tree traversal from On Lisp, p. 271"):
        def atom(x):
            return not isinstance(x, (list, tuple))
        t1 = ["a", ["b", ["d", "h"]], ["c", "e", ["f", "i"], "g"]]
        t2 = [1, [2, [3, 6, 7], 4, 5]]

        out = ""
        def dft(tree):  # classical, no continuations
            if not tree:
                return
            if atom(tree):
                nonlocal out
                out += tree
                return
            first, *rest = tree
            dft(first)
            dft(rest)
        dft(t1)
        test[out == "abdhcefig"]

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
            out = ""
            def dft2(tree):
                nonlocal saved
                saved = []
                node = call_cc[dft_node(tree)]
                if node == "done":
                    return "done"
                nonlocal out  # must be placed after call_cc[]; we write to out **in the continuation part**
                out += node
                return restart()
            dft2(t1)
            test[out == "abdhcefig"]

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
            test[out == [['a', 1], ['a', 2], ['a', 3], ['a', 6], ['a', 7], ['a', 4], ['a', 5],
                         ['b', 1], ['b', 2], ['b', 3], ['b', 6], ['b', 7], ['b', 4], ['b', 5],
                         ['d', 1], ['d', 2], ['d', 3], ['d', 6], ['d', 7], ['d', 4], ['d', 5],
                         ['h', 1], ['h', 2], ['h', 3], ['h', 6], ['h', 7], ['h', 4], ['h', 5],
                         ['c', 1], ['c', 2], ['c', 3], ['c', 6], ['c', 7], ['c', 4], ['c', 5],
                         ['e', 1], ['e', 2], ['e', 3], ['e', 6], ['e', 7], ['e', 4], ['e', 5],
                         ['f', 1], ['f', 2], ['f', 3], ['f', 6], ['f', 7], ['f', 4], ['f', 5],
                         ['i', 1], ['i', 2], ['i', 3], ['i', 6], ['i', 7], ['i', 4], ['i', 5],
                         ['g', 1], ['g', 2], ['g', 3], ['g', 6], ['g', 7], ['g', 4], ['g', 5]]]

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
        out2 = list(treeprod_gen(t1, t2))
        test[out2 == out]

        # The most pythonic way, of course, is to define dft as a generator,
        # since that already provides suspend-and-resume (a.k.a. single-shot continuations)...
        def dft3(tree):
            if not tree:
                return
            if atom(tree):
                yield tree
                return
            first, *rest = tree
            yield from dft3(first)
            yield from dft3(rest)
        test[list(dft3(t1)) == [x for x in "abdhcefig"]]

    # McCarthy's amb operator is very similar to dft, if a bit shorter:
    with testset("McCarthy's amb operator (the real deal)"):
        with continuations:
            stack = []
            def amb(lst, cc):
                if not lst:
                    return fail()
                first, *rest = tuple(lst)
                if rest:
                    ourcc = cc
                    stack.append(lambda: amb(rest, cc=ourcc))
                return first
            def fail():
                if stack:
                    f = stack.pop()
                    return f()

            # testing
            test[amb(()) is None]

            def doit1():
                c1 = call_cc[amb((1, 2, 3))]
                c2 = call_cc[amb((10, 20))]
                if c1 and c2:
                    return c1 + c2
            test[doit1() == 11]
            # How this differs from a comprehension is that we can fail()
            # **outside** the dynamic extent of doit1. Doing that rewinds,
            # and returns the next value. The control flow state is kept
            # on the continuation stack just like in Scheme/Racket.
            #
            # (The last call_cc[] is the innermost loop.)
            test[fail() == 21]
            test[fail() == 12]
            test[fail() == 22]
            test[fail() == 13]
            test[fail() == 23]
            test[fail() is None]

            def doit2():
                c1 = call_cc[amb((1, 2, 3))]
                c2 = call_cc[amb((10, 20))]
                if c1 + c2 != 22:  # we can require conditions like this
                    return fail()
                return c1, c2
            test[doit2() == (2, 20)]
            test[fail() is None]

        # Pythagorean triples, pythonic way (to generate a reference solution)
        def pt_gen(maxn):
            for z in range(1, maxn + 1):
                for y in range(1, z + 1):
                    for x in range(1, y + 1):
                        if x * x + y * y != z * z:
                            continue
                        yield x, y, z
        pts = list(pt_gen(20))

        with continuations:
            # Pythagorean triples.
            count = 0
            def pt(maxn):
                # This generates 1540 combinations, with several nested tail-calls each,
                # so we really need TCO here. (Without TCO, nothing would return until
                # the whole computation is done; it would blow the call stack very quickly.)
                z = call_cc[amb(range(1, maxn + 1))]
                y = call_cc[amb(range(1, z + 1))]
                x = call_cc[amb(range(1, y + 1))]
                nonlocal count
                count += 1
                if x * x + y * y != z * z:
                    return fail()
                return x, y, z
            out = []
            x = pt(20)
            while x is not None:
                out.append(x)
                x = fail()
            test[out == pts]
            print("combinations tested for Pythagorean triples: {:d}".format(count))

    with testset("integration with autoreturn"):
        with autoreturn, continuations:
            stack = []
            def amb(lst, cc):  # noqa: F811, the previous one is no longer used.
                if lst:
                    first, *rest = tuple(lst)
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

            # testing
            test[amb(()) is None]

            def pt(maxn):
                z = call_cc[amb(range(1, maxn + 1))]
                y = call_cc[amb(range(1, z + 1))]
                x = call_cc[amb(range(1, y + 1))]
                if x * x + y * y == z * z:
                    x, y, z
                else:
                    fail()
            out = []
            x = pt(20)
            while x is not None:
                out.append(x)
                x = fail()
            test[out == pts]

    with testset("integration with autoreturn and curry simultaneously"):
        with curry:  # major slowdown, but works; must be in a separate "with"  # TODO: why separate?  https://github.com/azazel75/macropy/issues/21
            with autoreturn, continuations:
                stack = []
                def amb(lst, cc):  # noqa: F811, the previous one is no longer used.
                    if lst:
                        first, *rest = tuple(lst)
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

                # testing
                test[amb(()) is None]

                def pt(maxn):
                    z = call_cc[amb(range(1, maxn + 1))]
                    y = call_cc[amb(range(1, z + 1))]
                    x = call_cc[amb(range(1, y + 1))]
                    if x * x + y * y == z * z:
                        x, y, z
                    else:
                        fail()
                out = []
                x = pt(20)
                while x is not None:
                    out.append(x)
                    x = fail()
                test[out == pts]

    with testset("integration with @looped (unpythonic.fploop)"):
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
            test[tuple(out) == tuple(range(11))]
            test[s == 10]
            s = k()  # k is re-captured at each iteration, so now acc=10...
            test[tuple(out) == tuple(range(11)) + (10,)]
            test[s == 10]

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
            test[tuple(out) == tuple(range(11))]
            test[s == 10]
            s = k(5)  # send in the new initial acc
            test[tuple(out) == tuple(range(11)) + tuple(range(5, 11))]
            test[s == 10]

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
            test[tuple(out) == tuple(range(11))]
            test[s == 10]
            s = k()
            test[tuple(out) == 2 * tuple(range(11))]
            test[s == 10]

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
            test[tuple(out) == tuple(range(11))]
            test[s == 10]
            s = k()
            test[tuple(out) == 2 * tuple(range(11))]
            test[s == 10]

    # conditional call_cc[f(...) if p else g(...)]
    # each of the calls f(...), g(...) may be replaced with None, which means
    # proceed directly to the cont, setting assignment targets (if any) to None.
    with testset("conditional call_cc syntax"):
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
            test[tuple(out) == tuple(range(11))]
            test[s == 10]
            s = k()
            test[tuple(out) == 2 * tuple(range(11))]
            test[s == 10]

if __name__ == '__main__':  # pragma: no cover
    with session(__file__):
        runtests()
