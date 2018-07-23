#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Introduce local bindings. Pythonic syntax."""

from unpythonic.misc import immediate

class env:
    """Bunch with context manager, iterator and subscripting support.

    Iteration and subscripting just expose the underlying dict.

    Also works as a bare bunch.

    Usage:
        # with context manager:
        with env(x = 0) as myenv:
            print(myenv.x)
        # DANGER: myenv still exists due to Python's scoping rules.

        # bare bunch:
        myenv2 = env(s="hello", orange="fruit", answer=42)
        print(myenv2.s)
        print(myenv2)

        # iteration and subscripting:
        names = [k for k in myenv2]

        for k,v in myenv2.items():
            print("Name {} has value {}".format(k, v))
    """
    def __init__(self, **bindings):
        self._env = {}
        for name,value in bindings.items():
            self._env[name] = value

    # item access by name
    #
    def __setattr__(self, name, value):
        if name == "_env":  # hook to allow creating _env directly in self
            return super().__setattr__(name, value)
        self._env[name] = value  # make all other attrs else live inside _env

    def __getattr__(self, name):
        env = self._env   # __getattr__ not called if direct attr lookup succeeds, no need for hook.
        if name in env:
            return env[name]
        else:
            raise AttributeError("Name '{:s}' not in environment".format(name))

    # context manager
    #
    def __enter__(self):
        return self

    def __exit__(self, et, ev, tb):
        # we could nuke our *contents* to make all names in the environment
        # disappear, but it's simpler and more predictable not to.
        pass

    # iteration
    #
    def __iter__(self):
        return self._env.__iter__()

    def __next__(self):
        return self._env.__next__()

    def items(self):
        return self._env.items()

    # subscripting
    #
    def __getitem__(self, k):
        return getattr(self, k)

    def __setitem__(self, k, v):
        setattr(self, k, v)

    # pretty-printing
    #
    def __str__(self):
        bindings = ["{}: {}".format(name,value) for name,value in self._env.items()]
        return "<env: <{:s}>>".format(", ".join(bindings))

    # other
    #
    def set(self, name, value):
        """Convenience method to allow assignment in expression contexts.

        Like Scheme's set! function.

        For convenience, returns the `value` argument.
        """
        setattr(self, name, value)
        return value  # for convenience


def let(body, **bindings):
    """let expression.

    Examples:

        # order-preserving list uniqifier
        f = lambda lst: let(seen=set(),
                            body=lambda env: [env.seen.add(x) or x for x in lst if x not in env.seen])

        # a lambda that uses a locally defined lambda as a helper
        g = let(square=lambda x: x**2,
                body=lambda env: lambda x: 42 * env.square(x))
        print(g(10))

    As Lisp programmers know, the second example is subtly different from:

        g = lambda x: let(square=lambda y: y**2,
                          body=lambda env: 42 * env.square(x))

    In the original version, the let expression runs just once, when g is
    defined, whereas in this one, it re-runs whenever g is called.

    Parameters:
        `body`: one-argument function to run, taking an `env` instance that
                contains the "let" bindings as its attributes.

                To pass in more stuff:
                    - Use the closure property (free variables, lexical scoping)
                    - Make a nested lambda; only the outermost one is implicitly
                      called with env as its only argument.

        Everything else: "let" bindings; each argument name is bound to its value.
        No "lambda env:" is needed, as the environment is not seen by the bindings.

    Returns:
        The value returned by body.
    """
    return body(env(**bindings))


