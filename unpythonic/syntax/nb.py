# -*- coding: utf-8 -*-
"""Ultralight math notebook.

Auto-print top-level expressions, auto-assign last result as _."""

# This is the kind of thing thinking with macros does to your program. ;)

from ast import Expr

from macropy.core.quotes import macros, q, ast_literal

def nb(body):
    newbody = []
    for stmt in body:
        if type(stmt) is not Expr:
            newbody.append(stmt)
            continue
        with q as newstmts:
            _ = ast_literal[stmt.value]
            print(_)
        newbody.extend(newstmts)
    return newbody
