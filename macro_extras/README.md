# ``unpythonic.syntax``: macro extras

These optional features are built on [MacroPy](https://github.com/azazel75/macropy), from PyPI package ``macropy3``.

Because macro expansion occurs at import time, the usage example `main.py` cannot be run directly. Instead, run it via the bootstrap script `run.py`, or use the included [generic MacroPy3 bootstrapper](macropy3). Usage of the bootstrapper is `./macropy3 main`; see `-h` for options.

There is no abbreviation for ``memoize(lambda: ...)``, because ``MacroPy`` itself already provides ``lazy`` and ``interned``.

!! **Currently** (10/2018) this requires the latest MacroPy from git HEAD. !!

**Contents**:

 - [``curry``: Automatic currying for Python](#curry-automatic-currying-for-python)
 - [``let``, ``letseq``, ``letrec`` as macros](#let-letseq-letrec-as-macros)
 - [``cond``: the missing ``elif`` for ``a if p else b``](#cond-the-missing-elif-for-a-if-p-else-b)
 - [``aif``: anaphoric if](#aif-anaphoric-if)
 - [``do`` as a macro: stuff imperative code into a lambda, *with style*](#do-as-a-macro-stuff-imperative-code-into-a-lambda-with-style)
 - [``forall``: nondeterministic evaluation](#forall-nondeterministic-evaluation)
 - [``multilambda``: supercharge your lambdas](#multilambda-supercharge-your-lambdas); multiple expressions, local variables
 - [``namedlambda``: auto-name your lambdas](#namedlambda-auto-name-your-lambdas) (by assignment)
 - [``continuations``: a form of call/cc for Python](#continuations-a-form-of-callcc-for-python)
 - [``fup``: functionally update a sequence](#fup-functionally-update-a-sequence); with slice notation
 - [``prefix``: prefix function call syntax for Python](#prefix-prefix-function-call-syntax-for-python)


## ``curry``: Automatic currying for Python

```python
from unpythonic.syntax import macros, curry
from unpythonic import foldr, composerc as compose, cons, nil

with curry:
    mymap = lambda f: foldr(compose(cons, f), nil)
    double = lambda x: 2 * x
    print(mymap(double, (1, 2, 3)))
```

All function calls *lexically* inside a ``with curry`` block are automatically curried, somewhat like in Haskell, or in ``#lang`` [``spicy``](https://github.com/Technologicat/spicy).

**CAUTION**: Builtins are uninspectable, so cannot be curried. In a ``with curry`` block, ``unpythonic.fun.curry`` runs in a special mode that no-ops on uninspectable functions instead of raising ``TypeError`` as usual. This special mode is enabled for the *dynamic extent* of the ``with curry`` block.


## ``let``, ``letseq``, ``letrec`` as macros

Properly lexically scoped ``let`` constructs, no boilerplate:

```python
from unpythonic.syntax import macros, let, letseq, letrec

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

Syntax is similar to ``unpythonic.lispylet``, but no quotes around variable names in bindings, and no ``lambda e: ...`` wrappers. Bindings are referred to by bare names like in Lisps, no ``e.`` prefix. Assignment to variables in the environment is supported via the left-shift syntax ``x << 42``.

Note the ``[...]``; these are ``expr`` macros. The bindings are given as macro arguments as ``((name, value), ...)``, the body goes into the ``[...]``.

``let`` and ``letrec`` expand into the ``unpythonic.lispylet`` constructs, implicitly inserting ``lambda e: ...``, quoting variable names in definitions, and transforming ``x`` to ``e.x`` for all ``x`` declared in the bindings. Assignment syntax ``x << 42`` transforms to ``e.set('x', 42)``. The implicit environment argument ``e`` is actually named using a gensym, so lexically outer environments automatically show through. ``letseq`` expands into a chain of nested ``let`` expressions.

Nesting utilizes the fact that (as of v1.1.0) MacroPy3 expands macros in an inside-out order:

```python
letrec((z, 1))[[
         print(z),
         letrec((z, 2))[
                  print(z)]]]
```

Hence the ``z`` in the inner scope expands to the inner environment's ``z``, which makes the outer expansion leave it alone. (This works by transforming only ``ast.Name`` nodes, stopping recursion when an ``ast.Attribute`` is encountered.)

### Multiple expressions in body

As of `unpythonic` 0.9.2, the `let` constructs can now use a multiple-expression body. The syntax to activate multiple expression mode is an extra set of brackets around the body (like in `multilambda`; see below):

```python
let((x, 1),
    (y, 2))[[  # note extra [
      y << x + y,
      print(y)]]
```

The let macros implement this by inserting a ``do[...]`` (see below). In a multiple-expression body, also an internal definition context exists for local variables that are not part of the ``let``; see ``do`` for details.

Only the outermost set of extra brackets is interpreted as a multiple-expression body; the rest are interpreted as usual, as lists. If you need to return a literal list from a let with only one body expression, use three sets of brackets:

```python
let((x, 1),
    (y, 2))[[
      [x, y]]]
```

The outermost brackets delimit the ``let`` body, the middle ones activate multiple-expression mode, and the innermost ones denote a list.

Only brackets are affected; parentheses are interpreted as usual, so returning a literal tuple works as expected:

```python
let((x, 1),
    (y, 2))[
      (x, y)]
```

### Note

We also provide ``simple_let`` and ``simple_letseq``, wholly implemented as AST transformations, providing true lexical variables but no assignment support (because in Python, assignment is a statement) or multi-expression body support. Just like in Lisps, ``simple_letseq`` (Scheme/Racket ``let*``) expands into a chain of nested ``simple_let`` expressions, which expand to lambdas.


## ``cond``: the missing ``elif`` for ``a if p else b``

Now lambdas too can have multi-branch conditionals, yet remain human-readable:

```python
from unpythonic.syntax import macros, cond

answer = lambda x: cond[x == 2, "two",
                        x == 3, "three",
                        "something else"]
print(answer(42))
```

Syntax is ``cond[test1, then1, test2, then2, ..., otherwise]``. Expansion raises an error if the ``otherwise`` branch is missing.


## ``aif``: anaphoric if

This is mainly of interest as a point of [comparison with Racket](https://github.com/Technologicat/python-3-scicomp-intro/blob/master/examples/beyond_python/aif.rkt); ``aif`` is about the simplest macro that relies on either the lack of hygiene or breaking thereof.

```python
from unpythonic.syntax import macros, aif

aif[2*21,
    print("it is {}".format(it)),
    print("it is False")]
```

Syntax is ``aif[test, then, otherwise]``. The magic identifier ``it`` refers to the test result while (lexically) inside the ``aif``, and does not exist outside the ``aif``.


## ``do`` as a macro: stuff imperative code into a lambda, *with style*

We provide an ``expr`` macro wrapper for ``unpythonic.seq.do``, with some extra features.

This essentially allows writing imperative code in any expression position. For an `if-elif-else` conditional, see `cond`; for loops, see the functions in `unpythonic.fploop` (esp. `looped`).

```python
from unpythonic.syntax import macros, do

y = do[localdef(x << 17),
       print(x),
       x << 23,
       x]
print(y)  # --> 23
```

Local variables are declared and initialized with ``localdef(var << value)``, where ``var`` is a bare name. To explicitly denote "no value", just use ``None``. Currently it does not matter where the ``localdef`` appears inside the ``do``; it captures the declared name as a local variable **for the whole lexical scope** of the ``do``, including any references to that name **before** the ``localdef``. (This is subject to change in a future version.) For readability and future-proofness, it is recommended to place localdefs at or near the start of the do-block, at the first use of each local name.

Already declared local variables are updated with ``var << value``. Updating variables in lexically outer environments (e.g. a ``let`` surrounding a ``do``) uses the same syntax.

The reason we require local variables to be declared is to allow write access to lexically outer environments.

Assignments are recognized anywhere inside the ``do``; but note that any ``let`` constructs nested *inside* the ``do``, that define variables of the same name, will (inside the ``let``) shadow those of the ``do`` - as expected of lexical scoping.

Like in the macro ``letrec``, no ``lambda e: ...`` wrappers. These are inserted automatically, so the lines are only evaluated as the underlying ``seq.do`` actually runs.

When running, ``do`` behaves like ``letseq``; assignments **above** the current line are in effect (and have been performed in the order presented). Re-assigning to the same name later overwrites (this is afterall an imperative tool).

There is also a ``do0`` macro, which returns the value of the first expression, instead of the last.


## ``forall``: nondeterministic evaluation

This is the multiple-body-expression tuple comprehension ``unpythonic.amb.forall``, wrapped into a macro:

```python
from unpythonic.syntax import macros, forall, insist, deny

out = forall[y << range(3),
             x << range(3),
             insist(x % 2 == 0),
             (x, y)]
assert out == ((0, 0), (2, 0), (0, 1), (2, 1), (0, 2), (2, 2))

# pythagorean triples
pt = forall[z << range(1, 21),   # hypotenuse
            x << range(1, z+1),  # shorter leg
            y << range(x, z+1),  # longer leg
            insist(x*x + y*y == z*z),
            (x, y, z)]
assert tuple(sorted(pt)) == ((3, 4, 5), (5, 12, 13), (6, 8, 10),
                             (8, 15, 17), (9, 12, 15), (12, 16, 20))
```

Assignment (with List-monadic magic) is ``var << iterable``. It transforms to ``choice(var=lambda e: iterable)``. It is only valid at the top level of the ``forall`` (e.g. not inside any possibly nested ``let``).

No need for ``lambda e: ...`` wrappers; variables are referred to by bare names without the ``e.`` prefix.

``insist`` and ``deny`` are not really macros; they are just the functions from ``unpythonic.amb``, re-exported for convenience.

### Note

We also provide ``forall_simple``, based purely on AST transformation, with real lexical variables. This is essentially Haskell's do-notation for Python, specialized to the List monad.

In the future, we may replace the current ``forall`` macro with this version. From the user perspective, the only difference is in error reporting; the function-based ``forall`` must internally simulate lexical scoping, whereas ``forall_simple`` just borrows Python's. In the function-based version, an undefined name will raise ``AttributeError``, whereas in ``forall_simple``, it will raise ``NameError``.


## ``multilambda``: supercharge your lambdas

**Multiple expressions**: use ``[...]`` to denote a multiple-expression body. The macro implements this by inserting a ``do``.

**Local variables**: available in a multiple-expression body. For details on usage, see ``do``.

```python
from unpythonic.syntax import macros, multilambda, let

with multilambda:
    echo = lambda x: [print(x), x]
    assert echo("hi there") == "hi there"

    count = let((x, 0))[
              lambda: [x << x + 1,  # x belongs to the surrounding let
                       x]]
    assert count() == 1
    assert count() == 2

    test = let((x, 0))[
             lambda: [x << x + 1,
                      localdef(y << 42),  # y is local to the implicit do
                      (x, y)]]
    assert test() == (1, 42)
    assert test() == (2, 42)

    myadd = lambda x, y: [print("myadding", x, y),
                          localdef(tmp << x + y),
                          print("result is", tmp),
                          tmp]
    assert myadd(2, 3) == 5

    # only the outermost set of brackets denote a multi-expr body:
    t = lambda: [[1, 2]]
    assert t() == [1, 2]
```

In the second example, returning ``x`` separately is redundant, because the assignment to the let environment already returns the new value, but it demonstrates the usage of multiple expressions in a lambda.


## ``namedlambda``: auto-name your lambdas

Who said lambdas have to be anonymous?

```python
from unpythonic.syntax import macros, namedlambda

with namedlambda:
    f = lambda x: x**3                       # lexical rule: name as "f"
    assert f.__name__ == "f (lambda)"
    gn, hn = let((x, 42), (g, None), (h, None))[[
                   g << (lambda x: x**2),    # dynamic rule: name as "g"
                   h << f,                   # no-rename rule: still "f"
                   (g.__name__, h.__name__)]]
    assert gn == "g (lambda)"
    assert hn == "f (lambda)"
```

This is a block macro that supports both simple assignment statements of the form ``f = lambda ...: ...``, and ``<<`` expression assignments to ``unpythonic`` environments.

All simple assignment statements lexically within the block, that assign a single lambda to a single name, will get code injected at macro-expansion time, to set the name of the resulting function object to the name the lambda is being assigned to.

Assignment in unpythonic environments is tracked dynamically at run-time, for the dynamic extent of the block. This is done by setting the dynvar ``env_namedlambda`` to ``True``, by injecting a ``with dyn.let(env_namedlambda=True):`` around the block.

For any function object instance representing a lambda, it takes the first name given to it, and keeps that; there is no renaming. See the function ``unpythonic.misc.namelambda``, which this uses internally.


## ``continuations``: a form of call/cc for Python

This is a loose pythonification of Paul Graham's continuation-passing macros, chapter 20 in [On Lisp](http://paulgraham.com/onlisp.html).

Perhaps a demonstration is the best explanation:

```python
from unpythonic.syntax import macros, continuations, bind

with continuations:
    # basic example - how to call a continuation manually:
    k = None  # kontinuation
    def setk(*args, cc):
        global k
        k = cc
        xs = list(args)
        return xs
    def doit(*, cc):
        lst = ['the call returned']
        with bind[setk('A')] as more:  # <-- essentially call/cc
            return lst + more          # ...with the body containing the continuation
    print(doit())
    print(k(['again']))
    print(k(['thrice', '!']))

    # McCarthy's amb operator - yes, the real thing - in Python:
    stack = []
    def amb(lst, *, cc):
        if not lst:
            return fail()
        first, *rest = lst
        if rest:
            ourcc = cc
            stack.append(lambda *, cc: amb(rest, cc=ourcc))
        return first
    def fail(*, cc):
        if stack:
            f = stack.pop()
            return f()

    # Pythagorean triples.
    def pt(*, cc):
        with bind[amb(tuple(range(1, 21)))] as z:
            with bind[amb(tuple(range(1, z+1)))] as y:
                with bind[amb(tuple(range(1, y+1)))] as x:
                    if x*x + y*y != z*z:
                        return fail()
                    return x, y, z
    print(pt())
    print(fail())  # ...outside the dynamic extent of pt()!
    print(fail())
    print(fail())
    print(fail())
    print(fail())
    print(fail())
```

Code within a ``with continuations`` block is treated specially. Roughly:

 - Each function definition (``def`` or ``lambda``) in a ``with continuations`` block must take a by-name-only parameter ``cc``.
   - It is a named parameter, so that we may inject a default value, to allow these functions to be called also normally without passing a ``cc``.
   - To keep things somewhat pythonic, the parameter must be spelled out explicitly even though it gets its value implicitly, just like ``self`` in object-oriented Python code.

 - In a function definition inside the block:
   - Most of the language works as usual; especially, any non-tail function calls can be made as usual.
   - ``return value`` or ``return v0, ..., vn`` actually tail-calls ``cc`` with the given value(s).
     - As in other parts of ``unpythonic``, returning a tuple means returning multiple-values. (This is important if the return value is received by the as-part of a ``with bind``.)
   - ``return func(...)`` actually tail-calls ``func``, passing on (by default) the current value of ``cc`` to become its ``cc``.
     - Hence, the tail call is inserted between the end of the current function and the invocation of ``cc``.
     - To use some other continuation, specify the ``cc=...`` kwarg, as in ``return func(..., cc=mycc)``.
     - The function ``func`` must be a defined in a ``with continuations`` block, so that it knows what to do with ``cc``.
       - Attempting to tail-call a regular function breaks the TCO chain and immediately returns to the original caller (provided the function even accepts a ``cc`` named parameter).
       - Hence, be careful: ``xs = list(args); return xs`` and ``return list(args)`` mean different things.
   - TCO, from ``unpythonic.fasttco``, is automatically applied to these tail calls.

 - Essentially, ``with bind`` is a limited form of ``call/cc``, where the body of the ``with`` block is captured as the continuation.
   - Unlike in Scheme/Racket, where continuations are built into the language itself, and the remaining expressions of the computation are in a sense captured automatically.
   - Unlike in Scheme, manually calling a continuation won't replace the whole call stack - it just runs the remaining part of the computation and returns the result. Hence in the first example above, ``1 + k(['something'])`` would be an error, whereas Scheme would throw away the pending ``1 +``, because it's not part of the continuation, and return just the result of ``k(['something'])``.
   - A first-class reference to the captured continuation is available in the function called by ``with bind``, as its ``cc`` argument.
     - The continuation is a function that takes as many positional arguments as there are names in the as-part of the ``with bind``. Additionally, it may take a named argument ``cc``.
       - If there are multiple names, **parentheses are mandatory**, due to the syntax of Python's ``with`` statement.
       - The body is technically a function; it gets its own ``cc``.
     - Basically everywhere else, ``cc`` points to the identity function - the default continuation just returns its arguments.
   - Inside a ``def``, ``with bind`` generates a tail call, terminating the function. Any code the function needs to run after the ``with bind`` must be placed in the body of the ``with bind``. The return value of the function is the return value of the body.
   - At the top level, ``with bind`` generates a normal call. In this case is not possible to capture the return value of the body the first time it runs, because ``with`` is a statement.

For more details, see the docstring of ``unpythonic.syntax.continuations``.

### Combo notes

If you need both ``continuations`` and ``multilambda`` simultaneously, the incantation is:

```python
with multilambda, continuations:
    f = lambda x, *, cc: [print(x), x**2]
    assert f(42) == 1764
```

The way this works is that ``continuations`` knows what ``multilambda`` does; it must, to correctly deduce which expressions are return values in tail position.

We have chosen the implementation where ``continuations`` works with input that has already been transformed by ``multilambda``. This is safer, because there is no risk to misinterpret a list in a lambda body, and it works also for any explicit use of ``do[]`` in a lambda body or in a ``return`` (recall that macros expand from inside out).

### Is this useful?

For most use cases, probably not, because we could just:

```python
def pt_gen():
    for z in range(1, 21):
        for y in range(1, z+1):
            for x in range(1, y+1):
                if x*x + y*y != z*z:
                    continue
                yield x, y, z
print(tuple(pt_gen()))
```

Generators already provide suspend-and-resume. Similarly to ``fail()`` above, here too ``next()`` can be called on the ``pt_gen`` instance after it has suspended itself at the ``yield``.

Finally, as a side note, generators [can be easily built](https://github.com/Technologicat/python-3-scicomp-intro/blob/master/examples/beyond_python/generator.rkt) on top of ``call/cc``.


## ``fup``: functionally update a sequence

This is a macro wrapper for ``unpythonic.fup.fupdate``, providing more natural syntax:

```python
from unpythonic.syntax import macros, fup
from itertools import repeat

lst = (1, 2, 3, 4, 5)
assert fup[lst[3] << 42] == (1, 2, 3, 42, 5)
assert fup[lst[0::2] << tuple(repeat(10, 3))] == (10, 2, 10, 4, 10)
```

Currently only one update specification is supported in a single ``fup[]``.

The notation follows the ``unpythonic.syntax`` convention that ``<<`` denotes an assignment of some sort. Here it denotes a functional update, which returns a modified copy, leaving the original untouched.

The transformation is ``fup[seq[idx] << value] --> fupdate(seq, idx, value)`` for a single index, and ``fup[seq[slicestx] << iterable] --> fupdate(seq, slice(...), iterable)`` for a slice. The main point of this macro is that slices are specified in the native slicing syntax (instead of by manually calling ``slice``, like when directly using the underlying ``fupdate`` function).


## ``prefix``: prefix function call syntax for Python

Write Python almost like Lisp!

Lexically inside a ``with prefix`` block, any literal tuple denotes a function call, unless quoted. The first element is the operator, the rest are arguments.

The rest is best explained by example:

```python
from unpythonic.syntax import macros, prefix, q, u, kw
from unpythonic import apply

with prefix:
    (print, "hello world")

    # quote operator q locally turns off the function-call transformation:
    t1 = (q, 1, 2, (3, 4), 5)  # q takes effect recursively
    x = 42
    t2 = (q, 17, 23, x)  # unlike in Lisps, x refers to its value even in a quote
    (print, t1, t2)

    # unquote operator u locally turns the transformation back on:
    t3 = (q, (u, print, 42), (print, 42), "foo", "bar")
    assert t3 == (q, None, (print, 42), "foo", "bar")

    # quotes nest; call transformation made when quote level == 0
    t4 = (q, (print, 42), (q, (u, u, print, 42)), "foo", "bar")
    assert t4 == (q, (print, 42), (None,), "foo", "bar")

    # Be careful:
    try:
        (x,)  # in a prefix block, this means "call the 0-arg function x"
    except TypeError:
        pass  # 'int' object is not callable
    (q, x)  # OK!

    # give named args with kw(...) [it's syntax, not really a function!]:
    def f(*, a, b):
        return (q, a, b)
    # in one kw(...), or...
    assert (f, kw(a="hi there", b="Tom")) == (q, "hi there", "Tom")
    # in several kw(...), doesn't matter
    assert (f, kw(a="hi there"), kw(b="Tom")) == (q, "hi there", "Tom")
    # in case of duplicate name across kws, rightmost wins
    assert (f, kw(a="hi there"), kw(b="Tom"), kw(b="Jerry")) == (q, "hi there", "Jerry")

    # give *args with unpythonic.fun.apply, like in Lisps:
    lst = [1, 2, 3]
    def g(*args):
        return args
    assert (apply, g, lst) == (q, 1, 2, 3)
    # lst goes last; may have other args first
    assert (apply, g, "hi", "ho", lst) == (q, "hi" ,"ho", 1, 2, 3)
```

This comboes with ``curry`` for an authentic *LisThEll* programming experience:

```python
from unpythonic.syntax import macros, curry, prefix, q, u, kw
from unpythonic import foldr, composerc as compose, cons, nil

with prefix, curry:  # important: apply prefix first, then curry
    mymap = lambda f: (foldr, (compose, cons, f), nil)
    double = lambda x: 2 * x
    (print, (mymap, double, (q, 1, 2, 3)))
    assert (mymap, double, (q, 1, 2, 3)) == ll(2, 4, 6)
```

*Toto, I've a feeling we're not in Python anymore.*

