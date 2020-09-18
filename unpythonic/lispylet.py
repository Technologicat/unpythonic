# -*- coding: utf-8 -*-
"""Introduce local bindings. Lispy syntax."""

__all__ = ["let", "letrec", "dlet", "dletrec", "blet", "bletrec"]

from functools import wraps

from .misc import call
from .env import env as _envcls
from .arity import arity_includes, UnknownArity

def let(bindings, body):
    """``let`` expression.

    In ``let``, the bindings are independent (do not see each other); only
    the body may refer to the bindings.

    Order-preserving list uniqifier::

        u = lambda lst: let((("seen", set()),),
                            lambda e:
                              [e.seen.add(x) or x for x in lst if x not in e.seen])

    Bindings must be a sequence even if there is just one binding.

    A lambda using a locally defined lambda as a helper::

        g = let((("square", lambda y:
                              y**2),),
                lambda e:
                  lambda x: 42 * e.square(x))
        g(10)  # --> 4200

    Unlike in ``letrec``, no ``lambda e: ...`` is needed for ``square``.
    Because in ``let``, the bindings do not see the environment, there is
    no risk of misunderstanding the lambda in the environment initialization
    procedure.

    Composability. As Lisp programmers know, the second example is subtly
    different from::

        g = lambda x: let((("square", lambda y:
                                        y**2),),
                          lambda e:
                            42 * e.square(x))

    We only moved the ``lambda x:``. In the original version, the let expression
    runs just once, when ``g`` is defined, whereas in this one, it re-runs
    whenever ``g`` is called.

    *Let over lambda*. The inner lambda is the definition of the function ``counter``::

        from unpythonic.seq import begin
        counter = let((("x", 0),),
                      lambda e:
                        lambda:
                          begin(e.set("x", e.x + 1),
                                e.x))
        counter()  # --> 1
        counter()  # --> 2
        counter()  # --> 3

    Parameters:
        `bindings`: sequence of `(name, value)` pairs
            `name`: str

            `value`: anything

            Each argument name is bound to its value. Unlike in ``letrec``,
            no ``lambda e: ...`` is needed, as the environment is not seen
            by the bindings.

        `body`: function
            One-argument function to run, taking an `env` instance that
            contains the ``let`` bindings as its attributes. The environment
            is passed as the first positional argument.

            If you need to pass in more stuff:

                - Use the closure property (free variables, lexical scoping).
                - Make a nested lambda, like above. Only the outermost one is
                  "eaten" by the environment initialization procedure.

    Returns:
        The return value of ``body``.
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

    If your value is callable, wrap it in a ``lambda e: ...``
    even if it doesn't need the environment, like this::

        letrec((('a', 1),          # just a value, doesn't use env
                ('b', lambda e:
                        e.a + 1),  # just a value, uses env
                ('f', lambda e:
                        lambda x:  # callable, whether or not uses env
                          42*x)),
               lambda e:
                 e.b * e.f(1))  # --> 84

    A callable value may depend on **any** binding, also later ones. This allows
    mutually recursive functions::

        letrec((('evenp', lambda e:
                            lambda x:
                              (x == 0) or  e.oddp(x - 1)),
                ('oddp',  lambda e:
                            lambda x:
                              (x != 0) and e.evenp(x - 1))),
               lambda e:
                 e.evenp(42))  # --> True

    Order-preserving list uniqifier::

        from unpythonic.seq import begin
        u = lambda lst: letrec((("seen", set()),
                                ("see", lambda e:
                                          lambda x:
                                            begin(e.seen.add(x),
                                                  x))),
                               lambda e:
                                 [e.see(x) for x in lst if x not in e.seen])
        L = [1, 1, 3, 1, 3, 2, 3, 2, 2, 2, 4, 4, 1, 2, 3]
        print(u(L))  # [1, 3, 2, 4]

    Parameters:
        `bindings`: sequence of `(name, value)` pairs

            `name`: str
                The name to which the value will be bound.

            `value`: anything
                Either a simple value (non-callable, doesn't use the environment),
                or an expression of the form ``lambda e: valexpr``, providing
                access to the environment as ``e``.

                If ``valexpr`` itself is callable, the value **must** have the
                ``lambda e: ...`` wrapper to prevent any misunderstandings in the
                environment initialization procedure.

        `body`: function
            Like in ``let``.

    Returns:
        The return value of ``body``.
    """
    return _let(bindings, body, mode="letrec")

def dlet(bindings):
    """``let`` decorator.

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

    The named argument `env` is an env instance that contains the let bindings;
    all other args and kwargs are passed through.
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

    This chains ``@dlet`` and ``@call``::

        @blet((('x', 9001),))
        def result(*, env):
            return env.x
        print(result)  # --> 9001
    """
    return _blet(bindings)

def bletrec(bindings):
    """``letrec`` block.

    This chains ``@dletrec`` and ``@call``."""
    return _blet(bindings, mode="letrec")

# Core idea based on StackOverflow answer by divs1210 (2017),
# used under the MIT license.  https://stackoverflow.com/a/44737147
def _let(bindings, body, *, env=None, mode="let"):
    assert mode in ("let", "letrec")

    env = env or _envcls()

    if not bindings:
        env.finalize()
        if body:
            if not callable(body):
                raise TypeError("Expected callable body, got {} with value {}".format(type(body), repr(body)))
            try:
                if not arity_includes(body, 1):
                    raise TypeError("Arity mismatch; body must allow arity 1, to take in the environment.")
            except UnknownArity:  # pragma: no cover; well, we tried!
                pass
        # decorators need just the final env; else run body now
        return env if body is None else body(env)

    (k, v), *more = bindings
    if k in env:
        raise AttributeError("Cannot rebind the same name {} in a {} initializer list".format(repr(k), mode))
    if mode == "letrec" and callable(v):
        try:
            if not arity_includes(v, 1):
                raise TypeError("Arity mismatch; callable value must allow arity 1, to take in the environment.")
        except UnknownArity:  # pragma: no cover; well, we tried!
            pass
        v = v(env)
    env[k] = v
    return _let(more, body, env=env, mode=mode)  # loop

# _envname is for co-operation with the dlet macro.
def _dlet(bindings, mode="let", _envname="env"):  # let and letrec decorator factory
    def deco(body):
        env = _let(bindings, body=None, mode=mode)  # set up env, don't run yet
        @wraps(body)
        def withenv(*args, **kwargs):
            kwargs_with_env = kwargs.copy()
            kwargs_with_env[_envname] = env
            return body(*args, **kwargs_with_env)
        return withenv
    return deco

def _blet(bindings, mode="let", _envname="env"):
    dlet_deco = _dlet(bindings, mode, _envname)
    def deco(body):
        return call(dlet_deco(body))
    return deco
