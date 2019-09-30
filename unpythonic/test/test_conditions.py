# -*- coding: utf-8 -*-

from ..conditions import signal, invoke_restart, restarts, handlers
from ..misc import raisef

def test():
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

    # TODO: test name shadowing (dynamically the most recent binding of the same restart name wins)
    # TODO: test cancel-and-delegate
    # TODO: test multithreading (threads should behave independently)

    print("All tests PASSED")

if __name__ == '__main__':
    test()
