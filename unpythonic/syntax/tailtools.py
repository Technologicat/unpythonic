# -*- coding: utf-8 -*-
"""Automatic TCO, continuations, implicit return statements.

The common factor is tail-position analysis."""

__all__ = ["autoreturn",
           "tco",
           "continuations", "call_cc"]

from functools import partial

from ast import (Lambda, FunctionDef, AsyncFunctionDef,
                 arguments, arg, keyword,
                 List, Tuple,
                 Call, Name, Starred, Constant,
                 BoolOp, And, Or,
                 With, AsyncWith, If, IfExp, Try, Assign, Return, Expr,
                 copy_location)
import sys

from mcpyrate.quotes import macros, q, u, n, a, h  # noqa: F401

from mcpyrate import gensym
from mcpyrate.markers import ASTMarker
from mcpyrate.quotes import capture_as_macro, is_captured_value
from mcpyrate.utils import NestingLevelTracker
from mcpyrate.walkers import ASTTransformer, ASTVisitor

from .astcompat import getconstant, NameConstant
from .ifexprs import aif, it
from .util import (isx, isec,
                   detect_callec, detect_lambda,
                   has_tco, sort_lambda_decorators,
                   suggest_decorator_index, ExpandedContinuationsMarker, wrapwith, isexpandedmacromarker)
from .letdoutil import isdo, islet, ExpandedLetView, ExpandedDoView

from ..dynassign import dyn
from ..it import uniqify
from ..fun import identity
from ..tco import trampolined, jump
from ..lazyutil import passthrough_lazy_args

# In `continuations`, we use `aif` and `it` as hygienically captured macros.
# Note the difference between `aif[..., it, ...]` and `q[a[_our_aif][..., a[_our_it], ...]]`.
#
# If `it` is bound in the current expander, even *mentioning* it outside an `aif` is a syntax error, by design.
#
# When constructing a quasiquoted tree that invokes `aif[]`, we can splice in a hygienic reference to `it`
# as `a[_our_it]` without even having the macro bound in the expander that expands *this* module.
_our_aif = capture_as_macro(aif)
_our_it = capture_as_macro(it)

# --------------------------------------------------------------------------------
# Macro interface

def autoreturn(tree, *, syntax, **kw):
    """[syntax, block] Implicit "return" in tail position, like in Lisps.

    Each ``def`` function definition lexically within the ``with autoreturn``
    block is examined, and if the last item within the body is an expression
    ``expr``, it is transformed into ``return expr``.

    If the last item is an if/elif/else block, the transformation is applied
    to the last item in each of its branches.

    If the last item is a ``with`` or ``async with`` block, the transformation
    is applied to the last item in its body.

    If the last item is a try/except/else/finally block, the rules are as follows.
    If an ``else`` clause is present, the transformation is applied to the last
    item in it; otherwise, to the last item in the ``try`` clause. Additionally,
    in both cases, the transformation is applied to the last item in each of the
    ``except`` clauses. The ``finally`` clause is not transformed; the intention
    is it is usually a finalizer (e.g. to release resources) that runs after the
    interesting value is already being returned by ``try``, ``else`` or ``except``.

    Example::

        with autoreturn:
            def f():
                "I'll just return this"
            assert f() == "I'll just return this"

            def g(x):
                if x == 1:
                    "one"
                elif x == 2:
                    "two"
                else:
                    "something else"
            assert g(1) == "one"
            assert g(2) == "two"
            assert g(42) == "something else"

    **CAUTION**: If the final ``else`` is omitted, as often in Python, then
    only the ``else`` item is in tail position with respect to the function
    definition - likely not what you want.

    So with ``autoreturn``, the final ``else`` should be written out explicitly,
    to make the ``else`` branch part of the same if/elif/else block.

    **CAUTION**: ``for``, ``async for``, ``while`` are currently not analyzed;
    effectively, these are defined as always returning ``None``. If the last item
    in your function body is a loop, use an explicit return.

    **CAUTION**: With ``autoreturn`` enabled, functions no longer return ``None``
    by default; the whole point of this macro is to change the default return
    value.

    The default return value is ``None`` only if the tail position contains
    a statement (because in a sense, a statement always returns ``None``).
    """
    if syntax != "block":
        raise SyntaxError("autoreturn is a block macro only")  # pragma: no cover
    if syntax == "block" and kw['optional_vars'] is not None:
        raise SyntaxError("autoreturn does not take an as-part")  # pragma: no cover

    # Expand outside in. Any nested macros should get clean standard Python,
    # not having to worry about implicit "return" statements.
    return _autoreturn(block_body=tree)

def tco(tree, *, syntax, expander, **kw):
    """[syntax, block] Implicit tail-call optimization (TCO).

    Examples::

        with tco:
            evenp = lambda x: (x == 0) or oddp(x - 1)
            oddp  = lambda x: (x != 0) and evenp(x - 1)
            assert evenp(10000) is True

        with tco:
            def evenp(x):
                if x == 0:
                    return True
                return oddp(x - 1)
            def oddp(x):
                if x != 0:
                    return evenp(x - 1)
                return False
            assert evenp(10000) is True

    This is based on a strategy similar to MacroPy's tco macro, but using
    the TCO machinery from ``unpythonic.tco``.

    This recursively handles also builtins ``a if p else b``, ``and``, ``or``;
    and from ``unpythonic.syntax``, ``do[]``, ``let[]``, ``letseq[]``, ``letrec[]``,
    when used in computing a return value. (``aif[]`` and ``cond[]`` also work.)

    Note only calls **in tail position** will be TCO'd. Any other calls
    are left as-is. Tail positions are:

        - The whole return value, if it is just a single call.

        - Both ``a`` and ``b`` branches of ``a if p else b`` (but not ``p``).

        - The last item in an ``and``/``or``. If these are nested, only the
          last item in the whole expression involving ``and``/``or``. E.g. in::

              (a and b) or c
              a and (b or c)

          in either case, only ``c`` is in tail position, regardless of the
          values of ``a``, ``b``.

        - The last item in a ``do[]``.

          - In a ``do0[]``, this is the implicit item that just returns the
            stored return value.

        - The argument of a call to an escape continuation. The ``ec(...)`` call
          itself does not need to be in tail position; escaping early is the
          whole point of an ec.

    All function definitions (``def`` and ``lambda``) lexically inside the block
    undergo TCO transformation. The functions are automatically ``@trampolined``,
    and any tail calls in their return values are converted to ``jump(...)``
    for the TCO machinery.

    Note in a ``def`` you still need the ``return``; it marks a return value.
    But see ``autoreturn``::

        with autoreturn, tco:
            def evenp(x):
                if x == 0:
                    True
                else:
                    oddp(x - 1)
            def oddp(x):
                if x != 0:
                    evenp(x - 1)
                else:
                    False
            assert evenp(10000) is True

    **CAUTION**: regarding escape continuations, only basic uses of ecs created
    via ``call_ec`` are currently detected as being in tail position. Any other
    custom escape mechanisms are not supported. (This is mainly of interest for
    lambdas, which have no ``return``, and for "multi-return" from a nested
    function.)

    *Basic use* is defined as either of these two cases::

        # use as decorator
        @call_ec
        def result(ec):
            ...

        # use directly on a literal lambda
        result = call_ec(lambda ec: ...)

    When macro expansion of the ``with tco`` block starts, names of escape
    continuations created **anywhere lexically within** the ``with tco`` block
    are captured. Lexically within the block, any call to a function having
    any of the captured names, or as a fallback, one of the literal names
    ``ec``, ``brk``, ``throw`` is interpreted as invoking an escape
    continuation.
    """
    if syntax != "block":
        raise SyntaxError("tco is a block macro only")  # pragma: no cover
    if syntax == "block" and kw['optional_vars'] is not None:
        raise SyntaxError("tco does not take an as-part")  # pragma: no cover

    # Two-pass macro.
    with dyn.let(_macro_expander=expander):
        return _tco(block_body=tree)

