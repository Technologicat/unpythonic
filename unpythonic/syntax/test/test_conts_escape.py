# -*- coding: utf-8 -*-
"""Using continuations as an escape mechanism."""

from ...syntax import macros, test  # noqa: F401
from ...test.fixtures import session, testset

from ...syntax import macros, tco, continuations, call_cc  # noqa: F401, F811
from ...ec import call_ec

def runtests():
    # basic strategy using an escape continuation
    with testset("basic ec"):
        def double_odd(x, ec):
            if x % 2 == 0:  # reject even "x"
                ec("not odd")
            return 2 * x
        @call_ec
        def result1(ec):
            y = double_odd(42, ec)  # noqa: F841, this is just a silly example for testing.
            z = double_odd(21, ec)  # pragma: no cover, should not be reached.
            return z  # pragma: no cover, should not be reached.
        @call_ec
        def result2(ec):
            y = double_odd(21, ec)  # noqa: F841, this is just a silly example for testing.
            z = double_odd(42, ec)
            return z  # pragma: no cover, should not be reached.
        test[result1 == "not odd"]
        test[result2 == "not odd"]

    # should work also in a "with tco" block
    with testset("basic ec in a TCO block"):
        with tco:
            def double_odd(x, ec):  # noqa: F811, the previous one is no longer used.
                if x % 2 == 0:  # reject even "x"
                    ec("not odd")
                return 2 * x
            @call_ec
            def result1(ec):
                y = double_odd(42, ec)  # noqa: F841, this is just a silly example for testing.
                z = double_odd(21, ec)  # avoid tail-calling because ec is not valid after result1() exits  # pragma: no cover, should not be reached.
                return z  # pragma: no cover, should not be reached.
            @call_ec
            def result2(ec):
                y = double_odd(21, ec)  # noqa: F841, this is just a silly example for testing.
                z = double_odd(42, ec)
                return z  # pragma: no cover, should not be reached.
            test[result1 == "not odd"]
            test[result2 == "not odd"]

    # can we do this using the **continuations** machinery?
    with testset("continuations idea"):
        with continuations:
            def double_odd(x, ec, cc):  # noqa: F811, the previous one is no longer used.
                if x % 2 == 0:
                    cc = ec  # try to escape by overriding cc...  # noqa: F841
                    return "not odd"
                return 2 * x
            def main1(cc):
                # cc actually has a default, so it's ok to not pass anything as cc here.
                y = double_odd(42, ec=cc)  # y = "not odd"  # noqa: F841, this is just a silly example for testing.
                z = double_odd(21, ec=cc)  # we could tail-call, but let's keep this similar to the first example.
                return z
            def main2(cc):
                y = double_odd(21, ec=cc)  # noqa: F841, this is just a silly example for testing.
                z = double_odd(42, ec=cc)
                return z
            # ...but no call_cc[] anywhere, so cc is actually always
            # unpythonic.fun.identity, cannot perform an escape.
            test[main1() == 42]
            test[main2() == "not odd"]

    # to fix that, let's call_cc[]:
    with testset("continuations implementation"):
        with continuations:
            def double_odd(x, ec, cc):  # noqa: F811, the previous one is no longer used.
                if x % 2 == 0:
                    cc = ec  # escape by overriding cc (now it works!)  # noqa: F841
                    return "not odd"
                return 2 * x
            def main1(cc):
                y = call_cc[double_odd(42, ec=cc)]  # noqa: F841, this is just a silly example for testing.
                z = call_cc[double_odd(21, ec=cc)]  # pragma: no cover, should not be reached.
                return z  # pragma: no cover, should not be reached.
            def main2(cc):
                y = call_cc[double_odd(21, ec=cc)]  # noqa: F841, this is just a silly example for testing.
                z = call_cc[double_odd(42, ec=cc)]
                return z  # pragma: no cover, should not be reached.
            # call_cc[] captures the actual cont, so now this works as expected.
            test[main1() == "not odd"]
            test[main2() == "not odd"]

    # In each case, the second call_cc[] is actually redundant, because after
    # the second call to double_odd(), there is no more code to run in each
    # main function.
    #
    # We can just as well use a tail-call, optimizing away a redundant
    # continuation capture:
    with testset("small optimization"):
        with continuations:
            def double_odd(x, ec, cc):  # noqa: F811, the previous one is no longer used
                if x % 2 == 0:
                    cc = ec  # noqa: F841
                    return "not odd"
                return 2 * x
            def main1(cc):
                y = call_cc[double_odd(42, ec=cc)]  # noqa: F841, this is just a silly example for testing.
                return double_odd(21, ec=cc)  # tail call, no further code to run in main1 so no call_cc needed.  # pragma: no cover, should not be reached.
            def main2(cc):
                y = call_cc[double_odd(21, ec=cc)]  # noqa: F841, this is just a silly example for testing.
                return double_odd(42, ec=cc)
            test[main1() == "not odd"]
            test[main2() == "not odd"]

if __name__ == '__main__':  # pragma: no cover
    with session(__file__):
        runtests()
