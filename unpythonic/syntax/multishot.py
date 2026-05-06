# -*- coding: utf-8 -*-
"""Multi-shot generators.

A `@multishot` function is a generator-shaped construct whose execution
state is captured *as a continuation* at every `myield`, so it can be
resumed from any earlier `myield` arbitrarily many times — branching
execution into independent timelines.

Built on top of `call_cc[]` / `get_cc()`. Only meaningful inside a
`with continuations:` block (this is enforced by `call_cc[]`, which the
expansion of `myield` produces).

For attribution: the one-shot vs. multi-shot continuation distinction
goes back at least to Bruggeman, Waddell & Dybvig 1996 ("Representing
control in the presence of one-shot continuations"). Racket's docs are
the canonical reference for current usage:
https://docs.racket-lang.org/reference/cont.html

Public surface:

  - `multishot` — decorator macro that turns a `def` into a multi-shot
    generator. Inside, the four `myield` forms are recognized and rewritten.
  - `myield` — name/expr macro for the four yield variants:

        Multi-shot yield    Returns      `k` expects   Single-shot analog

        myield              k            no argument   yield
        myield[expr]        (k, value)   no argument   yield expr
        var = myield        k            one argument  var = yield
        var = myield[expr]  (k, value)   one argument  var = yield expr

  - `MultishotIterator` — adapter that makes a `@multishot` conform to
    a subset of Python's generator protocol, plus `copy.copy()` for forking.

See `doc/macros.md` for the user-facing documentation.
"""

import ast
from functools import partial

from mcpyrate.quotes import macros, q, n, a, h  # noqa: F401

from mcpyrate import namemacro, gensym
from mcpyrate.quotes import is_captured_value
from mcpyrate.utils import extract_bindings
from mcpyrate.walkers import ASTTransformer

from ..misc import safeissubclass

from .scopeanalyzer import isnewscope
from .tailtools import macros, call_cc  # noqa: F401, F811 -- macro-import: makes `h[call_cc]` a hygienic *macro* reference
from .tailtools import get_cc, iscontinuation


__all__ = ["multishot", "myield", "MultishotIterator"]


# --------------------------------------------------------------------------------
# `myield` — name/expr macro

def myield_function(tree, syntax, **kw):
    """[syntax, name/expr] Yield from a multi-shot generator.

    Only meaningful at the top level of a function decorated with `@multishot`.
    Outside that context, raises `SyntaxError` at macro-expansion time.

    For details, see `multishot`.
    """
    if syntax not in ("name", "expr"):
        raise SyntaxError("myield is a name and expr macro only")  # pragma: no cover

    # Allow `myield` in non-Load contexts so the name can be assigned to / del'd
    # without spuriously triggering the macro (mostly defensive — `multishot`
    # itself recognizes the patterns it needs before this macro runs).
    if type(getattr(tree, "ctx", None)) in (ast.Store, ast.Del):
        return tree

    # `myield` is not really a macro; it's a marker that `@multishot` looks for
    # and rewrites away. If a `myield` survives to reach the expander, it was
    # placed somewhere `@multishot` couldn't see it (outside `@multishot`, or
    # inside a nested scope that `@multishot` deliberately doesn't recurse into).
    raise SyntaxError("myield may only appear at the top level of a `@multishot` generator")


myield = namemacro(myield_function)


# --------------------------------------------------------------------------------
# `@multishot` — decorator macro

