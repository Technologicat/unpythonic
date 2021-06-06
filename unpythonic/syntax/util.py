# -*- coding: utf-8 -*-
"""Utilities for working with syntax.

This module also contains the definitions for working with "decorated lambdas".
"""

__all__ = ["isec", "detect_callec",
           "detect_lambda",
           "is_decorator",
           "is_lambda_decorator", "is_decorated_lambda", "destructure_decorated_lambda",
           "has_tco", "has_curry", "has_deco",
           "sort_lambda_decorators", "suggest_decorator_index",
           "eliminate_ifones", "transform_statements",
           "UnpythonicASTMarker", "UnpythonicExpandedMacroMarker",
           "ExpandedContinuationsMarker", "ExpandedAutorefMarker"]

from functools import partial

from ast import Call, Lambda, FunctionDef, AsyncFunctionDef, If, stmt

from mcpyrate.core import add_postprocessor
from mcpyrate.markers import ASTMarker, delete_markers
from mcpyrate.quotes import is_captured_value
from mcpyrate.walkers import ASTTransformer, ASTVisitor

from .astcompat import getconstant
from .letdoutil import isdo, ExpandedDoView
from .nameutil import isx, getname

from ..regutil import all_decorators, tco_decorators, decorator_registry

def isec(tree, known_ecs):
    """Test whether tree is a call to a function known to be an escape continuation.

    known_ecs: list of ``str``, names of known escape continuations.

    **CAUTION**: Only bare-name references are supported.
    """
    return type(tree) is Call and getname(tree.func, accept_attr=False) in known_ecs

def detect_callec(tree):
    """Collect names of escape continuations from call_ec invocations in tree.

    Currently supported and unsupported cases::

        # use as decorator, supported
        @call_ec
        def result(ec):  # <-- we grab name "ec" from here
            ...

        # use directly on a literal lambda, supported
        result = call_ec(lambda ec: ...)  # <-- we grab name "ec" from here

        # use as a function, **NOT supported**
        def g(ec):           # <-- should grab from here
            ...
        ...
        result = call_ec(g)  # <-- but this is here; g could be in another module

    Additionally, the literal names `ec`, `brk`, `throw` are always interpreted
    as invoking an escape continuation (whether they actually do or not).
    So if you need the third pattern above, use **exactly** the name `ec`
    for the escape continuation parameter, and it will work.

    (The name `brk` covers the use of `unpythonic.fploop.breakably_looped`,
    and `throw` covers the use of `unpythonic.ec.throw`.)
    """
    fallbacks = ["ec", "brk", "throw"]
    iscallec = partial(isx, x="call_ec")
    def detect(tree):
        class Detector(ASTVisitor):
            def examine(self, tree):
                # TODO: add support for general use of call_ec as a function (difficult)
                if type(tree) in (FunctionDef, AsyncFunctionDef) and any(iscallec(deco) for deco in tree.decorator_list):
                    # TODO: Python 3.8+: handle the case where the ec is a positional-only arg?
                    fdef = tree
                    self.collect(fdef.args.args[0].arg)  # FunctionDef.arguments.(list of arg objects).arg
                elif is_decorated_lambda(tree, mode="any"):
                    # TODO: should we recurse selectively in this case?
                    decorator_list, thelambda = destructure_decorated_lambda(tree)
                    if any(iscallec(decocall.func) for decocall in decorator_list):
                        self.collect(thelambda.args.args[0].arg)  # we assume it's the first arg, as that's what call_ec expects.
                self.generic_visit(tree)
        d = Detector()
        d.visit(tree)
        return d.collected
    return fallbacks + detect(tree)

def detect_lambda(tree):
    """Find lambdas in tree. Helper for two-pass block macros.

    A two-pass block macro first performs some processing outside-in, then calls
    `expander.visit_recursively(tree)` to make any nested macro invocations expand,
    and then performs some processing inside-out.

    Run ``detect_lambda(tree)`` in the outside-in pass, before calling
    `expander.visit_recursively(tree)`, because nested macro invocations
    may generate more lambdas that your block macro is not interested in.

    The return value is a ``list``of ``id(lam)``, where ``lam`` is a Lambda node
    that appears in ``tree``. This list is suitable as ``userlambdas`` for the
    TCO macros.

    This ignores any "lambda e: ..." added by an already expanded ``do[]``,
    to allow other block macros to better work together with ``with multilambda``
    (which expands outside-in, to eliminate semantic surprises).
    """
    class LambdaDetector(ASTVisitor):
        def examine(self, tree):
            if isdo(tree, expanded=True):
                thebody = ExpandedDoView(tree).body
                for thelambda in thebody:  # lambda e: ...
                    self.visit(thelambda.body)
                return  # don't recurse generically, we already did it selectively
            if type(tree) is Lambda:
                self.collect(id(tree))
            self.generic_visit(tree)
    d = LambdaDetector()
    d.visit(tree)
    return d.collected

