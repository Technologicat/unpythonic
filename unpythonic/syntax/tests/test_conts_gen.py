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

from mcpyrate.multiphase import macros, phase

from ...syntax import macros, test, test_raises  # noqa: F401, F811
from ...test.fixtures import session, testset

from ...syntax import macros, continuations, call_cc, dlet, abbrev, let_syntax, block  # noqa: F401, F811

from ...fploop import looped
from ...fun import identity

from mcpyrate.debug import macros, step_expansion  # noqa: F811, F401

# TODO: pretty long, move into its own module
# Multishot generators can also be implemented using the pattern `k = call_cc[get_cc()]`.
#
# Because `with continuations` is a two-pass macro, it will first expand any
# `@multishot` inside the block before performing its own processing, which is
# exactly what we want.
#
# We could force the ordering with the metatool `mcpyrate.metatools.expand_first`
# added in `mcpyrate` 3.6.0, but we don't need to do that.
#
# To make these multi-shot generators support the most basic parts
# of the API of Python's native generators, make a wrapper object:
#
#  - `__iter__` on the original function should create the wrapper object
#    and initialize it. Maybe always inject a bare `myield` at the beginning
#    of a multishot function before other processing, and run the function
#    until it returns the initial continuation? This continuation can then
#    be stashed just like with any resume point.
#  - `__next__` needs a stash for the most recent continuation
#    per activation of the multi-shot generator. It should run
#    the most recent continuation (with no arguments) until the next `myield`,
#    stash the new continuation, and return the yielded value, if any.
#  - `send` should send a value into the most recent continuation
#    (thus resuming).
#  - When the function returns normally, without returning any further continuation,
#    the wrapper should `raise StopIteration`, providing the return value as argument
#    to the exception.
#
# Note that a full implementation of the generator API requires much
# more. We should at least support `close` and `throw`, and think hard
# about how to handle exceptions. Particularly, a `yield` inside a
# `finally` is a classic catch. This sketch also has no support for
# `yield from`; we would likely need our own `myield_from`.
with phase[1]:
    # TODO: relative imports
    # TODO: mcpyrate does not recognize current package in phases higher than 0? (parent missing)

    import ast
    from functools import partial
    import sys

    from mcpyrate.quotes import macros, q, n, a, h  # noqa: F811
    from unpythonic.syntax import macros, call_cc  # noqa: F811

    from mcpyrate import namemacro, gensym
    from mcpyrate.quotes import is_captured_value
    from mcpyrate.utils import extract_bindings
    from mcpyrate.walkers import ASTTransformer

    from unpythonic.syntax import get_cc, iscontinuation

    def myield_function(tree, syntax, **kw):
        """[syntax, name/expr] Yield from a multi-shot generator.

        For details, see `multishot`.
        """
        if syntax not in ("name", "expr"):
            raise SyntaxError("myield is a name and expr macro only")

        # Accept `myield` in any non-load context, so that we can below define the macro `myield`.
        #
        # This is only an issue, because this example uses multi-phase compilation.
        # The phase-1 `myield` is in the macro expander - preventing us from referring to
        # the name `myield` - when the lifted phase-0 definition is being run. During phase 0,
        # that makes the line `myield = namemacro(...)` below into a macro-expansion-time
        # syntax error, because that `myield` is not inside a `@multishot` generator.
        #
        # We hack around it, by allowing `myield` anywhere as long as the context is not a `Load`.
        if hasattr(tree, "ctx") and type(tree.ctx) is not ast.Load:
            return tree

        # `myield` is not really a macro, but a pattern that `multishot` looks for and compiles away.
        # Hence if any `myield` is left over and reaches the macro expander, it was placed incorrectly,
        # so we can raise an error at macro expansion time.
        raise SyntaxError("myield may only appear at the top level of a `@multishot` generator")
    myield = namemacro(myield_function)

    def multishot(tree, syntax, expander, **kw):
        """[syntax, block] Make a function into a multi-shot generator.

        Multi-shot yield is spelled `myield`. When using `multishot`, be sure to
        macro-import also `myield`, so that `multishot` knows which name you want
        to use to refer to the `myield` construct (it is automatically queried
        from the current expander's bindings).

        There are four variants::

            Multi-shot yield    Returns      `k` expects   Single-shot analog

            myield              k            no argument   yield
            myield[expr]        (k, value)   no argument   yield expr
            var = myield        k            one argument  var = yield
            var = myield[expr]  (k, value)   one argument  var = yield expr

        To resume, call the function `k`. In cases where `k` expects an argument,
        it is the value to send into `var`.

        Important differences:

          - A multi-shot generator may be resumed from any `myield` arbitrarily
            many times, in any order. There is no concept of a single paused
            activation. Each continuation is a function (technically a closure).

            When a multi-shot generator "myields", it returns just like a
            normal function, technically terminating its execution. But it gives
            you a continuation closure, that you can call to continue execution
            just after that particular `myield`.

            The magic is in that the continuation closures are nested, so for
            a given activation of the multi-shot generator, any local variables
            in the already executed part remain alive as long as at least one
            reference to any relevant closure instance exists.

            And yes, "nested" does imply that the execution will branch into
            "alternate timelines" if you re-invoke an earlier continuation.
            (Maybe you want to send a different value into some algorithm,
             to alter what it will do from a certain point onward.)

            This works in exactly the same way as manually nested closures.
            The parent cells (in the technical sense of "cell variable")
            are shared, but the continuation that was re-invoked is separately
            activated again (in the sense of "activation record"), so the
            continuation gets fresh locals. Thus the "timelines" will diverge.

          - `myield` is a *statement*, and it may only appear at the top level
            of a multishot function definition, due to limitations of our `call_cc`
            implementation.

        Usage::

            with continuations:
                @multishot
                def f():
                    # Stop, and return a continuation `k` that resumes just after this `myield`.
                    myield

                    # Stop, and return the tuple `(k, 42)`.
                    myield[42]

                    # Stop, and return a continuation `k`. Upon resuming `k`,
                    # set the local `k` to the value that was sent in.
                    k = myield

                    # Stop, and return the tuple `(k, 42)`. Upon resuming `k`,
                    # set the local `k` to the value that was sent in.
                    k = myield[42]

                # Instantiate the multi-shot generator (like calling a gfunc).
                # There is always an implicit bare `myield` at the beginning.
                k0 = f()

                # Start, run up to the explicit bare `myield` in the example,
                # receive new continuation.
                k1 = k0()

                # Continue to the `myield[42]`, receive new continuation and the `42`.
                k2, x2 = k1()
                test[x2 == 42]

                # Continue to the `k = myield`, receive new continuation.
                k3 = k2()

                # Send `23` as the value of `k`, continue to the `k = myield[42]`.
                k4, x4 = k3(23)
                test[x4 == 42]

                # Send `17` as the value of `k`, continue to the end.
                # As with a regular Python generator, reaching the end raises `StopIteration`.
                # (As with generators, you can also trigger a `StopIteration` earlier via `return`,
                #  with an optional value.)
                test_raises[StopIteration, k4(17)]

                # Re-invoke an earlier continuation:
                k2, x2 = k1()
                test[x2 == 42]
        """
        if syntax != "decorator":
            raise SyntaxError("multishot is a decorator macro only")  # pragma: no cover
        if type(tree) is not ast.FunctionDef:
            raise SyntaxError("@multishot supports `def` only")

        # Detect the name(s) of `myield` at the use site (this accounts for as-imports)
        macro_bindings = extract_bindings(expander.bindings, myield_function)
        if not macro_bindings:
            raise SyntaxError("The use site of `multishot` must macro-import `myield`, too.")
        names_of_myield = list(macro_bindings.keys())

        def is_myield_name(node):
            return type(node) is ast.Name and node.id in names_of_myield
        def is_myield_expr(node):
            return type(node) is ast.Subscript and is_myield_name(node.value)
        def getslice(subscript_node):
            if sys.version_info >= (3, 9, 0):  # Python 3.9+: no ast.Index wrapper
                return subscript_node.slice
            return subscript_node.slice.value
        class MultishotYieldTransformer(ASTTransformer):
            def transform(self, tree):
                if is_captured_value(tree):  # do not recurse into hygienic captures
                    return tree
                # respect scope boundaries
                if type(tree) in (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef,
                                  ast.ListComp, ast.DictComp, ast.SetComp, ast.GeneratorExp):
                    return tree

                # `k = myield[value]`
                if type(tree) is ast.Assign and is_myield_expr(tree.value):
                    if len(tree.targets) != 1:
                        raise SyntaxError("expected exactly one assignment target in k = myield[expr]")
                    var = tree.targets[0]
                    value = getslice(tree.value)
                    with q as quoted:
                        # Note in `mcpyrate` we can hygienically capture macros, too.
                        a[var] = h[call_cc][h[get_cc]()]
                        if h[iscontinuation](a[var]):
                            return a[var], a[value]
                    return quoted

                # `k = myield`
                elif type(tree) is ast.Assign and is_myield_name(tree.value):
                    if len(tree.targets) != 1:
                        raise SyntaxError("expected exactly one assignment target in k = myield[expr]")
                    var = tree.targets[0]
                    with q as quoted:
                        a[var] = h[call_cc][h[get_cc]()]
                        if h[iscontinuation](a[var]):
                            return a[var]
                    return quoted

                # `myield[value]`
                elif type(tree) is ast.Expr and is_myield_expr(tree.value):
                    var = q[n[gensym("k")]]  # kontinuation
                    value = getslice(tree.value)
                    with q as quoted:
                        a[var] = h[call_cc][h[get_cc]()]
                        if h[iscontinuation](a[var]):
                            return h[partial](a[var], None), a[value]
                    return quoted

                # `myield`
                elif type(tree) is ast.Expr and is_myield_name(tree.value):
                    var = q[n[gensym("k")]]
                    with q as quoted:
                        a[var] = h[call_cc][h[get_cc]()]
                        if h[iscontinuation](a[var]):
                            return h[partial](a[var], None)
                    return quoted

                return self.generic_visit(tree)

        class ReturnToStopIterationTransformer(ASTTransformer):
            def transform(self, tree):
                if is_captured_value(tree):  # do not recurse into hygienic captures
                    return tree
                # respect scope boundaries
                if type(tree) in (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef,
                                  ast.ListComp, ast.DictComp, ast.SetComp, ast.GeneratorExp):
                    return tree

                if type(tree) is ast.Return:
                    # `return`
                    if tree.value is None:
                        with q as quoted:
                            raise h[StopIteration]
                        return quoted
                    # `return value`
                    with q as quoted:
                        raise h[StopIteration](a[tree.value])
                    return quoted

                return self.generic_visit(tree)

        # ------------------------------------------------------------
        # main processing logic

        # Make the multishot generator raise `StopIteration` when it finishes
        # via any `return`. First make the implicit bare `return` explicit.
        #
        # We must do this before we transform the `myield` statements,
        # to avoid breaking tail-calling the continuations.
        if type(tree.body[-1]) is not ast.Return:
            with q as quoted:
                return
            tree.body.extend(quoted)
        tree.body = ReturnToStopIterationTransformer().visit(tree.body)

        # Inject a bare `myield` resume point at the beginning of the function body.
        # This makes the resulting function work somewhat like a Python generator.
        # When initially called, the arguments are bound, and you get a continuation;
        # then resuming that continuation starts the actual computation.
        tree.body.insert(0, ast.Expr(value=ast.Name(id=names_of_myield[0])))

        # Transform multishot yields (`myield`) into `call_cc`.
        tree.body = MultishotYieldTransformer().visit(tree.body)

        return tree