def continuations(tree, *, syntax, expander, **kw):
    """[syntax, block] call/cc for Python.

    This allows saving the control state and then jumping back later
    (in principle, any time later). Some possible use cases:

      - Tree traversal (possibly a cartesian product of multiple trees, with the
        current position in each tracked automatically).

      - McCarthy's amb operator.

      - Generators. (Python already has those, so only for teaching.)

    This is a very loose pythonification of Paul Graham's continuation-passing
    macros, which implement continuations by chaining closures and passing the
    continuation semi-implicitly. For details, see chapter 20 in On Lisp:

        http://paulgraham.com/onlisp.html

    Continuations are most readily implemented when the program is written in
    continuation-passing style (CPS), but that is unreadable for humans.
    The purpose of this macro is to partly automate the CPS transformation, so
    that at the use site, we can write CPS code in a much more readable fashion.

    A ``with continuations`` block implies TCO; the same rules apply as in a
    ``with tco`` block. Furthermore, ``with continuations`` introduces the
    following additional rules:

      - Functions which make use of continuations, or call other functions that do,
        must be defined within a ``with continuations`` block, using the usual
        ``def`` or ``lambda`` forms.

      - All function definitions in a ``with continuations`` block, including
        any nested definitions, have an implicit formal parameter ``cc``,
        **even if not explicitly declared** in the formal parameter list.

        If declared explicitly, ``cc`` must be in a position that can accept a
        default value.

        This means ``cc`` must be declared either as by-name-only::

            with continuations:
                def myfunc(a, b, *, cc):
                    ...

                    f = lambda *, cc: ...

        or as the last parameter that has no default::

            with continuations:
                def myfunc(a, b, cc):
                    ...

                    f = lambda cc: ...

        Then the continuation machinery will automatically set the default value
        of ``cc`` to the default continuation (``identity``), which just returns
        its arguments.

        The most common use case for explicitly declaring ``cc`` is that the
        function is the target of a ``call_cc[]``; then it helps readability
        to make the ``cc`` parameter explicit.

      - A ``with continuations`` block will automatically transform all
        function definitions and ``return`` statements lexically contained
        within the block to use the continuation machinery.

        - ``return somevalue`` actually means a tail-call to ``cc`` with the
          given ``somevalue``.

          Multiple values can be returned as a ``tuple``. Tupleness is tested
          at run-time.

          Any tuple return value is automatically unpacked to the positional
          args of ``cc``. To return multiple things as one without the implicit
          unpacking, use a ``list``.

        - An explicit ``return somefunc(arg0, ..., k0=v0, ...)`` actually means
          a tail-call to ``somefunc``, with its ``cc`` automatically set to our
          ``cc``. Hence this inserts a call to ``somefunc`` before proceeding
          with our current continuation. (This is most often what we want when
          making a tail-call from a continuation-enabled function.)

          Here ``somefunc`` **must** be a continuation-enabled function;
          otherwise the TCO chain will break and the result is immediately
          returned to the top-level caller.

          (If the call succeeds at all; the ``cc`` argument is implicitly
          filled in and passed by name. Regular functions usually do not
          accept a named parameter ``cc``, let alone know what to do with it.)

        - Just like in ``with tco``, a lambda body is analyzed as one big
          return-value expression. This uses the exact same analyzer; for example,
          ``do[]`` (including any implicit ``do[]``) and the ``let[]`` expression
          family are supported.

      - Calls from functions defined in one ``with continuations`` block to those
        defined in another are ok; there is no state or context associated with
        the block.

      - Much of the language works as usual.

        Any non-tail calls can be made normally. Regular functions can be called
        normally in any non-tail position.

        Continuation-enabled functions behave as regular functions when
        called normally; only tail calls implicitly set ``cc``. A normal call
        uses ``identity`` as the default ``cc``.

      - For technical reasons, the ``return`` statement is not allowed at the
        top level of the ``with continuations:`` block. (Because a continuation
        is essentially a function, ``return`` would behave differently based on
        whether it is placed lexically before or after a ``call_cc[]``.)

        If you absolutely need to terminate the function surrounding the
        ``with continuations:`` block from inside the block, use an exception
        to escape; see ``call_ec``, ``catch``, ``throw``.

    **Capturing the continuation**:

    Inside a ``with continuations:`` block, the ``call_cc[]`` statement
    captures a continuation. (It is actually a macro, for technical reasons.)

    For various possible program topologies that continuations may introduce, see
    the clarifying pictures under ``doc/`` in the source distribution.

    Syntax::

        x = call_cc[func(...)]
        *xs = call_cc[func(...)]
        x0, ... = call_cc[func(...)]
        x0, ..., *xs = call_cc[func(...)]
        call_cc[func(...)]

    Conditional variant::

        x = call_cc[f(...) if p else g(...)]
        *xs = call_cc[f(...) if p else g(...)]
        x0, ... = call_cc[f(...) if p else g(...)]
        x0, ..., *xs = call_cc[f(...) if p else g(...)]
        call_cc[f(...) if p else g(...)]

    Assignment targets:

     - To destructure a multiple-values (from a tuple return value),
       use a tuple assignment target (comma-separated names, as usual).

     - The last assignment target may be starred. It is transformed into
       the vararg (a.k.a. ``*args``) of the continuation function.
       (It will capture a whole tuple, or any excess items, as usual.)

     - To ignore the return value (useful if ``func`` was called only to
       perform its side-effects), just omit the assignment part.

    Conditional variant:

     - ``p`` is any expression. If truthy, ``f(...)`` is called, and if falsey,
       ``g(...)`` is called.

     - Each of ``f(...)``, ``g(...)`` may be ``None``. A ``None`` skips the
       function call, proceeding directly to the continuation. Upon skipping,
       all assignment targets (if any are present) are set to ``None``.
       The starred assignment target (if present) gets the empty tuple.

     - The main use case of the conditional variant is for things like::

           with continuations:
               k = None
               def setk(cc):
                   global k
                   k = cc
               def dostuff(x):
                   call_cc[setk() if x > 10 else None]  # capture only if x > 10
                   ...

    To keep things relatively straightforward, a ``call_cc[]`` is only
    allowed to appear **at the top level** of:

      - the ``with continuations:`` block itself
      - a ``def`` or ``async def``

    Nested defs are ok; here *top level* only means the top level of the
    *currently innermost* ``def``.

    If you need to place ``call_cc[]`` inside a loop, use ``@looped`` et al.
    from ``unpythonic.fploop``; this has the loop body represented as the
    top level of a ``def``.

    Multiple ``call_cc[]`` statements in the same function body are allowed.
    These essentially create nested closures.

    **Main differences to Scheme and Racket**:

    Compared to Scheme/Racket, where ``call/cc`` will capture also expressions
    occurring further up in the call stack, our ``call_cc`` may be need to be
    placed differently (further out, depending on what needs to be captured)
    due to the delimited nature of the continuations implemented here.

    Scheme and Racket implicitly capture the continuation at every position,
    whereas we do it explicitly, only at the use sites of the ``call_cc`` macro.

    Also, since there are limitations to where a ``call_cc[]`` may appear, some
    code may need to be structured differently to do some particular thing, if
    porting code examples originally written in Scheme or Racket.

    Unlike ``call/cc`` in Scheme/Racket, ``call_cc`` takes **a function call**
    as its argument, not just a function reference. Also, there's no need for
    it to be a one-argument function; any other args can be passed in the call.
    The ``cc`` argument is filled implicitly and passed by name; any others are
    passed exactly as written in the client code.

    **Technical notes**:

    The ``call_cc[]`` statement essentially splits its use site into *before*
    and *after* parts, where the *after* part (the continuation) can be run
    a second and further times, by later calling the callable that represents
    the continuation. This makes a computation resumable from a desired point.

    The return value of the continuation is whatever the original function
    returns, for any ``return`` statement that appears lexically after the
    ``call_cc[]``.

    The effect of ``call_cc[]`` is that the function call ``func(...)`` in
    the brackets is performed, with its ``cc`` argument set to the lexically
    remaining statements of the current ``def`` (at the top level, the rest
    of the ``with continuations`` block), represented as a callable.

    The continuation itself ends there (it is *delimited* in this particular
    sense), but it will chain to the ``cc`` of the function it appears in.
    This is termed the *parent continuation* (**pcc**), stored in the internal
    variable ``_pcc`` (which defaults to ``None``).

    Via the use of the pcc, here ``f`` will maintain the illusion of being
    just one function, even though a ``call_cc`` appears there::

        def f(*, cc):
            ...
            call_cc[g(1, 2, 3)]
            ...

    The continuation is a closure. For its pcc, it will use the value the
    original function's ``cc`` had when the definition of the continuation
    was executed (for that particular instance of the closure). Hence, calling
    the original function again with its ``cc`` set to something else will
    produce a new continuation instance that chains into that new ``cc``.

    The continuation's own ``cc`` will be ``identity``, to allow its use just
    like any other function (also as argument of a ``call_cc`` or target of a
    tail call).

    When the pcc is set (not ``None``), the effect is to run the pcc first,
    and ``cc`` only after that. This preserves the whole captured tail of a
    computation also in the presence of nested ``call_cc`` invocations (in the
    above example, this would occur if also ``g`` used ``call_cc``).

    Continuations are not accessible by name (their definitions are named by
    gensym). To get a reference to a continuation instance, stash the value
    of the ``cc`` argument somewhere while inside the ``call_cc``.

    The function ``func`` called by a ``call_cc[func(...)]`` is (almost) the
    only place where the ``cc`` argument is actually set. There it is the
    captured continuation. Roughly everywhere else, ``cc`` is just ``identity``.

    Tail calls are an exception to this rule; a tail call passes along the current
    value of ``cc``, unless overridden manually (by setting the ``cc=...`` kwarg
    in the tail call).

    When the pcc is set (not ``None``) at the site of the tail call, the
    machinery will create a composed continuation that runs the pcc first,
    and ``cc`` (whether current or manually overridden) after that. This
    composed continuation is then passed to the tail call as its ``cc``.

    **Tips**:

      - Once you have a captured continuation, one way to use it is to set
        ``cc=...`` manually in a tail call, as was mentioned. Example::

            def main():
                call_cc[myfunc()]  # call myfunc, capturing the current cont...
                ...                # ...which is the rest of "main"

            def myfunc(cc):
                ourcc = cc  # save the captured continuation (sent by call_cc[])
                def somefunc():
                    return dostuff(..., cc=ourcc)  # and use it here
                somestack.append(somefunc)

        In this example, when ``somefunc`` is eventually called, it will tail-call
        ``dostuff`` and then proceed with the continuation ``myfunc`` had
        at the time when that instance of the ``somefunc`` closure was created.
        (This pattern is essentially how to build the ``amb`` operator.)

      - Instead of setting ``cc``, you can also overwrite ``cc`` with a captured
        continuation inside a function body. That overrides the continuation
        for the rest of the dynamic extent of the function, not only for a
        particular tail call::

            def myfunc(cc):
                ourcc = cc
                def somefunc():
                    cc = ourcc
                    return dostuff(...)
                somestack.append(somefunc)

      - A captured continuation can also be called manually; it's just a callable.

        The assignment targets, at the ``call_cc[]`` use site that spawned this
        particular continuation, specify its call signature. All args are
        positional, except the implicit ``cc``, which is by-name-only.

      - Just like in Scheme/Racket's ``call/cc``, the values that get bound
        to the ``call_cc[]`` assignment targets on second and further calls
        (when the continuation runs) are the arguments given to the continuation
        when it is called (whether implicitly or manually).

      - Setting ``cc`` to ``unpythonic.fun.identity``, while inside a ``call_cc``,
        will short-circuit the rest of the computation. In such a case, the
        continuation will not be invoked automatically. A useful pattern for
        suspend/resume.

      - However, it is currently not possible to prevent the rest of the tail
        of a captured continuation (the pcc) from running, apart from manually
        setting ``_pcc`` to ``None`` before executing a ``return``. Note that
        doing that is not strictly speaking supported (and may be subject to
        change in a future version).

      - When ``call_cc[]`` appears inside a function definition:

          - It tail-calls ``func``, with its ``cc`` set to the captured
            continuation.

          - The return value of the function containing one or more ``call_cc[]``
            statements is the return value of the continuation.

      - When ``call_cc[]`` appears at the top level of ``with continuations``:

          - A normal call to ``func`` is made, with its ``cc`` set to the captured
            continuation.

          - In this case, if the continuation is called later, it always
            returns ``None``, because the use site of ``call_cc[]`` is not
            inside a function definition.

      - If you need to insert just a tail call (no further statements) before
        proceeding with the current continuation, no need for ``call_cc[]``;
        use ``return func(...)`` instead.

        The purpose of ``call_cc[func(...)]`` is to capture the current
        continuation (the remaining statements), and hand it to ``func``
        as a first-class value.

      - To combo with ``multilambda``, use this ordering::

            with multilambda, continuations:
                ...

      - Some very limited comboability with ``call_ec``. May be better to plan
        ahead, using ``call_cc[]`` at the appropriate outer level, and then
        short-circuit (when needed) by setting ``cc`` to ``identity``.
        This avoids the need to have both ``call_cc`` and ``call_ec`` at the
        same time.

      - ``unpythonic.ec.call_ec`` can be used normally **lexically before any**
        ``call_cc[]``, but (in a given function) after at least one ``call_cc[]``
        has run, the ``ec`` ceases to be valid. This is because our ``call_cc[]``
        actually splits the function into *before* and *after* parts, and
        **tail-calls** the *after* part.

        (Wrapping the ``def`` in another ``def``, and placing the ``call_ec``
        on the outer ``def``, does not help either, because even the outer
        function has exited by the time *the continuation* is later called
        the second and further times.)

        Usage of ``call_ec`` while inside a ``with continuations`` block is::

            with continuations:
                @call_ec
                def result(ec):
                    print("hi")
                    ec(42)
                    print("not reached")
                assert result == 42

                result = call_ec(lambda ec: do[print("hi"),
                                               ec(42),
                                               print("not reached")])

        Note the signature of ``result``. Essentially, ``ec`` is a function
        that raises an exception (to escape to a dynamically outer context),
        whereas the implicit ``cc`` is the closure-based continuation handled
        by the continuation machinery.

        See the ``tco`` macro for details on the ``call_ec`` combo.
    """
    if syntax != "block":
        raise SyntaxError("continuations is a block macro only")  # pragma: no cover
    if syntax == "block" and kw['optional_vars'] is not None:
        raise SyntaxError("continuations does not take an as-part")  # pragma: no cover

    # Two-pass macro.
    with dyn.let(_macro_expander=expander):
        return _continuations(block_body=tree)

