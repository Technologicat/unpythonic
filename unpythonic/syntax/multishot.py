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
from mcpyrate.utils import extract_bindings, rename
from mcpyrate.walkers import ASTTransformer

from ..fun import identity
from ..misc import safeissubclass

from .scopeanalyzer import isnewscope
from .tailtools import macros, call_cc  # noqa: F401, F811 -- macro-import: makes `h[call_cc]` a hygienic *macro* reference
from .tailtools import get_cc, iscontinuation


__all__ = ["multishot", "myield", "myield_from", "MultishotIterator"]


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
# `myield_from` — name/expr macro

def myield_from_function(tree, syntax, **kw):
    """[syntax, name/expr] Delegate to another `@multishot` generator.

    Multi-shot analog of `yield from`. Drives the inner multi-shot generator,
    re-yielding each of its values to the outer's caller. On inner exhaustion
    (`StopIteration`), execution continues in the outer body. The two forms::

        myield_from[expr]            # statement; inner's StopIteration value discarded
        var = myield_from[expr]      # statement; inner's StopIteration value bound to var

    Only meaningful at the top level of a `@multishot` function decorated within
    a `with continuations:` block. Forwards `send` and `throw` from the outer's
    caller into the inner; while delegating, `outer_mi.gi_yieldfrom` returns
    the inner `MultishotIterator`.

    For details, see `multishot`.
    """
    if syntax not in ("name", "expr"):
        raise SyntaxError("myield_from is a name and expr macro only")  # pragma: no cover

    if type(getattr(tree, "ctx", None)) in (ast.Store, ast.Del):
        return tree

    raise SyntaxError("myield_from may only appear at the top level of a `@multishot` "
                      "generator, as `myield_from[expr]` or `var = myield_from[expr]`")


myield_from = namemacro(myield_from_function)


# --------------------------------------------------------------------------------
# Expansion of `myield_from[expr]` / `var = myield_from[expr]`
#
# Architecture:
#
# - **Capture rest-of-outer at outer's top level**, before the iteration
#   begins, via `_rest = call_cc[get_cc()]`. The first pass through (when
#   `_rest` is a continuation) tail-calls the driver, passing `_rest`; the
#   second pass (when the driver has invoked `_rest(value)`) sees `_rest` as
#   the inner's `StopIteration` value and falls through to the post-
#   `myield_from` code in outer's body.
#
# - **The driver itself uses cut-the-tail** (`cc = identity` + return tuple)
#   to escape each `(captured_cc, inner_value)` to the user. Because the
#   driver is *tail-called* from outer (no nested trampoline started), and
#   the helper is *tail-called* via `call_cc[helper(...)]`, every step shares
#   the trampoline that `mi._k()` set up. The cut-the-tail escape therefore
#   reaches the user's `mi._k()` return — not a nested helper's frame.
#
# - **Resume after exhaustion via the captured rest-cc**: when inner raises
#   `StopIteration`, the driver does `return _rest_k(stopvalue)` (tail call),
#   resuming outer's body just after the rest-cc-capture point.
#
# - **`MultishotIterator` for inner**: convenient wrapper for `send`/`throw`
#   forwarding (we delegate to its protocol methods); it also lets
#   `gi_yieldfrom` surface the inner iterator via a stamp on the captured cc.
#
# Limitations of this v1: send/throw do reach the inner; `gi_yieldfrom`
# tracks correctly while delegating; multi-shot fork during delegation is
# inherited from the multi-shot semantics of the inner and the captured cc
# stamping. See `doc/macros.md` for the user-facing description.

