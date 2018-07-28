# Unpythonic: Lispy convenience features for Python

```python
from unpythonic import *
```

### Assign-once

Make `define` and `set!` look different:

```python
with assignonce() as e:
    e.foo = "bar"           # new definition, ok
    e.set("foo", "tavern")  # explicitly rebind e.foo, ok
    e << ("foo", "tavern")  # same thing (but return e instead of new value, suitable for chaining)
    e.foo = "quux"          # AttributeError, e.foo already defined.
```

### Multiple expressions in a lambda

```python
f1 = lambda x: begin(print("cheeky side effect"),
                     42*x)
f1(2)  # --> 84

f2 = lambda x: begin0(42*x,
                      print("cheeky side effect"))
f2(2)  # --> 84
```

Actually a tuple in disguise. If worried about memory consumption, use `lazy_begin` and `lazy_begin0` instead, which indeed use loops. The price is the need for a lambda wrapper for each expression to delay evaluation, see [`tour.py`](tour.py) for details.

Note also it's only useful for side effects, since there's no way to define new names, except...

### ``let``, ``letrec``

Use a `lambda e: ...` to supply the environment to the body:

```python
u = lambda lst: let(seen=set(),
                    body=lambda e:
                           [e.seen.add(x) or x for x in lst if x not in e.seen])
L = [1, 1, 3, 1, 3, 2, 3, 2, 2, 2, 4, 4, 1, 2, 3]
u(L)  # --> [1, 3, 2, 4]
```

*Let over lambda*. The inner ``lambda`` is the definition of the function ``counter``:

```python
counter = let(x=0,
              body=lambda e:
                     lambda:
                       begin(e.set("x", e.x + 1),  # can also use e << ("x", e.x + 1)
                             e.x))
counter()  # --> 1
counter()  # --> 2
```

