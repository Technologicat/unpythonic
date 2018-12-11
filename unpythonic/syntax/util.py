# -*- coding: utf-8 -*-
"""Utilities for working with syntax."""

from functools import partial

from ast import Call, Name, Attribute, Lambda, FunctionDef, \
                Subscript, Index, Tuple, List, Compare, In
from .astcompat import AsyncFunctionDef

from macropy.core import Captured
from macropy.core.walkers import Walker

from ..regutil import all_decorators, tco_decorators, decorator_registry

def isx(tree, x, accept_attr=True):
    """Test whether tree is a reference to the name ``x`` (str).

    Both bare names and attributes can be recognized, to support
    both from-imports and regular imports of ``somemodule.x``.

    We support:

        - bare name ``x``

        - ``x`` inside a ``macropy.core.Captured`` node, which may be inserted
          during macro expansion

        - ``x`` as an attribute (if ``accept_attr=True``)
    """
    # WTF, so sometimes there **is** a Captured node, while sometimes there isn't (_islet)? At which point are these removed?
    # Captured nodes only come from unpythonic.syntax, and we use from-imports
    # and bare names for anything hq[]'d; but explicit references may use either
    # bare names or somemodule.f.
    return (type(tree) is Name and tree.id == x) or \
           (type(tree) is Captured and tree.name == x) or \
           (accept_attr and type(tree) is Attribute and tree.attr == x)

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

def islet(tree, expanded=True):
    """Test whether tree is a ``let[]``, ``letseq[]``, ``letrec[]``,
    ``let_syntax[]``, or ``abbrev[]``.

    Return a truthy value if it is, ``False`` if not.

    expanded: if ``True``, test for the already expanded form.
    If ``False``, test for the form that exists prior to macro expansion.

    Note ``let_syntax[]`` and ``abbrev[]`` are completely eliminated by
    macro expansion, so they are seen only if ``expanded=False``.
    """
    if expanded:
        # name must match what ``unpythonic.syntax.letdo._letimpl`` uses in its output.
        if type(tree) is Call and isx(tree.func, "letter", accept_attr=False):
            return ("expanded", None)  # TODO: detect let/letseq/letrec mode also for expanded forms (from kwargs)
        return False
    # dlet((k0, v0), ...)  (call, usually in a decorator list)
    deconames = ("dlet", "dletseq", "dletrec",
                 "blet", "bletseq", "bletrec")
    if type(tree) is Call and type(tree.func) is Name:
        s = tree.func.id
        if any(s == x for x in deconames):
            return ("decorator", s)
    # otherwise we should have an expr macro invocation
    if not (type(tree) is Subscript and type(tree.slice) is Index):
        return False
    macro = tree.value
    expr = tree.slice.value
    exprnames = ("let", "letseq", "letrec", "let_syntax", "abbrev")
    # let((k0, v0), ...)[body]
    if type(macro) is Call and type(macro.func) is Name:
        s = macro.func.id
        if any(s == x for x in exprnames):
            return ("lispy_expr", s)
    # The haskelly syntaxes are only available as a let expression (no decorator form).
    elif type(macro) is Name:
        s = macro.id
        if not any(s == x for x in exprnames):
            return False
        h = _ishaskellylet(expr)
        if h:
            return (h, s)
    return False

def _ishaskellylet(tree):
    """Test whether tree is the content of a haskelly let.

    Return a truthy value if it is, ``False`` if not.

    In other words, detect the part inside the brackets in::

        let[((k0, v0), ...) in body]
        let[body, where((k0, v0), ...)]

    To detect the full expression including the ``let[]``, use ``islet`` instead.
    """
    # let[((k0, v0), ...) in body]
    if type(tree) is Compare and \
       len(tree.ops) == 1 and type(tree.ops[0]) is In and \
       type(tree.left) is Tuple:
        bindings = tree.left
        if all((type(b) is Tuple and len(b.elts) == 2 and type(b.elts[0]) is Name)
                   for b in bindings.elts):
            return "in_expr"
    # let[body, where((k0, v0), ...)]
    elif type(tree) is Tuple and len(tree.elts) == 2 and type(tree.elts[1]) is Call:
        thecall = tree.elts[1]
        if type(thecall.func) is Name and thecall.func.id == "where":
            return "where_expr"
    return False

def isdo(tree, expanded=True):
    """Detect whether tree is a ``do[]`` or ``do0[]``.

    expanded: if ``True``, test for the already expanded form.
    If ``False``, test for the form that exists prior to macro expansion.
    """
    if expanded:
        # name must match what ``unpythonic.syntax.letdo.do`` uses in its output.
        return type(tree) is Call and isx(tree.func, "dof")
    # TODO: detect also do[] with a single expression inside? (now requires a comma)
    return type(tree) is Subscript and \
           type(tree.value) is Name and any(tree.value.id == x for x in ("do", "do0")) and \
           type(tree.slice) is Index and type(tree.slice.value) is Tuple

