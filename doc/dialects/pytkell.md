## Pytkell: Because it's good to have a kell

Python with automatic currying and implicitly lazy functions.

Powered by [`mcpyrate`](https://github.com/Technologicat/mcpyrate/) and `unpythonic`.

```python
from unpythonic.dialects import dialects, Pytkell  # noqa: F401

from operator import add, mul

def addfirst2(a, b, c):
    return a + b
assert addfirst2(1)(2)(1 / 0) == 3

assert tuple(scanl(add, 0, (1, 2, 3))) == (0, 1, 3, 6)
assert tuple(scanr(add, 0, (1, 2, 3))) == (0, 3, 5, 6)

my_sum = foldl(add, 0)
my_prod = foldl(mul, 1)
my_map = lambda f: foldr(compose(cons, f), nil)
assert my_sum(range(1, 5)) == 10
assert my_prod(range(1, 5)) == 24
assert tuple(my_map((lambda x: 2 * x), (1, 2, 3))) == (2, 4, 6)

pt = forall[z << range(1, 21),   # hypotenuse
            x << range(1, z + 1),  # shorter leg
            y << range(x, z + 1),  # longer leg
            insist(x * x + y * y == z * z),
            (x, y, z)]
assert tuple(sorted(pt)) == ((3, 4, 5), (5, 12, 13), (6, 8, 10),
                             (8, 15, 17), (9, 12, 15), (12, 16, 20))

factorials = scanl(mul, 1, s(1, 2, ...))  # 0!, 1!, 2!, ...
assert last(take(6, factorials)) == 120

x = let[(a, 21) in 2 * a]
assert x == 42
x = let[2 * a, where(a, 21)]
assert x == 42
```

### Features

In terms of ``unpythonic.syntax``, we implicitly enable ``curry`` and ``lazify`` for the whole module.

We also import some macros and functions to serve as dialect builtins:

  - All ``let[]`` and ``do[]`` constructs from ``unpythonic.syntax``
  - ``lazy[]`` and ``lazyrec[]`` for manual lazification of atoms and data structure literals, respectively
  - If-elseif-else expression ``cond[]``
  - Nondeterministic evaluation ``forall[]`` (do-notation in the List monad)
  - Function composition, ``compose`` (like Haskell's ``.`` operator), aliased to `unpythonic`'s currying right-compose ``composerc``
  - Linked list utilities ``cons``, ``car``, ``cdr``, ``ll``, ``llist``, ``nil``
  - Folds and scans ``foldl``, ``foldr``, ``scanl``, ``scanr``
  - Memoization ``memoize``, ``gmemoize``, ``imemoize``, ``fimemoize``
  - Functional updates ``fup`` and ``fupdate``
  - Immutable dict ``frozendict``
  - Mathematical sequences ``s``, ``m``, ``mg``
  - Iterable utilities ``islice`` (`unpythonic`'s version), ``take``, ``drop``, ``split_at``, ``first``, ``second``, ``nth``, ``last``
  - Function arglist reordering utilities ``flip``, ``rotate``

For detailed documentation of the language features, see [``unpythonic.syntax``](https://github.com/Technologicat/unpythonic/tree/master/doc/macros.md).

The builtin ``let[]`` constructs are ``let``, ``letseq``, ``letrec``, the decorator versions ``dlet``, ``dletseq``, ``dletrec``, the block versions (decorator, call immediately, replace `def`'d name with result) ``blet``, ``bletseq``, ``bletrec``. Bindings may be made using any syntax variant supported by ``unpythonic.syntax``.

The builtin ``do[]`` constructs are ``do`` and ``do0``.

If you need more stuff, `unpythonic` is effectively the standard library of Pytkell, on top of what Python itself already provides.


### What Pytkell is

Pytkell is a dialect of Python implemented via macros and a thin whole-module AST transformation. The dialect definition lives in [`unpythonic.dialects.pytkell`](../../unpythonic/dialects/lispython.py). Usage examples can be found in [the unit tests](../../unpythonic/dialects/tests/test_pytkell.py).

Pytkell essentially makes Python feel slightly more haskelly.

It's also a minimal example of how to make an AST-transforming dialect.


### Comboability

**Not** comboable with most of the block macros in ``unpythonic.syntax``, because ``curry`` and ``lazify`` appear in the dialect template, hence at the lexically outermost position.

Only outside-in macros that should expand after ``lazify`` has recorded its userlambdas (currently, `unpythonic` provides no such macros) and inside-out macros that should expand before ``curry`` (there are two, namely ``tco`` and ``continuations``) can be used in programs written in the Pytkell dialect.


### CAUTION

No instrumentation exists (or is even planned) for the Pytkell layer; you'll have to use regular Python tooling to profile, debug, and such.

This layer is not quite as thin as Lispython's, but the dialect is not intended for serious use, either.


### Etymology?

The other obvious contraction, *Pyskell*, sounds like a serious programming language - or possibly the name of a fantasy airship - whereas *Pytkell* is obviously something quickly thrown together for system testing.
