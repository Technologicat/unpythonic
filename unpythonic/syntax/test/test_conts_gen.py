# -*- coding: utf-8 -*-
"""Another possible use for call/cc: implementing generators.

(Of course, Python already has them, so no need to; this is just to show how.)

The trick is, in ``my_yield``, to "cut the tail", returning immediately with
the given value after stashing the continuation. This particular ``call_cc``
invocation never returns! (Although more accurate is to say that it does return,
immediately, with a value, ignoring all of this silly continuation business.)

Then, when someone calls ``g`` again, check if we have a stashed continuation,
and if so, then instead of executing normally, run that and return whatever
it returns. Because of how ``call_cc`` and continuations are defined,
this resumes just after the last executed ``my_yield``.

See also the Racket version of this:

    https://github.com/Technologicat/python-3-scicomp-intro/blob/master/examples/beyond_python/generator.rkt
"""

from ...syntax import macros, continuations, call_cc, dlet

from ...fploop import looped
from ...fun import identity

def test():
    # a basic generator
    with continuations:
        # logic to resume after the last executed my_yield, if any
        @dlet((k, None))
        def g(*, cc):
            if k:
                return k()
            def my_yield(value, *, cc):
                k << cc
                cc = identity
                return value
            # generator body
            call_cc[my_yield(1)]
            call_cc[my_yield(2)]
            call_cc[my_yield(3)]
        out = []
        x = g()
        while x is not None:
            out.append(x)
            x = g()
        assert out == [1, 2, 3]

    # an FP loop based generator
    # - the resume logic **must** be outside the looped part,
    #   otherwise we get stuck in an infinite loop.
    with continuations:
        # logic to resume after the last executed my_yield, if any
        @dlet((k, None))
        def g(*, cc):
            if k:
                return k()
            def my_yield(value, *, cc):
                k << cc
                cc = identity
                return value
            # generator body
            @looped
            def result(loop, i=0, *, cc):
                call_cc[my_yield(i)]
                return loop(i+1)
            # To actually return the value when the yield escapes, pass it along.
            #
            # Recall that my_yield effectively returns a value, the normal way,
            # ignoring continuations. Because the loop just shut down, @looped
            # receives this value, and writes it to "result".
            #
            # This shows the delimited nature of our continuations - the outermost
            # level where call_cc[] appears is the loop body, so exiting from the
            # continuation exits that, dumping control back to ``g``.
            #
            # With no ``cc`` set (at this level), this return just normally
            # returns the value.
            return result
        out = []
        x = g()
        while x < 10:
            out.append(x)
            x = g()
        assert out == list(range(10))

    print("All tests PASSED")
