# Unpythonic: Lispy convenience features for Python

```python
from unpythonic import *
```


### Assign-once

Make `define` and `set!` look different:

```python
with assignonce() as e:
    e.foo = "bar"           # new definition, ok
    e.set("foo", "tavern")  # explicitly rebind e.foo, ok
    e << ("foo", "tavern")  # same thing (but return e instead of new value, suitable for chaining)
    e.foo = "quux"          # AttributeError, e.foo already defined.
```


### Multiple expressions in a lambda

```python
f1 = lambda x: begin(print("cheeky side effect"),
                     42*x)
f1(2)  # --> 84

f2 = lambda x: begin0(42*x,
                      print("cheeky side effect"))
f2(2)  # --> 84
```

Actually a tuple in disguise. If worried about memory consumption, use `lazy_begin` and `lazy_begin0` instead, which indeed use loops. The price is the need for a lambda wrapper for each expression to delay evaluation, see [`tour.py`](tour.py) for details.

Note also it's only useful for side effects, since there's no way to define new names, except...


### Local bindings: ``let``, ``letrec``

In ``let``, the bindings are independent (do not see each other); only the body may refer to the bindings. Use a `lambda e: ...` to supply the environment to the body:

```python
u = lambda lst: let(seen=set(),
                    body=lambda e:
                           [e.seen.add(x) or x for x in lst if x not in e.seen])
L = [1, 1, 3, 1, 3, 2, 3, 2, 2, 2, 4, 4, 1, 2, 3]
u(L)  # --> [1, 3, 2, 4]
```

Generally speaking, `body` is a one-argument function, which takes in the environment instance as the first positional parameter (usually named `env` or `e` for readability). In typical inline usage, `body` is `lambda e: expr`.

*Let over lambda*. The inner ``lambda`` is the definition of the function ``counter``:

```python
counter = let(x=0,
              body=lambda e:
                     lambda:
                       begin(e.set("x", e.x + 1),  # can also use e << ("x", e.x + 1)
                             e.x))
counter()  # --> 1
counter()  # --> 2
```

Compare this [Racket](http://racket-lang.org/) (here using `sweet-exp` [[1]](https://srfi.schemers.org/srfi-110/srfi-110.html) [[2]](https://docs.racket-lang.org/sweet/) for pythonic layout):

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

In `letrec`, bindings may depend on ones above them in the same `letrec`, using `lambda e: ...` (**Python 3.6+**):

```python
x = letrec(a=1,
           b=lambda e:
                  e.a + 1,
           body=lambda e:
                  e.b)  # --> 2
```

In `letrec`, the RHS of each binding is either a simple value (non-callable, and doesn't use the environment), or an expression of the form ``lambda e: valexpr``, providing access to the environment as ``e``. If ``valexpr`` itself is callable, the binding **must** have the ``lambda e: ...`` wrapper to prevent any misunderstandings in the environment initialization procedure.

In a non-callable ``valexpr``, trying to depend on a binding below it raises ``AttributeError``.

But a callable ``valexpr`` may depend on any bindings (also later ones) in the same `letrec`. Mutually recursive functions:

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
                    lambda x:
                      (x == 0) or e.oddp(x - 1)),
        ("oddp",  lambda e:
                    lambda x:
                      (x != 0) and e.evenp(x - 1))),
       lambda e:
         e.evenp(42))  # --> True
```

The syntax is `let(bindings, body)` (respectively `letrec(bindings, body)`), where `bindings` is `((name, value), ...)`, and `body` is like in the default variants.

Like in the default variant, in `letrec`, each `value` is either a simple value (non-callable, and doesn't use the environment), or an expression of the form ``lambda e: valexpr``, providing access to the environment as ``e``. If ``valexpr`` itself is callable, ``value`` **must** have the ``lambda e: ...`` wrapper to prevent any misunderstandings in the environment initialization procedure.

Like in the default variant, a callable ``valexpr`` may depend on any bindings (also later ones) in the same `letrec`, allowing mutually recursive functions.

```python
u = lambda lst: letrec((("seen", set()),
                        ("see",  lambda e:
                                   lambda x:  # callable, needs "lambda e: ..."
                                     begin(e.seen.add(x),
                                           x))),
                       lambda e:
                         [e.see(x) for x in lst if x not in e.seen])

