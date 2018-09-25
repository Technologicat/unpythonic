# Macro extras

These optional features use [MacroPy](https://github.com/azazel75/macropy), from PyPI package ``macropy3``. Because macro expansion occurs at import time, the usage example `main.py` cannot be run directly. Instead, run it via the bootstrap script `run.py`.

## autocurry: Automatic currying for Python

```python
from autocurry import macros, curry
from unpythonic import foldr, composerc as compose, cons, nil

with curry:
    mymap = lambda f: foldr(compose(cons, f), nil)
    double = lambda x: 2 * x
    print(mymap(double, (1, 2, 3)))
```

All function calls *lexically* inside a ``with curry`` block are automatically curried, somewhat like in Haskell, or in ``#lang`` [``spicy``](https://github.com/Technologicat/spicy).

**CAUTION**: Builtins are uninspectable, so cannot be curried. In a ``with curry`` block, ``unpythonic.fun.curry`` runs in a special mode that no-ops on uninspectable functions instead of raising ``TypeError`` as usual. This special mode is enabled for the *dynamic extent* of the ``with curry`` block.


## letm: let, letseq, letrec for Python, as macros

Properly lexically scoped ``let`` constructs, no boilerplate:

```python
from letm import macros, let, letseq, letrec

let((x, 17),  # parallel binding, i.e. bindings don't see each other
    (y, 23))[
      print(x, y)]

letseq((x, 1),  # sequential binding, i.e. Scheme/Racket let*
       (y, x+1))[
         print(x, y)]

letrec((evenp, lambda x: (x == 0) or oddp(x - 1)),
       (oddp,  lambda x: (x != 0) and evenp(x - 1)))[
         print(evenp(42))]
```

Syntax is similar to ``unpythonic.lispylet``, but no quotes around variable names in bindings, and no ``lambda e: ...`` wrappers. Bindings are referred to by bare names like in Lisps, no ``e.`` prefix.

Note the ``[...]``; these are ``expr`` macros. The bindings are given as macro arguments (in ``((name, value), ...)``), the body goes into the ``[...]``.

``let`` and ``letseq`` are wholly implemented as AST transformations. Just like in Lisps, ``letseq`` (Scheme/Racket ``let*``) expands into nested let expressions.

``letrec`` expands into ``unpythonic.lispylet.letrec``, implicitly inserting ``lambda e: ...`` around each value and the body, and (for both the values and the body) transforming ``x`` to ``e.x`` for all ``x`` in bindings. The implicit environment argument ``e`` is actually named using a gensym, so lexically outer environments automatically show through.

Nesting works also in ``letrec``, because (as of v1.1.0) MacroPy3 expands macros in an inside-out order::

```python
from unpythonic import begin

letrec((z, 1))[
  begin(print(z),
        letrec((z, 2))[
          print(z)])]  # (be careful with the parentheses!)
```

Here the ``z`` in the inner scope expands to the inner environment's ``z``, which makes the outer expansion leave it alone. (This works by transforming only ``ast.Name`` nodes, stopping recursion when an ``ast.Attribute`` is encountered.)