def letrec(body, **bindings):
    """letrec expression.

    The bindings have mutually recursive name resolution, like in Scheme.

    In letrec, also the bindings must be wrapped with a "lambda env:",
    to delay their evaluation until the environment instance has been created
    (and can thus be supplied to them, just before the body starts).

    The values for the bindings, inside the  lambda env: ...  wrapper, must be
    either expressions that do not use env (just like in a regular let),
    or lambdas (that may use env).

    Caveats:

        - When the arguments to the letrec are evaluated, the environment
          has not yet been created. The  lambda env: ...  works around this.

        - Initialization of the bindings occurs in an arbitrary order,
          because of the kwargs mechanism and storage as a dictionary.
          Hence the following does **not** work:

             x = letrec(a=lambda env: 1
                        b=lambda env: env.a + 1,
                        body=lambda env: env.b)

          because trying to reference env.a in the RHS of "b" may either get the
          lambda env: ..., or the value 1, depending on whether the binding "a"
          has been initialized at that point or not.

    Example:

        t = letrec(evenp=lambda env: lambda x: (x == 0) or env.oddp(x - 1),
                   oddp=lambda env: lambda x: (x != 0) and env.evenp(x - 1),
                   body=lambda env: env.evenp(42))

    Parameters:
        `body`: like in let()

        Everything else: "letrec" bindings, as one-argument functions.
        The argument is the environment.

    Returns:
        The value returned by body.
    """
    # Set up the environment as usual.
    e = env(**bindings)

    # Strip the "lambda env:" from each item, binding its "env"
    # formal parameter to this environment instance itself.
    #
    # Because we only aim to support function (lambda) definitions,
    # it doesn't matter that some of the names used in the definitions
    # might not yet exist in e, because Python only resolves the
    # name lookups at runtime (i.e. when the inner lambda is called).
    #
    for k in e:
        e[k] = e[k](e)

    return body(e)


# decorator factory: almost as fun as macros?
def dlet(**bindings):            # decorator factory
    """let decorator.

    Allows "let over def" for named functions.

    Usage is similar to the Lisp idiom "let over lambda": this gives a local
    environment that can be used to stash data to be preserved between calls.

    The "d" in the name stands for "decorator" or "def", your choice.

    Usage:

        @dlet(y = 23, z = 42)
        def foo(x, env=None):  # env is filled in by the decorator
            print(x, env.y, env.z)
        foo(17)

        @dlet(count = 0)
        def counter(env=None):
            env.count += 1
            return env.count
        print(counter())
        print(counter())
        print(counter())

    The named argument `env` is an env instance that contains the let bindings;
    all other args and kwargs are passed through.
    """
    def deco(body):                      # decorator
        # evaluate env when the function def runs!
        # (so that any mutations to its state are preserved
        #  between calls to the decorated function)
        env_instance = env(**bindings)
        # TODO: functools.wraps? wrapt?
        def decorated(*args, **kwargs):  # decorated function (replaces original body)
            kwargs_with_env = kwargs.copy()
            kwargs_with_env["env"] = env_instance
            return body(*args, **kwargs_with_env)
        return decorated
    return deco


def dletrec(**bindings):
    """letrec decorator.

    Like dlet, but for letrec.
    """
    def deco(body):
        # evaluate env when the function def runs!
        # (so that any mutations to its state are preserved
        #  between calls to the decorated function)
        e = env(**bindings)
        # Supply the environment instance to the letrec bindings.
        for k in e:
            e[k] = e[k](e)
        def decorated(*args, **kwargs):
            kwargs_with_env = kwargs.copy()
            kwargs_with_env["env"] = e
            return body(*args, **kwargs_with_env)
        return decorated
    return deco


def blet(**bindings):
    """let block.

    This is a decorator chain, first applying @dlet, then @immediate.

    In effect, this makes the def the body of the let, runs it immediately,
    and overwrites the def'd name with the result.

    Usage:

    @blet(x=17, y=23)
    def result(env=None):
        print(env.x, env.y)
        return env.x + env.y
    print(result)  # 40

    # can use a dummy name if the return value is of no interest:
    @blet(s="hello")
    def _(env=None):
        print(env.s)
    """
    dlet_deco = dlet(**bindings)
    def deco(body):
        return immediate(dlet_deco(body))
    return deco


def bletrec(**bindings):
    """letrec block.

    Like blet, but for letrec."""
    dletrec_deco = dletrec(**bindings)
    def deco(body):
        return immediate(dletrec_deco(body))
    return deco


############################################################
# Examples / tests
############################################################

# "let over lambda"-ish
#   - DANGER: "myenv" is bound in the surrounding scope; not what we want.
#   - If we have several of these in the same scope, the latest "myenv"
#     will win, overwriting the others. So a better solution is needed.
#
with env(x = 0) as myenv:
    def g():
        myenv.x += 1
        return myenv.x

# Abusing mutable default args gives true "let over lambda" behavior:
#
def h(_myenv = {"x": 0}):
    _myenv["x"] += 1
    return _myenv["x"]

