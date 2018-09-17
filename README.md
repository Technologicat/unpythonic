# Unpythonic: Lispy missing batteries for Python

Python clearly wants to be an impure-FP language. A decorator with arguments *is a curried closure* - how much more FP can you get?

In the spirit of [toolz](https://github.com/pytoolz/toolz), we provide missing features for Python from the list processing tradition. We place a special emphasis on **clear, pythonic syntax**, as far as possible without [MacroPy](https://github.com/azazel75/macropy).

Other design considerations are simplicity, robustness, and minimal dependencies (currently none). Pure Python 3.4.

**Contents**:

 - [Assign-once](#assign-once)
 - [Multi-expression lambdas](#multi-expression-lambdas)
   - [Sequence side effects: ``begin``](#sequence-side-effects-begin)
   - [Stuff imperative code into a lambda: ``do``](#stuff-imperative-code-into-a-lambda-do)
   - [Sequence functions: ``pipe``, ``piped``, ``lazy_piped``](#sequence-functions-pipe-piped-lazy_piped)
 - [Introduce local bindings: ``let``, ``letrec``](#introduce-local-bindings-let-letrec)
   - [The environment: ``env``](#the-environment-env)
 - [Tail call optimization (TCO) / explicit continuations](#tail-call-optimization-tco--explicit-continuations)
   - [Loops in FP style (with TCO)](#loops-in-fp-style-with-tco): FP looping constructs.
 - [Escape continuations (ec)](#escape-continuations-ec)
   - [First-class escape continuations: ``call/ec``](#first-class-escape-continuations-callec)
 - [Dynamic scoping](#dynamic-scoping) (a.k.a. parameterize, special variables, dynamic assignment)
 - [Batteries for functools](#batteries-for-functools): `memoize`, `curry`, `compose`
   - [``curry`` and reduction rules](#curry-and-reduction-rules): we provide some extra features for bonus haskellness.
 - [Batteries for itertools](#batteries-for-itertools): Racket-style multi-input `foldl`, `foldr`; uniqification, flattening
 - [Functional update, sequence shadowing](#functional-update-sequence-shadowing): like ``collections.ChainMap``, but for sequences
 - [Nondeterministic evaluation](#nondeterministic-evaluation): `forall`, a tuple comprehension with multiple body expressions
 - [`cons` and friends](#cons-and-friends): pythonic lispy linked lists
 - [``def`` as a code block: ``@call``](#def-as-a-code-block-call): run a block of code immediately, in a new lexical scope

Meta:

 - [Design notes](#design-notes)
 - [Installation](#installation)
 - [License](#license)
 - [Acknowledgements](#acknowledgements)
 - [Python-related FP resources](#python-related-fp-resources)

There is a [quick tour](quick_tour.py) and a slightly longer [tour](tour.py), but as of v0.8.2 neither are complete. For the most up-to-date examples, see the `test()` function in each submodule, the docstrings of the individual features, and this README.

### Assign-once

In Scheme terms, make `define` and `set!` look different:

```python
from unpythonic import assignonce

with assignonce() as e:
    e.foo = "bar"           # new definition, ok
    e.set("foo", "tavern")  # explicitly rebind e.foo, ok
    e << ("foo", "tavern")  # same thing (but return e instead of new value, suitable for chaining)
    e.foo = "quux"          # AttributeError, e.foo already defined.
```

It's a subclass of ``env``, so it shares most of the same [features](#the-environment-env) and allows similar usage.


### Multi-expression lambdas

Keep in mind the only reason to ever need multiple expressions: *side effects.*

(Assignment is a side effect, too; it modifies the environment. In functional style, intermediate named definitions to increase readability are the most useful kind of side effect.)

#### Sequence side effects: ``begin``

```python
from unpythonic import begin, begin0

f1 = lambda x: begin(print("cheeky side effect"),
                     42*x)
f1(2)  # --> 84

f2 = lambda x: begin0(42*x,
                      print("cheeky side effect"))
f2(2)  # --> 84
```

Actually a tuple in disguise. If worried about memory consumption, use `lazy_begin` and `lazy_begin0` instead, which indeed use loops. The price is the need for a lambda wrapper for each expression to delay evaluation, see [`tour.py`](tour.py) for details.

#### Stuff imperative code into a lambda: ``do``

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


#### Sequence functions: ``pipe``, ``piped``, ``lazy_piped``

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

Both one-in-one-out (*1-to-1*) and n-in-m-out (*n-to-m*) pipes are provided. The 1-to-1 versions have names suffixed with ``1``. The use case is one-argument functions that return one value (which may also be a tuple or list).

In the n-to-m versions, when a function returns a tuple or list, it is unpacked to the argument list of the next function in the pipe. At ``getvalue`` or ``runpipe`` time, the tuple wrapper (if any) around the final result is discarded if it contains only one item. (This allows the n-to-m versions to work also with a single value, as long as it is not a tuple or list.) The main use case is computations that deal with multiple values, the number of which may also change during the computation (as long as there are as many "slots" on both sides of each individual connection).


### Introduce local bindings: ``let``, ``letrec``

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

Generally speaking, `body` is a one-argument function, which takes in the environment instance as the first positional parameter (usually named `env` or `e` for readability). In typical inline usage, `body` is `lambda e: expr`.

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

#### Lispylet

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


### The environment: ``env``

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


### Tail call optimization (TCO) / explicit continuations

Express algorithms elegantly without blowing the call stack - with explicit, clear syntax.

*Tail recursion*:

```python
from unpythonic import trampolined, jump, SELF

@trampolined
def fact(n, acc=1):
    if n == 0:
        return acc
    else:
        return jump(fact, n - 1, n * acc)
print(fact(4))  # 24
```

**CAUTION**: The default implementation is based on exceptions, so catch-all ``except:`` statements will intercept also jumps, breaking the looping mechanism. As you already know, be specific in what you catch! (**See also** ``fasttco`` below for an alternative that **doesn't** use exceptions.)

Functions that use TCO **must** be `@trampolined`. Calling a trampolined function normally starts the trampoline.

Inside a trampolined function, a normal call `f(a, ..., kw=v, ...)` remains a normal call. A tail call with target `f` is denoted `jump(f, a, ..., kw=v, ...)`.

Optionally, **to make it work also with fasttco**, explained below, a tail call **can** be denoted also `return jump(f, a, ..., kw=v, ...)` (adding a ``return``). In the examples here, we will use this optional syntax to keep the examples compatible with both implementations, and also to explicitly mark that these are indeed tail calls (due to the explicit ``return``).

The final result is just returned normally. This shuts down the trampoline, and returns the given value from the initial call (to a ``@trampolined`` function) that originally started that trampoline.

*Tail recursion in a lambda*:

```python
t = trampolined(lambda n, acc=1:
                    acc if n == 0 else jump(SELF, n - 1, n * acc))
print(t(4))  # 24
```

To denote tail recursion in an anonymous function, use the special jump target `SELF` (all uppercase!). Here it's just `jump` instead of `return jump` also with `fasttco`, since lambda does not use the `return` syntax.

Technically, `SELF` means *keep current jump target*, so the function that was last explicitly tail-called by name in that particular trampoline remains as the target of the jump. When the trampoline starts, the current target is set to the initial entry point (also for lambdas).

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


#### Fasttco

If you think you know what you're doing, ``fasttco`` is **the recommended implementation**.

The default TCO implementation uses exceptions. A do-nothing loop that trampolines with [``tco.py``](unpythonic/tco.py) runs 150-200× slower than the built-in ``for``.

To improve performance by a factor of approximately 2-5× (i.e. to become only 40-80× slower than ``for``), we provide an alternative TCO implementation, which is faster, but pickier about its syntax.

To enable it:

```python
import unpythonic
unpythonic.enable_fasttco()
```

This redirects `unpythonic.tco` to actually point to [`fasttco.py`](unpythonic/fasttco.py), reloads `unpythonic.fploop` using `fasttco`, and resets `unpythonic.trampolined`, `unpythonic.jump` and `unpythonic.SELF` to point to those in `fasttco`. Short demonstration:

```python
import unpythonic
unpythonic.fploop.test()  # using default TCO
unpythonic.enable_fasttco()
unpythonic.fploop.test()  # using fast TCO
```

**CAUTION**: if you from-imported names from `unpythonic.tco` (also implicitly, e.g. by `from unpythonic import *`), this **will not** update your local references, since it cannot have access to your namespace. To update your local references, just from-import the names again. This works because the names *inside the unpythonic module* are refreshed by ``enable_fasttco()``. Or just import them only after calling `enable_fasttco()` in the first place.

In summary, do something like:

```python
import unpythonic
unpythonic.enable_fasttco()
from unpythonic import *  # do any from-imports **after** enable_fasttco() to get correct local references
```

to use ``unpythonic`` with ``fasttco`` enabled. Having the correct references everywhere is important, because the TCO implementations **cannot be mixed and matched**.

In `fasttco`, unlike in the default implementation, `jump` is **a noun, not a verb**. The `jump(f, ...)` part just evaluates to a `jump` instance, which on its own does nothing. Returning it to the trampoline actually performs the tail call; hence `fasttco` **requires** the syntax `return jump(f, ...)`. **This propagates to fploop**; i.e. ``loop`` also becomes a **noun**, because it is essentially a fancy wrapper on top of ``jump``.

With `fasttco`, trying to ``jump(...)`` without the ``return`` does nothing useful, and will **usually** print a warning. It does this by checking a flag in the ``__del__`` method of ``jump``; any correctly used jump instance should have been claimed by a trampoline before it gets garbage-collected.

Using `fasttco` introduces the serious usability trap of forgetting the ``return`` (hence it's not the default implementation), but in exchange, it can detect another kind of error not caught by `tco`, namely a trampoline declared at the wrong level:

```python
@trampolined
def foo():
    def bar():
        return jump(qux, 23)
    bar()  # normal call, no TCO
```

Here ``bar`` has no trampoline; only ``foo`` does. In `fasttco`, **only** a ``@trampolined`` function, or a function entered via a tail call, may return a jump. The default TCO implementation happily escapes out to the trampoline of ``foo``, performing the tail call as if ``foo`` had requested the ``jump``.


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

Each function in the TCO call chain tells the trampoline where to go next (and with what parameters). All hail [lambda, the ultimate GOTO](http://hdl.handle.net/1721.1/5753)!

Each TCO call chain brings its own trampoline, so they nest as expected:

```python
@trampolined
def foo():
    return jump(bar)
@trampolined
def bar():
    t = even(42)  # start another trampoline for even/odd, with SELF initially pointing to "even"
    return jump(baz, t)
@trampolined
def baz(result):
    print(result)
foo()  # start trampoline, with SELF initially pointing to "foo"
```


### Loops in FP style (with TCO)

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

Just like ``jump``, if `fasttco` is used, then ``loop`` is **a noun, not a verb.** This is because the expression ``loop(...)`` is essentially the same as ``jump(SELF, ...)``. However, it also inserts the magic parameter ``loop``, which can only be set up via this mechanism.

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

Keep in mind, though, that this pure-Python FP looping mechanism is slow (even with `fasttco`), so it may make sense to use it only when "the FP-ness" (no mutation, scoping) is important.

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

Multiple input sequences work somewhat like in Python's ``for``, except any tuple unpacking must be performed inside the body:

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

With the enhanced ``curry`` in v0.8.1 and later, this is also a possible solution:

```python
s = curry(looped_over, range(10), 0,
            lambda loop, x, acc:
              loop(acc + x))
assert s == 45
```


### Escape continuations (ec)

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


### First-class escape continuations: ``call/ec``

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

### Dynamic scoping

(To be technically correct, [dynamic assignment](https://groups.google.com/forum/#!topic/racket-users/2Baxa2DxDKQ) as termed by Felleisen.)

Like global variables, but better-behaved. Useful for sending some configuration parameters through several layers of function calls without changing their API. Best used sparingly. Similar to [Racket](http://racket-lang.org/)'s [`parameterize`](https://docs.racket-lang.org/guide/parameterize.html). The *special variables* in Common Lisp work somewhat similarly (but with indefinite scope).

There's a singleton, `dyn`:

```python
from unpythonic import dyn

def f():  # no "a" in lexical scope here
    assert dyn.a == 2

def g():
    with dyn.let(a=2, b="foo"):
        assert dyn.a == 2

        f()

        with dyn.let(a=3):  # dynamic scopes can be nested
            assert dyn.a == 3

        # now "a" has reverted to its previous value
        assert dyn.a == 2

    print(dyn.b)  # AttributeError, dyn.b no longer exists
g()
```

Dynamic variables can only be set using `with dyn.let(...)`. No `set`, `<<`, unlike in the other `unpythonic` environments.

The values of dynamic variables remain bound for the dynamic extent of the `with` block. Exiting the `with` block then pops the stack. Inner dynamic scopes shadow outer ones. Dynamic variables are seen also by code that is outside the lexical scope where the `with dyn.let` resides.

Each thread has its own dynamic scope stack. A newly spawned thread automatically copies the then-current state of the dynamic scope stack **from the main thread** (not the parent thread!). This feature is mainly intended for easily initializing default values for configuration parameters across all threads.

Any copied bindings will remain on the stack for the full dynamic extent of the new thread. Because these bindings are not associated with any `with` block running in that thread, and because aside from the initial copying, the dynamic scope stacks are thread-local, any copied bindings will never be popped, even if the main thread pops its own instances of them.

The source of the copy is always the main thread mainly because Python's `threading` module gives no tools to detect which thread spawned the current one. (If someone knows a simple solution, PRs welcome!)


### Batteries for functools

Some overlap with [toolz](https://github.com/pytoolz/toolz) and [funcy](https://github.com/suor/funcy/). In ``unpythonic``:

 - `memoize` caches also exceptions à la Racket.
   - If the memoized function is called again with arguments with which it raised an exception the first time, the same exception instance is raised again.
 - `curry` comes with some extra features:
   - Passthrough on the right when too many args (à la Haskell; or [spicy](https://github.com/Technologicat/spicy) for Racket)
     - If the intermediate result of a passthrough is callable, it is (curried and) invoked on the remaining positional args. This helps with some instances of [point-free style](https://en.wikipedia.org/wiki/Tacit_programming).
     - For simplicity, all remaining keyword args are fed in at the first step that has too many positional args.
   - Can be used both as a decorator and as a regular function.
     - As a regular function, `curry` itself is curried à la Racket. If it gets extra arguments (beside the function ``f``), they are the first step. This helps eliminate many parentheses.
   - **Caution**: If the positional arities of ``f`` cannot be inspected, currying fails, raising ``UnknownArity``. This may happen with builtins such as ``operator.add``.
 - `composel`, `composer`: both left-to-right and right-to-left function composition, to help readability.
   - Any number of positional arguments is supported, with the same rules as in the pipe system. Multiple return values packed into a tuple or list are unpacked to the argument list of the next function in the chain.
   - `composelc`, `composerc`: curry each function before composing them. Useful with passthrough.
   - `composel1`, `composer1`: 1-in-1-out chains (faster; also useful for a single value that is a tuple or list).
   - suffix `i` to use with an iterable (`composeli`, `composeri`, `composelci`, `composerci`, `composel1i`, `composer1i`)
 - `andf`, `orf`, `notf`: compose predicates (like Racket's `conjoin`, `disjoin`, `negate`).
 - `rotate`: a cousin of `flip`, for permuting positional arguments.
 - `to1st`, `to2nd`, `tokth`, `tolast`, `to` to help inserting 1-in-1-out functions into m-in-n-out compose chains.
 - `identity`, `const` which sometimes come in handy when programming with higher-order functions.

Examples (see also the next section):

```python
from operator import add, mul
from unpythonic import andf, orf, flatmap, rotate, curry, foldl, foldr, composer, to1st, cons, nil, ll

isint  = lambda x: isinstance(x, int)
iseven = lambda x: x % 2 == 0
isstr  = lambda s: isinstance(s, str)
assert andf(isint, iseven)(42) is True
assert andf(isint, iseven)(43) is False
pred = orf(isstr, andf(isint, iseven))
assert pred(42) is True
assert pred("foo") is True
assert pred(None) is False

@rotate(1)  # cycle *the args* (not their slots!) to the right by one place.
def zipper(acc, *rest):   # so that we can use the *args syntax to declare this
    return acc + (rest,)  # even though the input is (e1, ..., en, acc).
zipl = curry(foldl, zipper, ())  # same as (curry(foldl))(zipper, ())
zipr = curry(foldr, zipper, ())
assert zipl((1, 2, 3), (4, 5, 6), (7, 8)) == ((1, 4, 7), (2, 5, 8))
assert zipr((1, 2, 3), (4, 5, 6), (7, 8)) == ((3, 6, 8), (2, 5, 7))

# passthrough on the right
double = lambda x: 2 * x
assert curry(double, 2, "foo") == (4, "foo")   # arity of double is 1

mysum = curry(foldl, add, 0)
myprod = curry(foldl, mul, 1)
a = ll(1, 2)
b = ll(3, 4)
c = ll(5, 6)
append_two = lambda a, b: foldr(cons, b, a)
append_many = lambda *lsts: foldr(append_two, nil, lsts)  # see lappend
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
mapr_one = lambda f: curry(foldl, composer(cons, to1st(f)), nil)  # essentially reversed(map(...))
mapl_one = lambda f: composer(mapr_one(f), lreverse)
assert curry(mapl_one, double, ll(1, 2, 3)) == ll(2, 4, 6)
```

which may be a useful pattern for iterables that don't support ``reversed`` (used by ``foldr`` internally); although linked lists do.

In ``mapr_one``, we can use either ``curry`` or ``functools.partial``. In this case it doesn't matter which, since we want just one partial application anyway. We provide two arguments, and the minimum arity of ``foldl`` is 3, so ``curry`` will trigger the call as soon as (and only as soon as) it gets at least one more argument.

The final ``curry`` uses both of the extra features. It invokes passthrough, since ``mapl_one`` has arity 1. It also invokes a call to the callable returned from ``mapl_one``, with the remaining arguments (in this case just one, the ``ll(1, 2, 3)``).

As for v0.8.1, yet another way to write ``map_one`` is:

```python
mymap = lambda f: curry(foldr, composer(cons, curry(f)), nil)
```

The curried ``f`` uses up one argument (provided it is a one-argument function!), and the second argument is passed through on the right; this two-tuple then ends up as the arguments to ``cons``.

v0.8.2 adds currying variants of the compose functions (names suffixed with ``c``), so the inner curry is no longer needed:

```python
mymap = lambda f: curry(foldr, composerc(cons, f), nil)
assert curry(mymap, lambda x, y: x + y, (1, 2, 3), (2, 4, 6)) == (3, 6, 9)
```

This is as close to ```(define (map f) (foldr (compose cons f) empty)``` (in ``#lang`` [``spicy``](https://github.com/Technologicat/spicy)) as we're gonna get in Python.

Notice how the last two versions accept multiple input sequences; this is thanks to currying ``f`` inside the composition. An element from each of the sequences is taken by the processing function ``f``. Being the last argument, ``acc`` is passed through on the right. The output from the processing function - one new item - and ``acc`` then become a two-tuple, passed into cons.

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

because ``a2`` is already curried. Doing so does no harm, though; as of v0.8.2, ``curry`` automatically prevents stacking ``curried`` wrappers:

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

**Note**: to code in curried style, a [contract system](https://github.com/AndreaCensi/contracts) or [a static type checker](http://mypy-lang.org/) is useful; also, be careful with variadic functions.


### Batteries for itertools

 - Racket-style `foldl`, `foldr` that support multiple input sequences.
   - Like in Racket, `op(elt, acc)`; general case `op(e1, e2, ..., en, acc)`. Note Python's own `functools.reduce` uses the ordering `op(acc, elt)` instead.
   - No sane default for multi-input case, so the initial value for `acc` must be given.
   - One-input versions are provided as `reducel`, `reducer`, with semantics similar to Python's `functools.reduce`, but with the rackety ordering `op(elt, acc)`.
 - `flatmap`: map a function, that returns a list or tuple, over an iterable and then flatten by one level, concatenating the results into a single tuple.
   - Essentially, ``composel(map(...), flatten1)``; the same thing the bind operator of the List monad does.
 - `mapr`, `zipr`: variants of the builtin `map` and `zip` that first reverse each input sequence.
 - `uniqify`, `uniq`: remove duplicates (either all or consecutive only, respectively).
 - `flatten1`, `flatten`, `flatten_in`: remove nested list structure.
   - `flatten1`: outermost level only.
   - `flatten`: recursive, with an optional predicate that controls whether to flatten a given sublist.
   - `flatten_in`: recursive, with an optional predicate; but recurse also into items which don't match the predicate.
 - `take`, `drop`, `split_at`, based on `itertools` [recipes](https://docs.python.org/3/library/itertools.html#itertools-recipes), but returning a generator.
   - Especially useful for testing generators.

Examples:

```python
from functools import partial
from unpythonic import foldl, foldr, flatmap, mapr, zipr, uniqify, uniq, \
                       flatten1, flatten, flatten_in, take, drop

def msqrt(x):  # multivalued sqrt
    if x == 0.:
        return (0.,)
    else:
        s = x**0.5
        return (s, -s)
assert tuple(flatmap(msqrt, (0, 1, 4, 9))) == (0., 1., -1., 2., -2., 3., -3.)

assert tuple(zipr((1, 2, 3), (4, 5, 6), (7, 8))) == ((3, 6, 8), (2, 5, 7))

zipr2 = partial(mapr, identity)
assert tuple(zipr2((1, 2, 3), (4, 5, 6), (7, 8))) == ((3, 6, 8), (2, 5, 7))

assert tuple(uniqify((1, 1, 2, 2, 2, 1, 2, 2, 4, 3, 4, 3, 3))) == (1, 2, 4, 3)  # all
assert tuple(uniq((1, 1, 2, 2, 2, 1, 2, 2, 4, 3, 4, 3, 3))) == (1, 2, 1, 2, 4, 3, 4, 3)  # consecutive

assert tuple(flatten1(((1, 2), (3, (4, 5), 6), (7, 8, 9)))) == (1, 2, 3, (4, 5), 6, 7, 8, 9)
assert tuple(flatten(((1, 2), (3, (4, 5), 6), (7, 8, 9)))) == (1, 2, 3, 4, 5, 6, 7, 8, 9)

is_nested = lambda sublist: all(isinstance(x, (tuple, list)) for x in sublist)
assert tuple(flatten((((1, 2), (3, 4)), (5, 6)), is_nested)) == ((1, 2), (3, 4), (5, 6))

data = (((1, 2), ((3, 4), (5, 6)), 7), ((8, 9), (10, 11)))
assert tuple(flatten(data, is_nested))    == (((1, 2), ((3, 4), (5, 6)), 7), (8, 9), (10, 11))
assert tuple(flatten_in(data, is_nested)) == (((1, 2), (3, 4), (5, 6), 7),   (8, 9), (10, 11))

with_n = lambda *args: (partial(f, n) for n, f in args)
look = lambda n1, n2: composel(*with_n((n1, drop), (n2, take)))
assert tuple(look(5, 10)(range(20))) == tuple(range(5, 15))
```

In the last example, essentially we just want to `look 5 10 (range 20)`, the grouping of the parentheses being pretty much an implementation detail. With ``curry`` from the previous section, we can rewrite the last line as:

```python
assert tuple(curry(look, 5, 10, range(20)) == tuple(range(5, 15))
```


### Functional update, sequence shadowing

We provide ``ShadowedSequence``, which is a bit like ``collections.ChainMap``, but for sequences, and only two levels (but it's a sequence; instances can be chained). For details, see ``unpythonic.fup``.

``ShadowedSequence`` is used by the function ``fupdate``, which functionally updates sequences and mappings. Whereas ``ShadowedSequence`` reads directly from the original sequences at access time, ``fupdate`` makes a shallow copy (of the same type as the given input sequence) when it finalizes its output (this trades some memory for performance, useful if the same data is read often).

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

The replacement sequence must have at least as many items as the slice requires (when applied to the original input). Any extra items in the replacement sequence are simply ignored, but if the replacement is too short, ``ValueError`` is raised.

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

But there is no support for immutable mappings, because Python's standard library doesn't provide an immutable dict type. For mappings, ``fupdate`` is essentially just ``copy.copy()`` and then ``.update()`` (which wouldn't exist for immutable inputs).

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


### Nondeterministic evaluation

We provide a simple variant of nondeterministic evaluation. This is essentially a toy that has no more power than list comprehensions or nested for loops. An important feature of McCarthy's [`amb` operator](https://rosettacode.org/wiki/Amb) is its nonlocality - being able to jump back to a choice point, even after the dynamic extent of the function where that choice point resides. This sounds a lot like ``call/cc``; which is how ``amb`` is usually implemented. See implementations [in Ruby](http://www.randomhacks.net/2005/10/11/amb-operator/) and [in Racket](http://www.cs.toronto.edu/~david/courses/csc324_w15/extra/choice.html).

Python can't do that, short of compiling the whole program into [CPS](https://en.wikipedia.org/wiki/Continuation-passing_style), while applying TCO everywhere to prevent stack overflow. Arguably, the result would no longer be Python. (As Abelson and Sussman explain in SICP, ``call/cc`` can be implemented via this strategy. It's an instance of lambda as the ultimate GOTO.)

Instead, what we have here is essentially a tuple comprehension that:

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


### `cons` and friends

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

Iterators are supported to walk over linked lists (this also gives tuple unpacking support). When ``next()`` is called, we return the car of the current cell the iterator points to, and the iterator moves to point to the cons cell in the cdr, if any. When the cdr is not a cons cell, it is the next (and last) item returned; except if it `is nil`, then iteration ends without returning the `nil`.

Python's builtin ``reversed`` can be applied to linked lists; it will internally ``lreverse`` the list (which is O(n)), then return an iterator to that. This means also ``foldr`` works on linked lists. ``llist`` is special-cased so that if the input is ``reversed(some_ll)``, it just returns the internal already reversed list. (This is safe because cons cells are immutable.)

Cons structures are hashable and pickleable, and print like in Lisps:

```python
print(cons(1, 2))                    # --> (1 . 2)
print(ll(1, 2, 3))                   # --> (1 2 3)
print(cons(cons(1, 2), cons(3, 4)))  # --> ((1 . 2) . (3 . 4))
```

For more, see the ``llist`` submodule.

#### Notes

There is no ``copy`` method or ``lcopy`` function, because cons cells are immutable; which makes cons structures immutable.

(However, for example, it is possible to `cons` a new item onto an existing linked list; that's fine because it produces a new cons structure - which shares data with the original, just like in Racket.)

In general, copying cons structures can be error-prone. Given just a starting cell it is impossible to tell if a given instance of a cons structure represents a linked list, or something more general (such as a binary tree) that just happens to locally look like one, along the path that would be traversed if it was indeed a linked list.

The linked list iteration strategy does not recurse in the ``car`` half, which could lead to incomplete copying. The tree strategy that recurses on both halves, on the other hand, is not safe to use on linked lists, because if the list is long, it will cause a stack overflow (due to lack of TCO in Python). With the tools in this library it would be possible to make a tree recurser with TCO applied in the `cdr` half, but the current generator-based implementation of ``BinaryTreeIterator`` is much shorter.

**Caution**: the ``nil`` singleton is freshly created in each session; newnil is not oldnil, so don't pickle a standalone ``nil``. The unpickler of ``cons`` automatically refreshes any ``nil`` instances inside a pickled cons structure, so that **cons structures** support the illusion that ``nil`` is a special value like ``None`` or ``...``. After unpickling, ``car(c) is nil`` and ``cdr(c) is nil`` still work as expected, even though ``id(nil)`` has changed.


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


## Design notes

### On ``let`` and Python

Why no `let*`? In Python, name lookup always occurs at runtime. Python gives us no compile-time guarantees that no binding refers to a later one - in [Racket](http://racket-lang.org/), this guarantee is the main difference between `let*` and `letrec`.

Even Racket's `letrec` processes the bindings sequentially, left-to-right, but *the scoping of the names is mutually recursive*. Hence a binding may contain a lambda that, when eventually called, uses a binding defined further down in the `letrec` form.

In contrast, in a `let*` form, attempting such a definition is *a compile-time error*, because at any point in the sequence of bindings, only names found earlier in the sequence have been bound. See [TRG on `let`](https://docs.racket-lang.org/guide/let.html).

Our `letrec` behaves like `let*` in that if `valexpr` is not a function, it may only refer to bindings above it. But this is only enforced at run time, and we allow mutually recursive function definitions, hence `letrec`.

Note that our `let` constructs are **not** properly lexically scoped; in case of nested ``let`` expressions, one must be explicit about which environment the names come from.

Inspiration: [[1]](https://nvbn.github.io/2014/09/25/let-statement-in-python/) [[2]](https://stackoverflow.com/questions/12219465/is-there-a-python-equivalent-of-the-haskell-let) [[3]](http://sigusr2.net/more-about-let-in-python.html).

### Python is not a Lisp

The point behind providing `let` and `begin` is to make Python lambdas slightly more useful - which was really the starting point for this whole experiment.

The oft-quoted single-expression limitation of the Python ``lambda`` is ultimately a herring, as this library demonstrates. The real problem is the statement/expression dichotomy. In Python, the looping constructs (`for`, `while`), the full power of `if`, and `return` are statements, so they cannot be used in lambdas. We can work around some of this:

 - The expression form of `if` can be used to a limited extent. Actually, [`and` and `or` are sufficient for full generality](https://www.ibm.com/developerworks/library/l-prog/), but readability suffers, so it may be better not to go there. Another possibility is to use MacroPy to define a ``cond`` expression, but it's essentially duplicating a feature the language already almost has.
 - Functional looping (with TCO, to boot) is possible.
 - ``unpythonic.ec.call_ec`` gives us ``return`` (the ec), and ``unpythonic.misc.raisef`` gives us ``raise``.

Still, ultimately one must keep in mind that Python is not a Lisp. Not all of Python's standard library is expression-friendly; some standard functions and methods lack return values - even though a call is an expression! For example, `set.add(x)` returns `None`, whereas in an expression context, returning `x` would be much more useful, even though it does have a side effect.

### Assignment syntax

Why the clunky `e.set("foo", newval)` or `e << ("foo", newval)`, which do not directly mention `e.foo`? This is mainly because in Python, the language itself is not customizable. If we could define a new operator `e.foo <op> newval` to transform to `e.set("foo", newval)`, this would be easily solved.

We could abuse `e.foo << newval`, which transforms to `e.foo.__lshift__(newval)`, to essentially perform `e.set("foo", newval)`, but this requires some magic, because we then need to monkey-patch each incoming value (including the first one when the name "foo" is defined) to set up the redirect and keep it working.

 - Methods of builtin types such as `int` are read-only, so we can't just override `__lshift__` in any given `newval`.
 - For many types of objects, at the price of some copy-constructing, we can provide a wrapper object that inherits from the original's type, and just adds an `__lshift__` method to catch and redirect the appropriate call. See commented-out proof-of-concept in [`unpythonic/env.py`](unpythonic/env.py).
 - But that approach doesn't work for function values, because `function` is not an acceptable base type to inherit from. In this case we could set up a proxy object, whose `__call__` method calls the original function (but what about the docstring and such? Is `@functools.wraps` enough?). But then there are two kinds of wrappers, and the re-wrapping logic (which is needed to avoid stacking wrappers when someone does `e.a << e.b`) needs to know about that.
 - It's still difficult to be sure these two approaches cover all cases; a read of `e.foo` gets a wrapped value, not the original; and this already violates [The Zen of Python](https://www.python.org/dev/peps/pep-0020/) #1, #2 and #3.

If we later choose go this route nevertheless, `<<` is a better choice for the syntax than `<<=`, because `let` needs `e.set(...)` to be valid in an expression context.

### TCO syntax and speed

Benefits and costs of ``return jump(...)``, the syntax required by `fasttco`:

 - Explicitly a tail call due to ``return``.
 - The trampoline can be very simple and (relatively speaking) fast. Just a dumb ``jump`` record, a ``while`` loop, and regular function calls and returns.
 - The cost is that ``jump`` cannot detect whether the user forgot the ``return``, leaving a possibility for bugs in the client code (causing an FP loop to immediately exit, returning ``None``). Unit tests of client code become very important.
   - This is somewhat mitigated by the check in `__del__`, but it can only print a warning, not stop the incorrect program from proceeding.
   - We could mandate that trampolined functions must not return ``None``, but:
     - Uniformity is lost between regular and trampolined functions, if only one kind may return ``None``.
     - This breaks the *don't care about return value* use case, which is rather common when using side effects.
     - Failing to terminate at the intended point may well fall through into what was intended as another branch of the client code, which may correctly have a ``return``. So this would not even solve the problem.

The other simple-ish solution is to use exceptions, making the jump wrest control from the caller. Then ``jump(...)`` becomes a verb. This is the approach taken in the default [``tco.py``](unpythonic/tco.py).

For other libraries bringing TCO to Python, see:

 - [tco](https://github.com/baruchel/tco) by Thomas Baruchel, based on exceptions.
 - [ActiveState recipe 474088](https://github.com/ActiveState/code/tree/master/recipes/Python/474088_Tail_Call_Optimization_Decorator), based on ``inspect``.
 - ``recur.tco`` in [fn.py](https://github.com/fnpy/fn.py), the original source of the approach used here.

### Wait, no monads?

(Beside List inside ``forall``.)

Admittedly unpythonic, but Haskell feature, not Lisp. Besides, already done elsewhere, see [OSlash](https://github.com/dbrattli/OSlash) if you need them.

If you want to roll your own monads for whatever reason, there's [this silly hack](https://github.com/Technologicat/python-3-scicomp-intro/blob/master/examples/monads.py) that wasn't packaged into this; or just read Stephan Boyer's quick introduction [[part 1]](https://www.stephanboyer.com/post/9/monads-part-1-a-design-pattern) [[part 2]](https://www.stephanboyer.com/post/10/monads-part-2-impure-computations) [[super quick intro]](https://www.stephanboyer.com/post/83/super-quick-intro-to-monads) and figure it out, it's easy. (Until you get to `State` and `Reader`, where [this](http://brandon.si/code/the-state-monad-a-tutorial-for-the-confused/) and maybe [this](https://gaiustech.wordpress.com/2010/09/06/on-monads/) can be helpful.)

## Installation

### PyPI

Usually one of:

```pip3 install unpythonic --user```

```sudo pip3 install unpythonic```

depending on what you want.

### GitHub

Clone (or pull) from GitHub. Then, usually one of:

```python3 setup.py install --user```

```sudo python3 setup.py install```

depending on what you want.

### Uninstall

```pip3 uninstall unpythonic```

with ``sudo`` if needed.

Must be invoked in a folder which has no subfolder called `unpythonic`, so that `pip` recognizes it as a package name (instead of a filename).

## License

2-clause [BSD](LICENSE.md).

Dynamic scoping based on [StackOverflow answer by Jason Orendorff (2010)](https://stackoverflow.com/questions/2001138/how-to-create-dynamical-scoped-variables-in-python), used under CC-BY-SA. The threading support is original to our version.

Core idea of `lispylet` based on [StackOverflow answer by divs1210 (2017)](https://stackoverflow.com/a/44737147), used under the MIT license.

## Acknowledgements

Thanks to [TUT](http://www.tut.fi/en/home) for letting me teach [RAK-19006 in spring term 2018](https://github.com/Technologicat/python-3-scicomp-intro); early versions of parts of this library were originally developed as teaching examples for that course. Thanks to @AgenttiX for feedback.

The trampoline implementation of ``unpythonic.fasttco`` takes its remarkably clean and simple approach from ``recur.tco`` in [fn.py](https://github.com/fnpy/fn.py). Our main improvements are a cleaner syntax for the client code, and the addition of the FP looping constructs.

Another important source of inspiration was [tco](https://github.com/baruchel/tco) by Thomas Baruchel, for thinking about the possibilities of TCO in Python.

## Python-related FP resources

- [Awesome Functional Python](https://github.com/sfermigier/awesome-functional-python), especially a list of useful libraries. Some picks:

  - [fn.py: Missing functional features of fp in Python](https://github.com/fnpy/fn.py) (actively maintained fork). Includes e.g. tail call elimination by trampolining, and a very compact way to recursively define infinite streams.

  - [more-itertools: More routines for operating on iterables, beyond itertools.](https://github.com/erikrose/more-itertools)

  - [toolz: A functional standard library for Python](https://github.com/pytoolz/toolz)

  - [funcy: A fancy and practical functional tools](https://github.com/suor/funcy/)

  - [pyrsistent: Persistent/Immutable/Functional data structures for Python](https://github.com/tobgu/pyrsistent)

- [List of languages that compile to Python](https://github.com/vindarel/languages-that-compile-to-python) including Hy, a Lisp (in the [Lisp-2](https://en.wikipedia.org/wiki/Lisp-1_vs._Lisp-2) family) that can use Python libraries.

Old, but interesting:

- [Peter Norvig (2000): Python for Lisp Programmers](http://www.norvig.com/python-lisp.html)

- [David Mertz (2001): Charming Python - Functional programming in Python, part 2](https://www.ibm.com/developerworks/library/l-prog2/index.html)

