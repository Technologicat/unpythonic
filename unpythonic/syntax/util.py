# -*- coding: utf-8 -*-
"""Utilities for working with syntax."""

from functools import partial
import re

from ast import Call, Name, Attribute, Lambda, FunctionDef, \
                If, Num, NameConstant, For, While, With, Try, ClassDef, \
                withitem
from .astcompat import AsyncFunctionDef, AsyncFor, AsyncWith

from macropy.core import Captured
from macropy.core.walkers import Walker

from .letdoutil import isdo, ExpandedDoView

from ..regutil import all_decorators, tco_decorators, decorator_registry

def isx(tree, x, accept_attr=True):
    """Test whether tree is a reference to the name ``x`` (str).

    Alternatively, ``x`` may be a predicate that accepts a ``str``
    and returns whether it matches, to support more complex matching
    (e.g. ``lambda s: s.startswith("foo")``).

    Both bare names and attributes can be recognized, to support
    both from-imports and regular imports of ``somemodule.x``.

    We support:

        - bare name ``x``

        - ``x`` inside a ``macropy.core.Captured`` node, which may be inserted
          during macro expansion

        - ``x`` as an attribute (if ``accept_attr=True``)
    """
    # WTF, so sometimes there **is** a Captured node, while sometimes there isn't (letdoutil.islet)? At which point are these removed?
    # Captured nodes only come from unpythonic.syntax, and we use from-imports
    # and bare names for anything hq[]'d; but any references that appear
    # explicitly in the user code may use either bare names or somemodule.f.
    ismatch = x if callable(x) else lambda s: s == x
    return (type(tree) is Name and ismatch(tree.id)) or \
           (type(tree) is Captured and ismatch(tree.name)) or \
           (accept_attr and type(tree) is Attribute and ismatch(tree.attr))

def make_isxpred(x):
    """Make a predicate for isx.

    Here ``x`` is an ``str``; the resulting function will match the names
    x, x1, x2, ..., so that it works also with captured identifiers renamed
    by MacroPy's ``hq[]``.
    """
    rematch = re.match
    pat = re.compile(r"^{}\d*$".format(x))
    return lambda s: rematch(pat, s)

def getname(tree, accept_attr=True):
    """The cousin of ``isx``.

    From the same types of trees, extract the name as str.

    If no match on ``tree``, return ``None``.
    """
    if type(tree) is Name:
        return tree.id
    if type(tree) is Captured:
        return tree.name
    if accept_attr and type(tree) is Attribute:
        return tree.attr
    return None

