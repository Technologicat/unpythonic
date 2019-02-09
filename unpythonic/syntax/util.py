# -*- coding: utf-8 -*-
"""Utilities for working with syntax."""

from functools import partial
import re

from ast import Call, Name, Attribute, Lambda, FunctionDef
from .astcompat import AsyncFunctionDef

from macropy.core import Captured
from macropy.core.walkers import Walker

from .letdoutil import isdo, ExpandedDoView

from ..regutil import all_decorators, tco_decorators, decorator_registry

def isx(tree, x, accept_attr=True):
    """Test whether tree is a reference to the name ``x`` (str).

    Alternatively, ``x`` may be a predicate that accepts a ``str``
    and returns whether it matches, to support more complex matching
    (e.g. ``lambda s: s.beginswith("foo")``).

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

@Walker
def detect_callec(tree, *, collect, **kw):
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
    for x in fallbacks:
        collect(x)
    iscallec = partial(isx, x="call_ec")
    # TODO: add support for general use of call_ec as a function (difficult)
    if type(tree) in (FunctionDef, AsyncFunctionDef) and any(iscallec(deco) for deco in tree.decorator_list):
        fdef = tree
        collect(fdef.args.args[0].arg)  # FunctionDef.arguments.(list of arg objects).arg
    elif is_decorated_lambda(tree, mode="any"):
        decorator_list, thelambda = destructure_decorated_lambda(tree)
        if any(iscallec(decocall.func) for decocall in decorator_list):
            collect(thelambda.args.args[0].arg)  # we assume it's the first arg, as that's what call_ec expects.
    return tree

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
        for item in thebody:  # namelambda("do_lineXXX")(lambda e: ...)
            thelambda = item.args[0]
            detect_lambda.collect(thelambda.body)
    if type(tree) is Lambda:
        collect(id(tree))
    return tree

def is_decorator(tree, fname):
    """Test tree whether it is the decorator ``fname``.

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
    if type(tree) in (FunctionDef, AsyncFunctionDef):
        return any(is_decorator(x, fname) for fname in tco_decorators for x in tree.decorator_list)
    elif is_decorated_lambda(tree, mode="any"):
        decorator_list, thelambda = destructure_decorated_lambda(tree)
        if (not userlambdas) or (id(thelambda) in userlambdas):
            return any(is_lambda_decorator(x, fname) for fname in tco_decorators for x in decorator_list)
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
