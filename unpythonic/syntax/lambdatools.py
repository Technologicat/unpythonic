# -*- coding: utf-8 -*-
"""Lambdas with multiple expressions, local variables, and a name."""

from ast import Lambda, List, Name, Assign, With, withitem

from macropy.core.quotes import macros, u, ast_literal, name
from macropy.core.hquotes import macros, hq
from macropy.core.walkers import Walker

from ..dynassign import dyn
from ..misc import namelambda

from .letdo import do

def multilambda(block_body):
    @Walker
    def transform(tree, *, stop, **kw):
        if type(tree) is not Lambda or type(tree.body) is not List:
            return tree
        bodys = tree.body
        # bracket magic:
        # - stop() to prevent recursing to the implicit lambdas generated
        #   by the "do" we are inserting here
        #   - for each item, "do" internally inserts a lambda to delay execution,
        #     as well as to bind the environment
        #   - we must do() instead of hq[do[...]] for pickling reasons
        # - but recurse manually into each *do item*; these are explicit
        #   user-provided code so we should transform them
        stop()
        bodys = transform.recurse(bodys)
        tree.body = do(bodys)  # insert the do, with the implicit lambdas
        return tree
    # multilambda should expand first before any let[], do[] et al. that happen
    # to be inside the block, to avoid misinterpreting implicit lambdas.
    yield transform.recurse(block_body)

def namedlambda(block_body):
    def issingleassign(tree):
        return type(tree) is Assign and len(tree.targets) == 1 and type(tree.targets[0]) is Name

    @Walker
    def transform(tree, *, stop, **kw):
        if issingleassign(tree) and type(tree.value) is Lambda:
            # an assignment is a statement, so in the transformed tree,
            # we are free to use all of Python's syntax.
            myname = tree.targets[0].id
            value = tree.value
            # trick from MacroPy: to replace one statement with multiple statements,
            # use an "if 1:" block; the Python compiler optimizes it away.
            with hq as newtree:
                if 1:
#                    ast_literal[tree]   # TODO: doesn't work, why?
                    name[myname] = ast_literal[value]  # do the same thing as ast_literal[tree] should
                    namelambda(name[myname], u[myname])
            stop()  # prevent infinite loop
            return newtree[0]  # the if statement
        return tree

    new_block_body = [transform.recurse(stmt) for stmt in block_body]

#    # TODO: this syntax doesn't work due to missing line numbers?
#    with q as wrapped:  # name lambdas also in env
#        with dyn.let(env_namedlambda=True):
#            ast_literal[newtree]
#    return wrapped

    # name lambdas also in env (enabled for the dynamic extent of the block)
    item = hq[dyn.let(env_namedlambda=True)]
    wrapped = With(items=[withitem(context_expr=item, optional_vars=None)],
                   body=new_block_body)
    return [wrapped]
