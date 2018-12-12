# -*- coding: utf-8 -*-
"""Detect let and do forms, and destructure them writably.

Separate from letdo.py for dependency reasons.
Separate from util.py due to the length.
"""

from ast import Call, Name, Subscript, Index, Compare, In, Tuple, List

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
        if type(tree) is Call and type(tree.func) is Name and tree.func.id == "letter":
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
        return type(tree) is Call and type(tree.func) is Name and tree.func.id == "dof"
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
                # check a common mistake, missing trailing comma after a single binding ((k, v),)
                if type(tree) is Compare and len(tree.ops) == 1 and type(tree.ops[0]) is In:
                    bindings = tree.left
                    if type(bindings) is Tuple and len(bindings.elts) == 2 and type(bindings.elts[0]) is Name:
                        raise TypeError("expected a tree representing a let; maybe missing trailing comma after a single binding?")
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
