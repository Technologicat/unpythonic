**Navigation**

- [README](../README.md)
- **Pure-Python feature set**
- [Syntactic macro feature set](macros.md)
- [Examples of creating dialects using `mcpyrate`](dialects.md)
- [REPL server](repl.md)
- [Troubleshooting](troubleshooting.md)
- [Design notes](design-notes.md)
- [Essays](essays.md)
- [Additional reading](readings.md)
- [Contribution guidelines](../CONTRIBUTING.md)

# Unpythonic: Python meets Lisp and Haskell

This is the pure-Python API of `unpythonic`. Most features listed here need no macros, and are intended to be used directly.

The exception are the features marked **[M]**, which are primarily intended as a code generation target API for macros. See the [documentation for syntactic macros](macros.md) for details. Usually the relevant macro has the same name as the underlying implementation; for example, `unpythonic.do` is the implementation, while `unpythonic.syntax.do` is the macro. The purpose of the macro layer is to improve ease of use by removing accidental complexity, thus providing a more human-readable source code representation that compiles to calls to the underlying API. If you don't want to depend on `mcpyrate`, feel free to use also these APIs as defined below (though, this may be less convenient).

### Features

[**Bindings**](#bindings)
- [``let``, ``letrec``: local bindings in an expression](#let-letrec-local-bindings-in-an-expression) **[M]**
  - [``let``](#let)
  - [``dlet``, ``blet``](#dlet-blet): *let-over-def*, like the classic let-over-lambda.
  - [``letrec``](#letrec)
  - [Lispylet: alternative syntax](#lispylet-alternative-syntax) **[M]**
- [``env``: the environment](#env-the-environment)
- [``assignonce``](#assignonce), a relative of ``env``.
- [``dyn``: dynamic assignment](#dyn-dynamic-assignment) a.k.a. parameterize, special variables, fluid variables, "dynamic scoping".

[**Containers**](#containers)
- [``frozendict``: an immutable dictionary](#frozendict-an-immutable-dictionary)
- [`cons` and friends: pythonic lispy linked lists](#cons-and-friends-pythonic-lispy-linked-lists)
- [``box``: a mutable single-item container](#box-a-mutable-single-item-container)
  - [``box``](#box)
  - [``Some``](#some): immutable box, to explicitly indicate the presence of a value.
  - [``ThreadLocalBox``](#threadlocalbox)
- [``Shim``: redirect attribute accesses](#shim-redirect-attribute-accesses)
- [Container utilities](#container-utilities): ``get_abcs``, ``in_slice``, ``index_in_slice``

[**Sequencing**](#sequencing), run multiple expressions in any expression position (incl. inside a ``lambda``).
- [``begin``: sequence side effects](#begin-sequence-side-effects)
- [``do``: stuff imperative code into an expression](#do-stuff-imperative-code-into-an-expression) **[M]**
- [``pipe``, ``piped``, ``lazy_piped``: sequence functions](#pipe-piped-lazy_piped-sequence-functions)
  - [``pipe``](#pipe)
  - [``piped``](#piped)
  - [``lazy_piped``](#lazy_piped)

[**Batteries**](#batteries) missing from the standard library.
- [**Batteries for functools**](#batteries-for-functools): `memoize`, `curry`, `compose`, `withself`, `fix` and more.
  - [``memoize``](#memoize): a detailed explanation of the memoizer.
  - [``curry``](#curry): a detailed explanation of the curry utility.
  - [``curry`` and reduction rules](#curry-and-reduction-rules): we provide some extra features for bonus Haskellness.
  - [``fix``: break infinite recursion cycles](#fix-break-infinite-recursion-cycles)
- [**Batteries for itertools**](#batteries-for-itertools): multi-input folds, scans (lazy partial folds); unfold; lazy partial unpacking of iterables, etc.
- [**Batteries for network programming**](#batteries-for-network-programming): message protocol, PTY/socket proxy, etc.
- [``islice``: slice syntax support for ``itertools.islice``](#islice-slice-syntax-support-for-itertoolsislice)
- [`gmemoize`, `imemoize`, `fimemoize`: memoize generators](#gmemoize-imemoize-fimemoize-memoize-generators), iterables and iterator factories.
- [``fup``: functional update; ``ShadowedSequence``](#fup-functional-update-shadowedsequence): like ``collections.ChainMap``, but for sequences.
- [``view``: writable, sliceable view into a sequence](#view-writable-sliceable-view-into-a-sequence) with scalar broadcast on assignment.
- [``mogrify``: update a mutable container in-place](#mogrify-update-a-mutable-container-in-place)
- [``s``, ``imathify``, ``gmathify``: lazy mathematical sequences with infix arithmetic](#s-imathify-gmathify-lazy-mathematical-sequences-with-infix-arithmetic)
- [``sym``, ``gensym``, ``Singleton``: symbols and singletons](#sym-gensym-Singleton-symbols-and-singletons)

[**Control flow tools**](#control-flow-tools)
- [``trampolined``, ``jump``: tail call optimization (TCO) / explicit continuations](#trampolined-jump-tail-call-optimization-tco--explicit-continuations)
- [``looped``, ``looped_over``: loops in FP style (with TCO)](#looped-looped_over-loops-in-fp-style-with-tco)
- [``gtrampolined``: generators with TCO](#gtrampolined-generators-with-tco): tail-chaining; like ``itertools.chain``, but from inside a generator.
- [``catch``, ``throw``: escape continuations (ec)](#catch-throw-escape-continuations-ec) (as in [Lisp's `catch`/`throw`](http://www.gigamonkeys.com/book/the-special-operators.html), unlike C++ or Java)
  - [``call_ec``: first-class escape continuations](#call_ec-first-class-escape-continuations), like Racket's ``call/ec``.
- [``forall``: nondeterministic evaluation](#forall-nondeterministic-evaluation), a tuple comprehension with multiple body expressions.
- [``handlers``, ``restarts``: conditions and restarts](#handlers-restarts-conditions-and-restarts), a.k.a. **resumable exceptions**.
- [``generic``, ``typed``, ``isoftype``: multiple dispatch](#generic-typed-isoftype-multiple-dispatch): create generic functions with type annotation syntax; also some friendly utilities.

[**Exception tools**](#exception-tools)
- [``raisef``, ``tryf``: ``raise`` and ``try`` as functions](#raisef-tryf-raise-and-try-as-functions), useful inside a lambda.
- [``equip_with_traceback``](#equip-with-traceback), equip a manually created exception instance with a traceback. 
- [``async_raise``: inject an exception to another thread](#async_raise-inject-an-exception-to-another-thread) *(CPython only)*
- [`reraise_in`, `reraise`: automatically convert exception types](#reraise_in-reraise-automatically-convert-exception-types)

[**Function call and return value tools**](#function-call-and-return-value-tools)
- [``def`` as a code block: ``@call``](#def-as-a-code-block-call): run a block of code immediately, in a new lexical scope.
- [``@callwith``: freeze arguments, choose function later](#callwith-freeze-arguments-choose-function-later)
- [`Values`: multiple and named return values](#values-multiple-and-named-return-values)
  - [`valuify`](#valuify): convert pythonic multiple-return-values idiom of `tuple` into `Values`.

[**Numerical tools**](#numerical-tools)
  - [`almosteq`: floating-point almost-equality](#almosteq-floating-point-almost-equality)
  - [`fixpoint`: arithmetic fixed-point finder](#fixpoint-arithmetic-fixed-point-finder)
  - [`partition_int`, `partition_int_triangular`: partition integers](#partition_int-partition_int_triangular-partition-integers)
  - [``ulp``: unit in last place](#ulp-unit-in-last-place)

[**Other**](#other)
- [``callsite_filename``](#callsite-filename)
- [``safeissubclass``](#safeissubclass), convenience function.
- [``pack``: multi-arg constructor for tuple](#pack-multi-arg-constructor-for-tuple)
- [``namelambda``: rename a function](#namelambda-rename-a-function)
- [``timer``: a context manager for performance testing](#timer-a-context-manager-for-performance-testing)
- [``getattrrec``, ``setattrrec``: access underlying data in an onion of wrappers](#getattrrec-setattrrec-access-underlying-data-in-an-onion-of-wrappers)
- [``arities``, ``kwargs``, ``resolve_bindings``: Function signature inspection utilities](#arities-kwargs-resolve_bindings-function-signature-inspection-utilities)
- [``Popper``: a pop-while iterator](#popper-a-pop-while-iterator)

For many examples, see [the unit tests](unpythonic/tests/), the docstrings of the individual features, and this guide.

*This document doubles as the API reference, but despite maintenance on a best-effort basis, may occasionally be out-of-date at places. In case of conflicts in documentation, believe the unit tests first; specifically the code, not necessarily the comments. Everything else (comments, docstrings and this guide) should agree with the unit tests. So if something fails to work as advertised, check what the tests say - and optionally file an issue on GitHub so that the documentation can be fixed.*

**This document is up-to-date for v0.15.0.**

## Bindings

Tools to bind identifiers in ways not ordinarily supported by Python.

### ``let``, ``letrec``: local bindings in an expression

**NOTE**: *This is primarily a code generation target API for the ``let[]`` family of [macros](macros.md), which make the constructs easier to use, and make the code look almost like normal Python. Below is the documentation for the raw API.*

The `let` constructs introduce bindings local to an expression, like Scheme's ``let`` and ``letrec``.

#### ``let``

In ``let``, the bindings are independent (do not see each other). A binding is of the form ``name=value``, where ``name`` is a Python identifier, and ``value`` is any expression.

Use a `lambda e: ...` to supply the environment to the body:

```python
# These six are the constructs covered in this section of documentation.
from unpythonic import let, letrec, dlet, dletrec, blet, bletrec

u = lambda lst: let(seen=set(),
                    body=lambda e:
                           [e.seen.add(x) or x for x in lst if x not in e.seen])
L = [1, 1, 3, 1, 3, 2, 3, 2, 2, 2, 4, 4, 1, 2, 3]
u(L)  # --> [1, 3, 2, 4]
```

Generally speaking, `body` is a one-argument function, which takes in the environment instance as the first positional parameter (by convention, named `e` or `env`). In typical inline usage, `body` is `lambda e: expr`.

*Let over lambda*. Here the inner ``lambda`` is the definition of the function ``counter``:

```python
from unpythonic import let, begin

counter = let(x=0,
              body=lambda e:
                     lambda:
                       begin(e.set("x", e.x + 1),  # can also use e << ("x", e.x + 1)
                             e.x))
counter()  # --> 1
counter()  # --> 2
```

For comparison, with the macro API, this becomes:

```python
from unpythonic.syntax import macros, let, do

counter = let[[x << 0] in
              (lambda:
                 do[x << x + 1,
                    x])]
counter()  # --> 1
counter()  # --> 2
```

(*The parentheses around the lambda are just to make the expression into syntactically valid Python. You can also use brackets instead, denoting a multiple-expression `let` body - which is also valid even if there is just one expression. The `do` makes a multiple-expression `lambda` body. For more, see the [macro documentation](macros.md).*)

Compare the sweet-exp [Racket](http://racket-lang.org/) (see [SRFI-110](https://srfi.schemers.org/srfi-110/srfi-110.html) and [sweet](https://docs.racket-lang.org/sweet/)):

```racket
define counter
  let ([x 0])  ; In Racket, the (λ (e) (...)) in "let" is implicit, and needs no explicit "e".
    λ ()       ; Racket's λ has an implicit (begin ...), so we don't need a begin.
      set! x {x + 1}
      x
counter()  ; --> 1
counter()  ; --> 2
```

#### ``dlet``, ``blet``

*Let over def* decorator ``@dlet``, to *let over lambda* more pythonically:

```python
from unpythonic import dlet

@dlet(x=0)
def counter(*, env=None):  # named argument "env" filled in by decorator
    env.x += 1
    return env.x
counter()  # --> 1
counter()  # --> 2
```

For comparison, with the macro API, this becomes:

```python
from unpythonic.syntax import macros, dlet

@dlet(x << 0)
def counter():
    x << x + 1
    return x
counter()  # --> 1
counter()  # --> 2
```

The ``@blet`` decorator is otherwise the same as ``@dlet``, but instead of decorating a function definition in the usual manner, it runs the `def` block immediately, and upon exit, replaces the function definition with the return value. The name ``blet`` is an abbreviation of *block let*, since the role of the `def` is just a code block to be run immediately.

#### ``letrec``

The name of this construct comes from the Scheme family of Lisps, and stands for *let (mutually) recursive*. The "[mutually recursive](https://en.wikipedia.org/wiki/Mutual_recursion)" refers to the kind of scoping between the bindings in the same `letrec`.

In plain English, in `letrec`, bindings may depend on ones above them in the same `letrec`. The raw API in `unpythonic` uses a `lambda e: ...` to provide the environment:

```python
from unpythonic import letrec

x = letrec(a=1,
           b=lambda e:
                  e.a + 1,
           body=lambda e:
                  e.b)  # --> 2
```

The ordering of the definitions is respected, because Python 3.6 and later preserve the ordering of named arguments passed in a function call. See [PEP 468](https://www.python.org/dev/peps/pep-0468/).

For comparison, with the macro API, this becomes:

```python
from unpythonic.syntax import macros, letrec

x = letrec[[a << 1,
            b << a + 1] in
           b]
```

In the non-macro `letrec`, the ``value`` of each binding is either a simple value (non-callable, and doesn't use the environment), or an expression of the form ``lambda e: valexpr``, providing access to the environment as ``e``. If ``valexpr`` itself is callable, the binding **must** have the ``lambda e: ...`` wrapper to prevent misinterpretation by the machinery when the environment initialization procedure runs.

In a non-callable ``valexpr``, trying to depend on a binding below it raises ``AttributeError``.

A callable ``valexpr`` may depend on any bindings (**also later ones**) in the same `letrec`. For example, here is a pair of [mutually recursive](https://en.wikipedia.org/wiki/Mutual_recursion) functions:

```python
from unpythonic import letrec

letrec(evenp=lambda e:
               lambda x:
                 (x == 0) or e.oddp(x - 1),
       oddp=lambda e:
               lambda x:
                 (x != 0) and e.evenp(x - 1),
       body=lambda e:
               e.evenp(42))  # --> True
```

For comparison, with the macro API, this becomes:

```python
from unpythonic.syntax import macros, letrec

letrec[[evenp << (lambda x:
                   (x == 0) or oddp(x - 1)),
        oddp <<  (lambda x:
                   (x != 0) and evenp(x - 1))] in
       evenp(42)]  # --> True
```


Order-preserving list uniqifier:

```python
from unpythonic import letrec, begin

u = lambda lst: letrec(seen=set(),
                       see=lambda e:
                              lambda x:
                                begin(e.seen.add(x),
                                      x),
                       body=lambda e:
                              [e.see(x) for x in lst if x not in e.seen])
```

For comparison, with the macro API, this becomes:

```python
from unpythonic.syntax import macros, letrec, do

u = lambda lst: letrec[[seen << set(),
                        see << (lambda x:
                                  do[seen.add(x),
                                     x])] in
                       [[see(x) for x in lst if x not in seen]]]
```

(*The double brackets around the `letrec` body are needed because brackets denote a multiple-expression `letrec` body. So it is a multiple-expression body that contains just one expression, which is a list comprehension.*)

The decorators ``@dletrec`` and ``@bletrec`` work otherwise exactly like ``@dlet`` and ``@blet``, respectively, but the bindings are scoped like in ``letrec`` (mutually recursive scope).


#### Lispylet: alternative syntax

**NOTE**: This is primarily a code generation target API for the ``let[]`` family of [macros](macros.md), which make the constructs easier to use. Below is the documentation for the raw API.

The `lispylet` module was originally created to allow guaranteed left-to-right initialization of `letrec` bindings in Pythons older than 3.6, hence the positional syntax and more parentheses. The only difference is the syntax; the behavior is identical with the other implementation. As of 0.15, the main role of `lispylet` is to act as the run-time backend for the `let` family of macros.

These constructs are available in the top-level `unpythonic` namespace, with the ``ordered_`` prefix: ``ordered_let``, ``ordered_letrec``, ``ordered_dlet``, ``ordered_dletrec``, ``ordered_blet``, ``ordered_bletrec``.

It is also possible to override the default `let` constructs by the `ordered_` variants, like this:

```python
from unpythonic.lispylet import *  # override the default "let" implementation

letrec((('a', 1),
        ('b', lambda e:
                e.a + 1)),  # may refer to any bindings above it in the same letrec
       lambda e:
         e.b)  # --> 2

letrec((("evenp", lambda e:
                    lambda x:  # callable, needs the lambda e: ...
                      (x == 0) or e.oddp(x - 1)),
        ("oddp",  lambda e:
                    lambda x:
                      (x != 0) and e.evenp(x - 1))),
       lambda e:
         e.evenp(42))  # --> True
```

The syntax is `let(bindings, body)` (respectively `letrec(bindings, body)`), where `bindings` is `((name, value), ...)`, and `body` is like in the default variants. The same rules concerning `name` and `value` apply.

For comparison, with the macro API, the above becomes:

```python
from unpythonic.syntax import macros, letrec

letrec[[a << 1,
        b << a + 1] in
       b]

letrec[[evenp << (lambda x:
                   (x == 0) or oddp(x - 1)),
        oddp <<  (lambda x:
                   (x != 0) and evenp(x - 1))] in
       evenp(42)]  # --> True
```

(*The transformations made by the macros may be the most apparent when comparing these examples. Note that the macros scope the `let` bindings lexically, automatically figuring out which `let` environment, if any, to refer to.*)


### ``env``: the environment

The environment used by all the ``let`` constructs and ``assignonce`` (but **not** by `dyn`) is essentially a bunch with iteration, subscripting and context manager support. It is somewhat similar to [`types.SimpleNamespace`](https://docs.python.org/3/library/types.html#types.SimpleNamespace), but with many extra features. For details, see `unpythonic.env`.

Our ``env`` allows things like:

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

(This allows using `with env(...) as e:` as a poor man's `let`, if you have a block of statements you want to locally scope some names to, but don't want to introduce a `def`.)

``env`` provides the ``collections.abc.Mapping`` and  ``collections.abc.MutableMapping`` APIs.


### ``assignonce``

*As of v0.15.0, `assignonce` is mostly a standalone curiosity that has never been integrated with the rest of `unpythonic`. But anything that works with arbitrary subclasses of `env`, for example `mogrify`, works with it, too.*

In Scheme terms, make `define` and `set!` look different:

```python
from unpythonic import assignonce

with assignonce() as e:
    e.foo = "bar"           # new definition, ok
    e.set("foo", "tavern")  # explicitly rebind e.foo, ok
    e << ("foo", "tavern")  # same thing (but return e instead of new value, suitable for chaining)
    e.foo = "quux"          # AttributeError, e.foo already defined.
```

The `assignonce` construct is a subclass of ``env``, so it shares most of the same [features](#env-the-environment) and allows similar usage.

#### Historical note

The fact that in Python creating bindings and updating (rebinding) them look the same was already noted in 2000, in [PEP 227](https://www.python.org/dev/peps/pep-0227/#discussion), which introduced true closures to Python 2.1. For related history concerning the `nonlocal` keyword, see [PEP 3104](https://www.python.org/dev/peps/pep-3104/).


### ``dyn``: dynamic assignment

**Changed in v0.14.2.** *To bring this in line with [SRFI-39](https://srfi.schemers.org/srfi-39/srfi-39.html), `dyn` now supports rebinding, using assignment syntax such as `dyn.x = 42`, and the function `dyn.update(x=42, y=17, ...)`.*

([As termed by Felleisen.](https://groups.google.com/forum/#!topic/racket-users/2Baxa2DxDKQ) Other names seen in the wild for variants of this feature include *parameters* ([Scheme](https://srfi.schemers.org/srfi-39/srfi-39.html) and [Racket](https://docs.racket-lang.org/reference/parameters.html); not to be confused with function parameters), *special variables* (Common Lisp), *fluid variables*, *fluid let* (e.g. Emacs Lisp), and even the misnomer *"dynamic scoping"*.)

The feature itself is *dynamic assignment*; the things it creates are *dynamic variables* (a.k.a. *dynvars*).

Dynvars are like global variables, but better-behaved. Useful for sending some configuration parameters through several layers of function calls without changing their API. Best used sparingly.

There's a singleton, `dyn`:

```python
from unpythonic import dyn, make_dynvar

make_dynvar(c=17)  # top-level default value

def f():  # no "a" in lexical scope here
    assert dyn.a == 2

def g():
    with dyn.let(a=2, b="foo", c=42):
        assert dyn.a == 2
        assert dyn.c == 42

        f()

        with dyn.let(a=3):  # dynamic assignments can be nested
            assert dyn.a == 3

        # now "a" has reverted to its previous value
        assert dyn.a == 2

    assert dyn.c == 17  # "c" has reverted to its default value
    print(dyn.b)  # AttributeError, dyn.b no longer exists
g()
```

Dynvars are created using `with dyn.let(k0=v0, ...)`. The syntax is in line with the nature of the assignment, which is in effect *for the dynamic extent* of the `with`. Exiting the `with` block pops the dynamic environment stack. Inner dynamic environments shadow outer ones.

The point of dynamic assignment is that dynvars are seen also by code that is *outside the lexical scope* where the `with dyn.let` resides. The use case is to avoid a function parameter definition cascade, when you need to pass some information through several layers that do not care about it. This is especially useful for passing "background" information, such as plotter settings in scientific visualization, or the macro expander instance in metaprogramming.

To give a dynvar a top-level default value, use ``make_dynvar(k0=v0, ...)``. Usually this is done at the top-level scope of the module for which that dynvar is meaningful. Each dynvar, of the same name, should only have one default set; the (dynamically) latest definition always overwrites. However, we do not prevent overwrites, because in some codebases the same module may run its top-level initialization code multiple times (e.g. if a module has a ``main()`` for tests, and the file gets loaded both as a module and as the main program).

To rebind existing dynvars, use `dyn.k = v`, or `dyn.update(k0=v0, ...)`. Rebinding occurs in the closest enclosing dynamic environment that has the target name bound. If the name is not bound in any dynamic environment (including the top-level one), ``AttributeError`` is raised.

**CAUTION**: Use rebinding of dynvars carefully, if at all. Stealth updates of dynvars defined in an enclosing dynamic extent can destroy any chance of statically reasoning about your code.

There is no `set` function or `<<` operator, unlike in the other `unpythonic` environments.

<details>
<summary>Each thread has its own dynamic scope stack. There is also a global dynamic scope for default values, shared between threads. </summary>
A newly spawned thread automatically copies the then-current state of the dynamic scope stack **from the main thread** (not the parent thread!). Any copied bindings will remain on the stack for the full dynamic extent of the new thread. Because these bindings are not associated with any `with` block running in that thread, and because aside from the initial copying, the dynamic scope stacks are thread-local, any copied bindings will never be popped, even if the main thread pops its own instances of them.

The source of the copy is always the main thread mainly because Python's `threading` module gives no tools to detect which thread spawned the current one. (If someone knows a simple solution, a PR is welcome!)

Finally, there is one global dynamic scope shared between all threads, where the default values of dynvars live. The default value is used when ``dyn`` is queried for the value outside the dynamic extent of any ``with dyn.let()`` blocks. Having a default value is convenient for eliminating the need for ``if "x" in dyn`` checks, since the variable will always exist (at any time after the global definition has been executed).
</details>

For more details, see the methods of ``dyn``; particularly noteworthy are ``asdict`` and ``items``, which give access to a *live view* to dyn's contents in a dictionary format (intended for reading only!). The ``asdict`` method essentially creates a ``collections.ChainMap`` instance, while ``items`` is an abbreviation for ``asdict().items()``. The ``dyn`` object itself can also be iterated over; this creates a ``ChainMap`` instance and redirects to iterate over it. ``dyn`` also provides the ``collections.abc.Mapping`` API.

To support dictionary-like idioms in iteration, dynvars can alternatively be accessed by subscripting; ``dyn["x"]`` has the same meaning as ``dyn.x``, to allow things like:

```python
print(tuple((k, dyn[k]) for k in dyn))
```

Finally, ``dyn`` supports membership testing as ``"x" in dyn``, ``"y" not in dyn``, where the string is the name of the dynvar whose presence is being tested.

For some more details, see [the unit tests](../unpythonic/tests/test_dynassign.py).

### Relation to similar features in Lisps

This is essentially [SRFI-39: Parameter objects](https://srfi.schemers.org/srfi-39/) for Python, using the MzScheme approach in the presence of multiple threads.

[Racket](http://racket-lang.org/)'s [`parameterize`](https://docs.racket-lang.org/guide/parameterize.html) behaves similarly. However, Racket seems to be the state of the art in many lispy language design related things, so its take on the feature may have some finer points I have not thought of.

On Common Lisp's special variables, see [Practical Common Lisp by Peter Seibel](http://www.gigamonkeys.com/book/variables.html), especially footnote 10 in the linked chapter, for a definition of terms. Similarly, dynamic variables in our `dyn` have *indefinite scope* (because `dyn` is implemented as a module-level global, accessible from anywhere), but *dynamic extent*.

So what we have in `dyn` is almost exactly like Common Lisp's special variables, except we are missing convenience features such as `setf` and a smart `let` that auto-detects whether a variable is lexical or dynamic (if the name being bound is already in scope).


## Containers

We provide some additional low-level containers beyond those provided by Python itself.

The class names are lowercase, because these are intended as low-level utility classes in principle on par with the builtins. The immutable containers are hashable. All containers are pickleable (if their contents are).

### ``frozendict``: an immutable dictionary

**Changed in 0.14.2**. *[A bug in `frozendict` pickling](https://github.com/Technologicat/unpythonic/issues/55) has been fixed. Now also the empty `frozendict` pickles and unpickles correctly.*

Given the existence of ``dict`` and ``frozenset``, this one is oddly missing from the language.

```python
from unpythonic import frozendict

d = frozendict({'a': 1, 'b': 2})
d['a']      # OK
d['c'] = 3  # TypeError, not writable
```

Functional updates are supported:

```python
d2 = frozendict(d, a=42)
assert d2['a'] == 42 and d2['b'] == 2
assert d['a'] == 1  # original not mutated

d3 = frozendict({'a': 1, 'b': 2}, {'a': 42})  # rightmost definition of each key wins
assert d3['a'] == 42 and d3['b'] == 2

# ...also using unpythonic.fupdate
d4 = fupdate(d3, a=23)
assert d4['a'] == 23 and d4['b'] == 2
assert d3['a'] == 42 and d3['b'] == 2  # ...of course without touching the original
```

Any mappings used when creating an instance are shallow-copied, so that the bindings of the ``frozendict`` do not change even if the original input is later mutated:

```python
d = {1:2, 3:4}
fd = frozendict(d)
d[5] = 6
assert d == {1: 2, 3: 4, 5: 6}
assert fd == {1: 2, 3: 4}
```

**The usual caution** concerning immutable containers in Python applies: the container protects only the bindings against changes. If the values themselves are mutable, the container cannot protect from mutations inside them.

All the usual read-access features work:

```python
d7 = frozendict({1:2, 3:4})
assert 3 in d7
assert len(d7) == 2
assert set(d7.keys()) == {1, 3}
assert set(d7.values()) == {2, 4}
assert set(d7.items()) == {(1, 2), (3, 4)}
assert d7 == frozendict({1:2, 3:4})
assert d7 != frozendict({1:2})
assert d7 == {1:2, 3:4}  # like frozenset, __eq__ doesn't care whether mutable or not
assert d7 != {1:2}
assert {k for k in d7} == {1, 3}
assert d7.get(3) == 4
assert d7.get(5, 0) == 0
assert d7.get(5) is None
```

In terms of ``collections.abc``, a ``frozendict`` is a hashable immutable mapping:

```python
assert issubclass(frozendict, Mapping)
assert not issubclass(frozendict, MutableMapping)

assert issubclass(frozendict, Hashable)
assert hash(d7) == hash(frozendict({1:2, 3:4}))
assert hash(d7) != hash(frozendict({1:2}))
```

The abstract superclasses are virtual, just like for ``dict``. We mean *virtual* in the sense of [`abc.ABCMeta`](https://docs.python.org/3/library/abc.html#abc.ABCMeta), i.e. a virtual superclass does not appear in the MRO.

Finally, ``frozendict`` obeys the empty-immutable-container singleton invariant:

```python
assert frozendict() is frozendict()
```


### `cons` and friends: pythonic lispy linked lists

*Laugh, it's funny.*

**Changed in v0.14.2.** *`nil` is now a `Singleton`, so it is treated correctly by `pickle`. The `nil` instance refresh code inside the `cons` class has been removed, so the previous caveat about pickling a standalone `nil` value no longer applies.*

```python
from unpythonic import (cons, nil, ll, llist,
                        car, cdr, caar, cdar, cadr, cddr,
                        member, lreverse, lappend, lzip,
                        BinaryTreeIterator)

c = cons(1, 2)
assert car(c) == 1 and cdr(c) == 2

# ll(...) is like [...] or (...), but for linked lists:
assert ll(1, 2, 3) == cons(1, cons(2, cons(3, nil)))

t = cons(cons(1, 2), cons(3, 4))  # binary tree
assert [f(t) for f in [caar, cdar, cadr, cddr]] == [1, 2, 3, 4]

# default iteration scheme is "single cell or linked list":
a, b = cons(1, 2)                   # unpacking a cons cell
a, b, c = ll(1, 2, 3)               # unpacking a linked list
a, b, c, d = BinaryTreeIterator(t)  # unpacking a binary tree: use a non-default iteration scheme

assert list(ll(1, 2, 3)) == [1, 2, 3]
assert tuple(ll(1, 2, 3)) == (1, 2, 3)
assert llist((1, 2, 3)) == ll(1, 2, 3)  # llist() is like list() or tuple(), but for linked lists

l = ll(1, 2, 3)
assert member(2, l) == ll(2, 3)
assert not member(5, l)

assert lreverse(ll(1, 2, 3)) == ll(3, 2, 1)
assert lappend(ll(1, 2), ll(3, 4), ll(5, 6)) == ll(1, 2, 3, 4, 5, 6)
assert lzip(ll(1, 2, 3), ll(4, 5, 6)) == ll(ll(1, 4), ll(2, 5), ll(3, 6))
```

Cons cells are immutable à la Racket (no `set-car!`/`rplaca`, `set-cdr!`/`rplacd`). Accessors are provided up to `caaaar`, ..., `cddddr`.

Although linked lists are created with the functions ``ll`` or ``llist``, the data type (for e.g. ``isinstance``) is ``cons``.

Iterators are supported, to walk over linked lists. This also gives sequence unpacking support. When ``next()`` is called, we return the `car` of the current cell the iterator points to, and the iterator moves to point to the cons cell in the `cdr`, if any. When the `cdr` is not a cons cell, it is the next (and last) item returned; except if it `is nil`, then iteration ends without returning the `nil`.

Python's builtin ``reversed`` can be applied to linked lists; it will internally ``lreverse`` the list (which is O(n)), then return an iterator to that. The ``llist`` constructor is special-cased so that if the input is ``reversed(some_ll)``, it just returns the internal already reversed list. (This is safe because cons cells are immutable.)

Cons structures, by default, print in a pythonic format suitable for ``eval`` (if all elements are):

```python
print(cons(1, 2))                   # --> cons(1, 2)
print(ll(1, 2, 3))                  # --> ll(1, 2, 3)
print(cons(cons(1, 2), cons(3, 4))  # --> cons(cons(1, 2), cons(3, 4))
```

Cons structures can optionally print like in Lisps:

```python
print(cons(1, 2).lispyrepr())                    # --> (1 . 2)
print(ll(1, 2, 3).lispyrepr())                   # --> (1 2 3)
print(cons(cons(1, 2), cons(3, 4)).lispyrepr())  # --> ((1 . 2) . (3 . 4))
```

For more, see the ``llist`` submodule.

#### Notes

There is no ``copy`` method or ``lcopy`` function, because cons cells are immutable; which makes cons structures immutable.

However, for example, it is possible to ``cons`` a new item onto an existing linked list; that is fine, because it produces a new cons structure - which shares data with the original, just like in Racket.

In general, copying cons structures can be error-prone. Given just a starting cell it is impossible to tell if a given instance of a cons structure represents a linked list, or something more general (such as a binary tree) that just happens to locally look like one, along the path that would be traversed if it was indeed a linked list.

The linked list iteration strategy does not recurse in the ``car`` half, which could lead to incomplete copying. The tree strategy that recurses on both halves, on the other hand, will flatten nested linked lists and produce also the final ``nil``.

We provide a ``JackOfAllTradesIterator`` as a compromise that understands both trees and linked lists. Nested lists will be flattened, and in a tree any ``nil`` in a ``cdr`` position will be omitted from the output. ``BinaryTreeIterator`` and ``JackOfAllTradesIterator`` use an explicit data stack instead of implicitly using the call stack for keeping track of the recursion. All ``cons`` iterators work for arbitrarily deep cons structures without causing Python's call stack to overflow, and without the need for TCO.

``cons`` has no ``collections.abc`` virtual superclasses (except the implicit ``Hashable`` since ``cons`` provides ``__hash__`` and ``__eq__``), because general cons structures do not fit into the contracts represented by membership in those classes. For example, size cannot be known without iterating, and depends on which iteration scheme is used (e.g. ``nil`` dropping, flattening); which scheme is appropriate depends on the content.


### ``box``: a mutable single-item container

**Changed in v0.14.2**. *The `box` container API is now `b.set(newvalue)` to rebind, returning the new value as a convenience. The equivalent syntactic sugar is `b << newvalue`. The item inside the box can be extracted with `b.get()`. The equivalent syntactic sugar is `unbox(b)`.*

**Added in v0.14.2**. *`ThreadLocalBox`: like `box`, but with thread-local contents. It also holds a default object, which is used when a particular thread has not placed any object into the box.*

**Added in v0.14.2**. *`Some`: like `box`, but immutable. Useful to mark an optional attribute. `Some(None)` indicates a value that is set to `None`, in contrast to a bare `None`, which can then be used indicate the absence of a value.*

**Changed in v0.14.2**. *Accessing the `.x` attribute of a `box` directly is now deprecated. It will continue to work with `box` at least until 0.15, but it does not and cannot work with `ThreadLocalBox`, which must handle things differently due to implementation reasons. Use the API mentioned above; it supports both kinds of boxes with the same syntax.*

#### ``box``

Consider this highly artificial example:

```python
animal = "dog"

def f(x):
    animal = "cat"  # but I want to update the existing animal!

f(animal)
assert animal == "dog"
```

Many solutions exist. Common pythonic ones are abusing a ``list`` to represent a box (and then trying to remember that it is supposed to hold only a single item), or (if the lexical structure of the particular piece of code allows it) using the ``global`` or ``nonlocal`` keywords to tell Python, on assignment, to overwrite a name that already exists in a surrounding scope.

As an alternative to the rampant abuse of lists, we provide a rackety ``box``, which is a minimalistic mutable container that holds exactly one item. Any code that has a reference to the box can update the data in it:

```python
from unpythonic import box, unbox

cardboardbox = box("dog")

def f(thebox):
    thebox << "cat"  # send a cat into the box

f(cardboardbox)
assert unbox(cardboardbox) == "cat"
```

This simple example could have been handled by declaring `global animal` in the body of `f`, and then just assigning to `animal`. The similar case with nested functions can be handled similarly, by declaring [`nonlocal animal`](https://abstrusegoose.com/7). But consider this:

```python
from unpythonic import box, unbox

def f(x):
    b = box(x)
    g(b)
    assert unbox(b) == "bobcat"  # https://xkcd.com/325/

def g(thebox):
    thebox << "bobcat"

f("dog")
```

Here `g` *effectively rebinds a local variable of `f`* - whether that is a good idea is a separate question, but technically speaking, this would not be possible without a container. As mentioned, abusing a `list` is the standard Python (but not very pythonic!) solution. Using specifically a `box` makes the intent explicit.

The ``box`` API is summarized by:

```python
from unpythonic import box, unbox

box1 = box("cat")
box2 = box("cat")
box3 = box("dog")

assert box1.get() == "cat"  # .get() retrieves the current value
assert unbox(box1) == "cat"  # unbox() is syntactic sugar, does the same thing
assert "cat" in box1  # content is "in" the box, also syntactically
assert "dog" not in box1

assert [x for x in box1] == ["cat"]  # a box is iterable
assert len(box1) == 1  # a box always has length 1

assert box1 == "cat"  # for equality testing, a box is considered equal to its content
assert unbox(box1) == "cat"  # can also unbox the content before testing (good practice)

assert box2 == box1  # contents are equal, but
assert box2 is not box1  # different boxes

assert box3 != box1  # different contents

box3 << "fox"  # replacing the item in the box (rebinding the contents)
assert "fox" in box3
assert "dog" not in box3

box3.set("fox")  # same without syntactic sugar
assert "fox" in box3
```

The expression ``item in b`` has the same meaning as ``unbox(b) == item``. Note ``box`` is a **mutable container**, so it is **not hashable**.

The expression `unbox(b)` has the same meaning as `b.get()`, but because it is a function (instead of a method), it additionally sanity-checks that `b` is a box, and if not, raises `TypeError`.

The expression `b << newitem` has the same meaning as `b.set(newitem)`. In both cases, the new value is returned as a convenience.

#### ``Some``

We also provide an **immutable** box, `Some`. This can be useful to represent optional data.

The idea is that the value, when present, is placed into a `Some`, such as `Some(42)`, `Some("cat")`, `Some(myobject)`. Then, the situation where the value is absent can be represented as a bare `None`. So specifically, `Some(None)` means that a value is present and this value is `None`, whereas a bare `None` means that there is no value.

(It is like the `Some` constructor of a `Maybe` monad, but with no monadic magic. In this interpretation, the bare constant `None` plays the role of `Nothing`.)

#### ``ThreadLocalBox``

`ThreadLocalBox` is otherwise exactly like `box`, but magical: its contents are thread-local. It also holds a default object, which is set initially when the `ThreadLocalBox` is instantiated. The default object is seen by threads that have not placed any object into the box.

```python
from unpythonic import ThreadLocalBox, unbox

tlb = ThreadLocalBox("cat")  # This `"cat"` becomes the default object.
assert unbox(tlb) == "cat"
def test_threadlocalbox_worker():
    # This thread hasn't sent anything into the box yet,
    # so it sees the default object.
    assert unbox(tlb) == "cat"

    tlb << "hamster"                # Sending another object into the box...
    assert unbox(tlb) == "hamster"  # ...in this thread, now the box holds the new object.
t = threading.Thread(target=test_threadlocalbox_worker)
t.start()
t.join()

# But in the main thread, the box still holds the original object.
assert unbox(tlb) == "cat"
```

The method `.setdefault(x)` changes the default object, and `.getdefault()` retrieves the current default object. The method `.clear()` clears the value *sent to the box by the current thread*, thus unshadowing the default for the current thread.

```python
from unpythonic import ThreadLocalBox, unbox

tlb = ThreadLocalBox("gerbil")

# We haven't sent any object to the box, so we see the default object.
assert unbox(tlb) == "gerbil"

tlb.setdefault("cat")  # change the default (cats always fill available boxes)
assert unbox(tlb) == "cat"

tlb << "tortoise"                # Send an object to the box *for this thread*.
assert unbox(tlb) == "tortoise"  # Now we see the object we sent. The default is shadowed.

def test_threadlocalbox_worker():
    # Since this thread hasn't sent anything into the box yet,
    # we see the current default object.
    assert unbox(tlb) == "cat"

    tlb << "dog"                # But after we send an object into the box...
    assert unbox(tlb) == "dog"  # ...that's the object this thread sees.
t = threading.Thread(target=test_threadlocalbox_worker)
t.start()
t.join()

# In the main thread, this box still has the value the main thread sent there.
assert unbox(tlb) == "tortoise"
# But we can still see the default, if we want, by explicitly requesting it.
assert tlb.getdefault() == "cat"
tlb.clear()                 # When we clear the box in this thread...
assert unbox(tlb) == "cat"  # ...this thread sees the current default object again.
```


### ``Shim``: redirect attribute accesses

**Added in v0.14.2**.

A `Shim` is an *attribute access proxy*. The shim holds a `box` (or a `ThreadLocalBox`; your choice), and redirects attribute accesses on the shim to whatever object happens to currently be in the box. The point is that the object in the box can be replaced with a different one later (by sending another object into the box), and the code accessing the proxied object through the shim does not need to be aware that anything has changed.

For example, `Shim` can combo with `ThreadLocalBox` to redirect standard output only in particular threads. Place the stream object in a `ThreadLocalBox`, shim that box, then replace `sys.stdout` with the shim. See the source code of `unpythonic.net.server` for an example that actually does (and cleanly undoes) this.

Since deep down, attribute access is the whole point of objects, `Shim` is essentially a transparent object proxy. (For example, a method call is an attribute read (via a descriptor), followed by a function call.)

```python
from unpythonic import Shim, box, unbox

class TestTarget:
    def __init__(self, x):
        self.x = x
    def getme(self):  # not very pythonic; just for demonstration.
        return self.x

b = box(TestTarget(21))
s = Shim(b)  # We could use a ThreadLocalBox just as well.

assert hasattr(s, "x")
assert hasattr(s, "getme")
assert s.x == 21
assert s.getme() == 21

# We can also add or rebind attributes through the shim.
s.y = "hi from injected attribute"
assert unbox(b).y == "hi from injected attribute"
s.y = "hi again"
assert unbox(b).y == "hi again"

b << TestTarget(42)  # After we send a different object into the box held by the shim...
assert s.x == 42     # ...the shim accesses the new object.
assert s.getme() == 42
assert not hasattr(s, "y")  # The new TestTarget instance doesn't have "y".
```

A shim can have an optional fallback object. It can be either any object, or a `box` (or `ThreadLocalBox`) if you want to replace the fallback later. **For attribute reads** (i.e. `__getattr__`), if the object in the primary box does not have the requested attribute, `Shim` will try to get it from the fallback. If `fallback` is boxed, the attribute read takes place on the object in the box. If it is not boxed, the attribute read takes place directly on `fallback`.

Any **attribute writes** (i.e. `__setattr__`, binding or rebinding an attribute) always take place on the object in the **primary** box. That is, binding or rebinding of attributes is never performed on the fallback object.

```python
from unpythonic import Shim, box, unbox

class Ex:
    x = "hi from Ex"
class Wai:
    y = "hi from Wai"
x, y = [box(obj) for obj in (Ex(), Wai())]
s = Shim(x, fallback=y)
assert s.x == "hi from Ex"
assert s.y == "hi from Wai"  # no such attribute on Ex, fallback tried.
# Attribute writes (binding) always take place on the object in the primary box.
s.z = "hi from Ex again"
assert unbox(x).z == "hi from Ex again"
assert not hasattr(unbox(y), "z")
```

If you need to chain fallbacks, this can be done with `foldr`:

```python
from unpythonic import Shim, box, unbox, foldr

class Ex:
    x = "hi from Ex"
class Wai:
    x = "hi from Wai"
    y = "hi from Wai"
class Zee:
    x = "hi from Zee"
    y = "hi from Zee"
    z = "hi from Zee"

 # There will be tried from left to right.
boxes = [box(obj) for obj in (Ex(), Wai(), Zee())]
*others, final_fallback = boxes
s = foldr(Shim, final_fallback, others)  # Shim(box, fallback) <-> op(elt, acc)
assert s.x == "hi from Ex"
assert s.y == "hi from Wai"
assert s.z == "hi from Zee"
```

Or, since the operation takes just one `elt` and an `acc`, we can also use `reducer` instead of `foldr`, shortening this by one line:

```python
from unpythonic import Shim, box, unbox, reducer

class Ex:
    x = "hi from Ex"
class Wai:
    x = "hi from Wai"
    y = "hi from Wai"
class Zee:
    x = "hi from Zee"
    y = "hi from Zee"
    z = "hi from Zee"

 # There will be tried from left to right.
boxes = [box(obj) for obj in (Ex(), Wai(), Zee())]
s = reducer(Shim, boxes)  # Shim(box, fallback) <-> op(elt, acc)
assert s.x == "hi from Ex"
assert s.y == "hi from Wai"
assert s.z == "hi from Zee"
```


### Container utilities

**Changed in v0.15.0.** *The sequence length argument in `in_slice`, `index_in_slice` is now named `length`, not `l` (ell). This avoids an E741 warning in `flake8`, and is more descriptive.*

**Inspect the superclasses** that a particular container type has:

```python
from unpythonic import get_abcs
print(get_abcs(list))
```

This includes virtual superclasses, i.e. those that are not part of the MRO. This works by ``issubclass(cls, v)`` on all classes defined in ``collections.abc``.

**Reflection on slices**:

```python
from unpythonic import in_slice, index_in_slice

s = slice(1, 11, 2)  # 1, 3, 5, 7, 9
assert in_slice(5, s)
assert not in_slice(6, s)
assert index_in_slice(5, s) == 2
```

An optional length argument can be given to interpret negative indices. See the docstrings for details.



## Sequencing

Sequencing refers to running multiple expressions, in sequence, in place of one expression.

Keep in mind the only reason to ever need multiple expressions: *side effects.* Assignment is a side effect, too; it modifies the environment. In functional style, intermediate named definitions to increase readability are perhaps the most useful kind of side effect.

See also ``multilambda`` in [macros](macros.md).


### ``begin``: sequence side effects

**CAUTION**: the `begin` family of forms are provided **for use in pure-Python projects only**, and are a permanent part of the `unpythonic` API for that purpose. They are somewhat simpler and less flexible than the `do` family, described further below.

*If your project uses macros, prefer the `do[]` and `do0[]` macros; those are the only sequencing constructs understood by other macros in `unpythonic.syntax` that need to perform tail-position analysis (e.g. `tco`, `autoreturn`, `continuations`). The `do[]` and `do0[]` macros also provide some convenience features, such as expression-local variables.*

```python
from unpythonic import begin, begin0

f1 = lambda x: begin(print("cheeky side effect"),
                     42 * x)
f1(2)  # --> 84

f2 = lambda x: begin0(42 * x,
                      print("cheeky side effect"))
f2(2)  # --> 84
```

The `begin` and `begin0` forms are actually tuples in disguise; evaluation of all items occurs before the `begin` or `begin0` form gets control. Items are evaluated left-to-right due to Python's argument passing rules.

We provide also `lazy_begin` and `lazy_begin0`, which use loops. The price is the need for a lambda wrapper for each expression to delay evaluation, see [`unpythonic.seq`](../unpythonic/seq.py) for details.


### ``do``: stuff imperative code into an expression

**NOTE**: *This is primarily a code generation target API for the ``do[]`` and ``do0[]`` [macros](macros.md), which make the constructs easier to use, and make the code look almost like normal Python. Below is the documentation for the raw API.*

Basically, the ``do`` family is a more advanced and flexible variant of the ``begin`` family.

  - ``do`` can bind names to intermediate results and then use them in later items.

  - ``do`` is effectively a ``let*`` (technically, ``letrec``) where making a binding is optional, so that some items can have only side effects if so desired. There is no semantically distinct ``body``; all items play the same role.

  - Despite the name, there is no monadic magic.

Like in ``letrec``, use ``lambda e: ...`` to access the environment, and to wrap callable values (to prevent misinterpretation by the machinery).

Unlike ``begin`` (and ``begin0``), there is no separate ``lazy_do`` (``lazy_do0``), because using a ``lambda e: ...`` wrapper for an item will already delay its evaluation; and the main point of ``do``/``do0`` is that there is an environment that holds local definitions. If you want a lazy variant, just wrap each item with a ``lambda e: ...``, also those that don't otherwise need it.

#### ``do``

Like ``begin`` and ``lazy_begin``, the ``do`` form evaluates all items in order, and then returns the value of the **last** item.

```python
from unpythonic import do, assign

y = do(assign(x=17),          # create and set e.x
       lambda e: print(e.x),  # 17; uses environment, needs lambda e: ...
       assign(x=23),          # overwrite e.x
       lambda e: print(e.x),  # 23
       42)                    # return value
assert y == 42

y = do(assign(x=17),
       assign(z=lambda e: 2 * e.x),
       lambda e: e.z)
assert y == 34

y = do(assign(x=5),
       assign(f=lambda e: lambda x: x**2),  # callable, needs lambda e: ...
       print("hello from 'do'"),  # value is None; not callable
       lambda e: e.f(e.x))
assert y == 25
```

For comparison, with the macro API, this becomes:

```python
from unpythonic.syntax import macros, do, local

y = do[local[x << 17],  # create and set an x local to the environment
       print(x),
       x << 23,         # overwrite x
       print(x),
       42]              # return value
assert y == 42

y = do[local[x << 17],
       local[z << 2 * x],
       z]
assert y == 34

y = do[local[x << 5],
       local[f << (lambda x: x**2)],
       print("hello from 'do'"),
       f(x)]
assert y == 25
```

*In the macro version, all items are delayed automatically; that is, **every** item has an implicit ``lambda e: ...``.*

*Note that instead of the `assign` function, the macro version uses the syntax ``local[name << value]`` to **create** an expression-local variable. Updating an existing variable in the `do` environment is just ``name << value``. Finally, there is also ``delete[name]`.*

When using the raw API, beware of this pitfall:

```python
from unpythonic import do

do(lambda e: print("hello 2 from 'do'"),  # delayed because lambda e: ...
   print("hello 1 from 'do'"),  # Python prints immediately before do()
   "foo")                       # gets control, because technically, it is
                                # **the return value** that is an argument
                                # for do().
```

The above pitfall also applies to using escape continuations inside a ``do``. To do that, wrap the ec call into a ``lambda e: ...`` to delay its evaluation until the ``do`` actually runs:

```python
from unpythonic import call_ec, do, assign

call_ec(
  lambda ec:
    do(assign(x=42),
       lambda e: ec(e.x),                  # IMPORTANT: must delay this!
       lambda e: print("never reached")))  # and this (as above)
```

This way, any assignments made in the ``do`` (which occur only after ``do`` gets control), performed above the line with the ``ec`` call, will have been performed when the ``ec`` is called.

For comparison, with the macro API, the last example becomes:

```python
from unpythonic.syntax import macros, do, local
from unpythonic import call_ec

call_ec(
  lambda ec:
    do[local[x << 42],
       ec(x),
       print("never reached")])
```

*In the macro version, all items are delayed automatically, so there ``do``/``do0`` gets control before any items are evaluated. The `ec` fires when the `do` evaluates that item, and the `print` is indeed never reached.*

#### ``do0``

Like ``begin0`` and ``lazy_begin0``, the ``do0`` form evaluates all items in order, and then returns the value of the **first** item.

It effectively does this internally:

```python
from unpythonic import do, assign

y = do(assign(result=17),
       print("assigned 'result' in env"),
       lambda e: e.result)  # return value
assert y == 17
```

So we can write:

```python
from unpythonic import do0, assign

y = do0(17,
        assign(x=42),
        lambda e: print(e.x),
        print("hello from 'do0'"))
assert y == 17

y = do0(assign(x=17),  # the first item of do0 can be an assignment, too
        lambda e: print(e.x))
assert y == 17
```

For comparison, with the macro API, this becomes:

```python
from unpythonic.syntax import macros, do, local

y = do[local[result << 17],
       print("assigned 'result' in env"),
       result]
assert y == 17

y = do0[17,
        local[x << 42],
        print(x),
        print("hello from 'do0'")]
assert y == 17

y = do0[local[x << 17],
        print(x)]
assert y == 17
```


### ``pipe``, ``piped``, ``lazy_piped``: sequence functions

**Changed in v0.15.0.** *Multiple return values and named return values, for unpacking to the args and kwargs of the next function in the pipe, as well as in the final return value from the pipe, are now represented as a `Values`.*

*The variants `pipe` and `pipec` now expect a `Values` initial value if you want to unpack it into the args and kwargs of the first function in the pipe. Otherwise, the initial value is sent as a single positional argument (notably tuples too).*

*The variants `piped` and `lazy_piped` automatically pack the initial arguments into a `Values`.*

**Changed in v0.14.2**. *Both `getvalue` and `runpipe`, used in the shell-like syntax, are now known by the single unified name `exitpipe`. This is just a rename, with no functionality changes. The old names are deprecated in 0.14.2 and 0.14.3, and have been removed in 0.15.0.*

Similar to Racket's [threading macros](https://docs.racket-lang.org/threading/), but no macros. A pipe performs a sequence of operations, starting from an initial value, and then returns the final value. It is just function composition, but with an emphasis on data flow, which helps improve readability.

Both one-in-one-out (*1-to-1*) and n-in-m-out (*n-to-m*) pipes are provided. The 1-to-1 versions have names suffixed with ``1``, and they are slightly faster than the general versions. The use case is one-argument functions that return one value.

In the n-to-m versions, when a function returns a `Values`, it is unpacked to the args and kwargs of the next function in the pipeline. When a pipe exits, the `Values` wrapper (if any) around the final result is discarded if it contains only one positional value. The main use case is computations that deal with multiple values, the number of which may also change during the computation (as long as the args/kwargs of each output `Values` can be accepted as input by the next function in the pipe).

Additional examples can be found in [the unit tests](../unpythonic/tests/test_seq.py).

#### ``pipe``

The function `pipe` represents a self-contained pipeline that starts from a given value (or values), applies some operations in sequence, and then exits:

```python
from unpythonic import pipe, Values

double = lambda x: 2 * x
inc    = lambda x: x + 1

x = pipe(42, double, inc)
assert x == 85
```

To pass several positional values and/or named values, use a `Values` object:

```python
from unpythonic import pipe, Values

a, b = pipe(Values(2, 3),
            lambda x, y: Values(x=(x + 1), y=(2 * y)),
            lambda x, y: Values(x * 2, y + 1))
assert (a, b) == (6, 7)
```

In this example, we pass the initial values positionally into the first function in the pipeline; that function passes its return values by name; and the second function in the pipeline passes the final results positionally. Because there are only positional values in the final `Values` object, it can be unpacked like a tuple.

#### ``pipec``

The function ``pipec`` is otherwise exactly like ``pipe``, but it curries the functions before applying them. This is useful with the passthrough feature of ``curry``.

With ``pipec`` you can do things like:

```python
from unpythonic import pipec, Values

a, b = pipec(Values(1, 2),
             lambda x: x + 1,  # extra values passed through by curry (positionals on the right)
             lambda x, y: Values(x * 2, y + 1))
assert (a, b) == (4, 3)
```

For more on passthrough, see the section on ``curry``.

#### ``piped``

We also provide a **shell-like syntax**, with purely functional updates.

To set up a pipeline for use with the shell-like syntax, call ``piped`` to load the initial value(s). It is possible to provide both positional and named values. Each use of the pipe operator applies the given function, but keeps the result inside the pipeline, ready to accept another function.

When done, pipe into the sentinel ``exitpipe`` to exit the pipeline and return the current value(s):

```python
from unpythonic import piped, exitpipe

x = piped(42) | double | inc | exitpipe
assert x == 85

p = piped(42) | double
assert p | inc | exitpipe == 85
assert p | exitpipe == 84  # p itself is never modified by the pipe system
```

Multiple values work like in `pipe`, except the initial value(s) passed to ``piped`` are automatically packed into a `Values`. The pipe system then automatically unpacks a `Values` object into the args/kwargs of the next function in the pipeline.

To return multiple positional values and/or named values, return a `Values` object from your function.

When ``exitpipe`` is applied, if the last function returned anything other than one positional value, you will get a ``Values`` object.

```python
from unpythonic import piped, exitpipe, Values

f = lambda x, y: Values(2 * x, y + 1)
g = lambda x, y: Values(x + 1, 2 * y)
x = piped(2, 3) | f | g | exitpipe  # --> (5, 8)
assert x == Values(5, 8)
```

Unpacking works also here, because in the final result, there are only positional values:

```python
from unpythonic import piped, exitpipe

a, b = piped(2, 3) | f | g | exitpipe  # --> (5, 8)
assert (a, b) == (5, 8)
```

#### ``lazy_piped``

Lazy pipes are useful when you have mutable initial values. To perform the planned computation, pipe into the sentinel ``exitpipe``:

```python
from unpythonic import lazy_piped1, exitpipe

lst = [1]
def append_succ(lis):
    lis.append(lis[-1] + 1)
    return lis  # this return value is handed to the next function in the pipe
p = lazy_piped1(lst) | append_succ | append_succ  # plan a computation
assert lst == [1]        # nothing done yet
p | exitpipe             # run the computation
assert lst == [1, 2, 3]  # now the side effect has updated lst.
```

Lazy pipe as an unfold:

```python
from unpythonic import lazy_piped, exitpipe

fibos = []
def nextfibo(a, b):      # multiple arguments allowed
    fibos.append(a)      # store result by side effect
    # New state, handed to next function in the pipe.
    # As of v0.15.0, use `Values(...)` to represent multiple return values.
    # Positional args will be passed positionally, named ones by name.
    return Values(a=b, b=(a + b))
p = lazy_piped(1, 1)     # load initial state
for _ in range(10):      # set up pipeline
    p = p | nextfibo
assert (p | exitpipe) == Values(a=89, b=144)  # run; check final state
assert fibos == [1, 1, 2, 3, 5, 8, 13, 21, 34, 55]
```


## Batteries

Things missing from the standard library.

### Batteries for functools

 - `memoize`, with exception caching.
 - **Added in v0.15.0.** `partial` with run-time type checking, which helps a lot with fail-fast in code that uses partial application. This function type-checks arguments against type annotations, then delegates to `functools.partial`. Supports `unpythonic`'s `@generic` and `@typed` functions, too.
 - `curry`, with passthrough like in Haskell.
 - `composel`, `composer`: both left-to-right and right-to-left function composition, to help readability.
   - **Changed in v0.15.0.** *For the benefit of code using the `with lazify` macro, the compose functions are now marked lazy. Arguments will be forced only when a lazy function in the chain actually uses them, or when an eager (not lazy) function is encountered in the chain.*
   - Any number of positional and keyword arguments are supported, with the same rules as in the pipe system. Multiple return values, or named return values, represented as a `Values`, are automatically unpacked to the args and kwargs of the next function in the chain.
   - `composelc`, `composerc`: curry each function before composing them. This comboes well with the passthrough of extra args/kwargs in `curry`.
     - An implicit top-level curry context is inserted around all the functions except the one that is applied last, to allow passthrough to the top level while applying the composed function.
   - `composel1`, `composer1`: 1-in-1-out chains (faster).
   - suffix `i` to use with an iterable that contains the functions (`composeli`, `composeri`, `composelci`, `composerci`, `composel1i`, `composer1i`)
 - `withself`: essentially, the Y combinator trick as a decorator. Allows a lambda to refer to itself.
   - The ``self`` argument is declared explicitly, but passed implicitly (as the first positional argument), just like the ``self`` argument of a method.
 - `apply`: the lispy approach to starargs. Mainly useful with the ``prefix`` [macro](macros.md).
 - `andf`, `orf`, `notf`: compose predicates (like Racket's `conjoin`, `disjoin`, `negate`).
   - **Changed in v0.15.0.** *For the benefit of code using the `with lazify` macro, `andf` and `orf` are now marked lazy. Arguments will be forced only when a lazy predicate in the chain actually uses them, or when an eager (not lazy) predicate is encountered in the chain.*
 - `flip`: reverse the order of positional arguments.
 - `rotate`: a cousin of `flip`. Permute the order of positional arguments in a cycle.
 - `to1st`, `to2nd`, `tokth`, `tolast`, `to` to help inserting 1-in-1-out functions into m-in-n-out compose chains. (Currying can eliminate the need for these.)
 - `identity`, `const` which sometimes come in handy when programming with higher-order functions.
 - `fix`: detect and break infinite recursion cycles. **Added in v0.14.2.**

We will discuss `memoize` and `curry` in more detail shortly; first, we will give some examples of the other utilities. Note that as always, more examples can be found in [the unit tests](../unpythonic/tests/test_fun.py). 

```python
from typing import NoReturn
from unpythonic import (fix, andf, orf, rotate,
                        zipr, rzip, foldl, foldr,
                        withself)

# detect and break infinite recursion cycles:
# a(0) -> b(1) -> a(2) -> b(0) -> a(1) -> b(2) -> a(0) -> ...
@fix()
def a(k):
    return b((k + 1) % 3)
@fix()
def b(k):
    return a((k + 1) % 3)
assert a(0) is NoReturn  # the call does return, saying the original function wouldn't.

# andf, orf: short-circuiting predicate combinators
isint  = lambda x: isinstance(x, int)
iseven = lambda x: x % 2 == 0
isstr  = lambda s: isinstance(s, str)
assert andf(isint, iseven)(42) is True
assert andf(isint, iseven)(43) is False
pred = orf(isstr, andf(isint, iseven))
assert pred(42) is True
assert pred("foo") is True
assert pred(None) is False

# lambda that refers to itself
fact = withself(lambda self, n: n * self(n - 1) if n > 1 else 1)
assert fact(5) == 120

@rotate(-1)  # cycle the argument slots to the left by one place, so "acc" becomes last
def zipper(acc, *rest):   # so that we can use the *args syntax to declare this
    return acc + (rest,)  # even though the input is (e1, ..., en, acc).
myzipl = curry(foldl, zipper, ())  # same as (curry(foldl))(zipper, ())
myzipr = curry(foldr, zipper, ())
assert myzipl((1, 2, 3), (4, 5, 6), (7, 8)) == ((1, 4, 7), (2, 5, 8))
assert myzipr((1, 2, 3), (4, 5, 6), (7, 8)) == ((2, 5, 8), (1, 4, 7))

# zip and reverse don't commute for inputs with different lengths
assert tuple(zipr((1, 2, 3), (4, 5, 6), (7, 8))) == ((2, 5, 8), (1, 4, 7))  # zip first
assert tuple(rzip((1, 2, 3), (4, 5, 6), (7, 8))) == ((3, 6, 8), (2, 5, 7))  # reverse first
```


#### ``memoize``

The ``memoize`` decorator is meant for use with [pure functions](https://en.wikipedia.org/wiki/Pure_function). It caches the return value, so that *for each unique set of arguments*, the original function will be evaluated only once. All arguments must be hashable.

Our ``memoize`` caches also exceptions, à la the [Mischief package in Racket](https://docs.racket-lang.org/mischief/memoize.html). If the memoized function is called again with arguments with which it raised an exception the first time, **that same exception instance** is raised again.

The decorator **works also on instance methods**, with results cached separately for each instance. This is essentially because ``self`` is an argument, and custom classes have a default ``__hash__``. Hence it doesn't matter that the memo lives in the ``memoized`` closure on the class object (type), where the method is, and not directly on the instances. The memo itself is shared between instances, but calls with a different value of ``self`` will create unique entries in it. (This approach does have the expected problem: if lots of instances are created and destroyed, and a memoized method is called for each, the memo will grow without bound.)

*For a solution that performs memoization at the instance level, see [this ActiveState recipe](https://github.com/ActiveState/code/tree/master/recipes/Python/577452_memoize_decorator_instance) (and to demystify the magic contained therein, be sure you understand [descriptors](https://docs.python.org/3/howto/descriptor.html)).*

There are some **important differences** to the nearest equivalents in the standard library, [`functools.cache`](https://docs.python.org/3/library/functools.html#functools.cache) (Python 3.9+) and [`functools.lru_cache`](https://docs.python.org/3/library/functools.html#functools.lru_cache):

  - `memoize` **binds arguments** like Python itself does, so given this definition:

    ```python
    from unpythonic import memoize

    @memoize
    def f(a, b):
        return a + b
    ```

    the calls `f(1, 2)`, `f(1, b=2)`, `f(a=1, b=2)`, and `f(b=2, a=1)` all hit **the same cache key**.

    As of Python 3.9, in `functools.lru_cache` this is not so; see the internal function `functools._make_key` in [`functools.py`](https://github.com/python/cpython/blob/main/Lib/functools.py), where the comments explicitly say so.

  - `memoize` **caches exceptions**, too. A pure function that crashed for some combination of arguments, if given the same inputs again, will just crash again with the same error, so there is no reason to run it again.

  - `memoize` has **no** maximum cache size or hit/miss statistics counting.

  - `memoize` does **not** have a `typed` mode to treat `42` and `42.0` as different keys to the memo. The function arguments are hashed, and both an `int` and an equal `float` happen to hash to the same value.

    The `typed` mode of the standard library functions is actually a form of dispatch. Hence, you can use `@generic` (which see), and `@memoize` each individual multimethod:

    ```python
    from unpythonic import generic, memoize

    @generic
    @memoize
    def thrice(x: int):
        return 3 * x

    @generic
    @memoize
    def thrice(x: float):
        return 3.0 * x
    ```

    Without using ``@generic``, the essential idea is:

    ```python
    from unpythonic import memoize

    def thrice(x):  # the dispatcher
        if isinstance(x, int):
           return thrice_int(x)
        elif isinstance(x, float):
            return thrice_float(x)
        raise TypeError(type(x))

    @memoize
    def thrice_int(x):
        return 3 * x

    @memoize
    def thrice_float(x):
        return 3.0 * x
    ```

    Observe that we memoize **each implementation**, not the dispatcher.

    This solution keeps dispatching and memoization orthogonal.

Examples:

```python
from unpythonic import memoize

ncalls = 0
@memoize  # <-- important part
def square(x):
    global ncalls
    ncalls += 1
    return x**2
assert square(2) == 4
assert ncalls == 1
assert square(3) == 9
assert ncalls == 2
assert square(3) == 9
assert ncalls == 2  # called only once for each unique set of arguments
assert square(x=3) == 9
assert ncalls == 2  # only the resulting bindings matter, not how you pass the args

# "memoize lambda": classic evaluate-at-most-once thunk
# See also the `lazy[]` macro.
thunk = memoize(lambda: print("hi from thunk"))
thunk()  # the message is printed only the first time
thunk()
```


#### `curry`

**Changed in v0.15.0.** *`curry` supports both positional and named arguments, and binds arguments to function parameters like Python itself does. The call triggers when all parameters are bound, regardless of whether they were passed by position or by name, and at which step of the currying process they were passed.*

*`unpythonic`'s multiple-dispatch system (`@generic`, `@typed`) is supported. `curry` looks for an exact match first, then a match with extra args/kwargs, and finally a partial match. If there is still no match, this implies that at least one parameter would get a binding that fails the type check. In such a case `TypeError` regarding failed multiple dispatch is raised.*

*If the function being curried is `@generic` or `@typed`, or has type annotations on its parameters, the parameters being passed in are type-checked. A type mismatch immediately raises `TypeError`. This helps support [fail-fast](https://en.wikipedia.org/wiki/Fail-fast) in code using `curry`.*

[Currying](https://en.wikipedia.org/wiki/Currying) is a technique in functional programming, where a function that takes multiple arguments is converted to a sequence of nested one-argument functions, each one *specializing* (fixing the value of) the leftmost remaining positional parameter.

Some languages, such as Haskell, curry all functions natively. In languages that do not, like Python or [Racket](https://docs.racket-lang.org/reference/procedures.html#%28def._%28%28lib._racket%2Ffunction..rkt%29._curry%29%29), when currying is implemented as a library function, this is often done as a form of [partial application](https://en.wikipedia.org/wiki/Partial_application), which is a subtly different concept, but encompasses the curried behavior as a special case.

Our ``curry`` can be used both as a decorator and as a regular function. As a decorator, `curry` takes no decorator arguments. As a regular function, `curry` itself is curried à la Racket. If any args or kwargs are given (beside the function to be curried), they are the first step. This helps eliminate many parentheses.

**CAUTION**: If the signature of ``f`` cannot be inspected, currying fails, raising ``ValueError``, like ``inspect.signature`` does. This may happen with builtins such as ``list.append``, ``operator.add``, ``print``, or ``range``, depending on which version of Python is used (and whether it is CPython or PyPy3).

Like Haskell, and [`spicy` for Racket](https://github.com/Technologicat/spicy), our `curry` supports *passthrough*; but we pass through **both positional and named arguments**.

Any args and/or kwargs that are incompatible with the target function's call signature, are *passed through* in the sense that the function is called, and then its return value is merged with the remaining args and kwargs.

If the *first positional return value* of the result of passthrough is callable, it is (curried and) invoked on the remaining args and kwargs, after the merging. This helps with some instances of [point-free style](https://en.wikipedia.org/wiki/Tacit_programming).

Some finer points concerning the passthrough feature:

  - *Incompatible* means too many positional args, or named args that have no corresponding parameter. Note that if the function has a `**kwargs` parameter, then all named args are considered compatible, because it absorbs anything.

  - Multiple return values (both positional and named) are denoted using `Values` (which see). A standard return value is considered to consist of *one positional return value* only (even if it is a `tuple`).

  - Extra positional args are passed through **on the right**. Any positional return values of the curried function are prepended, on the left.

  - Extra named args are passed through by name. They may be overridden by named return values (with the same name) from the curried function.

  - If more args/kwargs are still remaining when the top-level curry context exits, by default ``TypeError`` is raised.
     - To override this behavior, set the dynvar ``curry_context``. It is a list representing the stack of currently active curry contexts. A context is any object, a human-readable label is fine. See below for an example.
       - To set the dynvar, `from unpythonic import dyn`, and then `with dyn.let(curry_context=["whatever"]):`.

Examples:

```python
from operator import add, mul
from unpythonic import curry, foldl, foldr, composer, to1st, cons, nil, ll, dyn, Values

mysum = curry(foldl, add, 0)
myprod = curry(foldl, mul, 1)
a = ll(1, 2)
b = ll(3, 4)
c = ll(5, 6)
append_two = lambda a, b: foldr(cons, b, a)
append_many = lambda *lsts: foldr(append_two, nil, lsts)  # see unpythonic.lappend
assert mysum(append_many(a, b, c)) == 21
assert myprod(b) == 12

# curry with passthrough
double = lambda x: 2 * x
with dyn.let(curry_context=["whatever"]):  # set a context to allow passthrough to the top level
    # positionals are passed through on the right
    assert curry(double, 2, "foo") == Values(4, "foo")   # arity of double is 1
    # named args are passed through by name
    assert curry(double, 2, nosucharg="foo") == Values(4, nosucharg="foo")

# actual use case for passthrough
map_one = lambda f: curry(foldr, composer(cons, to1st(f)), nil)
doubler = map_one(double)
assert doubler((1, 2, 3)) == ll(2, 4, 6)

assert curry(map_one, double, ll(1, 2, 3)) == ll(2, 4, 6)
```

We could also write the last example as:

```python
from unpythonic import curry, foldl, composer, const, to1st, nil, lreverse

double = lambda x: 2 * x
rmap_one = lambda f: curry(foldl, composer(cons, to1st(f)), nil)  # essentially reversed(map(...))
map_one = lambda f: composer(rmap_one(f), lreverse)
assert curry(map_one, double, ll(1, 2, 3)) == ll(2, 4, 6)
```

which may be a useful pattern for lengthy iterables that could overflow the call stack (although not in ``foldr``, since our implementation uses a linear process).

In the example, in ``rmap_one``, we can use either ``curry`` or ``partial``. In this case it does not matter which, since we want just one partial application anyway. We provide two arguments, and the minimum arity of ``foldl`` is 3, so ``curry`` will trigger the call as soon as (and only as soon as) it gets at least one more argument.

The final ``curry`` in the example uses the passthrough features. The function ``map_one`` has arity 1, but two positional arguments are given. It also invokes a call to the callable returned by ``map_one``, with the remaining arguments (in this case just one, the ``ll(1, 2, 3)``).

Yet another way to write ``map_one`` is:

```python
from unpythonic import curry, foldr, composer, cons, nil

mymap = lambda f: curry(foldr, composer(cons, curry(f)), nil)
```

The curried ``f`` uses up one argument (provided it is a one-argument function!), and the second argument is passed through on the right; these two values then end up as the arguments to ``cons``.

Using a **currying compose function** (name suffixed with ``c``), we can drop the inner curry:

```python
from unpythonic import curry, foldr, composerc, cons, nil

mymap = lambda f: curry(foldr, composerc(cons, f), nil)
myadd = lambda a, b: a + b
assert curry(mymap, myadd, ll(1, 2, 3), ll(2, 4, 6)) == ll(3, 6, 9)
```

This is as close to ```(define (map f) (foldr (compose cons f) empty)``` (in ``#lang`` [``spicy``](https://github.com/Technologicat/spicy)) as we're gonna get in pure Python.

Notice how the last two versions accept multiple input iterables; this is thanks to currying ``f`` inside the composition. An element from each of the iterables is taken by the processing function ``f``. Being the last argument, ``acc`` is passed through on the right. The output from the processing function - one new item - and ``acc`` then become two arguments, passed into cons.

Finally, keep in mind the `mymap` example is intended as a feature demonstration. In production code, the builtin ``map`` is much better. It produces a lazy iterable, so it does not care which kind of actual data structure the items will be stored in (once they are computed). In other words, a lazy iterable is a much better model for a process that produces a sequence of values; how, and whether, to store that sequence is an orthogonal concern.

The example we have here evaluates all items immediately, and specifically produces a linked list. It is just a nice example of function composition involving incompatible positional arities, thus demonstrating the kind of situation where the passthrough feature of `curry` is useful. It is taken from a paper by [John Hughes (1984)](https://www.cse.chalmers.se/~rjmh/Papers/whyfp.html).


#### ``curry`` and reduction rules

Our ``curry``, beside what it says on the tin, is effectively an explicit local modifier to Python's reduction rules, which allows some Haskell-like idioms. Let's consider a simple example with positional arguments only. When we say:

```python
curry(f, a0, a1, ..., a[n-1])
```

it means the following. Let ``m1`` and ``m2`` be the minimum and maximum positional arity of the callable ``f``, respectively.

 - If ``n > m2``, call ``f`` with the first ``m2`` arguments.
   - If the result is a callable, curry it, and recurse.
   - Else form a tuple, where first item is the result, and the rest are the remaining arguments ``a[m2]``, ``a[m2+1]``, ..., ``a[n-1]``. Return it.
     - If more positional args are still remaining when the top-level curry context exits, by default ``TypeError`` is raised. Use the dynvar ``curry_context`` to override; see above for an example.
 - If ``m1 <= n <= m2``, call ``f`` and return its result (like a normal function call).
   - **Any** positional arity accepted by ``f`` triggers the call; beware when working with [variadic](https://en.wikipedia.org/wiki/Variadic_function) functions.
 - If ``n < m1``, partially apply ``f`` to the given arguments, yielding a new function with smaller ``m1``, ``m2``. Then curry the result and return it.
   - Internally we stack ``functools.partial`` applications, but there will be only one ``curried`` wrapper no matter how many invocations are used to build up arguments before ``f`` eventually gets called.

As of v0.15.0, the actual algorithm by which `curry` decides what to do, in the presence of kwargs, `@generic` functions, and `Values` multiple-return-values (and named return values), is:

 - If `f` is **not** `@generic` or `@typed`:
   - Compute parameter bindings of the args and kwargs collected so far, against the call signature of `f`.
     - Note we keep track of which arguments were passed positionally and which by name. To avoid subtle errors, they are eventually passed to `f` the same way they were passed to `curry`. (Positional args are passed positionally, and kwargs are passed by name.)
   - If there are no unbound parameters, and no args/kwargs are left over, we have an exact match. Call `f` and return its result, like a normal function call.
     - Any sequence of curried calls that ends up binding all parameters of `f` triggers the call.
     - Beware when working with variadic functions. Particularly, keep in mind that `*args` matches **zero or more** positional arguments (as the [Kleene star](https://en.wikipedia.org/wiki/Kleene_star)-ish notation indeed suggests).
   - If there are no unbound parameters, but there are args/kwargs left over, arrange passthrough for the leftover args/kwargs (that were rejected by the call signature of `f`), and call `f`. Any leftover positional arguments are passed through **on the right**.
     - Merge the return value of `f` with the leftover args/kwargs, thus forming updated leftover args/kwargs.
       - If the return value of `f` is a `Values`: prepend positional return values into the leftover args (i.e. insert them **on the left**), and update the leftover kwargs with the named return values. (I.e. a key name conflict causes an overwrite in the leftover kwargs.)
       - Else: there is just one positional return value. Prepend it to the leftover args.
     - If the first positional return value is a callable: remove it from the leftover args, curry it, and recurse with the (updated) leftover args/kwargs.
     - Else: form a `Values` from the leftover args/kwargs, and return it. (This return goes to the next outer curry context, or at the top level, to the original caller.)
   - If neither of the above match, we know there is at least one unbound parameter, i.e. we have a partial match. Keep currying.
 - If `f` is `@generic` or `@typed`:
   - Iterate over multimethods registered on `f`, **up to three times**.
   - First, try for an exact match that passes the type check. **If any such match is found**, pick that multimethod. Call it and return its result (as above).
   - Then, try for a match that passes the type check, but has extra args/kwargs. **If any such match is found**, pick that multimethod. Arrange passthrough... (as above).
   - Then, try for a partial match that passes the type check. **If any such match is found**, keep currying.
   - If none of the above match, it implies that no matter which multimethod we pick, at least one parameter will get a binding that fails the type check. Raise `TypeError`.

If interested in the gritty details, see [the source code](../unpythonic/fun.py) of `unpythonic.fun.curry`. It calls some functions from `unpythonic.dispatch` for its `@generic` support, but otherwise it is pretty much self-contained.

Getting back to the simple case, in the above example:

```python
curry(mapl_one, double, ll(1, 2, 3))
```

the callable ``mapl_one`` takes one argument, which is a function. It returns another function, let us call it ``g``. We are left with:

```python
curry(g, ll(1, 2, 3))
```

The remaining argument is then passed into ``g``; we obtain a result, and reduction is complete.

A curried function is also a curry context:

```python
add2 = lambda x, y: x + y
a2 = curry(add2)
a2(a, b, c)  # same as curry(add2, a, b, c); reduces to (a + b, c)
```

so on the last line, we do not need to say

```python
curry(a2, a, b, c)
```

because ``a2`` is already curried. Doing so does no harm, though; ``curry`` automatically prevents stacking ``curried`` wrappers:

```python
curry(a2) is a2  # --> True
```

If we wish to modify precedence, parentheses are needed, which takes us out of the curry context, unless we explicitly ``curry`` the subexpression. This works:

```python
curry(f, a, curry(g, x, y), b, c)
```

but this **does not**:

```python
curry(f, a, (g, x, y), b, c)
```

because ``(g, x, y)`` is just a tuple of ``g``, ``x`` and ``y``. This is by design; as with all things Python, *explicit is better than implicit*.

**Note**: to code in curried style, a [contract system](https://en.wikipedia.org/wiki/Design_by_contract) or a type checker can be useful. Also, be careful with variadic functions, because any allowable arity will trigger the call.

(The `map` function in the standard library is a particular offender here, since it requires at least one iterable to actually do anything but raise `TypeError`, but its call signature suggests it can be called without any iterables. Hence, for curry-friendliness we provide a wrapper `unpythonic.map` that *requires* at least one iterable.)

- Contract systems for Python include [icontract](https://github.com/Parquery/icontract) and [PyContracts](https://github.com/AndreaCensi/contracts).

- For static type checking, consider [mypy](http://mypy-lang.org/).

- For run-time type checking, consider `@typed` or `@generic` right here in `unpythonic`.

- You can also just use Python's type annotations; `unpythonic`'s `curry` type-checks the arguments before accepting the curried function. The annotations work if the stdlib function [`typing.get_type_hints`](https://docs.python.org/3/library/typing.html#typing.get_type_hints) can find them.


#### ``fix``: break infinite recursion cycles

The name `fix` comes from the *least fixed point* with respect to the definedness relation, which is related to Haskell's `fix` function. However, this `fix` is not that function. Our `fix` breaks recursion cycles in strict functions - thus causing some non-terminating strict functions to return. (Here *strict* means that the arguments are evaluated eagerly.)

**CAUTION**: Worded differently, this function solves a small subset of the halting problem. This should be hint enough that it will only work for the advertised class of special cases - i.e., a specific kind of recursion cycles.

Usage:

```python
from unpythonic import fix, identity

@fix()
def f(...):
    ...
result = f(23, 42)  # start a computation with some args

@fix(bottom=identity)
def f(...):
    ...
result = f(23, 42)
```

If no recursion cycle occurs, `f` returns normally. If a cycle occurs, the call to `f` is aborted (dynamically, when the cycle is detected), and:

 - In the first example, the default special value `typing.NoReturn` is returned.

 - In the latter example, the name `"f"` and the offending args are returned.

**A cycle is detected when** `f` is called again with a set of args that have already been previously seen in the current call chain. Infinite mutual recursion is detected too, at the point where any `@fix`-instrumented function is entered again with a set of args already seen during the current call chain.

**CAUTION**: The infinitely recursive call sequence `f(0) → f(1) → ... → f(k+1) → ...` contains no cycles in the sense detected by `fix`. The `fix` function will not catch all cases of infinite recursion, but only those where a previously seen set of arguments is seen again. (If `f` is pure, the same arguments appearing again implies the call will not return, so we can terminate it.)

**CAUTION**: If we have a function `g(a, b)`, the argument lists of the invocations `g(1, 2)` and `g(a=1, b=2)` are in principle different. This is a Python gotcha that was originally noticed by the author of the `wrapt` library, and mentioned in [its documentation](https://wrapt.readthedocs.io/en/latest/decorators.html#processing-function-arguments). However, once arguments are bound to the formal parameters of `g`, the result is the same. We consider the *resulting bindings*, not the exact way the arguments were passed.

We can use `fix` to find the (arithmetic) fixed point of `cos`:

```python
from math import cos
from unpythonic import fix, identity

# let's use this as the `bottom` callable:
def justargs(funcname, *args):  # bottom doesn't need to accept kwargs if f doesn't.
    return identity(*args)      # identity unpacks if just one

@fix(justargs)
def cosser(x):
    return cosser(cos(x))

c = cosser(1)  # provide starting value
assert c == cos(c)  # 0.7390851332151607
```

This works because the fixed point of `cos` is attractive (see the [Banach fixed point theorem](https://en.wikipedia.org/wiki/Banach_fixed-point_theorem)). The general pattern to find an attractive fixed point with this strategy is:

```python
from functools import partial
from unpythonic import fix, identity

def justargs(funcname, *args):
    return identity(*args)

# setting `bottom=justargs` discards the name "iterate1_rec" from the bottom return value
@fix(justargs)
def iterate1_rec(f, x):
    return iterate1_rec(f, f(x))

def fixpoint(f, x0):
    effer = partial(iterate1_rec, f)
    # f ends up in the return value because it's in the args of iterate1_rec.
    _, c = effer(x0)
    return c

from math import cos
c = fixpoint(cos, x0=1)
assert c == cos(c)
```

**NOTE**: But see `unpythonic.fixpoint`, which is meant specifically for finding *arithmetic* fixed points, and `unpythonic.iterate1`, which produces a generator that iterates `f` without needing recursion.

**Notes**:

  - Our `fix` is a parametric decorator with the signature `def fix(bottom=typing.NoReturn, memo=True):`.

  - `f` must be pure for this to make sense.

  - All args of `f` must be hashable, for technical reasons.

  - The `bottom` parameter (named after the empty type ⊥) specifies the final return value to be returned when a recursion cycle is detected in a call to `f`.

    The default is the special value `typing.NoReturn`, which represents ⊥ in Python. If you just want to detect that a cycle occurred, this is usually fine.

    When bottom is returned, it means the collected evidence shows that *if we were to let `f` continue forever, the call would not return*.

  - `bottom` can be any non-callable value, in which case it is simply returned upon detection of a cycle.

  - `bottom` can be a callable, in which case the function name and args at the point where the cycle was detected are passed to it, and its return value becomes the final return value. This is useful e.g. for debug logging.

  - The `memo` flag controls whether to memoize also intermediate results. It adds some additional function call layers between function entries from recursive calls; if that is a problem (due to causing Python's call stack to blow up faster), use `memo=False`. You can still memoize the final result if you want; just put `@memoize` on the outside.

**NOTE**: If you need `fix` for code that uses TCO, use `fixtco` instead. The implementations of recursion cycle breaking and TCO must interact in a very particular way to work properly; this is done by `fixtco`.

##### Real-world use and historical note

This kind of `fix` is sometimes helpful in recursive pattern-matching definitions for parsers. When the pattern matcher gets stuck in an infinite left-recursion, it can return a customizable special value instead of not terminating. Being able to not care about non-termination may simplify definitions.

This `fix` can also be used to find fixed points of functions, as in the above examples.

The idea comes from Matthew Might's article on [parsing with (Brzozowski's) derivatives](http://matt.might.net/articles/parsing-with-derivatives/), where it was a utility implemented in Racket as the `define/fix` form. It was originally ported to Python [by Per Vognsen](https://gist.github.com/pervognsen/8dafe21038f3b513693e) (linked from the article). The `fix` in `unpythonic` is a redesign with kwargs support, thread safety, and TCO support.

##### Haskell's `fix`?

In Haskell, the function named `fix` computes the *least fixed point* with respect to the definedness ordering. For any strict `f`, we have `fix f = ⊥`. Why? If `f` is strict, `f(⊥) = ⊥` (does not terminate), so `⊥` is a fixed point. On the other hand, `⊥` means also `undefined`, describing a value about which nothing is known. So it is the least fixed point in this sense.

Haskell's `fix` is related to the Y combinator; it is essentially the idea of recursion packaged into a higher-order function. The name in `unpythonic` for the Y combinator idea is `withself`, allowing a lambda to refer to itself by passing in the self-reference from the outside.

A simple way to explain Haskell's `fix` is:

```haskell
fix f = let x = f x in x
```

so anywhere the argument is referred to in the definition of `f`, it is replaced by another application of `f`, recursively. This obviously yields a notation useful for corecursively defining infinite lazy lists.

For more, see [[1]](https://www.parsonsmatt.org/2016/10/26/grokking_fix.html) [[2]](https://www.vex.net/~trebla/haskell/fix.xhtml) [[3]](https://stackoverflow.com/questions/4787421/how-do-i-use-fix-and-how-does-it-work) [[4]](https://medium.com/@cdsmithus/fixpoints-in-haskell-294096a9fc10) [[5]](https://en.wikibooks.org/wiki/Haskell/Fix_and_recursion).


### Batteries for itertools

 - `unpack`: lazily unpack an iterable. Suitable for infinite inputs.
   - Return the first ``n`` items and the ``k``th tail, in a tuple. Default is ``k = n``.
   - Use ``k > n`` to fast-forward, consuming the skipped items. Works by `drop`.
   - Use ``k < n`` to peek without permanently extracting an item. Works by [tee](https://docs.python.org/3/library/itertools.html#itertools.tee)ing; plan accordingly.
 - *folds, scans, unfold*:
   - `foldl`, `foldr` with support for multiple input iterables, like in Racket.
     - Like in Racket, `op(elt, acc)`; general case `op(e1, e2, ..., en, acc)`. Note Python's own `functools.reduce` uses the ordering `op(acc, elt)` instead.
     - No sane default for multi-input case, so the initial value for `acc` must be given.
     - One-input versions with optional init are provided as `reducel`, `reducer`, with semantics similar to Python's `functools.reduce`, but with the rackety ordering `op(elt, acc)`.
     - By default, multi-input folds terminate on the shortest input. To instead terminate on the longest input, use the ``longest`` and ``fillvalue`` kwargs.
     - For multiple inputs with different lengths, `foldr` syncs the **left** ends.
     - `rfoldl`, `rreducel` reverse each input and then left-fold. This syncs the **right** ends.
   - `scanl`, `scanr`: scan (a.k.a. accumulate, partial fold); a lazy fold that returns a generator yielding intermediate results.
     - `scanl` is suitable for infinite inputs.
     - Iteration stops after the final result.
       - For `scanl`, this is what `foldl` would have returned (if the fold terminates at all, i.e. if the shortest input is finite).
       - For `scanr`, **ordering of output is different from Haskell**: we yield the results in the order they are computed (via a linear process).
     - Multiple input iterables and shortest/longest termination supported; same semantics as in `foldl`, `foldr`.
     - One-input versions with optional init are provided as `scanl1`, `scanr1`. Note ordering of arguments to match `functools.reduce`, but op is still the rackety `op(elt, acc)`.
     - `rscanl`, `rscanl1` reverse each input and then left-scan. This syncs the **right** ends.
   - `unfold1`, `unfold`: generate a sequence [corecursively](https://en.wikipedia.org/wiki/Corecursion). The counterpart of `foldl`.
     - `unfold1` is for 1-in-2-out functions. The input is `state`, the return value must be `(value, newstate)` or `None`.
     - `unfold` is for n-in-(1+n)-out functions. The input is `*states`, the return value must be `(value, *newstates)` or `None`.
     - Unfold returns a generator yielding the collected values. The output can be finite or infinite; to signify that a finite sequence ends, the user function must return `None`.
 - *mapping and zipping*:
   - `map_longest`: the final missing battery for `map`.
     - Essentially `starmap(func, zip_longest(*iterables))`, so it's [spanned](https://en.wikipedia.org/wiki/Linear_span) by ``itertools``.
   - `rmap`, `rzip`, `rmap_longest`, `rzip_longest`: reverse each input, then map/zip. For multiple inputs, syncs the **right** ends.
   - `mapr`, `zipr`, `mapr_longest`, `zipr_longest`: map/zip, then reverse the result. For multiple inputs, syncs the **left** ends.
   - `map`: curry-friendly wrapper for the builtin, making it mandatory to specify at least one iterable. **Added in v0.14.2.**
 - *windowing, chunking, and similar*:
   - `window`: sliding length-n window iterator for general iterables. Acts like the well-known [n-gram zip trick](http://www.locallyoptimal.com/blog/2013/01/20/elegant-n-gram-generation-in-python/), but the input can be any iterable. **Changed in v0.15.0.** *Parameter ordering is now `window(n, iterable)`, to make it curry-friendly.*
   - `chunked`: split an iterable into constant-length chunks. **Added in v0.14.2.**
   - `pad`: extend an iterable to length at least `n` with a `fillvalue`. **Added in v0.14.2.**
   - `interleave`: interleave items from several iterables: `interleave(a, b, c)` → `a0, b0, c0, a1, b1, c1, ...` until the next item does not exist. **Added in v0.14.2.**
     - This differs from `zip` in that the output is flattened, and the termination condition is checked after each item. So e.g. `interleave(['a', 'b', 'c'], ['+', '*'])` → `['a', '+', 'b', '*', 'c']` (the actual return value is a generator, not a list).
 - *flattening*:
   - `flatmap`: map a function, that returns a list or tuple, over an iterable and then flatten by one level, concatenating the results into a single tuple.
     - Essentially, ``composel(map(...), flatten1)``; the same thing the bind operator of the List monad does.
   - `flatten1`, `flatten`, `flatten_in`: remove nested list structure.
     - `flatten1`: outermost level only.
     - `flatten`: recursive, with an optional predicate that controls whether to flatten a given sublist.
     - `flatten_in`: recursive, with an optional predicate; but recurse also into items which don't match the predicate.
 - *extracting items, subsequences*:
   - `take`, `drop`, `split_at`: based on `itertools` [recipes](https://docs.python.org/3/library/itertools.html#itertools-recipes).
     - Especially useful for testing generators.
     - `islice` is maybe more pythonic than `take` and `drop`. We provide a utility that supports the slice syntax.
   - `tail`: return the tail of an iterable. Same as `drop(1, iterable)`; common use case.
   - `butlast`, `butlastn`: return a generator that yields from iterable, dropping the last `n` items if the iterable is finite. Inspired by a similar utility in PG's [On Lisp](http://paulgraham.com/onlisp.html).
     - Works by using intermediate storage. **Do not** use the original iterator after a call to `butlast` or `butlastn`.
   - `lastn`: yield the last `n` items from an iterable. Works by intermediate storage. Will not terminate for infinite iterables. **Added in v0.14.2.**
   - `first`, `second`, `nth`, `last`: return the specified item from an iterable. Any preceding items are consumed at C speed.
   - `partition` from `itertools` [recipes](https://docs.python.org/3/library/itertools.html#itertools-recipes).
   - `find`: return the first item that matches a predicate. Convenience function; if you need them all, just use `filter` or a comprehension. **Added in v0.14.2.**
     - Can be useful for the occasional abuse of `collections.deque` as an *alist* [[1]](https://en.wikipedia.org/wiki/Association_list) [[2]](http://www.gigamonkeys.com/book/beyond-lists-other-uses-for-cons-cells.html). Use `.appendleft(...)` to add new items, and then this `find` to get the currently active association.
   - `running_minmax`, `minmax`: Extract both min and max in one pass over an iterable. The `running_` variant is a scan and returns a generator; the just-give-me-the-final-result variant is a fold. **Added in v0.14.2.**
 - *math-related*:
   - `within`: yield items from iterable until successive iterates are close enough. Useful with [Cauchy sequences](https://en.wikipedia.org/wiki/Cauchy_sequence). **Added in v0.14.2.**
   - `prod`: like the builtin `sum`, but compute the product. Oddly missing from the standard library.
   - `iterate1`, `iterate`: return an infinite generator that yields `x`, `f(x)`, `f(f(x))`, ...
     - `iterate1` is for 1-to-1 functions; `iterate` for n-to-n, unpacking the return value to the argument list of the next call.
 - *miscellaneous*:
   - `uniqify`, `uniq`: remove duplicates (either all or consecutive only, respectively), preserving the original ordering of the items.
   - `rev` is a convenience function that tries `reversed`, and if the input was not a sequence, converts it to a tuple and reverses that. The return value is a `reversed` object.
   - `scons`: prepend one element to the start of an iterable, return new iterable. ``scons(x, iterable)`` is lispy shorthand for ``itertools.chain((x,), iterable)``, allowing to omit the one-item tuple wrapper.
   - `inn`: contains-check (``x in iterable``) with automatic termination for monotonic divergent infinite iterables.
     - Only applicable to monotonic divergent inputs (such as ``primes``). Increasing/decreasing is auto-detected from the first non-zero diff, but the function may fail to terminate if the input is actually not monotonic, or has an upper/lower bound.
   - `iindex`: like ``list.index``, but for a general iterable. Consumes the iterable, so only makes sense for memoized inputs.
   - `CountingIterator`: count how many items have been yielded, as a side effect. The count is stored in the `.count` attribute. **Added in v0.14.2.**
   - `slurp`: extract all items from a `queue.Queue` (until it is empty) to a list, returning that list. **Added in v0.14.2.**
   - `subset`: test whether an iterable is a subset of another. **Added in v0.14.3.**
   - `powerset`: yield the power set (set of all subsets) of an iterable. Works also for potentially infinite iterables, if only a finite prefix is ever requested. (But beware, both runtime and memory usage are exponential in the input size.) **Added in v0.14.2.**
   - `allsame`: test whether all elements of an iterable are the same. Sometimes useful in writing testing code. **Added in v0.14.3.**

Examples:

```python
from functools import partial
from unpythonic import (scanl, scanr, foldl, foldr,
                        mapr, zipr,
                        uniqify, uniq,
                        flatten1, flatten, flatten_in, flatmap,
                        take, drop,
                        unfold, unfold1,
                        cons, nil, ll, curry,
                        s, inn, iindex,
                        window,
                        subset, powerset,
                        allsame)

assert tuple(scanl(add, 0, range(1, 5))) == (0, 1, 3, 6, 10)
assert tuple(scanr(add, 0, range(1, 5))) == (0, 4, 7, 9, 10)
assert tuple(scanl(mul, 1, range(2, 6))) == (1, 2, 6, 24, 120)
assert tuple(scanr(mul, 1, range(2, 6))) == (1, 5, 20, 60, 120)

assert tuple(scanl(cons, nil, ll(1, 2, 3))) == (nil, ll(1), ll(2, 1), ll(3, 2, 1))
assert tuple(scanr(cons, nil, ll(1, 2, 3))) == (nil, ll(3), ll(2, 3), ll(1, 2, 3))

def step2(k):  # x0, x0 + 2, x0 + 4, ...
    return (k, k + 2)  # value, newstate
assert tuple(take(10, unfold1(step2, 10))) == (10, 12, 14, 16, 18, 20, 22, 24, 26, 28)

def nextfibo(a, b):
    return (a, b, a + b)  # value, *newstates
assert tuple(take(10, unfold(nextfibo, 1, 1))) == (1, 1, 2, 3, 5, 8, 13, 21, 34, 55)

def fibos():
    a, b = 1, 1
    while True:
        yield a
        a, b = b, a + b
a1, a2, a3, tl = unpack(3, fibos())
a4, a5, tl = unpack(2, tl)
print(a1, a2, a3, a4, a5, tl)  # --> 1 1 2 3 5 <generator object fibos at 0x7fe65fb9f798>

# inn: contains-check with automatic termination for monotonic iterables (infinites ok)
evens = imemoize(s(2, 4, ...))
assert inn(42, evens())
assert not inn(41, evens())

@gmemoize
def primes():
    yield 2
    for n in count(start=3, step=2):
        if not any(n % p == 0 for p in takewhile(lambda x: x*x <= n, primes())):
            yield n
assert inn(31337, primes())
assert not inn(1337, primes())

# partition: split an iterable according to a predicate
iseven = lambda x: x % 2 == 0
assert [tuple(it) for it in partition(iseven, range(10))] == [(1, 3, 5, 7, 9), (0, 2, 4, 6, 8)]

# partition_int: split a small positive integer, in all possible ways, into smaller integers that sum to it
assert tuple(partition_int(4)) == ((1, 1, 1, 1), (1, 1, 2), (1, 2, 1), (1, 3), (2, 1, 1), (2, 2), (3, 1), (4,))
assert all(sum(terms) == 10 for terms in partition_int(10))

# iindex: find index of item in iterable (mostly only makes sense for memoized input)
assert iindex(2, (1, 2, 3)) == 1
assert iindex(31337, primes()) == 3378

# find: return first item matching predicate (convenience function)
gen = (x for x in range(5))
assert find(lambda x: x >= 3, gen) == 3
assert find(lambda x: x >= 3, gen) == 4  # if consumable, consumed as usual

# window: length-n sliding window iterator for general iterables
lst = (x for x in range(5))
out = []
for a, b, c in window(3, lst):
    out.append((a, b, c))
assert out == [(0, 1, 2), (1, 2, 3), (2, 3, 4)]

# subset
assert subset([1, 2, 3], [1, 2, 3, 4, 5])
assert subset({"cat"}, {"cat", "lynx"})

# power set (set of all subsets) of an iterable
assert tuple(powerset(range(3))) == ((0,), (1,), (0, 1), (2,), (0, 2), (1, 2), (0, 1, 2))
r = range(10)
assert all(subset(s, r) for s in powerset(r))

# test whether all elements of a finite iterable are the same
assert allsame(())
assert allsame((1,))
assert allsame((8, 8, 8, 8, 8))
assert not allsame((1, 2, 3))

# flatmap
def msqrt(x):  # multivalued sqrt
    if x == 0.:
        return (0.,)
    else:
        s = x**0.5
        return (s, -s)
assert tuple(flatmap(msqrt, (0, 1, 4, 9))) == (0., 1., -1., 2., -2., 3., -3.)

# zipr reverses, then iterates.
assert tuple(zipr((1, 2, 3), (4, 5, 6), (7, 8))) == ((3, 6, 8), (2, 5, 7))

zipr2 = partial(mapr, identity)  # mapr works the same way.
assert tuple(zipr2((1, 2, 3), (4, 5, 6), (7, 8))) == ((3, 6, 8), (2, 5, 7))

# foldr doesn't; it walks from the left, but collects results from the right:
zipr1 = curry(foldr, zipper, ())
assert zipr1((1, 2, 3), (4, 5, 6), (7, 8)) == ((2, 5, 8), (1, 4, 7))
# so the result is reversed(zip(...)), whereas zipr gives zip(*(reversed(s) for s in ...))

assert tuple(uniqify((1, 1, 2, 2, 2, 1, 2, 2, 4, 3, 4, 3, 3))) == (1, 2, 4, 3)  # all
assert tuple(uniq((1, 1, 2, 2, 2, 1, 2, 2, 4, 3, 4, 3, 3))) == (1, 2, 1, 2, 4, 3, 4, 3)  # consecutive

assert tuple(flatten1(((1, 2), (3, (4, 5), 6), (7, 8, 9)))) == (1, 2, 3, (4, 5), 6, 7, 8, 9)
assert tuple(flatten(((1, 2), (3, (4, 5), 6), (7, 8, 9)))) == (1, 2, 3, 4, 5, 6, 7, 8, 9)

is_nested = lambda sublist: all(isinstance(x, (list, tuple)) for x in sublist)
assert tuple(flatten((((1, 2), (3, 4)), (5, 6)), is_nested)) == ((1, 2), (3, 4), (5, 6))

data = (((1, 2), ((3, 4), (5, 6)), 7), ((8, 9), (10, 11)))
assert tuple(flatten(data, is_nested))    == (((1, 2), ((3, 4), (5, 6)), 7), (8, 9), (10, 11))
assert tuple(flatten_in(data, is_nested)) == (((1, 2), (3, 4), (5, 6), 7),   (8, 9), (10, 11))

with_n = lambda *args: (partial(f, n) for n, f in args)
clip = lambda n1, n2: composel(*with_n((n1, drop), (n2, take)))
assert tuple(clip(5, 10)(range(20))) == tuple(range(5, 15))
```

In the last example, essentially we just want to `clip 5 10 (range 20)`, the grouping of the parentheses being pretty much an implementation detail. With ``curry``, we can rewrite the last line as:

```python
assert tuple(curry(clip, 5, 10, range(20)) == tuple(range(5, 15))
```

### Batteries for network programming

**Added in v0.14.2**.

While all other pure-Python features of `unpythonic` live in the main `unpythonic` package, the network-related features are placed in the subpackage `unpythonic.net`. This subpackage also contains the [REPL server and client](repl.md) for hot-patching live processes.

- `unpythonic.net.msg`: A simplistic message protocol for sending message data over a stream-based transport, such as TCP.
- `unpythonic.net.ptyproxy`: Proxy between a Linux [PTY](https://en.wikipedia.org/wiki/Pseudoterminal) and a network socket. Useful for serving terminal utilities over the network. The selling point is this doesn't use `pty.spawn`, so it can be used for proxying also Python libraries that expect to run in a terminal.
- `unpythonic.net.util`: Miscellaneous small utilities.

The thing about stream-based transports is that they have no concept of a message boundary [[1]](http://stupidpythonideas.blogspot.com/2013/05/sockets-are-byte-streams-not-message.html) [[2]](https://eli.thegreenplace.net/2011/08/02/length-prefix-framing-for-protocol-buffers) [[3]](https://docs.python.org/3/howto/sockets.html). This is where a message protocol comes in. We provide a [sans-io](https://sans-io.readthedocs.io/) implementation of a minimalistic custom protocol that adds rudimentary [message framing](https://blog.stephencleary.com/2009/04/message-framing.html) and [stream re-synchronization](https://en.wikipedia.org/wiki/Frame_synchronization). Example:

```python
from io import BytesIO, SEEK_SET

from unpythonic.net.msg import encodemsg, MessageDecoder
from unpythonic.net.util import bytessource, streamsource  # have also socketsource

# Encode a message:
rawdata = b"hello world"
message = encodemsg(rawdata)
# Decode a message:
decoder = MessageDecoder(bytessource(message))
assert decoder.decode() == b"the quick brown fox jumps over the lazy dog"
assert decoder.decode() is None  # The message is consumed by the first decode.

bio = BytesIO()
bio.write(encodemsg(b"hello world"))
bio.write(encodemsg(b"hello again"))
bio.seek(0, SEEK_SET)
# A streamsource accepts any byte stream, such as BytesIO,
# and files opened with open().
decoder = MessageDecoder(streamsource(bio))
assert decoder.decode() == b"hello world"
assert decoder.decode() == b"hello again"
assert decoder.decode() is None

# If junk arrives between messages, the protocol automatically
# re-synchronizes when retrieving the next message.
bio = BytesIO()
bio.write(encodemsg(b"cat"))
bio.write(b"junk junk junk")  # not a message!
bio.write(encodemsg(b"mew"))
bio.seek(0, SEEK_SET)
decoder = MessageDecoder(streamsource(bio))
assert decoder.decode() == b"cat"
assert decoder.decode() == b"mew"
assert decoder.decode() is None
```

For a usage example of `unpythonic.net.PTYProxy`, see the source code of `unpythonic.net.server`.


### ``islice``: slice syntax support for ``itertools.islice`

**Changed in v0.14.2.** *Added support for negative `start` and `stop`.*

Slice an iterable, using the regular slicing syntax:

```python
from unpythonic import islice, primes, s

p = primes()
assert tuple(islice(p)[10:15]) == (31, 37, 41, 43, 47)

assert tuple(islice(primes())[10:15]) == (31, 37, 41, 43, 47)

p = primes()
assert islice(p)[10] == 31

odds = islice(s(1, 2, ...))[::2]
assert tuple(islice(odds)[:5]) == (1, 3, 5, 7, 9)
assert tuple(islice(odds)[:5]) == (11, 13, 15, 17, 19)  # five more
```

As a convenience feature: a single index is interpreted as a length-1 islice starting at that index. The slice is then immediately evaluated and the item is returned.

The slicing variant calls ``itertools.islice`` with the corresponding slicing parameters, after possibly converting negative `start` and `stop` to the appropriate positive values.

**CAUTION**: When using negative `start` and/or `stop`, we must consume the whole iterable to determine where it ends, if at all. Obviously, this will not terminate for infinite iterables.

**CAUTION**: Keep in mind that negative `step` is not supported, and that the slicing process consumes elements from the iterable.

Like ``fup``, our ``islice`` is essentially a manually curried function with unusual syntax; the initial call to ``islice`` passes in the iterable to be sliced. The object returned by the call accepts a subscript to specify the slice or index. Once the slice or index is provided, the call to ``itertools.islice`` triggers.

Inspired by Python itself.


### `gmemoize`, `imemoize`, `fimemoize`: memoize generators

Make generator functions (gfunc, i.e. a generator definition) which create memoized generators, similar to how streams behave in Racket.

Memoize iterables; like `itertools.tee`, but no need to know in advance how many copies of the iterator will be made. Provided for both iterables and for factory functions that make iterables.

 - `gmemoize` is a decorator for a gfunc, which makes it memoize the instantiated generators.
   - If the gfunc takes arguments, they must be hashable. A separate memoized sequence is created for each unique set of argument values seen.
   - For simplicity, the generator itself may use ``yield`` for output only; ``send`` is not supported.
   - Any exceptions raised by the generator (except StopIteration) are also memoized, like in ``memoize``.
   - Thread-safe. Calls to ``next`` on the memoized generator from different threads are serialized via a lock. Each memoized sequence has its own lock. This uses ``threading.RLock``, so re-entering from the same thread (e.g. in recursively defined sequences) is fine.
   - The whole history is kept indefinitely. For infinite iterables, use this only if you can guarantee that only a reasonable number of terms will ever be evaluated (w.r.t. available RAM).
   - Typically, this should be the outermost decorator if several are used on the same gfunc.
 - `imemoize`: memoize an iterable. Like `itertools.tee`, but keeps the whole history, so more copies can be teed off later.
   - Same limitation: **do not** use the original iterator after it is memoized. The danger is that if anything other than the memoization mechanism advances the original iterator, some values will be lost before they can reach the memo.
   - Returns a gfunc with no parameters which, when called, returns a generator that yields items from the memoized iterable. The original iterable is used to retrieve more terms when needed.
   - Calling the gfunc essentially tees off a new instance, which begins from the first memoized item.
 - `fimemoize`: convert a factory function, that returns an iterable, into the corresponding gfunc, and `gmemoize` that. Return the memoized gfunc.
   - Especially convenient with short lambdas, where `(yield from ...)` instead of `...` is just too much text.

```python
from itertools import count, takewhile
from unpythonic import gmemoize, imemoize, fimemoize, take, nth

@gmemoize
def primes():  # FP sieve of Eratosthenes
    yield 2
    for n in count(start=3, step=2):
        if not any(n % p == 0 for p in takewhile(lambda x: x*x <= n, primes())):
            yield n
assert tuple(take(10, primes())) == (2, 3, 5, 7, 11, 13, 17, 19, 23, 29)
assert nth(3378, primes()) == 31337  # with memo, linear process; no crash

# but be careful:
31337 in primes()  # --> True
1337 in takewhile(lambda p: p <= 1337, primes())  # not prime, need takewhile() to stop

# or use unpythonic.inn, which auto-terminates on monotonic iterables:
from unpythonic import inn
inn(31337, primes())  # --> True
inn(1337, primes())  # --> False
```

Memoizing only a part of an iterable. This is where `imemoize` and `fimemoize` can be useful. The basic idea is to make a chain of generators, and only memoize the last one:

```python
from unpythonic import gmemoize, drop, last

def evens():  # the input iterable
    yield from (x for x in range(100) if x % 2 == 0)

@gmemoize
def some_evens(n):  # we want to memoize the result without the n first terms
    yield from drop(n, evens())

assert last(some_evens(25)) == last(some_evens(25))  # iterating twice!
```

Using a lambda, we can also write ``some_evens`` as:

```python
se = gmemoize(lambda n: (yield from drop(n, evens())))
assert last(se(25)) == last(se(25))
```

Using `fimemoize`, we can omit the ``yield from``, shortening this to:

```python
se = fimemoize(lambda n: drop(n, evens()))
assert last(se(25)) == last(se(25))
```

If we don't need to take an argument, we can memoize the iterable directly, using ``imemoize``:

```python
se = imemoize(drop(25, evens()))
assert last(se()) == last(se())  # se is a gfunc, so call it to get a generator instance
```

Finally, compare the `fimemoize` example, rewritten using `def`, to the original `gmemoize` example:

```python
@fimemoize
def some_evens(n):
    return drop(n, evens())

@gmemoize
def some_evens(n):
    yield from drop(n, evens())
```

The only differences are the name of the decorator and ``return`` vs. ``yield from``. The point of `fimemoize` is that in simple cases like this, it allows us to use a regular factory function that makes an iterable, instead of a gfunc. Of course, the gfunc could have several `yield` expressions before it finishes, whereas the factory function terminates at the `return`.


### ``fup``: Functional update; ``ShadowedSequence``

We provide ``ShadowedSequence``, which is a bit like ``collections.ChainMap``, but for sequences, and only two levels (but it's a sequence; instances can be chained). It supports slicing (read-only), equality comparison, ``str`` and ``repr``. Out-of-range read access to a single item emits a meaningful error, like in ``list``. See the docstring of ``ShadowedSequence`` for details.

The function ``fupdate`` functionally updates sequences and mappings. Whereas ``ShadowedSequence`` reads directly from the original sequences at access time, ``fupdate`` makes a shallow copy, of the same type as the given input sequence, when it finalizes its output.

**The preferred way** to use ``fupdate`` on sequences is through the ``fup`` utility function, which specializes ``fupdate`` to sequences, and adds support for Python's standard slicing syntax:

```python
from unpythonic import fup
from itertools import repeat

lst = (1, 2, 3, 4, 5)
assert fup(lst)[3] << 42 == (1, 2, 3, 42, 5)
assert fup(lst)[0::2] << tuple(repeat(10, 3)) == (10, 2, 10, 4, 10)
```

Currently only one update specification is supported in a single ``fup()``. (The ``fupdate`` function supports more; see below.)

The notation follows the ``unpythonic`` convention that ``<<`` denotes an assignment of some sort. Here it denotes a functional update, which returns a modified copy, leaving the original untouched.

The ``fup`` call is essentially curried. It takes in the sequence to be functionally updated. The object returned by the call accepts a subscript to specify the index or indices. This then returns another object that accepts a left-shift to specify the values. Once the values are provided, the underlying call to ``fupdate`` triggers, and the result is returned.

The ``fupdate`` function itself works as follows:

```python
from unpythonic import fupdate

lst = [1, 2, 3]
out = fupdate(lst, 1, 42)
assert lst == [1, 2, 3]  # the original remains untouched
assert out == [1, 42, 3]

lst = [1, 2, 3]
out = fupdate(lst, -1, 42)  # negative indices also supported
assert lst == [1, 2, 3]
assert out == [1, 2, 42]
```

Immutable input sequences are allowed. Replacing a slice of a tuple by a sequence:

```python
from itertools import repeat
lst = (1, 2, 3, 4, 5)
assert fupdate(lst, slice(0, None, 2), tuple(repeat(10, 3))) == (10, 2, 10, 4, 10)
assert fupdate(lst, slice(1, None, 2), tuple(repeat(10, 2))) == (1, 10, 3, 10, 5)
assert fupdate(lst, slice(None, None, 2), tuple(repeat(10, 3))) == (10, 2, 10, 4, 10)
assert fupdate(lst, slice(None, None, -1), tuple(range(5))) == (4, 3, 2, 1, 0)
```

Slicing supports negative indices and steps, and default starts, stops and steps, as usual in Python. Just remember ``a[start:stop:step]`` actually means ``a[slice(start, stop, step)]`` (with ``None`` replacing omitted ``start``, ``stop`` and ``step``), and everything should follow. Multidimensional arrays are **not** supported.

When ``fupdate`` constructs its output, the replacement occurs by walking *the input sequence* left-to-right, and pulling an item from the replacement sequence when the given replacement specification so requires. Hence the replacement sequence is not necessarily accessed left-to-right. (In the last example above, ``tuple(range(5))`` was read in the order ``(4, 3, 2, 1, 0)``.)

The replacement sequence must have at least as many items as the slice requires (when applied to the original input). Any extra items in the replacement sequence are simply ignored (so e.g. an infinite ``repeat`` is fine), but if the replacement is too short, ``IndexError`` is raised.

It is also possible to replace multiple individual items. These are treated as separate specifications, applied left to right (so later updates shadow earlier ones, if updating at the same index):

```python
lst = (1, 2, 3, 4, 5)
out = fupdate(lst, (1, 2, 3), (17, 23, 42))
assert lst == (1, 2, 3, 4, 5)
assert out == (1, 17, 23, 42, 5)
```

Multiple specifications can be used with slices and sequences as well:

```python
lst = tuple(range(10))
out = fupdate(lst, (slice(0, 10, 2), slice(1, 10, 2)),
                   (tuple(repeat(2, 5)), tuple(repeat(3, 5))))
assert lst == tuple(range(10))
assert out == (2, 3, 2, 3, 2, 3, 2, 3, 2, 3)
```

Strictly speaking, each specification can be either a slice/sequence pair or an index/item pair:

```python
lst = tuple(range(10))
out = fupdate(lst, (slice(0, 10, 2), slice(1, 10, 2), 6),
                   (tuple(repeat(2, 5)), tuple(repeat(3, 5)), 42))
assert lst == tuple(range(10))
assert out == (2, 3, 2, 3, 2, 3, 42, 3, 2, 3)
```

Also mappings can be functionally updated:

```python
d1 = {'foo': 'bar', 'fruit': 'apple'}
d2 = fupdate(d1, foo='tavern')
assert sorted(d1.items()) == [('foo', 'bar'), ('fruit', 'apple')]
assert sorted(d2.items()) == [('foo', 'tavern'), ('fruit', 'apple')]
```

For immutable mappings, ``fupdate`` supports ``frozendict`` (see below). Any other mapping is assumed mutable, and ``fupdate`` essentially just performs ``copy.copy()`` and then ``.update()``.

We can also functionally update a namedtuple:

```python
from collections import namedtuple
A = namedtuple("A", "p q")
a = A(17, 23)
out = fupdate(a, 0, 42)
assert a == A(17, 23)
assert out == A(42, 23)
```

Namedtuples export only a sequence interface, so they cannot be treated as mappings.

Support for ``namedtuple`` requires an extra feature, which is available for custom classes, too. When constructing the output sequence, ``fupdate`` first checks whether the input type has a ``._make()`` method, and if so, hands the iterable containing the final data to that to construct the output. Otherwise the regular constructor is called (and it must accept a single iterable).

### ``view``: writable, sliceable view into a sequence

A writable view into a sequence, with slicing, so you can take a slice of a slice (of a slice ...), and it reflects the original both ways:

```python
from unpythonic import view

lst = list(range(10))
v = view(lst)[::2]
assert v == [0, 2, 4, 6, 8]
v2 = v[1:-1]
assert v2 == [2, 4, 6]
v2[1:] = (10, 20)
assert lst == [0, 1, 2, 3, 10, 5, 20, 7, 8, 9]

lst[2] = 42
assert v == [0, 42, 10, 20, 8]
assert v2 == [42, 10, 20]

lst = list(range(5))
v = view(lst)[2:4]
v[:] = 42  # scalar broadcast
assert lst == [0, 1, 42, 42, 4]
```

While ``fupdate`` lets you be more functional than Python otherwise allows, ``view`` lets you be more imperative than Python otherwise allows.

We store slice specs, not actual indices, so this works also if the underlying sequence undergoes length changes.

Slicing a view returns a new view. Slicing anything else will usually copy, because the object being sliced does, before we get control. To slice lazily, first view the sequence itself and then slice that. The initial no-op view is optimized away, so it won't slow down accesses. Alternatively, pass a ``slice`` object into the ``view`` constructor.

The view can be efficiently iterated over. As usual, iteration assumes that no inserts/deletes in the underlying sequence occur during the iteration.

Getting/setting an item (subscripting) checks whether the index cache needs updating during each access, so it can be a bit slow. Setting a slice checks just once, and then updates the underlying iterable directly. Setting a slice to a scalar value broadcasts the scalar à la NumPy.

The ``unpythonic.collections`` module also provides the ``SequenceView`` and ``MutableSequenceView`` abstract base classes; ``view`` is a ``MutableSequenceView``.

There is the read-only cousin ``roview``, which behaves the same except it has no ``__setitem__`` or ``reverse``. This can be useful for giving read-only access to an internal sequence. The constructor of the writable ``view`` checks that the input is not read-only (``roview``, or a ``Sequence`` that is not also a ``MutableSequence``) before allowing creation of the writable view.


### ``mogrify``: update a mutable container in-place

**Changed in v0.14.3.** *`mogrify` now skips `nil`, actually making it useful for processing `ll` linked lists.*

Recurse on given container, apply a function to each atom. If the container is mutable, then update in-place; if not, then construct a new copy like ``map`` does.

If the container is a mapping, the function is applied to the values; keys are left untouched.

Unlike ``map`` and its cousins, only a single input container is supported. (Supporting multiple containers as input would require enforcing some compatibility constraints on their type and shape, since ``mogrify`` is not limited to sequences.)

```python
from unpythonic import mogrify

lst1 = [1, 2, 3]
lst2 = mogrify(lst1, lambda x: x**2)
assert lst2 == [2, 4, 6]
assert lst2 is lst1
```

Containers are detected by checking for instances of ``collections.abc`` superclasses (also virtuals are ok). Supported abcs are ``MutableMapping``, ``MutableSequence``, ``MutableSet``, ``Mapping``, ``Sequence`` and ``Set``. Any value that does not match any of these is treated as an atom. Containers can be nested, with an arbitrary combination of the types supported.

For convenience, we introduce some special cases:

  - Any classes created by ``collections.namedtuple``, because they do not conform to the standard constructor API for a ``Sequence``.

    Thus, for (an immutable) ``Sequence``, we first check for the presence of a ``._make()`` method, and if found, use it as the constructor. Otherwise we use the regular constructor.

  - ``str`` is treated as an atom, although technically a ``Sequence``.

    It doesn't conform to the exact same API (its constructor does not take an iterable), and often we don't want to treat strings as containers anyway.

    If you want to process strings, implement it in your function that is called by ``mogrify``.

  - The ``box``, `ThreadLocalBox` and `Some` containers from ``unpythonic.collections``. Although the first two are mutable, their update is not conveniently expressible by the ``collections.abc`` APIs.

  - The ``cons`` container from ``unpythonic.llist`` (including the ``ll``, ``llist`` linked lists). This is treated with the general tree strategy, so nested linked lists will be flattened, and the final ``nil`` is also processed.

    Note that since ``cons`` is immutable, anyway, if you know you have a long linked list where you need to update the values, just iterate over it and produce a new copy - that will work as intended.


### ``s``, ``imathify``, ``gmathify``: lazy mathematical sequences with infix arithmetic

**Changed in v0.14.3.** Added convenience mode to generate cyclic infinite sequences.

**Changed in v0.14.3.** To improve descriptiveness, and for consistency with names of other abstractions in `unpythonic`, `m` has been renamed `imathify` and `mg` has been renamed `gmathify`. The old names will continue working in v0.14.x, and will be removed in v0.15.0. This is a one-time change; it is not likely that these names will be changed ever again.

We provide a compact syntax to create lazy constant, cyclic, arithmetic, geometric and power sequences: ``s(...)``. Numeric (``int``, ``float``, ``mpmath``) and symbolic (SymPy) formats are supported. We avoid accumulating roundoff error when used with floating-point formats.

We also provide arithmetic operation support for iterables (termwise). To make any iterable infix math aware, use ``imathify(iterable)``. The arithmetic is lazy; it just plans computations, returning a new lazy mathematical sequence. To extract values, iterate over the result. (Note this implies that expressions consisting of thousands of operations will overflow Python's call stack. In practice this shouldn't be a problem.)

The function versions of the arithmetic operations (also provided, à la the ``operator`` module) have an **s** prefix (short for mathematical **sequence**), because in Python the **i** prefix (which could stand for *iterable*) is already used to denote the in-place operators.

We provide the [Cauchy product](https://en.wikipedia.org/wiki/Cauchy_product), and its generalization, the diagonal combination-reduction, for two (possibly infinite) iterables. Note ``cauchyprod`` **does not sum the series**; given the input sequences ``a`` and ``b``, the call ``cauchyprod(a, b)`` computes the elements of the output sequence ``c``.

We also provide ``gmathify``, a decorator to mathify a gfunc, so that it will ``imathify()`` the generator instances it makes. Combo with ``imemoize`` for great justice, e.g. ``a = gmathify(imemoize(myiterable))``, and then ``a()`` to instantiate a memoized-and-mathified copy.

Finally, we provide ready-made generators that yield some common sequences (currently, the Fibonacci numbers, the triangular numbers, and the prime numbers). The prime generator is an FP-ized sieve of Eratosthenes.

```python
from unpythonic import s, imathify, cauchyprod, take, last, fibonacci, triangular, primes

assert tuple(take(10, s(1, ...))) == (1,)*10
assert tuple(take(10, s(1, 2, ...))) == tuple(range(1, 11))
assert tuple(take(10, s(1, 2, 4, ...))) == (1, 2, 4, 8, 16, 32, 64, 128, 256, 512)
assert tuple(take(5, s(2, 4, 16, ...))) == (2, 4, 16, 256, 65536)  # 2, 2**2, (2**2)**2, ...

assert tuple(take(10, s([8], ...))) == (8,) * 10
assert tuple(take(10, s(1, [8], ...))) == (1,) + (8,) * 9
assert tuple(take(10, s([1, 2], ...))) == (1, 2) * 5
assert tuple(take(10, s(1, 2, [3, 4], ...))) == (1, 2) + (3, 4) * 4

assert tuple(s(1, 2, ..., 10)) == tuple(range(1, 11))
assert tuple(s(1, 2, 4, ..., 512)) == (1, 2, 4, 8, 16, 32, 64, 128, 256, 512)

assert tuple(take(5, s(1, -1, 1, ...))) == (1, -1, 1, -1, 1)

assert tuple(take(5, s(1, 3, 5, ...) + s(2, 4, 6, ...))) == (3, 7, 11, 15, 19)
assert tuple(take(5, s(1, 3, ...) * s(2, 4, ...))) == (2, 12, 30, 56, 90)

assert tuple(take(5, s(1, 3, ...)**s(2, 4, ...))) == (1, 3**4, 5**6, 7**8, 9**10)
assert tuple(take(5, s(1, 3, ...)**2)) == (1, 3**2, 5**2, 7**2, 9**2)
assert tuple(take(5, 2**s(1, 3, ...))) == (2**1, 2**3, 2**5, 2**7, 2**9)

assert tuple(take(3, cauchyprod(s(1, 3, 5, ...), s(2, 4, 6, ...)))) == (2, 10, 28)

assert tuple(take(10, primes())) == (2, 3, 5, 7, 11, 13, 17, 19, 23, 29)
assert tuple(take(10, fibonacci())) == (1, 1, 2, 3, 5, 8, 13, 21, 34, 55)
assert tuple(take(10, triangular())) == (1, 3, 6, 10, 15, 21, 28, 36, 45, 55)
```

A math iterable (i.e. one that has infix math support) is an instance of the class ``imathify``:

```python
a = s(1, 3, ...)
b = s(2, 4, ...)
c = a + b
assert isinstance(a, imathify)
assert isinstance(b, imathify)
assert isinstance(c, imathify)
assert tuple(take(5, c)) == (3, 7, 11, 15, 19)

d = 1 / (a + b)
assert isinstance(d, imathify)
```

Applying an operation meant for regular (non-math) iterables will drop the arithmetic support, but it can be restored by `imathify`-ing manually:

```python
e = take(5, c)
assert not isinstance(e, imathify)

f = imathify(take(5, c))
assert isinstance(f, imathify)
```

Symbolic expression support with SymPy:

```python
from unpythonic import s
from sympy import symbols

x0 = symbols("x0", real=True)
k = symbols("k", positive=True)

assert tuple(take(4, s(x0, ...))) == (x0, x0, x0, x0)
assert tuple(take(4, s(x0, x0 + k, ...))) == (x0, x0 + k, x0 + 2*k, x0 + 3*k)
assert tuple(take(4, s(x0, x0*k, x0*k**2, ...))) == (x0, x0*k, x0*k**2, x0*k**3)

assert tuple(s(x0, x0 + k, ..., x0 + 3*k)) == (x0, x0 + k, x0 + 2*k, x0 + 3*k)
assert tuple(s(x0, x0*k, x0*k**2, ..., x0*k**5)) == (x0, x0*k, x0*k**2, x0*k**3, x0*k**4, x0*k**5)

x0, k = symbols("x0, k", positive=True)
assert tuple(s(x0, x0**k, x0**(k**2), ..., x0**(k**4))) == (x0, x0**k, x0**(k**2), x0**(k**3), x0**(k**4))

x = symbols("x", real=True)
px = lambda stream: stream * s(1, x, x**2, ...)  # powers of x
s1 = px(s(1, 3, 5, ...))  # 1, 3*x, 5*x**2, ...
s2 = px(s(2, 4, 6, ...))  # 2, 4*x, 6*x**2, ...
assert tuple(take(3, cauchyprod(s1, s2))) == (2, 10*x, 28*x**2)
```

**CAUTION**: Symbolic sequence detection is sensitive to the assumptions on the symbols, because very pythonically, ``SymPy`` only simplifies when the result is guaranteed to hold in the most general case under the given assumptions.

Inspired by Haskell.


### ``sym``, ``gensym``, ``Singleton``: symbols and singletons

**Added in v0.14.2**.

We provide **lispy symbols**, an **uninterned symbol generator**, and a **pythonic singleton abstraction**. These are all pickle-aware, and instantiation is thread-safe.

#### Symbol

In plain English, a *symbol* is a **lightweight, human-readable, process-wide unique marker**, that can be quickly compared to another such marker *by comparing object identity*. For example:

```python
from unpythonic import sym

cat = sym("cat")
assert cat is sym("cat")
assert cat is not sym("dog")
```

The constructor `sym` produces an ***interned symbol***. Whenever (in the same process) **the same name** is passed to the `sym` constructor, it gives **the same object instance**. Even unpickling a symbol that has the same name produces the same `sym` object instance as any other `sym` with that name.

Thus a `sym` behaves like a Lisp symbol. Technically speaking, it's like a zen-minimalistic [Scheme/Racket symbol](https://stackoverflow.com/questions/8846628/what-exactly-is-a-symbol-in-lisp-scheme), since Common Lisp [stuffs all sorts of additional cruft in symbols](https://www.cs.cmu.edu/Groups/AI/html/cltl/clm/node27.html). If you insist on emulating that, note a `sym` is just a Python object you could customize in the usual ways, even though its instantiation logic plays by somewhat unusual rules.

#### Gensym

The function `gensym` creates an ***uninterned symbol***, also known as *a gensym*. The label given in the call to `gensym` is a short human-readable description, like the name of a named symbol, but it has no relation to object identity. Object identity is tracked by an [UUID](https://en.wikipedia.org/wiki/Universally_unique_identifier), which is automatically assigned when `gensym` creates the value. Even if `gensym` is called with the same label, the return value is a new unique symbol each time.

A gensym never conflicts with any named symbol; not even if one takes the UUID from a gensym and creates a named symbol using that as the name.

*The return value is the only time you'll see that symbol object; take good care of it!*

For example:

```python
from unpythonic import gensym

tabby = gensym("cat")
scottishfold = gensym("cat")
assert tabby is not scottishfold
print(tabby)         # gensym:cat:81a44c53-fe2d-4e65-b2de-329076cc7755
print(scottishfold)  # gensym:cat:94287f75-02b5-4138-9174-1e422e618d59
```

Uninterned symbols are useful as guaranteed-unique sentinel or [nonce (sense 2, adapted to programming)](https://en.wiktionary.org/wiki/nonce#Noun) values, like the pythonic idiom `nonce = object()`, but they come with a human-readable label.

They also have a superpower: with the help of the UUID automatically assigned by `gensym`, they survive a pickle roundtrip with object identity intact. Unpickling the *same* gensym value multiple times in the same process will produce just one object instance. (If the original return value from gensym is still alive, it is that same object instance.)

The UUID is generated with the pseudo-random algorithm [`uuid.uuid4`](https://docs.python.org/3/library/uuid.html). Due to rollover of the time field, it is possible for collisions with current UUIDs (as of the early 21st century) to occur with those generated after (approximately) the year 3400. See [RFC 4122](https://tools.ietf.org/html/rfc4122).

#### Compared to other languages

Our `sym` is like a Lisp/Scheme/Racket symbol, which is essentially an [interned string](https://en.wikipedia.org/wiki/String_interning), which in the Lisp family is a data type distinct from a regular string. In our implementation, we do **not** use [`sys.intern`](https://docs.python.org/3/library/sys.html#sys.intern); the interning mechanism of our symbol types is completely separate and independent of Python's string interning mechanism.

Our `gensym` is like the [Lisp `gensym`](http://clhs.lisp.se/Body/f_gensym.htm), and the [JavaScript `Symbol`](https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/Symbol).

If you're familiar with `mcpyrate`'s `gensym` or MacroPy's `gen_sym`, those mean something different. Their purpose is to create, in a macro, a lexical identifier that is not already in use in the source code being compiled, whereas our `gensym` creates an uninterned symbol object for run-time use. Lisp macros use symbols to represent identifiers, hence the potential for confusion in Python, where that is not the case. (The symbols of `unpythonic` are a purely run-time abstraction.)

If your background is in C++ or Java, you may notice the symbol abstraction is a kind of a parametric [singleton](https://en.wikipedia.org/wiki/Singleton_pattern); each symbol with the same name is a singleton (as is any gensym with the same UUID).

#### Singleton

A *singleton* is an object of which only one instance can exist at any given time (in the same process). We provide a base class, `Singleton`, which can also be used as a mixin. A basic example:

```python
import pickle
from unpythonic import Singleton

class SingleXHolder(Singleton):
    def __init__(self, x=42):
        self.x = x

h = SingleXHolder(17)
s = pickle.dumps(h)
h2 = pickle.loads(s)
assert h2 is h  # it's the same instance
```

Often the [singleton pattern](https://en.wikipedia.org/wiki/Singleton_pattern) is discussed in the context of classic relatively low-level, static languages such as C++ or Java. [In Python](https://stackoverflow.com/questions/6760685/creating-a-singleton-in-python), some of the classical issues, such as singletons being forced to use a clunky, nonstandard object construction syntax, are moot, because the language itself offers customization hooks that can be used to smooth away such irregularities.

Thus, rather than blindly copying the pattern from C++ or Java, the questions to ask first are, *what is a singleton? What is the service it provides? What responsibilities should it have? Does it even make sense to have a singleton abstraction for Python?*

As the result of answering these questions, `unpythonic`'s idea of a singleton slightly differs from the textbook pattern. In C++ or Java, one uses an instance accessor method (which is a static method) to retrieve the singleton instance, instead of calling a constructor normally - which is actually made private, so nothing except the accessor method can call it. Calling the accessor method either instantiates the singleton (if not created yet), or silently returns the existing instance (if already created).

However, Python can easily retrieve a singleton instance with syntax that looks like regular object construction, by customizing [`__new__`](https://docs.python.org/3/reference/datamodel.html#object.__new__). Hence no static accessor method is needed. This in turn raises the question, what should we do with constructor arguments, as we surely would like to (in general) to allow those, and they can obviously differ between call sites. Since there is only one object instance to load state into, we could either silently update the state, or silently ignore the new proposed arguments. Good luck tracking down bugs either way. But upon closer inspection, that question depends on an unfounded assumption. What we should be asking instead is, *what should happen* if the constructor of a singleton is called again, while an instance already exists?

We believe in the principles of [separation of concerns](https://en.wikipedia.org/wiki/Separation_of_concerns) and [fail-fast](https://en.wikipedia.org/wiki/Fail-fast). The textbook singleton pattern conflates two concerns, possibly due to language limitations: the *management of object instances*, and the *enforcement of the at-most-one-instance-only guarantee*. If we wish to uncouple these responsibilities, then the obvious pythonic answer is that attempting to construct the singleton again while it already exists **should be considered a run-time error**. Since a singleton **type** does not support that operation, this situation should raise a `TypeError`. This makes the error explicit as early as possible, thus adhering to the fail-fast principle, hence making it difficult for bugs to hide (constructor arguments will either take effect, or the constructor call will explicitly fail).

Another question arises due to Python having builtin support for object persistence, namely `pickle`. What *should* happen when a singleton is unpickled, while an instance of that singleton already exists? Arguably, by default, it should load the state from the pickle file into the existing instance, overwriting its current state.

(Scenario: during second and later runs, a program first initializes, which causes the singleton instance to be created, just like during the first run of that program. Then the program loads state from a pickle file, containing (among other data) the state the singleton instance was in when the program previously shut down. In this scenario, considering the singleton, the data in the file is more relevant than the defaults the program initialization feeds in. Hence the default should be to replace the state of the existing singleton instance with the data from the pickle file.)

Our `Singleton` abstraction is the result of these pythonifications applied to the classic pattern. For more documentation and examples, see the unit tests in [`unpythonic/tests/test_singleton.py`](../unpythonic/tests/test_singleton.py).

**NOTE**: A related pattern is the *[Borg](http://code.activestate.com/recipes/66531-singleton-we-dont-need-no-stinkin-singleton-the-bo/)*, a.k.a. *Monostate*. [After considering the matter](https://github.com/Technologicat/unpythonic/issues/22), it was felt that in the context of Python, it offers no advantages over the singleton abstraction, while eliminating a useful feature: the singleton abstraction allows using the object identity check (`is`) to check if a name refers to the singleton instance. For this reason, `unpythonic` provides `Singleton`, but no `Borg`. If you feel this is unjust, please let me know - this decision can be revisited, if a situation in which a `Borg` is more appropriate than a `Singleton` comes up.

**CAUTION**: `Singleton` introduces a custom metaclass to guard constructor calls. Hence it cannot be trivially combined with a class that uses another custom metaclass for some other purpose.

#### When to use a singleton?

Most often, **don't**. ``Singleton`` is provided for the very rare occasion where it's the appropriate abstraction. There exist **at least** three categories of use cases where singleton-like instantiation semantics are desirable:

 1. **A process-wide unique marker value**, which has no functionality other than being quickly and uniquely identifiable as that marker.
    - `sym` and `gensym` are the specific tools that cover this use case, depending on whether the intent is to allow that value to be independently "constructed" in several places yet always obtaining the same instance (`sym`), or if the implementation just happens to internally need a guaranteed-unique value that no value passed in from the outside could possibly clash with (`gensym`). For the latter case, sometimes a simple (and much faster) `nonce = object()` will do just as well, if you don't need the human-readable label and `pickle` support.
    - If you need the singleton object to have extra functionality (e.g. our `nil` supports the iterator protocol), it's possible to subclass `sym` or `gsym`, but subclassing `Singleton` is also a possible solution.
 2. **An empty immutable collection**.
    - It can't have elements added to it after construction, so there's no point in creating more than one instance of an empty *immutable* collection of any particular type.
    - Unfortunately, a class can't easily be partly `Singleton` (i.e., only when the instance is empty). So this use case is better coded manually, like `frozendict` does. Also, for this use case silently returning the existing instance is the right thing to do.
 3. **A service that may have at most one instance** per process.
    - *But only if it is certain* that there can't arise a situation where multiple simultaneous instances of the service are needed.
    - The dynamic assignment controller `dyn` is an example, and it is indeed a `Singleton`.

Cases 1 and 2 have no meaningful instance data. Case 3 may or may not, depending on the specifics. If your object does, and if you want it to support `pickle`, you may want to customize [`__getnewargs__`](https://docs.python.org/3/library/pickle.html#object.__getnewargs__) (called *at pickling time*), [`__setstate__`](https://docs.python.org/3/library/pickle.html#object.__setstate__), and sometimes maybe also [`__getstate__`](https://docs.python.org/3/library/pickle.html#object.__getstate__). Note that unpickling skips `__init__`, and calls just `__new__` (with the "newargs") and then `__setstate__`.

I'm not completely sure if it's meaningful to provide a generic `Singleton` abstraction for Python, except for teaching purposes. Practical use cases may differ so much, and some of the implementation details of the specific singleton object (esp. related to pickling) may depend so closely on the implementation details of the singleton abstraction, that it may be easier to just roll your own singleton code when needed. If you're new to customizing this part of Python, the code we have here should at least demonstrate an approach for how to do this.


## Control flow tools

Tools related to control flow.

### ``trampolined``, ``jump``: tail call optimization (TCO) / explicit continuations

Express algorithms elegantly without blowing the call stack - with explicit, clear syntax.

*Tail recursion*:

```python
from unpythonic import trampolined, jump

@trampolined
def fact(n, acc=1):
    if n == 0:
        return acc
    else:
        return jump(fact, n - 1, n * acc)
print(fact(4))  # 24
```

Functions that use TCO **must** be `@trampolined`. Calling a trampolined function normally starts the trampoline.

Inside a trampolined function, a normal call `f(a, ..., kw=v, ...)` remains a normal call.

A tail call with target `f` is denoted `return jump(f, a, ..., kw=v, ...)`. This explicitly marks that it is indeed a tail call (due to the explicit ``return``). Note that `jump` is **a noun, not a verb**. The `jump(f, ...)` part just evaluates to a `jump` instance, which on its own does nothing. Returning it to the trampoline actually performs the tail call.

If the jump target has a trampoline, don't worry; the trampoline implementation will automatically strip it and jump into the actual entrypoint.

Trying to ``jump(...)`` without the ``return`` does nothing useful, and will **usually** print an *unclaimed jump* warning. It does this by checking a flag in the ``__del__`` method of ``jump``; any correctly used jump instance should have been claimed by a trampoline before it gets garbage-collected.

(Some *unclaimed jump* warnings may appear also if the process is terminated by Ctrl+C (``KeyboardInterrupt``). This is normal; it just means that the termination occurred after a jump object was instantiated but before it was claimed by the trampoline.)

The final result is just returned normally. This shuts down the trampoline, and returns the given value from the initial call (to a ``@trampolined`` function) that originally started that trampoline.


*Tail recursion in a lambda*:

```python
t = trampolined(withself(lambda self, n, acc=1:
                           acc if n == 0 else jump(self, n - 1, n * acc)))
print(t(4))  # 24
```

Here the jump is just `jump` instead of `return jump`, since lambda does not use the `return` syntax.

To denote tail recursion in an anonymous function, use ``unpythonic.fun.withself``. The ``self`` argument is declared explicitly, but passed implicitly, just like the ``self`` argument of a method.


*Mutual recursion with TCO*:

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
assert even(42) is True
assert odd(4) is False
assert even(10000) is True  # no crash
```

*Mutual recursion in `letrec` with TCO*:

```python
letrec(evenp=lambda e:
               trampolined(lambda x:
                             (x == 0) or jump(e.oddp, x - 1)),
       oddp=lambda e:
               trampolined(lambda x:
                             (x != 0) and jump(e.evenp, x - 1)),
       body=lambda e:
               e.evenp(10000))
```


#### Reinterpreting TCO as explicit continuations

TCO from another viewpoint:

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

Each function in the TCO call chain tells the trampoline where to go next (and with what arguments). All hail [lambda, the ultimate GOTO](http://hdl.handle.net/1721.1/5753)!

Each TCO call chain brings its own trampoline, so they nest as expected:

```python
@trampolined
def foo():
    return jump(bar)
@trampolined
def bar():
    t = even(42)  # start another trampoline for even/odd
    return jump(baz, t)
@trampolined
def baz(result):
    print(result)
foo()  # start trampoline
```

#### Similar features in Lisps - `trampoline` in Clojure

Clojure has [`(trampoline ...)`](https://clojuredocs.org/clojure.core/trampoline), which works almost exactly like our `trampolined`.

The `return jump(...)` solution is essentially the same there (the syntax is `#(...)`), but in Clojure, the trampoline must be explicitly enabled at the call site, instead of baking it into the function definition, as our decorator does.

Clojure's trampoline system is thus more explicit and simple than ours (the trampoline doesn't need to detect and strip the tail-call target's trampoline, if it has one - because with Clojure's solution, it never does), at some cost to convenience at each use site. We have chosen to emphasize use-site convenience.


### ``looped``, ``looped_over``: loops in FP style (with TCO)

*Functional loop with automatic tail call optimization* (for calls re-invoking the loop body):

```python
from unpythonic import looped, looped_over

@looped
def s(loop, acc=0, i=0):
    if i == 10:
        return acc
    else:
        return loop(acc + i, i + 1)
print(s)  # 45
```

Compare the sweet-exp Racket:

```racket
define s
  let loop ([acc 0] [i 0])
    cond
      {i = 10}
        acc
      else
        loop {acc + i} {i + 1}
displayln s  ; 45
```

The `@looped` decorator is essentially sugar. Behaviorally equivalent code:

```python
@trampolined
def s(acc=0, i=0):
    if i == 10:
        return acc
    else:
        return jump(s, acc + i, i + 1)
s = s()
print(s)  # 45
```

In `@looped`, the function name of the loop body is the name of the final result, like in `@call`. The final result of the loop is just returned normally.

The first parameter of the loop body is the magic parameter ``loop``. It is *self-ish*, representing a jump back to the loop body itself, starting a new iteration. Just like Python's ``self``, ``loop`` can have any name; it is passed positionally.

Note that ``loop`` is **a noun, not a verb.** This is because the expression ``loop(...)`` is essentially the same as ``jump(...)`` to the loop body itself. However, it also inserts the magic parameter ``loop``, which can only be set up via this mechanism.

Additional arguments can be given to ``loop(...)``. When the loop body is called, any additional positional arguments are appended to the implicit ones, and can be anything. Additional arguments can also be passed by name. The initial values of any additional arguments **must** be declared as defaults in the formal parameter list of the loop body. The loop is automatically started by `@looped`, by calling the body with the magic ``loop`` as the only argument.

Any loop variables such as ``i`` in the above example are **in scope only in the loop body**; there is no ``i`` in the surrounding scope. Moreover, it's a fresh ``i`` at each iteration; nothing is mutated by the looping mechanism. (But be careful if you use a mutable object instance as a loop variable. The loop body is just a function call like any other, so the usual rules apply.)

FP loops don't have to be pure:

```python
out = []
@looped
def _(loop, i=0):
    if i <= 3:
        out.append(i)  # cheeky side effect
        return loop(i + 1)
    # the implicit "return None" terminates the loop.
assert out == [0, 1, 2, 3]
```

Keep in mind, though, that this pure-Python FP looping mechanism is slow, so it may make sense to use it only when "the FP-ness" (no mutation, scoping) is important.

Also be aware that `@looped` is specifically neither a ``for`` loop nor a ``while`` loop; instead, it is a general looping mechanism that can express both kinds of loops.

*Typical `while True` loop in FP style*:

```python
@looped
def _(loop):
    print("Enter your name (or 'q' to quit): ", end='')
    s = input()
    if s.lower() == 'q':
        return  # ...the implicit None. In a "while True:", "break" here.
    else:
        print(f"Hello, {s}!")
        return loop()
```

#### FP loop over an iterable

In Python, loops often run directly over the elements of an iterable, which markedly improves readability compared to dealing with indices. Enter ``@looped_over``:

```python
@looped_over(range(10), acc=0)
def s(loop, x, acc):
    return loop(acc + x)
assert s == 45
```

The ``@looped_over`` decorator is essentially sugar. Behaviorally equivalent code:

```python
@call
def s(iterable=range(10)):
    it = iter(iterable)
    @looped
    def _tmp(loop, acc=0):
        try:
            x = next(it)
            return loop(acc + x)
        except StopIteration:
            return acc
    return _tmp
assert s == 45
```

In ``@looped_over``, the loop body takes three magic positional parameters. The first parameter ``loop`` works like in ``@looped``. The second parameter ``x`` is the current element. The third parameter ``acc`` is initialized to the ``acc`` value given to ``@looped_over``, and then (functionally) updated at each iteration, taking as the new value the first positional argument given to ``loop(...)``, if any positional arguments were given. Otherwise ``acc`` retains its last value.

If ``acc`` is a mutable object, mutating it is allowed. For example, if ``acc`` is a list, it is perfectly fine to ``acc.append(...)`` and then just ``loop()`` with no arguments, allowing ``acc`` to retain its last value. To be exact, keeping the last value means *the binding of the name ``acc`` does not change*, so when the next iteration starts, the name ``acc`` still points to the same object that was mutated. This strategy can be used to pythonically construct a list in an FP loop.

Additional arguments can be given to ``loop(...)``. The same notes as above apply. For example, here we have the additional parameters ``fruit`` and ``number``. The first one is passed positionally, and the second one by name:

```python
@looped_over(range(10), acc=0)
def s(loop, x, acc, fruit="pear", number=23):
    print(fruit, number)
    newfruit = "orange" if fruit == "apple" else "apple"
    newnumber = number + 1
    return loop(acc + x, newfruit, number=newnumber)
assert s == 45
```

The loop body is called once for each element in the iterable. When the iterable runs out of elements, the last ``acc`` value that was given to ``loop(...)`` becomes the return value of the loop. If the iterable is empty, the body never runs; then the return value of the loop is the initial value of ``acc``.

To terminate the loop early, just ``return`` your final result normally, like in ``@looped``. (It can be anything, does not need to be ``acc``.)

Multiple input iterables work somewhat like in Python's ``for``, except any sequence unpacking must be performed inside the body:

```python
@looped_over(zip((1, 2, 3), ('a', 'b', 'c')), acc=())
def p(loop, item, acc):
    numb, lett = item
    return loop(acc + (f"{numb:d}{lett}",))
assert p == ('1a', '2b', '3c')

@looped_over(enumerate(zip((1, 2, 3), ('a', 'b', 'c'))), acc=())
def q(loop, item, acc):
    idx, (numb, lett) = item
    return loop(acc + (f"Item {idx:d}: {numb:d}{lett}",))
assert q == ('Item 0: 1a', 'Item 1: 2b', 'Item 2: 3c')
```

This is because while *tuple parameter unpacking* was supported in Python 2.x, it was removed starting from Python 3.0, in [PEP 3113](https://www.python.org/dev/peps/pep-3113/). The original implementation of the feature caused certain technical issues (detailed in the PEP), and it was not widely used. It is somewhat curious that re-engineering the implementation to overcome those issues was not even suggested in the PEP. For what it's worth, JavaScript (technically, [ECMAScript](https://www.ecma-international.org/ecma-262/)) does support this feature, so the rationale for removal seems specific to the Python community.

FP loops can be nested (also those over iterables):

```python
@looped_over(range(1, 4), acc=())
def outer_result(outer_loop, y, outer_acc):
    @looped_over(range(1, 3), acc=())
    def inner_result(inner_loop, x, inner_acc):
        return inner_loop(inner_acc + (y*x,))
    return outer_loop(outer_acc + (inner_result,))
assert outer_result == ((1, 2), (2, 4), (3, 6))
```

If you feel the trailing commas ruin the aesthetics, see ``unpythonic.misc.pack``.

#### Accumulator type and runtime cost

As [the reference warns (note 6)](https://docs.python.org/3/library/stdtypes.html#common-sequence-operations), repeated concatenation of tuples has an O(n²) runtime cost, because each concatenation creates a new tuple, which needs to copy all of the already existing elements. To keep the runtime O(n), there are two options:

 - *Pythonic solution*: Destructively modify a mutable sequence. Particularly, ``list`` is a dynamic array that has a low amortized cost for concatenation (most often O(1), with the occasional O(n) when the allocated storage grows).
 - *Unpythonic solution*: ``cons`` a linked list, and reverse it at the end. Cons cells are immutable; consing a new element to the front costs O(1). Reversing the list costs O(n).

Mutable sequence (Python ``list``):

```python
@looped_over(zip((1, 2, 3), ('a', 'b', 'c')), acc=[])
def p(loop, item, acc):
    numb, lett = item
    newelt = f"{numb:d}{lett}"
    acc.append(newelt)
    return loop()
assert p == ['1a', '2b', '3c']
```

Linked list:

```python
from unpythonic import cons, nil, ll

@lreverse
@looped_over(zip((1, 2, 3), ('a', 'b', 'c')), acc=nil)
def p(loop, item, acc):
    numb, lett = item
    newelt = f"{numb:d}{lett}"
    return loop(cons(newelt, acc))
assert p == ll('1a', '2b', '3c')
```

Note the unpythonic use of the ``lreverse`` function as a decorator. ``@looped_over`` overwrites the def'd name by the return value of the loop; then ``lreverse`` takes that as input, and overwrites once more. Thus ``p`` becomes the final list.

To get the output as a tuple, we can add ``tuple`` to the decorator chain:

```python
@tuple
@lreverse
@looped_over(zip((1, 2, 3), ('a', 'b', 'c')), acc=nil)
def p(loop, item, acc):
    numb, lett = item
    newelt = f"{numb:d}{lett}"
    return loop(cons(newelt, acc))
assert p == ('1a', '2b', '3c')
```

This works in both solutions. The cost is an additional O(n) step.

#### ``break``

The main way to exit an FP loop (also early) is, at any time, to just ``return`` the final result normally.

If you want to exit the function *containing* the loop from inside the loop, see **escape continuations** below.

#### ``continue``

The main way to *continue* an FP loop is, at any time, to ``loop(...)`` with the appropriate arguments that will make it proceed to the next iteration. Or package the appropriate `loop(...)` expression into your own function ``cont``, and then use ``cont(...)``:

```python
@looped
def s(loop, acc=0, i=0):
    cont = lambda newacc=acc: loop(newacc, i + 1)  # always increase i; by default keep current value of acc
    if i <= 4:
        return cont()  # essentially "continue" for this FP loop
    elif i == 10:
        return acc
    else:
        return cont(acc + i)
print(s)  # 35
```

This approach separates the computations of the new values for the iteration counter and the accumulator.

#### Prepackaged ``break`` and ``continue``

See ``@breakably_looped`` (offering `brk`) and ``@breakably_looped_over`` (offering `brk` and `cnt`).

The point of `brk(value)` over just `return value` is that `brk` is first-class, so it can be passed on to functions called by the loop body (so that those functions then have the power to directly terminate the loop).

In ``@looped``, a library-provided ``cnt`` wouldn't make sense, since all parameters except ``loop`` are user-defined. *The client code itself defines what it means to proceed to the "next" iteration*. Really the only way in a construct with this degree of flexibility is for the client code to fill in all the arguments itself.

Because ``@looped_over`` is a more specific abstraction, there the concept of *continue* is much more clear-cut. We define `cnt` to mean *proceed to take the next element from the iterable, keeping the current value of `acc`*. Essentially `cnt` is a partially applied `loop(...)` with the first positional argument set to the current value of `acc`.

#### FP loops using a lambda as body

Just call the `looped()` decorator manually:

```python
s = looped(lambda loop, acc=0, i=0:
             loop(acc + i, i + 1) if i < 10 else acc)
print(s)
```

It's not just a decorator; in Lisps, a construct like this would likely be named ``call/looped``.

We can also use ``let`` to make local definitions:

```python
s = looped(lambda loop, acc=0, i=0:
             let(cont=lambda newacc=acc:
                        loop(newacc, i + 1),
                 body=lambda e:
                        e.cont(acc + i) if i < 10 else acc)
print(s)
```

The `looped_over()` decorator also works, if we just keep in mind that parameterized decorators in Python are actually decorator factories:

```python
r10 = looped_over(range(10), acc=0)
s = r10(lambda loop, x, acc:
          loop(acc + x))
assert s == 45
```

If you **really** need to make that into an expression, bind ``r10`` using ``let`` (if you use ``letrec``, keeping in mind it is a callable), or to make your code unreadable, just inline it.

With ``curry``, this is also a possible solution:

```python
s = curry(looped_over, range(10), 0,
            lambda loop, x, acc:
              loop(acc + x))
assert s == 45
```

### ``gtrampolined``: generators with TCO

In ``unpythonic``, a generator can tail-chain into another generator. This is like invoking ``itertools.chain``, but as a tail call from inside the generator - so the generator itself can choose the next iterable in the chain. If the next iterable is a generator, it can again tail-chain into something else. If it is not a generator, it becomes the last iterable in the TCO chain.

Python provides a convenient hook to build things like this, in the guise of ``return``:

```python
from unpythonic import gtco, take, last

def march():
    yield 1
    yield 2
    return march()  # tail-chain to a new instance of itself
assert tuple(take(6, gtco(march()))) == (1, 2, 1, 2, 1, 2)
last(take(10000, gtco(march())))  # no crash
```

Note the calls to ``gtco`` at the use sites. For convenience, we provide ``@gtrampolined``, which automates that:

```python
from unpythonic import gtrampolined, take, last

@gtrampolined
def ones():
    yield 1
    return ones()
assert tuple(take(10, ones())) == (1,) * 10
last(take(10000, ones()))  # no crash
```

It is safe to tail-chain into a ``@gtrampolined`` generator; the system strips the TCO target's trampoline if it has one.

Like all tail calls, this works for any *iterative* process. In contrast, this **does not work**:

```python
from operator import add
from unpythonic import gtrampolined, scanl, take

@gtrampolined
def fibos():  # see numerics.py
    yield 1
    return scanl(add, 1, fibos())
print(tuple(take(10, fibos())))  # --> (1, 1, 2), only 3 terms?!
```

This sequence (technically iterable, but in the mathematical sense) is recursively defined, and the ``return`` shuts down the generator before it can yield more terms into ``scanl``. With ``yield from`` instead of ``return`` the second example works (but since it is recursive, it eventually blows the call stack).

This particular example can be converted into a linear process with a different higher-order function, no TCO needed:

```python
from unpythonic import unfold, take, last
def fibos():
    def nextfibo(a, b):
        return a, b, a + b  # value, *newstates
    return unfold(nextfibo, 1, 1)
assert tuple(take(10, fibos())) == (1, 1, 2, 3, 5, 8, 13, 21, 34, 55)
last(take(10000, fibos()))  # no crash
```


### ``catch``, ``throw``: escape continuations (ec)

**Changed in v0.14.2.** *These constructs were previously named `setescape`, `escape`. The names have been changed to match the standard naming for this feature in several Lisps. Starting in 0.14.2, using the old names emits a `FutureWarning`, and the old names will be removed in 0.15.0.*

Escape continuations can be used as a *multi-return*:

```python
from unpythonic import catch, throw

@catch()  # note the parentheses
def f():
    def g():
        throw("hello from g")  # the argument becomes the return value of f()
        print("not reached")
    g()
    print("not reached either")
assert f() == "hello from g"
```

**CAUTION**: The implementation is based on exceptions, so catch-all ``except:`` statements will intercept also throws, breaking the escape mechanism. As you already know, be specific in which exception types you catch in an `except` clause!

In Lisp terms, `@catch` essentially captures the escape continuation (ec) of the function decorated with it. The nearest (dynamically) surrounding ec can then be invoked by `throw(value)`. When the `throw` is performed, the function decorated with `@catch` immediately terminates, returning ``value``.

In Python terms, a throw means just raising a specific type of exception; the usual rules concerning ``try/except/else/finally`` and ``with`` blocks apply. It is a function call, so it works also in lambdas.

Escaping the function surrounding an FP loop, from inside the loop:

```python
@catch()
def f():
    @looped
    def s(loop, acc=0, i=0):
        if i > 5:
            throw(acc)
        return loop(acc + i, i + 1)
    print("never reached")
f()  # --> 15
```

For more control, both ``@catch`` points and ``throw`` instances can be tagged:

```python
@catch(tags="foo")  # catch point tags can be single value or tuple (tuples OR'd, like isinstance())
def foo():
    @call
    @catch(tags="bar")
    def bar():
        @looped
        def s(loop, acc=0, i=0):
            if i > 5:
                throw(acc, tag="foo")  # throw instance tag must be a single value
            return loop(acc + i, i + 1)
        print("never reached")
        return False
    print("never reached either")
    return False
assert foo() == 15
```

For details on tagging, especially how untagged and tagged throw and catch points interact, and how to make one-to-one connections, see the docstring for ``@catch``.

**Etymology**

This feature is known as `catch`/`throw` in several Lisps, e.g. in Emacs Lisp and in Common Lisp (as well as some of its ancestors). This terminology is independent of the use of `throw`/`catch` in C++/Java for the exception handling mechanism. Common Lisp also provides a lexically scoped variant (`BLOCK`/`RETURN-FROM`) that is more idiomatic [according to Seibel](http://www.gigamonkeys.com/book/the-special-operators.html).


#### ``call_ec``: first-class escape continuations

We provide ``call/ec`` (a.k.a. ``call-with-escape-continuation``), in Python spelled as ``call_ec``. It's a decorator that, like ``@call``, immediately runs the function and replaces the def'd name with the return value. The twist is that it internally sets up a catch point, and hands a **first-class escape continuation** to the callee.

The function to be decorated **must** take one positional argument, the ec instance.

The ec instance itself is another function, which takes one positional argument: the value to send to the catch point. The ec instance and the catch point are connected one-to-one. No other ``@catch`` point will catch the ec instance, and the catch point catches only this particular ec instance and nothing else.

Any particular ec instance is only valid inside the dynamic extent of the ``call_ec`` invocation that created it. Attempting to call the ec later raises ``RuntimeError``.

This builds on ``@catch`` and ``throw``, so the caution about catch-all ``except:`` statements applies here, too.

```python
from unpythonic import call_ec

@call_ec
def result(ec):  # effectively, just a code block, capturing the ec as an argument
    answer = 42
    ec(answer)  # here this has the same effect as "return answer"...
    print("never reached")
    answer = 23
    return answer
assert result == 42

@call_ec
def result(ec):
    answer = 42
    def inner():
        ec(answer)  # ...but here this directly escapes from the outer def
        print("never reached")
        return 23
    answer = inner()
    print("never reached either")
    return answer
assert result == 42
```

The ec doesn't have to be called from the lexical scope of the call_ec'd function, as long as the call occurs within the dynamic extent of the ``call_ec``. It's essentially a *return from me* for the original function:

```python
def f(ec):
    print("hi from f")
    ec(42)

@call_ec
def result(ec):
    f(ec)  # pass on the ec - it's a first-class value
    print("never reached")
assert result == 42
```

This also works with lambdas, by using ``call_ec()`` directly. No need for a trampoline:

```python
result = call_ec(lambda ec:
                   begin(print("hi from lambda"),
                         ec(42),
                         print("never reached")))
assert result == 42
```

Normally ``begin()`` would return the last value, but the ec overrides that; it is effectively a ``return`` for multi-expression lambdas!

But wait, doesn't Python evaluate all the arguments of `begin(...)` before the `begin` itself has a chance to run? Why doesn't the example print also *never reached*? This is because escapes are implemented using exceptions. Evaluating the ec call raises an exception, preventing any further elements from being evaluated.

This usage is valid with named functions, too - ``call_ec`` is not only a decorator:

```python
def f(ec):
    print("hi from f")
    ec(42)
    print("never reached")

# ...possibly somewhere else, possibly much later...

result = call_ec(f)
assert result == 42
```


### ``forall``: nondeterministic evaluation

We provide a simple variant of nondeterministic evaluation. This is essentially a toy that has no more power than list comprehensions or nested for loops. See also the easy-to-use [macro](macros.md) version with natural syntax and a clean implementation.

An important feature of McCarthy's [`amb` operator](https://rosettacode.org/wiki/Amb) is its nonlocality - being able to jump back to a choice point, even after the dynamic extent of the function where that choice point resides. If that sounds a lot like ``call/cc``, that's because that's how ``amb`` is usually implemented. See examples [in Ruby](http://www.randomhacks.net/2005/10/11/amb-operator/) and [in Racket](http://www.cs.toronto.edu/~david/courses/csc324_w15/extra/choice.html).

Python can't do that, short of transforming the whole program into [CPS](https://en.wikipedia.org/wiki/Continuation-passing_style), while applying TCO everywhere to prevent stack overflow. **If that's what you want**, see ``continuations`` in [the macros](macros.md).

This ``forall`` is essentially a tuple comprehension that:

 - Can have multiple body expressions (side effects also welcome!), by simply listing them in sequence.
 - Allows filters to be placed at any level of the nested looping.
 - Presents the source code in the same order as it actually runs.

The ``unpythonic.amb`` module defines four operators:

 - ``forall`` is the control structure, which marks a section with nondeterministic evaluation.
 - ``choice`` binds a name: ``choice(x=range(3))`` essentially means ``for e.x in range(3):``.
 - ``insist`` is a filter, which allows the remaining lines to run if the condition evaluates to truthy.
 - ``deny`` is ``insist not``; it allows the remaining lines to run if the condition evaluates to falsey.

Choice variables live in the environment, which is accessed via a ``lambda e: ...``, just like in ``letrec``. Lexical scoping is emulated. In the environment, each line only sees variables defined above it; trying to access a variable defined later raises ``AttributeError``.

The last line in a ``forall`` describes one item of the output. The output items are collected into a tuple, which becomes the return value of the ``forall`` expression.

```python
out = forall(choice(y=range(3)),
             choice(x=range(3)),
             lambda e: insist(e.x % 2 == 0),
             lambda e: (e.x, e.y))
assert out == ((0, 0), (2, 0), (0, 1), (2, 1), (0, 2), (2, 2))

out = forall(choice(y=range(3)),
             choice(x=range(3)),
             lambda e: deny(e.x % 2 == 0),
             lambda e: (e.x, e.y))
assert out == ((1, 0), (1, 1), (1, 2))
```

Pythagorean triples:

```python
pt = forall(choice(z=range(1, 21)),                 # hypotenuse
            choice(x=lambda e: range(1, e.z+1)),    # shorter leg
            choice(y=lambda e: range(e.x, e.z+1)),  # longer leg
            lambda e: insist(e.x*e.x + e.y*e.y == e.z*e.z),
            lambda e: (e.x, e.y, e.z))
assert tuple(sorted(pt)) == ((3, 4, 5), (5, 12, 13), (6, 8, 10),
                             (8, 15, 17), (9, 12, 15), (12, 16, 20))

```

Beware:

```python
out = forall(range(2),  # do the rest twice!
             choice(x=range(1, 4)),
             lambda e: e.x)
assert out == (1, 2, 3, 1, 2, 3)
```

The initial ``range(2)`` causes the remaining lines to run twice - because it yields two output values - regardless of whether we bind the result to a variable or not. In effect, each line, if it returns more than one output, introduces a new nested loop at that point.

For more, see the docstring of ``forall``.

#### For haskellers

The implementation is based on the List monad, and a bastardized variant of do-notation. Quick vocabulary:

 - ``forall(...)`` = ``do ...`` (for a List monad)
 - ``choice(x=foo)`` = ``x <- foo``, where ``foo`` is an iterable
 - ``insist x`` = ``guard x``
 - ``deny x`` = ``guard (not x)``
 - Last line = implicit ``return ...``


### ``handlers``, ``restarts``: conditions and restarts

**Added in v0.14.2**.

**Changed in v0.14.3**. *Conditions can now inherit from `BaseException`, not only from `Exception.` `with handlers` catches also derived types, e.g. a handler for `Exception` now catches a signaled `ValueError`.* 

*When an unhandled `error` or `cerror` occurs, the original unhandled error is now available in the `__cause__` attribute of the `ControlError` exception that is raised in this situation.*

*Signaling a class, as in `signal(SomeExceptionClass)`, now implicitly creates an instance with no arguments, just like the `raise` statement does. On Python 3.7+, `signal` now automatically equips the condition instance with a traceback, just like the `raise` statement does for an exception.*

**Changed in v0.15.0.** *Functions `resignal_in` and `resignal` added; these perform the same job for conditions as `reraise_in` and `reraise` do for exceptions, that is, they allow you to map library exception types to semantically appropriate application exception types, with minimum boilerplate.*

*Upon an unhandled signal, `signal` now returns the canonized input `condition`, with a nice traceback attached. This feature is intended for implementing custom error protocols on top of `signal`; `error` already uses it to produce a nice-looking error report.*

*The error-handling protocol that was used to send a signal is now available for inspection in the `__protocol__` attribute of the condition instance. It is the callable that sent the signal, such as `signal`, `error`, `cerror` or `warn`. It is the responsibility of each error-handling protocol (except the fundamental `signal` itself) to pass its own function to `signal` as the `protocol` argument; if not given, `protocol` defaults to `signal`. The protocol information is used by the `resignal` mechanism.*

One of the killer features of Common Lisp are *conditions*, which are essentially **resumable exceptions**.

Following Peter Seibel ([Practical Common Lisp, chapter 19](http://www.gigamonkeys.com/book/beyond-exception-handling-conditions-and-restarts.html)), we define *errors* as the consequences of [Murphy's Law](https://en.wikipedia.org/wiki/Murphy%27s_law), i.e. situations where circumstances cause interaction between the program and the outside world to fail. An error is no bug, but failing to handle an error certainly is.

An exception system splits error-recovery responsibilities into two parts. In Python terms, we speak of *raising* and then *handling* an exception. In comparison, a condition system splits error-recovery responsibilities into **three parts**: *signaling*, *handling* and *restarting*.

The result is improved modularity. Consider [separation of mechanism and policy](https://en.wikipedia.org/wiki/Separation_of_mechanism_and_policy). We place the actual error-recovery code (the mechanism) in *restarts*, at the inner level (of the call stack) - which has access to all the low-level technical details that are needed to actually perform the recovery. We can provide *several different* canned recovery strategies, which implement any appropriate ways to recover, in the context of each low- or middle-level function. We defer the decision of which one to use (the policy), *to an outer level*. The outer level knows about the big picture - *why* the inner levels are running in this particular case, i.e. what we are trying to accomplish and how. Hence, it is in the ideal position to choose which error-recovery strategy should be used *in its high-level context*.

Practical Common Lisp explains conditions in the context of a log file parser. In contrast, let us explain them with some Theoretical Python:

```python
from unpythonic import restarts, handlers, signal, invoke, unbox

class TellMeHowToRecover(Exception):
    pass

def low():
    with restarts(resume_low=(lambda x: x)) as result:  # result is a box
        signal(TellMeHowToRecover())
        result << "low level completed"  # value for normal exit from the `with restarts` block
    return unbox(result) + " > normal exit from low level"

def mid():
    with restarts(resume_mid=(lambda x: x)) as result:
        result << low()
    return unbox(result) + " > normal exit from mid level"

# Trivial use case where we want to just ignore the condition.
# An uncaught signal() is just a no-op; see warn(), error(), cerror() for other standard options.
def high1():
    assert mid() == "low level completed > normal exit from low level > normal exit from mid level"
high1()

# Use case where we want to resume at the low level. In a real-world application, repairing the error,
# and letting the rest of the low-level code (after the `with restarts` block) continue processing
# with the repaired data.
# Note we need new code only at the high level; the mid and low levels remain as-is.
def high2():
    with handlers((TellMeHowToRecover, lambda c: invoke("resume_low", "resumed at low level"))):
        assert mid() == "resumed at low level > normal exit from low level > normal exit from mid level"
high2()

# Use case where we want to resume at the mid level. In a real-world application, skipping a failed part.
def high3():
    with handlers((TellMeHowToRecover, lambda c: invoke("resume_mid", "resumed at mid level"))):
        assert mid() == "resumed at mid level > normal exit from mid level"
high3()
```

#### Fundamental signaling protocol

Generally a condition system operates as follows. A *signal* is sent (outward on the call stack) from the actual location where the error was detected. A *handler* at any outer level may then respond to it, and execution resumes from the *restart* that is *invoked* by the handler.

The sequence of catching a signal and invoking a restart is termed *handling* the signal. Handlers are searched in order from innermost to outermost on the call stack. (Strictly speaking, the handlers live on a separate stack; we consider those handlers whose dynamic extent the point of execution is in, at the point of time when the signal is sent.)

In general, it is allowed for a handler to fall through (return normally); then the next outer handler for the same signal type gets control. This allows the programmer to chain handlers to obtain their side effects, such as logging. This is referred to as *canceling*, since as a result, the signal remains unhandled.

Viewed with respect to the call stack, the restarts live between the (outer) level of the handler, and the (inner) level where the signal was sent from. The main difference to the exception model is that unlike raising an exception, **sending a signal does not unwind the call stack**. Although the handlers live further out on the call stack, the stack does not unwind that far. The handlers are just consulted for what to do. The call stack unwinds only when a restart is being invoked. Then, only the part of the call stack between the location that sent the signal, and the invoked restart, is unwound.

Restarts, despite the name, are a mildly behaved, structured control construct. The block of code that encountered the error is actually not arbitrarily resumed; instead, the restart code runs instead of the rest of the block, and the return value of the restart replaces the normal return value. (But see `cerror`.)

#### API summary

Restarts are set up using the `with restarts` context manager (Common Lisp: `RESTART-CASE`). Restarts are defined by giving named arguments to the `restarts` form; the argument name sets the restart name. The restart name is distinct from the name (if any) of the function that is used as the restart. A restart can only be invoked from within the dynamic extent of its `with restarts` (the same rule is effect also in Common Lisp). A restart may take any args and kwargs; any that it expects must be provided when it is invoked.

*Note difference to the API of [python-cl-conditions](https://github.com/svetlyak40wt/python-cl-conditions/), which requires functions used as restarts to be named, and uses the function name as the restart name.*

A common use case is a `use_value=(lambda x: x)` restart, which is just passed the value that should be returned when the restart is invoked. There is a predefined function of the same name, `use_value` (Common Lisp: `USE-VALUE`), which expects one argument, and immediately invokes the `use_value` restart currently in scope, sending it that argument. This allows using the shorthand `lambda c: use_value(...)` as a handler instead of the spelled-out `lambda c: invoke("use_value", ...)`.

Signals are sent using `signal` (Common Lisp: `SIGNAL`). Any exception or warning instance (both builtin or custom) can be signaled. If you need to send data to your handler, place it in attributes of the exception object (just like you would do when programming with the exception model).

Handlers are established using the `with handlers` context manager (Common Lisp: `HANDLER-BIND`). Handlers are bound to exception types, or tuples of types, just like regular exception handlers in Python. The `handlers` form takes as its arguments any number of `(exc_spec, handler)` pairs. Here `exc_spec` specifies the exception types to catch (when sent via `signal`), and `handler` is a callable. When catching a signal, in case of multiple matches in the same `with handlers` form, the handler that appears earlier in the argument list wins.

A handler catches signals of the types it is bound to. The code in the handler may invoke a restart by calling `invoke` (Common Lisp: `INVOKE-RESTART`), with the desired restart name as a string. In case of duplicate names, the most recently established restart (that is still in scope) with the given name wins. Any extra args and kwargs are passed through to the restart. The `invoke` function always transfers control, never returns normally.

A handler **may** take one optional positional argument, the exception instance being signaled. Roughly, API-wise signal handlers are similar to exception handlers (`except` clauses). A handler that accepts an argument is like an `except ... as ...`, whereas one that does not is like `except ...`. **The main difference** to an exception handler is that a **signal handler should not try to recover from the error itself**; instead, **it should just choose** which strategy the lower-level code should use to recover from the error. Usually, the only thing a signal handler needs to do, is to invoke a particular restart.

To create a simple handler that does not take an argument, and just invokes a pre-specified restart, see `invoker`. If you instead want to create a function that you can call from a handler, in order to invoke a particular restart immediately (so to define a shorthand notation similar to `use_value`), use `functools.partial(invoke, "my_restart_name")`.

Following Common Lisp terminology, *a named function that invokes a specific restart* - whether it is intended to act as a handler or to be called from one - is termed a *restart function*. (This is somewhat confusing, as a *restart function* is not a function that implements a restart, but a function that *invokes* a specific one.) The `use_value` function mentioned above is an example.

For a detailed API reference, see the module ``unpythonic.conditions``.

#### High-level signaling protocols

We actually provide four signaling protocols: `signal` (i.e. the fundamental protocol), and three that build additional behavior on top of it: `error`, `cerror` and `warn`. Each of the three is modeled after its Common Lisp equivalent.

If no handler *handles* the signal, the `signal(...)` protocol just returns normally. In effect, with respect to control flow, unhandled signals are ignored by this protocol. (But any side effects of handlers that caught the signal but did not invoke a restart, still take place.)

The `error(...)` protocol first delegates to `signal`, and if the signal was not handled by any handler, then **raises** `ControlError` as a regular exception. (Note the Common Lisp `ERROR` function would at this point drop you into the debugger.) The implementation of `error` itself is the only place in the condition system that *raises* an exception for the end user; everything else (including any error situations) uses the signaling mechanism.

The `cerror(...)` protocol likewise makes handling the signal mandatory, but allows the handler to optionally ignore the error (sort of like `ON ERROR RESUME NEXT` in some 1980s BASIC variants). To do this, invoke the `proceed` restart in your handler (or use the pre-defined `proceed` function *as* the handler); this makes the `cerror(...)` call return normally. If no handler handles the `cerror`, it then behaves like `error`.

Finally, there is the `warn(...)` protocol, which is just a lispy interface to Python's `warnings.warn`. It comes with a `muffle` restart that can be invoked by a handler to skip emitting a particular warning. Muffling a warning prevents its emission altogether, before it even hits Python's warnings filter.

The combination of `warn` and `muffle` (as well as `cerror` when a handler invokes its `proceed` restart) behaves somewhat like [`contextlib.suppress`](https://docs.python.org/3/library/contextlib.html#contextlib.suppress), except that execution continues normally from the next statement in the caller of `warn` (respectively `cerror`) instead of unwinding to the handler.

If the standard protocols don't cover what you need, you can also build your own high-level protocols on top of `signal`. See the source code of `error`, `cerror` and `warn` for examples (it's just a few lines in each case).

##### Notes

The name `cerror` stands for *correctable error*, see e.g. [CERROR in the CL HyperSpec](http://clhs.lisp.se/Body/f_cerror.htm). What we call `proceed`, Common Lisp calls `CONTINUE`; the name is different because in Python the function naming convention is lowercase, and `continue` is a reserved word.

If you really want to emulate `ON ERROR RESUME NEXT`, just use `Exception` as the condition type for your handler, and all `cerror` calls within the block will return normally, provided that no other handler handles those conditions first.

#### Conditions vs. exceptions

Using the condition system essentially requires eschewing exceptions, using only restarts and handlers instead. A regular `raise` will fly past a `with handlers` form uncaught. The form just maintains a stack of functions; it does not establish an *exception* handler. Similarly, a `try`/`except` cannot catch a signal, because no exception is raised yet at handler lookup time. Delaying the stack unwind, to achieve the three-way split of responsibilities, is the whole point of the condition system. Which of the two systems to use is a design decision that must be made consistently on a per-project basis.

Be aware that error-recovery code in a Lisp-style signal handler is of a very different nature compared to error-recovery code in an exception handler. A signal handler usually only chooses a restart and invokes it; as was explained above, the code that actually performs the error recovery (i.e. the *restart*) lives further in on the call stack, and still has available (in its local variables) the state that is needed to perform the recovery. An exception handler, on the other hand, must respond by directly performing error recovery right where it is, without any help from inner levels - because the stack has already unwound when the exception handler gets control.

Hence, the two systems are intentionally kept separate. The language discontinuity is unfortunate, but inevitable when conditions are added to a language where an error recovery culture based on the exception model (of the regular non-resumable kind) already exists.

**CAUTION**: Make sure to never catch the internal `InvokeRestart` exception (with an exception handler), as the condition system uses it to perform restarts. Again, do not use catch-all `except` clauses!

If a handler attempts to invoke a nonexistent restart (or one that is not in the current dynamic extent), `ControlError` is *signaled* using `error(...)`. The error message in the exception instance will have the details.

If this `ControlError` signal is not handled, a `ControlError` will then be **raised** (as a last-resort measure) as a regular exception, as per the `error` protocol. It **is** allowed to catch `ControlError` with an exception handler.

#### Historical note

Conditions are one of the killer features of Common Lisp, so if you're new to conditions, [Peter Seibel: Practical Common Lisp, chapter 19](http://www.gigamonkeys.com/book/beyond-exception-handling-conditions-and-restarts.html) is a good place to learn about them. There's also a relevant [discussion on Lambda the Ultimate](http://lambda-the-ultimate.org/node/1544).

For Python, conditions were first implemented in [python-cl-conditions](https://github.com/svetlyak40wt/python-cl-conditions/) by Alexander Artemenko (2016).

What we provide here is essentially a rewrite, based on studying that implementation. The main reasons for the rewrite are to give the condition system an API consistent with the style of `unpythonic`, to drop any and all historical baggage without needing to consider backward compatibility, and to allow interaction with (and customization taking into account) the other parts of `unpythonic`.

The core idea can be expressed in fewer than 100 lines of Python; ours is (as of v0.14.2) 151 lines, not counting docstrings, comments, or blank lines. The main reason our module is over 700 lines are the docstrings.


### ``generic``, ``typed``, ``isoftype``: multiple dispatch

**Added in v0.14.2**.

**Changed in v0.14.3**. *The multiple-dispatch decorator `@generic` no longer takes a master definition. Multimethods are registered directly with `@generic`; the first method definition implicitly creates the generic function.*

**Changed in v0.14.3**. *The `@generic` and `@typed` decorators can now decorate also instance methods, class methods and static methods (beside regular functions, as previously in 0.14.2).*

**Changed in v0.15.0**. *The `dispatch` and `typecheck` modules providing this functionality are now considered stable (no longer experimental). Starting with this release, they receive the same semantic-versioning guarantees as the rest of `unpythonic`.*

*Added the `@augment` parametric decorator that can register a new multimethod on an existing generic function originally defined in another lexical scope. Be careful of [type piracy](https://docs.julialang.org/en/v1/manual/style-guide/#Avoid-type-piracy) when you use it.* 

*Added the function `methods`, which displays a list of multimethods of a generic function.*

*Docstrings of the multimethods are now automatically concatenated to make up the docstring of the generic function, so you can document each multimethod separately.*

*`curry` now supports `@generic`. In the case where the **number** of positional arguments supplied so far matches at least one multimethod, but there is no match for the given combination of argument **types**, `curry` waits for more arguments (returning the curried function).*

*It is now possible to dispatch also on a homogeneous type of contents collected by a `**kwargs` parameter. In the type signature, use `typing.Dict[str, mytype]`. Note that in this use, the key type is always `str`.*

The ``generic`` decorator allows creating multiple-dispatch generic functions with type annotation syntax. We also provide some friendly utilities: ``augment`` adds a new multimethod to an existing generic function, ``typed`` creates a single-method generic with the same syntax (i.e. provides a compact notation for writing dynamic type checking code), and ``isoftype`` (which powers the first three) is the big sister of ``isinstance``, with support for many (but unfortunately not all) features of the ``typing`` standard library module.

For what kind of things can be done with this, see particularly the [*holy traits*](https://ahsmart.com/pub/holy-traits-design-patterns-and-best-practice-book/) example in [`unpythonic.tests.test_dispatch`](../unpythonic/tests/test_dispatch.py).

**NOTE**: This was inspired by the [multi-methods of CLOS](http://www.gigamonkeys.com/book/object-reorientation-generic-functions.html) (the Common Lisp Object System), and the [generic functions of Julia](https://docs.julialang.org/en/v1/manual/methods/).

In `unpythonic`, the terminology is as follows:

 - The function that supports multiple call signatures is a *generic function*.
 - Each of its individual implementations is a *multimethod*.

The term *multimethod* distinguishes them from the OOP sense of *method*, already established in Python, as well as reminds that multiple arguments participate in dispatching.

**CAUTION**: Code using the `with lazify` macro cannot usefully use `@generic` or `@typed`, because all arguments of each function call will be wrapped in a promise (`unpythonic.lazyutil.Lazy`) that carries no type information on its contents.


#### ``generic``: multiple dispatch with type annotation syntax

The ``generic`` decorator essentially allows replacing the `if`/`elif` dynamic type checking boilerplate of polymorphic functions with type annotations on the function parameters, with support for features from the `typing` stdlib module. This not only kills boilerplate, but makes the dispatch extensible, since the dispatcher lives outside the original function definition. There is no need to monkey-patch the original to add a new case.

If several multimethods of the same generic function match the arguments given, the most recently registered multimethod wins.

**CAUTION**: The winning multimethod is chosen differently from Julia, where the most specific multimethod wins. Doing that requires a more careful type analysis than what we have here.

The details are best explained by example:

```python
import typing
from unpythonic import generic

@generic  # The first definition creates the generic function, and registers the first multimethod.
def zorblify(x: int, y: int):
    return "int, int"
@generic  # noqa: F811, registered as a multimethod of the same generic function.
def zorblify(x: str, y: int):
    return "str, int"
@generic  # noqa: F811
def zorblify(x: str, y: float):
    return "str, float"

# Then we just call our function as usual.
# Note all arguments participate in dispatching (i.e. in choosing which multimethod gets called).
assert zorblify(2, 3) == "int, int"
assert zorblify("cat", 3) == "str, int"
assert zorblify("cat", 3.14) == "str, float"

# Let's emulate the argument handling of Python's `range` builtin, just for fun.
# Note the meaning of the argument in each position depends on the number of arguments.
@generic
def r(stop: int):
    return _r_impl(0, 1, stop)
@generic  # noqa: F811
def r(start: int, stop: int):
    return _r_impl(start, 1, stop)
@generic  # noqa: F811
def r(start: int, step: int, stop: int):
    return _r_impl(start, step, stop)
# With this arrangement, the actual implementation always gets the args in the same format,
# so we can use meaningful names for its parameters.
def _r_impl(start, step, stop):
    return start, step, stop

# Arity participates in dispatching, too.
assert r(10) == (0, 1, 10)
assert r(2, 10) == (2, 1, 10)
assert r(2, 3, 10) == (2, 3, 10)

# varargs are supported via `typing.Tuple`
@generic
def gargle(*args: typing.Tuple[int, ...]):  # any number of ints
    return "int"
@generic  # noqa: F811
def gargle(*args: typing.Tuple[float, ...]):  # any number of floats
    return "float"
@generic  # noqa: F811
def gargle(*args: typing.Tuple[int, float, str]):  # exactly three args, matching the specified types
    return "int, float, str"

assert gargle(1, 2, 3, 4, 5) == "int"
assert gargle(2.71828, 3.14159) == "float"
assert gargle(42, 6.022e23, "hello") == "int, float, str"
assert gargle(1, 2, 3) == "int"  # as many as in the [int, float, str] case. Still resolves correctly.

# v0.15.0: dispatching on a homogeneous type inside **kwargs is also supported, via `typing.Dict`
@generic
def kittify(**kwargs: typing.Dict[str, int]):  # all kwargs are ints
    return "int"
@generic
def kittify(**kwargs: typing.Dict[str, float]):  # all kwargs are floats  # noqa: F811
    return "float"

assert kittify(x=1, y=2) == "int"
assert kittify(x=1.0, y=2.0) == "float"
```

See [the unit tests](../unpythonic/tests/test_dispatch.py) for more. For which features of the ``typing`` stdlib module are supported, see ``isoftype`` below.

##### ``@generic`` and OOP

As of version 0.14.3, `@generic` and `@typed` can decorate instance methods, class methods and static methods (beside regular functions as in 0.14.2). 

When using both `@generic` or `@typed` and OOP:

 - **`self` and `cls` parameters**.
   - The `self` and `cls` parameters do not participate in dispatching, and need no type annotation.
   - Beside appearing as the first positional-or-keyword parameter, the self-like parameter **must be named** one of `self`, `this`, `cls`, or `klass` to be detected by the ignore mechanism. This limitation is due to implementation reasons; while a class body is being evaluated, the context needed to distinguish a method (OOP sense) from a regular function is not yet present.

 - **OOP inheritance**.
   - When `@generic` is installed on a method (instance method, or `@classmethod`), then at call time, classes are tried in [MRO](https://en.wikipedia.org/wiki/C3_linearization) order. All multimethods of the method defined in the class currently being looked up are tested for matches first, before moving on to the next class in the MRO. This has subtle consequences, related to in which class in the hierarchy the various multimethods for a particular method are defined.
   - To work with OOP inheritance, `@generic` must be the outermost decorator (except `@classmethod` or `@staticmethod`, which are essentially compiler annotations).
   - However, when installed on a `@staticmethod`, the `@generic` decorator does not support MRO lookup, because that would make no sense. See discussions on interaction between `@staticmethod` and `super` in Python: [[1]](https://bugs.python.org/issue31118) [[2]](https://stackoverflow.com/questions/26788214/super-and-staticmethod-interaction/26807879).


##### Notes

In both CLOS and in Julia, *function* is the generic entity, while *method* refers to its specialization to a particular combination of argument types. Note that *no object instance or class is needed*. Contrast with the classical OOP sense of *method*, i.e. a function that is associated with an object instance or class, with single dispatch based on the class (or in exotic cases, such as monkey-patched instances, on the instance).

Based on my own initial experiments with this feature, the machinery itself works well enough, but to really shine - just like resumable exceptions - multiple dispatch needs to be used everywhere, throughout the language's ecosystem. Python obviously doesn't do that.

The machinery itself is also missing some advanced features, such as matching the most specific multimethod candidate instead of the most recently defined one; an `issubclass` equivalent that understands `typing` type specifications; and a mechanism to remove previously declared multimethods.

**CAUTION**: Multiple dispatch can be dangerous. Particularly, `@augment` can be dangerous to the readability of your codebase. If a new multimethod is added for a generic function defined elsewhere, for types defined elsewhere, this may lead to [*spooky action at a distance*](https://lexi-lambda.github.io/blog/2016/02/18/simple-safe-multimethods-in-racket/) (as in [action at a distance](https://en.wikipedia.org/wiki/Action_at_a_distance_(computer_programming))). In the Julia community, this is known as [*type piracy*](https://docs.julialang.org/en/v1/manual/style-guide/#Avoid-type-piracy). Keep in mind that the multiple-dispatch table is global state!

If you need multiple dispatch, but not the other features of `unpythonic`, see the [multipledispatch](https://github.com/mrocklin/multipledispatch) library, which likely runs faster.


#### ``typed``: add run-time type checks with type annotation syntax

The ``typed`` decorator creates a one-multimethod pony, which automatically enforces its argument types. Just like with ``generic``, the type specification may use features from the `typing` stdlib module.

```python
import typing
from unpythonic import typed

@typed
def blubnify(x: int, y: float):
    return x * y

@typed
def jack(x: typing.Union[int, str]):
    return x

assert blubnify(2, 21.0) == 42
blubnify(2, 3)  # TypeError
assert not hasattr(blubnify, "register")  # no more multimethods can be registered on this function

assert jack(42) == 42
assert jack("foo") == "foo"
jack(3.14)  # TypeError
```

For which features of the ``typing`` stdlib module are supported, see ``isoftype`` below.


#### ``isoftype``: the big sister of ``isinstance``

Type check object instances against type specifications at run time. This is the machinery that powers ``generic`` and ``typed``. This goes beyond ``isinstance`` in that many (but unfortunately not all) features of the ``typing`` standard library module are supported.

Any checks on the type arguments of the meta-utilities defined in the ``typing`` stdlib module are performed recursively using `isoftype` itself, in order to allow compound abstract specifications.

Some examples:

```python
import typing
from unpythonic import isoftype

# concrete types - uninteresting, we just delegate to `isinstance`
assert isoftype(17, int)
assert isoftype(lambda: ..., typing.Callable)

# typing.newType
UserId = typing.NewType("UserId", int)
assert isoftype(UserId(42), UserId)
# Note limitation: since NewType types discard their type information at
# run time, any instance of the underlying actual run-time type will match.
assert isoftype(42, UserId)

# typing.Any
assert isoftype(5, typing.Any)
assert isoftype("something", typing.Any)

# TypeVar, bare; a named type, but behaves like Any.
X = typing.TypeVar("X")
assert isoftype(3.14, X)
assert isoftype("anything", X)
assert isoftype(lambda: ..., X)

# TypeVar, with arguments; matches only the specs in the constraints.
Number = typing.TypeVar("Number", int, float, complex)
assert isoftype(31337, Number)
assert isoftype(3.14159, Number)
assert isoftype(1 + 2j, Number)

# typing.Optional
assert isoftype(None, typing.Optional[int])
assert isoftype(1337, typing.Optional[int])

# typing.Tuple
assert isoftype((1, 2, 3), typing.Tuple)
assert isoftype((1, 2, 3), typing.Tuple[int, ...])
assert isoftype((1, 2.1, "footgun"), typing.Tuple[int, float, str])

# typing.List
assert isoftype([1, 2, 3], typing.List[int])

U = typing.Union[int, str]
assert isoftype(42, U)
assert isoftype("hello yet again", U)

# abstract container types
assert isoftype({1: "foo", 2: "bar"}, typing.MutableMapping[int, str])
assert isoftype((1, 2, 3), typing.Sequence[int])
assert isoftype({1, 2, 3}, typing.AbstractSet[int])

# one-trick ponies
assert isoftype(3.14, typing.SupportsRound)
assert isoftype([1, 2, 3], typing.Sized)
```

See [the unit tests](../unpythonic/tests/test_typecheck.py) for more.

**CAUTION**: Callables are just checked for being callable; no further analysis is done. Type-checking callables properly requires a much more complex type checker.

**CAUTION**: The `isoftype` function is one big hack. In Python 3.6 through 3.9, there is no consistent way to handle a type specification at run time. We must access some private attributes of the ``typing`` meta-utilities, because that seems to be the only way to get what we need to do this.

If you need a run-time type checker, but not the other features of `unpythonic`, see the [`typeguard`](https://github.com/agronholm/typeguard) library.


## Exception tools

Utilities for dealing with exceptions.

### ``raisef``, ``tryf``: ``raise`` and ``try`` as functions

**Changed in v0.14.3**. *Now we have also `tryf`.*

**Changed in v0.14.2**. *The parameters of `raisef` now more closely match what would be passed to `raise`. See examples below. Old-style parameters are now deprecated, and support for them will be dropped in v0.15.0.*

Raise an exception from an expression position:

```python
from unpythonic import raisef

# plain `raise ...`
f = lambda x: raisef(RuntimeError("I'm in ur lambda raising exceptions"))

# `raise ... from ...`
exc = TypeError("oof")
g = lambda x: raisef(RuntimeError("I'm in ur lambda raising exceptions"), cause=exc)
```

Catch an exception in an expression position:

```python
from unpythonic import raisef, tryf

raise_instance = lambda: raisef(ValueError("all ok"))
test[tryf(lambda: raise_instance(),
         (ValueError, lambda err: f"got a ValueError: '{err.args[0]}'")) == "got a ValueError: 'all ok'"]
```

The exception handler is a function. It may optionally accept one argument, the exception instance.

Functions can also be specified for the `else` and `finally` behavior; see the docstring of `unpythonic.misc.tryf` for details.


### ``equip_with_traceback``

**Added in v0.14.3**.

In Python 3.7 and later, equip a manually created exception instance with a traceback. This is useful mainly in special cases, where `raise` cannot be used for some reason. (The `signal` function in the conditions-and-restarts system uses this.)

```python
e = SomeException(...)
e = equip_with_traceback(e)
```

The traceback is automatically extracted from the call stack of the calling thread.

Optionally, you can cull a number of the topmost frames by passing the optional argument `stacklevel=...`. Typically, for direct use of this function `stacklevel` should be the default `1` (so it excludes `equip_with_traceback` itself, but shows all stack levels from your code), and for use in a utility function that itself is called from your code, it should be `2` (so it excludes the utility function, too).


### ``async_raise``: inject an exception to another thread

**Added in v0.14.2**.

*Currently CPython only, because as of this writing (March 2020) PyPy3 does not expose the required functionality to the Python level, nor there seem to be any plans to do so.*

Usually injecting an exception into an unsuspecting thread makes absolutely no sense. But there are special cases, such as a REPL server which needs to send a `KeyboardInterrupt` into a REPL session thread that's happily stuck waiting for input at [`InteractiveConsole.interact()`](https://docs.python.org/3/library/code.html#code.InteractiveConsole.interact) - while the client that receives the actual `Ctrl+C` is running in a separate process. This and similar awkward situations in network programming are pretty much the only legitimate use case for this feature.

The name is `async_raise`, because it injects an *asynchronous exception*. This has nothing to do with `async`/`await`. Synchronous vs. asynchronous exceptions [mean something different](https://en.wikipedia.org/wiki/Exception_handling#Exception_synchronicity).

In a nutshell, a *synchronous* exception (which is the usual kind of exception) has an explicit `raise` somewhere in the code that the thread that encountered the exception is running. In contrast, an *asynchronous* exception **doesn't**, it just suddenly magically materializes from the outside. As such, it can in principle happen *anywhere*, with absolutely no hint about it in any obvious place in the code.

Needless to say this can be very confusing, so this feature should be used sparingly, if at all. **We only have it because the REPL server needs it.**

```python
from unpythonic import async_raise, box

out = box()
def worker():
    try:
        for j in range(10):
            sleep(0.1)
    except KeyboardInterrupt:  # normally, KeyboardInterrupt is only raised in the main thread
        pass
    out << j
t = threading.Thread(target=worker)
t.start()
sleep(0.1)  # make sure the worker has entered the loop
async_raise(t, KeyboardInterrupt)
t.join()
assert unbox(out) < 9  # thread terminated early due to the injected KeyboardInterrupt
```

#### So this is how KeyboardInterrupt works under the hood?

No, this is **not** how `KeyboardInterrupt` usually works. Rather, the OS sends a [SIGINT](https://en.wikipedia.org/wiki/Signal_(IPC)#SIGINT), which is then trapped by an [OS signal handler](https://docs.python.org/3/library/signal.html) that runs in the main thread.

(Note OS signal, in the *nix sense; this is unrelated to the Lisp sense, as in conditions-and-restarts.)

At that point the magic has already happened: the control of the main thread is now inside the signal handler, as if the signal handler was called from the otherwise currently innermost point on the call stack. All the handler needs to do is to perform a regular `raise`, and the exception will propagate correctly.

#### History

Original detective work by [Federico Ficarelli](https://gist.github.com/nazavode/84d1371e023bccd2301e) and [LIU Wei](https://gist.github.com/liuw/2407154).

Raising async exceptions is a [documented feature of Python's public C API](https://docs.python.org/3/c-api/init.html#c.PyThreadState_SetAsyncExc), but it was never meant to be invoked from within pure Python code. But then the CPython devs gave us [ctypes.pythonapi](https://docs.python.org/3/library/ctypes.html#accessing-values-exported-from-dlls), which allows access to Python's C API from within Python. (If you think ctypes.pythonapi is too quirky, the [pycapi](https://pypi.org/project/pycapi/) PyPI package smooths over the rough edges.) Combining the two gives `async_raise` without the need to compile a C extension.

Unfortunately PyPy doesn't currently (March 2020) implement this function in its CPython C API emulation layer, `cpyext`. See `unpythonic` issue [#58](https://github.com/Technologicat/unpythonic/issues/58).


### `reraise_in`, `reraise`: automatically convert exception types

**Added in v0.15.0.**

Sometimes it is useful to semantically convert exception types from one problem domain to another, particularly across the different levels of abstraction in an application. We provide `reraise_in` and `reraise` to do this with minimum boilerplate:

```python
from unpythonic import reraise_in, reraise, raisef

class LibraryException(Exception):
    pass
class MoreSophisticatedLibraryException(LibraryException):
    pass

class UnrelatedException(Exception):
    pass

class ApplicationException(Exception):
    pass

# reraise_in: expr form
# The mapping is {in0: out0, ...}
try:
    # reraise_in(thunk, mapping)
    reraise_in(lambda: raisef(LibraryException),
               {LibraryException: ApplicationException})
except ApplicationException:  # note the type!
    print("all ok!")

try:
    # subclasses are converted, too
    reraise_in(lambda: raisef(MoreSophisticatedLibraryException),
               {LibraryException: ApplicationException})
except ApplicationException:
    print("all ok!")

try:
    # tuples of types are accepted, like in `except` clauses
    reraise_in(lambda: raisef(UnrelatedException),
               {(LibraryException, UnrelatedException):
                     ApplicationException})
except ApplicationException:
    print("all ok!")

# reraise: block form
# The mapping is {in0: out0, ...}
try:
    with reraise({LibraryException: ApplicationException}):
        raise LibraryException
except ApplicationException:
    print("all ok!")

try:
    with reraise({LibraryException: ApplicationException}):
        raise MoreSophisticatedLibraryException
except ApplicationException:
    print("all ok!")

try:
    with reraise({(LibraryException, UnrelatedException):
                       ApplicationException}):
        raise LibraryException
except ApplicationException:
    print("all ok!")

```

If that's not much shorter than the hand-written `try`/`except`/`raise from`, consider that you can create the mapping once and then use it from a variable - this shortens it to just `with reraise(my_mapping)`.

Any exceptions that don't match anything in the mapping are passed through. When no exception occurs, `reraise_in` passes the return value of `thunk` through, and `reraise` does nothing.

Full details in docstrings.

If you use the conditions-and-restarts system, see also `resignal_in`, `resignal`, which perform the same job for conditions. The new signal is sent using the same error handling protocol as the original signal, so e.g. an `error` will remain an `error` even if re-signaling changes its type.


## Function call and return value tools

### ``def`` as a code block: ``@call``

Fuel for different thinking. Compare `call-with-something` in Lisps - but without parameters, so just `call`. A `def` is really just a new lexical scope to hold code to run later... or right now!

At the top level of a module, this is seldom useful, but keep in mind that Python allows nested function definitions. Used with an inner ``def``, this becomes a versatile tool.

*Make temporaries fall out of scope as soon as no longer needed*:

```python
from unpythonic import call

@call
def x():
    a = 2  #    many temporaries that help readability...
    b = 3  # ...of this calculation, but would just pollute locals...
    c = 5  # ...after the block exits
    return a * b * c
print(x)  # 30
```

*Multi-break out of nested loops* - `continue`, `break` and `return` are really just second-class [ec](https://docs.racket-lang.org/reference/cont.html#%28def._%28%28lib._racket%2Fprivate%2Fletstx-scheme..rkt%29._call%2Fec%29%29)s. So `def` to make `return` escape to exactly where you want:

```python
@call
def result():
    for x in range(10):
        for y in range(10):
            if x * y == 42:
                return (x, y)
print(result)  # (6, 7)
```

(But see ``@catch``, ``throw``, and ``call_ec``.)

Compare the sweet-exp Racket:

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

Noting [what ``let/ec`` does](https://docs.racket-lang.org/reference/cont.html#%28form._%28%28lib._racket%2Fprivate%2Fletstx-scheme..rkt%29._let%2Fec%29%29), using ``call_ec`` we can make the Python even closer to the Racket:

```python
@call_ec
def result(rtn):
    for x in range(10):
        for y in range(10):
            if x * y == 42:
                rtn((x, y))
print(result)  # (6, 7)
```

*Twist the meaning of `def` into a "let statement"*:

```python
@call
def result(x=1, y=2, z=3):
    return x * y * z
print(result)  # 6
```

(But see `blet`, `bletrec` if you want an `env` instance.)

*Letrec without `letrec`*, when it doesn't have to be an expression:

```python
@call
def t():
    def evenp(x): return x == 0 or oddp(x - 1)
    def oddp(x): return x != 0 and evenp(x - 1)
    return evenp(42)
print(t)  # True
```

Essentially the implementation is just `def call(thunk): return thunk()`. The point is to:

 - Make it explicit right at the definition site that this block is *going to be called now* (in contrast to an explicit call and assignment *after* the definition). Centralize the related information. Align the presentation order with the thought process.

 - Help eliminate errors, in the same way as the habit of typing parentheses only in pairs. No risk of forgetting to call the block after writing the definition.

 - Document that the block is going to be used only once. Tell the reader there's no need to remember this definition.

Note [the grammar](https://docs.python.org/3/reference/grammar.html) requires a newline after a decorator.

**NOTE**: ``call`` can also be used as a normal function: ``call(f, *a, **kw)`` is the same as ``f(*a, **kw)``. This is occasionally useful.


### ``@callwith``: freeze arguments, choose function later

If you need to pass arguments when using ``@call`` as a decorator, use its cousin ``@callwith``:

```python
from unpythonic import callwith

@callwith(3)
def result(x):
    return x**2
assert result == 9
```

Like ``call``, it can also be called normally. It's essentially an argument freezer:

```python
def myadd(a, b):
    return a + b
def mymul(a, b):
    return a * b
apply23 = callwith(2, 3)
assert apply23(myadd) == 5
assert apply23(mymul) == 6
```

When called normally, the two-step application is mandatory. The first step stores the given arguments. It returns a function ``f(callable)``. When ``f`` is called, it calls its ``callable`` argument, passing in the arguments stored in the first step.

In other words, ``callwith`` is similar to ``functools.partial``, but without specializing to any particular function. The function to be called is given later, in the second step.

Hence, ``callwith(2, 3)(myadd)`` means "make a function that passes in two positional arguments, with values ``2`` and ``3``. Then call this function for the callable ``myadd``". But if we instead write``callwith(2, 3, myadd)``, it means "make a function that passes in three positional arguments, with values ``2``, ``3`` and ``myadd`` - not what we want in the above example.

If you want to specialize some arguments now and some later, combine with ``partial``:

```python
from functools import partial

p1 = partial(callwith, 2)
p2 = partial(p1, 3)
p3 = partial(p2, 4)
apply234 = p3()  # actually call callwith, get the function
def add3(a, b, c):
    return a + b + c
def mul3(a, b, c):
    return a * b * c
assert apply234(add3) == 9
assert apply234(mul3) == 24
```

If the code above feels weird, it should. Arguments are gathered first, and the function to which they will be passed is chosen in the last step.

Another use case of ``callwith`` is ``map``, if we want to vary the function instead of the data:

```python
m = map(callwith(3), [lambda x: 2*x, lambda x: x**2, lambda x: x**(1/2)])
assert tuple(m) == (6, 9, 3**(1/2))
```

If you use the quick lambda macro `f[]` (underscore notation for Python), this combines nicely:

```python
from unpythonic.syntax import macros, f
from unpythonic import callwith

m = map(callwith(3), [f[2 * _], f[_**2], f[_**(1/2)]])
assert tuple(m) == (6, 9, 3**(1/2))
```

A pythonic alternative to the above examples is:

```python
a = [2, 3]
def myadd(a, b):
    return a + b
def mymul(a, b):
    return a * b
assert myadd(*a) == 5
assert mymul(*a) == 6

a = [2]
a += [3]
a += [4]
def add3(a, b, c):
    return a + b + c
def mul3(a, b, c):
    return a * b * c
assert add3(*a) == 9
assert mul3(*a) == 24

m = (f(3) for f in [lambda x: 2*x, lambda x: x**2, lambda x: x**(1/2)])
assert tuple(m) == (6, 9, 3**(1/2))
```

Inspired by *Function application with $* in [LYAH: Higher Order Functions](http://learnyouahaskell.com/higher-order-functions).


### `Values`: multiple and named return values

**Added in v0.15.0.**

`Values` is a structured multiple-return-values type.

With `Values`, you can return multiple values positionally and by name. This completes the symmetry between passing function arguments and returning values from a function: Python itself allows passing arguments by name, but has no concept of returning values by name. This class adds that concept.

Having a `Values` type separate from `tuple` also helps with semantic accuracy. In `unpythonic` 0.15.0 and later, a `tuple` return value now means just that - one value that is a `tuple`. It is different from a `Values` that contains several positional return values (that are meant to be treated separately e.g. by a function composition utility).

Inspired by the [`values`](https://docs.racket-lang.org/reference/values.html) form of Racket.

#### When to use `Values`

Most of the time, returning a tuple to denote multiple-return-values and unpacking it is just fine, and that is exactly what `unpythonic` does internally in many places.

But the distinction is critically important in function composition, so that positional return values can be automatically mapped into positional arguments to the next function in the chain, and named return values into named arguments.

Accordingly, various parts of `unpythonic` that deal with function composition use the `Values` abstraction; particularly `curry`, and the `compose` and `pipe` families, and the `with continuations` macro.

#### Behavior

`Values` is a duck-type with some features of both sequences and mappings, but not the full `collections.abc` API of either.

Each operation that obviously and without ambiguity makes sense only for the positional or named part, accesses that part.

The only exception is `__getitem__` (subscripting), which makes sense for both parts, unambiguously, because the key types differ. If the index expression is an `int` or a `slice`, it is an index/slice for the positional part. If it is an `str`, it is a key for the named part.

If you need to explicitly access either part (and its full API), use the `rets` and `kwrets` attributes. The names are in analogy with `args` and `kwargs`.

`rets` is a `tuple`, and `kwrets` is an `unpythonic.collections.frozendict`.

`Values` objects can be compared for equality. Two `Values` objects are equal if both their `rets` and `kwrets` (respectively) are.

Examples:

```python
def f():
    return Values(1, 2, 3)
result = f()
assert isinstance(result, Values)
assert result.rets == (1, 2, 3)
assert not result.kwrets
assert result[0] == 1
assert result[:-1] == (1, 2)
a, b, c = result  # if no kwrets, can be unpacked like a tuple
a, b, c = f()

def g():
    return Values(x=3)  # named return value
result = g()
assert isinstance(result, Values)
assert not result.rets
assert result.kwrets == {"x": 3}  # actually a `frozendict`
assert "x" in result  # `in` looks in the named part
assert result["x"] == 3
assert result.get("x", None) == 3
assert result.get("y", None) is None
assert tuple(result.keys()) == ("x",)  # also `values()`, `items()`

def h():
    return Values(1, 2, x=3)
result = h()
assert isinstance(result, Values)
assert result.rets == (1, 2)
assert result.kwrets == {"x": 3}
a, b = result.rets  # positionals can always be unpacked explicitly
assert result[0] == 1
assert "x" in result
assert result["x"] == 3

def silly_but_legal():
    return Values(42)
result = silly_but_legal()
assert result.rets[0] == 42
assert result.ret == 42  # shorthand for single-value case
```

The last example is silly, but legal, because it is preferable to just omit the `Values` if it is known that there is only one return value. (This also applies when that value is a `tuple`, when the intent is to return it as a single `tuple`, in contexts where this distinction matters.)


### `valuify`

We also provide `valuify`, a decorator that converts the pythonic tuple-as-multiple-return-values idiom into `Values`, for compatibility with our function composition utilities.

It converts a `tuple` return value, exactly; no subclasses.

Demonstrating just the conversion:

```python
@valuify
def f(x, y, z):
    return x, y, z

assert isinstance(f(1, 2, 3), Values)
assert f(1, 2, 3) == Values(1, 2, 3)
```


## Numerical tools

We briefly introduce the functions below. More details and examples can be found in the docstrings and [the unit tests](../unpythonic/tests/test_numutil.py).

**CAUTION** for anyone new to numerics:

When working with floating-point numbers, keep in mind that they are, very roughly speaking, a finite-precision logarithmic representation of [ℝ](https://en.wikipedia.org/wiki/Real_line). They are, necessarily, actually a subset of [ℚ](https://en.wikipedia.org/wiki/Rational_number), that's not even [dense](https://en.wikipedia.org/wiki/Dense_set). The spacing between adjacent floats depends on where you are on the real line; see `ulp` below.

For finer points concerning the behavior of floating-point numbers, see [David Goldberg (1991): What every computer scientist should know about floating-point arithmetic](https://docs.oracle.com/cd/E19957-01/806-3568/ncg_goldberg.html), or for a [tl;dr](http://catplanet.org/tldr-cat-meme/) version, [the floating point guide](https://floating-point-gui.de/).

Or you could look at [my lecture slides from 2018](https://github.com/Technologicat/python-3-scicomp-intro/tree/master/lecture_slides); particularly, [lecture 7](https://github.com/Technologicat/python-3-scicomp-intro/blob/master/lecture_slides/lectures_tut_2018_7.pdf) covers the floating-point representation. It collects the most important details, and some more links to further reading.


### `almosteq`: floating-point almost-equality

Test floating-point numbers for near-equality. Beside the built-in `float`, we support also the arbitrary-precision software-implemented floating-point type `mpf` from `SymPy`'s `mpmath` package.

Anything else, for example `SymPy` expressions, strings, and containers (regardless of content), is tested for exact equality.

For ``mpmath.mpf``, we just delegate to ``mpmath.almosteq``, with the given tolerance.

For ``float``, we use the strategy suggested in [the floating point guide](https://floating-point-gui.de/errors/comparison/), because naive absolute and relative comparisons against a tolerance fail in commonly encountered situations.


### `fixpoint`: arithmetic fixed-point finder

**Added in v0.14.2.**

Compute the (arithmetic) fixed point of a function, starting from a given initial guess. The fixed point must be attractive for this to work. See the [Banach fixed point theorem](https://en.wikipedia.org/wiki/Banach_fixed-point_theorem).

(Not to be confused with the logical fixed point with respect to the definedness ordering, which is what Haskell's `fix` function relates to.)

If the fixed point is attractive, and the values are represented in floating point (hence finite precision), the computation should eventually converge down to the last bit (barring roundoff or catastrophic cancellation in the final few steps). Hence the default tolerance is zero; but a desired tolerance can be passed as an argument.

**CAUTION**: an arbitrary function from ℝ to ℝ **does not** necessarily have a fixed point. Limit cycles and chaotic behavior of the function will cause non-termination. Keep in mind the classic example, [the logistic map](https://en.wikipedia.org/wiki/Logistic_map).

Examples:

```python
from math import cos, sqrt
from unpythonic import fixpoint, ulp

c = fixpoint(cos, x0=1)

# Actually "Newton's" algorithm for the square root was already known to the
# ancient Babylonians, ca. 2000 BCE. (Carl Boyer: History of mathematics)
def sqrt_newton(n):
    def sqrt_iter(x):  # has an attractive fixed point at sqrt(n)
        return (x + n / x) / 2
    return fixpoint(sqrt_iter, x0=n / 2)
assert abs(sqrt_newton(2) - sqrt(2)) <= ulp(1.414)
```


### `partition_int`, `partition_int_triangular`: partition integers

**Added in v0.14.2.**

**Changed in v0.15.0.** *Added `partition_int_triangular`.*

The `partition_int` function [partitions](https://en.wikipedia.org/wiki/Partition_(number_theory)) a small positive integer, i.e., splits it in all possible ways, into smaller integers that sum to it. This is useful e.g. to determine the number of letters to allocate for each component of an anagram that may consist of several words.

The `partition_int_triangular` function is like `partition_int`, but accepts only triangular numbers (1, 3, 6, 10, ...) as components of the partition. This function answers a timeless question: if I have `n` stackable plushies, what are the possible stack configurations?

(These are not to be confused with `unpythonic.partition`, which partitions an iterable based on a predicate.)

Examples:

```python
from unpythonic import partition_int, partition_int_triangular

assert tuple(partition_int(4)) == ((4,), (3, 1), (2, 2), (2, 1, 1), (1, 3), (1, 2, 1), (1, 1, 2), (1, 1, 1, 1))
assert tuple(partition_int(5, lower=2)) == ((5,), (3, 2), (2, 3))
assert tuple(partition_int(5, lower=2, upper=3)) == ((3, 2), (2, 3))

assert (frozenset(tuple(sorted(c)) for c in partition_int_triangular(78, lower=10)) ==
        frozenset({(10, 10, 10, 10, 10, 28),
                   (10, 10, 15, 15, 28),
                   (15, 21, 21, 21),
                   (21, 21, 36),
                   (78,)}))
```

As the first example demonstrates, most of the splits are a ravioli consisting mostly of ones. It is much faster to not generate such splits than to filter them out from the result. Use the `lower` parameter to set the smallest acceptable value for one component of the split; the default value `lower=1` generates all splits. Similarly, the `upper` parameter sets the largest acceptable value for one component of the split. The default `upper=None` sets no upper limit.

In `partition_int_triangular`, the `lower` and `upper` parameters work exactly the same. The only difference to `partition_int` is that each component of the split must be a triangular number.

**CAUTION**: The number of possible partitions grows very quickly with `n`, so in practice these functions are only useful for small numbers, or with a lower limit that is not too much smaller than `n / 2`.


### ``ulp``: unit in last place

**Added in v0.14.2.**

Given a floating point number `x`, return the value of the *unit in the last place* (the "least significant bit"). This is the local size of a "tick", i.e. the difference between `x` and the *next larger* float. At `x = 1.0`, this is the [machine epsilon](https://en.wikipedia.org/wiki/Machine_epsilon), by definition of the machine epsilon.

The float format is [IEEE-754](https://en.wikipedia.org/wiki/IEEE_754), i.e. standard Python `float`.

This is just a small convenience function that is for some reason missing from the `math` standard library.

```python
from unpythonic import ulp

# in IEEE-754, exponent changes at integer powers of two
print([ulp(x) for x in (0.25, 0.5, 1.0, 2.0, 4.0)])
# --> [5.551115123125783e-17,
#      1.1102230246251565e-16,
#      2.220446049250313e-16,   # x = 1.0, so this is sys.float_info.epsilon
#      4.440892098500626e-16,
#      8.881784197001252e-16]
print(ulp(1e10))
# --> 1.9073486328125e-06
print(ulp(1e100))
# --> 1.942668892225729e+84
print(ulp(2**52))
# --> 1.0  # yes, exactly 1
```

When `x` is a round number in base-10, the ULP is not, because the usual kind of floats use base-2.


## Other

Stuff that didn't fit elsewhere.

### ``callsite_filename``

**Added in v0.14.3**.

**Changed in v0.15.0.** *This utility now ignores `unpythonic`'s call helpers, and gives the filename from the deepest stack frame that does not match one of our helpers. This allows the testing framework report the source code filename correctly when testing code using macros that make use of these helpers (e.g. `autocurry`, `lazify`).*

Return the filename from which this function is being called. Useful as a building block for debug utilities and similar.


### ``safeissubclass``

**Added in v0.14.3**.

Convenience function. Like `issubclass(cls)`, but if `cls` is not a class, swallow the `TypeError` and return `False`.


### ``pack``: multi-arg constructor for tuple

The default ``tuple`` constructor accepts a single iterable. But sometimes one needs to pass in the elements separately. Most often a literal tuple such as ``(1, 2, 3)`` is then the right solution, but there are situations that do not admit a literal tuple. Enter ``pack``:

```python
from unpythonic import pack

myzip = lambda lol: map(pack, *lol)
lol = ((1, 2), (3, 4), (5, 6))
assert tuple(myzip(lol)) == ((1, 3, 5), (2, 4, 6))
```


### ``namelambda``: rename a function

Rename any function object (including lambdas). The return value of ``namelambda`` is a modified copy; the original function object is not mutated. The input can be any function object (``isinstance(f, (types.LambdaType, types.FunctionType))``). It will be renamed even if it already has a name.

This is mainly useful in those situations where you return a lambda as a closure, call it much later, and it happens to crash - so you can tell from the stack trace *which* of the *N* lambdas in your codebase it is.

For technical reasons, ``namelambda`` conforms to the parametric decorator API. Usage:

```python
from unpythonic import namelambda

square = namelambda("square")(lambda x: x**2)
assert square.__name__ == "square"

kaboom = namelambda("kaboom")(lambda: some_typoed_name)
kaboom()  # --> stack trace, showing the function name "kaboom"
```

The first call returns a *foo-renamer*, which takes a function object and returns a copy that has its name changed to *foo*.

Technically, this updates ``__name__`` (the obvious place), ``__qualname__`` (used by ``repr()``), and ``__code__.co_name`` (used by stack traces).

**CAUTION**: There is one pitfall:

```python
from unpythonic import namelambda, withself

nested = namelambda("outer")(lambda: namelambda("inner")(withself(lambda self: self)))
print(nested.__qualname__)    # "outer"
print(nested().__qualname__)  # "<lambda>.<locals>.inner"
```

The inner lambda does not see the outer's new name; the parent scope names are baked into a function's ``__qualname__`` too early for the outer rename to be in effect at that time.


### ``timer``: a context manager for performance testing

```python
from unpythonic import timer

with timer() as tim:
    for _ in range(int(1e6)):
        pass
print(tim.dt)  # elapsed time in seconds (float)

with timer(p=True):  # if p, auto-print result
    for _ in range(int(1e6)):
        pass
```

The auto-print mode is a convenience feature to minimize bureaucracy if you just want to see the *Δt*. To instead access the *Δt* programmatically, name the timer instance using the ``with ... as ...`` syntax. After the context exits, the *Δt* is available in its ``dt`` attribute.


### ``getattrrec``, ``setattrrec``: access underlying data in an onion of wrappers

```python
from unpythonic import getattrrec, setattrrec

class Wrapper:
    def __init__(self, x):
        self.x = x

w = Wrapper(Wrapper(42))
assert type(getattr(w, "x")) == Wrapper
assert type(getattrrec(w, "x")) == int
assert getattrrec(w, "x") == 42

setattrrec(w, "x", 23)
assert type(getattr(w, "x")) == Wrapper
assert type(getattrrec(w, "x")) == int
assert getattrrec(w, "x") == 23
```


### ``arities``, ``kwargs``, ``resolve_bindings``: Function signature inspection utilities

**Added in v0.14.2**: `resolve_bindings`. *Get the parameter bindings a given callable would establish if it was called with the given args and kwargs. This is mainly of interest for implementing memoizers, since this allows them to see (e.g.) `f(1)` and `f(a=1)` as the same thing for `def f(a): pass`.*

**Changed in v0.15.0.** *Now `resolve_bindings` is a thin wrapper on top of `inspect.Signature.bind`, which was added in Python 3.5. In `unpythonic` 0.14.2 and 0.14.3, we used to have our own implementation of the parameter binding algorithm (that ran also on Python 3.4), but it is no longer needed, since now we support only Python 3.6 and later. Now `resolve_bindings` returns an `inspect.BoundArguments` object.*

*Now `tuplify_bindings` accepts an `inspect.BoundArguments` object instead of its previous input format. The function is only ever intended to be used to postprocess the output of `resolve_bindings`, so this change shouldn't affect your own code.*

Convenience functions providing an easy-to-use API for inspecting a function's signature. The heavy lifting is done by ``inspect``.

Methods on objects and classes are treated specially, so that the reported arity matches what the programmer actually needs to supply when calling the method (i.e., implicit ``self`` and ``cls`` are ignored).

```python
from unpythonic import (arities, arity_includes, UnknownArity,
                        kwargs, required_kwargs, optional_kwargs,
                        resolve_bindings)

f = lambda a, b: None
assert arities(f) == (2, 2)  # min, max positional arity

f = lambda a, b=23: None
assert arities(f) == (1, 2)
assert arity_includes(f, 2) is True
assert arity_includes(f, 3) is False

f = lambda a, *args: None
assert arities(f) == (1, float("+inf"))

f = lambda *, a, b, c=42: None
assert arities(f) == (0, 0)
assert required_kwargs(f) == set(('a', 'b'))
assert optional_kwargs(f) == set(('c'))
assert kwargs(f) == (set(('a', 'b')), set(('c')))

class A:
    def __init__(self):
        pass
    def meth(self, x):
        pass
    @classmethod
    def classmeth(cls, x):
        pass
    @staticmethod
    def staticmeth(x):
        pass
assert arities(A) == (0, 0)  # constructor of "A" takes no args beside the implicit self
# methods on the class
assert arities(A.meth) == (2, 2)
assert arities(A.classmeth) == (1, 1)
assert arities(A.staticmeth) == (1, 1)
# methods on an instance
a = A()
assert arities(a.meth) == (1, 1)       # self is implicit, so just one
assert arities(a.classmeth) == (1, 1)  # cls is implicit
assert arities(a.staticmeth) == (1, 1)

def f(a, b, c):
    pass
assert tuple(resolve_bindings(f, 1, 2, 3).items()) == (("a", 1), ("b", 2), ("c", 3))
assert tuple(resolve_bindings(f, a=1, b=2, c=3).items()) == (("a", 1), ("b", 2), ("c", 3))
assert tuple(resolve_bindings(f, 1, 2, c=3).items()) == (("a", 1), ("b", 2), ("c", 3))
assert tuple(resolve_bindings(f, 1, c=3, b=2).items()) == (("a", 1), ("b", 2), ("c", 3))
assert tuple(resolve_bindings(f, c=3, b=2, a=1).items()) == (("a", 1), ("b", 2), ("c", 3))
```

We special-case the builtin functions that either fail to return any arity (are uninspectable) or report incorrect arity information, so that also their arities are reported correctly. Note we **do not** special-case the *methods* of any builtin classes, so e.g. ``list.append`` remains uninspectable. This limitation might or might not be lifted in a future version.

If the arity cannot be inspected, and the function is not one of the special-cased builtins, the ``UnknownArity`` exception is raised.

These functions are internally used in various places in unpythonic, particularly ``curry``, ``fix``, and ``@generic``. The ``let`` and FP looping constructs also use these to emit a meaningful error message if the signature of user-provided function does not match what is expected.

Inspired by various Racket functions such as ``(arity-includes?)`` and ``(procedure-keywords)``.


### ``Popper``: a pop-while iterator

Consider this highly artificial example:

```python
from collections import deque

inp = deque(range(5))
out = []
while inp:
    x = inp.pop(0)
    out.append(x)
assert inp == deque([])
assert out == list(range(5))
```

``Popper`` condenses the ``while`` and ``pop`` into a ``for``, while allowing the loop body to mutate the input iterable in arbitrary ways (we never actually ``iter()`` it):

```python
from collections import deque
from unpythonic import Popper

inp = deque(range(5))
out = []
for x in Popper(inp):
    out.append(x)
assert inp == deque([])
assert out == list(range(5))

inp = deque(range(3))
out = []
for x in Popper(inp):
    out.append(x)
    if x < 10:
        inp.appendleft(x + 10)
assert inp == deque([])
assert out == [0, 10, 1, 11, 2, 12]
```

``Popper`` comboes with other iterable utilities, such as ``window``:

```python
from collections import deque
from unpythonic import Popper, window

inp = deque(range(3))
out = []
for a, b in window(2, Popper(inp)):
    out.append((a, b))
    if a < 10:
        inp.append(a + 10)
assert inp == deque([])
assert out == [(0, 1), (1, 2), (2, 10), (10, 11), (11, 12)]
```

(Although ``window`` invokes ``iter()`` on the ``Popper``, this works because the ``Popper`` never invokes ``iter()`` on the underlying container. Any mutations to the input container performed by the loop body will be understood by ``Popper`` and thus also seen by the ``window``. The first ``n`` elements, though, are read before the loop body gets control, because the window needs them to initialize itself.)

One possible real use case for ``Popper`` is to split sequences of items, stored as lists in a deque, into shorter sequences where some condition is contiguously ``True`` or ``False``. When the condition changes state, just commit the current subsequence, and push the rest of that input sequence (still requiring analysis) back to the input deque, to be dealt with later.

The argument to ``Popper`` (here ``lst``) contains the **remaining** items. Each iteration pops an element **from the left**. The loop terminates when ``lst`` is empty.

The input container must support either ``popleft()`` or ``pop(0)``. This is fully duck-typed. At least ``collections.deque`` and any ``collections.abc.MutableSequence`` (including ``list``) are fine.

Per-iteration efficiency is O(1) for ``collections.deque``, and O(n) for a ``list``.

Named after [Karl Popper](https://en.wikipedia.org/wiki/Karl_Popper).