def isec(tree, known_ecs):
    """Test whether tree is a call to a function known to be an escape continuation.

    known_ecs: list of ``str``, names of known escape continuations.

    **CAUTION**: Only bare-name references are supported.
    """
    return type(tree) is Call and type(tree.func) is Name and tree.func.id in known_ecs

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
    """
    # literal function names that are always interpreted as an ec.
    # "brk" is needed to combo with unpythonic.fploop.breakably_looped.
    fallbacks = ["ec", "brk"]
    iscallec = partial(isx, make_isxpred("call_ec"))
    @Walker
    def detect(tree, *, collect, **kw):
        # TODO: add support for general use of call_ec as a function (difficult)
        if type(tree) in (FunctionDef, AsyncFunctionDef) and any(iscallec(deco) for deco in tree.decorator_list):
            fdef = tree
            collect(fdef.args.args[0].arg)  # FunctionDef.arguments.(list of arg objects).arg
        elif is_decorated_lambda(tree, mode="any"):
            decorator_list, thelambda = destructure_decorated_lambda(tree)
            if any(iscallec(decocall.func) for decocall in decorator_list):
                collect(thelambda.args.args[0].arg)  # we assume it's the first arg, as that's what call_ec expects.
        return tree
    return fallbacks + detect.collect(tree)

@Walker
def detect_lambda(tree, *, collect, stop, **kw):
    """Find lambdas in tree. Helper for block macros.

    Run ``detect_lambda.collect(tree)`` in the first pass, before allowing any
    nested macros to expand. (Those may generate more lambdas that your block
    macro is not interested in).

    The return value from ``.collect`` is a ``list``of ``id(lam)``, where ``lam``
    is a Lambda node that appears in ``tree``. This list is suitable as
    ``userlambdas`` for the TCO macros.

    This ignores any "lambda e: ..." added by an already expanded ``do[]``,
    to allow other block macros to better work together with ``with multilambda``
    (which expands in the first pass, to eliminate semantic surprises).
    """
    if isdo(tree):
        stop()
        thebody = ExpandedDoView(tree).body
        for thelambda in thebody:  # lambda e: ...
            detect_lambda.collect(thelambda.body)
    if type(tree) is Lambda:
        collect(id(tree))
    return tree

def is_decorator(tree, fname):
    """Test tree whether it is the decorator ``fname``.

    ``fname`` may be ``str`` or a predicate, see ``isx``.

    References of the forms ``f``, ``foo.f`` and ``hq[f]`` are supported.

     We detect:

        - ``Name``, ``Attribute`` or ``Captured`` matching the given ``fname``
          (non-parametric decorator), and

        - ``Call`` whose ``.func`` matches the above rule (parametric decorator).
    """
    return isx(tree, fname) or \
           (type(tree) is Call and isx(tree.func, fname))

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
    return (type(tree) is Call and len(tree.args) == 1) and \
           (fname is None or is_decorator(tree.func, fname))

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
    else: # mode == "any":
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
        assert False, "Expected a chain of Call nodes terminating in a Lambda node"
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
        x = getname(tree.func) if type(tree) is Call else "<unknown>"
        assert False, "Only registered decorators can be auto-sorted, '{:s}' is not; see unpythonic.regutil".format(x)

    @Walker
    def fixit(tree, *, stop, **kw):
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
            stop()
            fixit.recurse(thelambda.body)
        return tree
    return fixit.recurse(tree)

# TODO: should we just sort the decorators here, like we do for lambdas?
# (The current solution is less magic, but less uniform.)
def suggest_decorator_index(deco_name, decorator_list):
    """Suggest insertion index for decorator deco_name in given decorator_list.

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
        return None  # unknown decorator, don't know where it should go
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
    for pri, dname in zip(knownpris, knownnames):
        if targetpri >= pri:
            break
    else:
        return None
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
            if type(tree.test) is Num:
                if tree.test.n == 1:
                    return "then"
                elif tree.test.n == 0:
                    return "else"
            elif type(tree.test) is NameConstant:
                if tree.test.value is True:
                    return "then"
                elif tree.test.value in (False, None):
                    return "else"
        return False

    def optimize(tree):  # stmt -> list of stmts
        t = isifone(tree)
        if t:
            branch = tree.body if t == "then" else tree.orelse
            return branch
        return [tree]

    return transform_statements(optimize, body)

def transform_statements(f, body):
    """Recurse over statement positions and apply the syntax transformer ``f``.

    This function understands statements such as ``def``, ``with``, ``if`` and
    ``for``, and calls ``f`` for each statement in their bodies, recursively.
    For example, for an ``if``, statements in all branches are processed through
    the transformation ``f``.

    ``f`` is a one-argument function that takes an AST representing a single
    statement, and returns a ``list`` of ASTs representing statements.
    If the output is such a ``list``, it will be spliced to replace the
    input statement. This allows ``f`` to drop a statement (1->0) or to
    replace one statement with several (1->n), beside making one-to-one (1->1)
    transformations.

    (Transformations requiring n input statements are currently not supported.)

    ``body`` may be an AST representing a single statement, or a ``list`` of
    such ASTs (e.g. the ``body`` of an ``ast.With``).

    The input is modified in-place, provided ``f`` does so. In any case, the
    original lists inside the ASTs containing the statements are in-place
    replaced with the transformed ones.

    The return value is the transformed ``body``. It is always a ``list`` of ASTs.
    """
    def rec(tree):
        # TODO: brittle, may need changes as the Python AST evolves. Better ways to do this?
        if type(tree) in (FunctionDef, AsyncFunctionDef, ClassDef, With, AsyncWith):
            tree.body = rec(tree.body)
        elif type(tree) in (If, For, While, AsyncFor):
            tree.body = rec(tree.body)
            tree.orelse = rec(tree.orelse)
        elif type(tree) is Try:
            tree.body = rec(tree.body)
            tree.orelse = rec(tree.orelse)
            tree.finalbody = rec(tree.finalbody)
            for handler in tree.handlers:
                handler.body = rec(handler.body)
        elif type(tree) is list:  # multiple-statement body in AST
            return [output_stmt for input_stmt in tree for output_stmt in rec(input_stmt)]
        return f(tree)  # a single statement
    return rec(body)

