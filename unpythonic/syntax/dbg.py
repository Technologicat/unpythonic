# -*- coding: utf-8 -*-
"""Debug printer, which prints both the expression source code and its value.

Both block and expression variants are provided.

The printing can be customized; see ``dbgprint_block`` and ``dbgprint_expr``.
"""

__all__ = ["dbg", "dbgprint_block", "dbgprint_expr"]

from ast import Call, Name, keyword

from mcpyrate.quotes import macros, q, u, a, t, h  # noqa: F401

from mcpyrate import parametricmacro, unparse
from mcpyrate.quotes import is_captured_value
from mcpyrate.walkers import ASTTransformer

from ..dynassign import dyn, make_dynvar
from ..misc import callsite_filename

@parametricmacro
def dbg(tree, *, args, syntax, expander, **kw):
    """[syntax, expr/block] Debug-print expressions including their source code.

    **Expression variant**:

    Example::

        dbg[25 + 17]  # --> [file.py:100] (25 + 17): 42

    The transformation is::

        dbg[expr] --> dyn.dbgprint_expr(k, v, filename=__file__, lineno=xxx)

    where ``k`` is the source code of the expression and ``v`` is its value,
    and `dyn` is `unpythonic.dynassign.dyn` (hygienically captured, so you
    don't need to import it just to use the `dbg[]` macro).

    ``xxx`` is the original line number before macro expansion, if available
    in the AST node of the expression, otherwise ``None``. (Some macros might
    not care about inserting line numbers, because `mcpyrate` fixes any missing
    line numbers in a postprocess step; this is why it might be missing at some
    locations in any specific macro-enabled program.)

    A default implementation of the debug printer is provided and automatically
    assigned as the default value for `dyn.dbgprint_expr`.

    To customize the debug printing, set your custom printer function to the
    dynvar ``dbgprint_expr``, using `with dyn.let(dbgprint_expr=...)`.

    The custom function, beside performing any printing/logging as a side effect,
    **must** return the value ``v``, so that surrounding an expression with
    ``dbg[...]`` does not alter its value.

    If you want to use the default implementation as part of your customized one
    (e.g. if you want to decorate that with some logging code), it is available as
    `unpythonic.syntax.dbgprint_expr`.

    **Block variant**:

    Lexically within the block, any call to ``print`` (alternatively, if specified,
    the optional custom print function), prints both the expression source code
    and the corresponding value.

    A custom print function can be supplied as an argument. To implement a
    custom print function, see the default implementation ``dbgprint_block``
    for the signature.

    If you want to use the default implementation as part of your customized one,
    it is available as `unpythonic.syntax.dbgprint_block`.

    Examples::

        with dbg:
            x = 2
            print(x)   # --> [file.py:100] x: 2

        with dbg:
            x = 2
            y = 3
            print(x, y)   # --> [file.py:100] x: 2, y: 3
            print(x, y, sep="\n")   # --> [file.py:100] x: 2
                                    #     [file.py:100] y: 3

        prt = lambda *args, **kwargs: print(*args)
        with dbg[prt]:
            x = 2
            prt(x)     # --> ('x',) (2,)
            print(x)   # --> 2

        with dbg[prt]:
            x = 2
            y = 17
            prt(x, y, 1 + 2)  # --> ('x', 'y', '(1 + 2)'), (2, 17, 3))

    **CAUTION**: The source code is back-converted from the AST representation;
    hence its surface syntax may look slightly different to the original (e.g.
    extra parentheses). See ``mcpyrate.unparse``.
    """
    if syntax not in ("expr", "block"):
        raise SyntaxError("dbg is an expr and block macro only")  # pragma: no cover
    if syntax == "block" and kw['optional_vars'] is not None:
        raise SyntaxError("dbg (block mode) does not take an as-part")  # pragma: no cover

    # Expand inside-out.
    with dyn.let(_macro_expander=expander):
        if syntax == "expr":
            return _dbg_expr(tree)
        else:  # syntax == "block":
            return _dbg_block(body=tree, args=args)