The above compares almost favorably to this [Racket](http://racket-lang.org/) (here using `sweet-exp` [[1]](https://srfi.schemers.org/srfi-110/srfi-110.html) [[2]](https://docs.racket-lang.org/sweet/) for pythonic layout):

```racket
define counter
  let ([x 0])
    λ ()  ; λ has an implicit begin(), so we don't need to explicitly have one
      set! x {x + 1}
      x
counter()  ; --> 1
counter()  ; --> 2
```

*Let over def* decorator ``@dlet``, to *let over lambda* more pythonically:

```python
@dlet(x=0)
def counter(*, env=None):  # named argument "env" filled in by decorator
    env.x += 1
    return env.x
counter()  # --> 1
counter()  # --> 2
```

In case of `letrec`, each binding takes a `lambda e: ...`, too:

```python
u = lambda lst: letrec(seen=lambda e:
                              set(),
                       see=lambda e:
                              lambda x:
                                begin(e.seen.add(x),
                                      x),
                       body=lambda e:
                              [e.see(x) for x in lst if x not in e.seen])

letrec(evenp=lambda e:
               lambda x:
                 (x == 0) or e.oddp(x - 1),
       oddp=lambda e:
               lambda x:
                 (x != 0) and e.evenp(x - 1),
       body=lambda e:
               e.evenp(42))  # --> True
```

**CAUTION**: bindings are **initialized in an arbitrary order**, also in `letrec`. This is a limitation of the kwargs abuse. Hence mutually recursive functions are possible, but simple data values cannot depend on other bindings in the same `letrec`.

Trying to access `e.foo` from `e.bar` arbitrarily produces either the intended value of `e.foo`, or the uninitialized `lambda e: ...`, depending on whether `e.foo` has been initialized or not at the point of time when `e.bar` is being initialized.

#### Lispylet

There is also an alternative implementation for all the `let` constructs, with **guaranteed left-to-right initialization** using positional syntax and more parentheses:

```python
from unpythonic.lispylet import *  # override the default "let" implementation

letrec((('a', 1),
        ('b', lambda e:
                e.a + 1)),  # may refer to any bindings above it in the same letrec
       lambda e:
         e.b)  # --> 2

letrec((("evenp", lambda e:
                    lambda x:
                      (x == 0) or e.oddp(x - 1)),
        ("oddp",  lambda e:
                    lambda x:
                      (x != 0) and e.evenp(x - 1))),
       lambda e:
         e.evenp(42))  # --> True
```

Usage is `let(bindings, body)` (respectively `letrec(bindings, body)`), where `bindings` is `((name, value), ...)`, and `body` is a one-argument function that takes in the environment. In typical inline usage, `body` is `lambda e: expr`.

Each `value` is bound to the corresponding `name`. As an exception, in the case of ``letrec``, if `value` is callable, it will be called with the environment as its only argument at environment setup time, and the result of the call is bound to `name`.

A callable `value`, of the form `lambda e: valexpr`, may refer to bindings above it in the same `letrec`. If `valexpr` itself is callable, it may refer to any binding (also later ones) in the same `letrec`, allowing mutually recursive function definitions (such as `evenp` and `oddp` above).

Thus, to bind a callable, use ``lambda e: mycallable`` as `value`, whether or not `mycallable` actually uses the environment. If the ``lambda e: ...`` wrapper is missing, `mycallable` itself will be called at environment setup time, with the environment as its argument (likely not what was intended).

Examples of binding callables:

```python
u = lambda lst: letrec((("seen", set()),
                        ("see",  lambda e:
                                   lambda x:  # a function, needs "lambda e: ..."
                                     begin(e.seen.add(x),
                                           x))),
                       lambda e:
                         [e.see(x) for x in lst if x not in e.seen])

letrec((('a', 2),
        ('f', lambda e:
                lambda x:  # a function, needs "lambda e: ..." even though it doesn't use e
                  42*x)),
       lambda e:
         e.a * e.f(1))  # --> 84

square = lambda x: x**2
letrec((('a', 2),
        ('f', lambda e: square)),  # callable, needs "lambda e: ..."
       lambda e: e.a * e.f(10))  # --> 200

def mul(x, y):
    return x * y
letrec((('a', 2),
        ('f', lambda e: mul)),  # "mul" is a callable
       lambda e: e.a * e.f(3, 4))  # --> 24

from functools import partial
double = partial(mul, 2)
letrec((('a', 2),
        ('f', lambda e: double)),  # "double" is a callable
       lambda e: e.a * e.f(3))  # --> 12

class TimesA:
    def __init__(self, a):
        self.a = a
    def __call__(self, x):
        return self.a * x
times5 = TimesA(5)
letrec((('a', 2),
        ('f', lambda e: times5)),  # "times5" is a callable
       lambda e: e.a * e.f(3))  # --> 30
```

### Tail call optimization (TCO) / explicit continuations

Express elegant algorithms without blowing the call stack - with explicit, clear syntax.

*Tail recursion*:

```python
@trampolined
def fact(n, acc=1):
    if n == 0:
        return acc
    else:
        return jump(fact, n - 1, n * acc)
print(fact(4))  # 24
```

Functions that use TCO must be `@trampolined`.

Inside a trampolined function, a normal call `f(a, ..., kw=v, ...)` remains a normal call. A tail call with target `f` is denoted `return jump(f, a, ..., kw=v, ...)`. The final result is just returned normally.

Here `jump` is **a noun, not a verb**. The `jump(f, ...)` part just evaluates to a `jump` instance, which on its own does nothing. Returning it to the trampoline actually performs the tail call.

*Tail recursion in a lambda*:

```python
t = trampolined(lambda n, acc=1:
                    acc if n == 0 else jump(SELF, n - 1, n * acc))
print(t(4))  # 24
```

To denote tail recursion in an anonymous function, use the special jump target `SELF` (all uppercase!). Here it's just `jump` instead of `return jump` since lambda does not use the `return` syntax.

*Mutual recursion*:

```python
@trampolined
def even(n):
    if n == 0:
        return True
    else:
        return jump(odd, n - 1)
@trampolined
def odd(n):
    if n == 0:
        return False
    else:
        return jump(even, n - 1)
print(even(42))  # True
print(odd(4))  # False
```

*Looping in FP style*, with TCO:

```python
@loop
def s(acc=0, i=0):
    if i == 10:
        return acc
    else:
        return jump(SELF, acc + i, i + 1)
print(s)  # 45
```

Compare this sweet-exp Racket:

```racket
define s
  let loop ([acc 0] [i 0])
    cond
      {i = 10}
        acc
      else
        loop {acc + i} {i + 1}
displayln s
```

Could also do this explicitly:

```python
@trampolined
def dowork(acc, i):
    if i == 10:
        return acc
    else:
        return jump(dowork, acc + i, i + 1)
s = dowork(0, 0)
print(s)  # 45
```

Reinterpreting the same feature as *explicit continuations*:

```python
@trampolined
def foo():
    return jump(bar)
@trampolined
def bar():
    return jump(baz)
@trampolined
def baz():
    print("How's the spaghetti today?")
foo()
```

Each function tells the trampoline where to go next (and with what parameters). All hail lambda, the ultimate GO TO!


### Dynamic scoping

A bit like global variables, but slightly better-behaved. Useful for sending some configuration parameters through several layers of function calls without changing their API. Best used sparingly. Similar to [Racket](http://racket-lang.org/)'s [`parameterize`](https://docs.racket-lang.org/guide/parameterize.html).

There's a singleton, `dyn`, which emulates dynamic scoping:

```python
def f():  # no "a" in lexical scope here
    assert dyn.a == 2

def g():
    with dyn.let(a=2, b="foo"):
        assert dyn.a == 2

        f()

        with dyn.let(a=3):  # dynamic scopes can be nested
            assert dyn.a == 3

        # now "a" has reverted to its previous value
        assert dyn.a == 2

    print(dyn.b)  # AttributeError, dyn.b no longer exists
g()
```

Dynamic variables can only be set using `with dyn.let(...)`. No `set`, `<<`, unlike in the other `unpythonic` environments.

The values of dynamic variables remain bound for the dynamic extent of the `with` block. Exiting the `with` block then pops the stack. Inner dynamic scopes shadow outer ones. Dynamic variables are seen also by code that is outside the lexical scope where the `with dyn.let` resides.

Each thread has its own dynamic scope stack. A newly spawned thread automatically copies the then-current state of the dynamic scope stack **from the main thread** (not the parent thread!). This feature is mainly intended for easily initializing default values for configuration parameters across all threads.

Any copied bindings will remain on the stack for the full dynamic extent of the new thread. Because these bindings are not associated with any `with` block running in that thread, and because aside from the initial copying, the dynamic scope stacks are thread-local, any copied bindings will never be popped, even if the main thread pops its own instances of them.

The source of the copy is always the main thread mainly because Python's `threading` module gives no tools to detect which thread spawned the current one. (If someone knows a simple solution, PRs welcome!)

### The environment

The environment used by all the ``let`` constructs and ``assignonce`` (but **not** by `dyn`) is essentially a bunch with iteration, subscripting and context manager support. For details, see `unpythonic.env`.

This allows things like:

```python
let(x=1, y=2, z=3,
    body=lambda e:
           [(name, 2*e[name]) for name in e])  # --> [('y', 4), ('z', 6), ('x', 2)]
```

It also works as a bare bunch, and supports printing for debugging:

```python
from unpythonic.env import env

e = env(s="hello", orange="fruit", answer=42)
print(e)  # --> <env object at 0x7ff784bb4c88: {orange='fruit', s='hello', answer=42}>
print(e.s)  # --> hello

d = {'monty': 'python', 'pi': 3.14159}
e = env(**d)
print(e)  # --> <env object at 0x7ff784bb4c18: {pi=3.14159, monty='python'}>
print(e.monty)  # --> python
```

Finally, it supports the context manager:

```python
with env(x=1, y=2, z=3) as e:
    print(e)  # --> <env object at 0x7fde7411b080: {x=1, z=3, y=2}>
    print(e.x)  # --> 1
print(e)  # empty!
```

When the `with` block exits, the environment clears itself. The environment instance itself remains alive due to Python's scoping rules.

### ``def`` as a code block

Fuel for different thinking. Compare the `something` in `call-with-something` in Lisps. A `def` is really just a new lexical scope to hold code to run later... or right now!

*Make temporaries fall out of scope as soon as no longer needed*:

```python
@immediate
def x():
    a = 2  #    many temporaries that help readability...
    b = 3  # ...of this calculation, but would just pollute locals...
    c = 5  # ...after the block exits
    return a * b * c
print(x)  # 30
```

*Multi-break out of nested loops* - `continue`, `break` and `return` are really just second-class [ec](https://docs.racket-lang.org/reference/cont.html#%28def._%28%28lib._racket%2Fprivate%2Fletstx-scheme..rkt%29._call%2Fec%29%29)s. So `def` to make `return` escape to exactly where you want:

```python
@immediate
def result():
    for x in range(10):
        for y in range(10):
            if x * y == 42:
                return (x, y)
print(result)  # (6, 7)
```

Compare this sweet-exp Racket:

```racket
define result
  let/ec return  ; name the (first-class) ec to break out of this let/ec block
    for ([x in-range(10)])
      for ([y in-range(10)])
        cond
          {{x * y} = 42}
            return (list x y)
displayln result  ; (6 7)
```

*Twist the meaning of `def` into a "let statement"* (but see `blet`, `bletrec` if you want an `env`):

```python
@immediate
def result(x=1, y=2, z=3):
    return x * y * z
print(result)  # 6
```

*Letrec without `letrec`*, when it doesn't have to be an expression:

```python
@immediate
def t():
    def evenp(x): return x == 0 or oddp(x - 1)
    def oddp(x): return x != 0 and evenp(x - 1)
    return evenp(42)
print(t)  # True
```

Essentially the implementation is just `def immediate(thunk): return thunk()`. The point is to:

 - Make it explicit right at the definition site that this block is going to be run ``@immediate``ly (in contrast to an explicit call and assignment *after* the definition). Centralize the related information. Align the presentation order with the thought process.

 - Help eliminate errors, in the same way as the habit of typing parentheses only in pairs. No risk of forgetting to call the block after writing the definition.

 - Document that the block is going to be used only once. Tell the reader there's no need to remember this definition.

Too bad [the grammar](https://docs.python.org/3/reference/grammar.html) requires a newline after a decorator; "`@immediate def`" would look nicer.

## Notes

The main design consideration in this package is to not need `inspect`, keeping these modules simple and robust.

Since we **don't** depend on [MacroPy](https://github.com/azazel75/macropy), we provide run-of-the-mill functions and classes, not actual syntactic forms.

For more examples, see [``tour.py``](tour.py), the `test()` function in each submodule, and the docstrings of the individual features.

### On ``let`` and Python

Why no `let*`? In Python, name lookup always occurs at runtime. Python gives us no compile-time guarantees that no binding refers to a later one - in [Racket](http://racket-lang.org/), this guarantee is the main difference between `let*` and `letrec`.

Even Racket's `letrec` processes the bindings sequentially, left-to-right, but *the scoping of the names is mutually recursive*. Hence a binding may contain a lambda that, when eventually called, uses a binding defined further down in the `letrec` form. We similarly allow this.

In contrast, in a `let*` form, attempting such a definition is *a compile-time error*, because at any point in the sequence of bindings, only names found earlier in the sequence have been bound. See [TRG on `let`](https://docs.racket-lang.org/guide/let.html).

The ``lispylet`` version of `letrec` behaves slightly more like `let*` in that if `valexpr` is not a function, it may only refer to bindings above it. But ``lispylet.letrec`` still allows mutually recursive function definitions, hence the name.

Inspiration: [[1]](https://nvbn.github.io/2014/09/25/let-statement-in-python/) [[2]](https://stackoverflow.com/questions/12219465/is-there-a-python-equivalent-of-the-haskell-let) [[3]](http://sigusr2.net/more-about-let-in-python.html).

### Python is not a Lisp

The point behind providing `let` and `begin` is to make Python lambdas slightly more useful - which was really the starting point for this whole experiment.

The oft-quoted single-expression limitation is ultimately a herring - it can be fixed with a suitable `begin` form, or a function to approximate one.

The real problem is the statement/expression dichotomy. In Python, the looping constructs (`for`, `while`), the full power of `if`, and `return` are statements, so they cannot be used in lambdas. The expression form of `if` can be used to a limited extent (actually [`and` and `or` are sufficient for full generality](https://www.ibm.com/developerworks/library/l-prog/), but readability suffers), and functional looping (via tail recursion) is possible (for short loops, without tricks; for long ones, with explicit TCO) - but still, ultimately one must keep in mind that Python is not a Lisp.

Another factor here is that not all of Python's standard library is expression-friendly; some standard functions and methods lack return values - even though a call is an expression! For example, `set.add(x)` returns `None`, whereas in an expression context, returning `x` would be much more useful.

### Assignment syntax

Why the clunky `e.set("foo", newval)` or `e << ("foo", newval)`, which do not directly mention `e.foo`? This is mainly because in Python, the language itself is not customizable. If we could define a new operator `e.foo <op> newval` to transform to `e.set("foo", newval)`, this would be easily solved.

We could abuse `e.foo << newval`, which transforms to `e.foo.__lshift__(newval)`, to essentially perform `e.set("foo", newval)`, but this requires some magic, because we then need to monkey-patch each incoming value (including the first one when the name "foo" is defined) to set up the redirect and keep it working.

 - Methods of builtin types such as `int` are read-only, so we can't just override `__lshift__` in any given `newval`.
 - For many types of objects, at the price of some copy-constructing, we can provide a wrapper object that inherits from the original's type, and just adds an `__lshift__` method to catch and redirect the appropriate call. See commented-out proof-of-concept in [`unpythonic/env.py`](unpythonic/env.py).
 - But that approach doesn't work for function values, because `function` is not an acceptable base type to inherit from. In this case we could set up a proxy object, whose `__call__` method calls the original function (but what about the docstring and such? Is `@functools.wraps` enough?). But then there are two kinds of wrappers, and the re-wrapping logic (which is needed to avoid stacking wrappers when someone does `e.a << e.b`) needs to know about that.
 - It's still difficult to be sure these two approaches cover all cases; a read of `e.foo` gets a wrapped value, not the original; and this already violates [The Zen of Python](https://www.python.org/dev/peps/pep-0020/) #1, #2 and #3.

If we later choose go this route nevertheless, `<<` is a better choice for the syntax than `<<=`, because `let` needs `e.set(...)` to be valid in an expression context.

### Wait, no monads?

Already done elsewhere, see [PyMonad](https://bitbucket.org/jason_delaat/pymonad/) or [OSlash](https://github.com/dbrattli/OSlash) if you need them. Especially the `List` monad can be useful also in Python, e.g. to make an [`amb`](https://rosettacode.org/wiki/Amb) without `call/cc`. Compare [this solution in Ruby](http://www.randomhacks.net/2005/10/11/amb-operator/), with `call/cc`.

If you want to roll your own monads for whatever reason, there's [this silly hack](https://github.com/Technologicat/python-3-scicomp-intro/blob/master/examples/monads.py) that wasn't packaged into this; or just read Stephan Boyer's quick introduction [[part 1]](https://www.stephanboyer.com/post/9/monads-part-1-a-design-pattern) [[part 2]](https://www.stephanboyer.com/post/10/monads-part-2-impure-computations) [[super quick intro]](https://www.stephanboyer.com/post/83/super-quick-intro-to-monads) and figure it out, it's easy. (Until you get to `State` and `Reader`, where [this](http://brandon.si/code/the-state-monad-a-tutorial-for-the-confused/) and maybe [this](https://gaiustech.wordpress.com/2010/09/06/on-monads/) can be helpful.)

## Installation

Not yet available on PyPI; clone from GitHub.

### Install

Usually one of:

```
python3 setup.py install --user
```

```
sudo python3 setup.py install
```

depending on what you want.

### Uninstall

```
pip3 uninstall unpythonic
```

Must be invoked in a folder which has no subfolder called `unpythonic`, so that `pip` recognizes it as a package name (instead of a filename).

## License

2-clause [BSD](LICENSE.md).

Dynamic scoping based on [StackOverflow answer by Jason Orendorff (2010)](https://stackoverflow.com/questions/2001138/how-to-create-dynamical-scoped-variables-in-python), used under CC-BY-SA. The threading support is original to our version.

Core idea of `lispylet` based on [StackOverflow answer by divs1210 (2017)](https://stackoverflow.com/a/44737147), used under the MIT license.

## Python-related FP resources

- [Awesome Functional Python](https://github.com/sfermigier/awesome-functional-python), especially a list of useful libraries. Some picks:

  - [fn.py: Missing functional features of fp in Python](https://github.com/fnpy/fn.py) (actively maintained fork). Includes e.g. tail call elimination by trampolining, and a very compact way to recursively define infinite streams.

  - [more-itertools: More routines for operating on iterables, beyond itertools.](https://github.com/erikrose/more-itertools)

  - [toolz: A functional standard library for Python](https://github.com/pytoolz/toolz)

  - [funcy](https://github.com/suor/funcy/)

  - [pyrsistent: Persistent/Immutable/Functional data structures for Python](https://github.com/tobgu/pyrsistent)

- [List of languages that compile to Python](https://github.com/vindarel/languages-that-compile-to-python) including Hy, a Lisp (in the [Lisp-2](https://en.wikipedia.org/wiki/Lisp-1_vs._Lisp-2) family) that can use Python libraries.

Old, but interesting:

- [Peter Norvig (2000): Python for Lisp Programmers](http://www.norvig.com/python-lisp.html)

- [David Mertz (2001): Charming Python - Functional programming in Python, part 2](https://www.ibm.com/developerworks/library/l-prog2/index.html)

