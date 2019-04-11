# -*- coding: utf-8 -*-

from ...syntax import macros, nb, dbg, pop_while
from ...misc import call

def test():
    with nb:
        assert _ is None
        2 + 3          # top-level expressions autoprint, and auto-assign result to _
        assert _ == 5  # ...and only expressions do that, so...
        _ * 42         # ...here _ still has the value from the first line.
        assert _ == 210

    try:
        from sympy import symbols, pprint
    except ImportError:
        print("*** SymPy not installed, skipping symbolic math test ***")
    else:
        with nb(pprint):  # you can specify a custom print function (first positional arg)
            assert _ is None
            x, y = symbols("x, y")
            x * y
            assert _ == x * y
            3 * _
            assert _ == 3 * x * y

    with dbg:
        x = 2
        y = 3
        print(x, y, 17 + 23)

    prt = lambda *args, **kwargs: print(*args)
    with dbg(prt):  # can specify a custom print function
        x = 2
        prt(x)    # transformed
        print(x)  # not transformed, because custom print function specified

    with dbg(prt):
        x = 2
        y = 3
        prt(x, y, 17 + 23)

    # now for some proper unit testing
    prt = lambda *args, **kwargs: args
    with dbg(prt):
        x = 2
        assert prt(x) == (("x",), (2,))

        x = 2
        y = 3
        assert prt(x, y, 17 + 23) == (("x", "y", "(17 + 23)"), (2, 3, 40))

    # the expression variant can be used in any expression position
    x = dbg[25 + 17]
    assert x == 42

    # Customize the expression debug printer.
    #
    # Here must be done in a different scope, so that the above use of dbg[]
    # resolves to the global default dbgprint_expr, and this test to the
    # local customized dbgprint_expr.
    @call
    def just_a_scope():
        dbgprint_expr = lambda *args, **kwargs: args
        x = dbg[2 + 3]
        assert x == ("(2 + 3)", 5)

    # silly imperative pop-while construct for handling lists in cases
    # where the body needs to append to or extend the input (so that a
    # for-loop is not appropriate)
    lst1 = list(range(5))
    lst2 = []
    with pop_while(lst1):
        lst2.append(it)
    assert lst1 == []
    assert lst2 == list(range(5))

    lst1 = list(range(5))
    lst2 = []
    with pop_while(lst1):
        lst2.append(it)
        if it == 4:
            lst1.append(5)
    assert lst1 == []
    assert lst2 == list(range(6))

    lst2 = []
    with pop_while(list(range(5))) as mylist:
        lst2.append(it)
        if it == 4:
            mylist.append(5)
    assert mylist == []
    assert lst2 == list(range(6))

    # hmm? Maybe no macro needed?
    class popping_iterator:
        def __init__(self, seq):
            self.seq = seq
        def __iter__(self):
            return self
        def __next__(self):
            if not self.seq:
                raise StopIteration
            return self.seq.pop(0)

    lst1 = list(range(5))
    lst2 = []
    for x in popping_iterator(lst1):
        lst2.append(x)
    assert lst1 == []
    assert lst2 == list(range(5))

    lst1 = list(range(5))
    lst2 = []
    for x in popping_iterator(lst1):
        lst2.append(x)
        if x == 4:
            lst1.append(5)
    assert lst1 == []
    assert lst2 == list(range(6))

    # in this solution we can't as-name an expr on the fly, but maybe that feature is not needed.

    print("All tests PASSED")

if __name__ == '__main__':
    test()