letrec((('a', 2),
        ('f', lambda e:
                lambda x:  # callable, needs "lambda e: ..." even though it doesn't use e
                  42*x)),
       lambda e:
         e.a * e.f(1))  # --> 84

square = lambda x: x**2
letrec((('a', 2),
        ('f', lambda e: square)),  # callable, needs "lambda e: ..."
       lambda e:
         e.a * e.f(10))  # --> 200

def mul(x, y):
    return x * y
letrec((('a', 2),
        ('f', lambda e: mul)),  # "mul" is a callable
       lambda e:
         e.a * e.f(3, 4))  # --> 24

from functools import partial
double = partial(mul, 2)
letrec((('a', 2),
        ('f', lambda e: double)),  # "double" is a callable
       lambda e:
         e.a * e.f(3))  # --> 12

class TimesA:
    def __init__(self, a):
        self.a = a
    def __call__(self, x):
        return self.a * x
times5 = TimesA(5)
letrec((('a', 2),
        ('f', lambda e: times5)),  # "times5" is a callable
       lambda e:
         e.a * e.f(3))  # --> 30
```


### Tail call optimization (TCO) / explicit continuations

Express elegant algorithms without blowing the call stack - with explicit, clear syntax.

*Tail recursion*:

```python
@trampolined
def fact(n, acc=1):
    if n == 0:
        return acc
    else:
        return jump(fact, n - 1, n * acc)
print(fact(4))  # 24
```

Functions that use TCO **must** be `@trampolined`. Calling a trampolined function normally starts the trampoline.

Inside a trampolined function, a normal call `f(a, ..., kw=v, ...)` remains a normal call. A tail call with target `f` is denoted `return jump(f, a, ..., kw=v, ...)`.

Here `jump` is **a noun, not a verb**. The `jump(f, ...)` part just evaluates to a `jump` instance, which on its own does nothing. Returning it to the trampoline actually performs the tail call.

The final result is just returned normally. Returning a normal value (anything that is not a ``jump`` instance) to a trampoline shuts down that trampoline, and returns the given value from the initial call (to a ``@trampolined`` function) that originally started that trampoline.

*Tail recursion in a lambda*:

```python
t = trampolined(lambda n, acc=1:
                    acc if n == 0 else jump(SELF, n - 1, n * acc))
print(t(4))  # 24
```

To denote tail recursion in an anonymous function, use the special jump target `SELF` (all uppercase!). Here it's just `jump` instead of `return jump` since lambda does not use the `return` syntax.

Technically, `SELF` means *keep current jump target*, so the function that was last explicitly named in that particular trampoline remains as the target of the jump. When the trampoline starts, the current target is set to the initial entry point (also for lambdas).

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
print(even(42))  # True
print(odd(4))  # False
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

Each function in the TCO call chain tells the trampoline where to go next (and with what parameters). All hail lambda, the ultimate GO TO!

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
@looped
def s(loop, acc=0, i=0):
    if i == 10:
        return acc
    else:
        return loop(acc + i, i + 1)
print(s)  # 45
```

Compare this sweet-exp Racket:

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

In `@looped`, the function name of the loop body is the name of the final result, like in `@immediate`. The final result of the loop is just returned normally.

The first parameter of the loop body is the magic parameter ``loop``. It is *self-ish*, representing a jump back to the loop body itself, starting a new iteration. Just like Python's ``self``, ``loop`` can have any name; it is passed positionally.

Just like ``jump``, here ``loop`` is **a noun, not a verb.** The expression ``loop(...)`` is otherwise the same as ``jump(SELF, ...)``, but it also inserts the magic parameter ``loop``, which can only be set up via this mechanism.

For any other parameters, their initial values must be set as defaults. The loop is automatically started by `@looped`, by calling the body with the magic ``loop`` as the only parameter.

Any loop variables such as ``i`` in the above example are **in scope only in the loop body**; there is no ``i`` in the surrounding scope. Moreover, it's a fresh ``i`` at each iteration; nothing is mutated by the looping mechanism. (But be careful if you use a mutable object instance as a loop variable. The loop body is just a function call like any other, so the usual rules apply.)

FP loops don't have to be pure:

```python
out = []
@looped
def _(loop, i=0):  # _ = don't care about return value
    if i <= 3:
        out.append(i)  # cheeky side effect
        return loop(i + 1)
    # the implicit "return None" terminates the loop.
assert out == [0, 1, 2, 3]
```

Keep in mind, though, that if you don't need the FP-ness, it may be better to use ``for``.

The `@looped` decorator is essentially sugar. The first example above is roughly equivalent to:

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

This is slightly faster, because in `@looped` setting up ``loop`` costs some magic at each iteration (no macros in this package!). But if you do it manually like this, remember to start the loop after the definition is done!

Keep in mind that this pure-Python FP looping mechanism is 40-80× slower than Python's builtin imperative ``for``, anyway, so in places where using these constructs makes sense, readability may be more important than speed.

Also be aware that `@looped` is specifically neither a ``for`` loop nor a ``while`` loop. Instead, it is a general mechanism that can express both kinds of loops - i.e. it embodies the raw primitive essence of looping.

*Typical `while True` loop in FP style*:

```python
@looped
def _(loop):
    print("Enter your name (or 'q' to quit): ", end='')
    s = input()
    if s.lower() == 'q':
        return  # ...the implicit None. In a "while True:", we'd put a "break" here.
    else:
        print("Hello, {}!".format(s))
        return loop()
```

#### FP loop over an iterable

In Python, many loops are *foreach* loops directly over the elements of an iterable, which gives a marked improvement in readability compared to dealing with indices. For that extremely common use case, we provide ``@looped_over``:

```python
@looped_over(range(10), acc=0)
def s(loop, x, acc):
    return loop(acc + x)
assert s == 45
```

The loop body takes three magic positional parameters. The first parameter ``loop`` works like in ``@looped``. The second parameter ``x`` is the current element. The third parameter ``acc`` is initialized to the ``acc`` value given to ``@looped_over``, and then (functionally) updated at each iteration, taking as the new value the first positional parameter given to ``return loop(...)``, if any positional parameters were given. If no positional parameters were given, ``acc`` resets to its initial value.

Additional arguments can be given to ``return loop(...)``. When the loop body is called, any additional positional arguments are appended to the implicit ones, and can be anything. Their initial values **must** be set as defaults in the formal parameter list of the body. Additional arguments can also be passed by name.

This silly example has the additional parameters ``fruit`` and ``number``. Here the first one is passed positionally, and the second one by name.

```python
@looped_over(range(10), acc=0)
def s(loop, x, acc, fruit="pear", number=23):
    print(fruit, answer)
    newfruit = "orange" if fruit == "pear" else "pear"
    return loop(acc + x, newfruit, number=42)
assert s == 45
```

The loop body is called once for each element in the iterable. When the iterable runs out of elements, the last ``acc`` value that was given to ``return loop(...)`` becomes the return value of the loop. If the iterable is empty, the body never runs; then the return value of the loop is the initial value of ``acc``.

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
@looped_over(range(1, 4), acc=[])
def outer_result(outer_loop, y, outer_acc):
    @looped_over(range(1, 3), acc=[])
    def inner_result(inner_loop, x, inner_acc):
        return inner_loop(inner_acc + [y*x])
    return outer_loop(outer_acc + [inner_result])
assert outer_result == [[1, 2], [2, 4], [3, 6]]
```

The ``@looped_over`` decorator is essentially sugar. Code roughly equivalent to the first example:

```python
@immediate
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

The actual implementation looks different, though, because this is not a macro.

#### FP loops using a lambda as body

Just use the `looped()` decorator manually:

```python
s = looped(lambda loop, acc=0, i=0:
             loop(acc + i, i + 1) if i < 10 else acc)
print(s)
```

The same, using ``let`` to define a ``cont``:

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

#### ``continue``

**There is no** FP ``continue``. At any time, ``return loop(...)`` with the appropriate arguments to proceed to the next iteration. Or package the appropriate `loop(...)` expression into your own function ``cont``:

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

This approach also separates the computations of the new values of the iteration counter and the accumulator.

#### ``break``

**There is no** FP ``break``. At any time, just ``return`` your final result normally to terminate the loop.

Because ``return`` in FP loops is reserved for this, barring the use of exceptions, there is no direct way to exit the function *containing* the loop from inside the loop.