# Combining these strategies (bunch, without context manager):
#
def i(_myenv = env(x = 0)):
    _myenv.x += 1
    return _myenv.x

# The decorator factory also gives us true "let over lambda" behavior:
#
@dlet(x = 0)
def j(env):
    env.x += 1
    return env.x


def uniqify_test():
    # the named function solution:
    def f(lst):
        seen = set()
        def see(x):
            seen.add(x)
            return x
        return [see(x) for x in lst if x not in seen]

    # the one-liner:
    f2 = lambda lst: (lambda seen: [seen.add(x) or x for x in lst if x not in seen])(seen=set())

    # we essentially want something like this:
    def f3(lst):
        with env(seen = set()) as myenv:
            return [myenv.seen.add(x) or x for x in lst if x not in myenv.seen]

    # using the above let:
    f4 = lambda lst: let(seen=set(),
                         body=lambda env: [env.seen.add(x) or x for x in lst if x not in env.seen])

    # testing:
    #
    L = [1, 1, 3, 1, 3, 2, 3, 2, 2, 2, 4, 4, 1, 2, 3]

    # Call each implementation twice to demonstrate that a fresh `seen`
    # is indeed created at each call.
    #
    print(f(L))
    print(f(L))

    print(f2(L))
    print(f2(L))

    print(f3(L))
    print(f3(L))

    print(f4(L))
    print(f4(L))

if __name__ == '__main__':
    uniqify_test()

    print(g())
    print(g())
    print(g())
    print(myenv)  # DANGER: visible from here

    print(h())
    print(h())
    print(h())

    print(i())
    print(i())
    print(i())

    print(j())
    print(j())
    print(j())

    ################################

    @dlet(y = 23)
    def foo(x, env):  # the named argument env contains the let bindings
        print(x, env.y)
    foo(17)

    ################################

    # Lexical scoping - actually, just by borrowing Python's:
    #
    @dlet(x = 5)
    def bar(env):
        print("in bar x is", env.x)

        @dlet(x = 42)
        def baz(env):  # this env shadows the outer env
            print("in baz x is", env.x)
        baz()

        print("in bar x is still", env.x)
    bar()

    ################################

    # To eliminate the explicit calls, @immediate from lecture 11, slide 33:
    #
    @immediate
    @dlet(x = 5)
    def _(env):  # this is now the let block
        print("outer x is", env.x)

        @immediate
        @dlet(x = 42)
        def _(env):
            print("inner x is", env.x)

        print("outer x is still", env.x)

    ################################

    # With a combined decorator:
    #
    @blet(x = 5)
    def _(env):  # the body of the let block
        print("outer x is", env.x)

        @blet(x = 42)
        def _(env):
            print("inner x is", env.x)

        print("outer x is still", env.x)

    ################################

    # reinterpreting the idea of "immediate" is also a possible approach:
    letify = lambda thunk: thunk()

    @letify
    def _(x = 1):
        # ...this is just a block of code with the above bindings...
        return x*42  # ...but we can also return to break out of it early, if needed.
    print(_)  # the def'd "function" is replaced by its return value

    ################################

    # Let over lambda, expression version.
    # The inner lambda is the definition of the function f.
    from unpythonic.misc import begin
    f = let(x = 0,
            body = lambda env: lambda: begin(env.set("x", env.x + 1),
                                             env.x))
    print(f())
    print(f())
    print(f())

    # expression
    #
    # https://docs.racket-lang.org/reference/let.html
    t = letrec(evenp=lambda env: lambda x: (x == 0) or env.oddp(x - 1),
               oddp=lambda env: lambda x: (x != 0) and env.evenp(x - 1),
               body=lambda env: env.evenp(42))
    print(t)

    # decorator
    #
    @dletrec(evenp=lambda env: lambda x: (x == 0) or env.oddp(x - 1),
             oddp=lambda env: lambda x: (x != 0) and env.evenp(x - 1))
    def is_even(x, *, env):  # make env passable by name only
        return env.evenp(x)
    print(is_even(23))

    # decorator with immediate
    #
    @bletrec(evenp=lambda env: lambda x: (x == 0) or env.oddp(x - 1),
             oddp=lambda env: lambda x: (x != 0) and env.evenp(x - 1))
    def result(env):
        return env.evenp(23)
    print(result)