def call_cc(tree, **kw):
    """[syntax] Only meaningful in a "with continuations" block.

    Syntax cheat sheet::

        x = call_cc[func(...)]
        *xs = call_cc[func(...)]
        x0, ... = call_cc[func(...)]
        x0, ..., *xs = call_cc[func(...)]
        call_cc[func(...)]

    Conditional variant::

        x = call_cc[f(...) if p else g(...)]
        *xs = call_cc[f(...) if p else g(...)]
        x0, ... = call_cc[f(...) if p else g(...)]
        x0, ..., *xs = call_cc[f(...) if p else g(...)]
        call_cc[f(...) if p else g(...)]

    where ``f()`` or ``g()`` may be ``None`` instead of a function call.

    For more, see the docstring of ``continuations``.
    """
    if _continuations_level.value < 1:
        raise SyntaxError("call_cc[] is only meaningful in a `with continuations` block.")  # pragma: no cover, not meant to hit the expander (expanded away by `with continuations`)
    return UnpythonicCallCcMarker(tree)


# --------------------------------------------------------------------------------
# Syntax transformers

# Implicit return statement. This performs a tail-position analysis of function bodies.
def _autoreturn(block_body):
    class AutoreturnTransformer(ASTTransformer):
        def transform(self, tree):
            if is_captured_value(tree):
                return tree  # don't recurse!
            if type(tree) in (FunctionDef, AsyncFunctionDef):
                tree.body[-1] = transform_tailstmt(tree.body[-1])
            return self.generic_visit(tree)
    def transform_tailstmt(tree):
        # TODO: For/AsyncFor/While?
        if type(tree) is If:
            tree.body[-1] = transform_tailstmt(tree.body[-1])
            if tree.orelse:
                tree.orelse[-1] = transform_tailstmt(tree.orelse[-1])
        elif type(tree) in (With, AsyncWith):
            tree.body[-1] = transform_tailstmt(tree.body[-1])
        elif type(tree) is Try:
            # We don't care about finalbody; typically used for unwinding only.
            if tree.orelse:  # tail position is in else clause if present
                tree.orelse[-1] = transform_tailstmt(tree.orelse[-1])
            else:  # tail position is in the body of the "try"
                tree.body[-1] = transform_tailstmt(tree.body[-1])
            # additionally, tail position is in each "except" handler
            for handler in tree.handlers:
                handler.body[-1] = transform_tailstmt(handler.body[-1])
        elif type(tree) is Expr:
            tree = Return(value=tree.value)
        return tree
    # This is a first-pass macro. Any nested macros should get clean standard Python,
    # not having to worry about implicit "return" statements.
    return AutoreturnTransformer().visit(block_body)


