# -*- coding: utf-8 -*-
"""Introduce local bindings. Pythonic syntax."""

__all__ = ["let", "letrec", "dlet", "dletrec", "blet", "bletrec"]

from functools import wraps

from .arity import arity_includes, UnknownArity
from .env import env as _envcls
from .funutil import call

def let(body, **bindings):
    """``let`` expression.

    In ``let``, the bindings are independent (do not see each other); only
    the body may refer to the bindings.

    Order-preserving list uniqifier::

        u = lambda lst: let(seen=set(),
                            body=lambda e:
                                   [e.seen.add(x) or x for x in lst if x not in e.seen])

    A lambda using a locally defined lambda as a helper::

        g = let(square=lambda y:
                         y**2,
                body=lambda e:
                         lambda x: 42 * e.square(x))
        g(10)  # --> 4200

    Unlike in ``letrec``, no ``lambda e: ...`` is needed for ``square``.
    Because in ``let``, the bindings do not see the environment, there is
    no risk of misunderstanding the lambda in the environment initialization
    procedure.

    Composability. As Lisp programmers know, the second example is subtly
    different from::

        g = lambda x: let(square=lambda y:
                                   y**2,
                          body=lambda e:
                                   42 * e.square(x))

    We only moved the ``lambda x:``. In the original version, the let expression
    runs just once, when ``g`` is defined, whereas in this one, it re-runs
    whenever ``g`` is called.

    *Let over lambda*. The inner lambda is the definition of the function ``counter``::

        from unpythonic.seq import begin
        counter = let(x=0,
                      body=lambda e:
                             lambda:
                               begin(e.set("x", e.x + 1),
                                     e.x))
        counter()  # --> 1
        counter()  # --> 2
        counter()  # --> 3

    Parameters:
        `body`: function
            One-argument function to run, taking an `env` instance that
            contains the ``let`` bindings as its attributes. The environment
            is passed as the first positional argument.

            If you need to pass in more stuff:

                - Use the closure property (free variables, lexical scoping).
                - Make a nested lambda, like above. Only the outermost one is
                  "eaten" by the environment initialization procedure.

        `any other named arguments`: ``let`` bindings
            Each argument name is bound to its value. Unlike in ``letrec``,
            no ``lambda e: ...`` is needed, as the environment is not seen
            by the bindings.

    Returns:
        The return value of ``body``.
    """
    return _let("let", body, **bindings)

def letrec(body, **bindings):
    """``letrec`` expression.

    Like ``let``, but bindings can see each other. To make a binding use the
    value of an earlier one, use a ``lambda e: ...``::

        x = letrec(a=1,
                   b=lambda e: e.a + 1,
                   body=lambda e: e.b)  # --> 2

    Each RHS is evaluated just once, and the result is bound to the name on
    the LHS. So even if 'a' is ``e.set()`` to a different value later,
    'b' **won't** be updated.

    If your value is callable, wrap it in a ``lambda e: ...``
    even if it doesn't need the environment, like this::

        letrec(a=1,              # just a value, doesn't use env
               b=lambda e:
                      e.a + 1,   # just a value, uses env
               f=lambda e:
                      lambda x:  # callable, whether or not uses env
                        42*x,
               body=lambda e:
                      e.b * e.f(1))  # --> 84

    Simple values (non-callables) may depend on earlier definitions
    in the same letrec.

    A callable value may depend on **any** binding, also later ones. This allows
    mutually recursive functions::

        t = letrec(evenp=lambda e:
                           lambda x:
                             (x == 0) or e.oddp(x - 1),
                   oddp=lambda e:
                           lambda x:
                             (x != 0) and e.evenp(x - 1),
                   body=lambda e:
                           e.evenp(42))

    Order-preserving list uniqifier::

        from unpythonic.seq import begin
        u = lambda lst: letrec(seen=set(),
                               see=lambda e:
                                      lambda x:
                                        begin(e.seen.add(x),
                                              x),
                               body=lambda e:
                                      [e.see(x) for x in lst if x not in e.seen])
        L = [1, 1, 3, 1, 3, 2, 3, 2, 2, 2, 4, 4, 1, 2, 3]
        print(u(L))  # [1, 3, 2, 4]

    Note that ``see`` is a callable. Hence, strictly speaking it doesn't matter
    if ``e.seen`` exists when the *definition* of ``see`` is evaluated; it only
    has to exist when ``e.see(x)`` is *called*.

    Parameters:
        `body`: function
            Like in ``let``.

        `any other named arguments`: ``let`` bindings
            The RHS of each binding is either a simple value (non-callable,
            doesn't use the environment), or an expression of the form
            ``lambda e: valexpr``, providing access to the environment as ``e``.

            If ``valexpr`` itself is callable, the RHS of its binding **must**
            have the ``lambda e: ...`` wrapper to prevent any misunderstandings
            in the environment initialization procedure.

    Returns:
        The return value of ``body``.
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

    Like ``dlet``, but with ``letrec`` instead of ``let``::

        @dletrec(x=2,
                 y=lambda e: e.x + 3)
        def bar(a, *, env):
            return a + env.y
        bar(10)  # --> 15
    """
    return _dlet("letrec", **bindings)