### Escape continuations (ecs)

To remedy the above issue, we provide a form of escape continuations with `@setescape` and `escape`, based on exceptions.

```python
@setescape()  # note the parentheses
def f():
    @looped
    def s(loop, acc=0, i=0):
        if i > 5:
            return escape(acc)  # the argument becomes the return value of f()
        return loop(acc + i, i + 1)
    print("never reached")
f()  # --> 15
```

In Lisp terms, `@setescape` essentially captures the escape continuation (ec) of the function decorated with it. The nearest (dynamically) surrounding ec can then be invoked by `raise escape(value)`. The escaped function immediately terminates, returning ``value``.

To make this work with lambdas, and for uniformity of syntax, **in trampolined functions** (such as FP loops) it is also legal to ``return escape(value)``. The trampoline specifically detects `escape` instances, and performs the ``raise``.

For more control, both ``@setescape`` points and ``escape`` instances can be tagged:

```python
@setescape(tag="foo")  # setescape point tag can be single value or tuple (tuples OR'd, like isinstance())
def foo():
    @immediate
    @setescape(tag="bar")
    def bar():
        @looped
        def s(loop, acc=0, i=0):
            if i > 5:
                return escape(acc, tag="foo")  # escape instance tag must be a single value
            return loop(acc + i, i + 1)
        print("never reached")
        return False
    print("never reached either")
    return False
assert foo() == 15
```

Default tag is ``None``. An ``escape`` instance with ``tag=None`` can be caught by any ``@setescape`` point.

If an ``escape`` instance has a tag that is not ``None``, it can only be caught by ``@setescape`` points whose tags include that tag, and by untagged ``@setescape`` points (which catch everything).

On their own, ecs can be used as a *multi-return*:

```python
@setescape()
def f():
    def g():
        raise escape("hello from g")  # the argument becomes the return value of f()
        print("not reached")
    g()
    print("not reached either")
assert f() == "hello from g"
```

### Dynamic scoping

