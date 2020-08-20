# -*- coding: utf-8 -*-

from ..syntax import macros, test  # noqa: F401
from .fixtures import session, testset

from ..arity import (arities, required_kwargs, optional_kwargs, kwargs,
                     resolve_bindings, tuplify_bindings)

def runtests():
    with testset("arities basic usage"):
        _ = None  # just some no-op value
        infty = float("+inf")
        items = (((lambda a: _), (1, 1)),
                 ((lambda a, b: _), (2, 2)),
                 ((lambda a, b, c, *args: _), (3, infty)),
                 ((lambda *args: _), (0, infty)),
                 ((lambda **kwargs: _), (0, 0)),
                 ((lambda *args, **kwargs: _), (0, infty)),
                 ((lambda a, b, *, c: _), (2, 2)),
                 ((lambda *, a: _), (0, 0)),
                 ((lambda a, b, *arg, c, **kwargs: _), (2, infty)),
                 ((lambda a, b=42: _), (1, 2)))
        for f, answer in items:
            test[arities(f) == answer]

    with testset("kwargs"):
        test[required_kwargs(lambda *, a, b, c=42: _) == set(('a', 'b'))]
        test[optional_kwargs(lambda *, a, b, c=42: _) == set(('c'))]
        test[kwargs(lambda *, a, b, c=42: _) == (set(('a', 'b')), set(('c')))]
        test[required_kwargs(lambda a, b, c=42: _) == set()]
        test[optional_kwargs(lambda a, b, c=42: _) == set()]
        test[kwargs(lambda a, b, c=42: _) == (set(), set())]

    with testset("arities and OOP"):
        class A:
            def __init__(self):
                pass
            def meth(self, x):
                pass
            @classmethod
            def classmeth(cls, x):
                pass
            @staticmethod
            def staticmeth(x):
                pass
        test[arities(A) == (0, 0)]  # no args beside the implicit self
        # methods on the class
        test[arities(A.meth) == (2, 2)]
        test[arities(A.classmeth) == (1, 1)]
        test[arities(A.staticmeth) == (1, 1)]
        # methods on an instance
        a = A()
        test[arities(a.meth) == (1, 1)]  # self is implicit, so just one
        # class and static methods are always unbound
        test[arities(a.classmeth) == (1, 1)]
        test[arities(a.staticmeth) == (1, 1)]

    # resolve_bindings: resolve parameter bindings established by a function
    # when it is called with the given args and kwargs.
    #
    # This is useful for memoizers and the like, to prevent spurious cache misses
    # due to Python's flexible argument passing syntax.
    with testset("resolve_bindings"):
        def r(f, *args, **kwargs):
            return tuplify_bindings(resolve_bindings(f, *args, **kwargs))

        def f(a):
            pass
        byposition = r(f, 1)
        byname = r(f, a=1)
        test[byposition == byname]

        def f(a=42):
            pass
        test[r(f) == (("args", (("a", 42),)),
                      ("vararg", None), ("vararg_name", None),
                      ("kwarg", None), ("kwarg_name", None))]
        test[r(f, 17) == (("args", (("a", 17),)),
                          ("vararg", None), ("vararg_name", None),
                          ("kwarg", None), ("kwarg_name", None))]
        test[r(f, a=23) == (("args", (("a", 23),)),
                            ("vararg", None), ("vararg_name", None),
                            ("kwarg", None), ("kwarg_name", None))]

        def f(a, b, c):
            pass
        test[r(f, 1, 2, 3) == (("args", (("a", 1), ("b", 2), ("c", 3))),
                               ("vararg", None), ("vararg_name", None),
                               ("kwarg", None), ("kwarg_name", None))]
        test[r(f, a=1, b=2, c=3) == (("args", (("a", 1), ("b", 2), ("c", 3))),
                                     ("vararg", None), ("vararg_name", None),
                                     ("kwarg", None), ("kwarg_name", None))]
        test[r(f, 1, 2, c=3) == (("args", (("a", 1), ("b", 2), ("c", 3))),
                                 ("vararg", None), ("vararg_name", None),
                                 ("kwarg", None), ("kwarg_name", None))]
        test[r(f, 1, c=3, b=2) == (("args", (("a", 1), ("b", 2), ("c", 3))),
                                   ("vararg", None), ("vararg_name", None),
                                   ("kwarg", None), ("kwarg_name", None))]
        test[r(f, c=3, b=2, a=1) == (("args", (("a", 1), ("b", 2), ("c", 3))),
                                     ("vararg", None), ("vararg_name", None),
                                     ("kwarg", None), ("kwarg_name", None))]

        def f(a, b, c, *args):
            pass
        test[r(f, 1, 2, 3, 4, 5) == (("args", (("a", 1), ("b", 2), ("c", 3))),
                                     ("vararg", (4, 5)), ("vararg_name", "args"),
                                     ("kwarg", None), ("kwarg_name", None))]

        # On Python 3.5, there's no guarantee about the ordering of the kwargs.
        # Our analysis machinery preserves the order it gets, but the *input*
        # may already differ from how the invocation of `r` is written in the
        # source code here.
        #
        # So we must allow for arbitrary ordering of the kwargs when checking
        # the result.
        #
        def check35(result, truth):
            args_r, vararg_r, vararg_name_r, kwarg_r, kwarg_name_r = result
            args_t, vararg_t, vararg_name_t, kwarg_t, kwarg_name_t = truth
            couldbe = (args_r == args_t and vararg_r == vararg_t and
                       vararg_name_r == vararg_name_t and kwarg_name_r == kwarg_name_t)
            if not couldbe:
                return False
            name_r, contents_r = kwarg_r
            name_t, contents_t = kwarg_t
            return name_r == name_t and set(contents_r) == set(contents_t)

        def f(a, b, c, **kw):
            pass
        test[check35(r(f, 1, 2, 3, d=4, e=5), (("args", (("a", 1), ("b", 2), ("c", 3))),
                                               ("vararg", None), ("vararg_name", None),
                                               ("kwarg", (("d", 4), ("e", 5))), ("kwarg_name", "kw")))]

        def f(a, b, c, *args, **kw):
            pass
        test[check35(r(f, 1, 2, 3, 4, 5, d=6, e=7), (("args", (("a", 1), ("b", 2), ("c", 3))),
                                                     ("vararg", (4, 5)), ("vararg_name", "args"),
                                                     ("kwarg", (("d", 6), ("e", 7))), ("kwarg_name", "kw")))]

        # TODO: On Python 3.6+, this becomes just:
        #
        # def f(a, b, c, **kw):
        #     pass
        # test[r(f, 1, 2, 3, d=4, e=5) == (("args", (("a", 1), ("b", 2), ("c", 3))),
        #                                  ("vararg", None), ("vararg_name", None),
        #                                  ("kwarg", (("d", 4), ("e", 5))), ("kwarg_name", "kw"))]
        #
        # def f(a, b, c, *args, **kw):
        #     pass
        # test[r(f, 1, 2, 3, 4, 5, d=6, e=7) == (("args", (("a", 1), ("b", 2), ("c", 3))),
        #                                        ("vararg", (4, 5)), ("vararg_name", "args"),
        #                                        ("kwarg", (("d", 6), ("e", 7))), ("kwarg_name", "kw"))]

if __name__ == '__main__':  # pragma: no cover
    with session(__file__):
        runtests()
