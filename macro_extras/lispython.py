# -*- coding: utf-8 -*-
"""Lispython - lispy Python, powered by Pydialect and unpythonic.

This module is the dialect definition, invoked by ``dialects.DialectFinder``
when it detects a lang-import that matches the module name of this module.

This dialect is implemented in MacroPy.
"""

# TODO: fix the unpythonic.syntax block macros to leave a placeholder for
# other macros; TCO needs to detect and ignore "with continuations" blocks
# inside it in order for lispython to work properly when "with continuations"
# is manually used in a lispython program.

from ast import Expr, Name, If, Num, copy_location

from macropy.core.quotes import macros, q, name
from macropy.core.walkers import Walker

def ast_transformer(tree):
    # Skeleton for AST-transformed user module.
    with q as newbody:
        from unpythonic.syntax import macros, tco, autoreturn, \
                                      multilambda, quicklambda, namedlambda, \
                                      let, letseq, letrec, \
                                      dlet, dletseq, dletrec, \
                                      blet, bletseq, bletrec, \
                                      let_syntax, abbrev
        from unpythonic import cons, car, cdr, prod
        with autoreturn, quicklambda, multilambda, tco, namedlambda:
            name["__paste_here__"]

    # Boilerplate.
    # TODO: make a utility for the boilerplate tasks?
    def is_paste_here(tree):
        return type(tree) is Expr and type(tree.value) is Name and tree.value.id == "__paste_here__"

    module_body = tree
    if not module_body:
        assert False, "{}: expected at least one statement or expression in module body".format(__name__)

    locref = module_body[0]
    @Walker
    def splice(tree, **kw):
        if not is_paste_here(tree):
            # XXX: MacroPy's debug logger will crash if a node is missing a source location.
            # The skeleton is fully macro-generated with no location info to start with.
            if not all(hasattr(tree, x) for x in ("lineno", "col_offset")):
                return copy_location(tree, locref)
            return tree
        return If(test=Num(n=1),
                  body=module_body,
                  orelse=[],
                  lineno=locref.lineno, col_offset=locref.col_offset)
    return splice.recurse(newbody)
