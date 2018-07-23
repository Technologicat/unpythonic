#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Introduce local bindings. Lispy syntax.

The forms "let" and "letrec" are supported(-ish).

This version uses a lispy syntax. Left-to-right eager evaluation of tuples
in Python allows us to provide sequential assignments.

Core idea of _let() based on StackOverflow answer by divs1210 (2017),
used under the MIT license:
    https://stackoverflow.com/a/44737147
"""

__all__ = ["let", "letrec", "dlet", "dletrec", "blet", "bletrec"]

from unpythonic.misc import immediate

def let(bindings, body):
    """let expression.

    The bindings are independent (do not see each other).

    Parameters:
        bindings: iterable
            (name, value) pairs
        body: function
            One-argument function that takes in the environment.

    Returns:
        Return value of body.

    Example:

        let((('a', 1),
             ('b', 2)),
            lambda e: [e.a, e.b])  # --> [1, 2]

    Bindings must be an iterable even if there is only one pair:

        let((('a', 1),),
            lambda e: e.a)  # --> 1

    A let-over-lambda is also possible:

        from unpythonic.misc import begin
        lc = let((('count', 0),),
                 lambda e: lambda: begin(e.set('count', e.count + 1),
                                         e.count))
        lc()  # --> 1
        lc()  # --> 2
        lc()  # --> 3

    The  lambda e: ...  handles the environment; the rest is the definition.
    """
    return _let(bindings, body)

def letrec(bindings, body):
    """letrec expression.

    Like ``let``, but bindings can see each other.

    A binding may depend on an earlier one:

        letrec((('a', 1),
                ('b', lambda e: e.a + 1)),
               lambda e: e.b)  # --> 2

    DANGER: **any** callable as a value for a binding is interpreted as a
    one-argument function that takes an environment.

    Hence, if you need to define a function (lambda) in a ``letrec``, wrap it
    in a  lambda e: ...  even if it doesn't need the environment, like this:

        letrec((('a', 1),
                ('b', lambda e: e.a + 1),          # just a value, uses env
                ('f', lambda e: lambda x: 42*x)),  # a function, whether or not uses env
               lambda e: e.b * e.f(1))  # --> 84

    Also possible: mutually recursive functions:

        letrec((('evenp', lambda e: lambda x: (x == 0) or  e.oddp(x - 1)),
                ('oddp',  lambda e: lambda x: (x != 0) and e.evenp(x - 1))),
               lambda e: e.evenp(42))  # --> True
    """
    return _let(bindings, body, mode="letrec")

def dlet(bindings):
    """let decorator.

    The environment is passed in by name, as "env". The function can take
    any other arguments as usual.

    For let-over-def; think "let over lambda" in Lisp:

        @dlet((('x', 17),))
        def f(*, env):
            return env.x
        f()  # --> 17

    ``dlet`` provides a local storage that persists across calls:

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
    """letrec decorator.

    Like ``dlet``, but with ``letrec`` instead of ``let``.

        @dletrec((('x', 2),
                  ('y', lambda e: e.x + 3)))
        def bar(a, *, env):
            return a + env.y
        bar(10)  # --> 15
    """
    return _dlet(bindings, mode="letrec")

def blet(bindings):
    """let block, chaining @dlet and @immediate.

        @blet((('x', 9001),))
        def result(*, env):
            return env.x
        print(result)  # 9001
    """
    return _blet(bindings)

def bletrec(bindings):
    """letrec block, chaining @dletrec and @immediate."""
    return _blet(bindings, mode="letrec")

class _env:
    """Environment; used as storage for local bindings."""

    # TODO: use << for set!
    def set(self, k, v):
        """Convenience method to allow assignment in expression contexts.

        For extra convenience, return the assigned value.

        DANGER: avoid the name k="set"; it will happily shadow this method,
        because instance attributes are seen before class attributes."""
        setattr(self, k, v)
        return v

def _let(bindings, body, *, env=None, mode="let"):
    assert mode in ("let", "letrec")

    if not bindings:
        # decorators need just the final env; else run body now
        return env if body is None else body(env)

    env = env or _env()
    (k, v), *more = bindings

    if mode == "letrec" and callable(v):
        v = v(env)

    setattr(env, k, v)

    return _let(more, body, env=env, mode=mode)

def _dlet(bindings, mode="let"):  # let and letrec decorator factory
    def deco(body):
        env = _let(bindings, body=None, mode=mode)  # set up env, don't run yet
        # TODO: functools.wraps? wrapt?
        def decorated(*args, **kwargs):
            kwargs_with_env = kwargs.copy()
            kwargs_with_env["env"] = env
            return body(*args, **kwargs_with_env)
        return decorated
    return deco

def _blet(bindings, mode="let"):
    """let block, chaining @_dlet and @immediate.

        @_blet(x=17, y=23)
        def result(env=None):
            print(env.x, env.y)
            return env.x + env.y
        print(result)  # 40

        # if the return value is of no interest:
        @_blet(s="hello")
        def _(env=None):
            print(env.s)
    """
    dlet_deco = _dlet(bindings, mode)
    def deco(body):
        return immediate(dlet_deco(body))
    return deco

def test():
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
    from unpythonic.misc import begin
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

    print("All tests passed")

if __name__ == '__main__':
    test()
