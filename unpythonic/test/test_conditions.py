# -*- coding: utf-8 -*-

from ..conditions import signal, invoke_restart, restarts, handlers
from ..misc import raisef
from ..collections import box, unbox

def test():
    # basic usage
    def lowlevel():
        # low-level logic - define here what actions are available when stuff goes wrong
        with restarts(use_value=(lambda x: x),
                      double=(lambda x: 2 * x),
                      bail=(lambda x: raisef(ValueError, x))):
            out = []
            for k in range(10):
                # Silly example: let's pretend we only want to deal with even
                # numbers. We consider odd numbers so exceptional we should let
                # the caller decide which action to take when we see one.
                result = k if k % 2 == 0 else signal("odd_number", k)
                out.append(result)
            return out

    # high-level logic - choose here which action the low-level logic should take
    # for each named signal (here we only have one signal, named "odd_number")
    with handlers(odd_number=(lambda x: invoke_restart("use_value", x))):
        assert lowlevel() == list(range(10))

    with handlers(odd_number=(lambda x: invoke_restart("double", x))):
        assert lowlevel() == [0, 2 * 1, 2, 2 * 3, 4, 2 * 5, 6, 2 * 7, 8, 2 * 9]

    try:
        with handlers(odd_number=(lambda x: invoke_restart("bail", x))):
            lowlevel()
    except ValueError as err:
        assert str(err) == "1"

    # name shadowing: dynamically the most recent binding of the same restart name wins
    def lowlevel2():
        out = []
        with restarts(r=(lambda x: x)):
            out.append(signal("help_me", 21))
            # here this is lexically nested, too, but could be in a separate function.
            with restarts(r=(lambda x: 2 * x)):
                out.append(signal("help_me", 21))
        return out
    with handlers(help_me=(lambda x: invoke_restart("r", x))):
        assert lowlevel2() == [21, 42]

    # cancel-and-delegate
    def lowlevel3():
        with restarts(use_value=(lambda x: x)):
            return signal("help_me", 42)

    # if the inner handler returns normally, the outer handler takes over
    # (note any side effects of the inner handler remain in effect)
    inner_handler_ran = box(False)  # use a box so we can rebind the value from inside a lambda
    outer_handler_ran = box(False)
    with handlers(help_me=(lambda x: [outer_handler_ran.set(True),
                                      invoke_restart("use_value", x)])):
        with handlers(help_me=(lambda x: [inner_handler_ran.set(True),
                                          None])):  # return normally from handler to cancel-and-delegate
            assert lowlevel3() == 42
            assert unbox(inner_handler_ran) is True
            assert unbox(outer_handler_ran) is True

    # if the inner handler invokes a restart, the outer handler doesn't run
    inner_handler_ran = box(False)
    outer_handler_ran = box(False)
    with handlers(help_me=(lambda x: [outer_handler_ran.set(True),
                                      invoke_restart("use_value", x)])):
        with handlers(help_me=(lambda x: [inner_handler_ran.set(True),
                                          invoke_restart("use_value", x)])):
            assert lowlevel3() == 42
            assert unbox(inner_handler_ran) is True
            assert unbox(outer_handler_ran) is False

    # TODO: test multithreading (threads should behave independently)

    print("All tests PASSED")

if __name__ == '__main__':
    test()