def dbgprint_block(ks, vs, *, filename=None, lineno=None, sep=", ", **kwargs):
    """Default debug printer for the ``dbg`` macro, block variant.

    The default print format looks like::

        [/home/developer/codes/foo.py:42] x: 2, y: 3, (17 + 23): 40

    Parameters:

        ``ks``: ``tuple``
            expressions as strings

        ``vs``: ``tuple``
            the corresponding values

        ``filename``: ``str``
            filename where the debug print call occurred

        ``lineno``: number or ``None``
            line number where the debug print call occurred

        ``sep``: ``str``
            separator as in built-in ``print``,
            used between the expression/value pairs.

        ``kwargs``: anything
            passed through to built-in ``print``

    **Implementing a custom debug printer**:

    When implementing a custom print function, it **must** accept two
    positional arguments, ``ks`` and ``vs``, and two by-name arguments,
    ``filename`` and ``lineno``.

    It may also accept other arguments (see built-in ``print``), or just
    ``**kwargs`` them through to the built-in ``print``, if you like.

    Other arguments are only needed if the print calls in the ``dbg`` sections
    of your client code use them. (To be flexible, this default debug printer
    supports ``sep`` and passes everything else through.)

    The ``lineno`` argument may be ``None`` if the input resulted from macro
    expansion and the macro that generated it didn't bother to fill in the
    ``lineno`` attribute of the AST node.
    """
    header = f"[{filename}:{lineno}] "
    if "\n" in sep:
        print(sep.join(f"{header}{k}: {v}" for k, v in zip(ks, vs)), **kwargs)
    else:
        print(header + sep.join(f"{k}: {v}" for k, v in zip(ks, vs)), **kwargs)

def dbgprint_expr(k, v, *, filename, lineno):
    """Default debug printer for the ``dbg`` macro, expression variant.

    The default print format looks like::

        [/home/developer/codes/foo.py:42] (17 + 23): 40

    Parameters:

        ``k``: ``str``
            the expression source code

        ``v``: anything
            the corresponding value

        ``filename``: ``str``
            filename of the expression being debug-printed

        ``lineno``: number or ``None``
            line number of the expression being debug-printed

    **Implementing a custom debug printer**:

    When implementing a custom print function, it **must** accept two
    positional arguments, ``k`` and ``v``, and two by-name arguments,
    ``filename`` and ``lineno``.

    It **must** return ``v``, because the ``dbg[]`` macro replaces the
    original expression with the print call.

    The ``lineno`` argument may be ``None`` if the input expression resulted
    from macro expansion and the macro that generated it didn't bother to
    fill in the ``lineno`` attribute of the AST node.
    """
    print(f"[{filename}:{lineno}] {k}: {v}")
    return v  # IMPORTANT! (passthrough; debug printing is a side effect)

# --------------------------------------------------------------------------------
# Syntax transformers

def _dbg_block(body, args):
    if args:  # custom print function hook
        # TODO: add support for Attribute to support using a method as a custom print function
        # (the problem is we must syntactically find matches in the AST, and AST nodes don't support comparison)
        if type(args[0]) is not Name:  # pragma: no cover, let's not test the macro expansion errors.
            raise SyntaxError("Custom debug print function must be specified by a bare name")  # pragma: no cover
        pfunc = args[0]
        pname = pfunc.id  # name of the print function as it appears in the user code
    else:
        pfunc = q[h[dbgprint_block]]
        pname = "print"  # override standard print function within this block

    # TODO: Do we really need to expand inside-out here?
    body = dyn._macro_expander.visit_recursively(body)

    class DbgBlockTransformer(ASTTransformer):
        def transform(self, tree):
            if is_captured_value(tree):
                return tree  # don't recurse!
            if type(tree) is Call and type(tree.func) is Name and tree.func.id == pname:
                names = [q[u[unparse(node)]] for node in tree.args]  # x --> "x"; (1 + 2) --> "(1 + 2)"; ...
                names = q[t[names]]
                values = q[t[tree.args]]
                tree.args = [names, values]
                # can't use inspect.stack in the printer itself because we want the line number *before macro expansion*.
                lineno = tree.lineno if hasattr(tree, "lineno") else None
                tree.keywords += [keyword(arg="filename", value=q[h[callsite_filename]()]),
                                  keyword(arg="lineno", value=q[u[lineno]])]
                tree.func = pfunc
            return self.generic_visit(tree)
    return DbgBlockTransformer().visit(body)

def _dbg_expr(tree):
    # TODO: Do we really need to expand inside-out here?
    tree = dyn._macro_expander.visit_recursively(tree)

    ln = q[u[tree.lineno]] if hasattr(tree, "lineno") else q[None]
    filename = q[h[callsite_filename]()]
    # Careful here! We must `h[]` the `dyn`, but not `dbgprint_expr` itself,
    # because we want to look up that attribute dynamically.
    return q[h[dyn].dbgprint_expr(u[unparse(tree)], a[tree], filename=a[filename], lineno=a[ln])]

make_dynvar(dbgprint_expr=dbgprint_expr)
