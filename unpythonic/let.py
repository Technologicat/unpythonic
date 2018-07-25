#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Introduce local bindings. Pythonic syntax."""

__all__ = ["let", "letrec", "dlet", "dletrec", "blet", "bletrec"]

from functools import wraps

from unpythonic.misc import immediate
from unpythonic.letenv import env as _env

def let(body, **bindings):
    """``let`` expression.

    The bindings are independent (do not see each other); only the body may
    refer to the bindings. Examples::

        # order-preserving list uniqifier
        u = lambda lst: let(seen=set(),
                            body=lambda e: [e.seen.add(x) or x for x in lst if x not in e.seen])

        # a lambda using a locally defined lambda as a helper
        g = let(square=lambda y: y**2,
                body=lambda e: lambda x: 42 * e.square(x))
        g(10)  # --> 4200

    Composability. As Lisp programmers know, the second example is subtly
    different from::

        g = lambda x: let(square=lambda y: y**2,
                          body=lambda e: 42 * e.square(x))

    (We only moved the ``lambda x:``.) In the original version, the let expression
    runs just once, when ``g`` is defined, whereas in this one, it re-runs
    whenever ``g`` is called.

    *Let over lambda*. The inner lambda is the definition of the function ``counter``::

        from unpythonic.misc import begin
        counter = let(x=0,
                      body=lambda e: lambda: begin(e.set("x", e.x + 1),
                                                   e.x))
        counter()  # --> 1
        counter()  # --> 2
        counter()  # --> 3

    Parameters:
        `body`: function
            One-argument function to run, taking an `env` instance that
            contains the "let" bindings as its attributes.

            To pass in more stuff:

                - Use the closure property (free variables, lexical scoping)
                - Make a nested lambda; only the outermost one is implicitly
                  called with env as its only argument.

        Everything else: ``let`` bindings; each argument name is bound to its value.
        No ``lambda e: ...`` is needed, as the environment is not seen by the bindings.

    Returns:
        The value returned by body.
    """
    return _let("let", body, **bindings)

def letrec(body, **bindings):
    """``letrec`` expression.

    Like ``let``, but bindings can see each other.

    The bindings must be wrapped with a ``lambda e: ...``, to delay their evaluation
    until the environment instance has been created (and can thus be supplied
    to them, just before the body starts).

    The value inside each ``lambda e: ...`` wrapper **must** be either:

        - an expression that **does not** use ``e``, just like in a regular ``let``, or
        - a lambda, which may use ``e``. (Mutually recursive function example below.)

    Caveats:
        - When the arguments to the ``letrec`` are evaluated (eagerly, by Python),
          the environment has not yet been created. The ``lambda e: ...``
          works around this.

        - Initialization of the bindings occurs **in an arbitrary order**,
          because of the kwargs mechanism and storage as a dictionary.
          Hence the following **does not** work::

             x = letrec(a=lambda e: 1
                        b=lambda e: e.a + 1,
                        body=lambda e: e.b)

          because trying to reference ``env.a`` on the RHS of ``b`` may get either the
          ``lambda e: ...``, or the value ``1``, depending on whether the binding ``a``
          has been initialized at that point or not.

          If you need left-to-right ordering, use the ``unpythonic.lispylet``
          module instead.

    The main use case of this ``letrec`` is mutually recursive functions::

        t = letrec(evenp=lambda e: lambda x: (x == 0) or e.oddp(x - 1),
                   oddp=lambda e: lambda x: (x != 0) and e.evenp(x - 1),
                   body=lambda e: e.evenp(42))

    Functions may use any bindings from ``e``. Order-preserving list uniqifier::

        from unpythonic.misc import begin
        u = lambda lst: letrec(seen=lambda e: set(),
                               see=lambda e: lambda x: begin(e.seen.add(x), x),
                               body=lambda e: [e.see(x) for x in lst if x not in e.seen])
        L = [1, 1, 3, 1, 3, 2, 3, 2, 2, 2, 4, 4, 1, 2, 3]
        print(u(L))  # [1, 3, 2, 4]

    This works, because ``see`` is a function, so ``e.seen`` doesn't have to
    yet exist at the time the definition of ``see`` is evaluated.

    Parameters:
        `body`: like in ``let``

        Everything else: ``letrec`` bindings, as one-argument functions.
        The argument is the environment.

    Returns:
        The value returned by body.
    """
    return _let("letrec", body, **bindings)

def dlet(**bindings):
    """``let`` decorator.

    For let-over-def; think *let over lambda* in Lisp::

        @dlet(y=23, z=42)
        def foo(x, *, env=None):  # env is filled in by the decorator
            print(x, env.y, env.z)
        foo(17)  # --> "17, 23, 42"

    ``dlet`` provides a local storage that persists across calls::

        @dlet(count=0)
        def counter(*, env=None):
            env.count += 1
            return env.count
        counter()  # --> 1
        counter()  # --> 2
        counter()  # --> 3

    The named argument `env` is an env instance that contains the let bindings;
    all other args and kwargs are passed through.
    """
    return _dlet("let", **bindings)

def dletrec(**bindings):
    """``letrec`` decorator.

    Like ``dlet``, but with ``letrec`` instead of ``let``.
    """
    return _dlet("letrec", **bindings)

