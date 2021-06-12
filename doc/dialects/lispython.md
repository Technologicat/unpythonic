**Navigation**

- [README](../../README.md)
- [Pure-Python feature set](../features.md)
- [Syntactic macro feature set](../macros.md)
- [Examples of creating dialects using `mcpyrate`](../dialects.md)
  - **Lispython**
  - [Listhell](listhell.md)
  - [Pytkell](pytkell.md)
- [REPL server](../repl.md)
- [Troubleshooting](../troubleshooting.md)
- [Design notes](../design-notes.md)
- [Essays](../essays.md)
- [Additional reading](../readings.md)
- [Contribution guidelines](../../CONTRIBUTING.md)

<!-- markdown-toc start - Don't edit this section. Run M-x markdown-toc-refresh-toc -->
**Table of Contents**

- [Lispython: The love child of Python and Scheme](#lispython-the-love-child-of-python-and-scheme)
    - [Features](#features)
        - [The `Lispy` variant](#the-lispy-variant)
        - [The `Lispython` variant](#the-lispython-variant)
    - [What Lispython is](#what-lispython-is)
    - [Comboability](#comboability)
    - [Lispython and continuations (call/cc)](#lispython-and-continuations-callcc)
    - [Why extend Python?](#why-extend-python)
    - [PG's accumulator-generator puzzle](#pgs-accumulator-generator-puzzle)
    - [CAUTION](#caution)
    - [Etymology?](#etymology)

<!-- markdown-toc end -->

# Lispython: The love child of Python and Scheme

Python with automatic tail-call optimization, an implicit return statement, and automatically named, multi-expression lambdas.

Powered by [`mcpyrate`](https://github.com/Technologicat/mcpyrate/) and `unpythonic`.

```python
from unpythonic.dialects import dialects, Lispython  # noqa: F401

def factorial(n):
    def f(k, acc):
        if k == 1:
            return acc  # `return` is available to cause an early return
        f(k - 1, k * acc)
    f(n, acc=1)
assert factorial(4) == 24
factorial(5000)  # no crash

t = letrec[[evenp << (lambda x: (x == 0) or oddp(x - 1)),
            oddp << (lambda x: (x != 0) and evenp(x - 1))] in
           evenp(10000)]
assert t is True

square = lambda x: x**2
assert square(3) == 9
assert square.__name__ == "square"

# - local[name << value] makes an expression-local variable
g = lambda x: [local[y << 2 * x],
               y + 1]
assert g(10) == 21

c = cons(1, 2)
assert tuple(c) == (1, 2)
assert car(c) == 1
assert cdr(c) == 2
assert ll(1, 2, 3) == llist((1, 2, 3))
```

## Features

In terms of ``unpythonic.syntax``, we implicitly enable ``autoreturn``, ``tco``, ``multilambda``, ``namedlambda``, and ``quicklambda`` for the whole module:

  - In tail position, the ``return`` keyword can be omitted, like in Lisps.
    - In a `def`, the last statement at the top level of the `def` is in tail position.
    - If the tail position contains an expression, a ``return`` will be automatically injected, with that expression as the return value.
    - It is still legal to use `return` whenever you would in Python; this just makes the `return` keyword non-mandatory in places where a Lisp would not require it.
      - To be technically correct, Schemers and Racketeers should read this as, *"in places where a Lisp would not require explicitly invoking an escape continuation"*.
  - Automatic tail-call optimization (TCO) for both ``def`` and ``lambda``.
    - In a `def`, the last statement at the top level of the `def` is in tail position.
    - Tail positions *inside an expression* that itself appears in tail position are:
      - Both the `body` and `orelse` branches of an if-expression. (Exactly one of them runs, hence both are in tail position.)
      - The lexically last item of an `and`/`or` chain.
        - Note the analysis is performed at compile time, whence it does **not** care about the short-circuit behavior that occurs at run time.
      - The last item of a `do[]`.
      - The last item of an implicit `do[]` in a `let[]` where the body uses the extra bracket syntax. (All `let` constructs provided by `unpythonic.syntax` are supported.)
    - For the gritty details, see the syntax transformer `_transform_retexpr` in [`unpythonic.syntax.tailtools`](../../unpythonic/syntax/tailtools.py).
  - Multiple-expression lambdas, using bracket syntax, for example ``lambda x: [expr0, ...]``.
    - Brackets denote a multiple-expression lambda body. Technically, the brackets create a `do[]` environment.
    - If you want your lambda to have one expression that is a literal list, double the brackets: `lambda x: [[5 * x]]`.
  - Lambdas are automatically named whenever the machinery can figure out a name from the surrounding context.
    - When not, source location is auto-injected into the name.

The multi-expression lambda syntax uses ``do[]``, so it also allows lambdas to manage local variables using ``local[name << value]`` and ``delete[name]``. See the documentation of ``do[]`` for details.

If you need more stuff, `unpythonic` is effectively the standard library of Lispython, on top of what Python itself already provides.

There are **two variants** of the dialect, `Lispython` and `Lispy`.


### The `Lispy` variant

In the `Lispy` variant, that's it - the dialect changes the semantics only. Nothing is imported implicitly, except the macros injected by the dialect template (to perform the whole-module semantic changes at macro expansion time).

This is the pythonic variant of Lispython, keeping in line with *explicit is better than implicit*. The rule is: *if a name appears in user code, it must be defined explicitly*, as is usual in Python.

Note this implies that you must **explicitly import** the `local[]` macro if you want to declare local variables in a multiple-expression lambda, and the `fn[]` macro if you want to take advantage of the implicit `quicklambda`. Both are available in `unpythonic.syntax`, as usual.

The point of the implicit `quicklambda` is that all invocations of `fn[]`, if there are any, will expand early, so that other macros that expect lambdas to be in standard Python notation will get exactly that. This includes other macros invoked by the dialect definition, namely `multilambda`, `namedlambda`, and `tco`.

The main point of `Lispy`, compared to plain Python, is automatic TCO. The ability to omit `return` is a minor convenience, and the other three features only improve the usability of lambdas.


### The `Lispython` variant

In the `Lispython` variant, we implicitly import some macros and functions to serve as dialect builtins, keeping in line with expectations for a ~language in the~ *somewhat distant relative of the* Lisp family:

  - ``cons``, ``car``, ``cdr``, ``ll``, ``llist``, ``nil``, ``prod``.
  - All ``let[]`` and ``do[]`` constructs from ``unpythonic.syntax``.
  - The underscore: e.g. `fn[_ * 3]` becomes `lambda x: x * 3`, and `fn[_ * _]` becomes `lambda x, y: x * y`.
  - ``dyn``, for dynamic assignment.
  - ``Values``, for returning multiple values and/or named return values. (This ties in to `unpythonic`'s function composition subsystem, e.g. `curry`, `unfold`, `iterate`, the `pipe` family, the `compose` family, and the `with continuations` macro.)

For detailed documentation of the language features, see [``unpythonic.syntax``](../macros.md), especially the macros ``tco``, ``autoreturn``, ``multilambda``, ``namedlambda``, ``quicklambda``, ``let`` and ``do``.

The dialect builtin ``let[]`` constructs are ``let``, ``letseq``, ``letrec``, the decorator versions ``dlet``, ``dletseq``, ``dletrec``, the block versions (decorator, call immediately, replace def'd name with result) ``blet``, ``bletseq``, ``bletrec``, and the code-splicing variants ``let_syntax`` and ``abbrev``. Bindings may be made using any syntax variant supported by ``unpythonic.syntax``.

The dialect builtin ``do[]`` constructs are ``do`` and ``do0``.


## What Lispython is

Lispython is a dialect of Python implemented via macros and a thin whole-module AST transformation. The dialect definition lives in [`unpythonic.dialects.lispython`](../../unpythonic/dialects/lispython.py). Usage examples can be found in the unit tests, [for `Lispy`](../../unpythonic/dialects/tests/test_lispy.py) and [for `Lispython`](../../unpythonic/dialects/tests/test_lispython.py).

Lispython essentially makes Python feel slightly more lispy, in parts where that makes sense.

It's also a minimal example of how to make an AST-transforming dialect.

We take the approach of a relatively thin layer of macros (and underlying functions that implement the actual functionality), minimizing magic as far as reasonably possible.

Performance is only a secondary concern; performance-critical parts fare better at the other end of [the wide spectrum](https://en.wikipedia.org/wiki/Wide-spectrum_language), with [Cython](http://cython.org/). Lispython is for [the remaining 80%](https://en.wikipedia.org/wiki/Pareto_principle), where the bottleneck is human developer time.


## Comboability

The aforementioned block macros are enabled implicitly for the whole module; this is the essence of the Lispython dialect. Other block macros can still be invoked manually in the user code.

Of the other block macros in ``unpythonic.syntax``, code written in Lispython supports only ``continuations``. ``autoref`` should also be harmless enough (will expand too early, but shouldn't matter).

``prefix``, ``autocurry``, ``lazify`` and ``envify`` are **not compatible** with the ordering of block macros implicit in the Lispython dialect.

``prefix`` is an outside-in macro that should expand first, so it should be placed in a lexically outer position with respect to the ones Lispython invokes implicitly; but nothing can be more outer than the dialect template.

The other three are inside-out macros that should expand later, so similarly, also they should be placed in a lexically outer position.

Basically, any block macro that can be invoked *lexically inside* a ``with tco`` block will work, the rest will not.

If you need e.g. a lazy Lispython, the way to do that is to make a copy of the dialect module, change the dialect template to import the ``lazify`` macro, and then include a ``with lazify`` in the appropriate position, outside the ``with namedlambda`` block. Other customizations can be made similarly.


## Lispython and continuations (call/cc)

Just use ``with continuations`` from ``unpythonic.syntax`` where needed. See its documentation for usage.

Lispython works with ``with continuations``, because:

  - Nesting ``with continuations`` within a ``with tco`` block is allowed, for the specific reason of supporting continuations in Lispython.

    The dialect's implicit ``with tco`` will just skip the ``with continuations`` block (``continuations`` implies TCO).

  - ``autoreturn``, ``quicklambda`` and ``multilambda`` are outside-in macros, so although they will be in a lexically outer position with respect to the manually invoked ``with continuations`` in the user code, this is correct (because being on the outside, they run before ``continuations``, as they should).

  - The same applies to the outside-in pass of ``namedlambda``. Its inside-out pass, on the other hand, must come after ``continuations``, which it does, since the dialect's implicit ``with namedlambda`` is in a lexically outer position with respect to the ``with continuations``.

Be aware, though, that the combination of the ``autoreturn`` implicit in the dialect and ``with continuations`` might have usability issues, because ``continuations`` handles tail calls specially (the target of a tail-call in a ``continuations`` block must be continuation-enabled; see the documentation of ``continuations``), and ``autoreturn`` makes it visually slightly less clear which positions are in fact tail calls (since no explicit ``return``). Also, the top level of a ``with continuations`` block may not use ``return`` - while Lispython's implicit ``autoreturn`` happily auto-injects a ``return`` to whatever is the last statement in any particular function.


## Why extend Python?

[Racket](https://racket-lang.org/) is an excellent Lisp, especially with [sweet](https://docs.racket-lang.org/sweet/), sweet expressions [[1]](https://sourceforge.net/projects/readable/) [[2]](https://srfi.schemers.org/srfi-110/srfi-110.html) [[3]](https://srfi.schemers.org/srfi-105/srfi-105.html), not to mention extremely pythonic. The word is *rackety*; the syntax of the language comes with an air of Zen minimalism (as perhaps expected of a descendant of Scheme), but the focus on *batteries included* and understandability are remarkably similar to the pythonic ideal. Racket even has an IDE (DrRacket) and an equivalent of PyPI, and the documentation is simply stellar.

Python, on the other hand, has a slight edge in usability to the end-user programmer, and importantly, a huge ecosystem of libraries, second to ``None``. Python is where science happens (unless you're in CS). Python is an almost-Lisp that has delivered on [the productivity promise](http://paulgraham.com/icad.html) of Lisp. Python also gets many things right, such as well developed support for lazy sequences, and decorators.

In certain other respects, Python the base language leaves something to be desired, if you have been exposed to Racket (or Haskell, but that's a different story). Writing macros is harder due to the irregular syntax, but thankfully macro expanders already exist, and any set of macros only needs to be created once.

Practicality beats purity ([ZoP §9](https://www.python.org/dev/peps/pep-0020/)): hence, fix the minor annoyances that would otherwise quickly add up, and reap the benefits of both worlds. If Python is software glue, Lispython is an additive that makes it flow better.


## PG's accumulator-generator puzzle

The puzzle was posted by Paul Graham in 2002, in the essay [Revenge of the Nerds](http://paulgraham.com/icad.html). It asks to implement, in the shortest code possible, an accumulator-generator. The desired behavior is:

```python
f = foo(10)
assert f(1) == 11
assert f(1) == 12
assert f(5) == 17
```

(The original name of the function is literally `foo`; we have chosen to keep the name, although [nowadays one should do better than that](https://docs.racket-lang.org/style/reference-style.html#%28part._examples-style%29).)

Even Lispython can do no better than this let-over-lambda (here using the haskelly let-in syntax to establish let-bindings):

```python
foo = lambda n0: let[[n << n0] in
                     (lambda i: n << n + i)]
```

This still sets up a separate place for the accumulator (that is, separate from the argument of the outer function). The pure Python 3 solution avoids that, but needs many lines:

```python
def foo(n):
    def accumulate(i):
        nonlocal n
        n += i
        return n
    return accumulate
```

The Python 3.8+ solution, using the new walrus operator, is one line shorter:

```python
def foo(n):
    def accumulate(i):
        nonlocal n
        return (n := n + i)
    return accumulate
```

This is rather clean, but still needs the `nonlocal` declaration, which is a statement.

If we abbreviate ``accumulate`` as a lambda, it needs a ``let`` environment to write in, to use `unpythonic`'s expression-assignment (`name << value`).

But see ``envify`` in ``unpythonic.syntax``, which shallow-copies function arguments into an `env` implicitly:

```python
from unpythonic.syntax import macros, envify

with envify:
    def foo(n):
        return lambda i: n << n + i
```

or as a one-liner:

```python
with envify:
    foo = lambda n: lambda i: n << n + i
```

``envify`` is not part of the Lispython dialect definition, because this particular, perhaps rarely used, feature is not really worth a global performance hit whenever a function is entered.

Note that ``envify`` is **not** compatible with Lispython, because it would need to appear in a lexically outer position compared to macros already invoked by the dialect template. If you need an envified Lispython, copy `unpythonic/dialects/lispython.py` and modify the template therein. [The xmas tree combo](../macros.md#the-xmas-tree-combo) says `envify` should come lexically after `multilambda`, but before `namedlambda`.


## CAUTION

No instrumentation exists (or is even planned) for the Lispython layer; you'll have to use regular Python tooling to profile, debug, and such. The Lispython layer should be thin enough for this not to be a major problem in practice.


## Etymology?

*Lispython* is obviously made of two parts: Python, and...

![mascot](lis.png)