# TODO: kwargs support for let(x=42)[...] if implemented later
class UnexpandedLetView:
    """Destructure a let form, writably.

    If ``tree`` cannot be interpreted as a ``let`` form, then ``TypeError``
    is raised.

    For in-place modification of ``bindings`` or ``body``. Use before the ``let``
    form is expanded away.

    **Supported formats**::

        dlet((k0, v0), ...)              # decorator
        let((k0, v0), ...)[body]         # lispy expression
        let[((k0, v0), ...) in body]     # haskelly expression
        let[body, where((k0, v0), ...)]  # haskelly expression, inverted

    In addition, we also support *just the bracketed part* of the haskelly
    formats. This is to make it easier for the macro interface to destructure
    these forms (for sending into the ``let`` syntax transformer). So these
    forms are supported, too::

        ((k0, v0), ...) in body
        (body, where((k0, v0), ...))

    This is a data abstraction that hides the detailed structure of the AST,
    since there are three alternate syntaxes that can be used for a ``let``
    expression.

    For the decorator forms, ``tree`` should be the decorator call. In this case
    only ``bindings`` is available (the body is then the body of the function
    being decorated).

    **Attributes**:

        ``bindings`` is a ``list`` of ``ast.Tuple``, where each item is of the form
        ``(k, v)``, where ``k`` is an ``ast.Name``. Writing to ``bindings`` updates
        the original.

        ``body`` (when available) is an AST representing an expression. If the
        outermost layer is an ``ast.List``, it means an implicit ``do[]``
        (handled by the ``let`` expander), allowing a multiple-expression body.
        Writing to ``body`` updates the original.

        When not available, ``body is None``.

        ``mode`` is one of ``let``, ``letseq``, ``letrec``; for information only
        (this essentially says what the ``bindings`` mean).

        If ``tree`` is just the bracketed part of a haskelly let, then ``mode`` is
        ``None``, because the mode information is contained in the surrounding
        subscript form (expr macro invocation) and hence not accessible from here.
    """
    def __init__(self, tree):
        data = islet(tree, expanded=False)
        if not data:
            # the macro interface only gets the bracketed part as tree,
            # so we jump through hoops to make this usable both from
            # syntax transformers (which have access to the full AST)
            # and the macro interface (which needs to destructure bindings and body
            # from the given tree, to send them to the let transformer).
            h = _ishaskellylet(tree)
            if not h:
                raise TypeError("expected a tree representing a let, got {}".format(tree))
            data = (h, None)  # cannot detect mode, no access to the surrounding subscript form
        self._tree = tree
        self._type, self.mode = data
        if self._type == "decorator":
            self.body = None

    def _getbindings(self):
        t = self._type
        if t == "decorator":  # bare Call
            return self._tree.args
        elif t == "lispy_expr":  # Call inside a Subscript
            return self._tree.value.args
        else:  # haskelly let
            # self.mode is set if the Subscript container is present.
            theexpr = self._tree.slice.value if self.mode else self._tree
            if t == "in_expr":
                return theexpr.left.elts
            elif t == "where_expr":
                return theexpr.elts[1].args
            raise NotImplementedError("unknown let form type '{}'".format(t))
    def _setbindings(self, newbindings):
        t = self._type
        if t == "decorator":
            self._tree.args = newbindings
        elif t == "lispy_expr":
            self._tree.value.args = newbindings
        else:
            theexpr = self._tree.slice.value if self.mode else self._tree
            if t == "in_expr":
                theexpr.left.elts = newbindings
            elif t == "where_expr":
                theexpr.elts[1].args = newbindings
            raise NotImplementedError("unknown let form type '{}'".format(t))
    bindings = property(fget=_getbindings, fset=_setbindings, doc="The bindings subform of the let. Writable.")

    def _getbody(self):
        t = self._type
        if t == "decorator":
            # not reached, but let's leave this here for documentation.
            raise TypeError("the body of a decorator let form is the body of decorated function, not a subform of the let.")
        elif t == "lispy_expr":
            return self._tree.slice.value
        else:
            theexpr = self._tree.slice.value if self.mode else self._tree
            if t == "in_expr":
                return theexpr.comparators[0]
            elif t == "where_expr":
                return theexpr.elts[0]
            raise NotImplementedError("unknown let form type '{}'".format(t))
    def _setbody(self, newbody):
        t = self._type
        if t == "decorator":
            # not reached, but let's leave this here for documentation.
            raise TypeError("the body of a decorator let form is the body of decorated function, not a subform of the let.")
        elif t == "lispy_expr":
            self._tree.slice.value = newbody
        else:
            theexpr = self._tree.slice.value if self.mode else self._tree
            if t == "in_expr":
                theexpr.comparators[0] = newbody
            elif t == "where_expr":
                theexpr.elts[0] = newbody
            raise NotImplementedError("unknown let form type '{}'".format(t))
    body = property(fget=_getbody, fset=_setbody, doc="The body subform of the let (only for expr forms). Writable.")

class UnexpandedDoView:
    """Destructure a do form, writably.

    If ``tree`` cannot be interpreted as a ``do`` form, then ``TypeError``
    is raised.

    For easy in-place modification of ``body``. Use before the ``do`` form
    is expanded away.

    **Supported formats**:

        do[body0, ...]
        do0[body0, ...]
        [...]

    The list format is for convenience, for viewing an implicit ``do[]`` in the
    body of a ``let`` form.

    **Attributes**:

        ``body`` is a ``list`` of the expressions in the body of the ``do[]``.
        Writing to it updates the original.
    """
    def __init__(self, tree):
        self._implicit = False
        if not isdo(tree, expanded=False):
            if type(tree) is not List:  # for implicit do[]
                raise TypeError("expected a tree representing a do, got {}".format(tree))
            self._implicit = True
        self._tree = tree

    def _getbody(self):
        return self._tree.slice.value.elts if not self._implicit else self._tree.elts
    def _setbody(self, newbody):
        if not self._implicit:
            self._tree.slice.value.elts = newbody
        else:
            self._tree.elts = newbody
    body = property(fget=_getbody, fset=_setbody, doc="The body of the do. Writable.")

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
        for item in tree.args:  # each arg to dof() is a lambda
            detect_lambda.collect(item.body)
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
        assert False  # we currently support known decorators only

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
