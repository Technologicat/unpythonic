# -*- coding: utf-8 -*-
"""Multi-shot generator demo using the pattern `k = call_cc[get_cc()]`.

This is a barebones implementation.

We provide everything in one file, so we use `mcpyrate`'s multi-phase compilation
to be able to define the macros in the same module that uses them.

Because `with continuations` is a two-pass macro, it will first expand any
`@multishot` inside the block before performing its own processing, which
is exactly what we want. We could force the ordering with the metatool
`mcpyrate.metatools.expand_first` that was added in `mcpyrate` 3.6.0,
but we don't need to do that.

We provide a minimal `MultishotIterator` wrapper that makes a `@multishot`
multi-shot generator conform to the most basic parts of Python's generator API.
A full implementation of the generator API would require much more:

 - There is no `yield from` (delegation); needs a custom `myield_from`.
 - Think hard about exception handling.
   - Particularly, a `yield` inside a `finally` block is a classic catch.
"""

from mcpyrate.multiphase import macros, phase

from ...syntax import macros, test, test_raises  # noqa: F401, F811
from ...test.fixtures import session, testset

from ...syntax import macros, continuations  # noqa: F811

with phase[1]:
    # TODO: relative imports
    # TODO: mcpyrate does not recognize current package in phases higher than 0? (parent package missing)

    import ast
    from functools import partial
    import sys

    from mcpyrate.quotes import macros, q, n, a, h  # noqa: F811
    from unpythonic.misc import safeissubclass
    from unpythonic.syntax import macros, call_cc  # noqa: F811

    from mcpyrate import namemacro, gensym
    from mcpyrate.quotes import is_captured_value
    from mcpyrate.utils import extract_bindings
    from mcpyrate.walkers import ASTTransformer

    from unpythonic.syntax import get_cc, iscontinuation
    from unpythonic.syntax.scopeanalyzer import isnewscope

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

        Only meaningful inside a `with continuations` block. This is not checked.

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
                if isnewscope(tree):  # respect scope boundaries
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
                        # For `throw` support: if we are sent an exception instance or class, raise it.
                        elif isinstance(a[var], BaseException) or h[safeissubclass](a[var], BaseException):
                            raise a[var]
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
                        elif isinstance(a[var], BaseException) or h[safeissubclass](a[var], BaseException):
                            raise a[var]
                    return quoted

                # `myield[value]`
                elif type(tree) is ast.Expr and is_myield_expr(tree.value):
                    var = q[n[gensym("k")]]  # kontinuation
                    value = getslice(tree.value)
                    with q as quoted:
                        a[var] = h[call_cc][h[get_cc]()]
                        if h[iscontinuation](a[var]):
                            return h[partial](a[var], None), a[value]
                        # For `throw` support: `MultishotIterator` digs the `.func` from inside the `partial`
                        # to force a send, even though this variant of `myield` cannot receive a value by
                        # a normal `send`.
                        elif isinstance(a[var], BaseException) or h[safeissubclass](a[var], BaseException):
                            raise a[var]
                    return quoted

                # `myield`
                elif type(tree) is ast.Expr and is_myield_name(tree.value):
                    var = q[n[gensym("k")]]
                    with q as quoted:
                        a[var] = h[call_cc][h[get_cc]()]
                        if h[iscontinuation](a[var]):
                            return h[partial](a[var], None)
                        elif isinstance(a[var], BaseException) or h[safeissubclass](a[var], BaseException):
                            raise a[var]
                    return quoted

                return self.generic_visit(tree)

        class ReturnToRaiseStopIterationTransformer(ASTTransformer):
            def transform(self, tree):
                if is_captured_value(tree):  # do not recurse into hygienic captures
                    return tree
                if isnewscope(tree):  # respect scope boundaries
                    return tree

                if type(tree) is ast.Return:
                    # `return`
                    if tree.value is None:
                        with q as quoted:
                            raise h[StopIteration]
                        return quoted
                    # `return expr`
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
        tree.body = ReturnToRaiseStopIterationTransformer().visit(tree.body)

        # Inject a bare `myield` resume point at the beginning of the function body.
        # This makes the resulting function work somewhat like a Python generator.
        # When initially called, the arguments are bound, and you get a continuation;
        # then resuming that continuation actually starts executing the function body.
        tree.body.insert(0, ast.Expr(value=ast.Name(id=names_of_myield[0])))

        # Transform multishot yields (`myield`) into `call_cc`.
        tree.body = MultishotYieldTransformer().visit(tree.body)

        return tree


