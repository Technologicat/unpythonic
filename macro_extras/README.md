# Macro extras

These optional features are built on [MacroPy](https://github.com/azazel75/macropy), from PyPI package ``macropy3``.

Because macro expansion occurs at import time, the usage example `main.py` cannot be run directly. Instead, run it via the bootstrap script `run.py`, or use the included [generic MacroPy3 bootstrapper](macropy3). (Usage: `./macropy3 main`; see `-h` for options.)

There is no abbreviation for ``memoize(lambda: ...)``, because ``MacroPy`` itself already provides ``lazy`` and ``interned``.

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

letrec((evenp, lambda x: (x == 0) or oddp(x - 1)),  # mutually recursive binding, sequentially evaluated
       (oddp,  lambda x: (x != 0) and evenp(x - 1)))[
         print(evenp(42))]
```

Syntax is similar to ``unpythonic.lispylet``, but no quotes around variable names in bindings, and no ``lambda e: ...`` wrappers. Bindings are referred to by bare names like in Lisps, no ``e.`` prefix.

Note the ``[...]``; these are ``expr`` macros. The bindings are given as macro arguments as ``((name, value), ...)``, the body goes into the ``[...]``.

``let`` and ``letseq`` are wholly implemented as AST transformations. Just like in Lisps, ``letseq`` (Scheme/Racket ``let*``) expands into a sequence of nested ``let`` expressions, which expand to lambdas.

``letrec`` expands into ``unpythonic.lispylet.letrec``, implicitly inserting ``lambda e: ...`` around each value and the body, and (for both the values and the body) transforming ``x`` to ``e.x`` for all ``x`` in bindings. The implicit environment argument ``e`` is actually named using a gensym, so lexically outer environments automatically show through.

Nesting works also in ``letrec``, because (as of v1.1.0) MacroPy3 expands macros in an inside-out order:

```python
from unpythonic import begin

letrec((z, 1))[
  begin(print(z),
        letrec((z, 2))[
          print(z)])]  # (be careful with the parentheses!)
```

Here the ``z`` in the inner scope expands to the inner environment's ``z``, which makes the outer expansion leave it alone. (This works by transforming only ``ast.Name`` nodes, stopping recursion when an ``ast.Attribute`` is encountered.)


## ``aif``: anaphoric if for Python

This is mainly of interest as a point of [comparison with Racket](https://github.com/Technologicat/python-3-scicomp-intro/blob/master/examples/beyond_python/aif.rkt); ``aif`` is about the simplest macro that relies on either the lack of hygiene or breaking thereof.

```python
from aif import macros, aif

aif[2*21,
    print("it is {}".format(it)),
    print("it is False")]
```

Syntax is ``aif[test, then, otherwise]``. The magic identifier ``it`` refers to the test result while (lexically) inside the ``aif``, and does not exist outside the ``aif``.


## ``cond``: the missing ``elif`` for ``a1 if cond else a2``

Now lambdas too can have multi-branch conditionals, yet remain human-readable:

```python
from cond import macros, cond

answer = lambda x: cond[x == 2, "two",
                        x == 3, "three",
                        "something else"]
print(answer(42))
```

Syntax is ``cond[test1, then1, test2, then2, ..., otherwise]``. Expansion raises an error if the ``otherwise`` branch is missing.


## ``do`` as a macro: stuff imperative code into a lambda, *with style*

The ``letm`` module also provides an ``expr`` macro wrapper for ``unpythonic.seq.do``, similar to and with much the same advantages as the macro variants of the let contructs:

```python
from letm import macros, do

y = do[x << 17,
       print(x),
       x << 23,
       x]
print(y)  # --> 23
```

Assignment to the ``do`` environment is denoted ``var << value``. This is triggered when a line is a ``BinOp`` of type ``LShift``, and the left-hand operand is a bare name.

Like in the macro ``letrec``, no ``lambda e: ...`` wrappers. These are inserted automatically, so the lines are only evaluated as the underlying ``seq.do`` actually runs.

When expanding bare names, ``do`` behaves like ``letseq``; assignments **above** the current line are in effect (and have been performed in the order presented). Re-assigning to the same name later overwrites (this is afterall an imperative tool).

*Whether the language with these additions is Python anymore, is another question.*

