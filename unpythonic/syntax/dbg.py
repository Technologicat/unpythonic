# -*- coding: utf-8 -*-
"""Debug printer, which prints both the expression source code and its value.

Both block and expression variants are provided.

The printing can be customized; see ``dbgprint_block`` and ``dbgprint_expr``.
"""

__all__ = ["dbgprint_block", "dbg_block",
           "dbgprint_expr", "dbg_expr"]

from ast import Call, Name, keyword

from mcpyrate.quotes import macros, q, u, a, t, h  # noqa: F401

from mcpyrate import unparse
from mcpyrate.quotes import is_captured_value
from mcpyrate.walkers import ASTTransformer

from ..dynassign import dyn, make_dynvar
from ..misc import callsite_filename

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

def dbg_block(body, args):
    if args:  # custom print function hook
        # TODO: add support for Attribute to support using a method as a custom print function
        # (the problem is we must syntactically find matches in the AST, and AST nodes don't support comparison)
        if type(args[0]) is not Name:  # pragma: no cover, let's not test the macro expansion errors.
            raise SyntaxError("Custom debug print function must be specified by a bare name")
        pfunc = args[0]
        pname = pfunc.id  # name of the print function as it appears in the user code
    else:
        pfunc = q[h[dbgprint_block]]
        pname = "print"  # override standard print function within this block

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

def dbg_expr(tree):
    ln = q[u[tree.lineno]] if hasattr(tree, "lineno") else q[None]
    filename = q[h[callsite_filename]()]
    # Careful here! We must `h[]` the `dyn`, but not `dbgprint_expr` itself,
    # because we want to look up that attribute dynamically.
    return q[h[dyn].dbgprint_expr(u[unparse(tree)], a[tree], filename=a[filename], lineno=a[ln])]

make_dynvar(dbgprint_expr=dbgprint_expr)