def _build_myield_from_expansion(arg, target):
    """Build the AST list for a `myield_from` invocation.

    See the section comment above for the architecture. `arg` is the AST of
    the inner-multishot-call expression (e.g., `inner()`). `target` is the
    assignment target for `var = myield_from[...]`, or `None` for statement
    form (inner's `StopIteration` value discarded).
    """
    inner_mi_name = gensym("_inner_mi")
    yieldf_name = gensym("_yieldf")
    drive_name = gensym("_drive")
    rest_name = gensym("_rest")

    with q as quoted:
        _INNER_MI_ = h[MultishotIterator](a[arg])

        def _YIELDF_(_value, _inner_mi, *, cc):
            # Cut-the-tail: capture cc as `_k` (this is the at-call-cc
            # continuation, which is "rest of `_drive` after the call_cc"),
            # stamp it for `gi_yieldfrom`, then locally `cc = identity` so
            # the trampolined return delivers the (k, value) tuple straight
            # to whoever started the trampoline — i.e., the user's `mi._k()`.
            _k = cc
            _k._yieldfrom_inner = _inner_mi
            cc = h[identity]
            return (_k, _value)

        def _DRIVE_(_inner_mi, _rest_k, _value=None, _is_throw=False):
            try:
                if _is_throw:
                    _x = _inner_mi.throw(_value)
                else:
                    _x = _inner_mi.send(_value)
            except h[StopIteration] as _stopit:
                # Inner exhausted. Resume outer's body via the captured
                # rest-cc; outer continues at the post-`myield_from` code.
                return _rest_k(_stopit.value)
            _sent = h[call_cc][_YIELDF_(_x, _inner_mi)]
            if isinstance(_sent, BaseException) or h[safeissubclass](_sent, BaseException):
                return _DRIVE_(_inner_mi, _rest_k, _sent, True)
            return _DRIVE_(_inner_mi, _rest_k, _sent)

        # `_REST_ = call_cc[get_cc()]` is the multi-shot analog of Racket's
        # `(let/cc return ...)`: `_REST_` is bound to "rest of outer" as a
        # continuation. The first pass captures it; the driver later invokes
        # it with inner's `StopIteration` value to fall through to the rest.
        _REST_ = h[call_cc][h[get_cc]()]
        if h[iscontinuation](_REST_):
            return _DRIVE_(_INNER_MI_, _REST_)
        # control reaches here when inner exhausted; `_REST_` holds inner's
        # `StopIteration` value (or `None` if inner returned without a value).

    rename("_INNER_MI_", inner_mi_name, quoted)
    rename("_YIELDF_", yieldf_name, quoted)
    rename("_DRIVE_", drive_name, quoted)
    rename("_REST_", rest_name, quoted)

    if target is not None:
        with q as quoted_assign:
            a[target] = n[rest_name]
        quoted = quoted + quoted_assign

    return quoted


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
        execution into an independent timeline — but only for *locals*.
        Each resume gets a fresh activation record, so locals diverge;
        closure cells captured before the resume point are shared, so a
        mutation through one (a `nonlocal`, a mutable argument, or
        module-level state) is visible to every timeline reached from the
        same fork point.

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

    # `myield_from` is optional; only present if the user macro-imported it.
    macro_bindings_from = extract_bindings(expander.bindings, myield_from_function)
    names_of_myield_from = set(macro_bindings_from.keys())

    def is_myield_name(node):
        return type(node) is ast.Name and node.id in names_of_myield
    def is_myield_expr(node):
        return type(node) is ast.Subscript and is_myield_name(node.value)
    def is_myield_from_expr(node):
        # `myield_from[expr]` parses as a Subscript with `value` being the
        # `myield_from` name. Mirrors how `myield[expr]` is recognized.
        return (type(node) is ast.Subscript
                and type(node.value) is ast.Name
                and node.value.id in names_of_myield_from)
    def getslice(subscript_node):
        return subscript_node.slice

    class MultishotYieldTransformer(ASTTransformer):
        def transform(self, tree):
            if is_captured_value(tree):
                return tree
            if isnewscope(tree):
                return tree

            # `myield_from[expr]` / `var = myield_from[expr]` — handled before
            # `myield` shapes since both macros share the user-namespace symbol family.
            if names_of_myield_from:
                if (type(tree) is ast.Assign and len(tree.targets) == 1
                        and is_myield_from_expr(tree.value)):
                    return _build_myield_from_expansion(getslice(tree.value),
                                                       target=tree.targets[0])
                if type(tree) is ast.Expr and is_myield_from_expr(tree.value):
                    return _build_myield_from_expansion(getslice(tree.value), target=None)

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


