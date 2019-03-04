# -*- coding: utf-8 -*-
"""Using continuations as an escape mechanism."""

from ...syntax import macros, tco, continuations, call_cc
from ...ec import call_ec

def test():
    # basic strategy using an escape continuation
    def double_odd(x, ec):
        if x % 2 == 0:  # reject even "x"
            ec("not odd")
        return 2*x
    @call_ec
    def result1(ec):
        y = double_odd(42, ec)
        z = double_odd(21, ec)
        return z
    @call_ec
    def result2(ec):
        y = double_odd(21, ec)
        z = double_odd(42, ec)
        return z
    assert result1 == "not odd"
    assert result2 == "not odd"

    # should work also in a "with tco" block
    with tco:
        def double_odd(x, ec):
            if x % 2 == 0:  # reject even "x"
                ec("not odd")
            return 2*x
        @call_ec
        def result1(ec):
            y = double_odd(42, ec)
            z = double_odd(21, ec)  # avoid tail-calling because ec is not valid after result1() exits
            return z
        @call_ec
        def result2(ec):
            y = double_odd(21, ec)
            z = double_odd(42, ec)
            return z
        assert result1 == "not odd"
        assert result2 == "not odd"

    # can we do this using the **continuations** machinery?
    with continuations:
        def double_odd(x, ec, cc):
            if x % 2 == 0:
                cc = ec  # try to escape by overriding cc...
                return "not odd"
            return 2*x
        def main1(cc):
            # cc actually has a default, so it's ok to not pass anything as cc here.
            y = double_odd(42, ec=cc)  # y = "not odd"
            z = double_odd(21, ec=cc)  # we could tail-call, but let's keep this similar to the first example.
            return z
        def main2(cc):
            y = double_odd(21, ec=cc)
            z = double_odd(42, ec=cc)
            return z
        # ...but no call_cc[] anywhere, so cc is actually always
        # unpythonic.fun.identity, cannot perform an escape.
        assert main1() == 42
        assert main2() == "not odd"

    # to fix that, let's call_cc[]:
    with continuations:
        def double_odd(x, ec, cc):
            if x % 2 == 0:
                cc = ec  # escape by overriding cc (now it works!)
                return "not odd"
            return 2*x
        def main1(cc):
            y = call_cc[double_odd(42, ec=cc)]
            z = call_cc[double_odd(21, ec=cc)]
            return z
        def main2(cc):
            y = call_cc[double_odd(21, ec=cc)]
            z = call_cc[double_odd(42, ec=cc)]
            return z
        # call_cc[] captures the actual cont, so now this works as expected.
        assert main1() == "not odd"
        assert main2() == "not odd"

    # In each case, the second call_cc[] is actually redundant, because after
    # the second call to double_odd(), there is no more code to run in each
    # main function.
    #
    # We can just as well use a tail-call, optimizing away a redundant
    # continuation capture:
    with continuations:
        def double_odd(x, ec, cc):
            if x % 2 == 0:
                cc = ec
                return "not odd"
            return 2*x
        def main1(cc):
            y = call_cc[double_odd(42, ec=cc)]
            return double_odd(21, ec=cc)  # tail call, no further code to run in main1 so no call_cc needed.
        def main2(cc):
            y = call_cc[double_odd(21, ec=cc)]
            return double_odd(42, ec=cc)
        assert main1() == "not odd"
        assert main2() == "not odd"

    print("All tests PASSED")

if __name__ == '__main__':
    test()
