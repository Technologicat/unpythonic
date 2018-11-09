# -*- coding: utf-8 -*-
"""Automatic TCO, continuations, implicit return statements.

The common factor is tail-position analysis."""

from functools import partial

from ast import Lambda, FunctionDef, \
                arguments, arg, keyword, \
                List, Tuple, \
                Subscript, Index, \
                Call, Name, Num, \
                BoolOp, And, Or, \
                With, If, IfExp, Try, Assign, Return, Expr, \
                copy_location
from .astcompat import AsyncFunctionDef, AsyncWith

from macropy.core.macros import macro_stub
from macropy.core.quotes import macros, q, ast_literal, name
from macropy.core.hquotes import macros, hq
from macropy.core.walkers import Walker

from .util import isx, isec, isdo, islet, \
                  detect_callec, detect_lambda, \
                  has_tco, is_decorator, sort_lambda_decorators
from .ifexprs import aif
from .letdo import let

from ..dynassign import dyn
from ..it import uniqify
from ..fun import identity
from ..tco import trampolined, jump

# -----------------------------------------------------------------------------
# Implicit return. This performs a tail-position analysis of function bodies.

def autoreturn(block_body):
    @Walker
    def transform_fdef(tree, **kw):
        if type(tree) in (FunctionDef, AsyncFunctionDef):
            tree.body[-1] = transform_tailstmt(tree.body[-1])
        return tree
    def transform_tailstmt(tree):
        # TODO: For/AsyncFor/While?
        if type(tree) is If:
            tree.body[-1] = transform_tailstmt(tree.body[-1])
            if tree.orelse:
                tree.orelse[-1] = transform_tailstmt(tree.orelse[-1])
        elif type(tree) in (With, AsyncWith):
            tree.body[-1] = transform_tailstmt(tree.body[-1])
        elif type(tree) is Try:
            # We don't care about finalbody; it is typically a finalizer.
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
    yield transform_fdef.recurse(block_body)

# -----------------------------------------------------------------------------
# Automatic TCO. This is the same framework as in "continuations", in its simplest form.

def tco(block_body):
    # first pass, outside-in
    userlambdas = detect_lambda.collect(block_body)
    known_ecs = list(uniqify(detect_callec.collect(block_body)))
    block_body = yield block_body

    # second pass, inside-out
    transform_retexpr = partial(_transform_retexpr)
    new_block_body = []
    for stmt in block_body:
        stmt = _tco_transform_return.recurse(stmt, known_ecs=known_ecs,
                                             transform_retexpr=transform_retexpr)
        stmt = _tco_transform_def.recurse(stmt, preproc_cb=None)
        stmt = _tco_transform_lambda.recurse(stmt, preproc_cb=None,
                                             userlambdas=userlambdas,
                                             known_ecs=known_ecs,
                                             transform_retexpr=transform_retexpr)
        stmt = sort_lambda_decorators(stmt)
        new_block_body.append(stmt)
    return new_block_body

# -----------------------------------------------------------------------------

@macro_stub
def bind(tree, **kw):
    """[syntax] Only meaningful in a "with bind[...] as ..."."""
    pass

def continuations(block_body):
    # This is a loose pythonification of Paul Graham's continuation-passing
    # macros in On Lisp, chapter 20.
    #
    # We don't have an analog of PG's "=apply", since Python doesn't need "apply"
    # to pass in varargs.

    # first pass, outside-in
    userlambdas = detect_lambda.collect(block_body)
    known_ecs = list(uniqify(detect_callec.collect(block_body)))
    block_body = yield block_body

    # second pass, inside-out

    # _tco_transform_def and _tco_transform_lambda correspond to PG's
    # "=defun" and "=lambda", but we don't need to generate a macro.
    #
    # Here we define only the callback to perform the additional transformations
    # we need for the continuation machinery.
    def transform_args(tree):
        assert type(tree) in (FunctionDef, AsyncFunctionDef, Lambda)
        # require explicit by-name-only arg for continuation, "cc"
        # (by name because we need to set a default value; otherwise "cc"
        #  could be positional and be placed just after "self" or "cls", if any)
        kwonlynames = [a.arg for a in tree.args.kwonlyargs]
        hascc = any(x == "cc" for x in kwonlynames)
        if not hascc:
            assert False, "functions in a 'with continuations' block must have a by-name-only arg 'cc'"
        # we could add it implicitly like this
