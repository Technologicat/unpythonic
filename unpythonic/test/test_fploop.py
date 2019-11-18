# -*- coding: utf-8 -*-

from ..fploop import looped, looped_over, breakably_looped, breakably_looped_over
from ..tco import trampolined, jump

from ..let import let
from ..seq import begin
from ..misc import call, timer
from ..ec import setescape, escape

def test():
    # basic usage
    #
    @looped
    def s(loop, acc=0, i=0):
        if i == 10:
            return acc  # there's no "break"; loop terminates at the first normal return
        # same as return jump(s, acc+i, i+1), but sets up the "loop" arg.
        return loop(acc + i, i + 1)
    assert s == 45

    # equivalent to:
    @trampolined
    def dowork(acc=0, i=0):
        if i == 10:
            return acc
        return jump(dowork, acc + i, i + 1)
    s = dowork()  # when using just @trampolined, must start the loop manually
    assert s == 45

    # error cases
    try:
        @looped
        def s():  # invalid definition, no loop parameter
            pass
    except ValueError:
        pass
    else:
        assert False

    try:
        @looped
        def s(loop, myextra):  # invalid definition, extra parameter not initialized
            pass
    except ValueError:
        pass
    else:
        assert False

    try:
        @looped_over(range(10), acc=())
        def s():  # invalid definition, no (loop, x, acc)
            pass
    except ValueError:
        pass
    else:
        assert False

    try:
        @looped_over(range(10), acc=())
        def s(loop, x):  # invalid definition, no acc
            pass
    except ValueError:
        pass
    else:
        assert False

    try:
        @looped_over(range(10), acc=())
        def s(loop, x, acc, myextra):  # invalid definition, myextra not initialized
            pass
    except ValueError:
        pass
    else:
        assert False

    # impure FP loop - side effects:
    out = []
    @looped
    def _ignored1(loop, i=0):
        if i < 3:
            out.append(i)
            return loop(i + 1)
        # the implicit "return None" terminates the loop.
    assert out == [0, 1, 2]

    # same without using side effects - use an accumulator parameter:
    @looped
    def out(loop, i=0, acc=[]):
        if i >= 3:
            return acc
        acc.append(i)
        return loop(i + 1)
    assert out == [0, 1, 2]

    # there's no "continue"; package your own:
    @looped
    def s(loop, acc=0, i=0):
        cont = lambda newacc=acc: loop(newacc, i + 1)
        if i == 10:
            return acc
        elif i <= 4:
            return cont()
        return cont(acc + i)
    assert s == 35

    # FP loop over iterable
    @looped_over(zip((1, 2, 3), ('a', 'b', 'c')), acc=())
    def p(loop, item, acc):
        numb, lett = item  # unpack here, in body
        return loop(acc + ("{:d}{:s}".format(numb, lett),))
    assert p == ('1a', '2b', '3c')

    @looped_over(enumerate(zip((1, 2, 3), ('a', 'b', 'c'))), acc=())
    def q(loop, item, acc):
        idx, (numb, lett) = item
        return loop(acc + ("Item {:d}: {:d}{:s}".format(idx, numb, lett),))
    assert q == ('Item 0: 1a', 'Item 1: 2b', 'Item 2: 3c')

    # nested FP loops over collections
    @looped_over(range(1, 4), acc=[])
    def outer_result(outer_loop, y, outer_acc):
        @looped_over(range(1, 3), acc=[])
        def inner_result(inner_loop, x, inner_acc):
            return inner_loop(inner_acc + [y * x])
        return outer_loop(outer_acc + [inner_result])
    assert outer_result == [[1, 2], [2, 4], [3, 6]]

    # We can also FP loop over an iterable like this:
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
    assert map_fp_raw(lambda x: 2 * x, range(5)) == (0, 2, 4, 6, 8)

    # But it looks much clearer with @looped_over:
    @looped_over(range(10), acc=0)
    def s(loop, x, acc):
        return loop(acc + x)
    assert s == 45

    # So map simplifies to:
    def map_fp(function, iterable):
        @looped_over(iterable, acc=())
        def out(loop, x, acc):  # body always takes at least these three parameters, in this order
            return loop(acc + (function(x),))  # first argument is the new value of acc
        return out
    assert map_fp(lambda x: 2 * x, range(5)) == (0, 2, 4, 6, 8)

    # similarly
    def filter_fp(predicate, iterable):
        predicate = predicate or (lambda x: x)  # None -> truth value test
        @looped_over(iterable, acc=())
        def out(loop, x, acc):
            if not predicate(x):
                return loop(acc)
            return loop(acc + (x,))
        return out
    assert filter_fp(lambda x: x % 2 == 0, range(10)) == (0, 2, 4, 6, 8)

    # similarly
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
    assert reduce_fp(add, range(10), 0) == 45
    assert reduce_fp(add, (), 0) == 0
    assert reduce_fp(add, ()) is None

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
    assert result == (0, 1, 4, 9, 16, 25, 36, 49, 64, 81)
    @collect_over(range(10), filter=lambda x: x % 2 == 0)
    def result(x):
        return x**2
    assert result == (0, 4, 16, 36, 64)

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
    assert result == 24

    # This old chestnut:
    funcs = []
    for i in range(3):
        funcs.append(lambda x: i * x)  # always the same "i", which "for" just mutates
    assert [f(10) for f in funcs] == [20, 20, 20]  # not what we wanted!

    # with FP loop:
    @looped_over(range(3), acc=())
    def funcs(loop, i, acc):
        return loop(acc + ((lambda x: i * x),))  # new "i" each time, no mutation!
    assert [f(10) for f in funcs] == [0, 10, 20]  # yes!

    # using the more primitive @looped:
    funcs = []
    @looped
    def _ignored2(loop, i=0):
        if i < 3:
            funcs.append(lambda x: i * x)  # new "i" each time, no mutation!
            return loop(i + 1)
    assert [f(10) for f in funcs] == [0, 10, 20]  # yes!

    # comprehension versions:
    funcs = [lambda x: i * x for i in range(3)]
    assert [f(10) for f in funcs] == [20, 20, 20]  # not what we wanted!

    @collect_over(range(3))
    def funcs(i):
        return lambda x: i * x
    assert [f(10) for f in funcs] == [0, 10, 20]  # yes!

    # though to be fair, the standard solution:
    funcs = [(lambda j: (lambda x: j * x))(i) for i in range(3)]
    assert [f(10) for f in funcs] == [0, 10, 20]  # yes!

    # can be written as:
    def body(i):
        return lambda x: i * x
    funcs = [body(i) for i in range(3)]  # the call grabs the current value of "i".
    assert [f(10) for f in funcs] == [0, 10, 20]  # yes!

    # FP loop in a lambda, with TCO:
    s = looped(lambda loop, acc=0, i=0:
                 loop(acc + i, i + 1) if i < 10 else acc)
    assert s == 45

    # The same, using "let" to define a "cont":
    s = looped(lambda loop, acc=0, i=0:
                 let(cont=lambda newacc=acc:
                            loop(newacc, i + 1),
                     body=lambda e:
                            e.cont(acc + i) if i < 10 else acc))
    assert s == 45

    # We can also use such expressions locally, like "s" here:
    result = let(s=looped(lambda loop, acc=0, i=0:
                            let(cont=lambda newacc=acc:
                                       loop(newacc, i + 1),
                                body=lambda e:
                                       e.cont(acc + i) if i < 10 else acc)),
                 body=lambda e:
                        begin(print("s is {:d}".format(e.s)),
                              2 * e.s))
    assert result == 90

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
    assert result == 90

    # How to terminate surrounding function from inside FP loop:
    @setescape()
    def f():
        @looped
        def s(loop, acc=0, i=0):
            if i > 5:
                escape(acc)
            return loop(acc + i, i + 1)
        print("not reached")
        return False
    assert f() == 15

    # tagged escapes to control where the escape is sent:
    #
    # setescape point tags can be single value or tuple (tuples OR'd, like isinstance())
    @setescape(tags="foo")
    def foo():
        @call
        @setescape(tags="bar")
        def bar():
            @looped
            def s(loop, acc=0, i=0):
                if i > 5:
                    escape(acc, tag="foo")  # escape instance tag must be a single value
                return loop(acc + i, i + 1)
            print("never reached")
            return False
        print("never reached either")
        return False
    assert foo() == 15

    # break
    @breakably_looped
    def result(loop, brk, acc=0, i=0):
        if i == 10:
            return brk(acc)
        return loop(acc + i, i + 1)  # provide the additional parameters
    assert result == 45

    # break, continue
    @breakably_looped_over(range(100), acc=0)
    def s(loop, x, acc, cnt, brk):
        if x < 5:
            return cnt()  # trampolined jump; default newacc=acc
        if x >= 10:
            return brk(acc)  # escape; must specify return value
        return loop(acc + x)
    assert s == 35

    @breakably_looped_over(range(100), acc=0)
    def s(loop, x, acc, cnt, brk):
        if x >= 10:
            return brk(acc)
        if x > 5:
            return cnt()
        return loop(acc + x)
    assert s == 15

    print("All tests PASSED")

    # loop performance?
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

if __name__ == '__main__':
    test()
