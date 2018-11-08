# -*- coding: utf-8 -*-

from sys import stderr

from ..tco import trampolined, jump, SELF

from ..let import letrec

def test():
    # tail recursion
    @trampolined
    def fact(n, acc=1):
        if n == 0:
            return acc
        return jump(fact, n - 1, n * acc)
    assert fact(4) == 24

    # tail recursion in a lambda
    t = trampolined(lambda n, acc=1:
                        acc if n == 0 else jump(SELF, n - 1, n * acc))
    assert t(4) == 24

    # mutual recursion
    @trampolined
    def even(n):
        if n == 0:
            return True
        return jump(odd, n - 1)
    @trampolined
    def odd(n):
        if n == 0:
            return False
        return jump(even, n - 1)
    assert even(42) is True
    assert odd(4) is False
    assert even(10000) is True  # no crash

    # explicit continuations - DANGER: functional spaghetti code!
    @trampolined
    def foo():
        return jump(bar)
    @trampolined
    def bar():
        return jump(baz)
    @trampolined
    def baz():
        raise RuntimeError("Look at the call stack, bar() was zapped by TCO!")
    try:
        foo()
    except RuntimeError:
        pass

    # trampolined lambdas in a letrec
    t = letrec(evenp=lambda e:
                     trampolined(lambda x:
                                   (x == 0) or jump(e.oddp, x - 1)),
             oddp=lambda e:
                     trampolined(lambda x:
                                   (x != 0) and jump(e.evenp, x - 1)),
             body=lambda e:
                     e.evenp(10000))
    assert t is True

    print("All tests PASSED")

    print("*** These two error cases SHOULD PRINT A WARNING:", file=stderr)
    print("** No surrounding trampoline:", file=stderr)
    def bar2():
        pass
    def foo2():
        return jump(bar2)
    foo2()
    print("** Missing 'return' in 'return jump':", file=stderr)
    def foo3():
        jump(bar2)
    foo3()

    # loop performance?
    n = 100000
    import time

    t0 = time.time()
    for _ in range(n):
        pass
    dt_ip = time.time() - t0

    t0 = time.time()
    @trampolined
    def dowork(i=0):
        if i < n:
            return jump(dowork, i + 1)
    dowork()
    dt_fp1 = time.time() - t0

    print("do-nothing loop, {:d} iterations:".format(n))
    print("  builtin for {:g}s ({:g}s/iter)".format(dt_ip, dt_ip/n))
    print("  @trampolined {:g}s ({:g}s/iter)".format(dt_fp1, dt_fp1/n))
    print("@trampolined slowdown {:g}x".format(dt_fp1/dt_ip))

if __name__ == '__main__':
    test()