#            tree.args.kwonlyargs = [arg(arg="cc")] + tree.args.kwonlyargs
#            tree.args.kw_defaults = [hq[identity]] + tree.args.kw_defaults
        # Patch in the default identity continuation to allow regular
        # (non-tail) calls without explicitly passing a continuation.
        j = kwonlynames.index("cc")
        if tree.args.kw_defaults[j] is None:
            tree.args.kw_defaults[j] = hq[identity]
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
    #     return f(...) --> return jump(f, cc=cc, ...)  # customize the transform to add the cc kwarg
    #     return value --> return jump(cc, value)
    #     return v1, ..., vn --> return jump(cc, *(v1, ..., vn))
    #
    # Here we only customize the transform_retexpr callback.
    def call_cb(tree):  # add the cc kwarg (this plugs into the TCO transformation)
        # Pass our current continuation (if no continuation already specified by user).
        hascc = any(kw.arg == "cc" for kw in tree.keywords)
        if not hascc:
            tree.keywords = [keyword(arg="cc", value=q[name["cc"]])] + tree.keywords
        return tree
    def data_cb(tree):  # transform an inert-data return value into a tail-call to cc.
        # Handle multiple-return-values like the rest of unpythonic does:
        # returning a tuple means returning multiple values. Unpack them
        # to cc's arglist.
        if type(tree) is Tuple:  # optimization: literal tuple, always unpack
            tree = hq[jump(name["cc"], *ast_literal[tree])]
        else:  # general case: check tupleness at run-time
            thecall_multi = hq[jump(name["cc"], *name["_retval"])]
            thecall_single = hq[jump(name["cc"], name["_retval"])]
#            tree = let([q[(name["_retval"], ast_literal[tree])]],
#                       q[ast_literal[thecall_multi]  # TODO: doesn't work, IfExp missing line number
#                         if isinstance(name["_retval"], tuple)
#                         else ast_literal[thecall_single]])
#            tree = fill_line_numbers(newtree, tree.lineno, tree.col_offset)  # doesn't work even with this.
            tree = let([q[(name["_retval"], ast_literal[tree])]],
                       IfExp(test=q[isinstance(name["_retval"], tuple)],
                             body=thecall_multi,
                             orelse=thecall_single,
                             lineno=tree.lineno, col_offset=tree.col_offset))
        return tree
    transform_retexpr = partial(_transform_retexpr, call_cb=call_cb, data_cb=data_cb)

    # Helper for "with bind".
    # bind[func(arg0, ..., k0=v0, ...)] --> func(arg0, ..., cc=cc, k0=v0, ...)
    # This roughly corresponds to PG's "=funcall".
    def isbind(tree):
        return type(tree) is Subscript and type(tree.value) is Name and tree.value.id == "bind"
    @Walker
    def transform_bind(tree, *, contname, **kw):  # contname: name of function (as bare str) to use as continuation
        if isbind(tree):
            if not (type(tree.slice) is Index and type(tree.slice.value) is Call):
                assert False, "bind: expected a single function call as subscript"
            thecall = tree.slice.value
            thecall.keywords = [keyword(arg="cc", value=q[name[contname]])] + thecall.keywords
            return thecall  # discard the bind[] wrapper
        return tree
    # Inside FunctionDef nodes:
    #     with bind[...] as ...: --> CPS transformation
    # This corresponds to PG's "=bind". This is essentially the call/cc.
    def iswithbind(tree):
        if type(tree) is With:
            if len(tree.items) == 1 and isbind(tree.items[0].context_expr):
                return True
            if any(isbind(item.context_expr) for item in tree.items):
                assert False, "the 'bind' in a 'with bind' statement must be the only context manager"
        return False
    gen_sym = dyn.gen_sym
    @Walker
    def transform_withbind(tree, *, deftypes, set_ctx, **kw):
        if type(tree) in (FunctionDef, AsyncFunctionDef):  # function definition **inside the "with continuations" block**
            set_ctx(deftypes=(deftypes + [type(tree)]))
        if not iswithbind(tree):
            return tree
        toplevel = not deftypes
        ctxmanager = tree.items[0].context_expr
        optvars = tree.items[0].optional_vars
        if optvars:
            if type(optvars) is Name:
                posargs = [optvars.id]
            elif type(optvars) in (List, Tuple):
                if not all(type(x) is Name for x in optvars.elts):
                    assert False, "with bind[...] as ... expected only names in as-part tuple/list"
                posargs = list(x.id for x in optvars.elts)
            else:
                assert False, "with bind[...] as ... expected a name, list or tuple in as-part"
        else:
            posargs = []

        # Create the continuation function, set our body as its body.
        #
        # Any return statements in the body have already been transformed,
        # because they appear literally in the code at the use site.
        thename = gen_sym("cont")
        FDef = deftypes[-1] if deftypes else FunctionDef  # use same type (regular/async) as parent function
        funcdef = FDef(name=thename,
                       args=arguments(args=[arg(arg=x) for x in posargs],
                                      kwonlyargs=[arg(arg="cc")],
                                      vararg=None,
                                      kwarg=None,
                                      defaults=[],
                                      kw_defaults=[None]),  # patched later by transform_def
                       body=tree.body,
                       decorator_list=[],  # patched later by transform_def
                       returns=None)  # return annotation not used here

        # Set up the call to func, specifying our new function as its continuation
        thecall = transform_bind.recurse(ctxmanager, contname=thename)
        if not toplevel:
            # apply TCO
            thecall.args = [thecall.func] + thecall.args
            thecall.func = hq[jump]
            # Inside a function definition, output a block that defines the
            # continuation function and then calls func, **as a tail call**
