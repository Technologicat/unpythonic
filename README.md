# Unpythonic: `let`, assign-once, dynamic scoping

Constructs that change the rules.

```python
from unpythonic import *
```

### Assign-once environment

```python
with assignonce() as e:
    e.foo = "bar"      # new definition, ok
    e.foo << "tavern"  # explicitly rebind e.foo, ok
    e.foo = "quux"     # AttributeError, e.foo already defined.
```

### Multiple expressions in a lambda

```python
f1 = lambda x: begin(print("cheeky side effect"), 42*x)
f1(2)  # --> 84

f2 = lambda x: begin0(42*x, print("cheeky side effect"))
f2(2)  # --> 84
```

### ``let``, ``letrec``

```python
u = lambda lst: let(seen=set(),
                    body=lambda e: [e.seen.add(x) or x for x in lst if x not in e.seen])
L = [1, 1, 3, 1, 3, 2, 3, 2, 2, 2, 4, 4, 1, 2, 3]
u(L)  # --> [1, 3, 2, 4]

t = letrec(evenp=lambda e: lambda x: (x == 0) or e.oddp(x - 1),
           oddp=lambda e: lambda x: (x != 0) and e.evenp(x - 1),
           body=lambda e: e.evenp(42))  # --> True
```

Traditional *let over lambda*. The inner ``lambda`` is the definition of the function ``counter``:

```python
counter = let(x=0,
          body=lambda e: lambda: begin(e.set("x", e.x + 1),
                                       e.x))
counter()  # --> 1
counter()  # --> 2
counter()  # --> 3
```

