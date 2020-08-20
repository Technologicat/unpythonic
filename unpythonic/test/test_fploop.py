# -*- coding: utf-8 -*-

from ..syntax import macros, test, test_raises, fail  # noqa: F401
from .fixtures import session, testset

from ..fploop import looped, looped_over, breakably_looped, breakably_looped_over
from ..tco import trampolined, jump

from ..let import let
from ..seq import begin
from ..misc import call, timer
from ..ec import catch, throw

def runtests():
    with testset("basic usage"):
        @looped
        def s(loop, acc=0, i=0):
            if i == 10:
                return acc  # there's no "break"; loop terminates at the first normal return
            # same as return jump(s, acc+i, i+1), but sets up the "loop" arg.
            return loop(acc + i, i + 1)
        test[s == 45]

        # equivalent to:
        @trampolined
        def dowork(acc=0, i=0):
            if i == 10:
                return acc
            return jump(dowork, acc + i, i + 1)
        s = dowork()  # when using just @trampolined, must start the loop manually
        test[s == 45]

        # impure FP loop - side effects:
        out = []
        @looped
        def _ignored1(loop, i=0):
            if i < 3:
                out.append(i)
                return loop(i + 1)
            # the implicit "return None" terminates the loop.
        test[out == [0, 1, 2]]

        # same without using side effects - make an accumulator parameter:
        @looped
        def out(loop, i=0, acc=[]):
            if i >= 3:
                return acc
            acc.append(i)
            return loop(i + 1)
        test[out == [0, 1, 2]]

        # there's no "continue"; make your own:
        @looped
        def s(loop, acc=0, i=0):
            cont = lambda newacc=acc: loop(newacc, i + 1)  # <-- this
            if i == 10:
                return acc
            elif i <= 4:
                return cont()  # default: current value of acc
            return cont(acc + i)
        test[s == 35]

    with testset("error cases"):
        with test_raises(ValueError, "@looped: should detect invalid definition, no loop parameter"):
            @looped
            def s():
                pass

        with test_raises(ValueError, "@looped: should detect invalid definition, extra parameter not initialized"):
            @looped
            def s(loop, myextra):
                pass

        with test_raises(ValueError, "@looped_over: should detect invalid definition, no (loop, x, acc) parameters for loop body"):
            @looped_over(range(10), acc=())
            def s():
                pass

        with test_raises(ValueError, "@looped_over: should detect invalid definition, no acc parameter for loop body"):
            @looped_over(range(10), acc=())
            def s(loop, x):
                pass

        with test_raises(ValueError, "@looped_over: should detect invalid definition, extra parameter not initialized"):
            @looped_over(range(10), acc=())
            def s(loop, x, acc, myextra):
                pass

    with testset("FP loop over iterable"):
        @looped_over(zip((1, 2, 3), ('a', 'b', 'c')), acc=())
        def p(loop, item, acc):
            numb, lett = item  # unpack here, in body
            return loop(acc + ("{:d}{:s}".format(numb, lett),))
        test[p == ('1a', '2b', '3c')]

        @looped_over(enumerate(zip((1, 2, 3), ('a', 'b', 'c'))), acc=())
        def q(loop, item, acc):
            idx, (numb, lett) = item
            return loop(acc + ("Item {:d}: {:d}{:s}".format(idx, numb, lett),))
        test[q == ('Item 0: 1a', 'Item 1: 2b', 'Item 2: 3c')]

    with testset("nested FP loops over collections"):
        @looped_over(range(1, 4), acc=[])
        def outer_result(outer_loop, y, outer_acc):
            @looped_over(range(1, 3), acc=[])
            def inner_result(inner_loop, x, inner_acc):
                return inner_loop(inner_acc + [y * x])
            return outer_loop(outer_acc + [inner_result])
        test[outer_result == [[1, 2], [2, 4], [3, 6]]]

    with testset("building map, filter, reduce, custom constructs out of FP loops"):
        def map_fp_raw(function, iterable):
            it = iter(iterable)
            @looped
            def out(loop, acc=()):
                try:
                    x = next(it)
                    return loop(acc + (function(x),))
                except StopIteration:
                    return acc
            return out
        test[map_fp_raw(lambda x: 2 * x, range(5)) == (0, 2, 4, 6, 8)]

        # This looks much clearer with @looped_over:
        @looped_over(range(10), acc=0)
        def s(loop, x, acc):
            return loop(acc + x)
        test[s == 45]

        # So map simplifies to:
        def map_fp(function, iterable):
            @looped_over(iterable, acc=())
            def out(loop, x, acc):  # body always takes at least these three parameters, in this order
                return loop(acc + (function(x),))  # first argument is the new value of acc
            return out
        test[map_fp(lambda x: 2 * x, range(5)) == (0, 2, 4, 6, 8)]

        # Similarly, filter:
        def filter_fp(predicate, iterable):
            predicate = predicate or (lambda x: x)  # None -> truth value test
            @looped_over(iterable, acc=())
            def out(loop, x, acc):
                if not predicate(x):
                    return loop(acc)
                return loop(acc + (x,))
            return out
        test[filter_fp(lambda x: x % 2 == 0, range(10)) == (0, 2, 4, 6, 8)]

        # Similarly, reduce (a.k.a. foldl):
        def reduce_fp(function, iterable, initial=None):  # foldl
            it = iter(iterable)
            if initial is None:
                try:
                    initial = next(it)
                except StopIteration:
                    return None  # empty iterable
            @looped_over(it, acc=initial)  # either all elements, or all but first
            def out(loop, x, acc):
                return loop(function(acc, x))
            return out
        add = lambda acc, elt: acc + elt
        test[reduce_fp(add, range(10), 0) == 45]
        test[reduce_fp(add, (), 0) == 0]
        test[reduce_fp(add, ()) is None]

        # We can also define new looping constructs.
        #
        # A simple tuple comprehension:
        def collect_over(iterable, filter=None):  # parameterized decorator
            doit = looped_over(iterable, acc=())
            def run(body):
                if filter is None:
                    def comprehend_one(loop, x, acc):  # loop body for looped_over
                        return loop(acc + (body(x),))
                else:
                    def comprehend_one(loop, x, acc):
                        return loop(acc + (body(x),)) if filter(x) else loop()
                return doit(comprehend_one)
            return run
        @collect_over(range(10))
        def result(x):  # the comprehension body (do what to one element)
            return x**2
        test[result == (0, 1, 4, 9, 16, 25, 36, 49, 64, 81)]
        @collect_over(range(10), filter=lambda x: x % 2 == 0)
        def result(x):
            return x**2
        test[result == (0, 4, 16, 36, 64)]

        # Left fold, like reduce_fp above (same semantics as in functools.reduce):
        def fold_over(iterable, initial=None):
            def run(function):
                it = iter(iterable)
                nonlocal initial
                if initial is None:
                    try:
                        initial = next(it)
                    except StopIteration:
                        return None  # empty iterable
                doit = looped_over(it, acc=initial)
                def comprehend_one(loop, x, acc):
                    return loop(function(acc, x))  # op(acc, elt) like functools.reduce
                return doit(comprehend_one)
            return run
        @fold_over(range(1, 5))
        def result(acc, elt):
            return acc * elt
        test[result == 24]

    with testset("the old chestnut"):
        funcs = []
        for i in range(3):
            funcs.append(lambda x: i * x)  # always the same "i", which "for" just mutates
        test[[f(10) for f in funcs] == [20, 20, 20]]  # not what we wanted!

        # with FP loop:
        @looped_over(range(3), acc=())
        def funcs(loop, i, acc):
            return loop(acc + ((lambda x: i * x),))  # new "i" each time, no mutation!
        test[[f(10) for f in funcs] == [0, 10, 20]]  # yes!

        # using the more primitive @looped:
        funcs = []
        @looped
        def _ignored2(loop, i=0):
            if i < 3:
                funcs.append(lambda x: i * x)  # new "i" each time, no mutation!
                return loop(i + 1)
        test[[f(10) for f in funcs] == [0, 10, 20]]  # yes!

        # comprehension versions:
        funcs = [lambda x: i * x for i in range(3)]
        test[[f(10) for f in funcs] == [20, 20, 20]]  # not what we wanted!

        @collect_over(range(3))
        def funcs(i):
            return lambda x: i * x
        test[[f(10) for f in funcs] == [0, 10, 20]]  # yes!

        # though to be fair, the standard solution:
        funcs = [(lambda j: (lambda x: j * x))(i) for i in range(3)]
        test[[f(10) for f in funcs] == [0, 10, 20]]  # yes!

        # can be written as:
        def body(i):
            return lambda x: i * x
        funcs = [body(i) for i in range(3)]  # the call grabs the current value of "i".
        test[[f(10) for f in funcs] == [0, 10, 20]]  # yes!

    with testset("loop in a lambda, with TCO"):
        s = looped(lambda loop, acc=0, i=0:
                     loop(acc + i, i + 1) if i < 10 else acc)
        test[s == 45]

        # The same, using "let" to define a "cont":
        s = looped(lambda loop, acc=0, i=0:
                     let(cont=lambda newacc=acc:
                                loop(newacc, i + 1),
                         body=lambda e:
                                e.cont(acc + i) if i < 10 else acc))
        test[s == 45]

        # We can also use such expressions locally, like "s" here:
        result = let(s=looped(lambda loop, acc=0, i=0:
                                let(cont=lambda newacc=acc:
                                           loop(newacc, i + 1),
                                    body=lambda e:
                                           e.cont(acc + i) if i < 10 else acc)),
                     body=lambda e:
                            begin(print("s is {:d}".format(e.s)),
                                  2 * e.s))
        test[result == 90]

        # but for readability, we can do the same more pythonically:
        @call
        def result():
            @looped
            def s(loop, acc=0, i=0):
                cont = lambda newacc=acc: loop(newacc, i + 1)
                if i >= 10:
                    return acc
                return cont(acc + i)
            print("s is {:d}".format(s))
            return 2 * s
        test[result == 90]

    with testset("how to terminate surrounding function from inside loop"):
        # Use the lispy throw/catch:
        @catch()
        def f():
            @looped
            def s(loop, acc=0, i=0):
                if i > 5:
                    throw(acc)
                return loop(acc + i, i + 1)
            fail["This line should not be reached."]
            return False
        test[f() == 15]

        # Use tagged throws to control where the escape is sent.
        #
        # Catch point tags can be single value or tuple.
        # Tuples are OR'd, like in `isinstance`.
        @catch(tags="foo")
        def foo():
            @call
            @catch(tags="bar")
            def bar():
                @looped
                def s(loop, acc=0, i=0):
                    if i > 5:
                        throw(acc, tag="foo")  # Throw instance tag must be a single value.
                    return loop(acc + i, i + 1)
                fail["This line should not be reached."]
                return False
            fail["This line should not be reached."]
            return False
        test[foo() == 15]

    with testset("break, continue"):
        # break
        @breakably_looped
        def result(loop, brk, acc=0, i=0):
            if i == 10:
                return brk(acc)
            return loop(acc + i, i + 1)  # provide the additional parameters
        test[result == 45]

        # break, continue
        @breakably_looped_over(range(100), acc=0)
        def s(loop, x, acc, cnt, brk):
            if x < 5:
                return cnt()  # trampolined jump; default newacc=acc
            if x >= 10:
                return brk(acc)  # escape; must specify return value
            return loop(acc + x)
        test[s == 35]

        @breakably_looped_over(range(100), acc=0)
        def s(loop, x, acc, cnt, brk):
            if x >= 10:
                return brk(acc)
            if x > 5:
                return cnt()
            return loop(acc + x)
        test[s == 15]

    # TODO: need some kind of benchmarking tools to do this properly.
    with testset("performance benchmark"):
        n = 100000

        with timer() as ip:
            for i in range(n):
                pass

        with timer() as fp2:
            @looped
            def _ignored3(loop, i=0):
                if i < n:
                    return loop(i + 1)

        with timer() as fp3:
            @looped_over(range(n))  # no need for acc, not interested in it
            def _ignored4(loop, x, acc):    # but body always takes at least these three parameters
                return loop()

        print("do-nothing loop, {:d} iterations:".format(n))
        print("  builtin for {:g}s ({:g}s/iter)".format(ip.dt, ip.dt / n))
        print("  @looped {:g}s ({:g}s/iter)".format(fp2.dt, fp2.dt / n))
        print("  @looped_over {:g}s ({:g}s/iter)".format(fp3.dt, fp3.dt / n))
        print("@looped slowdown {:g}x".format(fp2.dt / ip.dt))
        print("@looped_over slowdown {:g}x".format(fp3.dt / ip.dt))

if __name__ == '__main__':  # pragma: no cover
    with session(__file__):
        runtests()