def blet(**bindings):
    """``let`` block.

    This chains ``@dlet`` and ``@immediate``::

        @blet(x=17, y=23)
        def result(*, env=None):
            print(env.x, env.y)
            return env.x + env.y
        print(result)  # 40

        # if the return value is of no interest:
        @blet(s="hello")
        def _(*, env=None):
            print(env.s)
    """
    return _blet("let", **bindings)

def bletrec(**bindings):
    """``letrec`` block.

    This chains ``@dletrec`` and ``@immediate``."""
    return _blet("letrec", **bindings)

def _let(mode, body, **bindings):
    assert mode in ("let", "letrec")
    env = _env(**bindings)
    if mode == "letrec":  # supply the environment instance to the letrec bindings.
        for k in env:
            env[k] = env[k](env)
    # decorators need just the final env; else run body now
    return env if body is None else body(env)

# decorator factory: almost as fun as macros?
def _dlet(mode, **bindings):
    assert mode in ("let", "letrec")
    def deco(body):
        # evaluate env only once, when the function def runs
        # (to preserve state between calls to the decorated function)
        env = _let(mode, body=None, **bindings)
        @wraps(body)
        def decorated(*args, **kwargs):
            kwargs_with_env = kwargs.copy()
            kwargs_with_env["env"] = env
            return body(*args, **kwargs_with_env)
        return decorated
    return deco

def _blet(mode, **bindings):
    dlet_deco = _dlet(mode, **bindings)
    def deco(body):
        return immediate(dlet_deco(body))
    return deco

def test():
    from unpythonic.misc import begin

    # order-preserving list uniqifier
    def uniqify_test():
        def f(lst):  # classical solution
            seen = set()
            def see(x):
                seen.add(x)
                return x
            return [see(x) for x in lst if x not in seen]

        # one-liner
        f2 = lambda lst: (lambda seen: [seen.add(x) or x for x in lst if x not in seen])(seen=set())

        # context manager only
        def f3(lst):
            with _env(seen = set()) as myenv:
                return [myenv.seen.add(x) or x for x in lst if x not in myenv.seen]
            # myenv still lives due to Python's scoping rules.
            # This is why we provide a separate let construct
            # and not just the env class.

        f4 = lambda lst: let(seen=set(),
                             body=lambda e: [e.seen.add(x) or x for x in lst if x not in e.seen])

        f5 = lambda lst: letrec(seen=lambda e: set(),
                                see=lambda e: lambda x: begin(e.seen.add(x), x),
                                body=lambda e: [e.see(x) for x in lst if x not in e.seen])

        L = [1, 1, 3, 1, 3, 2, 3, 2, 2, 2, 4, 4, 1, 2, 3]

        # Call each implementation twice to make sure that a fresh `seen`
        # is indeed created at each call.
        assert f(L) == f(L)
        assert f2(L) == f2(L)
        assert f3(L) == f3(L)
        assert f4(L) == f4(L)
        assert f5(L) == f5(L)

        assert f(L) == f2(L) == f3(L) == f4(L) == f5(L) == [1, 3, 2, 4]

    uniqify_test()

    @dlet(y=23)
    def foo(x, *, env):  # the named argument env contains the let bindings
        return x + env.y
    assert foo(17) == 40

    @dlet(x=5)
    def bar(*, env):
        assert env.x == 5

        @dlet(x=42)
        def baz(*, env):  # this env shadows the outer env
            assert env.x == 42
        baz()

        assert env.x == 5
    bar()

    @immediate
    @dlet(x=5)
    def _(*, env):  # this is now the let block, run immediately
        assert env.x == 5

        @immediate
        @dlet(x = 42)
        def _(*, env):
            assert env.x == 42

        assert env.x == 5

    # same effect
    @blet(x=5)
    def _(*, env):
        assert env.x == 5

        @blet(x = 42)
        def _(*, env):
            assert env.x == 42

        assert env.x == 5

    # Let over lambda. The inner lambda is the definition of the function f.
    counter = let(x=0,
                  body=lambda e: lambda: begin(e.set("x", e.x + 1),
                                               e.x))
    counter()
    counter()
    assert counter() == 3

    # https://docs.racket-lang.org/reference/let.html
    t = letrec(evenp=lambda e: lambda x: (x == 0) or e.oddp(x - 1),
               oddp=lambda e: lambda x: (x != 0) and e.evenp(x - 1),
               body=lambda e: e.evenp(42))
    assert t is True

    @dletrec(evenp=lambda e: lambda x: (x == 0) or e.oddp(x - 1),
             oddp=lambda e: lambda x: (x != 0) and e.evenp(x - 1))
    def is_even(x, *, env):
        return env.evenp(x)
    assert is_even(23) is False

    @bletrec(evenp=lambda e: lambda x: (x == 0) or e.oddp(x - 1),
             oddp=lambda e: lambda x: (x != 0) and e.evenp(x - 1))
    def result(*, env):
        return env.evenp(23)
    assert result is False

    try:
        let(x=0,
            body=lambda e: e.set('y', 3))  # error, y is not defined
    except AttributeError as err:
        pass
    else:
        assert False

    print("All tests PASSED")

if __name__ == '__main__':
    test()