def blet(**bindings):
    """``let`` block.

    This chains ``@dlet`` and ``@call``::

        @blet(x=9001)
        def result(*, env):
            return env.x
        print(result)  # --> 9001
    """
    return _blet("let", **bindings)

def bletrec(**bindings):
    """``letrec`` block.

    This chains ``@dletrec`` and ``@call``."""
    return _blet("letrec", **bindings)

def _let(mode, body, **bindings):
    assert mode in ("let", "letrec")
    # Important for Python 3.6+, which preserves ordering of kwargs (PEP 468):
    #
    # Bind names sequentially to catch invalid reference errors. In letrec,
    # a simple value (non-callable) can only refer to bindings above it.
    #
    # If we bind the names one by one - calling each value's  lambda e: ...
    # wrapper when that name is bound, any reference to a yet unbound name
    # will alert the user by raising an AttributeError.
    #
    # If we instead initialize as _envcls(**bindings), and then call the
    # wrappers in a second pass, we lose this validation, because all names
    # are then already bound when the wrappers are called.
    env = _envcls()
    for k, v in bindings.items():
        if k in env:
            # Can't happen when used via the public API, because Python itself
            # blocks passing the same argument by name twice.
            raise AttributeError(f"Cannot rebind the same name {repr(k)} in a {mode} initializer list")  # pragma: no cover
        if mode == "letrec" and callable(v):
            try:
                if not arity_includes(v, 1):
                    raise TypeError("Arity mismatch; callable value must allow arity 1, to take in the environment.")
            except UnknownArity:  # well, we tried!  # pragma: no cover
                pass
            v = v(env)
        env[k] = v
    # decorators need just the final env; else run body now
    env.finalize()
    if body:
        if not callable(body):
            raise TypeError(f"Expected callable body, got {type(body)} with value {repr(body)}")
        try:
            if not arity_includes(body, 1):
                raise TypeError("Arity mismatch; body must allow arity 1, to take in the environment.")
        except UnknownArity:  # well, we tried!  # pragma: no cover
            pass
    return env if body is None else body(env)

# decorator factory: almost as fun as macros?
# _envname is for co-operation with the dlet macro.
def _dlet(mode, _envname="env", **bindings):
    def deco(body):
        # evaluate env only once, when the function def runs
        # (to preserve state between calls to the decorated function)
        env = _let(mode, body=None, **bindings)
        @wraps(body)
        def withenv(*args, **kwargs):
            kwargs_with_env = kwargs.copy()
            kwargs_with_env[_envname] = env
            return body(*args, **kwargs_with_env)
        return withenv
    return deco

def _blet(mode, _envname="env", **bindings):
    dlet_deco = _dlet(mode, _envname, **bindings)
    def deco(body):
        return call(dlet_deco(body))
    return deco
