# -*- coding: utf-8 -*-
"""Automatic TCO, continuations, implicit return statements.

The common factor is tail-position analysis."""

from functools import partial

from ast import (Lambda, FunctionDef,
                 arguments, arg, keyword,
                 List, Tuple,
                 Subscript, Index,
                 Call, Name, Starred, NameConstant,
                 BoolOp, And, Or,
                 With, If, IfExp, Try, Assign, Return, Expr,
                 copy_location)
from .astcompat import AsyncFunctionDef, AsyncWith

from macropy.core.macros import macro_stub
from macropy.core.quotes import macros, q, u, ast_literal, name
from macropy.core.hquotes import macros, hq  # noqa: F811, F401
from macropy.core.walkers import Walker

from .util import (isx, make_isxpred, isec,
                   detect_callec, detect_lambda,
                   has_tco, sort_lambda_decorators,
                   suggest_decorator_index, ContinuationsMarker, wrapwith, ismarker)
from .letdoutil import isdo, islet, ExpandedLetView, ExpandedDoView
from .ifexprs import aif

from ..dynassign import dyn
from ..it import uniqify
from ..fun import identity, orf
from ..tco import trampolined, jump
from ..lazyutil import passthrough_lazy_args

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
    known_ecs = list(uniqify(detect_callec(block_body)))
    block_body = yield block_body

    # second pass, inside-out
    transform_retexpr = partial(_transform_retexpr)
    new_block_body = []
    for stmt in block_body:
        # skip nested, already expanded "with continuations" blocks
        # (needed to support continuations in the Lispython dialect, which applies tco globally)
        if ismarker("ContinuationsMarker", stmt):
            new_block_body.append(stmt)
            continue

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
    pass  # pragma: no cover

# _pcc/cc chaining handler, to be exported to client code via hq[].
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