# Automatic TCO. This is the same framework as in "continuations", in its simplest form.
def _tco(block_body):
    # first pass, outside-in
    userlambdas = detect_lambda(block_body)
    known_ecs = list(uniqify(detect_callec(block_body)))

    block_body = dyn._macro_expander.visit(block_body)

    # second pass, inside-out
    transform_retexpr = partial(_transform_retexpr)
    new_block_body = []
    for stmt in block_body:
        # skip nested, already expanded "with continuations" blocks
        # (needed to support continuations in the Lispython dialect, which applies tco globally)
        if isexpandedmacromarker("ExpandedContinuationsMarker", stmt):
            new_block_body.append(stmt)
            continue

        stmt = _tco_transform_return(stmt, known_ecs=known_ecs,
                                     transform_retexpr=transform_retexpr)
        stmt = _tco_transform_def(stmt, preproc_cb=None)
        stmt = _tco_transform_lambda(stmt, preproc_cb=None,
                                     userlambdas=userlambdas,
                                     known_ecs=known_ecs,
                                     transform_retexpr=transform_retexpr)
        stmt = sort_lambda_decorators(stmt)
        new_block_body.append(stmt)
    return new_block_body


# -----------------------------------------------------------------------------
# True multi-shot continuations for Python, based on a CPS transformation.

