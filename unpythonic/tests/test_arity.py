# -*- coding: utf-8 -*-

from ..syntax import macros, test, test_raises, the  # noqa: F401
from ..test.fixtures import session, testset

import sys

from ..arity import (arities, arity_includes,
                     required_kwargs, optional_kwargs, kwargs,
                     resolve_bindings, tuplify_bindings,
                     getfunc, UnknownArity)

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
        test[r(f) == (("a", 42),)]
        test[r(f, 17) == (("a", 17),)]
        test[r(f, a=23) == (("a", 23),)]

        def f(a, b, c):
            pass  # pragma: no cover
        test[r(f, 1, 2, 3) == (("a", 1), ("b", 2), ("c", 3))]
        test[r(f, a=1, b=2, c=3) == (("a", 1), ("b", 2), ("c", 3))]
        test[r(f, 1, 2, c=3) == (("a", 1), ("b", 2), ("c", 3))]
        test[r(f, 1, c=3, b=2) == (("a", 1), ("b", 2), ("c", 3))]
        test[r(f, c=3, b=2, a=1) == (("a", 1), ("b", 2), ("c", 3))]

        def f(a, b, c, *args):
            pass  # pragma: no cover
        test[r(f, 1, 2, 3, 4, 5) == (('a', 1), ('b', 2), ('c', 3),
                                     ('args', (4, 5)))]

        def f(a, b, c, **kw):
            pass
        test[r(f, 1, 2, 3, d=4, e=5) == (('a', 1), ('b', 2), ('c', 3),
                                         ('kw', (('d', 4), ('e', 5))))]

        def f(a, b, c, *args, **kw):
            pass
        test[r(f, 1, 2, 3, 4, 5, d=6, e=7) == (('a', 1), ('b', 2), ('c', 3),
                                               ('args', (4, 5)),
                                               ('kw', (('d', 6), ('e', 7))))]

    with testset("resolve_bindings error cases"):
        def f(a):
            pass  # pragma: no cover
        test_raises[TypeError, resolve_bindings(f, 1, 2)]  # too many args
        test_raises[TypeError, resolve_bindings(f, 1, a=2)]  # same arg assigned twice
        test_raises[TypeError, resolve_bindings(f, 1, b=2)]  # unexpected kwarg

if __name__ == '__main__':  # pragma: no cover
    with session(__file__):
        runtests()
