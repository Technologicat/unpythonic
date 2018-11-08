# -*- coding: utf-8 -*-

from ..arity import arities, required_kwargs, optional_kwargs, kwargs

def test():
    _ = None  # just some no-op value
    infty = float("+inf")
    items = (((lambda a: _),                       (1, 1)),
             ((lambda a, b: _),                    (2, 2)),
             ((lambda a, b, c, *args: _),          (3, infty)),
             ((lambda *args: _),                   (0, infty)),
             ((lambda **kwargs: _),                (0, 0)),
             ((lambda *args, **kwargs: _),         (0, infty)),
             ((lambda a, b, *, c: _),              (2, 2)),
             ((lambda *, a: _),                    (0, 0)),
             ((lambda a, b, *arg, c, **kwargs: _), (2, infty)),
             ((lambda a, b=42: _),                 (1, 2)))
    for f, answer in items:
        assert arities(f) == answer

    assert required_kwargs(lambda *, a, b, c=42: _) == set(('a', 'b'))
    assert optional_kwargs(lambda *, a, b, c=42: _) == set(('c'))
    assert kwargs(lambda *, a, b, c=42: _) == (set(('a', 'b')), set(('c')))
    assert required_kwargs(lambda a, b, c=42: _) == set()
    assert optional_kwargs(lambda a, b, c=42: _) == set()
    assert kwargs(lambda a, b, c=42: _) == (set(), set())

    # OOP
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
    assert arities(A) == (0, 0)  # no args beside the implicit self
    # methods on the class
    assert arities(A.meth) == (2, 2)
    assert arities(A.classmeth) == (1, 1)
    assert arities(A.staticmeth) == (1, 1)
    # methods on an instance
    a = A()
    assert arities(a.meth) == (1, 1)  # self is implicit, so just one
    # class and static methods are always unbound
    assert arities(a.classmeth) == (1, 1)
    assert arities(a.staticmeth) == (1, 1)

    print("All tests PASSED")

if __name__ == '__main__':
    test()