def _step(k, mode, value=None):
    """Advance a continuation by one step. ``mode`` ∈ {"next", "send", "throw"}.

    ``"next"`` is treated as ``"send"`` with ``value=None`` — **matching the
    standard generator protocol**, where ``next(gen)`` is defined to be
    ``gen.send(None)``.

    For ``"send"``, if ``k`` is partial-wrapped (came from a bare ``myield`` or
    ``myield[expr]`` that doesn't bind a local), the sent value is dropped and
    the continuation advances normally — **also matching the standard generator
    protocol**, where ``gen.send(value)`` against a bare ``yield`` also discards
    the value silently. For raw-form continuations (from ``var = myield`` or
    ``var = myield[expr]``), the value is bound to ``var``.

    For ``"throw"``, the partial is unwrapped to inject the exception directly
    into the underlying continuation; the partial's pre-applied ``None`` would
    otherwise cause an arity mismatch.

    Returns whatever the continuation returns (typically a ``(next_k, value)``
    tuple, or it raises if the continuation raises).
    """
    if mode == "throw":
        underlying = k.func if isinstance(k, partial) else k
        return underlying(value)
    # mode in ("next", "send"); next ≡ send(None)
    if mode == "next":
        value = None
    return k() if isinstance(k, partial) else k(value)


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
    current continuation; subsequent advances get fresh activation records, so
    the forks' locals diverge. Closure cells captured before the fork point
    are shared, so a mutation through one (a `nonlocal`, a mutable argument,
    or module-level state) in one fork is visible to the others. Forks are
    independent timelines for *locals* only, not for state reached through
    closure cells. (Unlike standard generators, multi-shot generators support
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
        The standard-generator idiom `gen.gi_frame is None ↔ exhausted` does
        *not* apply here.
      - `mi.gi_running` — **always `False`**. Nothing is ever paused.
      - `mi.gi_yieldfrom` — currently always `None` (delegation via
        `myield_from` is not yet implemented).

    Not supported:

      - `yield from` across a standard generator and a multi-shot generator
        (semantic mismatch — standard generators have paused state, multi-shots
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
        if self._closed:
            return None
        # `_yieldfrom_inner` is stamped on the captured continuation by the
        # `myield_from` helper. The continuation is raw there (not partial-
        # wrapped), so a direct attribute read suffices — but check the
        # underlying function too for robustness in case a future code path
        # ever returns a partial-wrapped continuation from `myield_from`.
        underlying = self._k.func if isinstance(self._k, partial) else self._k
        return getattr(underlying, "_yieldfrom_inner", None)

    # Internal: drives one step via `_step`, updates `self._k` from the
    # returned `(next_k, value)`, and surfaces the value to the caller.
    # Used by `__next__`, `send`, and `throw`.
    def _advance(self, mode, value=None):
        assert mode in ("next", "send", "throw")
        if self._closed:
            raise StopIteration
        try:
            result = _step(self._k, mode, value)
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
        # Re-enters the current continuation, making it raise `exc`. If the
        # body catches and reaches another `myield`, the new continuation
        # becomes the current one and we return the next yielded value
        # (matching the standard generator protocol). If the exception isn't
        # caught, it propagates out of this call.
        return self._advance("throw", exc)

    def close(self):
        # https://docs.python.org/3/reference/expressions.html#generator.close
        # Bypass `_advance` here: close has different semantics (it injects
        # `GeneratorExit` and accepts `StopIteration` as a clean exit), and
        # `_advance` would short-circuit on the pre-set `_closed` flag.
        if self._closed:
            return
        self._closed = True
        try:
            _step(self._k, "throw", GeneratorExit)
        except GeneratorExit:
            return  # body let the close exception propagate (expected)
        except StopIteration:
            return  # body caught GeneratorExit and exited cleanly
        # Body caught `GeneratorExit` and `myield`ed another value — disallowed,
        # mirroring the standard generator protocol.
        raise RuntimeError("@multishot generator attempted to `myield` a value while it was being closed")

    # Forking — the multi-shot superpower exposed through the stdlib `copy` protocol.
    def __copy__(self):
        """Return a fork of this iterator at the current continuation.

        Both iterators share the current continuation. Each subsequent
        advance gets a fresh activation record, so the forks' locals
        diverge. Closure cells captured before the fork point are shared,
        so a mutation through one (a `nonlocal`, a mutable argument, or
        module-level state) in one fork is visible to the others. Forks
        are independent timelines for *locals* only, not for state reached
        through closure cells.

        This is the multi-shot semantics, not a quirk of `copy.copy()`;
        the same applies to plain re-invocation of an earlier continuation.

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
