# -*- coding: utf-8 -*-
"""Detect let and do forms, and destructure them writably."""

__all__ = ["where",
           "canonize_bindings",  # used by the macro interface layer
           "isenvassign", "islet", "isdo",
           "UnexpandedEnvAssignView", "UnexpandedLetView", "UnexpandedDoView",
           "ExpandedLetView", "ExpandedDoView"]

from ast import (Call, Name, Subscript, Index, Compare, In,
                 Tuple, List, Constant, BinOp, LShift, Lambda)
import sys

from mcpyrate.core import Done

from .astcompat import getconstant, Str
from .nameutil import isx, getname

def where(*bindings):
    """[syntax] Only meaningful in a let[body, where((k0, v0), ...)]."""
    raise RuntimeError("where() is only meaningful in a let[body, where((k0, v0), ...)]")  # pragma: no cover

letf_name = "letter"  # must match what ``unpythonic.syntax.letdo._let_expr_impl`` uses in its output.
dof_name = "dof"      # name must match what ``unpythonic.syntax.letdo.do`` uses in its output.
currycall_name = "currycall"  # output of ``unpythonic.syntax.curry``

# TODO: switch from call to subscript in name position for let_syntax templates.
def canonize_bindings(elts, allow_call_in_name_position=False):  # public as of v0.14.3+
    """Wrap a single binding without container into a length-1 `list`.

    Pass through multiple bindings as-is.

    Yell if the input format is invalid.

    elts: `list` of bindings, either::
        [(k0, v0), ...]   # multiple bindings contained in a tuple
        [(k, v),]         # single binding contained in a tuple also ok
        [k, v]            # special single binding format, missing tuple container

    where the ks and vs are AST nodes.

    allow_call_in_name_position: used by let_syntax to allow template definitions;
    in the call, the "function" is the template name, and the positional "parameters"
    are the template parameters (which may then appear in the template body).
    """
    def isname(x):
        # The `Done` may be produced by expanded `@namemacro`s.
        return type(x) is Name or (isinstance(x, Done) and isname(x.body))
    def iskey(x):
        return (isname(x) or
                (allow_call_in_name_position and type(x) is Call and isname(x.func)))
    if len(elts) == 2 and iskey(elts[0]):
        return [Tuple(elts=elts)]  # TODO: `mcpyrate`: just `q[t[elts]]`?
    if all((type(b) is Tuple and len(b.elts) == 2 and iskey(b.elts[0])) for b in elts):
        return elts
    raise SyntaxError("expected bindings to be ((k0, v0), ...) or a single (k, v)")  # pragma: no cover

def isenvassign(tree):
    """Detect whether tree is an unpythonic ``env`` assignment, ``name << value``.

    The only way this differs from a general left-shift is that the LHS must be
    an ``ast.Name``.
    """
    if not (type(tree) is BinOp and type(tree.op) is LShift):
        return False
    # The `Done` may be produced by expanded `@namemacro`s.
    return type(tree.left) is Name or (isinstance(tree.left, Done) and type(tree.body) is Name)