#            with q as newtree:
#                if 1:
#                    ast_literal[funcdef]  # TODO: doesn't work, why? (expected expr, not stmt - why?)
#                    return ast_literal[thecall]
#            return newtree[0]  # the if statement
            newtree = If(test=Num(n=1),
                         body=[q[ast_literal[funcdef]],
                               Return(value=q[ast_literal[thecall]])],
                         orelse=[])
        else:
            # At the top level, output a block that defines the
            # continuation function and then calls func normally.
            newtree = If(test=Num(n=1),
                         body=[q[ast_literal[funcdef]],
                               Expr(value=q[ast_literal[thecall]])],
                         orelse=[])
        return newtree

    # set up the default continuation that just returns its args
    new_block_body = [Assign(targets=[q[name["cc"]]], value=hq[identity])]
    # CPS conversion
    @Walker
    def check_for_strays(tree, **kw):
        if isbind(tree):
            assert False, "bind[...] may only appear as part of with bind[...] as ..."
        return tree
    for stmt in block_body:
        # transform "return" statements before "with bind[]"'s tail calls generate new ones.
        stmt = _tco_transform_return.recurse(stmt, known_ecs=known_ecs,
                                             transform_retexpr=transform_retexpr)
        # transform "with bind[]" blocks
        stmt = transform_withbind.recurse(stmt, deftypes=[])
        check_for_strays.recurse(stmt)
        # transform all defs, including those added by "with bind[]".
        stmt = _tco_transform_def.recurse(stmt, preproc_cb=transform_args)
        stmt = _tco_transform_lambda.recurse(stmt, preproc_cb=transform_args,
                                             userlambdas=userlambdas,
                                             known_ecs=known_ecs,
                                             transform_retexpr=transform_retexpr)
        stmt = sort_lambda_decorators(stmt)
        new_block_body.append(stmt)
    return new_block_body

# -----------------------------------------------------------------------------

@Walker
def _tco_transform_def(tree, *, preproc_cb, **kw):
    if type(tree) in (FunctionDef, AsyncFunctionDef):
        if preproc_cb:
            tree = preproc_cb(tree)
        # Enable TCO if not TCO'd already.
        #
        # @trampolined needs to be inside of @memoize, otherwise outermost;
        # so that it is applied **after** any call_ec; this allows also escapes
        # to return a jump object to the trampoline.
        if not has_tco(tree):
            ismemoize = [is_decorator(x, "memoize") for x in tree.decorator_list]
            try:
                k = ismemoize.index(True) + 1
                rest = tree.decorator_list[k:] if len(tree.decorator_list) > k else []
                tree.decorator_list = tree.decorator_list[:k] + [hq[trampolined]] + rest
            except ValueError:  # no memoize decorator in list
                tree.decorator_list = [hq[trampolined]] + tree.decorator_list
    return tree