def is_decorator(tree, fname):
    """Test tree whether it is the decorator ``fname``.

    ``fname`` may be ``str`` or a predicate, see ``isx``.

    References of the forms ``f``, ``foo.f`` and ``q[h[f]]`` are supported.

     We detect:

        - ``Name``, ``Attribute``, a `mcpyrate.core.Done`, or a `mcpyrate`
          hygienic capture matching the given ``fname`` (non-parametric decorator), and

        - ``Call`` whose ``.func`` matches the above rule (parametric decorator).
    """
    return ((isx(tree, fname)) or
            (type(tree) is Call and isx(tree.func, fname)))

def is_lambda_decorator(tree, fname=None):
    """Test tree whether it decorates a lambda with ``fname``.

    A node is detected as a lambda decorator if it is a ``Call`` that supplies
    exactly one positional argument, and its ``.func`` is the decorator ``fname``
    (``is_decorator(tree.func, fname)`` returns ``True``).

    This function does not know or care whether a chain of ``Call`` nodes
    terminates in a ``Lambda`` node. See ``is_decorated_lambda``.

    ``fname`` is optional; if ``None``, do not check the name.

    Examples::

        trampolined(arg)                    # --> non-parametric decorator
        looped_over(range(10), acc=0)(arg)  # --> parametric decorator
    """
    return ((type(tree) is Call and len(tree.args) == 1) and
            (fname is None or is_decorator(tree.func, fname)))

def is_decorated_lambda(tree, mode):
    """Detect a tree of the form f(g(h(lambda ...: ...)))

    mode: str, "known" or "any":

        "known": match a chain containing known decorators only.
                 See ``unpythonic.regutil``.

        "any": match any chain of one-argument ``Call`` nodes terminating
               in a ``Lambda`` node.

    Note this works also for parametric decorators; for them, the ``func``
    of the ``Call`` is another ``Call`` (that specifies the parameters).
    """
    assert mode in ("known", "any")
    if mode == "known":
        detectors = [partial(is_lambda_decorator, fname=x) for x in all_decorators]
    else:  # mode == "any":
        detectors = [is_lambda_decorator]

    def detect(tree):
        if type(tree) is not Call:
            return False
        if not any(f(tree) for f in detectors):
            return False
        if type(tree.args[0]) is Lambda:
            return True
        return detect(tree.args[0])
    return detect(tree)

def destructure_decorated_lambda(tree):
    """Get the AST nodes for ([f, g, h], lambda) in f(g(h(lambda ...: ...)))

    Input must be a tree for which ``is_decorated_lambda`` returns ``True``.

    This returns **the original AST nodes**, to allow in-place transformations.
    """
    def get(tree, lst):
        if type(tree) is Call:
            # collect tree itself, not tree.func, because sort_lambda_decorators needs to reorder the funcs.
            return get(tree.args[0], lst + [tree])
        elif type(tree) is Lambda:
            return lst, tree
        raise SyntaxError("Expected a chain of Call nodes terminating in a Lambda node")  # pragma: no cover
    return get(tree, [])

def has_tco(tree, userlambdas=[]):
    """Return whether a FunctionDef or a decorated lambda has TCO applied.

    userlambdas: list of ``id(some_tree)``; when detecting a lambda,
    only consider it if its id matches one of those in the list.

    Return value is ``True`` or ``False`` (depending on test result) if the
    test was applicable, and ``None`` if it was not applicable (no match on tree).
    """
    return has_deco(tco_decorators, tree, userlambdas)

def has_curry(tree, userlambdas=[]):
    """Return whether a FunctionDef or a decorated lambda has curry applied.

    userlambdas: list of ``id(some_tree)``; when detecting a lambda,
    only consider it if its id matches one of those in the list.

    Return value is ``True`` or ``False`` (depending on test result) if the
    test was applicable, and ``None`` if it was not applicable (no match on tree).
    """
    return has_deco(["curry"], tree, userlambdas)