def islet(tree, expanded=True):
    """Test whether tree is a ``let[]``, ``letseq[]``, ``letrec[]``,
    ``let_syntax[]``, or ``abbrev[]``.

    expanded: if ``True``, test for the already expanded form.
    If ``False``, test for the form that exists prior to macro expansion.
    (Which you need depends on when your macro runs.)

    Note ``let_syntax[]`` and ``abbrev[]`` are completely eliminated by
    macro expansion, so they are seen only if ``expanded=False``.

    Return a truthy value if ``tree`` is a let form, ``False`` if not.
    The truthy return value is a tuple of two strings, ``(kind, mode)``.

    **If expanded=False**:

    Then ``kind`` is one of ``"decorator"``, ``"lispy_expr"``, ``"in_expr"``
    or ``"where_expr"``.

    If ``kind="decorator"``, then ``mode`` is one of ``"dlet"``, ``"dletseq"``,
    ``"dletrec"``, ``"blet"``, ``"bletseq"`` or ``"bletrec"``, identifying
    which decorator it is.

    Otherwise ``mode`` is one of ``"let"``, ``"letseq"``, ``"letrec"``,
    ``"let_syntax"`` or ``"abbrev"``, identifying which let form it is.

    **If expanded=True**:

    Then ``kind`` is one of ``"expanded_decorator"``, ``"expanded_expr"``,
    ``"curried_decorator"`` or ``"curried_expr"``, and ``mode`` is
    ``"let"`` or ``"letrec"``.

    Keep in mind that ``letseq[]`` expands into a sequence of nested ``let[]``.

    (This is a lot of cases for the caller to handle, but that's because
    there are many different AST structures that correspond to ``let`` forms
    in unpythonic.)
    """
    if expanded:
        if type(tree) is not Call:
            return False
        kind = "expanded"
        if isx(tree.func, currycall_name) and isx(tree.args[0], letf_name):
            kind = "curried"
        elif not isx(tree.func, letf_name):
            return False
        mode = [kw.value for kw in tree.keywords if kw.arg == "mode"]
        assert len(mode) == 1 and type(mode[0]) in (Constant, Str)
        mode = getconstant(mode[0])
        kwnames = [kw.arg for kw in tree.keywords]
        if "_envname" in kwnames:
            return (f"{kind}_decorator", mode)  # this call was generated by _let_decorator_impl
        else:
            return (f"{kind}_expr", mode)       # this call was generated by _let_expr_impl
    # dlet[(k0, v0), ...]  (usually in a decorator list)
    deconames = ("dlet", "dletseq", "dletrec",
                 "blet", "bletseq", "bletrec")
    if type(tree) is Subscript and type(tree.value) is Name:  # could be a Subscript decorator (Python 3.9+)
        s = tree.value.id
        if any(s == x for x in deconames):
            return ("decorator", s)
    if type(tree) is Call and type(tree.func) is Name:  # parenthesis syntax for macro arguments  TODO: Python 3.9+: remove once we bump minimum Python to 3.9
        s = tree.func.id
        if any(s == x for x in deconames):
            return ("decorator", s)
    # otherwise we should have an expr macro invocation
    if not type(tree) is Subscript:
        return False
    # let[(k0, v0), ...][body]
    # let((k0, v0), ...)[body]
    # ^^^^^^^^^^^^^^^^^^
    macro = tree.value
    # let[(k0, v0), ...][body]
    # let((k0, v0), ...)[body]
    #                    ^^^^
    if sys.version_info >= (3, 9, 0):  # Python 3.9+: the Index wrapper is gone.
        expr = tree.slice
    else:
        expr = tree.slice.value
    exprnames = ("let", "letseq", "letrec", "let_syntax", "abbrev")
    if type(macro) is Subscript and type(macro.value) is Name:
        s = macro.value.id
        if any(s == x for x in exprnames):
            return ("lispy_expr", s)
    elif type(macro) is Call and type(macro.func) is Name:  # parenthesis syntax for macro arguments  TODO: Python 3.9+: remove once we bump minimum Python to 3.9
        s = macro.func.id
        if any(s == x for x in exprnames):
            return ("lispy_expr", s)
    # The haskelly syntaxes are only available as a let expression (no decorator form).
    elif type(macro) is Name:
        s = macro.id
        if any(s == x for x in exprnames):
            h = _ishaskellylet(expr)
            if h:
                return (h, s)
    return False  # not a let macro invocation, or invalid let syntax.

