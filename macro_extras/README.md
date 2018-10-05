# ``unpythonic.syntax``: macro extras

These optional features are built on [MacroPy](https://github.com/azazel75/macropy), from PyPI package ``macropy3``.

Because macro expansion occurs at import time, the usage example `main.py` cannot be run directly. Instead, run it via the bootstrap script `run.py`, or use the included [generic MacroPy3 bootstrapper](macropy3). Usage of the bootstrapper is `./macropy3 main`; see `-h` for options.

There is no abbreviation for ``memoize(lambda: ...)``, because ``MacroPy`` itself already provides ``lazy`` and ``interned``.

!! **Currently** (10/2018) this requires the latest MacroPy from git HEAD. !!

## ``curry``: Automatic currying for Python

```python
from unpythonic.syntax import macros, curry
from unpythonic import foldr, composerc as compose, cons, nil

with curry:
    mymap = lambda f: foldr(compose(cons, f), nil)
    double = lambda x: 2 * x
    print(mymap(double, (1, 2, 3)))
```

All function calls *lexically* inside a ``with curry`` block are automatically curried, somewhat like in Haskell, or in ``#lang`` [``spicy``](https://github.com/Technologicat/spicy).

**CAUTION**: Builtins are uninspectable, so cannot be curried. In a ``with curry`` block, ``unpythonic.fun.curry`` runs in a special mode that no-ops on uninspectable functions instead of raising ``TypeError`` as usual. This special mode is enabled for the *dynamic extent* of the ``with curry`` block.


## ``let``, ``letseq``, ``letrec`` as macros

Properly lexically scoped ``let`` constructs, no boilerplate:

```python
from unpythonic.syntax import macros, let, letseq, letrec

let((x, 17),  # parallel binding, i.e. bindings don't see each other
    (y, 23))[
      print(x, y)]

letseq((x, 1),  # sequential binding, i.e. Scheme/Racket let*
       (y, x+1))[
         print(x, y)]

letrec((evenp, lambda x: (x == 0) or oddp(x - 1)),  # mutually recursive binding, sequentially evaluated
       (oddp,  lambda x: (x != 0) and evenp(x - 1)))[
         print(evenp(42))]
```

Syntax is similar to ``unpythonic.lispylet``, but no quotes around variable names in bindings, and no ``lambda e: ...`` wrappers. Bindings are referred to by bare names like in Lisps, no ``e.`` prefix. Assignment to variables in the environment is supported via the left-shift syntax ``x << 42``.

Note the ``[...]``; these are ``expr`` macros. The bindings are given as macro arguments as ``((name, value), ...)``, the body goes into the ``[...]``.

``let`` and ``letrec`` expand into the ``unpythonic.lispylet`` constructs, implicitly inserting ``lambda e: ...``, quoting variable names in definitions, and transforming ``x`` to ``e.x`` for all ``x`` declared in the bindings. Assignment syntax ``x << 42`` transforms to ``e.set('x', 42)``. The implicit environment argument ``e`` is actually named using a gensym, so lexically outer environments automatically show through. ``letseq`` expands into a chain of nested ``let`` expressions.

Nesting utilizes the fact that (as of v1.1.0) MacroPy3 expands macros in an inside-out order:

```python
from unpythonic import begin

letrec((z, 1))[
  begin(print(z),
        letrec((z, 2))[
          print(z)])]  # (be careful with the parentheses!)
```

Hence the ``z`` in the inner scope expands to the inner environment's ``z``, which makes the outer expansion leave it alone. (This works by transforming only ``ast.Name`` nodes, stopping recursion when an ``ast.Attribute`` is encountered.)

### Note

We also provide ``simple_let`` and ``simple_letseq``, wholly implemented as AST transformations, providing true lexical variables but no assignment support (because in Python, assignment is a statement). Just like in Lisps, ``simple_letseq`` (Scheme/Racket ``let*``) expands into a chain of nested ``simple_let`` expressions, which expand to lambdas.


## ``cond``: the missing ``elif`` for ``a if p else b``

Now lambdas too can have multi-branch conditionals, yet remain human-readable:

```python
from unpythonic.syntax import macros, cond

answer = lambda x: cond[x == 2, "two",
                        x == 3, "three",
                        "something else"]
print(answer(42))
```

Syntax is ``cond[test1, then1, test2, then2, ..., otherwise]``. Expansion raises an error if the ``otherwise`` branch is missing.


## ``aif``: anaphoric if

This is mainly of interest as a point of [comparison with Racket](https://github.com/Technologicat/python-3-scicomp-intro/blob/master/examples/beyond_python/aif.rkt); ``aif`` is about the simplest macro that relies on either the lack of hygiene or breaking thereof.

```python
from unpythonic.syntax import macros, aif

aif[2*21,
    print("it is {}".format(it)),
    print("it is False")]
```

Syntax is ``aif[test, then, otherwise]``. The magic identifier ``it`` refers to the test result while (lexically) inside the ``aif``, and does not exist outside the ``aif``.


## ``do`` as a macro: stuff imperative code into a lambda, *with style*

We provide an ``expr`` macro wrapper for ``unpythonic.seq.do``, with some extra features.

```python
from unpythonic.syntax import macros, do

y = do[localdef(x << 17),
       print(x),
       x << 23,
       x]
print(y)  # --> 23
```

Local variables are declared and initialized with ``localdef(var << value)``, where ``var`` is a bare name. To explicitly denote "no value", just use ``None``. Currently it does not matter where the ``localdef`` appears inside the ``do``; it captures the declared name as a local variable **for the whole lexical scope** of the ``do``, including any references to that name **before** the ``localdef``. (This is subject to change in a future version.) For readability and future-proofness, it is recommended to place localdefs at or near the start of the do-block, at the first use of each local name.

Already declared local variables are updated with ``var << value``.

The reason we require local variables to be declared is to allow write access to lexically outer environments (e.g. a ``let`` surrounding a ``do``).

Assignments are recognized anywhere inside the ``do``; but note that any nested ``let`` constructs that define variables of the same name will (inside the ``let``) shadow those of the ``do``.

Like in the macro ``letrec``, no ``lambda e: ...`` wrappers. These are inserted automatically, so the lines are only evaluated as the underlying ``seq.do`` actually runs.

When running, ``do`` behaves like ``letseq``; assignments **above** the current line are in effect (and have been performed in the order presented). Re-assigning to the same name later overwrites (this is afterall an imperative tool).

There is also a ``do0`` macro, which returns the value of the first expression, instead of the last.


## ``forall``: nondeterministic evaluation

This is the multiple-body-expression tuple comprehension ``unpythonic.amb.forall``, wrapped into a macro:

```python
from unpythonic.syntax import macros, forall, insist, deny

out = forall[y << range(3),
             x << range(3),
             insist(x % 2 == 0),
             (x, y)]
assert out == ((0, 0), (2, 0), (0, 1), (2, 1), (0, 2), (2, 2))

# pythagorean triples
pt = forall[z << range(1, 21),   # hypotenuse
            x << range(1, z+1),  # shorter leg
            y << range(x, z+1),  # longer leg
            insist(x*x + y*y == z*z),
            (x, y, z)]
assert tuple(sorted(pt)) == ((3, 4, 5), (5, 12, 13), (6, 8, 10),
                             (8, 15, 17), (9, 12, 15), (12, 16, 20))
```

Assignment (with List-monadic magic) is ``var << iterable``. It transforms to ``choice(var=lambda e: iterable)``. It is only valid at the top level of the ``forall`` (e.g. not inside any possibly nested ``let``).

No need for ``lambda e: ...`` wrappers; variables are referred to by bare names without the ``e.`` prefix.

``insist`` and ``deny`` are not really macros; they are just the functions from ``unpythonic.amb``, re-exported for convenience.

### Note

We also provide ``forall_simple``, based purely on AST transformation, with real lexical variables. This is essentially Haskell's do-notation for Python, specialized to the List monad.

In the future, we may replace the current ``forall`` macro with this version. From the user perspective, the only difference is in error reporting; the function-based ``forall`` must internally simulate lexical scoping, whereas ``forall_simple`` just borrows Python's. In the function-based version, an undefined name will raise ``AttributeError``, whereas in ``forall_simple``, it will raise ``NameError``.


## ``λ``: because in the UTF-8 age λ ought to be called λ

...and multiple expressions ought to be the default. This is a rackety λ that has an implicit begin:

```python
from unpythonic.syntax import macros, λ

count = let((x, 0))[
          λ()[x << x + 1,
              x]]
assert count() == 1
assert count() == 2

myadd = λ(x, y)[print("myadding", x, y),
                x + y]
assert myadd(2, 3) == 5
```

(In the first example, returning ``x`` separately is redundant, because the assignment to the let environment already returns the new value, but it demonstrates the usage of multiple expressions in λ.)

Syntax is ``λ(arg0, ...)[body0, ...]``.

Current **limitations** are no ``*args``, ``**kwargs``, and no default values for arguments.

### Note

Version 0.9.1 adds an internal definition context, internally using ``do`` instead of ``begin``:

```python
myadd =  λ(x, y)[print("myadding", x, y),
                 localdef(tmp << x + y),
                 print("result is", tmp),
                 tmp]
assert myadd(2, 3) == 5
```

To write to an outer lexical environment, simply don't ``localdef`` the name:

```python
count = let((x, 0))[
          λ()[x << x + 1,  # no localdef; update the "x" of the "let"
              x]]
assert count() == 1
assert count() == 2
```


## ``prefix``: prefix function call syntax for Python

Write Python almost like Lisp!

Lexically inside a ``with prefix`` block, any literal tuple denotes a function call, unless quoted. The first element is the operator, the rest are arguments.

The rest is best explained by example:

```python
from unpythonic.syntax import macros, prefix, q, u, kw
from unpythonic import apply

with prefix:
    (print, "hello world")

    # quote operator q locally turns off the function-call transformation:
    t1 = (q, 1, 2, (3, 4), 5)  # q takes effect recursively
    x = 42
    t2 = (q, 17, 23, x)  # unlike in Lisps, x refers to its value even in a quote
    (print, t1, t2)

    # unquote operator u locally turns the transformation back on:
    t3 = (q, (u, print, 42), (print, 42), "foo", "bar")
    assert t3 == (q, None, (print, 42), "foo", "bar")

    # quotes nest; call transformation made when quote level == 0
    t4 = (q, (print, 42), (q, (u, u, print, 42)), "foo", "bar")
    assert t4 == (q, (print, 42), (None,), "foo", "bar")

    # Be careful:
    try:
        (x,)  # in a prefix block, this means "call the 0-arg function x"
    except TypeError:
        pass  # 'int' object is not callable
    (q, x)  # OK!

    # give named args with kw(...) [it's syntax, not really a function!]:
    def f(*, a, b):
        return (q, a, b)
    # in one kw(...), or...
    assert (f, kw(a="hi there", b="Tom")) == (q, "hi there", "Tom")
    # in several kw(...), doesn't matter
    assert (f, kw(a="hi there"), kw(b="Tom")) == (q, "hi there", "Tom")
    # in case of duplicate name across kws, rightmost wins
    assert (f, kw(a="hi there"), kw(b="Tom"), kw(b="Jerry")) == (q, "hi there", "Jerry")

    # give *args with unpythonic.fun.apply, like in Lisps:
    lst = [1, 2, 3]
    def g(*args):
        return args
    assert (apply, g, lst) == (q, 1, 2, 3)
    # lst goes last; may have other args first
    assert (apply, g, "hi", "ho", lst) == (q, "hi" ,"ho", 1, 2, 3)
```

This comboes with ``curry`` for an authentic *LisThEll* programming experience:

```python
from unpythonic.syntax import macros, curry, prefix, q, u, kw
from unpythonic import foldr, composerc as compose, cons, nil

with prefix, curry:  # important: apply prefix first, then curry
    mymap = lambda f: (foldr, (compose, cons, f), nil)
    double = lambda x: 2 * x
    (print, (mymap, double, (q, 1, 2, 3)))
    assert (mymap, double, (q, 1, 2, 3)) == ll(2, 4, 6)
```

*Toto, I've a feeling we're not in Python anymore.*

