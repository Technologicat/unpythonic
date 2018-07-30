#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Introduce local bindings. Lispy syntax."""

__all__ = ["let", "letrec", "dlet", "dletrec", "blet", "bletrec"]

from functools import wraps

from unpythonic.misc import immediate
from unpythonic.env import env as _envcls

def let(bindings, body):
    """``let`` expression.

    The bindings are independent (do not see each other); only the body may
    refer to the bindings.

    Parameters:
        bindings: tuple of (name, value) pairs
            name: str
            value: anything
        body: function
            One-argument function that takes in the environment.

    Returns:
        Return value of body.

    Example::

        let((('a', 1),
             ('b', 2)),
            lambda e: [e.a, e.b])  # --> [1, 2]

    Bindings must be an iterable even if there is only one pair::

        let((('a', 1),),
            lambda e: e.a)  # --> 1

    *Let over lambda*. The inner lambda is the definition of the function ``counter``::

        from unpythonic.misc import begin
        counter = let((('x', 0),),
                      lambda e: lambda: begin(e.set('x', e.x + 1),
                                              e.x))
        counter()  # --> 1
        counter()  # --> 2
        counter()  # --> 3
    """
    return _let(bindings, body)

def letrec(bindings, body):
    """``letrec`` expression.

    Like ``let``, but bindings can see each other. To make a binding use the
    value of an earlier one, use a ``lambda e: ...``::

        letrec((('a', 1),
                ('b', lambda e: e.a + 1)),
               lambda e: e.b)  # --> 2

    Each RHS is evaluated just once, and the result is bound to the name on
    the LHS. So even if 'a' is ``e.set()`` to a different value later,
    'b' **won't** be updated.

    DANGER:
        **any** callable as a value for a binding is interpreted as a
        one-argument function that takes an environment.

    If you need to define a function (lambda) in a ``letrec``, wrap it in a
    ``lambda e: ...``  even if it doesn't need the environment, like this::

        letrec((('a', 1),
                ('b', lambda e: e.a + 1),          # just a value, uses env
                ('f', lambda e: lambda x: 42*x)),  # function, whether or not uses env
               lambda e: e.b * e.f(1))  # --> 84

    Order-preserving list uniqifier::

        from unpythonic.misc import begin
        u = lambda lst: letrec((("seen", set()),
                                ("see", lambda e: lambda x: begin(e.seen.add(x), x))),
                               lambda e: [e.see(x) for x in lst if x not in e.seen])
        L = [1, 1, 3, 1, 3, 2, 3, 2, 2, 2, 4, 4, 1, 2, 3]
        print(u(L))  # [1, 3, 2, 4]

    Mutually recursive functions are also possible:

        letrec((('evenp', lambda e: lambda x: (x == 0) or  e.oddp(x - 1)),
                ('oddp',  lambda e: lambda x: (x != 0) and e.evenp(x - 1))),
               lambda e: e.evenp(42))  # --> True
    """
    return _let(bindings, body, mode="letrec")

def dlet(bindings):
    """``let`` decorator.

    The environment is passed in by name, as ``env``. The function can take
    any other arguments as usual.

    For let-over-def; think *let over lambda* in Lisp::

        @dlet((('x', 17),))
        def f(*, env):
            return env.x
        f()  # --> 17

    ``dlet`` provides a local storage that persists across calls::

        @dlet((('count', 0),))
        def counter(*, env):
            env.count += 1
            return env.count
        counter()  # --> 1
        counter()  # --> 2
        counter()  # --> 3
    """
    return _dlet(bindings)

def dletrec(bindings):
    """``letrec`` decorator.

    Like ``dlet``, but with ``letrec`` instead of ``let``::

        @dletrec((('x', 2),
                  ('y', lambda e: e.x + 3)))
        def bar(a, *, env):
            return a + env.y
        bar(10)  # --> 15
    """
    return _dlet(bindings, mode="letrec")

