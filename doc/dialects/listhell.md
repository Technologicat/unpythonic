**Navigation**

- [README](../../README.md)
- [Pure-Python feature set](../features.md)
- [Syntactic macro feature set](../macros.md)
- [Examples of creating dialects using `mcpyrate`](../dialects.md)
  - [Lispython](lispython.md)
  - **Listhell**
  - [Pytkell](pytkell.md)
- [REPL server](../repl.md)
- [Troubleshooting](../troubleshooting.md)
- [Design notes](../design-notes.md)
- [Additional reading](../readings.md)
- [Contribution guidelines](../../CONTRIBUTING.md)

<!-- markdown-toc start - Don't edit this section. Run M-x markdown-toc-refresh-toc -->
**Table of Contents**

- [Listhell: It's not Lisp, it's not Python, it's not Haskell](#listhell-its-not-lisp-its-not-python-its-not-haskell)
    - [Features](#features)
    - [What Listhell is](#what-listhell-is)
    - [Comboability](#comboability)
    - [Notes](#notes)
    - [CAUTION](#caution)
    - [Etymology?](#etymology)

<!-- markdown-toc end -->

# Listhell: It's not Lisp, it's not Python, it's not Haskell

Python with prefix syntax for function calls, and automatic currying.

Powered by [`mcpyrate`](https://github.com/Technologicat/mcpyrate/) and `unpythonic`.

```python
from unpythonic.dialects import dialects, Listhell  # noqa: F401

from unpythonic import foldr, cons, nil, ll

(print, "hello from Listhell")

double = lambda x: 2 * x
my_map = lambda f: (foldr, (compose, cons, f), nil)
assert (my_map, double, (q, 1, 2, 3)) == (ll, 2, 4, 6)
```

## Features

In terms of ``unpythonic.syntax``, we implicitly enable ``prefix`` and ``curry`` for the whole module.

The following are dialect builtins:

  - ``apply``, aliased to ``unpythonic.fun.apply``
  - ``compose``, aliased to unpythonic's currying right-compose ``composerc``
  - ``q``, ``u``, ``kw`` for the prefix syntax (note these are not `mcpyrate`'s
    ``q`` and ``u``, but those from `unpythonic.syntax`, specifically for ``prefix``)

For detailed documentation of the language features, see [``unpythonic.syntax``](https://github.com/Technologicat/unpythonic/tree/master/doc/macros.md).

If you need more stuff, `unpythonic` is effectively the standard library of Listhell, on top of what Python itself already provides.


## What Listhell is

Listhell is a dialect of Python implemented via macros and a thin whole-module AST transformation. The dialect definition lives in [`unpythonic.dialects.listhell`](../../unpythonic/dialects/listhell.py). Usage examples can be found in [the unit tests](../../unpythonic/dialects/tests/test_listhell.py).

Listhell is essentially a demonstration of how Python could look, if it had Lisp's prefix syntax for function calls and Haskell's automatic currying.

It's also a minimal example of how to make an AST-transforming dialect.


## Comboability

Only outside-in macros that should expand after ``autocurry`` (currently, `unpythonic` provides no such macros) and inside-out macros that should expand before ``autocurry`` (there are two, namely ``tco`` and ``continuations``) can be used in programs written in the Listhell dialect.


## Notes

If you like the idea and want autocurry for a Lisp, try
[spicy](https://github.com/Technologicat/spicy) for [Racket](https://racket-lang.org/).

## CAUTION

Not intended for serious use.

## Etymology?

Prefix syntax of **Lis**p, speed of Py**th**on, and readability of Hask**ell**, all in one.
