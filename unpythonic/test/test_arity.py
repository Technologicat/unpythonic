# -*- coding: utf-8 -*-

from ..syntax import macros, test, test_raises, the  # noqa: F401
from .fixtures import session, testset

from ..arity import (arities, arity_includes,
                     required_kwargs, optional_kwargs, kwargs,
                     resolve_bindings, tuplify_bindings,
                     getfunc)

def runtests():
    def barefunction(x):
        pass  # pragma: no cover

    class AnalysisTarget:
        def __init__(self):
            pass
        def instmeth(self, x):
            pass  # pragma: no cover, this class is here just to be analyzed, not run.
        @classmethod
        def classmeth(cls, x):
            pass  # pragma: no cover
        @staticmethod
        def staticmeth(x):
            pass  # pragma: no cover
    target = AnalysisTarget()

    with testset("internal utilities"):
        def kindof(thecallable):
            function, kind = getfunc(thecallable)
            return kind
        test[kindof(barefunction) == "function"]
        test[kindof(AnalysisTarget.instmeth) == "function"]  # instance method, not bound to instance
        test[kindof(AnalysisTarget.classmeth) == "classmethod"]
        test[kindof(AnalysisTarget.staticmeth) == "function"]  # @staticmethod vanishes by this point
        test[kindof(target.instmeth) == "instancemethod"]
        test[kindof(target.classmeth) == "classmethod"]
        test[kindof(target.staticmeth) == "function"]

        # Behavior of `getfunc` while evaluating a class body and called from
        # a decorator that applies *after* `@classmethod` or `@staticmethod`.
        # Not actually used in the codebase, but we want those cases covered too.
        kinds = []
        def grabkind(meth):
            kinds.append(kindof(meth))
            return meth
        class Silly:
            @grabkind
            @classmethod
            def classmeth(cls):
                pass  # pragma: no cover

            @grabkind
            @staticmethod
            def staticmeth():
                pass  # pragma: no cover

            # At class body evaluation time, an instance method
            # is indistinguishable from a bare function.
            @grabkind
            def instmeth(self):
                pass  # pragma: no cover
        test[kinds == ["classmethod", "staticmethod", "function"]]

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
                 ((lambda a, b=42: _), (1, 2)),
                 (print, (1, infty)))  # builtin
        for f, answer in items:
            test[arities(f) == answer]

        test[arity_includes((lambda a: _), 1)]
        test[not arity_includes((lambda a: _), 2)]
        test[arity_includes((lambda a, *args: _), 5)]

    with testset("kwargs"):
        test[required_kwargs(lambda *, a, b, c=42: _) == set(('a', 'b'))]
        test[optional_kwargs(lambda *, a, b, c=42: _) == set(('c'))]
        test[kwargs(lambda *, a, b, c=42: _) == (set(('a', 'b')), set(('c')))]
        test[required_kwargs(lambda a, b, c=42: _) == set()]
        test[optional_kwargs(lambda a, b, c=42: _) == set()]
        test[kwargs(lambda a, b, c=42: _) == (set(), set())]

    with testset("arities and OOP"):
        test[arities(AnalysisTarget) == (0, 0)]  # no args beside the implicit self
        # methods on the class
        test[arities(AnalysisTarget.instmeth) == (2, 2)]  # instance method, not bound to instance
        test[arities(AnalysisTarget.classmeth) == (1, 1)]  # cls is implicit, so just one
        test[arities(AnalysisTarget.staticmeth) == (1, 1)]
        # methods on an instance
        test[arities(target.instmeth) == (1, 1)]  # self is implicit, so just one
        test[arities(target.classmeth) == (1, 1)]
        test[arities(target.staticmeth) == (1, 1)]

    # resolve_bindings: resolve parameter bindings established by a function
    # when it is called with the given args and kwargs.
    #
    # This is useful for memoizers and the like, to prevent spurious cache misses
    # due to Python's flexible argument passing syntax.
    with testset("resolve_bindings"):
        def r(f, *args, **kwargs):
            return tuplify_bindings(resolve_bindings(f, *args, **kwargs))

        def f(a):
            pass  # pragma: no cover, this is here just to be analyzed.
        byposition = r(f, 1)
        byname = r(f, a=1)
        test[the[byposition] == the[byname]]

        def f(a=42):
            pass  # pragma: no cover
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
            pass  # pragma: no cover
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
            pass  # pragma: no cover
        test[r(f, 1, 2, 3, 4, 5) == (("args", (("a", 1), ("b", 2), ("c", 3))),
                                     ("vararg", (4, 5)), ("vararg_name", "args"),
                                     ("kwarg", None), ("kwarg_name", None))]

        # On Pythons < 3.6, there's no guarantee about the ordering of the kwargs.
        # Our analysis machinery preserves the order it gets, but the *input*
        # may already differ from how the invocation of `r` is written in the
        # source code here.
        #
        # So we must allow for arbitrary ordering of the kwargs when checking
        # the result.
        #
        def checkpre36(result, truth):
            args_r, vararg_r, vararg_name_r, kwarg_r, kwarg_name_r = result
            args_t, vararg_t, vararg_name_t, kwarg_t, kwarg_name_t = truth
            couldbe = (args_r == args_t and vararg_r == vararg_t and
                       vararg_name_r == vararg_name_t and kwarg_name_r == kwarg_name_t)
            if not couldbe:
                return False  # pragma: no cover, should only happen if the tests fail.
            name_r, contents_r = kwarg_r
            name_t, contents_t = kwarg_t
            return name_r == name_t and set(contents_r) == set(contents_t)

        def f(a, b, c, **kw):
            pass  # pragma: no cover
        test[checkpre36(the[r(f, 1, 2, 3, d=4, e=5)], (("args", (("a", 1), ("b", 2), ("c", 3))),
                                                       ("vararg", None), ("vararg_name", None),
                                                       ("kwarg", (("d", 4), ("e", 5))), ("kwarg_name", "kw")))]

        def f(a, b, c, *args, **kw):
            pass  # pragma: no cover
        test[checkpre36(the[r(f, 1, 2, 3, 4, 5, d=6, e=7)], (("args", (("a", 1), ("b", 2), ("c", 3))),
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

    with testset("resolve_bindings error cases"):
        def f(a):
            pass  # pragma: no cover
        test_raises[TypeError, resolve_bindings(f, 1, 2)]  # too many args
        test_raises[TypeError, resolve_bindings(f, 1, a=2)]  # same arg assigned twice
        test_raises[TypeError, resolve_bindings(f, 1, b=2)]  # unexpected kwarg

        # The number of missing required positional args affects the error message
        # à la Python 3.6, so let's exercise that part of the code, too.
        test_raises[TypeError, resolve_bindings(f)]  # missing 1 required positional arg
        def g(a, b):
            pass  # pragma: no cover
        test_raises[TypeError, resolve_bindings(g)]  # missing 2 required positional args
        def h(a, b, c):
            pass  # pragma: no cover
        test_raises[TypeError, resolve_bindings(h)]  # missing 3 required positional args

if __name__ == '__main__':  # pragma: no cover
    with session(__file__):
        runtests()
