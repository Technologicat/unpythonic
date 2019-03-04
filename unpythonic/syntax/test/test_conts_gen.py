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

from ...syntax import macros, continuations, call_cc, dlet, abbrev, let_syntax, block

from ...fploop import looped
from ...fun import identity

from macropy.tracing import macros, show_expanded

def test():
    # a basic generator
    with continuations:
        # logic to resume after the last executed my_yield, if any
        @dlet((k, None))
        def g():
            if k:
                return k()
            def my_yield(value, cc):
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
        def g():
            if k:
                return k()
            def my_yield(value, cc):
                k << cc
                cc = identity
                return value
            # generator body
            @looped
            def result(loop, i=0):
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

    # A basic generator template using abbrev[].
    with continuations:
        # We must expand abbreviations in the first pass, before the @dlet that's
        # not part of the template (since we splice in stuff that is intended to
        # refer to the "k" in the @dlet env). So use abbrev[] instead of let_syntax[].
        with abbrev:
            with block(value) as my_yield:
                call_cc[my_yieldf(value)]  # for this to work, abbrev[] must eliminate its "if 1" blocks.
            with block as begin_generator_body:
                # logic to resume after the last executed my_yield, if any
                if k:
                    return k()
                def my_yieldf(value, cc):
                    k << cc
                    cc = identity
                    return value

            @dlet((k, None))  # <-- we must still remember this line
            def g():
                begin_generator_body
                my_yield(1)
                my_yield(2)
                my_yield(3)

            out = []
            x = g()
            while x is not None:
                out.append(x)
                x = g()
            assert out == [1, 2, 3]

    # With some gymnastics we can make a template that includes the @dlet:
    with continuations:
        # Now we can use let_syntax, since the @dlet is part of the code being spliced
        # and the user code (generator body) doesn't refer to k directly.
        # (So "k" can be resolved lexically *in the input source code that goes to dlet[]*.)
        with let_syntax:
            with block(value) as my_yield:
                call_cc[my_yieldf(value)]  # for this to work, let_syntax[] must eliminate its "if 1" blocks.
            with block(myname, body) as make_generator:
                @dlet((k, None))
                def myname():  # replaced by the user-supplied name, since "myname" is a template parameter.
                    # logic to resume after the last executed my_yield, if any
                    if k:
                        return k()
                    def my_yieldf(value, cc):
                        k << cc
                        cc = identity
                        return value
                    body

            # We must define the body as an abbrev block to give it a name,
            # because template arguments must be expressions (and a name is,
            # but a literal block of code isn't).
            #
            # This user-defined body gets spliced in after the make_generator
            # template itself has expanded.
            with block as mybody:
                my_yield(1)
                my_yield(2)
                my_yield(3)
            make_generator(g, mybody)

            out = []
            x = g()
            while x is not None:
                out.append(x)
                x = g()
            assert out == [1, 2, 3]

            # Let's remake the FP loop based generator example using this version.
            with block as mybody2:
                @looped
                def result(loop, i=0):
                    my_yield(i)
                    return loop(i+1)
                return result
            make_generator(g2, mybody2)

            out = []
            x = g2()
            while x < 10:
                out.append(x)
                x = g2()
            assert out == list(range(10))

    # Unfortunately, this is as far as let_syntax[] gets us; if we wanted to
    # "librarify" this any further, we'd need to define a macro in MacroPy.
    #
    # (Suggestions: make_generator as a decorator macro; my_yield[] as a special
    # literal Subscript that make_generator understands and expands away. At the
    # module level, define my_yield as a @macro_stub so that accidental uses
    # outside any make_generator are caught at runtime. The actual template the
    # make_generator macro needs to splice in is already here in the final example.)

    print("All tests PASSED")

if __name__ == '__main__':
    test()