# Transform return statements and calls to escape continuations (ec).
# known_ecs: list of names (str) of known escape continuations.
# transform_retexpr: return-value expression transformer.
@Walker
def _tco_transform_return(tree, *, known_ecs, transform_retexpr, **kw):
    treeisec = isec(tree, known_ecs)
    if type(tree) is Return:
        value = tree.value or q[None]  # return --> return None  (bare return has value=None in the AST)
        if not treeisec:
            return Return(value=transform_retexpr(value, known_ecs))
        else:
            # An ec call already escapes, so the return is redundant.
            #
            # If someone writes "return ec(...)" in a "with continuations" block,
            # this cleans up the code, since eliminating the "return" allows us
            # to omit a redundant "let".
            return Expr(value=value)  # return ec(...) --> ec(...)
    elif treeisec:  # TCO the arg of an ec(...) call
        if len(tree.args) > 1:
            assert False, "expected exactly one argument for escape continuation"
        tree.args[0] = transform_retexpr(tree.args[0], known_ecs)
    return tree

# userlambdas: list of ids; the purpose is to avoid transforming lambdas implicitly added by macros (do, let).
@Walker
def _tco_transform_lambda(tree, *, preproc_cb, userlambdas, known_ecs, transform_retexpr, stop, set_ctx, hastco=False, **kw):
    # Detect a userlambda which already has TCO applied.
    #
    # Note at this point we haven't seen the lambda; at most, we're examining
    # a Call node. The checker internally descends if tree looks promising.
    if type(tree) is Call and has_tco(tree, userlambdas):
        set_ctx(hastco=True)  # the lambda inside the trampolined(...) is the next Lambda node we will descend into.
    elif type(tree) is Lambda and id(tree) in userlambdas:
        if preproc_cb:
            tree = preproc_cb(tree)
        tree.body = transform_retexpr(tree.body, known_ecs)
        lam = tree
        if not hastco:  # Enable TCO if not TCO'd already.
            # Just slap it on; we will sort_lambda_decorators() later.
            tree = hq[trampolined(ast_literal[tree])]
        # don't recurse on the lambda we just moved, but recurse inside it.
        stop()
        _tco_transform_lambda.recurse(lam.body,
                                      preproc_cb=preproc_cb,
                                      userlambdas=userlambdas,
                                      known_ecs=known_ecs,
                                      transform_retexpr=transform_retexpr,
                                      hastco=False)
    return tree

# Tail-position analysis for a return-value expression (also the body of a lambda).
# Here we need to be very, very selective about where to recurse so this is not a Walker.
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
        if isdo(tree) or islet(tree):
            # Ignore the "lambda e: ...", and descend into the ..., in:
            #   - let[] or letrec[] in tail position.
            #     - letseq[] is a nested sequence of lets, so covers that too.
            #   - do[] in tail position.
            #     - May be generated also by a "with multilambda" block
            #       that has already expanded.
            tree.args[-1].body = transform(tree.args[-1].body)
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
            if not (isx(tree.func, "jump") or isx(tree.func, "loop") or isec(tree, known_ecs)):
                tree.args = [tree.func] + tree.args
                tree.func = hq[jump]
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
                    op_of_others = BoolOp(op=tree.op, values=tree.values[:-1],
                                          lineno=tree.lineno, col_offset=tree.col_offset)
                else:
                    op_of_others = tree.values[0]
                if type(tree.op) is Or:
                    # or(data1, ..., datan, tail) --> it if any(others) else tail
                    tree = aif(Tuple(elts=[op_of_others,
                                           transform_data(Name(id="it",
                                                               lineno=tree.lineno,
                                                               col_offset=tree.col_offset)),
                                           transform(tree.values[-1])],
                                     lineno=tree.lineno, col_offset=tree.col_offset)) # tail-call item
                elif type(tree.op) is And:
                    # and(data1, ..., datan, tail) --> tail if all(others) else False
                    fal = q[False]
                    fal = copy_location(fal, tree)
                    tree = IfExp(test=op_of_others,
                                 body=transform(tree.values[-1]),
                                 orelse=transform_data(fal))
                else:  # cannot happen
                    assert False, "unknown BoolOp type {}".format(tree.op)
            else:  # optimization: BoolOp, no call or compound in tail position --> treat as single data item
                tree = transform_data(tree)
        else:
            tree = transform_data(tree)
        return tree
    return transform(tree)