def has_deco(deconames, tree, userlambdas=[]):
    """Return whether a FunctionDef or a decorated lambda has any given deco applied.

    deconames: list of decorator names to test.

    userlambdas: list of ``id(some_tree)``; when detecting a lambda,
    only consider it if its id matches one of those in the list.

    Return value is ``True`` or ``False`` (depending on test result) if the
    test was applicable, and ``None`` if it was not applicable (no match on tree).
    """
    if type(tree) in (FunctionDef, AsyncFunctionDef):
        return any(is_decorator(x, fname) for fname in deconames for x in tree.decorator_list)
    elif is_decorated_lambda(tree, mode="any"):
        decorator_list, thelambda = destructure_decorated_lambda(tree)
        if (not userlambdas) or (id(thelambda) in userlambdas):
            return any(is_lambda_decorator(x, fname) for fname in deconames for x in decorator_list)
    return None  # not applicable

def sort_lambda_decorators(tree):
    """Fix ordering of known lambda decorators (recursively) in ``tree``.

    Strictly, lambdas have no decorator_list, but can be decorated by explicitly
    surrounding them with calls to decorator functions.

    Examples::
        call_ec(trampolined(lambda ...: ...))
            --> trampolined(call_ec(lambda ...: ...))

        call_ec(curry(trampolined(lambda ...: ...)))
            --> trampolined(call_ec(curry(lambda ...: ...)))
    """
    def prioritize(tree):  # sort key for Call nodes invoking known decorators
        for k, (pri, fname) in enumerate(decorator_registry):
            if is_lambda_decorator(tree, fname):
                return k
        # Only happens if called for a `tree` containing unknown (not registered) decorators.
        x = getname(tree.func) if type(tree) is Call else tree  # pragma: no cover
        raise SyntaxError(f"Only registered decorators can be auto-sorted, {repr(x)} is not; see unpythonic.regutil")  # pragma: no cover

    class FixIt(ASTTransformer):
        def transform(self, tree):
            if is_captured_value(tree):
                return tree  # don't recurse!
            # we can robustly sort only decorators for which we know the correct ordering.
            if is_decorated_lambda(tree, mode="known"):
                decorator_list, thelambda = destructure_decorated_lambda(tree)
                # We can just swap the func attributes of the nodes.
                ordered_decorator_list = sorted(decorator_list, key=prioritize)
                ordered_funcs = [x.func for x in ordered_decorator_list]
                for thecall, newfunc in zip(decorator_list, ordered_funcs):
                    thecall.func = newfunc
                # don't recurse on the tail of the "decorator list" (call chain),
                # but recurse into the lambda body.
                thelambda.body = self.visit(thelambda.body)
                return tree
            return self.generic_visit(tree)
    return FixIt().visit(tree)

# TODO: should we just sort the decorators here, like we do for lambdas?
# (The current solution is less magic, but also less uniform.)
def suggest_decorator_index(deco_name, decorator_list):
    """Suggest insertion index for decorator deco_name in given decorator_list.

    ``decorator_list`` is the eponymous attribute of a ``FunctionDef``
    or ``AsyncFunctionDef`` AST node.

    The return value ``k`` is intended to be used like this::

        if k is not None:
            decorator_list.insert(k, mydeco)
        else:
            decorator_list.append(mydeco)  # or do something else

    If ``deco_name`` is not in the registry (see ``unpythonic.regutil``),
    or if an approprite index could not be determined, the return value
    is ``None``.
    """
    if deco_name not in all_decorators:
        return None  # unknown decorator, don't know where it should go  # pragma: no cover
    names = [getname(tree) for tree in decorator_list]
    pri_by_name = {dname: pri for pri, dname in decorator_registry}

    # sanity check that existing known decorators are ordered correctly
    # (otherwise there is no unique insert position)
    knownnames = [x for x in names if x in pri_by_name]
    knownpris = [pri_by_name[x] for x in knownnames]
    def isascending(lst):
        maxes = cummax(lst)
        return all(b >= a for a, b in zip(maxes, maxes[1:]))
    def cummax(lst):
        m = float("-inf")
        out = []
        for x in lst:
            m = max(x, m)
            out.append(m)
        return out
    if not (knownpris and isascending(knownpris)):
        return None

    # when deciding the index, only care about known decorators (hence "suggest")
    targetpri = pri_by_name[deco_name]
    if targetpri < knownpris[0]:
        return 0
    if targetpri > knownpris[-1]:
        return len(decorator_list)
    assert knownpris[0] <= targetpri <= knownpris[-1]
    for pri, dname in zip(knownpris, knownnames):
        if pri >= targetpri:
            break
    else:
        assert False  # pragma: no cover
    return names.index(dname)

