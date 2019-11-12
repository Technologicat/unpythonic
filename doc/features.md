# Unpythonic: Python meets Lisp and Haskell

This is the pure-Python API of `unpythonic`. Most features listed here need no macros, and are intended to be used directly.

The exception are the features marked **[M]**, which are primarily intended as a code generation target API for macros. See the [documentation for syntactic macros](../macro_extras/) for details. Usually the relevant macro has the same name as the underlying implementation; for example, `unpythonic.do` is the implementation, while `unpythonic.syntax.do` is the macro. The purpose of the macro layer is to improve ease of use by removing accidental complexity, thus providing a more human-readable source code representation that compiles to calls to the underlying API. If you don't want to depend on MacroPy, feel free to use also these APIs as defined below (though, this may be less convenient).

### Features

[**Bindings**](#bindings)
- [``let``, ``letrec``: local bindings in an expression](#let-letrec-local-bindings-in-an-expression) **[M]**
  - [Lispylet: alternative syntax](#lispylet-alternative-syntax) **[M]**
- [``env``: the environment](#env-the-environment)
- [``assignonce``](#assignonce), a relative of ``env``.
- [``dyn``: dynamic assignment](#dyn-dynamic-assignment) a.k.a. parameterize, special variables, fluid variables, "dynamic scoping".

[**Containers**](#containers)
- [``frozendict``: an immutable dictionary](#frozendict-an-immutable-dictionary)
- [`cons` and friends: pythonic lispy linked lists](#cons-and-friends-pythonic-lispy-linked-lists)
- [``box``: a mutable single-item container](#box-a-mutable-single-item-container)
- [Container utilities](#container-utilities): ``get_abcs``, ``in_slice``, ``index_in_slice``

[**Sequencing**](#sequencing), run multiple expressions in any expression position (incl. inside a ``lambda``).
- [``begin``: sequence side effects](#begin-sequence-side-effects)
- [``do``: stuff imperative code into an expression](#do-stuff-imperative-code-into-an-expression) **[M]**
- [``pipe``, ``piped``, ``lazy_piped``: sequence functions](#pipe-piped-lazy_piped-sequence-functions)

[**Batteries**](#batteries) missing from the standard library.
- [**Batteries for functools**](#batteries-for-functools): `memoize`, `curry`, `compose`, `withself`, `fix` and more.
  - [``curry`` and reduction rules](#curry-and-reduction-rules): we provide some extra features for bonus Haskellness.
  - [``fix``: break infinite recursion cycles](#fix-break-infinite-recursion-cycles)
- [**Batteries for itertools**](#batteries-for-itertools): multi-input folds, scans (lazy partial folds); unfold; lazy partial unpacking of iterables, etc.
- [``islice``: slice syntax support for ``itertools.islice``](#islice-slice-syntax-support-for-itertoolsislice)
- [`gmemoize`, `imemoize`, `fimemoize`: memoize generators](#gmemoize-imemoize-fimemoize-memoize-generators), iterables and iterator factories.
- [``fup``: functional update; ``ShadowedSequence``](#fup-functional-update-shadowedsequence): like ``collections.ChainMap``, but for sequences.
- [``view``: writable, sliceable view into a sequence](#view-writable-sliceable-view-into-a-sequence) with scalar broadcast on assignment.
- [``mogrify``: update a mutable container in-place](#mogrify-update-a-mutable-container-in-place)
- [``s``, ``m``, ``mg``: lazy mathematical sequences with infix arithmetic](#s-m-mg-lazy-mathematical-sequences-with-infix-arithmetic)

[**Control flow tools**](#control-flow-tools)
- [``trampolined``, ``jump``: tail call optimization (TCO) / explicit continuations](#trampolined-jump-tail-call-optimization-tco--explicit-continuations)
- [``looped``, ``looped_over``: loops in FP style (with TCO)](#looped-looped_over-loops-in-fp-style-with-tco)
- [``gtrampolined``: generators with TCO](#gtrampolined-generators-with-tco): tail-chaining; like ``itertools.chain``, but from inside a generator.
- [``setescape``, ``escape``: escape continuations (ec)](#setescape-escape-escape-continuations-ec)
  - [``call_ec``: first-class escape continuations](#call_ec-first-class-escape-continuations), like Racket's ``call/ec``.
- [``forall``: nondeterministic evaluation](#forall-nondeterministic-evaluation), a tuple comprehension with multiple body expressions.

[**Other**](#other)
- [``def`` as a code block: ``@call``](#def-as-a-code-block-call): run a block of code immediately, in a new lexical scope.
- [``@callwith``: freeze arguments, choose function later](#callwith-freeze-arguments-choose-function-later)
- [``raisef``: ``raise`` as a function](#raisef-raise-as-a-function), useful inside a lambda.
- [``pack``: multi-arg constructor for tuple](#pack-multi-arg-constructor-for-tuple)
- [``namelambda``, rename a function](#namelambda-rename-a-function)
- [``timer``: a context manager for performance testing](#timer-a-context-manager-for-performance-testing)
- [``getattrrec``, ``setattrrec``: access underlying data in an onion of wrappers](#getattrrec-setattrrec-access-underlying-data-in-an-onion-of-wrappers)
- [``arities``, ``kwargs``: Function signature inspection utilities](#arities-kwargs-function-signature-inspection-utilities)
- [``Popper``: a pop-while iterator](#popper-a-pop-while-iterator)
- [``ulp``: unit in last place](#ulp-unit-in-last-place)

For many examples, see [the unit tests](unpythonic/test/), the docstrings of the individual features, and this guide.

*This document doubles as the API reference, but despite maintenance on a best-effort basis, may occasionally be out-of-date at places. In case of conflicts in documentation, believe the unit tests first; specifically the code, not necessarily the comments. Everything else (comments, docstrings and this guide) should agree with the unit tests. So if something fails to work as advertised, check what the tests say - and optionally file an issue on GitHub so that the documentation can be fixed.*

**This document is up-to-date for v0.14.1.**

## Bindings

Tools to bind identifiers in ways not ordinarily supported by Python.

### ``let``, ``letrec``: local bindings in an expression

**NOTE**: This is primarily a code generation target API for the ``let[]`` family of [macros](../macro_extras/), which make the constructs easier to use. Below is the documentation for the raw API.

Introduces bindings local to an expression, like Scheme's ``let`` and ``letrec``. For easy-to-use versions of these constructs that look almost like normal Python, see [our macros](../macro_extras/).

In ``let``, the bindings are independent (do not see each other). A binding is of the form ``name=value``, where ``name`` is a Python identifier, and ``value`` is any expression.

Use a `lambda e: ...` to supply the environment to the body:

```python
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
counter = let(x=0,
              body=lambda e:
                     lambda:
                       begin(e.set("x", e.x + 1),  # can also use e << ("x", e.x + 1)
                             e.x))
counter()  # --> 1
counter()  # --> 2
```

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

*Let over def* decorator ``@dlet``, to *let over lambda* more pythonically:

```python
@dlet(x=0)
def counter(*, env=None):  # named argument "env" filled in by decorator
    env.x += 1
    return env.x
counter()  # --> 1
counter()  # --> 2
```

In `letrec`, bindings may depend on ones above them in the same `letrec`, by using `lambda e: ...` (**Python 3.6+**):

```python
x = letrec(a=1,
           b=lambda e:
                  e.a + 1,
           body=lambda e:
                  e.b)  # --> 2
```

In `letrec`, the ``value`` of each binding is either a simple value (non-callable, and doesn't use the environment), or an expression of the form ``lambda e: valexpr``, providing access to the environment as ``e``. If ``valexpr`` itself is callable, the binding **must** have the ``lambda e: ...`` wrapper to prevent any misunderstandings in the environment initialization procedure.

In a non-callable ``valexpr``, trying to depend on a binding below it raises ``AttributeError``.

A callable ``valexpr`` may depend on any bindings (also later ones) in the same `letrec`. Mutually recursive functions:

```python
letrec(evenp=lambda e:
               lambda x:
                 (x == 0) or e.oddp(x - 1),
       oddp=lambda e:
               lambda x:
                 (x != 0) and e.evenp(x - 1),
       body=lambda e:
               e.evenp(42))  # --> True
```

Order-preserving list uniqifier:

```python
u = lambda lst: letrec(seen=set(),
                       see=lambda e:
                              lambda x:
                                begin(e.seen.add(x),
                                      x),
                       body=lambda e:
                              [e.see(x) for x in lst if x not in e.seen])
```

**CAUTION**: in Pythons older than 3.6, bindings are **initialized in an arbitrary order**, also in `letrec`. This is a limitation of the kwargs abuse. Hence mutually recursive functions are possible, but a non-callable `valexpr` cannot depend on other bindings in the same `letrec`.

Trying to access `e.foo` from `e.bar` arbitrarily produces either the intended value of `e.foo`, or the uninitialized `lambda e: ...`, depending on whether `e.foo` has been initialized or not at the point of time when `e.bar` is being initialized.

This has been fixed in Python 3.6, see [PEP 468](https://www.python.org/dev/peps/pep-0468/).

#### Lispylet: alternative syntax

**NOTE**: This is primarily a code generation target API for the ``let[]`` family of [macros](../macro_extras/), which make the constructs easier to use. Below is the documentation for the raw API.

If you need **guaranteed left-to-right initialization** of `letrec` bindings in Pythons older than 3.6, there is also an alternative implementation for all the `let` constructs, with positional syntax and more parentheses. The only difference is the syntax; the behavior is identical with the default implementation.

These constructs are available in the top-level `unpythonic` namespace, with the ``ordered_`` prefix: ``ordered_let``, ``ordered_letrec``, ``ordered_dlet``, ``ordered_dletrec``, ``ordered_blet``, ``ordered_bletrec``.

It is also possible to override the default `let` constructs by the `ordered_` variants, like this:

```python
from unpythonic.lispylet import *  # override the default "let" implementation

letrec((('a', 1),
        ('b', lambda e:
                e.a + 1)),  # may refer to any bindings above it in the same letrec, also in Python < 3.6
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

The let macros internally use this *lispylet* implementation.


### ``env``: the environment

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

(This allows using `with env(...) as e:` as a poor man's `let`, if you have a block of statements you want to locally scope some names to, but don't want to introduce a `def`.)

``env`` provides the ``collections.abc.Mapping`` and  ``collections.abc.MutableMapping`` APIs.


### ``assignonce``

In Scheme terms, make `define` and `set!` look different:

```python
from unpythonic import assignonce

with assignonce() as e:
    e.foo = "bar"           # new definition, ok
    e.set("foo", "tavern")  # explicitly rebind e.foo, ok
    e << ("foo", "tavern")  # same thing (but return e instead of new value, suitable for chaining)
    e.foo = "quux"          # AttributeError, e.foo already defined.
```

It's a subclass of ``env``, so it shares most of the same [features](#env-the-environment) and allows similar usage.


### ``dyn``: dynamic assignment

([As termed by Felleisen.](https://groups.google.com/forum/#!topic/racket-users/2Baxa2DxDKQ) Other names seen in the wild for variants of this feature include *parameters* (not to be confused with function parameters), *special variables*, *fluid variables*, *fluid let*, and even the misnomer *"dynamic scoping"*.)

Like global variables, but better-behaved. Useful for sending some configuration parameters through several layers of function calls without changing their API. Best used sparingly.

There's a singleton, `dyn`:

```python
from unpythonic import dyn

def f():  # no "a" in lexical scope here
    assert dyn.a == 2

def g():
    with dyn.let(a=2, b="foo"):
        assert dyn.a == 2

        f()

        with dyn.let(a=3):  # dynamic assignments can be nested
            assert dyn.a == 3

        # now "a" has reverted to its previous value
        assert dyn.a == 2

    print(dyn.b)  # AttributeError, dyn.b no longer exists
g()
```

Dynamic variables are set using `with dyn.let(...)`. There is no `set`, `<<`, unlike in the other `unpythonic` environments.

**Changed in v0.14.2.** *To bring this in line with [SRFI-39](https://srfi.schemers.org/srfi-39/srfi-39.html), `dyn` now supports rebinding, using assignment syntax such as `dyn.x = 42`. For an atomic mass update, see `dyn.update`. Rebinding occurs in the closest enclosing dynamic environment that has the target name bound. If the name is not bound in any dynamic environment, ``AttributeError`` is raised.*

**CAUTION**: Use rebinding of dynamic variables carefully, if at all. Stealth updates of dynamic variables defined in an enclosing dynamic extent can destroy any chance of statically reasoning about the code.

The values of dynamic variables remain bound for the dynamic extent of the `with` block. Exiting the `with` block then pops the stack. Inner dynamic scopes shadow outer ones. Dynamic variables are seen also by code that is outside the lexical scope where the `with dyn.let` resides.

<details>
<summary>Each thread has its own dynamic scope stack. There is also a global dynamic scope for default values, shared between threads. </summary>
A newly spawned thread automatically copies the then-current state of the dynamic scope stack **from the main thread** (not the parent thread!). Any copied bindings will remain on the stack for the full dynamic extent of the new thread. Because these bindings are not associated with any `with` block running in that thread, and because aside from the initial copying, the dynamic scope stacks are thread-local, any copied bindings will never be popped, even if the main thread pops its own instances of them.

The source of the copy is always the main thread mainly because Python's `threading` module gives no tools to detect which thread spawned the current one. (If someone knows a simple solution, PRs welcome!)

Finally, there is one global dynamic scope shared between all threads, where the default values of dynvars live. The default value is used when ``dyn`` is queried for the value outside the dynamic extent of any ``with dyn.let()`` blocks. Having a default value is convenient for eliminating the need for ``if "x" in dyn`` checks, since the variable will always exist (after the global definition has been executed).
</details>

To create a dynvar and set its default value, use ``make_dynvar``. Each dynamic variable, of the same name, should only have one default set; the (dynamically) latest definition always overwrites. However, we do not prevent overwrites, because in some codebases the same module may run its top-level initialization code multiple times (e.g. if a module has a ``main()`` for tests, and the file gets loaded both as a module and as the main program).

See also the methods of ``dyn``; particularly noteworthy are ``asdict`` and ``items``, which give access to a live view to dyn's contents in a dictionary format (intended for reading only!). The ``asdict`` method essentially creates a ``collections.ChainMap`` instance, while ``items`` is an abbreviation for ``asdict().items()``. The ``dyn`` object itself can also be iterated over; this creates a ``ChainMap`` instance and redirects to iterate over it. ``dyn`` also provides the ``collections.abc.Mapping`` API.

To support dictionary-like idioms in iteration, dynvars can alternatively be accessed by subscripting; ``dyn["x"]`` has the same meaning as ``dyn.x``, so you can do things like:

```python
print(tuple((k, dyn[k]) for k in dyn))
```

Finally, ``dyn`` supports membership testing as ``"x" in dyn``, ``"y" not in dyn``, where the string is the name of the dynvar whose presence is being tested.

For some more details, see [the unit tests](../unpythonic/test/test_dynassign.py).

### Relation to similar features in Lisps

This is essentially [SRFI-39: Parameter objects](https://srfi.schemers.org/srfi-39/), using the MzScheme approach in the presence of multiple threads.

[Racket](http://racket-lang.org/)'s [`parameterize`](https://docs.racket-lang.org/guide/parameterize.html) behaves similarly. However, Racket seems to be the state of the art in many lispy language design related things, so its take on the feature may have some finer points I haven't thought of.

On Common Lisp's special variables, see [Practical Common Lisp by Peter Seibel](http://www.gigamonkeys.com/book/variables.html), especially footnote 10 in the linked chapter, for a definition of terms. Similarly, dynamic variables in our `dyn` have *indefinite scope* (because `dyn` is implemented as a module-level global, accessible from anywhere), but *dynamic extent*.

So what we have in `dyn` is almost exactly like Common Lisp's special variables, except we are missing convenience features such as `setf` and a smart `let` that auto-detects whether a variable is lexical or dynamic (if the name being bound is already in scope).

## Containers

We provide some additional containers.

The class names are lowercase, because these are intended as low-level utility classes in principle on par with the builtins. The immutable containers are hashable. All containers are pickleable (if their contents are).

### ``frozendict``: an immutable dictionary

Given the existence of ``dict`` and ``frozenset``, this one is oddly missing from the standard library.

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

All the usual read-access stuff works:

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

The abstract superclasses are virtual, just like for ``dict`` (i.e. they do not appear in the MRO).

Finally, ``frozendict`` obeys the empty-immutable-container singleton invariant:

```python
assert frozendict() is frozendict()
```

...but don't pickle the empty ``frozendict`` and expect this invariant to hold; it's freshly created in each session.


### `cons` and friends: pythonic lispy linked lists

*Laugh, it's funny.*

```python
from unpythonic import cons, nil, ll, llist, car, cdr, caar, cdar, cadr, cddr, \
                       member, lreverse, lappend, lzip, BinaryTreeIterator

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

Although linked lists are created with ``ll`` or ``llist``, the data type (for e.g. ``isinstance``) is ``cons``.

Iterators are supported to walk over linked lists (this also gives sequence unpacking support). When ``next()`` is called, we return the car of the current cell the iterator points to, and the iterator moves to point to the cons cell in the cdr, if any. When the cdr is not a cons cell, it is the next (and last) item returned; except if it `is nil`, then iteration ends without returning the `nil`.

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

(However, for example, it is possible to ``cons`` a new item onto an existing linked list; that's fine because it produces a new cons structure - which shares data with the original, just like in Racket.)

In general, copying cons structures can be error-prone. Given just a starting cell it is impossible to tell if a given instance of a cons structure represents a linked list, or something more general (such as a binary tree) that just happens to locally look like one, along the path that would be traversed if it was indeed a linked list.

The linked list iteration strategy does not recurse in the ``car`` half, which could lead to incomplete copying. The tree strategy that recurses on both halves, on the other hand, will flatten nested linked lists and produce also the final ``nil``.

We provide a ``JackOfAllTradesIterator`` as a compromise that understands both trees and linked lists. Nested lists will be flattened, and in a tree any ``nil`` in a ``cdr`` position will be omitted from the output. ``BinaryTreeIterator`` and ``JackOfAllTradesIterator`` use an explicit data stack instead of implicitly using the call stack for keeping track of the recursion. All ``cons`` iterators work for arbitrarily deep cons structures without causing Python's call stack to overflow, and without the need for TCO.

``cons`` has no ``collections.abc`` virtual superclasses (except the implicit ``Hashable`` since ``cons`` provides ``__hash__`` and ``__eq__``), because general cons structures do not fit into the contracts represented by membership in those classes. For example, size cannot be known without iterating, and depends on which iteration scheme is used (e.g. ``nil`` dropping, flattening); which scheme is appropriate depends on the content.

**Caution**: the ``nil`` singleton is freshly created in each session; newnil is not oldnil, so don't pickle a standalone ``nil``. The unpickler of ``cons`` automatically refreshes any ``nil`` instances inside a pickled cons structure, so that **cons structures** support the illusion that ``nil`` is a special value like ``None`` or ``...``. After unpickling, ``car(c) is nil`` and ``cdr(c) is nil`` still work as expected, even though ``id(nil)`` has changed between sessions.


### ``box``: a mutable single-item container

**Changed in v0.14.2.** *The `box` container now supports `.set(newvalue)` to rebind, returning the new value as a convenience. Syntactic sugar for rebinding is `b << newvalue`, where `b` is a `box`. The item inside the box can be extracted with `unbox(b)`.*

No doubt anyone programming in an imperative language has run into the situation caricatured by this highly artificial example:

```python
a = 23

def f(x):
    x = 17  # but I want to update the existing a!

f(a)
assert a == 23
```

Many solutions exist. Common pythonic ones are abusing a ``list`` to represent a box (and then trying to remember it is supposed to hold only a single item), or using the ``global`` or ``nonlocal`` keywords to tell Python, on assignment, to overwrite a name that already exists in a surrounding scope.

As an alternative to the rampant abuse of lists, we provide a rackety ``box``, which is a minimalistic mutable container that holds exactly one item. The data in the box is accessed via an attribute, so any code that has a reference to the box can update the data in it:

```python
from unpythonic import box

a = box(23)

def f(b):
    b.x = 17

f(a)
assert a == 17
```

The attribute name is just ``x`` to reduce the number of additional keystrokes required. The ``box`` API is summarized by:

```python
b1 = box(23)
b2 = box(23)
b3 = box(17)

assert b1.x == 23    # data lives in the attribute .x
assert unbox(b1) == 23  # but is usually accessed by unboxing
assert 23 in b1      # content is "in" the box, also syntactically
assert 17 not in b1

assert [x for x in b1] == [23]  # box is iterable
assert len(b1) == 1             # and always has length 1

assert b1 == 23      # for equality testing, a box is considered equal to its content
assert unbox(b1) == 23  # of course, can also unbox the content before testing

assert b2 == b1  # contents are equal, but
assert b2 is not b1  # different boxes

assert b3 != b1      # different contents

b2 << 42         # replacing the item in the box (rebinding the contents)
assert 42 in b2
assert 23 not in b2

b2.set(42)       # same without syntactic sugar
assert 42 in b2
```

The expression ``item in b`` has the same meaning as ``b.x == item``. Note ``box`` is a mutable container, so it is **not hashable**.

The expression `unbox(b)` has the same meaning as getting the attribute `b.x`, but additionally sanity checks that `b` is a `box`, and if not, raises `TypeError`.

The expressions `b.set(newitem)` and `b << newitem` have the same meaning as setting the attribute `b.x`, except that they also return the new value as a convenience.


### Container utilities

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

Keep in mind the only reason to ever need multiple expressions: *side effects.* (Assignment is a side effect, too; it modifies the environment. In functional style, intermediate named definitions to increase readability are perhaps the most useful kind of side effect.)

See also ``multilambda`` in [macros](../macro_extras/).


### ``begin``: sequence side effects

**CAUTION**: the `begin` family of forms are provided **for use in pure-Python projects only** (and are a permanent part of the `unpythonic` API for that purpose). If your project uses macros, prefer the `do[]` and `do0[]` macros; these are the only sequencing constructs understood by other macros in `unpythonic.syntax` that need to perform tail-position analysis (e.g. `tco`, `autoreturn`, `continuations`). The `do[]` and `do0[]` macros also provide some convenience features, such as expression-local variables.

```python
from unpythonic import begin, begin0

f1 = lambda x: begin(print("cheeky side effect"),
                     42*x)
f1(2)  # --> 84

f2 = lambda x: begin0(42*x,
                      print("cheeky side effect"))
f2(2)  # --> 84
```

Actually a tuple in disguise. If worried about memory consumption, use `lazy_begin` and `lazy_begin0` instead, which indeed use loops. The price is the need for a lambda wrapper for each expression to delay evaluation, see [`unpythonic.seq`](../unpythonic/seq.py) for details.


### ``do``: stuff imperative code into an expression

**NOTE**: This is primarily a code generation target API for the ``do[]`` [macro](../macro_extras/), which makes the construct easier to use. Below is the documentation for the raw API.

No monadic magic. Basically, ``do`` is:

  - An improved ``begin`` that can bind names to intermediate results and then use them in later items.

  - A ``let*`` (technically, ``letrec``) where making a binding is optional, so that some items can have only side effects if so desired. No semantically distinct ``body``; all items play the same role.

Like in ``letrec`` (see below), use ``lambda e: ...`` to access the environment, and to wrap callable values (to prevent misunderstandings).

```python
from unpythonic import do, assign

y = do(assign(x=17),          # create and set e.x
       lambda e: print(e.x),  # 17; uses environment, needs lambda e: ...
       assign(x=23),          # overwrite e.x
       lambda e: print(e.x),  # 23
       42)                    # return value
assert y == 42

y = do(assign(x=17),
       assign(z=lambda e: 2*e.x),
       lambda e: e.z)
assert y == 34

y = do(assign(x=5),
       assign(f=lambda e: lambda x: x**2),  # callable, needs lambda e: ...
       print("hello from 'do'"),  # value is None; not callable
       lambda e: e.f(e.x))
assert y == 25
```

If you need to return the first value instead of the last one, use this trick:

```python
y = do(assign(result=17),
       print("assigned 'result' in env"),
       lambda e: e.result)  # return value
assert y == 17
```

Or use ``do0``, which does it for you:

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

Beware of this pitfall:

```python
do(lambda e: print("hello 2 from 'do'"),  # delayed because lambda e: ...
   print("hello 1 from 'do'"),  # Python prints immediately before do()
   "foo")                       # gets control, because technically, it is
                                # **the return value** that is an argument
                                # for do().
```

Unlike ``begin`` (and ``begin0``), there is no separate ``lazy_do`` (``lazy_do0``), because using a ``lambda e: ...`` wrapper will already delay evaluation of an item. If you want a lazy variant, just wrap each item (also those which don't otherwise need it).

The above pitfall also applies to using escape continuations inside a ``do``. To do that, wrap the ec call into a ``lambda e: ...`` to delay its evaluation until the ``do`` actually runs:

```python
call_ec(
  lambda ec:
    do(assign(x=42),
       lambda e: ec(e.x),                  # IMPORTANT: must delay this!
       lambda e: print("never reached")))  # and this (as above)
```

This way, any assignments made in the ``do`` (which occur only after ``do`` gets control), performed above the line with the ``ec`` call, will have been performed when the ``ec`` is called.


### ``pipe``, ``piped``, ``lazy_piped``: sequence functions

Similar to Racket's [threading macros](https://docs.racket-lang.org/threading/). A pipe performs a sequence of operations, starting from an initial value, and then returns the final value. It's just function composition, but with an emphasis on data flow, which helps improve readability:

```python
from unpythonic import pipe

double = lambda x: 2 * x
inc    = lambda x: x + 1

x = pipe(42, double, inc)
assert x == 85
```

We also provide ``pipec``, which curries the functions before applying them. Useful with passthrough (see below on ``curry``).

Optional **shell-like syntax**, with purely functional updates:

```python
from unpythonic import piped, getvalue

x = piped(42) | double | inc | getvalue
assert x == 85

p = piped(42) | double
assert p | inc | getvalue == 85
assert p | getvalue == 84  # p itself is never modified by the pipe system
```

Set up a pipe by calling ``piped`` for the initial value. Pipe into the sentinel ``getvalue`` to exit the pipe and return the current value.

**Lazy pipes**, useful for mutable initial values. To perform the planned computation, pipe into the sentinel ``runpipe``:

```python
from unpythonic import lazy_piped1, runpipe

lst = [1]
def append_succ(l):
    l.append(l[-1] + 1)
    return l  # this return value is handed to the next function in the pipe
p = lazy_piped1(lst) | append_succ | append_succ  # plan a computation
assert lst == [1]        # nothing done yet
p | runpipe              # run the computation
assert lst == [1, 2, 3]  # now the side effect has updated lst.
```

Lazy pipe as an unfold:

```python
from unpythonic import lazy_piped, runpipe

fibos = []
def nextfibo(a, b):      # multiple arguments allowed
    fibos.append(a)      # store result by side effect
    return (b, a + b)    # new state, handed to next function in the pipe
p = lazy_piped(1, 1)     # load initial state
for _ in range(10):      # set up pipeline
    p = p | nextfibo
p | runpipe
assert fibos == [1, 1, 2, 3, 5, 8, 13, 21, 34, 55]
```

Both one-in-one-out (*1-to-1*) and n-in-m-out (*n-to-m*) pipes are provided. The 1-to-1 versions have names suffixed with ``1``. The use case is one-argument functions that return one value (which may also be a tuple).

In the n-to-m versions, when a function returns a tuple, it is unpacked to the argument list of the next function in the pipe. At ``getvalue`` or ``runpipe`` time, the tuple wrapper (if any) around the final result is discarded if it contains only one item. (This allows the n-to-m versions to work also with a single value, as long as it is not a tuple.) The main use case is computations that deal with multiple values, the number of which may also change during the computation (as long as there are as many "slots" on both sides of each individual connection).


## Batteries

Things missing from the standard library.

### Batteries for functools

 - `memoize`:
   - Caches also exceptions à la Racket. If the memoized function is called again with arguments with which it raised an exception the first time, the same exception instance is raised again.
   - Works also on instance methods, with results cached separately for each instance.
     - This is essentially because ``self`` is an argument, and custom classes have a default ``__hash__``.
     - Hence it doesn't matter that the memo lives in the ``memoized`` closure on the class object (type), where the method is, and not directly on the instances. The memo itself is shared between instances, but calls with a different value of ``self`` will create unique entries in it.
     - For a solution that performs memoization at the instance level, see [this ActiveState recipe](https://github.com/ActiveState/code/tree/master/recipes/Python/577452_memoize_decorator_instance) (and to demystify the magic contained therein, be sure you understand [descriptors](https://docs.python.org/3/howto/descriptor.html)).
 - `curry`, with some extra features:
   - Passthrough on the right when too many args (à la Haskell; or [spicy](https://github.com/Technologicat/spicy) for Racket)
     - If the intermediate result of a passthrough is callable, it is (curried and) invoked on the remaining positional args. This helps with some instances of [point-free style](https://en.wikipedia.org/wiki/Tacit_programming).
     - For simplicity, all remaining keyword args are fed in at the first step that has too many positional args.
     - If more positional args are still remaining when the top-level curry context exits, by default ``TypeError`` is raised.
     - To override, set the dynvar ``curry_context``. It is a list representing the stack of currently active curry contexts. A context is any object, a human-readable label is fine. See below for an example.
       - To set the dynvar, `from unpythonic import dyn`, and then `with dyn.let(curry_context=...):`.
   - Can be used both as a decorator and as a regular function.
     - As a regular function, `curry` itself is curried à la Racket. If it gets extra arguments (beside the function ``f``), they are the first step. This helps eliminate many parentheses.
   - **Caution**: If the positional arities of ``f`` cannot be inspected, currying fails, raising ``UnknownArity``. This may happen with builtins such as ``list.append``.
 - `composel`, `composer`: both left-to-right and right-to-left function composition, to help readability.
   - Any number of positional arguments is supported, with the same rules as in the pipe system. Multiple return values packed into a tuple are unpacked to the argument list of the next function in the chain.
   - `composelc`, `composerc`: curry each function before composing them. Useful with passthrough.
     - An implicit top-level curry context is inserted around all the functions except the one that is applied last.
   - `composel1`, `composer1`: 1-in-1-out chains (faster; also useful for a single value that is a tuple).
   - suffix `i` to use with an iterable that contains the functions (`composeli`, `composeri`, `composelci`, `composerci`, `composel1i`, `composer1i`)
 - `withself`: essentially, the Y combinator trick as a decorator. Allows a lambda to refer to itself.
   - The ``self`` argument is declared explicitly, but passed implicitly (as the first positional argument), just like the ``self`` argument of a method.
 - `apply`: the lispy approach to starargs. Mainly useful with the ``prefix`` [macro](../macro_extras/).
 - `andf`, `orf`, `notf`: compose predicates (like Racket's `conjoin`, `disjoin`, `negate`).
 - `flip`: reverse the order of positional arguments.
 - `rotate`: a cousin of `flip`. Permute the order of positional arguments in a cycle.
 - `to1st`, `to2nd`, `tokth`, `tolast`, `to` to help inserting 1-in-1-out functions into m-in-n-out compose chains. (Currying can eliminate the need for these.)
 - `identity`, `const` which sometimes come in handy when programming with higher-order functions.
 - `fix`: detect and break infinite recursion cycles. **Added in v0.14.2.**

Examples (see also the next section):

```python
from operator import add, mul
from typing import NoReturn
from unpythonic import andf, orf, flatmap, rotate, curry, dyn, zipr, rzip, \
                       foldl, foldr, composer, to1st, cons, nil, ll, withself, \
                       fix

# detect and break infinite recursion cycles:
# a(0) -> b(1) -> a(2) -> b(0) -> a(1) -> b(2) -> a(0) -> ...
@fix()
def a(k):
    return b((k + 1) % 3)
@fix()
def b(k):
    return a((k + 1) % 3)
assert a(0) is NoReturn  # the call does return, saying the original function wouldn't.

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

# curry with passthrough on the right
# final result is a tuple of the result(s) and the leftover args
double = lambda x: 2 * x
with dyn.let(curry_context=["whatever"]):  # set a context to allow passthrough to the top level
    assert curry(double, 2, "foo") == (4, "foo")   # arity of double is 1

mysum = curry(foldl, add, 0)
myprod = curry(foldl, mul, 1)
a = ll(1, 2)
b = ll(3, 4)
c = ll(5, 6)
append_two = lambda a, b: foldr(cons, b, a)
append_many = lambda *lsts: foldr(append_two, nil, lsts)  # see unpythonic.lappend
assert mysum(append_many(a, b, c)) == 21
assert myprod(b) == 12

map_one = lambda f: curry(foldr, composer(cons, to1st(f)), nil)
doubler = map_one(double)
assert doubler((1, 2, 3)) == ll(2, 4, 6)

assert curry(map_one, double, ll(1, 2, 3)) == ll(2, 4, 6)
```

*Minor detail*: We could also write the last example as:

```python
double = lambda x: 2 * x
rmap_one = lambda f: curry(foldl, composer(cons, to1st(f)), nil)  # essentially reversed(map(...))
map_one = lambda f: composer(rmap_one(f), lreverse)
assert curry(map_one, double, ll(1, 2, 3)) == ll(2, 4, 6)
```

which may be a useful pattern for lengthy iterables that could overflow the call stack (although not in ``foldr``, since our implementation uses a linear process).

In ``rmap_one``, we can use either ``curry`` or ``functools.partial``. In this case it doesn't matter which, since we want just one partial application anyway. We provide two arguments, and the minimum arity of ``foldl`` is 3, so ``curry`` will trigger the call as soon as (and only as soon as) it gets at least one more argument.

The final ``curry`` uses both of the extra features. It invokes passthrough, since ``map_one`` has arity 1. It also invokes a call to the callable returned from ``map_one``, with the remaining arguments (in this case just one, the ``ll(1, 2, 3)``).

Yet another way to write ``map_one`` is:

```python
mymap = lambda f: curry(foldr, composer(cons, curry(f)), nil)
```

The curried ``f`` uses up one argument (provided it is a one-argument function!), and the second argument is passed through on the right; this two-tuple then ends up as the arguments to ``cons``.

Using a currying compose function (name suffixed with ``c``), the inner curry can be dropped:

```python
mymap = lambda f: curry(foldr, composerc(cons, f), nil)
myadd = lambda a, b: a + b
assert curry(mymap, myadd, ll(1, 2, 3), ll(2, 4, 6)) == ll(3, 6, 9)
```

This is as close to ```(define (map f) (foldr (compose cons f) empty)``` (in ``#lang`` [``spicy``](https://github.com/Technologicat/spicy)) as we're gonna get in Python.

Notice how the last two versions accept multiple input iterables; this is thanks to currying ``f`` inside the composition. An element from each of the iterables is taken by the processing function ``f``. Being the last argument, ``acc`` is passed through on the right. The output from the processing function - one new item - and ``acc`` then become a two-tuple, passed into cons.

Finally, keep in mind this exercise is intended as a feature demonstration. In production code, the builtin ``map`` is much better.


#### ``curry`` and reduction rules

The provided variant of ``curry``, beside what it says on the tin, is effectively an explicit local modifier to Python's reduction rules, which allows some Haskell-like idioms. When we say:

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

In the above example:

```python
curry(mapl_one, double, ll(1, 2, 3))
```

the callable ``mapl_one`` takes one argument, which is a function. It yields another function, let us call it ``g``. We are left with:

```python
curry(g, ll(1, 2, 3))
```

The argument is then passed into ``g``; we obtain a result, and reduction is complete.

A curried function is also a curry context:

```python
add2 = lambda x, y: x + y
a2 = curry(add2)
a2(a, b, c)  # same as curry(add2, a, b, c); reduces to (a + b, c)
```

so on the last line, we don't need to say

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

**Note**: to code in curried style, a [contract system](https://github.com/AndreaCensi/contracts) or a [static type checker](http://mypy-lang.org/) is useful; also, be careful with variadic functions.


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

**CAUTION**: If we have a function `g(a, b)`, the argument lists of the invocations `g(1, 2)` and `g(a=1, b=2)` are seen as different. This is because the decorator must internally accept `(*args, **kwargs)` to pass everything through, and in the first case the arguments end up in `args`, whereas in the second they end up in `kwargs` - even though as far as `g` itself sees it, both calls result in the same bindings being established. See [issue #26](https://github.com/Technologicat/unpythonic/issues/26) (and please post an idea if you have one). This is a Python gotcha that was originally noticed by the author of the `wrapt` library, and mentioned in [its documentation](https://wrapt.readthedocs.io/en/latest/decorators.html#processing-function-arguments).

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

  - `bottom` can be a callable, in which case the function name and args at the point where the cycle was detected are passed to it, and its return value becomes the final return value.

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
   - `window`: sliding length-n window iterator for general iterables. Acts like the well-known [n-gram zip trick](http://www.locallyoptimal.com/blog/2013/01/20/elegant-n-gram-generation-in-python/), but the input can be any iterable.
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
 - *math-related*:
   - `fixpoint`: arithmetic fixed-point finder (not to be confused with `fix`). **Added in v0.14.2.**
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

Examples:

```python
from functools import partial
from unpythonic import scanl, scanr, foldl, foldr, flatmap, mapr, zipr, \
                       uniqify, uniq, flatten1, flatten, flatten_in, take, drop, \
                       unfold, unfold1, cons, nil, ll, curry, s, inn, iindex, window

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

# iindex: find index of item in iterable (mostly only makes sense for memoized input)
assert iindex(2, (1, 2, 3)) == 1
assert iindex(31337, primes()) == 3378

# window: length-n sliding window iterator for general iterables
lst = (x for x in range(5))
out = []
for a, b, c in window(lst, n=3):
    out.append((a, b, c))
assert out == [(0, 1, 2), (1, 2, 3), (2, 3, 4)]

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

  - The ``box`` container from ``unpythonic.collections``; although mutable, its update is not conveniently expressible by the ``collections.abc`` APIs.

  - The ``cons`` container from ``unpythonic.llist`` (including the ``ll``, ``llist`` linked lists). This is treated with the general tree strategy, so nested linked lists will be flattened, and the final ``nil`` is also processed.

    Note that since ``cons`` is immutable, anyway, if you know you have a long linked list where you need to update the values, just iterate over it and produce a new copy - that will work as intended.


### ``s``, ``m``, ``mg``: lazy mathematical sequences with infix arithmetic

We provide a compact syntax to create lazy constant, arithmetic, geometric and power sequences: ``s(...)``. Numeric (``int``, ``float``, ``mpmath``) and symbolic (SymPy) formats are supported. We avoid accumulating roundoff error when used with floating-point formats.

We also provide arithmetic operation support for iterables (termwise). To make any iterable infix math aware, use ``m(iterable)``. The arithmetic is lazy; it just plans computations, returning a new lazy mathematical sequence. To extract values, iterate over the result. (Note this implies that expressions consisting of thousands of operations will overflow Python's call stack. In practice this shouldn't be a problem.)

The function versions of the arithmetic operations (also provided, à la the ``operator`` module) have an **s** prefix (short for mathematical **sequence**), because in Python the **i** prefix (which could stand for *iterable*) is already used to denote the in-place operators.

We provide the [Cauchy product](https://en.wikipedia.org/wiki/Cauchy_product), and its generalization, the diagonal combination-reduction, for two (possibly infinite) iterables. Note ``cauchyprod`` **does not sum the series**; given the input sequences ``a`` and ``b``, the call ``cauchyprod(a, b)`` computes the elements of the output sequence ``c``.

We also provide ``mg``, a decorator to mathify a gfunc, so that it will ``m()`` the generator instances it makes. Combo with ``imemoize`` for great justice, e.g. ``a = mg(imemoize(s(1, 2, ...)))``.

Finally, we provide ready-made generators that yield some common sequences (currently, the Fibonacci numbers and the prime numbers). The prime generator is an FP-ized sieve of Eratosthenes.

```python
from unpythonic import s, m, cauchyprod, take, last, fibonacci, primes

assert tuple(take(10, s(1, ...))) == (1,)*10
assert tuple(take(10, s(1, 2, ...))) == tuple(range(1, 11))
assert tuple(take(10, s(1, 2, 4, ...))) == (1, 2, 4, 8, 16, 32, 64, 128, 256, 512)
assert tuple(take(5, s(2, 4, 16, ...))) == (2, 4, 16, 256, 65536)  # 2, 2**2, (2**2)**2, ...

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
```

A math iterable (i.e. one that has infix math support) is an instance of the class ``m``:

```python
a = s(1, 3, ...)
b = s(2, 4, ...)
c = a + b
assert isinstance(a, m)
assert isinstance(b, m)
assert isinstance(c, m)
assert tuple(take(5, c)) == (3, 7, 11, 15, 19)

d = 1 / (a + b)
assert isinstance(d, m)
```

Applying an operation meant for regular (non-math) iterables will drop the arithmetic support, but it can be restored by m'ing manually:

```python
e = take(5, c)
assert not isinstance(e, m)

f = m(take(5, c))
assert isinstance(f, m)
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
        print("Hello, {}!".format(s))
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
    return loop(acc + ("{:d}{:s}".format(numb, lett),))
assert p == ('1a', '2b', '3c')

@looped_over(enumerate(zip((1, 2, 3), ('a', 'b', 'c'))), acc=())
def q(loop, item, acc):
    idx, (numb, lett) = item
    return loop(acc + ("Item {:d}: {:d}{:s}".format(idx, numb, lett),))
assert q == ('Item 0: 1a', 'Item 1: 2b', 'Item 2: 3c')
```

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
    acc.append("{:d}{:s}".format(numb, lett))
    return loop(acc)
assert p == ['1a', '2b', '3c']
```

Linked list:

```python
from unpythonic import cons, nil, ll

@lreverse
@looped_over(zip((1, 2, 3), ('a', 'b', 'c')), acc=nil)
def p(loop, item, acc):
    numb, lett = item
    return loop(cons("{:d}{:s}".format(numb, lett), acc))
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
    return loop(cons("{:d}{:s}".format(numb, lett), acc))
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


### ``setescape``, ``escape``: escape continuations (ec)

This feature is known as `catch`/`throw` in several Lisps, e.g. in Emacs Lisp and in Common Lisp (as well as some of its ancestors). This terminology is independent of the use of `throw`/`catch` in C++/Java for the exception handling mechanism. Common Lisp also provides a lexically scoped variant (`BLOCK`/`RETURN-FROM`) that is more idiomatic [according to Seibel](http://www.gigamonkeys.com/book/the-special-operators.html).

Escape continuations can be used as a *multi-return*:

```python
from unpythonic import setescape, escape

@setescape()  # note the parentheses
def f():
    def g():
        escape("hello from g")  # the argument becomes the return value of f()
        print("not reached")
    g()
    print("not reached either")
assert f() == "hello from g"
```

**CAUTION**: The implementation is based on exceptions, so catch-all ``except:`` statements will intercept also escapes, breaking the escape mechanism. As you already know, be specific in what you catch!

In Lisp terms, `@setescape` essentially captures the escape continuation (ec) of the function decorated with it. The nearest (dynamically) surrounding ec can then be invoked by `escape(value)`. The function decorated with `@setescape` immediately terminates, returning ``value``.

In Python terms, an escape means just raising a specific type of exception; the usual rules concerning ``try/except/else/finally`` and ``with`` blocks apply. It is a function call, so it works also in lambdas.

Escaping the function surrounding an FP loop, from inside the loop:

```python
@setescape()
def f():
    @looped
    def s(loop, acc=0, i=0):
        if i > 5:
            escape(acc)
        return loop(acc + i, i + 1)
    print("never reached")
f()  # --> 15
```

For more control, both ``@setescape`` points and escape instances can be tagged:

```python
@setescape(tags="foo")  # setescape point tags can be single value or tuple (tuples OR'd, like isinstance())
def foo():
    @call
    @setescape(tags="bar")
    def bar():
        @looped
        def s(loop, acc=0, i=0):
            if i > 5:
                escape(acc, tag="foo")  # escape instance tag must be a single value
            return loop(acc + i, i + 1)
        print("never reached")
        return False
    print("never reached either")
    return False
assert foo() == 15
```

For details on tagging, especially how untagged and tagged escapes and points interact, and how to make one-to-one connections, see the docstring for ``@setescape``.


#### ``call_ec``: first-class escape continuations

We provide ``call/ec`` (a.k.a. ``call-with-escape-continuation``), in Python spelled as ``call_ec``. It's a decorator that, like ``@call``, immediately runs the function and replaces the def'd name with the return value. The twist is that it internally sets up an escape point, and hands a **first-class escape continuation** to the callee.

The function to be decorated **must** take one positional argument, the ec instance.

The ec instance itself is another function, which takes one positional argument: the value to send to the escape point. The ec instance and the escape point are connected one-to-one. No other ``@setescape`` point will catch the ec instance, and the escape point catches only this particular ec instance and nothing else.

Any particular ec instance is only valid inside the dynamic extent of the ``call_ec`` invocation that created it. Attempting to call the ec later raises ``RuntimeError``.

This builds on ``@setescape`` and ``escape``, so the caution about catch-all ``except:`` statements applies here, too.

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

We provide a simple variant of nondeterministic evaluation. This is essentially a toy that has no more power than list comprehensions or nested for loops. See also the easy-to-use [macro](../macro_extras/) version with natural syntax and a clean implementation.

An important feature of McCarthy's [`amb` operator](https://rosettacode.org/wiki/Amb) is its nonlocality - being able to jump back to a choice point, even after the dynamic extent of the function where that choice point resides. If that sounds a lot like ``call/cc``, that's because that's how ``amb`` is usually implemented. See examples [in Ruby](http://www.randomhacks.net/2005/10/11/amb-operator/) and [in Racket](http://www.cs.toronto.edu/~david/courses/csc324_w15/extra/choice.html).

Python can't do that, short of transforming the whole program into [CPS](https://en.wikipedia.org/wiki/Continuation-passing_style), while applying TCO everywhere to prevent stack overflow. **If that's what you want**, see ``continuations`` in [the macros](../macro_extras/).

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


## Other

Stuff that didn't fit elsewhere.

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

(But see ``@setescape``, ``escape``, and ``call_ec``.)

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

If you have MacroPy, this combines nicely with ``quick_lambda``:

```python
from macropy.quick_lambda import macros, f, _
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


### ``raisef``: ``raise`` as a function

Raise an exception from an expression position:

```python
from unpythonic import raisef

f = lambda x: raisef(RuntimeError, "I'm in ur lambda raising exceptions")
```


### ``pack``: multi-arg constructor for tuple

The default ``tuple`` constructor accepts a single iterable. But sometimes one needs to pass in the elements separately. Most often a literal tuple such as ``(1, 2, 3)`` is then the right solution, but there are situations that do not admit a literal tuple. Enter ``pack``:

```python
from unpythonic import pack

myzip = lambda lol: map(pack, *lol)
lol = ((1, 2), (3, 4), (5, 6))
assert tuple(myzip(lol)) == ((1, 3, 5), (2, 4, 6))
```


### ``namelambda``, rename a function

For those situations where you return a lambda as a closure, call it much later, and it happens to crash - so you can tell from the stack trace *which* of the *N* lambdas in the codebase it is. The return value is a modified copy; the original function object is not mutated. You can rename any function object (``isinstance(f, (types.LambdaType, types.FunctionType))``), and it will rename a lambda even if it has already been named.

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


### ``arities``, ``kwargs``: Function signature inspection utilities

Convenience functions providing an easy-to-use API for inspecting a function's signature. The heavy lifting is done by ``inspect``.

Methods on objects and classes are treated specially, so that the reported arity matches what the programmer actually needs to supply when calling the method (i.e., implicit ``self`` and ``cls`` are ignored).

```python
from unpythonic import arities, arity_includes, UnknownArity, \
                       kwargs, required_kwargs, optional_kwargs,

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
```

We special-case the builtin functions that either fail to return any arity (are uninspectable) or report incorrect arity information, so that also their arities are reported correctly. Note we **do not** special-case the *methods* of any builtin classes, so e.g. ``list.append`` remains uninspectable. This limitation might or might not be lifted in a future version.

If the arity cannot be inspected, and the function is not one of the special-cased builtins, the ``UnknownArity`` exception is raised.

These functions are internally used in various places in unpythonic, particularly ``curry``. The ``let`` and FP looping constructs also use these to emit a meaningful error message if the signature of user-provided function does not match what is expected.

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
for a, b in window(Popper(inp)):
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


### ``ulp``: unit in last place

**Added in v0.14.2.**

Given a floating point number `x`, return the value of the *unit in the last place* (the "least significant bit"). This is the local size of a "tick", i.e. the difference between `x` and the next larger float. At `x = 1.0`, this is the [machine epsilon](https://en.wikipedia.org/wiki/Machine_epsilon), by definition of the machine epsilon.

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

For more reading, see [David Goldberg (1991): What every computer scientist should know about floating-point arithmetic](https://docs.oracle.com/cd/E19957-01/806-3568/ncg_goldberg.html), or for a [tl;dr](http://catplanet.org/tldr-cat-meme/) version, [the floating point guide](https://floating-point-gui.de/).
