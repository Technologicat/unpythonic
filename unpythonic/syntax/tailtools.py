# -*- coding: utf-8 -*-
"""Automatic TCO, continuations, implicit return statements.

The common factor is tail-position analysis."""

from functools import partial

from ast import Lambda, FunctionDef, \
                arguments, arg, keyword, \
                List, Tuple, \
                Subscript, Index, \
                Call, Name, Starred, Num, \
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
                  has_tco, is_decorator, sort_lambda_decorators, \
                  suggest_decorator_index
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
def with_cc(tree, **kw):
    """[syntax] Only meaningful in a "with continuations" block."""
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

    # CPS conversion, essentially the call/cc. Corresponds to PG's "=bind".
    #
    # But we have a code walker, so we don't need to require the body to be
    # specified inside the body of the macro invocation like PG's solution does.
    # Instead, we capture as the continuation all remaining statements (i.e.
    # those that lexically appear after the ``with_cc[]``) in the current block.
    #
    # To keep things relatively straightforward, the ``with_cc[]`` construct
    # is only allowed to appear at the top level of:
    #
    #   - the ``with continuations:`` block itself
    #   - a ``def`` or ``async def``
    #
    # Nested closures are ok; here "top level" only refers to the currently
    # innermost ``def``.
    #
    # Syntax::
    #
    #   x = with_cc[func(...)]
    #   *xs = with_cc[func(...)]
    #   x0, ... = with_cc[func(...)]
    #   x0, ..., *xs = with_cc[func(...)]
    #   with_cc[func(...)]  # ignoring the return value of ``func`` is also ok
    #
    # On the LHS, the starred item, if it appears, must be last. This limitation
    # is due to how Python handles varargs.
    #
    # The function ``func`` called by a ``with_cc[func(...)]`` is the only place
    # where the ``cc`` argument is actually set. There it is the captured
    # continuation, represented as a function object.
    #
    # The ``with_cc[]`` construct essentially splits the function at its use site
    # into "before" and "after" parts, where the "after" part (the continuation)
    # can be run multiple times, by calling the continuation as a function.
    #
    # The return value of the continuation is whatever the original function
    # returns (for any ``return`` statement that appears lexically after the
    # ``with_cc[]``).
    #
    # Multiple ``with_cc[]`` invocations in the same function are allowed.
    # These essentially create nested closures.
    #
    # Note that when ``with_cc[]`` is used at the top level of the
    # ``with continuations:`` block, the return value of the continuation
    # is always ``None``, because the block itself returns nothing.
    #
    # For technical reasons, the ``return`` statement is not allowed at the
    # top level of the ``with continuations:`` block. (Because the continuation
    # is essentially a function, ``return`` would behave differently based on
    # whether it is placed lexically before or after a ``with_cc[]``, which is
    # needlessly complicated.)
    #
    # If you absolutely need to terminate the function surrounding the
    # ``with continuations:`` block from inside the block, use an exception
    # to escape; see ``call_ec``, ``setescape``, ``escape``.
    def iswithcc(tree):
        if type(tree) in (Assign, Expr):
            tree = tree.value
        if type(tree) is Subscript and type(tree.value) is Name \
           and tree.value.id == "with_cc":
            if type(tree.slice) is Index:
                return True
            assert False, "expected single expr, not slice in with_cc[...]"
        return False
    def split_at_withcc(body):
        if not body:
            return [], None, []
        before, rest = [], body
        while True:
            stmt, *rest = rest
            if iswithcc(stmt):
                return before, stmt, rest
            before.append(stmt)
            if not rest:
                return before, None, rest
    def analyze_withcc(stmt):
        starget = None  # "starget" = starred target, becomes the vararg for the cont
        def maybe_starred(expr):  # return expr.id or set starget
            nonlocal starget
            if type(expr) is Name:
                return [expr.id]
            elif type(expr) is Starred:
                if type(expr.value) is not Name:
                    assert False, "with_cc[] starred assignment target must be a bare name"
                starget = expr.value.id
                return []
            assert False, "all with_cc[] assignment targets must be bare names (last one may be starred)"
        # extract the assignment targets (args of the cont)
        if type(stmt) is Assign:
            if len(stmt.targets) != 1:
                assert False, "expected at most one '=' in a with_cc[] statement"
            target = stmt.targets[0]
            if type(target) in (Tuple, List):
                rest, last = target.elts[:-1], target.elts[-1]
                # TODO: limitation due to Python's vararg syntax - the "*args" must be after positional args.
                if any(type(x) is Starred for x in rest):
                    assert False, "in with_cc[], only the last assignment target may be starred"
                if not all(type(x) is Name for x in rest):
                    assert False, "all with_cc[] assignment targets must be bare names"
                targets = [x.id for x in rest] + maybe_starred(last)
            else:  # single target
                targets = maybe_starred(target)
        elif type(stmt) is Expr:  # no assignment targets, cont takes no args
            if type(stmt.value) is not Subscript:
                assert False, "expected a bare with_cc[] expr, got {}".format(stmt.value)
            targets = []
        else:
            assert False, "with_cc[]: expected an assignment or a bare expr, got {}".format(stmt)
        # extract the function call
        if type(stmt.value) is not Subscript:  # both Assign and Expr have a .value
            assert False, "expected either an assignment with a with_cc[] expr on RHS, or a bare with_cc[] expr, got {}".format(stmt.value)
        thecall = stmt.value.slice.value
        if type(thecall) is not Call:
            assert False, "the bracketed expression in with_cc[...] must be a function call"
        return targets, starget, thecall
    gen_sym = dyn.gen_sym
    def make_continuation(owner, withcc, contbody):
        targets, starget, thecall = analyze_withcc(withcc)

        # Set our captured continuation as the cc of func in with_cc[func(...)]
        basename = "{}_cont".format(owner.name) if owner else "cont"
        contname = gen_sym(basename)
        thecall.keywords = [keyword(arg="cc", value=q[name[contname]])] + thecall.keywords

        # Create the continuation function, set contbody as its body.
        #
        # Any return statements in the body have already been transformed,
        # because they appear literally in the code at the use site,
        # and our main processing logic runs the return statement transformer
        # before transforming with_cc[].
        FDef = type(owner) if owner else FunctionDef  # use same type (regular/async) as parent function
        funcdef = FDef(name=contname,
                       args=arguments(args=[arg(arg=x) for x in targets],
                                      kwonlyargs=[arg(arg="cc")],
                                      vararg=(arg(arg=starget) if starget else None),
                                      kwarg=None,
                                      defaults=[],
                                      kw_defaults=[None]),  # patched later by transform_def
                       body=contbody,
                       decorator_list=[],  # patched later by transform_def
                       returns=None)  # return annotation not used here

        # in the output stmts, define the continuation function...
        newstmts = [funcdef]
        if owner:  # ...and tail-call it (if currently inside a def)
            thecall.args = [thecall.func] + thecall.args
            thecall.func = hq[jump]
            newstmts.append(Return(value=q[ast_literal[thecall]]))
        else:  # ...and call it normally (if at the top level)
            newstmts.append(Expr(value=q[ast_literal[thecall]]))
        return newstmts
    @Walker  # find and transform with_cc[] statements inside function bodies
    def transform_withccs(tree, **kw):
        if type(tree) in (FunctionDef, AsyncFunctionDef):
            tree.body = transform_withcc(tree, tree.body)
        return tree
    def transform_withcc(owner, body):
        # owner: FunctionDef or AsyncFunctionDef node, or None (top level of block)
        # body: list of stmts
        # we need to consider only one withcc in the body, because each one
        # generates a new nested def for the walker to pick up.
        before, withcc, after = split_at_withcc(body)
        if withcc:
            body = before + make_continuation(owner, withcc, contbody=after)
        return body
    # TODO: improve error reporting for stray with_cc[] invocations
    @Walker
    def check_for_strays(tree, **kw):
        if iswithcc(tree):
            assert False, "with_cc[...] only allowed at the top level of a def or async def, or at the top level of the block; must appear as an expr or an assignment RHS"
        return tree

    # Disallow return at the top level of the block, because it would behave
    # differently depending on whether placed before or after the first with_cc[]
    # invocation. (Because with_cc[] internally creates a function and calls it.)
    for stmt in block_body:
        if type(stmt) is Return:
            assert False, "'return' not allowed at the top level of a 'with continuations' block"

    # transform "return" statements before with_cc[] invocations generate new ones.
    block_body = [_tco_transform_return.recurse(stmt, known_ecs=known_ecs,
                                                transform_retexpr=transform_retexpr)
                     for stmt in block_body]
    # transform with_cc[] invocations
    block_body = transform_withcc(owner=None, body=block_body)  # at top level
    block_body = [transform_withccs.recurse(stmt) for stmt in block_body]  # inside defs
    # Validate. Each with_cc[] reached by the transformer was in a syntactically correct
    # position and has now been eliminated. Any remaining ones indicate syntax errors.
    for stmt in block_body:
        check_for_strays.recurse(stmt)
    # set up the default continuation that just returns its args
    new_block_body = [Assign(targets=[q[name["cc"]]], value=hq[identity])]
    # transform all defs, including those added by with_cc[].
    for stmt in block_body:
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
        if not has_tco(tree):
            k = suggest_decorator_index("trampolined", tree.decorator_list)
            if k is not None:
                tree.decorator_list.insert(k, hq[trampolined])
            else:  # couldn't determine insert position; just plonk it at the start and hope for the best
                tree.decorator_list.insert(0, hq[trampolined])
    return tree

# Transform return statements and calls to escape continuations (ec).
# known_ecs: list of names (str) of known escape continuations.
# transform_retexpr: return-value expression transformer.
@Walker
def _tco_transform_return(tree, *, known_ecs, transform_retexpr, **kw):
    treeisec = isec(tree, known_ecs)
    if type(tree) is Return:
        non = q[None]
        non = copy_location(non, tree)
        value = tree.value or non  # return --> return None  (bare return has value=None in the AST)
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