def eliminate_ifones(body):
    """Eliminate ``if 1`` by splicing the contents into the surrounding body.

    We also support "if True", "if 0", "if False" and "if None". The *then* or
    *else* branch is spliced accordingly.

    Here ``body`` is a ``list`` of statements.

    **NOTE**: The Python compiler already performs this optimization, but the
    ``call_cc`` macro must be placed at the top level of a function body, and
    ``let_syntax`` (and its cousin ``abbrev``) generates these ``if 1`` blocks.
    So to be able to use ``let_syntax`` in block mode, when the RHS happens to
    include a ``call_cc`` (see the example in test_conts_gen.py)...
    """
    def isifone(tree):
        if type(tree) is If:
            try:
                value = getconstant(tree.test)
            except TypeError:
                pass
            else:
                if value in (1, True):
                    return "then"
                elif value in (0, False, None):
                    return "else"
        return False

    def optimize(tree):  # stmt -> list of stmts
        t = isifone(tree)
        if t:
            branch = tree.body if t == "then" else tree.orelse
            return branch
        return tree

    return transform_statements(optimize, body)

def transform_statements(f, body):
    """Recurse over statement positions and apply the syntax transformer ``f``.

    This function understands statements such as ``def``, ``with``, ``if`` and
    ``for``, and calls ``f`` for each statement in their bodies, recursively.
    For example, for an ``if``, statements in all branches are processed through
    the transformation ``f``.

    ``f`` is a one-argument function that takes an AST representing a single
    statement, and that **must** return a ``list`` of ASTs representing statements.

    The output ``list`` will be spliced to replace the input statement. This
    allows ``f`` to drop a statement (1->0) or to replace one statement with
    several (1->n), beside making one-to-one (1->1) transformations.

    (Transformations requiring n input statements are currently not supported.)

    ``body`` may be an AST representing a single statement, or a ``list`` of
    such ASTs (e.g. the ``body`` of an ``ast.With``).

    The input is modified in-place, provided ``f`` does so. In any case, the
    original lists inside the ASTs containing the statements are in-place
    replaced with the transformed ones.

    The return value is the transformed ``body``.
    """
    class StatementTransformer(ASTTransformer):
        def transform(self, tree):
            tree = self.generic_visit(tree)
            if isinstance(tree, stmt):
                return f(tree)
            return tree
    return StatementTransformer().visit(body)

# --------------------------------------------------------------------------------
# AST markers.

class UnpythonicASTMarker(ASTMarker):
    """Base class for all AST markers used by `unpythonic`."""
class UnpythonicExpandedMacroMarker(UnpythonicASTMarker):
    """AST marker base class for expanded `unpythonic.syntax` macros."""

class ExpandedContinuationsMarker(UnpythonicExpandedMacroMarker):
    """AST marker for an expanded "with continuations" block."""

class ExpandedAutorefMarker(UnpythonicExpandedMacroMarker):
    """AST marker for an expanded "with autoref[o]" block."""
    def __init__(self, body, varname):
        super().__init__(body)
        self.varname = varname
        self._fields += ["varname"]

# The point of having these two functions is:
#   - `__init__` must explicitly enable the hook, thus making its existence
#     obvious, since the entry-point source file for the macro layer has an
#     obvious function call, instead of having the hook secretly registered
#     by an innocuous-looking utility module.
#
#   - We could register `partial(delete_markers, cls=UnpythonicASTMarker)`,
#     but then we would be unable to `remove_postprocessor` it later, because
#     the function object itself is the key used for unregistering. Currently
#     we don't need to do that, but it's nice to have the possibility.
def register_postprocessor_hook():
    """Set up global postprocessor hook for `mcpyrate` to nuke `unpythonic`'s AST markers from the final tree."""
    add_postprocessor(_delete_unpythonic_ast_markers)
def _delete_unpythonic_ast_markers(tree):
    return delete_markers(tree, cls=UnpythonicASTMarker)