Compare this [Racket](http://racket-lang.org/) equivalent (here using `sweet-exp` [[1]](https://srfi.schemers.org/srfi-110/srfi-110.html) [[2]](https://docs.racket-lang.org/sweet/)):

```racket
define counter
  let ([x 0])
    λ ()
      set! x {x + 1}
      x
counter()  ; --> 1
counter()  ; --> 2
counter()  ; --> 3
```

*Let over def* decorator ``@dlet``:

```python
@dlet(x=0)
def counter(*, env=None):  # named argument "env" filled in by decorator
    env.x += 1
    return env.x
counter()  # --> 1
counter()  # --> 2
counter()  # --> 3
```

**CAUTION**: bindings are initialized in an arbitrary order, also in ``letrec``. This is a limitation of the kwargs abuse. If you need left-to-right initialization, ``unpythonic.lispylet`` provides an alternative implementation with positional syntax:

```python
from unpythonic.lispylet import *  # override the default "let" implementation

letrec((('a', 1),
        ('b', lambda e: e.a + 1)),
       lambda e: e.b)  # --> 2
```

### ``def`` as a code block

Make temporaries fall out of scope as soon as no longer needed:

```python
@immediate
def x():
    a = 2  #    many temporaries that help readability...
    b = 3  # ...of this calculation, but would just pollute locals...
    c = 5  # ...after the block exits
    return a * b * c
assert x == 30
```

Multi-break out of nested loops:

```python
@immediate
def result():
    for x in range(10):
        for y in range(10):
            if x * y == 42:
                return (x, y)
            ... # more code here
assert result == (6, 7)
```

This is purely a convenience feature, which:

 - Makes it explicit right at the definition site that this block is going to be run ``@immediate``ly (in contrast to an explicit call and assignment *after* the definition). Collects related information into one place. Aligns the ordering of the presentation with the ordering of the thought process, reducing the need to skip back and forth.

 - Helps eliminate errors, in the same way as the habit of typing parentheses only in pairs. There's no risk of forgetting to call the block after the possibly lengthy process of thinking through and writing the definition.

 - Documents that the block is going to be used only once, and not called from elsewhere possibly much later. Tells the reader there's no need to remember this definition.

### Dynamic scoping

Via creative application of lexical scoping. There's a singleton, `dyn`:

```python
def f():
    assert dyn.a == 2

def g():
    with dyn.let(a=2, b="foo"):
        assert dyn.a == 2

        f()  # defined outside the lexical scope of g()!

        with dyn.let(a=3):  # dynamic scopes can be nested
            assert dyn.a == 3

        assert dyn.a == 2

    print(dyn.b)  # AttributeError, dyn.b no longer exists
g()
```

Each thread gets its own dynamic scope stack.

## Notes

Since we **don't** depend on [MacroPy](https://github.com/azazel75/macropy), we provide run-of-the-mill functions and classes, not actual syntactic forms.

For more examples, see [``tour.py``](tour.py), the `test()` function in each submodule, and the docstrings of the individual features.

### On ``let`` and Python

Why no `let*`? In Python, name lookup always occurs at runtime. Hence, if we allow using the environment instance in the RHS of the bindings, that automatically gives us `letrec`. Each binding is only looked up when we attempt to use it, and at that point they all already exist.

Python gives us no compile-time guarantees that no binding refers to a later one - in [Racket](http://racket-lang.org/), this guarantee is the main difference between `let*` and `letrec`.

Even Racket's `letrec` processes the bindings sequentially, left-to-right, but *the scoping of the names is mutually recursive*. Hence a binding may contain a lambda that, when eventually called, uses a binding defined further down in the `letrec` form.

In contrast, in a `let*` form, attempting such a definition is *a compile-time error*, because at any point in the sequence of bindings, only names found earlier in the sequence have been bound. See [TRG on `let`](https://docs.racket-lang.org/guide/let.html).

Inspiration: [[1]](https://nvbn.github.io/2014/09/25/let-statement-in-python/) [[2]](https://stackoverflow.com/questions/12219465/is-there-a-python-equivalent-of-the-haskell-let) [[3]](http://sigusr2.net/more-about-let-in-python.html).

### Python is not a Lisp

The point behind providing `let` and `begin` is to make Python lambdas slightly more useful. The oft-quoted single-expression limitation is ultimately a herring - it can be fixed with a suitable `begin` form, or a function to approximate one.

The real problem is that in Python, the looping constructs (`for`, `while`), the full power of `if`, and `return` are statements, so they cannot be used in lambdas. The expression form of `if` (and `and` and `or`) can be used to a limited extent, and functional looping (via tail recursion) is possible for short loops - where the lack of tail call elimination does not yet crash the program - but still, ultimately one must keep in mind that Python is not a Lisp.

Another factor here is that not all of Python's standard library is expression-friendly; some standard functions and methods lack return values. For example, `set.add(x)` returns `None`, whereas in an expression context, returning `x` would be much more useful. This can be worked around like the similar situation with `set!` in Scheme, using `begin()`.

### Wait, no monads?

Already done elsewhere, see [PyMonad](https://bitbucket.org/jason_delaat/pymonad/) or [OSlash](https://github.com/dbrattli/OSlash) if you need them. (The `List` monad can be useful also in Python - e.g. to make an [`amb`](https://rosettacode.org/wiki/Amb) without `call/cc`. Compare [this solution in Ruby](http://www.randomhacks.net/2005/10/11/amb-operator/), with `call/cc`.)

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

while outside the `unpythonic` folder, so that `pip` recognizes it as a package name (instead of a filename).

## License

2-clause [BSD](LICENSE.md).

Dynamic scoping based on [StackOverflow answer by Jason Orendorff (2010)](https://stackoverflow.com/questions/2001138/how-to-create-dynamical-scoped-variables-in-python), used under CC-BY-SA.

Core idea of `lispylet` based on [StackOverflow answer by divs1210 (2017)](https://stackoverflow.com/a/44737147), used under the MIT license.

## Python-related FP resources

[Awesome Functional Python](https://github.com/sfermigier/awesome-functional-python), especially a list of useful libraries.

[List of languages that compile to Python](https://github.com/vindarel/languages-that-compile-to-python) including Hy, a Lisp that can use Python libraries.

