# -*- coding: utf-8 -*-
"""Monadic do-notation as a block macro.

Syntax::

    with monadic_do[M] as result:
        [x := mx,
         y := my(x),
         M.guard(...)] in M.unit(x + y)

Expands to::

    result = mx >> (lambda x: my(x) >> (lambda _: M.guard(...) >> (lambda _: M.unit(x + y))))

The bindings list on the left of ``in`` uses the same ``:=`` / ``<<``
binding syntax that ``let`` uses, parsed by ``letdoutil.canonize_bindings``.

- A ``name := mexpr`` entry introduces a monadic bind: the ``name`` is
  bound to the unwrapped value for subsequent lines.
- A bare ``mexpr`` entry (no ``:=``) is a sequencing-only line — matches
  Haskell do-notation's bare-expression form, used e.g. for ``guard``:
  the result is threaded through the chain but discarded, so the whole
  shape short-circuits for monads that do (Maybe's ``Nothing``, List's
  empty, Either's ``Left``, etc.).

The RHS of ``in`` is simply the final monadic expression — same
semantics as Haskell, where the last line of a ``do`` block is any
monadic value (``return (...)``, a direct constructor call, or a call
to a monad-producing function). No specific form required.

Empty bindings shorthand is supported: ``[] in M.unit(x)`` expands to
just ``result = M.unit(x)``.

**Placement in the xmas tree**: always the innermost ``with``. Its body
shape (a single ``[bindings] in final_expr`` statement) forbids
lexically wrapping other ``with`` blocks inside it, and outer two-pass
macros (``lazify``, ``continuations``, ``tco``, ``autocurry``, etc.)
expand inner macros between their two passes, which means they will
correctly see and edit the expanded bind chain.

**Always in its own nested ``with``** — unlike the other xmas-tree
macros which chain in one ``with`` for brevity, ``monadic_do[M] as result``
has both a macro argument and an as-binding, and same-``with`` chaining
with that combo is syntactically fragile.
"""

__all__ = ["monadic_do"]

from ast import Compare, In, List, Name, NamedExpr, BinOp, LShift, Expr, Assign, Store, arg, expr

from mcpyrate.quotes import macros, q, a, n  # noqa: F401

from mcpyrate import parametricmacro

from ..dynassign import dyn

from .letdoutil import canonize_bindings


@parametricmacro
def monadic_do(tree, *, args, syntax, expander, **kw):
    """[syntax, block] Monadic do-notation.

    See module docstring for usage, placement, and expansion.
    """
    if syntax != "block":
        raise SyntaxError("monadic_do is a block macro only")  # pragma: no cover

    # Require exactly one macro argument: the monad type.
    if len(args) != 1:
        raise SyntaxError(
            f"monadic_do expects exactly one macro argument (the monad type), got {len(args)}"
        )  # pragma: no cover

    # Require the `as` binding — this is where the result lands.
    result_var = kw.get("optional_vars", None)
    if result_var is None:
        raise SyntaxError(
            "monadic_do requires an as-binding: `with monadic_do[M] as result:`"
        )  # pragma: no cover
    if type(result_var) is not Name:
        raise SyntaxError(
            "monadic_do's as-binding must be a single name"
        )  # pragma: no cover

    with dyn.let(_macro_expander=expander):
        return _monadic_do(block_body=tree, monad_type=args[0], result_name=result_var.id)


def _monadic_do(block_body: list, monad_type: expr, result_name: str) -> list:
    # Expand inner macros first (outside-in), just like `forall` and `autoref` do.
    block_body = dyn._macro_expander.visit_recursively(block_body)

    # Body must be exactly one statement, an Expr wrapping a Compare(In).
    if len(block_body) != 1:
        raise SyntaxError(
            f"monadic_do body must be a single statement of the form "
            f"`[bindings] in final_expr`, got {len(block_body)} statements"
        )  # pragma: no cover
    stmt = block_body[0]
    if type(stmt) is not Expr:
        raise SyntaxError(
            "monadic_do body must be a single expression statement "
            "`[bindings] in final_expr`"
        )  # pragma: no cover
    compare = stmt.value
    if not (type(compare) is Compare and
            len(compare.ops) == 1 and
            type(compare.ops[0]) is In):
        raise SyntaxError(
            "monadic_do body must have the form `[bindings] in final_expr`"
        )  # pragma: no cover

    bindings_node = compare.left
    final_expr = compare.comparators[0]

    # Bindings: must be a List literal.
    if type(bindings_node) is not List:
        raise SyntaxError(
            "monadic_do bindings must be a list literal `[x := mx, ...]`"
        )  # pragma: no cover

    # Wrap bare expressions as `_ := expr` so they look like sequencing-only
    # bindings to `canonize_bindings`. This mirrors Haskell's do-notation
    # where a bare expression line is sequence-only (>>, not >>=).
    normalized_elts = [
        item if _is_binding_form(item) else NamedExpr(target=Name(id="_", ctx=Store()), value=item)
        for item in bindings_node.elts
    ]

    # Parse via letdoutil — accepts := and << for each binding, and []/() for the list shape
    # (we already unpacked the outer List).
    if normalized_elts:
        canonical = canonize_bindings(normalized_elts)  # [Tuple(elts=[Name(k), v]), ...]
        pairs = [(t.elts[0].id, t.elts[1]) for t in canonical]
    else:
        pairs = []

    # Build the bind chain, innermost-first:
    #   final_expr
    #   mz >> (lambda z: final_expr)
    #   my >> (lambda y: mz >> (lambda z: final_expr))
    #   mx >> (lambda x: my >> (lambda y: mz >> (lambda z: final_expr)))
    body = final_expr
    for name, mexpr in reversed(pairs):
        # lambda <name>: <body>
        lam = q[lambda: a[body]]
        lam.args.args = [arg(arg=name)]
        # <mexpr> >> <lam>
        body = q[a[mexpr] >> a[lam]]

    # Final assignment: `<result_name> = <body>`. This is a statement; we replace
    # the entire `with` body with it.
    assignment = Assign(targets=[Name(id=result_name, ctx=Store())], value=body)
    return [assignment]


def _is_binding_form(item) -> bool:
    """Return True if *item* is ``name := expr`` or ``name << expr`` (a let-style binding).

    Two nested ``if``s (rather than a single combined expression) keep the two
    binding-syntax variants visually separate and easy to scan at the use site.
    """
    if type(item) is NamedExpr and type(item.target) is Name:
        return True
    if type(item) is BinOp and type(item.op) is LShift and type(item.left) is Name:  # noqa: SIM103 -- keep cases visually separate
        return True
    return False