def multishot(tree, syntax, expander, **kw):
    """[syntax, decorator] Make a function into a multi-shot generator.

    Only meaningful inside a `with continuations:` block — required, not
    auto-wrapped. The expansion of `myield` produces `call_cc[get_cc()]`,
    which `with continuations` then turns into the actual continuation
    machinery; outside `with continuations`, that step fails with the
    standard `call_cc[]` SyntaxError.

    Multi-shot yield is spelled `myield`. The use site of `@multishot`
    must macro-import `myield` too, so that this macro knows which name
    you've bound it under.

    There are four variants::

        Multi-shot yield    Returns      `k` expects   Single-shot analog

        myield              k            no argument   yield
        myield[expr]        (k, value)   no argument   yield expr
        var = myield        k            one argument  var = yield
        var = myield[expr]  (k, value)   one argument  var = yield expr

    To resume, call `k`. In cases where `k` expects an argument, that
    argument is the value to send into `var`.

    Important differences from standard Python generators:

      - A multi-shot generator may be resumed from any `myield` arbitrarily
        many times, in any order. There is no concept of a single paused
        activation; each continuation is a function (technically a closure).

        When a multi-shot generator "myields", it returns just like a
        normal function, technically terminating its execution. But it
        gives you a continuation closure that you can call to resume
        execution just after that particular `myield`.

        The state lives in the closure cells of the continuation. The
        continuations are nested, so for a given activation, any locals
        in the already-executed part remain alive as long as at least
        one reference to a relevant continuation closure exists.

        "Nested" implies that re-invoking an earlier continuation branches
        execution into an independent timeline. Multiple resumes of the
        same continuation share the cells from before that point but get
        fresh activation records — so timelines diverge.

      - `myield` is a *statement*, and it may only appear at the top level
        of a `@multishot` function definition (limitation of the underlying
        `call_cc[]`). Use inside lambdas, comprehensions, or nested `def`s
        is rejected at macro-expansion time.

    Usage::

        with continuations:
            @multishot
            def f():
                # Stop and return a continuation `k` that resumes just after this `myield`.
                myield

                # Stop and return the tuple `(k, 42)`.
                myield[42]

                # Stop and return a continuation `k`. Upon resuming `k`,
                # set the local `k` to the value sent in.
                k = myield

                # Stop and return the tuple `(k, 42)`. Upon resuming `k`,
                # set the local `k` to the value sent in.
                k = myield[42]

            # Instantiate the multi-shot generator (like calling a gfunc).
            # There is always an implicit bare `myield` at the beginning.
            k0 = f()

            # Start; run up to the explicit bare `myield`; receive new continuation.
            k1 = k0()

            # Continue to `myield[42]`; receive new continuation and the `42`.
            k2, x2 = k1()

            # Continue to `k = myield`; receive new continuation.
            k3 = k2()

            # Send `23` as the value of `k`; continue to `k = myield[42]`.
            k4, x4 = k3(23)

            # Send `17` as the value of `k`; continue to the end.
            # Reaching the end raises `StopIteration` (as with a regular generator).
            # `return value` inside `@multishot` raises `StopIteration(value)`.

            # Re-invoke an earlier continuation:
            k2, x2 = k1()

    For ergonomic generator-shaped consumption, wrap the initial continuation
    in a `MultishotIterator`.
    """
    if syntax != "decorator":
        raise SyntaxError("multishot is a decorator macro only")  # pragma: no cover
    if type(tree) is not ast.FunctionDef:
        raise SyntaxError("@multishot supports `def` only")

    # Detect the name(s) under which `myield` is macro-imported (handles as-imports).
    macro_bindings = extract_bindings(expander.bindings, myield_function)
    if not macro_bindings:
        raise SyntaxError("The use site of `@multishot` must macro-import `myield`, too.")
    names_of_myield = list(macro_bindings.keys())

    def is_myield_name(node):
        return type(node) is ast.Name and node.id in names_of_myield
    def is_myield_expr(node):
        return type(node) is ast.Subscript and is_myield_name(node.value)
    def getslice(subscript_node):
        return subscript_node.slice

    class MultishotYieldTransformer(ASTTransformer):
        def transform(self, tree):
            if is_captured_value(tree):
                return tree
            if isnewscope(tree):
                return tree

            # `k = myield[value]`
            if type(tree) is ast.Assign and is_myield_expr(tree.value):
                if len(tree.targets) != 1:
                    raise SyntaxError("expected exactly one assignment target in `k = myield[expr]`")
                var = tree.targets[0]
                value = getslice(tree.value)
                with q as quoted:
                    a[var] = h[call_cc][h[get_cc]()]
                    if h[iscontinuation](a[var]):
                        return a[var], a[value]
                    elif isinstance(a[var], BaseException) or h[safeissubclass](a[var], BaseException):
                        raise a[var]
                return quoted

            # `k = myield`
            elif type(tree) is ast.Assign and is_myield_name(tree.value):
                if len(tree.targets) != 1:
                    raise SyntaxError("expected exactly one assignment target in `k = myield`")
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
                var = q[n[gensym("k")]]
                value = getslice(tree.value)
                with q as quoted:
                    a[var] = h[call_cc][h[get_cc]()]
                    if h[iscontinuation](a[var]):
                        return h[partial](a[var], None), a[value]
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
            if is_captured_value(tree):
                return tree
            if isnewscope(tree):
                return tree

            if type(tree) is ast.Return:
                if tree.value is None:
                    with q as quoted:
                        raise h[StopIteration]
                    return quoted
                with q as quoted:
                    raise h[StopIteration](a[tree.value])
                return quoted

            return self.generic_visit(tree)

    # Make the multishot generator raise `StopIteration` when it finishes via
    # any `return`. First make the implicit bare `return` explicit, then rewrite.
    # This must happen before transforming `myield`, to avoid breaking tail-calling
    # of the continuations.
    if type(tree.body[-1]) is not ast.Return:
        with q as quoted:
            return
        tree.body.extend(quoted)
    tree.body = ReturnToRaiseStopIterationTransformer().visit(tree.body)

    # Inject a bare `myield` resume point at the beginning of the function body.
    # When the multishot is initially called, the arguments are bound, and the
    # caller gets a continuation back; resuming that continuation actually starts
    # executing the function body. Mirrors a Python generator's first-`next` shape.
    tree.body.insert(0, ast.Expr(value=ast.Name(id=names_of_myield[0])))

    tree.body = MultishotYieldTransformer().visit(tree.body)

    return tree


# --------------------------------------------------------------------------------
# `MultishotIterator` — generator-protocol adapter