def _ishaskellylet(tree):
    """Test whether tree is the content of a haskelly let.

    Return a truthy value if it is, ``False`` if not.

    In other words, detect the part inside the brackets in::

        let[((k0, v0), ...) in body]
        let[body, where((k0, v0), ...)]

    To detect the full expression including the ``let[]``, use ``islet`` instead.
    """
    # let[((k0, v0), ...) in body]
    def maybeiscontentofletin(tree):
        return (type(tree) is Compare and
                len(tree.ops) == 1 and type(tree.ops[0]) is In and
                type(tree.left) is Tuple)
    # let[body, where((k0, v0), ...)]
    def maybeiscontentofletwhere(tree):
        return type(tree) is Tuple and len(tree.elts) == 2 and type(tree.elts[1]) is Call

    if maybeiscontentofletin(tree):
        bindings = tree.left
        if all((type(b) is Tuple and len(b.elts) == 2 and type(b.elts[0]) is Name)
                   for b in bindings.elts):
            return "in_expr"
        # Single binding special case: let's not require a trailing comma.
        # In this case, the wrapper tuple containing the bindings is missing.
        # (For consistency of surface syntax with the other variants that don't
        #  require it, because they look like function calls in the AST.)
        if len(bindings.elts) == 2 and type(bindings.elts[0]) is Name:
            return "in_expr"
    elif maybeiscontentofletwhere(tree):
        thecall = tree.elts[1]
        if type(thecall.func) is Name and thecall.func.id == "where":
            return "where_expr"
    return False  # invalid syntax for haskelly let

def isdo(tree, expanded=True):
    """Detect whether tree is a ``do[]`` or ``do0[]``.

    expanded: if ``True``, test for the already expanded form.
    If ``False``, test for the form that exists prior to macro expansion.

    Return a truthy value if ``tree`` is a do form, ``False`` if not.

    **If expanded=False**:

    Then the truthy return value is just ``True``.

    **If expanded=True**:

    Then the truthy return value is one of the strings ``"expanded"`` or
    ``"curried"``.
    """
    if expanded:
        if type(tree) is not Call:
            return False
        kind = "expanded"
        if isx(tree.func, currycall_name) and isx(tree.args[0], dof_name):
            kind = "curried"
        elif not isx(tree.func, dof_name):
            return False
        return kind

    if not (type(tree) is Subscript and
            type(tree.value) is Name and any(tree.value.id == x for x in ("do", "do0"))):
        return False

    # TODO: detect also do[] with a single expression inside? (now requires a comma)
    if sys.version_info >= (3, 9, 0):  # Python 3.9+: the Index wrapper is gone.
        if not type(tree.slice) is Tuple:
            return False
    else:
        if not type(tree.slice) is Index and type(tree.slice.value) is Tuple:
            return False

    return tree.value.id

# -----------------------------------------------------------------------------

class UnexpandedEnvAssignView:
    """Destructure an env-assignment, writably.

    If ``tree`` cannot be interpreted as an unpythonic ``env`` assignment
    of the form ``name << value``, then ``TypeError`` is raised.

    For easy in-place modification of both ``name`` and ``value``. Use before
    the env-assignment is expanded away (so, before the ``let[]`` or ``do[]``
    containing it is expanded away).

    **Attributes**:

        ``name``: the name of the variable, as a str.

        ``value``: the thing being assigned, as an AST.

    Writing to either attribute updates the original.
    """
    def __init__(self, tree):
        if not isenvassign(tree):
            raise TypeError(f"expected a tree representing an unexpanded env-assignment, got {tree}")
        self._tree = tree

    def _getname(self):
        return getname(self._tree.left, accept_attr=False)
    def _setname(self, newname):
        if not isinstance(newname, str):
            raise TypeError(f"expected str for new name, got {type(newname)} with value {repr(newname)}")
        # The `Done` may be produced by expanded `@namemacro`s.
        if isinstance(self._tree.left, Done):
            self._tree.left.body.id = newname
        else:
            self._tree.left.id = newname
    name = property(fget=_getname, fset=_setname, doc="The name of the assigned var, as an str. Writable.")

    def _getvalue(self):
        return self._tree.right
    def _setvalue(self, newvalue):
        self._tree.right = newvalue
    value = property(fget=_getvalue, fset=_setvalue, doc="The value of the assigned var, as an AST. Writable.")