# _pcc/cc chaining handler, to be exported to client code via q[h[]].
#
# We handle multiple-return-values like the rest of unpythonic does:
# returning a tuple means returning multiple values. Unpack them
# to cc's arglist.
#
def chain_conts(cc1, cc2, with_star=False):  # cc1=_pcc, cc2=cc
    """Internal function, used in code generated by the continuations macro."""
    if with_star:  # to be chainable from a tail call, accept a multiple-values arglist
        if cc1 is not None:
            @passthrough_lazy_args
            def cc(*value):
                return jump(cc1, cc=cc2, *value)
        else:
            # Beside a small optimization, it is important to preserve
            # "identity" as "identity", so that the call_cc logic that
            # defines the continuation functions will detect it and
            # know when to set _pcc (and importantly, when not to).
            cc = cc2
    else:  # for inert data value returns (this produces the multiple-values arglist)
        if cc1 is not None:
            @passthrough_lazy_args
            def cc(value):
                if isinstance(value, tuple):
                    return jump(cc1, cc=cc2, *value)
                else:
                    return jump(cc1, value, cc=cc2)
        else:
            @passthrough_lazy_args
            def cc(value):
                if isinstance(value, tuple):
                    return jump(cc2, *value)
                else:
                    return jump(cc2, value)
    return cc


_continuations_level = NestingLevelTracker()  # for checking validity of call_cc[]

class UnpythonicContinuationsMarker(ASTMarker):
    """AST marker related to the unpythonic's continuations (call_cc) subsystem."""
class UnpythonicCallCcMarker(UnpythonicContinuationsMarker):
    """AST marker denoting a `call_cc[]` invocation."""