A bit like global variables, but slightly better-behaved. Useful for sending some configuration parameters through several layers of function calls without changing their API. Best used sparingly. Similar to [Racket](http://racket-lang.org/)'s [`parameterize`](https://docs.racket-lang.org/guide/parameterize.html).

There's a singleton, `dyn`, which emulates dynamic scoping:

```python
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

### The environment

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

### ``def`` as a code block

Fuel for different thinking. Compare the `something` in `call-with-something` in Lisps. A `def` is really just a new lexical scope to hold code to run later... or right now!

*Make temporaries fall out of scope as soon as no longer needed*:

```python
@immediate
def x():
    a = 2  #    many temporaries that help readability...
    b = 3  # ...of this calculation, but would just pollute locals...
    c = 5  # ...after the block exits
    return a * b * c
print(x)  # 30
```

*Multi-break out of nested loops* - `continue`, `break` and `return` are really just second-class [ec](https://docs.racket-lang.org/reference/cont.html#%28def._%28%28lib._racket%2Fprivate%2Fletstx-scheme..rkt%29._call%2Fec%29%29)s. So `def` to make `return` escape to exactly where you want:

```python
@immediate
def result():
    for x in range(10):
        for y in range(10):
            if x * y == 42:
                return (x, y)
print(result)  # (6, 7)
```

Compare this sweet-exp Racket:

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

*Twist the meaning of `def` into a "let statement"* (but see `blet`, `bletrec` if you want an `env` instance):

```python
@immediate
def result(x=1, y=2, z=3):
    return x * y * z
print(result)  # 6
```

*Letrec without `letrec`*, when it doesn't have to be an expression:

```python
@immediate
def t():
    def evenp(x): return x == 0 or oddp(x - 1)
    def oddp(x): return x != 0 and evenp(x - 1)
    return evenp(42)
print(t)  # True
```

Essentially the implementation is just `def immediate(thunk): return thunk()`. The point is to:

 - Make it explicit right at the definition site that this block is going to be run ``@immediate``ly (in contrast to an explicit call and assignment *after* the definition). Centralize the related information. Align the presentation order with the thought process.

 - Help eliminate errors, in the same way as the habit of typing parentheses only in pairs. No risk of forgetting to call the block after writing the definition.

 - Document that the block is going to be used only once. Tell the reader there's no need to remember this definition.

Too bad [the grammar](https://docs.python.org/3/reference/grammar.html) requires a newline after a decorator; "`@immediate def`" would look nicer.

## Notes

The main design consideration in this package is to not need `inspect`, keeping these modules simple and robust. The sole exception is the ``arity`` module, which could not work without `inspect`.

Since we **don't** depend on [MacroPy](https://github.com/azazel75/macropy), we provide run-of-the-mill functions and classes, not actual syntactic forms.

For more examples, see [``tour.py``](tour.py), the `test()` function in each submodule, and the docstrings of the individual features.

### On ``let`` and Python

Why no `let*`? In Python, name lookup always occurs at runtime. Python gives us no compile-time guarantees that no binding refers to a later one - in [Racket](http://racket-lang.org/), this guarantee is the main difference between `let*` and `letrec`.

Even Racket's `letrec` processes the bindings sequentially, left-to-right, but *the scoping of the names is mutually recursive*. Hence a binding may contain a lambda that, when eventually called, uses a binding defined further down in the `letrec` form.

In contrast, in a `let*` form, attempting such a definition is *a compile-time error*, because at any point in the sequence of bindings, only names found earlier in the sequence have been bound. See [TRG on `let`](https://docs.racket-lang.org/guide/let.html).

Our `letrec` behaves like `let*` in that if `valexpr` is not a function, it may only refer to bindings above it. But this is only enforced at run time, and we allow mutually recursive function definitions, hence `letrec`.

Note that our `let` constructs are not properly lexically scoped; in case of nested ``let`` expressions, one must be explicit about which environment the names come from.

Inspiration: [[1]](https://nvbn.github.io/2014/09/25/let-statement-in-python/) [[2]](https://stackoverflow.com/questions/12219465/is-there-a-python-equivalent-of-the-haskell-let) [[3]](http://sigusr2.net/more-about-let-in-python.html).

### Python is not a Lisp

The point behind providing `let` and `begin` is to make Python lambdas slightly more useful - which was really the starting point for this whole experiment.

The oft-quoted single-expression limitation is ultimately a herring - it can be fixed with a suitable `begin` form, or a function to approximate one.

The real problem is the statement/expression dichotomy. In Python, the looping constructs (`for`, `while`), the full power of `if`, and `return` are statements, so they cannot be used in lambdas. The expression form of `if` can be used to a limited extent (actually [`and` and `or` are sufficient for full generality](https://www.ibm.com/developerworks/library/l-prog/), but readability suffers), and functional looping is possible - but still, ultimately one must keep in mind that Python is not a Lisp.

Another factor here is that not all of Python's standard library is expression-friendly; some standard functions and methods lack return values - even though a call is an expression! For example, `set.add(x)` returns `None`, whereas in an expression context, returning `x` would be much more useful.

### Assignment syntax

Why the clunky `e.set("foo", newval)` or `e << ("foo", newval)`, which do not directly mention `e.foo`? This is mainly because in Python, the language itself is not customizable. If we could define a new operator `e.foo <op> newval` to transform to `e.set("foo", newval)`, this would be easily solved.

We could abuse `e.foo << newval`, which transforms to `e.foo.__lshift__(newval)`, to essentially perform `e.set("foo", newval)`, but this requires some magic, because we then need to monkey-patch each incoming value (including the first one when the name "foo" is defined) to set up the redirect and keep it working.

 - Methods of builtin types such as `int` are read-only, so we can't just override `__lshift__` in any given `newval`.
 - For many types of objects, at the price of some copy-constructing, we can provide a wrapper object that inherits from the original's type, and just adds an `__lshift__` method to catch and redirect the appropriate call. See commented-out proof-of-concept in [`unpythonic/env.py`](unpythonic/env.py).
 - But that approach doesn't work for function values, because `function` is not an acceptable base type to inherit from. In this case we could set up a proxy object, whose `__call__` method calls the original function (but what about the docstring and such? Is `@functools.wraps` enough?). But then there are two kinds of wrappers, and the re-wrapping logic (which is needed to avoid stacking wrappers when someone does `e.a << e.b`) needs to know about that.
 - It's still difficult to be sure these two approaches cover all cases; a read of `e.foo` gets a wrapped value, not the original; and this already violates [The Zen of Python](https://www.python.org/dev/peps/pep-0020/) #1, #2 and #3.

If we later choose go this route nevertheless, `<<` is a better choice for the syntax than `<<=`, because `let` needs `e.set(...)` to be valid in an expression context.

### Wait, no `cons` and friends?

[If you insist](https://github.com/Technologicat/python-3-scicomp-intro/blob/master/examples/beyond_python/lisplists.py) (but that's a silly teaching example, not optimized for production use).

### Wait, no monads?

Admittedly unpythonic, but Haskell feature, not Lisp. Besides, already done elsewhere, see [PyMonad](https://bitbucket.org/jason_delaat/pymonad/) or [OSlash](https://github.com/dbrattli/OSlash) if you need them. Especially the `List` monad can be useful also in Python, e.g. to make an [`amb`](https://rosettacode.org/wiki/Amb) without `call/cc`. Compare [this solution in Ruby](http://www.randomhacks.net/2005/10/11/amb-operator/), with `call/cc`.

If you want to roll your own monads for whatever reason, there's [this silly hack](https://github.com/Technologicat/python-3-scicomp-intro/blob/master/examples/monads.py) that wasn't packaged into this; or just read Stephan Boyer's quick introduction [[part 1]](https://www.stephanboyer.com/post/9/monads-part-1-a-design-pattern) [[part 2]](https://www.stephanboyer.com/post/10/monads-part-2-impure-computations) [[super quick intro]](https://www.stephanboyer.com/post/83/super-quick-intro-to-monads) and figure it out, it's easy. (Until you get to `State` and `Reader`, where [this](http://brandon.si/code/the-state-monad-a-tutorial-for-the-confused/) and maybe [this](https://gaiustech.wordpress.com/2010/09/06/on-monads/) can be helpful.)

## Installation

Not yet available on PyPI; clone from GitHub.

### Install

Usually one of:

```
python3 setup.py install --user
```

```
sudo python3 setup.py install
```

depending on what you want.

### Uninstall

```
pip3 uninstall unpythonic
```

Must be invoked in a folder which has no subfolder called `unpythonic`, so that `pip` recognizes it as a package name (instead of a filename).

## License

2-clause [BSD](LICENSE.md).

Dynamic scoping based on [StackOverflow answer by Jason Orendorff (2010)](https://stackoverflow.com/questions/2001138/how-to-create-dynamical-scoped-variables-in-python), used under CC-BY-SA. The threading support is original to our version.

Core idea of `lispylet` based on [StackOverflow answer by divs1210 (2017)](https://stackoverflow.com/a/44737147), used under the MIT license.

## Acknowledgements

Thanks to [TUT](http://www.tut.fi/en/home) for letting me teach [RAK-19006 in spring term 2018](https://github.com/Technologicat/python-3-scicomp-intro); early versions of parts of this library were originally developed as teaching examples for that course. Thanks to @AgenttiX for feedback.

## Python-related FP resources

- [Awesome Functional Python](https://github.com/sfermigier/awesome-functional-python), especially a list of useful libraries. Some picks:

  - [fn.py: Missing functional features of fp in Python](https://github.com/fnpy/fn.py) (actively maintained fork). Includes e.g. tail call elimination by trampolining, and a very compact way to recursively define infinite streams.

  - [more-itertools: More routines for operating on iterables, beyond itertools.](https://github.com/erikrose/more-itertools)

  - [toolz: A functional standard library for Python](https://github.com/pytoolz/toolz)

  - [funcy](https://github.com/suor/funcy/)

  - [pyrsistent: Persistent/Immutable/Functional data structures for Python](https://github.com/tobgu/pyrsistent)

- [List of languages that compile to Python](https://github.com/vindarel/languages-that-compile-to-python) including Hy, a Lisp (in the [Lisp-2](https://en.wikipedia.org/wiki/Lisp-1_vs._Lisp-2) family) that can use Python libraries.

Old, but interesting:

- [Peter Norvig (2000): Python for Lisp Programmers](http://www.norvig.com/python-lisp.html)

- [David Mertz (2001): Charming Python - Functional programming in Python, part 2](https://www.ibm.com/developerworks/library/l-prog2/index.html)