def continuations(block_body):
    # This is a very loose pythonification of Paul Graham's continuation-passing
    # macros in On Lisp, chapter 20.
    #
    # We don't have an analog of PG's "=apply", since Python doesn't need "apply"
    # to pass in varargs.

    # first pass, outside-in
    userlambdas = detect_lambda.collect(block_body)
    known_ecs = list(uniqify(detect_callec(block_body)))
    block_body = yield block_body

    # second pass, inside-out

    # _tco_transform_def and _tco_transform_lambda correspond to PG's
    # "=defun" and "=lambda", but we don't need to generate a macro.
    #
    # Here we define only the callback to perform the additional transformations
    # we need for the continuation machinery.
    def transform_args(tree):
        assert type(tree) in (FunctionDef, AsyncFunctionDef, Lambda)
        # Add a cc kwarg if the function has no cc arg.
        posnames = [a.arg for a in tree.args.args]  # positional-or-keyword
        kwonlynames = [a.arg for a in tree.args.kwonlyargs]
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
                tree.args.defaults.insert(0, hq[identity])
        else:  # "cc" in kwonlynames:
            j = kwonlynames.index("cc")
            if tree.args.kw_defaults[j] is None:  # not already set
                tree.args.kw_defaults[j] = hq[identity]
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
            thekw.value = hq[chain_conts(name["_pcc"], ast_literal[usercc], with_star=True)]
        else:
            # chain our _pcc and the current value of cc
            tree.keywords = [keyword(arg="cc", value=hq[chain_conts(name["_pcc"], name["cc"], with_star=True)])] + tree.keywords
        return tree
    def data_cb(tree):  # transform an inert-data return value into a tail-call to cc.
        tree = hq[chain_conts(name["_pcc"], name["cc"])(ast_literal[tree])]
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
        tree = tree.value
        if type(tree) is Subscript and type(tree.value) is Name and tree.value.id == "call_cc":
            if type(tree.slice) is Index:
                return True
            assert False, "expected single expr, not slice in call_cc[...]"  # pragma: no cover
        return False
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
                    assert False, "call_cc[] cannot appear as the last statement of a 'with continuations' block (no continuation to capture)"  # pragma: no cover
                # TODO: To support Python's scoping properly in assignments after the `call_cc`,
                # TODO: we have to scan `before` for assignments to local variables (stopping at
                # TODO: scope boundaries; use `get_names_in_store_context` from our `scoping` module),
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
                    assert False, "call_cc[] starred assignment target must be a bare name"  # pragma: no cover
                starget = expr.value.id
                return []
            assert False, "all call_cc[] assignment targets must be bare names (last one may be starred)"  # pragma: no cover
        # extract the assignment targets (args of the cont)
        if type(stmt) is Assign:
            if len(stmt.targets) != 1:
                assert False, "expected at most one '=' in a call_cc[] statement"  # pragma: no cover
            target = stmt.targets[0]
            if type(target) in (Tuple, List):
                rest, last = target.elts[:-1], target.elts[-1]
                # TODO: limitation due to Python's vararg syntax - the "*args" must be after positional args.
                if any(type(x) is Starred for x in rest):
                    assert False, "in call_cc[], only the last assignment target may be starred"  # pragma: no cover
                if not all(type(x) is Name for x in rest):
                    assert False, "all call_cc[] assignment targets must be bare names"  # pragma: no cover
                targets = [x.id for x in rest] + maybe_starred(last)
            else:  # single target
                targets = maybe_starred(target)
        elif type(stmt) is Expr:  # no assignment targets, cont takes no args
            targets = []
        else:
            assert False, "call_cc[]: expected an assignment or a bare expr, got {}".format(stmt)  # pragma: no cover
        # extract the function call(s)
        if type(stmt.value) is not Subscript:  # both Assign and Expr have a .value
            assert False, "expected either an assignment with a call_cc[] expr on RHS, or a bare call_cc[] expr, got {}".format(stmt.value)  # pragma: no cover
        theexpr = stmt.value.slice.value
        if not (type(theexpr) in (Call, IfExp) or (type(theexpr) is NameConstant and theexpr.value is None)):
            assert False, "the bracketed expression in call_cc[...] must be a function call, an if-expression, or None"  # pragma: no cover
        def extract_call(tree):
            if type(tree) is Call:
                return tree
            elif type(tree) is NameConstant and tree.value is None:
                return None
            else:
                assert False, "call_cc[...]: expected a function call or None"  # pragma: no cover
        if type(theexpr) is IfExp:
            condition = theexpr.test
            thecall = extract_call(theexpr.body)
            altcall = extract_call(theexpr.orelse)
        else:
            condition = altcall = None
            thecall = extract_call(theexpr)
        return targets, starget, condition, thecall, altcall
    gen_sym = dyn.gen_sym
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
            basename = "{}_cont".format(strip_suffix(owner.name, "_cont"))
        else:
            basename = "cont"
        contname = gen_sym(basename)

        # Set our captured continuation as the cc of f and g in
        #   call_cc[f(...)]
        #   call_cc[f(...) if p else g(...)]
        def prepare_call(tree):
            if tree:
                tree.keywords = [keyword(arg="cc", value=q[name[contname]])] + tree.keywords
            else:  # no call means proceed to cont directly, with args set to None
                tree = q[name[contname](*([None] * u[len(targets)]), cc=name["cc"])]
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
        FDef = type(owner) if owner else FunctionDef  # use same type (regular/async) as parent function
        locref = callcc  # bad but no better source location reference node available
        non = q[None]
        non = copy_location(non, locref)
        maybe_capture = IfExp(test=hq[name["cc"] is not identity],
                              body=q[name["cc"]],
                              orelse=non,
                              lineno=locref.lineno, col_offset=locref.col_offset)
        funcdef = FDef(name=contname,
                       args=arguments(args=[arg(arg=x) for x in targets],
                                      kwonlyargs=[arg(arg="cc"), arg(arg="_pcc")],
                                      vararg=(arg(arg=starget) if starget else None),
                                      kwarg=None,
                                      defaults=posargdefaults,
                                      kw_defaults=[hq[identity], maybe_capture]),
                       body=contbody,
                       decorator_list=[],  # patched later by transform_def
                       returns=None,  # return annotation not used here
                       lineno=locref.lineno, col_offset=locref.col_offset)

        # in the output stmts, define the continuation function...
        newstmts = [funcdef]
        if owner:  # ...and tail-call it (if currently inside a def)
            def jumpify(tree):
                tree.args = [tree.func] + tree.args
                tree.func = hq[jump]
            jumpify(thecall)
            if condition:
                jumpify(altcall)
                newstmts.append(If(test=condition,
                                   body=[Return(value=q[ast_literal[thecall]])],
                                   orelse=[Return(value=q[ast_literal[altcall]])]))
            else:
                newstmts.append(Return(value=q[ast_literal[thecall]]))
        else:  # ...and call it normally (if at the top level)
            if condition:
                newstmts.append(If(test=condition,
                                   body=[Expr(value=q[ast_literal[thecall]])],
                                   orelse=[Expr(value=q[ast_literal[altcall]])]))
            else:
                newstmts.append(Expr(value=q[ast_literal[thecall]]))
        return newstmts
    @Walker  # find and transform call_cc[] statements inside function bodies
    def transform_callccs(tree, **kw):
        if type(tree) in (FunctionDef, AsyncFunctionDef):
            tree.body = transform_callcc(tree, tree.body)
        return tree
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
    @Walker
    def check_for_strays(tree, **kw):
        if iscallcc(tree):
            assert False, "call_cc[...] only allowed at the top level of a def or async def, or at the top level of the block; must appear as an expr or an assignment RHS"  # pragma: no cover
        if type(tree) in (Assign, Expr):
            v = tree.value
            if type(v) is Call and type(v.func) is Name and v.func.id == "call_cc":
                assert False, "call_cc(...) should be call_cc[...] (note brackets; it's a macro)"  # pragma: no cover
        return tree

    # -------------------------------------------------------------------------
    # Main processing logic begins here
    # -------------------------------------------------------------------------

    # Disallow return at the top level of the block, because it would behave
    # differently depending on whether placed before or after the first call_cc[]
    # invocation. (Because call_cc[] internally creates a function and calls it.)
    for stmt in block_body:
        if type(stmt) is Return:
            assert False, "'return' not allowed at the top level of a 'with continuations' block"  # pragma: no cover

    # Since we transform **all** returns (even those with an inert data value)
    # into tail calls (to cc), we must insert any missing implicit "return"
    # statements so that _tco_transform_return() sees them.
    @Walker
    def add_implicit_bare_return(tree, **kw):
        if type(tree) in (FunctionDef, AsyncFunctionDef):
            if type(tree.body[-1]) is not Return:
                tree.body.append(Return(value=None,  # bare "return"
                                        lineno=tree.lineno, col_offset=tree.col_offset))
        return tree
    block_body = [add_implicit_bare_return.recurse(stmt) for stmt in block_body]

    # transform "return" statements before call_cc[] invocations generate new ones.
    block_body = [_tco_transform_return.recurse(stmt, known_ecs=known_ecs,
                                                transform_retexpr=transform_retexpr)
                     for stmt in block_body]

    # transform call_cc[] invocations
    block_body = transform_callcc(owner=None, body=block_body)  # at top level
    block_body = [transform_callccs.recurse(stmt) for stmt in block_body]  # inside defs
    # Validate. Each call_cc[] reached by the transformer was in a syntactically correct
    # position and has now been eliminated. Any remaining ones indicate syntax errors.
    for stmt in block_body:
        check_for_strays.recurse(stmt)

    # set up the default continuation that just returns its args
    # (the top-level "cc" is only used for continuations created by call_cc[] at the top level of the block)
    new_block_body = [Assign(targets=[q[name["cc"]]], value=hq[identity])]

    # transform all defs (except the chaining handler), including those added by call_cc[].
    for stmt in block_body:
        stmt = _tco_transform_def.recurse(stmt, preproc_cb=transform_args)
        stmt = _tco_transform_lambda.recurse(stmt, preproc_cb=transform_args,
                                             userlambdas=userlambdas,
                                             known_ecs=known_ecs,
                                             transform_retexpr=transform_retexpr)
        stmt = sort_lambda_decorators(stmt)
        new_block_body.append(stmt)

    # Leave a marker so "with tco", if applied, can ignore the expanded "with continuations" block
    # (needed to support continuations in the Lispython dialect, since it applies tco globally.)
    return wrapwith(item=hq[ContinuationsMarker],
                    body=new_block_body,
                    locref=block_body[0])

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
# transform_retexpr: return-value expression transformer (for TCO and stuff).
@Walker
def _tco_transform_return(tree, *, known_ecs, transform_retexpr, **kw):
    if type(tree) is Return:
        non = q[None]
        non = copy_location(non, tree)
        value = tree.value or non  # return --> return None  (bare return has value=None in the AST)
        if not isec(value, known_ecs):
            return Return(value=transform_retexpr(value, known_ecs))
        else:
            # An ec call already escapes, so the return is redundant.
            #
            # If someone writes "return ec(...)" in a "with continuations" block,
            # this cleans up the code, since eliminating the "return" allows us
            # to omit a redundant "let".
            return Expr(value=value)  # return ec(...) --> ec(...)
    elif isec(tree, known_ecs):  # TCO the arg of an ec(...) call
        if len(tree.args) > 1:
            assert False, "expected exactly one argument for escape continuation"  # pragma: no cover
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
_isjump = orf(make_isxpred("jump"), make_isxpred("loop"))
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
                                     lineno=tree.lineno, col_offset=tree.col_offset))  # tail-call item
                elif type(tree.op) is And:
                    # and(data1, ..., datan, tail) --> tail if all(others) else False
                    fal = q[False]
                    fal = copy_location(fal, tree)
                    tree = IfExp(test=op_of_others,
                                 body=transform(tree.values[-1]),
                                 orelse=transform_data(fal))
                else:  # cannot happen
                    assert False, "unknown BoolOp type {}".format(tree.op)  # pragma: no cover
            else:  # optimization: BoolOp, no call or compound in tail position --> treat as single data item
                tree = transform_data(tree)
        else:
            tree = transform_data(tree)
        return tree
    return transform(tree)