def blet(bindings):
    """``let`` block.

    This chains ``@dlet`` and ``@immediate``::

        @blet((('x', 9001),))
        def result(*, env):
            return env.x
            print(result)  # --> 9001
    """
    return _blet(bindings)

def bletrec(bindings):
    """``letrec`` block.

    This chains ``@dletrec`` and ``@immediate``."""
    return _blet(bindings, mode="letrec")

# Core idea based on StackOverflow answer by divs1210 (2017),
# used under the MIT license.  https://stackoverflow.com/a/44737147
def _let(bindings, body, *, env=None, mode="let"):
    assert mode in ("let", "letrec")

    env = env or _envcls()

    if not bindings:
        env.finalize()
        # decorators need just the final env; else run body now
        return env if body is None else body(env)

    (k, v), *more = bindings
    if mode == "letrec" and callable(v):
        v = v(env)
    setattr(env, k, v)
    return _let(more, body, env=env, mode=mode)

def _dlet(bindings, mode="let"):  # let and letrec decorator factory
    def deco(body):
        env = _let(bindings, body=None, mode=mode)  # set up env, don't run yet
        @wraps(body)
        def decorated(*args, **kwargs):
            kwargs_with_env = kwargs.copy()
            kwargs_with_env["env"] = env
            return body(*args, **kwargs_with_env)
        return decorated
    return deco

def _blet(bindings, mode="let"):
    dlet_deco = _dlet(bindings, mode)
    def deco(body):
        return immediate(dlet_deco(body))
    return deco

def test():
    from unpythonic.misc import begin

    x = let((('a', 1),
             ('b', 2)),
            lambda o: o.a + o.b)
    assert x == 3

    x = letrec((('a', 1),
                ('b', lambda o: o.a + 2)),  # hence, b = 3
               lambda o: o.a + o.b)
    assert x == 4

    t = letrec((('evenp', lambda o: lambda x: (x == 0) or  o.oddp(x - 1)),
                ('oddp',  lambda o: lambda x: (x != 0) and o.evenp(x - 1))),
               lambda o: o.evenp(42))
    assert t == True

    f = lambda lst: letrec((("seen", set()),
                            ("see", lambda e: lambda x: begin(e.seen.add(x), x))),
                           lambda e: [e.see(x) for x in lst if x not in e.seen])
    L = [1, 1, 3, 1, 3, 2, 3, 2, 2, 2, 4, 4, 1, 2, 3]
    assert f(L) == [1, 3, 2, 4]

    @dlet((('x', 17),))
    def foo(*, env):
        return env.x
    assert foo() == 17

    @dletrec((('x', 2),
              ('y', lambda o: o.x + 3)))
    def bar(a, *, env):
        return a + env.y
    assert bar(10) == 15

    @dlet((('count', 0),))
    def counter(*, env):
        env.count += 1
        return env.count
    counter()
    counter()
    assert counter() == 3

    # let-over-lambda
    lc = let((('count', 0),),
             lambda o: lambda: begin(o.set('count', o.count + 1),
                                     o.count))
    lc()
    lc()
    assert lc() == 3

    @blet((('x', 9001),))
    def result(*, env):
        return env.x
    assert result == 9001

    @bletrec((('evenp', lambda e: lambda x: (x == 0) or  e.oddp(x - 1)),
              ('oddp',  lambda e: lambda x: (x != 0) and e.evenp(x - 1)),))
    def result(*, env):
        return env.evenp(42)
    assert result is True

    try:
        let((('x', 0),),
            lambda e: e.set('y', 3))  # error, y is not defined
    except AttributeError:
        pass
    else:
        assert False

    try:
        @blet((('x', 1),))
        def error1(*, env):
            env.y = 2  # cannot add new bindings to a let environment
    except AttributeError as err:
        pass
    else:
        assert False

    print("All tests PASSED")

if __name__ == '__main__':
    test()