def splice(tree, rep, tag):
    """Splice in a tree into another tree.

    Walk ``tree``, replacing the first occurrence of a ``Name(id=tag)`` with
    the tree ``rep``.

    This is convenient for first building a skeleton with a marker such as
    ``q[name["_here_"]]``, and then splicing in ``rep`` later. See ``forall``
    and ``envify`` for usage examples.
    """
    @Walker
    def doit(tree, *, stop, **kw):
        if type(tree) is Name and tree.id == tag:
            stop()
            return rep
        return tree
    return doit.recurse(tree)

def wrapwith(item, body, locref=None):
    """Wrap ``body`` with a single-item ``with`` block, using ``item``.

    ``item`` must be an ``ast.withitem``.

    ``locref`` is an optional AST node to copy source location info from.
    If not supplied, ``body[0]`` is used.

    Syntax transformer. Returns the wrapped body.
    """
    locref = locref or body[0]
    wrapped = With(items=[withitem(context_expr=item, optional_vars=None)],
                   body=body,
                   lineno=locref.lineno, col_offset=locref.col_offset)
    return [wrapped]

def ismarker(typename, tree):
    """Return whether tree is a specific AST marker. Used by block macros.

    That is, whether ``tree`` is a ``with`` block with a single context manager,
    which is represented by a ``Name`` whose ``id`` matches the given ``typename``.

    Example. If ``tree`` is the AST for the following code::

        with ContinuationsMarker:
            ...

    then ``ismarker("ContinuationsMarker", tree)`` returns ``True``.
    """
    if type(tree) is not With or len(tree.items) != 1:
        return False
    ctxmanager = tree.items[0].context_expr
    return type(ctxmanager) is Name and ctxmanager.id == typename

# We use a custom metaclass to make __enter__ and __exit__ callable on the class
# instead of requiring an instance.
#
# Note ``thing.dostuff(...)`` means ``Thing.dostuff(thing, ...)``; the method
# is looked up *on the class* of the instance ``thing``, not on the instance
# itself. Hence, to make method lookup succeed when we have no instance, the
# method should be defined on the class of the class, i.e. *on the metaclass*.
# https://stackoverflow.com/questions/20247841/using-delitem-with-a-class-object-rather-than-an-instance-in-python
class ASTMarker(type):
    """Metaclass for AST markers used by block macros.

    This can be used by block macros to tell other block macros that a section
    of the AST is an already-expanded block of a given kind (so that others can
    tune their processing or skip it, as appropriate). At run time a marker
    does nothing.

    Usage::

        with SomeMarker:
            ... # expanded code goes here

    We provide a custom metaclass so that there is no need to instantiate
    ``SomeMarker``; suitable no-op ``__enter__`` and ``__exit__`` methods
    are defined on the metaclass, so e.g. ``SomeMarker.__enter__`` is valid.
    """
    def __enter__(cls):
        pass
    def __exit__(cls, exctype, excvalue, traceback):
        pass

class ContinuationsMarker(metaclass=ASTMarker):
    """AST marker for an expanded "with continuations" block."""
    pass