def _continuations(block_body):
    # This is a very loose pythonification of Paul Graham's continuation-passing
    # macros in On Lisp, chapter 20.
    #
    # We don't have an analog of PG's "=apply", since Python doesn't need "apply"
    # to pass in varargs.

    # first pass, outside-in
    userlambdas = detect_lambda(block_body)
    known_ecs = list(uniqify(detect_callec(block_body)))

    with _continuations_level.changed_by(+1):
        block_body = dyn._macro_expander.visit(block_body)

    # second pass, inside-out

    # _tco_transform_def and _tco_transform_lambda correspond to PG's
    # "=defun" and "=lambda", but we don't need to generate a macro.
    #
    # Here we define only the callback to perform the additional transformations
    # we need for the continuation machinery.
    def transform_args(tree):
        assert type(tree) in (FunctionDef, AsyncFunctionDef, Lambda)
        # Add a cc kwarg if the function has no cc arg.
        posnames = [arg.arg for arg in tree.args.args]  # positional-or-keyword
        kwonlynames = [kw.arg for kw in tree.args.kwonlyargs]
        if "cc" not in posnames + kwonlynames:
            tree.args.kwonlyargs = tree.args.kwonlyargs + [arg(arg="cc")]
            tree.args.kw_defaults = tree.args.kw_defaults + [None]  # not set
            kwonlynames.append("cc")
        # Patch in the default (if possible), i.e. the identity continuation,
        # to allow regular (non-tail) calls without explicitly passing a continuation.
        if "cc" in posnames:
            j = posnames.index("cc")
            na = len(posnames)
            nd = len(tree.args.defaults)  # defaults apply to n last args
            if j == na - nd - 1:  # last one that has no default
                tree.args.defaults.insert(0, q[h[identity]])
        else:  # "cc" in kwonlynames:
            j = kwonlynames.index("cc")
            if tree.args.kw_defaults[j] is None:  # not already set
                tree.args.kw_defaults[j] = q[h[identity]]
        # implicitly add "parent cc" arg for treating the tail of a computation
        # as one entity (only actually used in continuation definitions created by
        # call_cc; everywhere else, it's None). See callcc_topology.pdf for clarifying pictures.
        if "_pcc" not in kwonlynames:
            non = q[None]
            non = copy_location(non, tree)
            tree.args.kwonlyargs = tree.args.kwonlyargs + [arg(arg="_pcc")]
            tree.args.kw_defaults = tree.args.kw_defaults + [non]  # has the value None **at runtime**
        return tree

    # _tco_transform_return corresponds to PG's "=values".
    # It uses _transform_retexpr to transform return-value expressions
    # and arguments of calls to escape continuations.
    #
    # Ours is applied automatically to all return statements (and calls to
    # escape continuations) in the block, and there's some extra complexity
    # to support IfExp, BoolOp, and the do and let macros in return-value expressions.
    #
    # Already performed by the TCO machinery:
    #     return f(...) --> return jump(f, ...)
    #
    # Additional transformations needed here:
    #     return jump(f, ...) --> return jump(f, cc=cc, ...)  # customize the transform to add the cc kwarg
    #     return value --> return jump(cc, value)
    #     return v1, ..., vn --> return jump(cc, *(v1, ..., vn))
    #
    # Here we only customize the transform_retexpr callback to pass our
    # current continuation (if no continuation already specified by user).
    def call_cb(tree):  # add the cc kwarg (this plugs into the TCO transformation)
        # we're a postproc; our input is "jump(some_target_func, *args)"
        hascc = any(kw.arg == "cc" for kw in tree.keywords)
        if hascc:
            # chain our _pcc and the cc=... manually provided by the user
            thekw = [kw for kw in tree.keywords if kw.arg == "cc"][0]  # exactly one
            usercc = thekw.value
            thekw.value = q[h[chain_conts](n["_pcc"], a[usercc], with_star=True)]
        else:
            # chain our _pcc and the current value of cc
            tree.keywords = [keyword(arg="cc", value=q[h[chain_conts](n["_pcc"], n["cc"], with_star=True)])] + tree.keywords
        return tree
    def data_cb(tree):  # transform an inert-data return value into a tail-call to cc.
        tree = q[h[chain_conts](n["_pcc"], n["cc"])(a[tree])]
        return tree
    transform_retexpr = partial(_transform_retexpr, call_cb=call_cb, data_cb=data_cb)

    # CPS conversion, essentially the call/cc. Corresponds to PG's "=bind".
    #
    # But we have a code walker, so we don't need to require the body to be
    # specified inside the body of the macro invocation like PG's solution does.
    # Instead, we capture as the continuation all remaining statements (i.e.
    # those that lexically appear after the ``call_cc[]``) in the current block.
    def iscallcc(tree):
        if type(tree) not in (Assign, Expr):
            return False
        return isinstance(tree.value, UnpythonicCallCcMarker)
    def split_at_callcc(body):
        if not body:
            return [], None, []
        before, after = [], body
        while True:
            stmt, *after = after
            if iscallcc(stmt):
                # after is always non-empty here (has at least the explicitified "return")
                # ...unless we're at the top level of the "with continuations" block
                if not after:
                    raise SyntaxError("call_cc[] cannot appear as the last statement of a 'with continuations' block (no continuation to capture)")  # pragma: no cover
                # TODO: To support Python's scoping properly in assignments after the `call_cc`,
                # TODO: we have to scan `before` for assignments to local variables (stopping at
                # TODO: scope boundaries; use `unpythonic.syntax.scoping.get_names_in_store_context`,
                # TODO: and declare those variables `nonlocal` in `after`. This way the binding
                # TODO: will be shared between the original context and the continuation.
                # See Politz et al 2013 (the "full monty" paper), section 4.2.
                return before, stmt, after
            before.append(stmt)
            if not after:
                return before, None, []
    def analyze_callcc(stmt):
        starget = None  # "starget" = starred target, becomes the vararg for the cont
        def maybe_starred(expr):  # return expr.id or set starget
            nonlocal starget
            if type(expr) is Name:
                return [expr.id]
            elif type(expr) is Starred:
                if type(expr.value) is not Name:
                    raise SyntaxError("call_cc[] starred assignment target must be a bare name")  # pragma: no cover
                starget = expr.value.id
                return []
            raise SyntaxError("all call_cc[] assignment targets must be bare names (last one may be starred)")  # pragma: no cover
        # extract the assignment targets (args of the cont)
        if type(stmt) is Assign:
            if len(stmt.targets) != 1:
                raise SyntaxError("expected at most one '=' in a call_cc[] statement")  # pragma: no cover
            target = stmt.targets[0]
            if type(target) in (Tuple, List):
                rest, last = target.elts[:-1], target.elts[-1]
                # TODO: limitation due to Python's vararg syntax - the "*args" must be after positional args.
                if any(type(x) is Starred for x in rest):
                    raise SyntaxError("in call_cc[], only the last assignment target may be starred")  # pragma: no cover
                if not all(type(x) is Name for x in rest):
                    raise SyntaxError("all call_cc[] assignment targets must be bare names")  # pragma: no cover
                targets = [x.id for x in rest] + maybe_starred(last)
            else:  # single target
                targets = maybe_starred(target)
        elif type(stmt) is Expr:  # no assignment targets, cont takes no args
            targets = []
        else:
            raise SyntaxError(f"call_cc[]: expected an assignment or a bare expr, got {stmt}")  # pragma: no cover
        # extract the function call(s)
        if not isinstance(stmt.value, UnpythonicCallCcMarker):  # both Assign and Expr have a .value
            assert False  # we should get only valid call_cc[] invocations that pass the `iscallcc` test  # pragma: no cover
        theexpr = stmt.value.body  # discard the AST marker
        if not (type(theexpr) in (Call, IfExp) or (type(theexpr) in (Constant, NameConstant) and getconstant(theexpr) is None)):
            raise SyntaxError("the bracketed expression in call_cc[...] must be a function call, an if-expression, or None")  # pragma: no cover
        def extract_call(tree):
            if type(tree) is Call:
                return tree
            elif type(tree) in (Constant, NameConstant) and getconstant(tree) is None:
                return None
            else:
                raise SyntaxError("call_cc[...]: expected a function call or None")  # pragma: no cover
        if type(theexpr) is IfExp:
            condition = theexpr.test
            thecall = extract_call(theexpr.body)
            altcall = extract_call(theexpr.orelse)
        else:
            condition = altcall = None
            thecall = extract_call(theexpr)
        return targets, starget, condition, thecall, altcall
    def make_continuation(owner, callcc, contbody):
        targets, starget, condition, thecall, altcall = analyze_callcc(callcc)

        # no-args special case: allow but ignore one arg so there won't be arity errors
        # from a "return None"-generated None being passed into the cc
        # (in Python, a function always has a return value, though it may be None)
        if not targets and not starget:
            targets = ["_ignored_arg"]
            posargdefaults = [q[None]]
        else:
            posargdefaults = []

        # Name the continuation: f_cont, f_cont1, f_cont2, ...
        # if multiple call_cc[]s in the same function body.
        if owner:
            # TODO: robustness: use regexes, strip suf and any numbers at the end, until no match.
            # return prefix of s before the first occurrence of suf.
            def strip_suffix(s, suf):
                n = s.find(suf)
                if n == -1:
                    return s
                return s[:n]
            stripped_ownername = strip_suffix(owner.name, '_cont')
            basename = f"{stripped_ownername}_cont"
        else:
            basename = "cont"
        contname = gensym(basename)

        # Set our captured continuation as the cc of f and g in
        #   call_cc[f(...)]
        #   call_cc[f(...) if p else g(...)]
        def prepare_call(tree):
            if tree:
                tree.keywords = [keyword(arg="cc", value=q[n[contname]])] + tree.keywords
            else:  # no call means proceed to cont directly, with args set to None
                tree = q[n[contname](*([None] * u[len(targets)]), cc=n["cc"])]
            return tree
        thecall = prepare_call(thecall)
        if condition:
            altcall = prepare_call(altcall)

        # Create the continuation function, set contbody as its body.
        #
        # Any return statements in the body have already been transformed,
        # because they appear literally in the code at the use site,
        # and our main processing logic runs the return statement transformer
        # before transforming call_cc[].
        #
        # TODO: Fix async/await support. See https://github.com/Technologicat/unpythonic/issues/4
        # TODO: We should at least `await` the continuation when calling it. Maybe something else
        # TODO: needs to be modified, too.
        #
        FDef = type(owner) if owner else FunctionDef  # use same type (regular/async) as parent function
        non = q[None]
        maybe_capture = IfExp(test=q[n["cc"] is not h[identity]],
                              body=q[n["cc"]],
                              orelse=non)
        contarguments = arguments(args=[arg(arg=x) for x in targets],
                                  kwonlyargs=[arg(arg="cc"), arg(arg="_pcc")],
                                  vararg=(arg(arg=starget) if starget else None),
                                  kwarg=None,
                                  defaults=posargdefaults,
                                  kw_defaults=[q[h[identity]], maybe_capture])
        if sys.version_info >= (3, 8, 0):  # Python 3.8+: positional-only arguments
            contarguments.posonlyargs = []
        funcdef = FDef(name=contname,
                       args=contarguments,
                       body=contbody,
                       decorator_list=[],  # patched later by transform_def
                       returns=None)  # return annotation not used here

        # in the output stmts, define the continuation function...
        newstmts = [funcdef]
        if owner:  # ...and tail-call it (if currently inside a def)
            def jumpify(tree):
                tree.args = [tree.func] + tree.args
                tree.func = q[h[jump]]
            jumpify(thecall)
            if condition:
                jumpify(altcall)
                newstmts.append(If(test=condition,
                                   body=[Return(value=q[a[thecall]])],
                                   orelse=[Return(value=q[a[altcall]])]))
            else:
                newstmts.append(Return(value=q[a[thecall]]))
        else:  # ...and call it normally (if at the top level)
            if condition:
                newstmts.append(If(test=condition,
                                   body=[Expr(value=q[a[thecall]])],
                                   orelse=[Expr(value=q[a[altcall]])]))
            else:
                newstmts.append(Expr(value=q[a[thecall]]))
        return newstmts
    class CallccTransformer(ASTTransformer):  # find and transform call_cc[] statements inside function bodies
        def transform(self, tree):
            if is_captured_value(tree):
                return tree  # don't recurse!
            if type(tree) in (FunctionDef, AsyncFunctionDef):
                tree.body = transform_callcc(tree, tree.body)
            return self.generic_visit(tree)
    def transform_callcc(owner, body):
        # owner: FunctionDef or AsyncFunctionDef node, or None (top level of block)
        # body: list of stmts
        # we need to consider only one call_cc in the body, because each one
        # generates a new nested def for the walker to pick up.
        before, callcc, after = split_at_callcc(body)
        if callcc:
            body = before + make_continuation(owner, callcc, contbody=after)
        return body
    # TODO: improve error reporting for stray call_cc[] invocations
    class StrayCallccChecker(ASTVisitor):
        def examine(self, tree):
            if iscallcc(tree):
                raise SyntaxError("call_cc[...] only allowed at the top level of a def or async def, or at the top level of the block; must appear as an expr or an assignment RHS")  # pragma: no cover
            if type(tree) in (Assign, Expr):
                v = tree.value
                if type(v) is Call and type(v.func) is Name and v.func.id == "call_cc":
                    raise SyntaxError("call_cc(...) should be call_cc[...] (note brackets; it's a macro)")  # pragma: no cover
            self.generic_visit(tree)

    # -------------------------------------------------------------------------
    # Main processing logic begins here
    # -------------------------------------------------------------------------

    # Disallow return at the top level of the block, because it would behave
    # differently depending on whether placed before or after the first call_cc[]
    # invocation. (Because call_cc[] internally creates a function and calls it.)
    for stmt in block_body:
        if type(stmt) is Return:
            raise SyntaxError("'return' not allowed at the top level of a 'with continuations' block")  # pragma: no cover

    # Since we transform **all** returns (even those with an inert data value)
    # into tail calls (to cc), we must insert any missing implicit bare "return"
    # statements so that _tco_transform_return() sees them.
    #
    # Note that a bare "return" returns `None`, but in the AST `return` looks
    # different from `return None`.
    class ImplicitBareReturnInjector(ASTTransformer):
        def transform(self, tree):
            if is_captured_value(tree):
                return tree  # don't recurse!
            if type(tree) in (FunctionDef, AsyncFunctionDef):
                if type(tree.body[-1]) is not Return:
                    tree.body.append(Return(value=None))  # bare "return"
            return self.generic_visit(tree)
    block_body = ImplicitBareReturnInjector().visit(block_body)

    # transform "return" statements before call_cc[] invocations generate new ones.
    block_body = [_tco_transform_return(stmt, known_ecs=known_ecs,
                                        transform_retexpr=transform_retexpr)
                     for stmt in block_body]

    # transform call_cc[] invocations
    block_body = transform_callcc(owner=None, body=block_body)  # at top level
    block_body = CallccTransformer().visit(block_body)  # inside defs
    # Validate. Each call_cc[] reached by the transformer was in a syntactically correct
    # position and has now been eliminated. Any remaining ones indicate syntax errors.
    StrayCallccChecker().visit(block_body)

    # set up the default continuation that just returns its args
    # (the top-level "cc" is only used for continuations created by call_cc[] at the top level of the block)
    new_block_body = [Assign(targets=[q[n["cc"]]], value=q[h[identity]])]

    # transform all defs (except the chaining handler), including those added by call_cc[].
    for stmt in block_body:
        stmt = _tco_transform_def(stmt, preproc_cb=transform_args)
        stmt = _tco_transform_lambda(stmt, preproc_cb=transform_args,
                                     userlambdas=userlambdas,
                                     known_ecs=known_ecs,
                                     transform_retexpr=transform_retexpr)
        stmt = sort_lambda_decorators(stmt)
        new_block_body.append(stmt)

    # Leave a marker so "with tco", if applied, can ignore the expanded "with continuations" block
    # (needed to support continuations in the Lispython dialect, since it applies tco globally.)
    return wrapwith(item=q[h[ExpandedContinuationsMarker]],
                    body=new_block_body)