from __self__ import macros, multishot, myield  # noqa: F811, F401


def runtests():
    with testset("a basic generator"):
        with continuations:
            # logic to resume after the last executed my_yield, if any
            @dlet(k << None)  # noqa: F821, dlet defines the name.
            def g():
                if k:  # noqa: F821
                    return k()  # noqa: F821
                def my_yield(value, cc):
                    k << cc  # noqa: F821
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
            test[out == [1, 2, 3]]

    # an FP loop based generator
    # - the resume logic **must** be outside the looped part,
    #   otherwise we get stuck in an infinite loop.
    with testset("FP loop based generator"):
        with continuations:
            # logic to resume after the last executed my_yield, if any
            @dlet(k << None)  # noqa: F821
            def g():
                if k:  # noqa: F821
                    return k()  # noqa: F821
                def my_yield(value, cc):
                    k << cc  # noqa: F821
                    cc = identity
                    return value
                # generator body
                @looped
                def result(loop, i=0):
                    call_cc[my_yield(i)]
                    return loop(i + 1)
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
            test[out == list(range(10))]

    # A basic generator template using abbrev[].
    with testset("integration with abbrev"):
        with continuations:
            # We must expand abbreviations in the outside-in pass, before the @dlet that's
            # not part of the template (since we splice in stuff that is intended to
            # refer to the "k" in the @dlet env). So use abbrev[] instead of let_syntax[].
            with abbrev:
                with block[value] as my_yield:  # noqa: F821, here `abbrev` defines the name `value` when we call `my_yield`.
                    call_cc[my_yieldf(value)]  # for this to work, abbrev[] must eliminate its "if 1" blocks.  # noqa: F821, my_yieldf will be defined below and this is a macro.
                with block as begin_generator_body:
                    # logic to resume after the last executed my_yield, if any
                    if k:  # noqa: F821
                        return k()  # noqa: F821
                    def my_yieldf(value, cc):
                        k << cc  # noqa: F821
                        cc = identity
                        return value

                @dlet(k << None)  # <-- we must still remember this line  # noqa: F821
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
                test[out == [1, 2, 3]]

    # With some gymnastics we can make a template that includes the @dlet:
    with testset("integration with let_syntax"):
        with continuations:
            # Now we can use let_syntax, since the @dlet is part of the code being spliced
            # and the user code (generator body) doesn't refer to k directly.
            # (So "k" can be resolved lexically *in the input source code that goes to dlet[]*.)
            with let_syntax:
                with block[value] as my_yield:  # noqa: F821
                    call_cc[my_yieldf(value)]  # for this to work, let_syntax[] must eliminate its "if 1" blocks.  # noqa: F821
                with block[myname, body] as make_generator:  # noqa: F821, `let_syntax` defines `myname` and `body` when we call `make_generator`.
                    @dlet(k << None)  # noqa: F821
                    def myname():  # replaced by the user-supplied name, since "myname" is a template parameter.
                        # logic to resume after the last executed my_yield, if any
                        if k:  # noqa: F821
                            return k()  # noqa: F821
                        def my_yieldf(value, cc):
                            k << cc  # noqa: F821
                            cc = identity
                            return value
                        body  # noqa: F821

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
                test[out == [1, 2, 3]]

                # Let's remake the FP loop based generator example using this version.
                with block as mybody2:
                    @looped
                    def result(loop, i=0):
                        my_yield(i)
                        return loop(i + 1)
                    return result
                make_generator(g2, mybody2)  # noqa: F821, the name `g2` is used by `make_generator` (see above) to name the generator being created.

                out = []
                x = g2()  # noqa: F821
                while x < 10:
                    out.append(x)
                    x = g2()  # noqa: F821
                test[out == list(range(10))]

    with testset("multi-shot generators with call_cc[]"):
        with continuations:
            with let_syntax:
                with block[value] as my_yield:  # noqa: F821
                    call_cc[my_yieldf(value)]  # noqa: F821
                with block[myname, body] as make_multishot_generator:  # noqa: F821
                    def myname(k=None):  # "myname" is replaced by the user-supplied name
                        if k:  # noqa: F821
                            return k()  # noqa: F821
                        def my_yieldf(value=None, *, cc):
                            k = cc  # noqa: F821
                            cc = identity
                            if value is None:
                                return k
                            return k, value
                        body  # noqa: F821
                        # If we wanted a mechanism to `return` a final value,
                        # this would be the place to send it.
                        raise StopIteration

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
                make_multishot_generator(g, mybody)

                # basic test
                out = []
                k, x = g()
                try:
                    while True:
                        out.append(x)
                        k, x = g(k)
                except StopIteration:
                    pass
                test[out == [1, 2, 3]]

                # multi-shot test
                k1, x1 = g()    # no argument: start from the beginning
                k2, x2 = g(k1)  # continue execution from k1 (after the first `my_yield`)
                k3, x3 = g(k2)
                k, x = g(k1)  # multi-shot: continue *again* from k1
                test[x1 == 1]
                test[x2 == x == 2]
                test[x3 == 3]
                test[k.__qualname__ == k2.__qualname__]  # same bookmarked position...
                test[k is not k2]  # ...but different function object instance
                test_raises[StopIteration, g(k3)]

        # Unfortunately, this is as far as let_syntax[] gets us; if we wanted to
        # "librarify" this any further, we'd need to define a macro in `mcpyrate`.
        #
        # (Suggestions: make_generator as a decorator macro; my_yield[] as a special
        # literal Subscript that make_generator understands and expands away. At the
        # module level, define my_yield as a magic variable so that accidental uses
        # outside any make_generator are caught at compile time. The actual template the
        # make_generator macro needs to splice in is already here in the final example.)

    with testset("multi-shot generators with the pattern call_cc[get_cc()]"):
        with continuations:
            @multishot
            def g():
                myield[1]
                myield[2]
                myield[3]

            try:
                out = []
                k = g()  # instantiate the multishot generator
                while True:
                    k, x = k()
                    out.append(x)
            except StopIteration:
                pass
            test[out == [1, 2, 3]]

            k0 = g()  # instantiate the multishot generator
            k1, x1 = k0()
            k2, x2 = k1()
            k3, x3 = k2()
            k, x = k1()  # multi-shot generator can resume from an earlier point
            test[x1 == 1]
            test[x2 == x == 2]
            test[x3 == 3]
            test[k.func.__qualname__ == k2.func.__qualname__]  # same bookmarked position...
            test[k.func is not k2.func]  # ...but different function object instance
            test_raises[StopIteration, k3()]

    with continuations:
        def f():
            # original function scope
            x = None

            # continuation 1 scope begins here
            # (from the statement following `call_cc` onward, but including the `k1`)
            k1 = call_cc[get_cc()]
            nonlocal x
            if iscontinuation(k1):
                x = "cont 1 first time"
                return k1, x

            # continuation 2 scope begins here
            k2 = call_cc[get_cc()]
            nonlocal x
            if iscontinuation(k2):
                x = "cont 2 first time"
                return k2, x

            x = "cont 2 second time"
            return None, x

        k1, x = f()
        test[x == "cont 1 first time"]
        k2, x = k1(None)  # when resuming, send `None` as the new value of variable `k1` in continuation 1
        test[x == "cont 2 first time"]
        k3, x = k2(None)
        test[k3 is None]
        test[x == "cont 2 second time"]

        k2, x = k1(None)  # multi-shotting from earlier resume point
        test[x == "cont 2 first time"]

    with continuations:
        def f():
            # original function scope
            x = None

            # continuation 1 scope begins here
            # (from the statement following `call_cc` onward, but including the `k1`)
            k1 = call_cc[get_cc()]
            if iscontinuation(k1):
                x = "cont 1 first time"
                return k1, x

            # continuation 2 scope begins here
            k2 = call_cc[get_cc()]
            if iscontinuation(k2):
                x = "cont 2 first time"
                return k2, x

            x = "cont 2 second time"
            return None, x

        k1, x = f()
        test[x == "cont 1 first time"]
        k2, x = k1(None)  # when resuming, send `None` as the new value of variable `k1` in continuation 1
        test[x == "cont 2 first time"]
        k3, x = k2(None)
        test[k3 is None]
        test[x == "cont 2 second time"]

        k2, x = k1(None)  # multi-shotting from earlier resume point
        test[x == "cont 2 first time"]

    with continuations:
        @multishot
        def f():
            myield
            myield[42]
            k = myield
            test[k == 23]
            k = myield[42]
            test[k == 17]

        k0 = f()
        k1 = k0()
        k2, x2 = k1()
        test[x2 == 42]
        k3 = k2()
        k4, x4 = k3(23)
        test[x4 == 42]
        test_raises[StopIteration, k4(17)]

        # multi-shot: re-invoke an earlier continuation
        k2, x2 = k1()
        test[x2 == 42]

if __name__ == '__main__':  # pragma: no cover
    with session(__file__):
        runtests()
