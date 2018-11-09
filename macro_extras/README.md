# ``unpythonic.syntax``: macro extras

These optional features are built on [MacroPy](https://github.com/azazel75/macropy), from PyPI package ``macropy3``.

Because macro expansion occurs at import time, the unit tests that contain usage examples (located in [unpythonic/syntax/test/](unpythonic/syntax/test/)) cannot be run directly. Instead, run them via the included [generic MacroPy3 bootstrapper](macropy3). Usage of the bootstrapper is `./macropy3 some.module` (like `python3 -m some.module`); see `-h` for options.

The tests use relative imports; invoke them from the top-level directory of ``unpythonic`` as e.g. ``macro_extras/macropy3 unpythonic.syntax.test.test_curry``. This is to make the tests run against the source tree without installing it first; in your own code, once you have installed ``unpythonic``, feel free to use absolute imports, like those shown in this README.

There is no abbreviation for ``memoize(lambda: ...)``, because ``MacroPy`` itself already provides ``lazy`` and ``interned``.

!! **Currently** (10/2018) this requires the latest MacroPy from git HEAD. !!

**Contents**:

 - [``curry``: Automatic currying for Python](#curry-automatic-currying-for-python)
 - [``let``, ``letseq``, ``letrec`` as macros](#let-letseq-letrec-as-macros); proper lexical scoping, no boilerplate
   - [``dlet``, ``dletseq``, ``dletrec``, ``blet``, ``bletseq``, ``bletrec``: decorator versions](#dlet-dletseq-dletrec-blet-bletseq-bletrec-decorator-versions)
   - [``let_syntax``, ``abbrev``: syntactic local bindings](#let_syntax-abbrev-syntactic-local-bindings); splice code at macro expansion time
 - [``cond``: the missing ``elif`` for ``a if p else b``](#cond-the-missing-elif-for-a-if-p-else-b)
 - [``aif``: anaphoric if](#aif-anaphoric-if)
 - [``do`` as a macro: stuff imperative code into a lambda, *with style*](#do-as-a-macro-stuff-imperative-code-into-a-lambda-with-style)
 - [``forall``: nondeterministic evaluation](#forall-nondeterministic-evaluation)
 - [``multilambda``: supercharge your lambdas](#multilambda-supercharge-your-lambdas); multiple expressions, local variables
 - [``namedlambda``: auto-name your lambdas](#namedlambda-auto-name-your-lambdas) (by assignment)
 - [``continuations``: a form of call/cc for Python](#continuations-a-form-of-callcc-for-python)
 - [``tco``: automatically apply tail call optimization](#tco-automatically-apply-tail-call-optimization)
   - [TCO and continuations](#tco-and-continuations)
 - [``autoreturn``: implicit ``return`` in tail position](#autoreturn-implicit-return-in-tail-position)
 - [``fup``: functionally update a sequence](#fup-functionally-update-a-sequence); with slice notation
 - [``prefix``: prefix function call syntax for Python](#prefix-prefix-function-call-syntax-for-python)

Meta:

 - [Comboability](#comboability): notes on the macros working together


## ``curry``: Automatic currying for Python

```python
from unpythonic.syntax import macros, curry
from unpythonic import foldr, composerc as compose, cons, nil

with curry:
    def add3(a, b, c):
        return a + b + c
    assert add3(1)(2)(3) == 6
    assert add3(1, 2)(3) == 6
    assert add3(1)(2, 3) == 6
    assert add3(1, 2, 3) == 6

    mymap = lambda f: foldr(compose(cons, f), nil)
    double = lambda x: 2 * x
    print(mymap(double, (1, 2, 3)))

# The definition was auto-curried, so this works here too.
# (Provided add3 contains no calls to uninspectable functions, since
#  we are now outside the dynamic extent of the ``with curry`` block.)
assert add3(1)(2)(3) == 6
```

All **function calls** and **function definitions** (``def``, ``lambda``) *lexically* inside a ``with curry`` block are automatically curried, somewhat like in Haskell, or in ``#lang`` [``spicy``](https://github.com/Technologicat/spicy).

**CAUTION**: Some builtins are uninspectable or may report their arities incorrectly; in those cases, ``curry`` may fail, occasionally in mysterious ways. The function ``unpythonic.arity.arities``, which ``unpythonic.fun.curry`` internally uses, has a workaround for the inspectability problems of all builtins in the top-level namespace (as of Python 3.7), but e.g. methods of builtin types are not handled.

In a ``with curry`` block, ``unpythonic.fun.curry`` runs in a special mode that no-ops on uninspectable functions instead of raising ``TypeError`` as usual. This special mode is enabled for the *dynamic extent* of the ``with curry`` block.


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

As seen in the examples, the syntax is similar to ``unpythonic.lispylet``. Assignment to variables in the environment is supported via the left-shift syntax ``x << 42``.

Note the ``[...]``; these are ``expr`` macros. The bindings are given as macro arguments as ``((name, value), ...)``, the body goes into the ``[...]``.

``let`` and ``letrec`` expand into the ``unpythonic.lispylet`` constructs, implicitly inserting the necessary boilerplate: the ``lambda e: ...`` wrappers, quoting variable names in definitions, and transforming ``x`` to ``e.x`` for all ``x`` declared in the bindings. Assignment syntax ``x << 42`` transforms to ``e.set('x', 42)``. The implicit environment argument ``e`` is actually named using a gensym, so lexically outer environments automatically show through. ``letseq`` expands into a chain of nested ``let`` expressions.

Nesting utilizes the fact that MacroPy3 (as of v1.1.0) expands macros in an inside-out order:

```python
letrec((z, 1))[[
         print(z),
         letrec((z, 2))[
                  print(z)]]]
```

Hence the ``z`` in the inner scope expands to the inner environment's ``z``, which makes the outer expansion leave it alone. (This works by transforming only ``ast.Name`` nodes, stopping recursion when an ``ast.Attribute`` is encountered.)

### Multiple expressions in body

*Added in v0.9.2.* The `let` constructs can now use a multiple-expression body. The syntax to activate multiple expression mode is an extra set of brackets around the body (like in `multilambda`; see below):

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

We also provide classical simple ``let`` and ``letseq``, wholly implemented as AST transformations, providing true lexical variables but no assignment support (because in Python, assignment is a statement) or multi-expression body support. Just like in Lisps, this version of ``letseq`` (Scheme/Racket ``let*``) expands into a chain of nested ``let`` expressions, which expand to lambdas.

These are however not meant to work together with the rest of the macros; for that, use the above ``let``, ``letseq`` and ``letrec`` from the module ``unpythonic.syntax``.

*Changed in v0.11.0.* These additional constructs now live in the separate module ``unpythonic.syntax.simplelet``, and are imported like ``from unpythonic.syntax.simplelet import macros, let, letseq``.

### ``dlet``, ``dletseq``, ``dletrec``, ``blet``, ``bletseq``, ``bletrec``: decorator versions

*Added in v0.10.4.* Similarly to ``let``, ``letseq``, ``letrec``, these are sugar around the corresponding ``unpythonic.lispylet`` constructs, with the ``dletseq`` and ``bletseq`` constructs existing only as macros (they expand to nested ``dlet`` or ``blet``, respectively).

Lexical scoping is respected; each environment is internally named using a gensym. Nesting is allowed.

Examples:

```python
from unpythonic.syntax import macros, dlet, dletseq, dletrec, blet, bletseq, bletrec

@dlet((x, 0))
def count():
    x << x + 1
    return x
assert count() == 1
assert count() == 2

@dletrec((evenp, lambda x: (x == 0) or oddp(x - 1)),
         (oddp,  lambda x: (x != 0) and evenp(x - 1)))
def f(x):
    return evenp(x)
assert f(42) is True
assert f(23) is False

@dletseq((x, 1),
         (x, x+1),
         (x, x+2))
def g(a):
    return a + x
assert g(10) == 14

# block versions: the def takes no arguments, runs immediately, and is replaced by the return value.
@blet((x, 21))
def result():
    return 2*x
assert result == 42

@bletrec((evenp, lambda x: (x == 0) or oddp(x - 1)),
         (oddp,  lambda x: (x != 0) and evenp(x - 1)))
def result():
    return evenp(42)
assert result is True

@bletseq((x, 1),
         (x, x+1),
         (x, x+2))
def result():
    return x
assert result == 4
```

**CAUTION**: assignment to the let environment uses the syntax ``name << value``, as always with ``unpythonic`` environments. The standard Python syntax ``name = value`` creates a local variable, as usual - *shadowing any variable with the same name from the ``let``*.

The write of a ``name << value`` always occurs to the lexically innermost environment (as seen from the write site) that has that ``name``. If no lexically surrounding environment has that ``name``, *then* the expression remains untransformed, and means a left-shift (if ``name`` happens to be otherwise defined).

**CAUTION**: formal parameters of a function definition, local variables, and any names declared as ``global`` or ``nonlocal`` in a given lexical scope shadow names from the ``let`` environment. Mostly, this applies *to the entirety of that lexical scope*. This is modeled after Python's standard scoping rules.

As an exception to the rule, for the purposes of the scope analysis performed by ``unpythonic.syntax``, creations and deletions *of lexical local variables* take effect from the next statement, and remain in effect for the **lexically** remaining part of the current scope. This allows ``x = ...`` to see the old bindings on the RHS, as well as allows the client code to restore access to a surrounding env's ``x`` (by deleting a local ``x`` shadowing it) when desired.

Note that this behaves differently from Python itself, where everything is dynamic. This is essentially because ``unpythonic.syntax`` needs to resolve references to env variables statically, at compile time.

To clarify, here's a sampling from the unit tests:

```python
@dlet((x, "the env x"))
def f():
    return x
assert f() == "the env x"

@dlet((x, "the env x"))
def f():
    x = "the local x"
    return x
assert f() == "the local x"

@dlet((x, "the env x"))
def f():
    return x
    x = "the unused local x"
assert f() == "the env x"

x = "the global x"
@dlet((x, "the env x"))
def f():
    global x
    return x
assert f() == "the global x"

@dlet((x, "the env x"))
def f():
    x = "the local x"
    del x           # deleting a local, ok!
    return x
assert f() == "the env x"

try:
    x = "the global x"
    @dlet((x, "the env x"))
    def f():
        global x
        del x       # ignored by unpythonic's scope analysis, deletion of globals is too dynamic
        return x    # trying to refer to the deleted global x
    f()
except NameError:
    pass
else:
    assert False, "should have tried to access the deleted global x"
```

### ``let_syntax``, ``abbrev``: syntactic local bindings

*Added in v0.11.0.* Locally splice code at macro expansion time:

```python
from unpythonic.syntax import macros, let_syntax, block, expr

def verylongfunctionname(x=1):
    return x

# works as an expr macro
y = let_syntax((f, verylongfunctionname))[[  # extra brackets: implicit do in body
                 print(f()),
                 f(5)]]
assert y == 5

y = let_syntax((f(a), verylongfunctionname(2*a)))[[
                 print(f(2)),
                 f(3)]]
assert y == 6

# works as a block macro
with let_syntax:
    with block(a, b, c) as makeabc:  # capture a block of statements
        lst = [a, b, c]
    makeabc(3 + 4, 2**3, 3 * 3)
    assert lst == [7, 8, 9]
    with expr(n) as nth:             # capture a single expression
        lst[n]
    assert nth(2) == 9

with let_syntax:
    with block(a) as twice:
        a
        a
    with block(x, y, z) as appendxyz:
        lst += [x, y, z]
    lst = []
    twice(appendxyz(7, 8, 9))
    assert lst == [7, 8, 9]*2
```

After macro expansion completes, ``let_syntax`` has zero runtime overhead; it completely disappears in macro expansion.

There are two kinds of substitutions: *bare name* and *template*. A bare name substitution has no parameters. A template substitution has positional parameters. (Named parameters, ``*args``, ``**kwargs`` and default values are currently **not** supported.)

In the body of ``let_syntax``, a bare name substitution is invoked by name (just like a variable). A template substitution is invoked like a function call. Just like in an actual function call, when the template is substituted, any instances of its formal parameters in the definition get replaced by the argument values from the "call" site; but ``let_syntax`` performs this at macro-expansion time, and the "value" is a snippet of code.

Note each instance of the same formal parameter (in the definition) gets a fresh copy of the corresponding argument value. In other words, in the example above, each ``a`` in the body of ``twice`` separately expands to a copy of whatever code was given as the positional argument ``a``.

When used as a block macro, there are furthermore two capture modes: *block of statements*, and *single expression*. (The single expression can be an explicit ``do[]`` if multiple expressions are needed.) When invoking substitutions, keep in mind Python's usual rules regarding where statements or expressions may appear.

(If you know about Python ASTs, don't worry about the ``ast.Expr`` wrapper needed to place an expression in a statement position; this is handled automatically.)

**HINT**: If you get a compiler error that an ``If`` was encountered where an expression was expected, check your uses of ``let_syntax``. The most likely reason is that a substitution is trying to splice a block of statements into an expression position. A captured block of statements internally generates an ``if 1:`` (so that the block may replace a single statement), which the Python compiler optimizes away; this is the ``If`` node referred to by the error message.

Expansion of ``let_syntax`` is a two-step process:

  - First, template substitutions.
  - Then, bare name substitutions, applied to the result of the first step.

This design is to avoid accidental substitutions of formal parameters of templates (that would usually break the template, resulting at best in a mysterious error, and at worst silently doing something unexpected), if the name of a formal parameter happens to match one of the currently active bare name substitutions.

Within each step, the substitutions are applied **in definition order**:

  - If the bindings are ``((x, y), (y, z))``, then an ``x`` at the use site transforms to ``z``. So does a ``y`` at the use site.
  - But if the bindings are ``((y, z), (x, y))``, then an ``x`` at the use site transforms to ``y``, and only an explicit ``y`` at the use site transforms to ``z``.

Even in block templates, parameters are always expressions, because invoking a template uses the function-call syntax. But names and calls are expressions, so a previously defined substitution (whether bare name or an invocation of a template) can be passed as an argument just fine. Definition order is then important; consult the rules above.

It is allowed to nest ``let_syntax``, with lexical scoping (inner definitions of substitutions shadow outer ones).

When used as an expr macro, all bindings are registered first, and then the body is evaluated. When used as a block macro, a new binding (substitution declaration) takes effect from the next statement onward, and remains active for the lexically remaining part of the ``with let_syntax:`` block.

The ``abbrev`` macro is otherwise exactly like ``let_syntax``, but it expands in the first pass (outside in). Hence, no lexically scoped nesting, but it has the power to locally rename also macros, because the ``abbrev`` itself expands before any macros invoked in its body. This allows things like:

```python
abbrev((a, ast_literal))[
         a[tree1] if a[tree2] else a[tree3]]
```

which can be useful when writing macros.

**CAUTION**: ``let_syntax`` is essentially a toy macro system within the real macro system. The usual caveats of macro systems apply. Especially, we support absolutely no form of hygiene. Be very, very careful to avoid name conflicts.

Inessential repetition is often introduced by syntactic constraints. The ``let_syntax`` macro is meant for simple local substitutions where the elimination of such repetition can shorten the code and improve its readability.

If you need to do something complex (or indeed save a definition and reuse it somewhere else, non-locally), write a real macro directly in MacroPy.

This was inspired by Racket's [``let-syntax``](https://docs.racket-lang.org/reference/let.html) and [``with-syntax``](https://docs.racket-lang.org/reference/stx-patterns.html).


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

*Added in v0.10.0.* Any part of ``cond`` may have multiple expressions by surrounding it with brackets:

```python
cond[[pre1, ..., test1], [post1, ..., then1],
     [pre2, ..., test2], [post2, ..., then2],
     ...
     [postn, ..., otherwise]]
```

To denote a single expression that is a literal list, use an extra set of brackets: ``[[1, 2, 3]]``.


## ``aif``: anaphoric if

This is mainly of interest as a point of [comparison with Racket](https://github.com/Technologicat/python-3-scicomp-intro/blob/master/examples/beyond_python/aif.rkt); ``aif`` is about the simplest macro that relies on either the lack of hygiene or breaking thereof.

```python
from unpythonic.syntax import macros, aif

aif[2*21,
    print("it is {}".format(it)),
    print("it is False")]
```

Syntax is ``aif[test, then, otherwise]``. The magic identifier ``it`` refers to the test result while (lexically) inside the ``aif``, and does not exist outside the ``aif``.

*Added in v0.10.0.* Any part of ``aif`` may have multiple expressions by surrounding it with brackets:

```python
aif[[pre, ..., test],
    [post_true, ..., then],        # "then" branch
    [post_false, ..., otherwise]]  # "otherwise" branch
```

To denote a single expression that is a literal list, use an extra set of brackets: ``[[1, 2, 3]]``.


## ``do`` as a macro: stuff imperative code into a lambda, *with style*

We provide an ``expr`` macro wrapper for ``unpythonic.seq.do``, with some extra features.

This essentially allows writing imperative code in any expression position. For an `if-elif-else` conditional, see `cond`; for loops, see the functions in `unpythonic.fploop` (esp. `looped`).

```python
from unpythonic.syntax import macros, do

y = do[local(x << 17),
       print(x),
       x << 23,
       x]
print(y)  # --> 23
```

*Changed in v0.11.0.* ``localdef(...)`` is now just ``local(...)``. Shorter, and more descriptive, as it defines a local name, not a function.

Local variables are declared and initialized with ``local(var << value)``, where ``var`` is a bare name. To explicitly denote "no value", just use ``None``.  A ``local`` declaration comes into effect in the expression following the one where it appears, capturing the declared name as a local variable for the **lexically** remaining part of the ``do``. In a ``local``, the RHS still sees the previous bindings, so this is valid (although maybe not readable):

```python
result = []
let((lst, []))[[result.append(lst),       # the let "lst"
                local(lst << lst + [1]),  # LHS: do "lst", RHS: let "lst"
                result.append(lst)]]      # the do "lst"
assert result == [[], [1]]
```

Already declared local variables are updated with ``var << value``. Updating variables in lexically outer environments (e.g. a ``let`` surrounding a ``do``) uses the same syntax.

The reason we require local variables to be declared is to allow write access to lexically outer environments.

Assignments are recognized anywhere inside the ``do``; but note that any ``let`` constructs nested *inside* the ``do``, that define variables of the same name, will (inside the ``let``) shadow those of the ``do`` - as expected of lexical scoping.

The necessary boilerplate (notably the ``lambda e: ...`` wrappers) is inserted automatically, so the expressions in a ``do[]`` are only evaluated when the underlying ``seq.do`` actually runs.

When running, ``do`` behaves like ``letseq``; assignments **above** the current line are in effect (and have been performed in the order presented). Re-assigning to the same name later overwrites (this is afterall an imperative tool).

There is also a ``do0`` macro, which returns the value of the first expression, instead of the last.


## ``forall``: nondeterministic evaluation

*Changed in v0.11.0.* The previous ``forall_simple`` has been renamed ``forall``; the macro wrapper for the hacky function version of ``forall`` is gone. This change has the effect of changing the error raised by an undefined name in a ``forall`` section; previously it was ``AttributeError``, now it is ``NameError``.

Behaves the same as the multiple-body-expression tuple comprehension ``unpythonic.amb.forall``, but implemented purely by AST transformation, with real lexical variables. This is essentially Haskell's do-notation for Python, specialized to the List monad.

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

``insist`` and ``deny`` are not really macros; they are just the functions from ``unpythonic.amb``, re-exported for convenience.


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
                      local(y << 42),  # y is local to the implicit do
                      (x, y)]]
    assert test() == (1, 42)
    assert test() == (2, 42)

    myadd = lambda x, y: [print("myadding", x, y),
                          local(tmp << x + y),
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

This is a block macro that supports both simple assignment statements of the form ``f = lambda ...: ...``, and ``name << (lambda ...: ...)`` expression assignments to ``unpythonic`` environments.

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
   - TCO is automatically applied to these tail calls.

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

**CAUTION**: Do not combo with ``tco``; the ``continuations`` block already implies TCO.

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


## ``tco``: automatically apply tail call optimization

```python
from unpythonic.syntax import macros, tco

with tco:
    evenp = lambda x: (x == 0) or oddp(x - 1)
    oddp  = lambda x: (x != 0) and evenp(x - 1)
    assert evenp(10000) is True

with tco:
    def evenp(x):
        if x == 0:
            return True
        return oddp(x - 1)
    def oddp(x):
        if x != 0:
            return evenp(x - 1)
        return False
    assert evenp(10000) is True
```

All function definitions (``def`` and ``lambda``) lexically inside the block undergo TCO transformation. The functions are automatically ``@trampolined``, and any tail calls in their return values are converted to ``jump(...)`` for the TCO machinery. Here *return value* is defined as:

 - In a ``def``, the argument expression of ``return``, or of a call to an escape continuation.

 - In a ``lambda``, the whole body, as well as the argument expression of a call to an escape continuation.

To find the tail position inside a compound return value, this recursively handles any combination of ``a if p else b``, ``and``, ``or``; and from ``unpythonic.syntax``, ``do[]``, ``let[]``, ``letseq[]``, ``letrec[]``. Support for ``do[]`` includes also any ``multilambda`` blocks that have already expanded when ``tco`` is processed. The macros ``aif[]`` and ``cond[]`` are also supported, because they expand into a combination of ``let[]``, ``do[]``, and ``a if p else b``.

**CAUTION**: In an ``and``/``or`` expression, only the last item of the whole expression is in tail position. This is because in general, it is impossible to know beforehand how many of the items will be evaluated.

**CAUTION**: In a ``def`` you still need the ``return``; it marks a return value.

**CAUTION**: Do not combo ``tco`` and ``continuations`` blocks; the latter already implies TCO. (They actually share a lot of the code that implements TCO.)

TCO is based on a strategy similar to MacroPy's ``tco`` macro, but using unpythonic's TCO machinery, and working together with the macros introduced by ``unpythonic.syntax``. The semantics are slightly different; by design, ``unpythonic`` requires an explicit ``return`` to mark tail calls in a ``def``. A call that is strictly speaking in tail position, but lacks the ``return``, is not TCO'd, and the implicit ``return None`` then shuts down the trampoline, returning ``None`` as the result of the TCO chain.

### TCO and continuations

#### TCO and ``call_ec``

(Mainly of interest for lambdas, which have no ``return``, and for "multi-return" from a nested function.)

For escape continuations in ``tco`` and ``continuations`` blocks, only basic uses of ``call_ec`` are supported. The literal function names ``ec`` and ``brk`` are always *understood as referring to* an escape continuation; in addition, ec names are harvested from uses of ``call_ec``.

See the docstring of ``unpythonic.syntax.tco`` for details.

However, the name ``ec`` or ``brk`` alone is not sufficient to make a function into an escape continuation, even though ``tco`` (and ``continuations``) will think of it as such. The function also needs to actually implement some kind of an escape mechanism. An easy way to get an escape continuation, where this has already been done for you, is to use ``call_ec``.

#### In a ``with continuations`` block, why even use ``call_ec``?

Pretty much by the definition of a continuation, in a ``with continuations`` block, another solution that *should* at first glance produce an escape is to set ``cc`` to the ``cc`` of the caller, and then return the desired value. There is however a subtle catch, due to the way we implement continuations. Consider:

```python
from unpythonic.syntax import macros, tco, continuations
from unpythonic import call_ec, identity

with tco:
    def double_odd(x, ec):
        if x % 2 == 0:  # reject even "x"
            ec("not odd")
        return 2*x
    @call_ec
    def result1(ec):
        y = double_odd(42, ec)
        z = double_odd(21, ec)  # avoid tail-calling because ec is not valid after result1() exits
        return z
    @call_ec
    def result2(ec):
        y = double_odd(21, ec)
        z = double_odd(42, ec)
        return z
    assert result1 == "not odd"
    assert result2 == "not odd"

with continuations:
    def double_odd(x, ec, *, cc):
        if x % 2 == 0:
            cc = ec
            return "not odd"
        return 2*x
    def main1(*, cc):
        y = double_odd(42, ec=cc)  # y = "not odd"
        z = double_odd(21, ec=cc)  # we could tail-call, but let's keep this similar to the first example.
        return z
    def main2(*, cc):
        y = double_odd(21, ec=cc)
        z = double_odd(42, ec=cc)
        return z
    assert main1() == 42
    assert main2() == "not odd"
```

In the first example, ``ec`` is the escape continuation of the ``result1``/``result2`` block, due to the placement of the ``call_ec``. In the second example, the ``cc`` inside ``double_odd`` is the implicitly passed ``cc``... which, naively, should represent the continuation of the current call into ``double_odd``. So far, so good.

However, because in this example there are no ``with bind`` blocks, the actual value of ``cc``, anywhere in this example, is always just ``identity``. *It's not the actual continuation.* Even though we pass the ``cc`` of ``main1``/``main2`` as an explicit argument "``ec``" to use as an escape continuation (like the first example does with ``ec``), it is still ``identity`` - and hence cannot perform an escape.

If we wish to use that strategy in this implementation, we must use ``with bind``, and place the rest of the original function body (i.e. *the actual continuation*) into the body of the ``with bind``, so that it is indeed captured as the continuation:

```python
from unpythonic.syntax import macros, continuations, bind
from unpythonic import identity

with continuations:
    def double_odd(x, ec, *, cc):
        if x % 2 == 0:
            cc = ec
            return "not odd"
        return 2*x
    def main1(*, cc):
        with bind[double_odd(42, ec=cc)] as y:
            return double_odd(21, ec=cc)
    def main2(*, cc):
        with bind[double_odd(21, ec=cc)] as y:
            return double_odd(42, ec=cc)
    assert main1() == "not odd"
    assert main2() == "not odd"
```

This variant performs as expected.

There's also a second, even subtler catch; instead of setting ``cc = ec`` and returning a value, just tail-calling ``ec`` with that value doesn't do what we want. This is because - as explained in the rules of the ``continuations`` macro, above - a tail-call is *inserted* between the end of the function, and whatever ``cc`` currently points to.

Most often that's exactly what we want, but in this particular case, it causes *both* continuations to run, in sequence. But if we overwrite ``cc``, then the function's original ``cc`` argument is discarded, so it never runs - and we get the effect we want, *replacing* the ``cc`` by the ``ec``.

Such subtleties arise essentially from the difference between a language that natively supports continuations (Scheme, Racket) and one that has continuations hacked on top of it as macros performing a CPS conversion only partially (like Python with ``unpythonic.syntax``, or Common Lisp with PG's continuation-passing macros). The macro approach works, but the programmer needs to be careful.


## ``autoreturn``: implicit ``return`` in tail position

In Lisps, a function implicitly returns the value of the expression in tail position (along the code path being executed). Now Python can, too:

```python
from unpythonic.syntax import macros, autoreturn

with autoreturn:
    def f():
        "I'll just return this"
    assert f() == "I'll just return this"

    def g(x):
        if x == 1:
            "one"
        elif x == 2:
            "two"
        else:
            "something else"
    assert g(1) == "one"
    assert g(2) == "two"
    assert g(42) == "something else"
```

Each ``def`` function definition lexically within the ``with autoreturn`` block is examined, and if the last item within the body is an expression ``expr``, it is transformed into ``return expr``. Additionally:

 - If the last item is an ``if``/``elif``/``else`` block, the transformation is applied to the last item in each of its branches.

 - If the last item is a ``with`` or ``async with`` block, the transformation is applied to the last item in its body.

 - If the last item is a ``try``/``except``/``else``/``finally`` block, the rules are as follows. If an ``else`` clause is present, the transformation is applied to the last item in it; otherwise, to the last item in the ``try`` clause. Additionally, in both cases, the transformation is applied to the last item in each of the ``except`` clauses. The ``finally`` clause is not transformed; the intention is it is usually a finalizer (e.g. to release resources) that runs after the interesting value is already being returned by ``try``, ``else`` or ``except``.

Any explicit ``return`` statements are left alone, so ``return`` can still be used as usual.

**CAUTION**: If the final ``else`` of an ``if``/``elif``/``else`` is omitted, as often in Python, then only the ``else`` item is in tail position with respect to the function definition - likely not what you want. So with ``autoreturn``, the final ``else`` should be written out explicitly, to make the ``else`` branch part of the same ``if``/``elif``/``else`` block.

**CAUTION**: ``for``, ``async for``, ``while`` are currently not analyzed; effectively, these are defined as always returning ``None``. If the last item in your function body is a loop, use an explicit return.

**CAUTION**: With ``autoreturn`` enabled, functions no longer return ``None`` by default; the whole point of this macro is to change the default return value. The default return value is ``None`` only if the tail position contains a statement (because in a sense, a statement always returns ``None``).

If you wish to omit ``return`` in tail calls, this comboes with ``tco``; just apply ``autoreturn`` first (either ``with autoreturn, tco:`` or in nested format, ``with tco:``, ``with autoreturn:``).


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

The transformation is ``fup[seq[idx] << value] --> fupdate(seq, idx, value)`` for a single index, and ``fup[seq[slicestx] << iterable] --> fupdate(seq, slice(...), iterable)`` for a slice. The main point of this macro is that slices are specified in the native slicing syntax. (Contrast the direct use of the underlying ``fupdate`` function, which requires manually calling ``slice``.)


## ``prefix``: prefix function call syntax for Python

Write Python almost like Lisp!

Lexically inside a ``with prefix`` block, any literal tuple denotes a function call, unless quoted. The first element is the operator, the rest are arguments.

*Changed in v0.11.0.* Bindings of the ``let`` macros and the top-level tuple in a ``do[]`` are now left alone, but ``prefix`` recurses inside them (in the case of bindings, on each RHS).

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

**CAUTION**: The ``prefix`` macro is experimental and not intended for use in production code.


## Comboability

The macros in ``unpythonic.syntax`` are designed to work together, in principle in arbitrary combinations, but some care needs to be taken regarding the order in which they expand.

If some particular combo doesn't work and it's not at least documented as such, please raise an issue.

For the christmas tree combo, the block macros are designed to run in the following order (leftmost first):

```
prefix > autoreturn > multilambda, namedlambda > continuations, tco > curry
```

For simplicity, **the block macros make no attempt to prevent invalid combos**. Be careful; e.g. don't nest several ``with tco`` blocks, that won't work.

Other things to note:

 - ``continuations`` and ``tco`` are mutually exclusive, since ``continuations`` already implies TCO.

 - ``prefix``, ``autoreturn`` and ``multilambda`` are first-pass macros (expand from outside in), because they change the semantics:
   - ``prefix`` transforms things-that-look-like-tuples into function calls,
   - ``autoreturn`` adds ``return`` statements where there weren't any,
   - ``multilambda`` transforms things-that-look-like-lists into sequences of multiple expressions, using ``do[]``.
   - Hence, a lexically outer block of one of these types *will expand first*, before any macros inside it are expanded, in contrast to the default *from inside out* expansion order.
   - This yields clean, standard-ish Python for the rest of the macros, which then don't need to worry about their input meaning something completely different from what it looks like.

 - An already expanded ``do[]`` (including that inserted by `multilambda`) is accounted for by all ``unpythonic.syntax`` macros when handling expressions.
   - For simplicity, this is **the only** type of sequencing understood by the macros.
   - E.g. the more rudimentary ``unpythonic.seq.begin`` is not treated as a sequencing operation. This matters especially in ``tco``, where it is critically important to correctly detect a tail position in a return-value expression or (multi-)lambda body.

 - The TCO transformation knows about TCO-enabling decorators provided by ``unpythonic``, and adds the ``@trampolined`` decorator to a function definition only when it is not already TCO'd.
   - This applies also to lambdas; they are decorated by directly wrapping them with a call: ``trampolined(lambda ...: ...)``.
   - This allows ``with tco`` to work together with the functions in ``unpythonic.fploop``, which imply TCO.

 - Macros that transform lambdas (notably ``continuations`` and ``tco``):
   - Perform a first pass to take note of all lambdas that appear in the code *before the expansion of any inner macros*. Then in the second pass, *after the expansion of all inner macros*, only the recorded lambdas are transformed.
     - This mechanism distinguishes between explicit lambdas in the client code, and internal implicit lambdas automatically inserted by a macro. The latter are a technical detail that should not undergo the same transformations as user-written explicit lambdas.
     - The identification is based on the ``id`` of the AST node instance. Hence, if you plan to write your own macros that work together with those in ``unpythonic.syntax``, avoid going overboard with FP. Modifying the tree in-place, preserving the original AST node instances as far as sensible, is just fine.
   - Support a limited form of *decorated lambdas*, i.e. trees of the form ``f(g(h(lambda ...: ...)))``.
     - The macros will reorder a chain of lambda decorators (i.e. nested calls) to use the correct ordering, when only known decorators are used on a literal lambda.
       - This allows some combos such as ``tco``, ``unpythonic.fploop.looped``, ``curry``.
     - Only decorators provided by ``unpythonic`` are recognized, and only some of them are supported. For details, see ``unpythonic.syntax.util.decorator_registry``.
     - If you need to combo ``unpythonic.fploop.looped`` and ``unpythonic.ec.call_ec``, use ``unpythonic.fploop.breakably_looped``, which does exactly that.
       - The problem with a direct combo is that the required ordering is the trampoline (inside ``looped``) outermost, then ``call_ec``, and then the actual loop, but because an escape continuation is only valid for the dynamic extent of the ``call_ec``, the whole loop must be run inside the dynamic extent of the ``call_ec``.
       - ``unpythonic.fploop.breakably_looped`` internally inserts the ``call_ec`` at the right step, and gives you the ec as ``brk``.

 - Some of the block macros can be comboed as multiple context managers in the same ``with`` statement (expansion order is then *left-to-right*), whereas some (notably ``curry``) require their own ``with`` statement.
   - This is a known bug. Probably something to do with the semantics of a ``with`` statement in MacroPy.
   - If something goes wrong in the expansion of one block macro in a ``with`` statement that specifies several block macros, surprises may occur.
   - When in doubt, use a separate ``with`` statement for each block macro that applies to the same section of code, and nest the blocks.


*Toto, I've a feeling we're not in Python anymore.*