# -----------------------------------------------------------------------------

def _tco_transform_def(tree, *, preproc_cb):
    class TcoDefTransformer(ASTTransformer):
        def transform(self, tree):
            if is_captured_value(tree):
                return tree  # don't recurse!
            if type(tree) in (FunctionDef, AsyncFunctionDef):
                if preproc_cb:
                    tree = preproc_cb(tree)
                # Enable TCO if not TCO'd already.
                if not has_tco(tree):
                    k = suggest_decorator_index("trampolined", tree.decorator_list)
                    if k is not None:
                        tree.decorator_list.insert(k, q[h[trampolined]])
                    else:  # couldn't determine insert position; just plonk it at the start and hope for the best
                        tree.decorator_list.insert(0, q[h[trampolined]])
            return self.generic_visit(tree)
    return TcoDefTransformer().visit(tree)

# Transform return statements and calls to escape continuations (ec).
# known_ecs: list of names (str) of known escape continuations.
# transform_retexpr: return-value expression transformer (for TCO and stuff).
def _tco_transform_return(tree, *, known_ecs, transform_retexpr):
    class TcoReturnTransformer(ASTTransformer):
        def transform(self, tree):
            if is_captured_value(tree):
                return tree  # don't recurse!
            if type(tree) is Return:
                non = q[None]
                non = copy_location(non, tree)
                value = tree.value or non  # return --> return None  (bare return has value=None in the AST)
                if not isec(value, known_ecs):
                    tree = Return(value=transform_retexpr(value, known_ecs))
                else:
                    # An ec call already escapes, so the return is redundant.
                    #
                    # If someone writes "return ec(...)" in a "with continuations" block,
                    # this cleans up the code, since eliminating the "return" allows us
                    # to omit a redundant "let".
                    tree = Expr(value=value)  # return ec(...) --> ec(...)
            elif isec(tree, known_ecs):  # TCO the arg of an ec(...) call
                if len(tree.args) > 1:
                    raise SyntaxError("expected exactly one argument for escape continuation")  # pragma: no cover
                tree.args[0] = transform_retexpr(tree.args[0], known_ecs)
            return self.generic_visit(tree)
    return TcoReturnTransformer().visit(tree)