# macro-import from higher phase; we're now in phase 0
from __self__ import macros, multishot, myield  # noqa: F811, F401

class MultishotIterator:
    """Adapt a `@multishot` generator to Python's generator API.

    Example::

        with continuations:
            @multishot
            def g():
                myield[1]
                myield[2]
                myield[3]

            # Instantiating the multi-shot generator returns a continuation;
            # we can send that into a `MultishotIterator`. The resulting iterator
            # behaves almost like a standard generator.
            mi = MultishotIterator(g())
            assert [x for x in mi] == [1, 2, 3]

    `k`: A continuation, or a partially applied continuation
        (e.g. one that does not usefully expect a value;
         an `myield` with no assignment target will return such).

         The initial continuation to start execution from.

    Each `next` or `.send` will call the current `self.k`, and then overwrite
    `self.k` with the new continuation returned by the multi-shot generator.
    If the multi-shot generator raises `StopIteration` (so there is no new
    continuation), the `MultishotIterator` marks itself as closed, and re-raises.

    The current continuation is stored as `self.k`. It is read/write,
    type-checked at write time.

    If you overwrite `self.k` with another continuation, the next call
    to `next` or `.send` will resume from that continuation instead.
    If the iterator was closed, overwriting `self.k` will re-open it.

    This proof-of-concept demo only supports a subset of the generator API:

      - `iter(mi)`
      - `next(mi)`,
      - `mi.send(value)`
      - `mi.throw(exc)`
      - `mi.close()`

    where `mi` is a `MultishotIterator` instance.
    """
    def __init__(self, k):
        self.k = k
        self._closed = False

    # make writes into `self.k` type-check, for fail-fast
    def _getk(self):
        return self._k
    def _setk(self, k):
        if not (iscontinuation(k) or (isinstance(k, partial) and iscontinuation(k.func))):
            raise TypeError(f"expected `k` to be a continuation or a partially applied continuation, got {k}")
        self._k = k
        self._closed = False
    k = property(fget=_getk, fset=_setk, doc="The current continuation. Read/write.")

    # Internal method that implements `next` and `.send`.
    def _advance(self, mode, value=None):
        assert mode in ("next", "send")
        if self._closed:
            raise StopIteration
        # Intercept possible `StopIteration` and enter the closed
        # state, to prevent re-running the last continuation (that
        # raised `StopIteration`) when `next()` is called again.
        try:
            if mode == "next":
                result = self.k()
            else:  # mode == "send"
                result = self.k(value)
        except StopIteration:  # no new continuation
            self._closed = True
            raise
        if isinstance(result, tuple):
            self.k, x = result
        else:
            self.k, x = result, None
        return x

    # generator API
    def __iter__(self):
        return self
    def __next__(self):
        return self._advance("next")
    def send(self, value):
        return self._advance("send", value)

    # The `throw` and `close` methods are not so useful as with regular
    # generators, due to there being no concept of paused execution.
    #
    # The continuation is a separate nested closure, and it is not
    # possible to usefully straddle a `try` or `with` across the
    # boundary.
    #
    # For example, `with` only takes effect whenever it is "entered
    # from the top", and it will release the context as soon as the
    # multi-shot generator `myield`s the continuation.
    #
    # `throw` pretty much just enters the continuation function, and
    # makes it raise an exception; in true multi-shot fashion, the same
    # continuation can still be resumed later (also without making it
    # raise that time).
    #
    # `close` is only useful in that closing makes the multi-shot generator
    # reject any further attempts to `next` or `.send` (unless you then
    # overwrite the continuation manually).
    #
    # For an example of what serious languages that have `call_cc` do, see
    # Racket's `dynamic-wind` construct ("wind" as in "winding/unwinding the call stack").
    # It's the supercharged big sister of Python's `with` construct that accounts for
    # execution topologies where control may leave the block, and then suddenly return
    # to the middle of it later (most often due to the invocation of a continuation
    # that was created inside that block).
    # https://docs.racket-lang.org/reference/cont.html#%28def._%28%28quote._~23~25kernel%29._dynamic-wind%29%29
    def throw(self, exc):
        # If we are stopped at an `myield` that has no assignment target, so
        # that it normally does not expect a value, we unwrap the original
        # continuation from the `partial` to force-send the exception.
        k = self.k.func if isinstance(self.k, partial) else self.k
        k(exc)

    # https://stackoverflow.com/questions/60137570/explanation-of-generator-close-with-exception-handling
    def close(self):
        if self._closed:
            return
        self._closed = True
        try:
            self.throw(GeneratorExit)
        except GeneratorExit:
            return  # ok!
        # Any other exception is propagated.
        else:  # No exception means that the generator is trying to yield something.
            raise RuntimeError("@multishot generator attempted to `myield` a value while it was being closed")


