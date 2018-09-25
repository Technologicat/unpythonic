# autocurry: Automatic currying for Python

Uses [MacroPy](https://github.com/azazel75/macropy), from PyPI package ``macropy3``. Because macro expansion occurs at import time, the usage example `main.py` cannot be run directly. Instead, run it via the bootstrap script `run.py`.

This macro allows to:

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