# userlambdas: list of ids; the purpose is to avoid transforming lambdas implicitly added by macros (do, let).
def _tco_transform_lambda(tree, *, preproc_cb, userlambdas, known_ecs, transform_retexpr):
    class TcoLambdaTransformer(ASTTransformer):
        def transform(self, tree):
            if is_captured_value(tree):
                return tree  # don't recurse!
            hastco = self.state.hastco
            # Detect a userlambda which already has TCO applied.
            #
            # Note at this point we haven't seen the lambda; at most, we're examining
            # a Call node. The checker internally descends if tree looks promising.
            if type(tree) is Call and has_tco(tree, userlambdas):
                self.generic_withstate(tree, hastco=True)  # the lambda inside the trampolined(...) is the next Lambda node we will descend into.
            elif type(tree) is Lambda and id(tree) in userlambdas:
                if preproc_cb:
                    tree = preproc_cb(tree)
                tree.body = transform_retexpr(tree.body, known_ecs)
                lam = tree
                if not hastco:  # Enable TCO if not TCO'd already.
                    # Just slap it on; we will sort_lambda_decorators() later.
                    tree = q[h[trampolined](a[tree])]
                # don't recurse on the lambda we just moved, but recurse inside it.
                self.withstate(lam.body, hastco=False)
                lam.body = self.visit(lam.body)
                return tree
            return self.generic_visit(tree)
    return TcoLambdaTransformer(hastco=False).visit(tree)

# Tail-position analysis for a return-value expression (also the body of a lambda).
# Here we need to be very, very selective about where to recurse so this would not
# benefit much from being made into an ASTTransformer. Just a function is fine.
_isjump = lambda name: name in ("jump", "loop")
def _transform_retexpr(tree, known_ecs, call_cb=None, data_cb=None):
    """Analyze and TCO a return-value expression or a lambda body.

    This performs a tail-position analysis on the given ``tree``, recursively
    handling the builtins ``a if p else b``, ``and``, ``or``; and from
    ``unpythonic.syntax``, ``do[]``, ``let[]``, ``letseq[]``, ``letrec[]``.

      - known_ecs: list of str, names of known escape continuations.

      - call_cb(tree): either None; or tree -> tree, callback for Call nodes

      - data_cb(tree): either None; or tree -> tree, callback for inert data nodes

    The callbacks (if any) may perform extra transformations; they are applied
    as postprocessing for each node of matching type, after any transformations
    performed by this macro.

    *Inert data* is defined as anything except Call, IfExp, BoolOp-with-tail-call,
    or one of the supported macros from ``unpythonic.syntax``.
    """
    transform_call = call_cb or (lambda tree: tree)
    transform_data = data_cb or (lambda tree: tree)
    def transform(tree):
        # Ignore the "lambda e: ...", and descend into the ..., in:
        #   - let[] or letrec[] in tail position.
        #     - letseq[] is a nested sequence of lets, so covers that too.
        #   - do[] in tail position.
        #     - May be generated also by a "with multilambda" block
        #       that has already expanded.
        if islet(tree):
            view = ExpandedLetView(tree)
            assert view.body, "BUG: what's this, a decorator inside a lambda?"
            thelambda = view.body  # lambda e: ...
            thelambda.body = transform(thelambda.body)
        elif isdo(tree):
            thebody = ExpandedDoView(tree).body   # list of do-items
            lastitem = thebody[-1]  # lambda e: ...
            thelambda = lastitem
            thelambda.body = transform(thelambda.body)
        elif type(tree) is Call:
            # Apply TCO to tail calls.
            #   - If already an explicit jump() or loop(), leave it alone.
            #   - If a call to an ec, leave it alone.
            #     - Because an ec call may appear anywhere, a tail-position
            #       analysis will not find all of them.
            #     - This function analyzes only tail positions within
            #       a return-value expression.
            #     - Hence, transform_return() calls us on the content of
            #       all ec nodes directly. ec(...) is like return; the
            #       argument is the retexpr.
            if not (isx(tree.func, _isjump) or isec(tree, known_ecs)):
                tree.args = [tree.func] + tree.args
                tree.func = q[h[jump]]
                tree = transform_call(tree)
        elif type(tree) is IfExp:
            # Only either body or orelse runs, so both of them are in tail position.
            # test is not in tail position.
            tree.body = transform(tree.body)
            tree.orelse = transform(tree.orelse)
        elif type(tree) is BoolOp:  # and, or
            # and/or is a combined test-and-return. Any number of these may be nested.
            # Because it is in general impossible to know beforehand how many
            # items will be actually evaluated, we define only the last item
            # (in the whole expression) to be in tail position.
            if type(tree.values[-1]) in (Call, IfExp, BoolOp):  # must match above handlers
                # other items: not in tail position, compute normally
                if len(tree.values) > 2:
                    op_of_others = BoolOp(op=tree.op, values=tree.values[:-1])
                else:
                    op_of_others = tree.values[0]
                if type(tree.op) is Or:
                    # or(data1, ..., datan, tail) --> aif[any(others), it, tail]
                    tree = q[a[_our_aif][a[op_of_others],
                                         a[transform_data(_our_it)],
                                         a[transform(tree.values[-1])]]]  # tail-call item
                elif type(tree.op) is And:
                    # and(data1, ..., datan, tail) --> tail if all(others) else False
                    tree = q[a[transform(tree.values[-1])]
                             if a[op_of_others]
                             else a[transform_data(q[False])]]
                else:  # cannot happen
                    raise SyntaxError(f"unknown BoolOp type {tree.op}")  # pragma: no cover
            else:  # optimization: BoolOp, no call or compound in tail position --> treat as single data item
                tree = transform_data(tree)
        else:
            tree = transform_data(tree)
        return tree
    return transform(tree)