def _continuation_code(k):
    """Extract the `__code__` of a continuation, unwrapping `partial` if present."""
    func = k.func if isinstance(k, partial) else k
    return getattr(func, "__code__", None)


class MultishotIterator:
    """Adapt a `@multishot` generator to a subset of Python's generator protocol.

    Example::

        with continuations:
            @multishot
            def g():
                myield[1]
                myield[2]
                myield[3]

            mi = MultishotIterator(g())
            assert [x for x in mi] == [1, 2, 3]

    Beyond the standard subset, `MultishotIterator` supports `copy.copy(mi)`,
    which forks the iterator at its current continuation. The fork shares the
    current continuation; subsequent advances of the two iterators are
    independent. (Unlike standard generators, multi-shot generators support
    `copy.copy()`.)

    `copy.deepcopy(mi)` raises `TypeError` — the continuation closes over caller
    state we can't meaningfully deep-copy. Use `copy.copy(mi)` to fork.

    The current continuation is stored as `self.k` (read/write, type-checked).
    Overwriting `self.k` re-opens a closed iterator.

    Supported subset of the generator protocol:

      - `iter(mi)`, `next(mi)`, `mi.send(value)`
      - `mi.throw(exc)`, `mi.close()`
      - `mi.gi_code` — the `__code__` of the current continuation, or `None`
        when closed. **Use this as the liveness signal**, not `gi_frame`.
      - `mi.gi_frame` — **always `None`**. A multi-shot generator has no
        paused frame; state lives in the closure cells of the continuation.
        The real-generator idiom `gen.gi_frame is None ↔ exhausted` does *not*
        apply here.
      - `mi.gi_running` — **always `False`**. Nothing is ever paused.
      - `mi.gi_yieldfrom` — currently always `None` (delegation via
        `myield_from` is not yet implemented).

    Not supported:

      - `yield from` across a real generator and a multi-shot generator
        (semantic mismatch — real generators have paused state, multi-shots
        don't; cannot be papered over).
      - Pickling — continuations are closures.
      - Async (`__aiter__`, `asend`, etc.).
    """
    def __init__(self, k):
        self._k = None
        self._closed = False
        self.k = k

    # `self.k` — type-checked, fail-fast.
    @property
    def k(self):
        return self._k
    @k.setter
    def k(self, k):
        if not (iscontinuation(k) or (isinstance(k, partial) and iscontinuation(k.func))):
            raise TypeError(
                f"expected `k` to be a continuation or a partially applied continuation, got {k!r}"
            )
        self._k = k
        self._closed = False

    # Generator-protocol introspection.
    @property
    def gi_frame(self):
        return None

    @property
    def gi_code(self):
        if self._closed:
            return None
        return _continuation_code(self._k)

    @property
    def gi_running(self):
        return False

    @property
    def gi_yieldfrom(self):
        return None

    # Internal: implements `next` and `send` (and `__next__`).
    def _advance(self, mode, value=None):
        assert mode in ("next", "send")
        if self._closed:
            raise StopIteration
        try:
            if mode == "next":
                result = self._k()
            else:
                result = self._k(value)
        except StopIteration:
            self._closed = True
            raise
        if isinstance(result, tuple):
            self.k, x = result
        else:
            self.k, x = result, None
        return x

    # Generator API.
    def __iter__(self):
        return self

    def __next__(self):
        return self._advance("next")

    def send(self, value):
        return self._advance("send", value)

    def throw(self, exc):
        # Re-enter the current continuation, making it raise `exc`.
        # If the continuation was wrapped by `partial(..., None)` (the bare-
        # `myield` form, which doesn't usefully take a value), unwrap it so
        # we can pass `exc` directly.
        k = self._k.func if isinstance(self._k, partial) else self._k
        k(exc)

    def close(self):
        # https://docs.python.org/3/reference/expressions.html#generator.close
        if self._closed:
            return
        self._closed = True
        try:
            self.throw(GeneratorExit)
        except GeneratorExit:
            return
        else:
            raise RuntimeError("@multishot generator attempted to `myield` a value while it was being closed")

    # Forking — the multi-shot superpower exposed through the stdlib `copy` protocol.
    def __copy__(self):
        """Return a fork of this iterator at the current continuation.

        Both iterators share the current continuation; subsequent advances
        of the two are independent (the timelines diverge from the next
        advance onward). The fork is shallow: closure cells captured before
        the current continuation are *shared*, not duplicated — that is the
        multi-shot semantics.

        If this iterator is closed, the fork is also closed (the underlying
        continuation is preserved, so the fork can be re-opened by assigning
        to `.k`).
        """
        forked = MultishotIterator(self._k)
        forked._closed = self._closed
        return forked

    def __deepcopy__(self, memo):
        raise TypeError(
            "multi-shot iterators cannot be deep-copied; use copy.copy() to fork"
        )

    def __del__(self):
        # Mirror generator GC semantics. Mostly cosmetic for multishots
        # (no paused frame to clean up), but politely closes the iterator.
        try:
            self.close()
        except Exception:
            pass