def runtests():
    # To start with, here's a sketch of what we want to do.
    with testset("multi-shot generators with the pattern call_cc[get_cc()]"):
        with continuations:
            def g():
                # The resume point at the beginning (just after parameters of `g` have
                # been bound to the given arguments; though here we don't have any).
                k = call_cc[get_cc()]
                if iscontinuation(k):
                    # The `partial` makes it so `k` doesn't expect an argument;
                    # otherwise it would expect a value to set the local variable `k` to
                    # when the continuation is resumed.
                    #
                    # Since this example doesn't use that `k` if it's not the continuation
                    # (i.e. the initial return value of the `call_cc[get_cc()]`),
                    # we can just set the argument to `None` here.
                    return partial(k, None)

                # yield 1
                k = call_cc[get_cc()]
                if iscontinuation(k):
                    return partial(k, None), 1

                # yield 2
                k = call_cc[get_cc()]
                if iscontinuation(k):
                    return partial(k, None), 2

                # yield 3
                k = call_cc[get_cc()]
                if iscontinuation(k):
                    return partial(k, None), 3

                raise StopIteration

            try:
                out = []
                k = g()  # instantiate the multi-shot generator
                while True:
                    k, x = k()
                    out.append(x)
            except StopIteration:
                pass
            test[out == [1, 2, 3]]

            k0 = g()  # instantiate the multi-shot generator
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

    # Now, let's automate this. Testing all four kinds of multi-shot yield:
    with testset("@multishot macro"):
        with continuations:
            @multishot
            def f():
                myield
                myield[42]
                k = myield
                test[k == 23]
                k = myield[42]
                test[k == 17]

            k0 = f()  # instantiate the multi-shot generator
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

    # The first example rewritten to use the macro:
    with testset("multi-shot generators with @multishot"):
        with continuations:
            @multishot
            def g():
                myield[1]
                myield[2]
                myield[3]

            try:
                out = []
                k = g()  # instantiate the multi-shot generator
                while True:
                    k, x = k()
                    out.append(x)
            except StopIteration:
                pass
            test[out == [1, 2, 3]]

            k0 = g()  # instantiate the multi-shot generator
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

    # Using a `@multishot` as if it was a standard generator:
    with testset("MultishotIterator: adapting @multishot to Python's generator API"):
        # basic use
        test[[x for x in MultishotIterator(g())] == [1, 2, 3]]
        # TODO: advanced example, exercise all features

if __name__ == '__main__':  # pragma: no cover
    with session(__file__):
        runtests()