# TODO: kwargs support for let(x=42)[...] if implemented later
class UnexpandedLetView:
    """Destructure a let form, writably.

    If ``tree`` cannot be interpreted as a ``let`` form, then ``TypeError``
    is raised.

    For in-place modification of ``bindings`` or ``body``. Use before the ``let``
    form is expanded away.

    **Supported formats**::

        dlet[(k0, v0), ...]              # decorator
        let[(k0, v0), ...][body]         # lispy expression
        let[((k0, v0), ...) in body]     # haskelly expression
        let[body, where((k0, v0), ...)]  # haskelly expression, inverted

    Lispy expressions are supported also using the old parenthesis syntax
    to pass macro arguments::

        let((k0, v0), ...)[body]         # lispy expression

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

        ``body`` (when available) is an AST representing a single expression.
        If it is an ``ast.List``, it means an implicit ``do[]`` (handled by the
        ``let`` expander), allowing a multiple-expression body.

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
        self._has_subscript_container = True
        if not data:
            # The macro interface only gets the bracketed part as "tree",
            # so we jump through hoops to make this usable both from
            # syntax transformers (which have access to the full AST)
            # and the macro interface (which needs to destructure bindings and body
            # from the given tree, to send them to the let transformer).
            h = _ishaskellylet(tree)
            if not h:
                raise TypeError(f"expected a tree representing an unexpanded let, got {tree}")
            data = (h, None)  # cannot detect mode, because no access to the surrounding Subscript AST node
            self._has_subscript_container = False
        self._tree = tree
        self._type, self.mode = data
        if self._type not in ("decorator", "lispy_expr", "in_expr", "where_expr"):
            raise NotImplementedError(f"unknown unexpanded let form type '{self._type}'")  # pragma: no cover, this just catches the internal error if we add new forms but forget to add them here.

    # Resolve the "content" node in the haskelly format.
    def _theexpr_ref(self):
        if self._has_subscript_container:
            if sys.version_info >= (3, 9, 0):  # Python 3.9+: the Index wrapper is gone.
                return self._tree.slice
            else:
                return self._tree.slice.value
        else:
            return self._tree

    def _getbindings(self):
        t = self._type
        if t == "decorator":  # bare Subscript, dlet[...], blet[...]
            if type(self._tree) is Call:  # parenthesis syntax for macro arguments  TODO: Python 3.9+: remove once we bump minimum Python to 3.9
                return canonize_bindings(self._tree.args)
            # Subscript as decorator (Python 3.9+)
            if sys.version_info >= (3, 9, 0):  # Python 3.9+: the Index wrapper is gone.
                theargs = self._tree.slice
            else:
                theargs = self._tree.slice.value
            return canonize_bindings(theargs.elts)
        elif t == "lispy_expr":
            # Subscript inside a Subscript, (let[...])[...]
            if type(self._tree.value) is Subscript:
                if sys.version_info >= (3, 9, 0):  # Python 3.9+: the Index wrapper is gone.
                    theargs = self._tree.value.slice.elts
                else:
                    theargs = self._tree.value.slice.value.elts
            # parenthesis syntax for macro arguments  TODO: Python 3.9+: remove once we bump minimum Python to 3.9
            # Call inside a Subscript, (let(...))[...]
            else:  # type(self._tree.value) is Call:
                theargs = self._tree.value.args
            return canonize_bindings(theargs)
        else:  # haskelly let, let[(...) in ...], let[..., where(...)]
            theexpr = self._theexpr_ref()
            if t == "in_expr":
                return canonize_bindings(theexpr.left.elts)
            elif t == "where_expr":
                return canonize_bindings(theexpr.elts[1].args)
    def _setbindings(self, newbindings):
        t = self._type
        if t == "decorator":
            if type(self._tree) is Call:  # parenthesis syntax for macro arguments  TODO: Python 3.9+: remove once we bump minimum Python to 3.9
                self._tree.args = newbindings
                return
            # Subscript as decorator (Python 3.9+)
            if sys.version_info >= (3, 9, 0):  # Python 3.9+: the Index wrapper is gone.
                self._tree.slice.elts = newbindings
            else:
                self._tree.slice.value.elts = newbindings
        elif t == "lispy_expr":
            # Subscript inside a Subscript, (let[...])[...]
            if type(self._tree.value) is Subscript:
                if sys.version_info >= (3, 9, 0):  # Python 3.9+: the Index wrapper is gone.
                    self._tree.value.slice.elts = newbindings
                else:
                    self._tree.value.slice.value.elts = newbindings
            # parenthesis syntax for macro arguments  TODO: Python 3.9+: remove once we bump minimum Python to 3.9
            # Call inside a Subscript, (let(...))[...]
            else:  # type(self._tree.value) is Call:
                self._tree.value.args = newbindings
        else:
            theexpr = self._theexpr_ref()
            if t == "in_expr":
                theexpr.left.elts = newbindings
            elif t == "where_expr":
                theexpr.elts[1].args = newbindings
    bindings = property(fget=_getbindings, fset=_setbindings, doc="The bindings subform of the let. Writable.")

    def _getbody(self):
        t = self._type
        if t == "decorator":
            raise TypeError("the body of a decorator let form is the body of decorated function, not a subform of the let.")
        elif t == "lispy_expr":
            if sys.version_info >= (3, 9, 0):  # Python 3.9+: the Index wrapper is gone.
                return self._tree.slice
            else:
                return self._tree.slice.value
        else:
            theexpr = self._theexpr_ref()
            if t == "in_expr":
                return theexpr.comparators[0]
            elif t == "where_expr":
                return theexpr.elts[0]
    def _setbody(self, newbody):
        t = self._type
        if t == "decorator":
            raise TypeError("the body of a decorator let form is the body of decorated function, not a subform of the let.")
        elif t == "lispy_expr":
            if sys.version_info >= (3, 9, 0):  # Python 3.9+: the Index wrapper is gone.
                self._tree.slice = newbody
            else:
                self._tree.slice.value = newbody
        else:
            theexpr = self._theexpr_ref()
            if t == "in_expr":
                theexpr.comparators[0] = newbody
            elif t == "where_expr":
                theexpr.elts[0] = newbody
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
                raise TypeError(f"expected a tree representing an unexpanded do, got {tree}")
            self._implicit = True
        self._tree = tree

    def _getbody(self):
        if not self._implicit:
            if sys.version_info >= (3, 9, 0):  # Python 3.9+: the Index wrapper is gone.
                return self._tree.slice.elts
            else:
                return self._tree.slice.value.elts
        else:
            return self._tree.elts
    def _setbody(self, newbody):
        if not self._implicit:
            if sys.version_info >= (3, 9, 0):  # Python 3.9+: the Index wrapper is gone.
                self._tree.slice.elts = newbody
            else:
                self._tree.slice.value.elts = newbody
        else:
            self._tree.elts = newbody
    body = property(fget=_getbody, fset=_setbody, doc="The body of the do. Writable.")

# -----------------------------------------------------------------------------

class ExpandedLetView:
    """Like UnexpandedLetView, but for already expanded let constructs.

    We support both "with autocurry" and bare formats.

    This is for simple in-place modifications; changing the number of bindings
    is currently not supported. Prefer doing any extensive modifications in the
    first pass, before the ``let[]`` expands.

    The bindings are contained in an `ast.Tuple`. Each binding is also an `ast.Tuple`.

    The LHS of each binding (containing a variable name) is an `str` (not a
    `Name` node; the expansion of the `let` has transformed them).

    Depending on whether let mode is "let" or "letrec", the RHS of each binding
    is a bare value or ``lambda e: ...``, respectively.

    ``body``, when available, is a single expression, of the format ``lambda e: ...``.

    In the case of a multiple-expression body (implicit do, a.k.a. extra bracket syntax),
    the body *of that lambda* is an expanded ``do``, which can be destructured using
    ``ExpandedDoView``.

    **New features added in v0.14.3**:

    The ``let`` environment name is available in the ``envname`` attribute.
    When editing the bindings and the body, you'll need it to refer to the
    variables defined in the let, since those are actually attributes of the
    env.

    For the ``lambda e: ...``, in both the body and in letrec bindings, when
    assigning a new `body` or `bindings`, the correct envname is auto-injected
    as the arg of the lambda. So you only need ``envname`` to refer to the let
    environment *inside the body of that lambda*.

    Some basic type validation is performed by the property setters when
    assigning a new `body` or `bindings`. Note this implies that if you edit
    `bindings` in-place, without assigning to the `bindings` property,
    **absolutely no validation is performed**, and also the envname
    auto-injection is skipped, because that too is performed by the property
    setter. So it's better to always reassign the whole `bindings`, even if you
    just make some minor adjustment to one of the bindings.
    """
    def __init__(self, tree):
        data = islet(tree, expanded=True)
        if not data:
            raise TypeError(f"expected a tree representing an expanded let, got {tree}")
        self._tree = tree
        self._type, self.mode = data
        if self._type not in ("expanded_decorator", "expanded_expr", "curried_decorator", "curried_expr"):
            raise NotImplementedError(f"unknown expanded let form type '{self._type}'")  # pragma: no cover, this just catches the internal error if we add new forms but forget to add them here.
        self.curried = self._type.startswith("curried")
        self.envname = self._deduce_envname()  # stash at init time to prevent corruption by user mutations.

    def _deduce_envname(self):
        assert all(hasattr(self, x) for x in ("_tree", "_type", "mode", "curried"))  # fully initialized
        try:
            body = self.body
            if type(body) is not Lambda:
                raise TypeError  # pragma: no cover
            return body.args.args[0].arg
        except (TypeError, AttributeError):  # pragma: no cover
            pass
        # no body (we might be a decorator) or can't access it - if we're a letrec, try the bindings
        try:
            # only happens for @dletrec, because a regular letrec always has a body.
            if self.mode == "letrec":
                bindings = self.bindings
                if not bindings.elts:  # need at least one binding
                    raise ValueError  # pragma: no cover
                b = bindings.elts[0]
                if len(b.elts) != 2:  # (k, lambda e: ...)
                    raise ValueError  # pragma: no cover
                lam = b.elts[1]
                if type(lam) is not Lambda:
                    raise TypeError  # pragma: no cover
                return lam.args.args[0].arg
        except (TypeError, AttributeError, ValueError):  # pragma: no cover
            pass
        return None  # give up

    def _getbindings(self):
        # Abstract away the namelambda(...). We support both "with autocurry" and bare formats:
        #   currycall(letter, bindings, currycall(currycall(namelambda, "let_body"), curryf(lambda e: ...)))
        #   letter(bindings, namelambda("let_body")(lambda e: ...))
        thebindings = self._tree.args[1] if self.curried else self._tree.args[0]
        if self.mode == "letrec":
            myelts = []
            if self.curried:
                # "((k, currycall(currycall(namelambda, "letrec_binding_YYY"), curryf(lambda e: ...))), ...)"
                #   ~~~                                                               ^^^^^^^^^^^^^
                for b in thebindings.elts:
                    k, v = b.elts
                    myelts.append(Tuple(elts=[k, v.args[1].args[0]]))
            else:
                # "((k, (namelambda("letrec_binding_YYY"))(lambda e: ...)), ...)"
                #   ~~~                                    ^^^^^^^^^^^^^
                for b in thebindings.elts:
                    k, v = b.elts
                    myelts.append(Tuple(elts=[k, v.args[0]]))
            return Tuple(elts=myelts)
        else:  # "((k, v), ...)"
            return thebindings
    def _setbindings(self, newbindings):
        if type(newbindings) is not Tuple:
            raise TypeError(f"Expected ast.Tuple as the new bindings of the let, got {type(newbindings)}")  # pragma: no cover
        if not all(type(elt) is Tuple for elt in newbindings.elts):
            raise TypeError("Expected ast.Tuple of ast.Tuple as the new bindings of the let")  # pragma: no cover
        if not all(len(binding.elts) == 2 for binding in newbindings.elts):
            raise TypeError("Expected ast.Tuple of length-2 ast.Tuple as the new bindings of the let")  # pragma: no cover
        if len(newbindings.elts) != len(self.bindings.elts):
            raise NotImplementedError("changing the number of items currently not supported by this view (do that before the let[] expands)")  # pragma: no cover
        for newb in newbindings.elts:
            newk, newv = newb.elts
            if type(newk) not in (Constant, Str):  # Python 3.8+: ast.Constant
                raise TypeError("ExpandedLetView: let: each key must be an ast.Constant or an ast.Str")  # pragma: no cover
        # Abstract away the namelambda(...). We support both "with autocurry" and bare formats:
        #   currycall(letter, bindings, currycall(currycall(namelambda, "let_body"), curryf(lambda e: ...)))
        #   letter(bindings, namelambda("let_body")(lambda e: ...))
        thebindings = self._tree.args[1] if self.curried else self._tree.args[0]
        if self.mode == "letrec":
            newelts = []
            curried = self.curried
            envname = self.envname
            for oldb, newb in zip(thebindings.elts, newbindings.elts):
                oldk, thev = oldb.elts
                newk, newv = newb.elts
                newk_string = getconstant(newk)  # Python 3.8+: ast.Constant
                if type(newv) is not Lambda:
                    raise TypeError("ExpandedLetView: letrec: each value must be of the form `lambda e: ...`")  # pragma: no cover
                if curried:
                    #   ((k, currycall(currycall(namelambda, "letrec_binding_YYY"), curryf(lambda e: ...))), ...)
                    #                                        ~~~~~~~~~~~~~~~~~~~~          ^^^^^^^^^^^^^
                    newv.args.args[0].arg = envname  # v0.14.3+: convenience: auto-inject correct envname
                    thev.args[1].args[0] = newv
                    thev.args[0].args[1] = Constant(value=f"letrec_binding_{newk_string}")  # Python 3.8+: ast.Constant
                else:
                    #   ((k, (namelambda("letrec_binding_YYY"))(lambda e: ...)), ...)
                    #                    ~~~~~~~~~~~~~~~~~~~~   ^^^^^^^^^^^^^
                    newv.args.args[0].arg = envname  # v0.14.3+: convenience: auto-inject correct envname
                    thev.args[0] = newv
                    # update name in the namelambda(...)
                    thev.func.args[0] = Constant(value=f"letrec_binding_{newk_string}")  # Python 3.8+: ast.Constant
                # Macro-generated nodes may be missing source location information,
                # in which case we let `mcpyrate` fix it later.
                # This is mainly an issue for the unit tests of this module, which macro-generate the "old" data.
                if hasattr(oldb, "lineno") and hasattr(oldb, "col_offset"):
                    newelts.append(Tuple(elts=[newk, thev], lineno=oldb.lineno, col_offset=oldb.col_offset))
                else:
                    newelts.append(Tuple(elts=[newk, thev]))
            thebindings.elts = newelts
        else:
            thebindings.elts = newbindings.elts
    bindings = property(fget=_getbindings, fset=_setbindings, doc="The bindings subform of the let, as an ast.Tuple. Writable.")

    def _getbody(self):
        if self._type.endswith("decorator"):
            raise TypeError("the body of a decorator let form is the body of decorated function, not a subform of the let.")
        #   currycall(letter, bindings, currycall(currycall(namelambda, "let_body"), curryf(lambda e: ...)))
        #                                                                                   ^^^^^^^^^^^^^
        #   letter(bindings, (namelambda("let_body"))(lambda e: ...))
        #                                             ^^^^^^^^^^^^^
        if self.curried:
            return self._tree.args[2].args[1].args[0]
        else:
            return self._tree.args[1].args[0]
    def _setbody(self, newbody):
        if self._type.endswith("decorator"):
            raise TypeError("the body of a decorator let form is the body of decorated function, not a subform of the let.")
        if type(newbody) is not Lambda:
            raise TypeError("The body must be of the form `lambda e: ...`")  # pragma: no cover
        newbody.args.args[0].arg = self.envname  # v0.14.3+: convenience: auto-inject correct envname
        #   currycall(letter, bindings, currycall(currycall(namelambda, "let_body"), curryf(lambda e: ...)))
        #                                                                                   ^^^^^^^^^^^^^
        #   letter(bindings, (namelambda("let_body"))(lambda e: ...))
        #                                             ^^^^^^^^^^^^^
        if self.curried:
            self._tree.args[2].args[1].args[0] = newbody
        else:
            self._tree.args[1].args[0] = newbody
    body = property(fget=_getbody, fset=_setbody, doc="The body subform of the let (only for expr forms). Writable.")

class ExpandedDoView:
    """Like UnexpandedDoView, but for already expanded do forms.

    We support both "with autocurry" and bare formats.

    This is for simple in-place modifications; changing the number of do-items
    is currently not supported. Prefer doing any extensive modifications in the
    first pass, before the ``do[]`` expands.

    ``body`` is a ``list``, where each item is of the form ``lambda e: ...``.

    **New features added in v0.14.3**:

    The ``do`` environment name is available in the ``envname`` attribute. When
    editing the body, you'll need it to refer to the variables defined in the
    do, since those are actually attributes of the env.

    For all the ``lambda e: ...`` in the body, when assigning a new `body`, the
    correct envname is auto-injected as the arg of the lambda. So you only need
    ``envname`` to refer to the let environment *inside the body of those lambdas*.

    Some basic type validation is performed by the property setter when
    assigning a new `body`. Note this implies that if you edit `body` in-place,
    without assigning to the `body` property, **absolutely no validation is
    performed**, and also the envname auto-injection is skipped, because that
    too is performed by the property setter. So it's better to always reassign
    the whole `body`, even if you just make some minor adjustment to one of the
    items.
    """
    def __init__(self, tree):
        t = isdo(tree, expanded=True)
        if not t:
            raise TypeError(f"expected a tree representing an expanded do, got {tree}")
        self.curried = t.startswith("curried")
        self._tree = tree
        self.envname = self._deduce_envname()  # stash at init time to prevent corruption by user mutations.

    def _deduce_envname(self):
        assert all(hasattr(self, x) for x in ("_tree", "curried"))  # fully initialized
        try:
            body = self.body
            if not body:  # no body items
                raise ValueError  # pragma: no cover
            firstitem = body[0]
            if type(firstitem) is not Lambda:
                raise TypeError  # pragma: no cover
            return firstitem.args.args[0].arg
        except (TypeError, ValueError, AttributeError):  # pragma: no cover
            pass
        return None  # give up  # pragma: no cover

    def _getbody(self):
        #   currycall(dof, currycall(currycall(namelambda, "do_lineXXX"), curryf(lambda e: ...)), ...)
        #                                                                        ^^^^^^^^^^^^^
        #   dof((namelambda("do_lineXXX"))(lambda e: ...), ...)
        #                                  ^^^^^^^^^^^^^
        if self.curried:
            theitems = self._tree.args[1:]
            return [item.args[1].args[0] for item in theitems]
        else:
            theitems = self._tree.args
            return [item.args[0] for item in theitems]
    def _setbody(self, newbody):
        if not isinstance(newbody, list):  # yes, a runtime list!
            raise TypeError(f"Expected list as the new body of the do, got {type(newbody)}")  # pragma: no cover
        if len(newbody) != len(self.body):
            raise NotImplementedError("changing the number of items currently not supported by this view (do that before the do[] expands)")  # pragma: no cover
        #   currycall(dof, currycall(currycall(namelambda, "do_lineXXX"), curryf(lambda e: ...)), ...)
        #                                                                        ^^^^^^^^^^^^^
        #   dof((namelambda("do_lineXXX"))(lambda e: ...), ...)
        #                                  ^^^^^^^^^^^^^
        envname = self.envname
        if self.curried:
            theitems = self._tree.args[1:]
            for old, new in zip(theitems, newbody):
                if type(new) is not Lambda:
                    raise TypeError("Each item of the body must be of the form `lambda e: ...`")  # pragma: no cover
                new.args.args[0].arg = envname  # v0.14.3+: convenience: auto-inject correct envname
                old.args[1].args[0] = new
        else:
            theitems = self._tree.args
            for old, new in zip(theitems, newbody):
                if type(new) is not Lambda:
                    raise TypeError("Each item of the body must be of the form `lambda e: ...`")  # pragma: no cover
                new.args.args[0].arg = envname  # v0.14.3+: convenience: auto-inject correct envname
                old.args[0] = new
    body = property(fget=_getbody, fset=_setbody, doc="The body of the do. Writable.")

# -----------------------------------------------------------------------------
