**Navigation**

- [README](../README.md)
- [Pure-Python feature set](features.md)
- **Syntactic macro feature set**
- [Examples of creating dialects using `mcpyrate`](dialects.md)
- [REPL server](repl.md)
- [Troubleshooting](troubleshooting.md)
- [Design notes](design-notes.md)
- [Essays](essays.md)
- [Additional reading](readings.md)
- [Contribution guidelines](../CONTRIBUTING.md)

# Language extensions using `unpythonic.syntax`

Our extensions to the Python language are built on [`mcpyrate`](https://github.com/Technologicat/mcpyrate), from the PyPI package [`mcpyrate`](https://pypi.org/project/mcpyrate/).

Because in Python macro expansion occurs *at import time*, Python programs whose main module uses macros, such as [our unit tests that contain usage examples](../unpythonic/syntax/tests/), cannot be run directly by `python3`. Instead, run them via the `macropython` bootstrapper, included in `mcpyrate`.

**Our macros expect a from-import style** for detecting uses of `unpythonic` constructs, *even when those constructs are regular functions*. For example, the function `curry` is detected from its bare name. So if you intend to use these macros, then, for regular imports from `unpythonic`, use `from unpythonic import ...` and avoid renaming (`as`).

*This document doubles as the API reference, but despite maintenance on a best-effort basis, may occasionally be out of date at places. In case of conflicts in documentation, believe the unit tests first; specifically the code, not necessarily the comments. Everything else (comments, docstrings and this guide) should agree with the unit tests. So if something fails to work as advertised, check what the tests do - and optionally file an issue on GitHub so that the documentation can be fixed.*

**Changed in v0.15.0.** *To run macro-enabled programs, use the [`macropython`](https://github.com/Technologicat/mcpyrate/blob/master/doc/repl.md#macropython-the-universal-bootstrapper) bootstrapper from [`mcpyrate`](https://github.com/Technologicat/mcpyrate).*

**This document is up-to-date for v0.15.0.**


### Features

[**Bindings**](#bindings)
- [`let`, `letseq`, `letrec` as macros](#let-letseq-letrec-as-macros); proper lexical scoping, no boilerplate.
- [`dlet`, `dletseq`, `dletrec`, `blet`, `bletseq`, `bletrec`: decorator versions](#dlet-dletseq-dletrec-blet-bletseq-bletrec-decorator-versions)
- [Caution on name resolution and scoping](#caution-on-name-resolution-and-scoping)
- [`let_syntax`, `abbrev`: syntactic local bindings](#let_syntax-abbrev-syntactic-local-bindings); splice code at macro expansion time.
- [Bonus: barebones `let`](#bonus-barebones-let): pure AST transformation of `let` into a `lambda`.

[**Sequencing**](#sequencing)
- [`do` as a macro: stuff imperative code into an expression, *with style*](#do-as-a-macro-stuff-imperative-code-into-an-expression-with-style)

[**Tools for lambdas**](#tools-for-lambdas)
- [`multilambda`: supercharge your lambdas](#multilambda-supercharge-your-lambdas); multiple expressions, local variables.
- [`namedlambda`: auto-name your lambdas](#namedlambda-auto-name-your-lambdas) by assignment.
- [`fn`: underscore notation (quick lambdas) for Python](#f-underscore-notation-quick-lambdas-for-python)
- [`quicklambda`: expand quick lambdas first](#quicklambda-expand-quick-lambdas-first)
- [`envify`: make formal parameters live in an unpythonic `env`](#envify-make-formal-parameters-live-in-an-unpythonic-env)

[**Language features**](#language-features)
- [`autocurry`: automatic currying for Python](#autocurry-automatic-currying-for-python)
- [`lazify`: call-by-need for Python](#lazify-call-by-need-for-python)
  - [`lazy[]` and `lazyrec[]` macros](#lazy-and-lazyrec-macros)
  - [Forcing promises manually](#forcing-promises-manually)
  - [Binding constructs and auto-lazification](#binding-constructs-and-auto-lazification)
  - [Note about TCO](#note-about-tco)
- [`tco`: automatic tail call optimization for Python](#tco-automatic-tail-call-optimization-for-python)
  - [TCO and continuations](#tco-and-continuations)
- [`continuations`: call/cc for Python](#continuations-callcc-for-python)
  - [General remarks on continuations](#general-remarks-on-continuations)
  - [Differences between `call/cc` and certain other language features](#differences-between-callcc-and-certain-other-language-features) (generators, exceptions)
  - [`call_cc` API reference](#call_cc-api-reference)
  - [Combo notes](#combo-notes)
  - [Continuations as an escape mechanism](#continuations-as-an-escape-mechanism)
  - [What can be used as a continuation?](#what-can-be-used-as-a-continuation)
  - [This isn't `call/cc`!](#this-isnt-callcc)
  - [Why this syntax?](#why-this-syntax)
- [`prefix`: prefix function call syntax for Python](#prefix-prefix-function-call-syntax-for-python)
- [`autoreturn`: implicit `return` in tail position](#autoreturn-implicit-return-in-tail-position), like in Lisps.
- [`forall`: nondeterministic evaluation](#forall-nondeterministic-evaluation) with monadic do-notation for Python.

[**Convenience features**](#convenience-features)
- [`cond`: the missing `elif` for `a if p else b`](#cond-the-missing-elif-for-a-if-p-else-b)
- [`aif`: anaphoric if](#aif-anaphoric-if), the test result is `it`.
- [`autoref`: implicitly reference attributes of an object](#autoref-implicitly-reference-attributes-of-an-object)

[**Testing and debugging**](#testing-and-debugging)
- [`unpythonic.test.fixtures`: a test framework for macro-enabled Python](#unpythonic-test-fixtures-a-test-framework-for-macro-enabled-python)
  - [Overview](#overview)
  - [Testing syntax quick reference](#testing-syntax-quick-reference)
  - [Expansion order](#expansion-order)
  - [`with test`: test blocks](#with-test-test-blocks)
  - [`the`: capture the value of interesting subexpressions](#the-capture-the-value-of-interesting-subexpressions)
  - [Test sessions and testsets](#test-sessions-and-testsets)
  - [Producing unconditional failures, errors, and warnings](#producing-unconditional-failures-errors-and-warnings)
  - [Advanced: building a custom test framework](#advanced-building-a-custom-test-framework)
  - [Why another test framework?](#why-another-test-framework)
  - [Etymology and roots](#etymology-and-roots)
- [`dbg`: debug-print expressions with source code](#dbg-debug-print-expressions-with-source-code)

[**Other**](#other)
- [`nb`: silly ultralight math notebook](#nb-silly-ultralight-math-notebook)

[**Meta**](#meta)
- [The xmas tree combo](#the-xmas-tree-combo): notes on the macros working together.
- [Emacs syntax highlighting](#emacs-syntax-highlighting) for `unpythonic.syntax` and `mcpyrate`.
- [This is semantics, not syntax!](#this-is-semantics-not-syntax)

## Bindings

Macros that introduce new ways to bind identifiers.

### `let`, `letseq`, `letrec` as macros

**Changed in v0.15.0.** *Added support for env-assignment syntax in the bindings subform. For consistency with other env-assignments, this is now the preferred syntax to establish let bindings. Additionally, the old lispy syntax now accepts also brackets, for consistency with the use of brackets for macro invocations.*

These macros provide properly lexically scoped `let` constructs, no boilerplate:

```python
from unpythonic.syntax import macros, let, letseq, letrec

let[x << 17,  # parallel binding, i.e. bindings don't see each other
    y << 23][
      print(x, y)]

letseq[x << 1,  # sequential binding, i.e. Scheme/Racket let*
       y << x + 1][
         print(x, y)]

letrec[evenp << (lambda x: (x == 0) or oddp(x - 1)),  # mutually recursive binding, sequentially evaluated
       oddp << (lambda x: (x != 0) and evenp(x - 1))][
         print(evenp(42))]
```

Even with just one binding, the syntax remains the same:

```python
let[x << 21][2 * x]
```

There must be at least one binding; `let[][...]` is a syntax error, since Python's parser rejects an empty subscript slice.

Bindings are established using the `unpythonic` *env-assignment* syntax, `name << value`. The let bindings can be rebound in the body with the same env-assignment syntax, e.g. `x << 42`.

The same syntax for the bindings subform is used by:

- `let`, `letseq`, `letrec` (expressions)
- `dlet`, `dletseq`, `dletrec`, `blet`, `bletseq`, `bletrec` (decorators)
  - As of v0.15.0, it is possible to use `@dlet(...)` instead of `@dlet[...]` in Python 3.8 and earlier.
- `let_syntax`, `abbrev` (expression mode)


#### Haskelly let-in, let-where

The following Haskell-inspired, perhaps more pythonic alternative syntaxes are also available:

```python
let[[x << 21,
     y << 17,
     z << 4] in
    x + y + z]

let[x + y + z,
    where[x << 21,
          y << 17,
          z << 4]]

let[[x << 21] in 2 * x]
let[2 * x, where[x << 21]]
```

These syntaxes take no macro arguments; both the let-body and the bindings are placed inside the `...` in `let[...]`.

Note the bindings subform is always enclosed by brackets.

The `where` operator, if used, must be macro-imported. It may only appear at the top level of the let-where form, separating the body and the bindings subforms. In any invalid position, `where` is considered a syntax error at macro expansion time.

<details>
<summary>Semantically, these do the exact same thing as the original lispy syntax: </summary>

>The bindings are evaluated first, and then the body is evaluated with the bindings in place. The purpose of the second variant (the *let-where*) is just readability; sometimes it looks clearer to place the body expression first, and only then explain what the symbols in it mean.
>
>These syntaxes are valid for all **expression forms** of `let`, namely: `let[]`, `letseq[]`, `letrec[]`, `let_syntax[]` and `abbrev[]`. The decorator variants (`dlet` et al., `blet` et al.) and the block variants (`with let_syntax`, `with abbrev`) support only the formats where the bindings subform is given in the macro arguments part, because there the body is in any case placed differently (it's the body of the function being decorated).
>
>In the first variant above (the *let-in*), note that even there, the bindings block needs the brackets. This is due to Python's precedence rules; `in` binds more strongly than the comma (which makes sense almost everywhere else), so to make the `in` refer to all of the bindings, the bindings block must be bracketed. If the `let` expander complains your code does not look like a `let` form and you have used *let-in*, check your brackets.
>
>In the second variant (the *let-where*), note the comma between the body and `where`; it is compulsory to make the expression into syntactically valid Python. (It's however semi-easyish to remember, since also English requires the comma for a where-expression. It's not only syntactically valid Python, it is also syntactically valid English, at least for mathematicians.)
</details>

#### Alternative syntaxes for the bindings subform

**Changed in v0.15.0.**

Beginning with v0.15.0, the env-assignment syntax presented above is the preferred syntax to establish let bindings, for consistency with other env-assignments. This reminds that let variables live in an `env`, which is created by the `let` form.

There is also an alternative, lispy notation for the bindings subform, where each name-value pair is given using brackets:

```python
let[[x, 42], [y, 9001]][...]
let[[[x, 42], [y, 9001]] in ...]
let[..., where[[x, 42], [y, 9001]]]

# one-binding special case: outer brackets not needed
let[x, 42][...]
let[[x, 42] in ...]
let[..., where[x, 42]]
```

This is similar in spirit to the notation used in v0.14.3 and earlier.

Actually, for backwards compatibility, we still support some use of parentheses instead of brackets in the bindings subform. The following formats, used in versions of `unpythonic` up to v0.14.3, are still accepted:

```python
let((x, 42), (y, 9001))[...]
let[((x, 42), (y, 9001)) in ...]
let[..., where((x, 42), (y, 9001))]

# one-binding special case: outer parentheses not needed
let(x, 42)[...]
let[(x, 42) in ...]
let[..., where(x, 42)]
```

Even though an expr macro invocation itself is always denoted using brackets, as of `unpythonic` v0.15.0 parentheses can still be used *to pass macro arguments*, hence `let(...)[...]` is still accepted. The code that interprets the AST for the let bindings accepts both lists and tuples for each key-value pair, and the top-level container for the bindings subform in a let-in or let-where can be either list or tuple, so whether brackets or parentheses are used does not matter there, either.

Still, brackets are now the preferred delimiter, for consistency between the bindings and body subforms.

We plan to drop support for parentheses to pass macro arguments in the future, when Python 3.9 becomes the minimum Python version supported. The reason we will wait that long is that up to Python 3.8, decorators cannot be subscripted. Up to Python 3.8, `@dlet[x, 42]` is rejected by Python's parser, whereas `@dlet(x, 42)` is accepted.

The issue has been fixed in Python 3.9. If you already only use 3.9 and later, please prefer brackets to pass macro arguments.


#### Multiple expressions in body

The `let` constructs can use a multiple-expression body. The syntax to activate multiple expression mode is an extra set of brackets around the body ([like in `multilambda`](#multilambda-supercharge-your-lambdas)):

```python
let[x << 1,
    y << 2][[  # note extra [
      y << x + y,
      print(y)]]

let[[x << 1,
     y << 2] in
    [y << x + y,  # body starts here
     print(y)]]

let[[y << x + y,
     print(y)],   # body ends here
    where[x << 1,
          y << 2]]
```

The let macros implement this by inserting a `do[...]` (see below). In a multiple-expression body, a separate internal definition context exists for local variables that are not part of the `let`; see [the `do` macro for details](#do-as-a-macro-stuff-imperative-code-into-an-expression-with-style).

Only the outermost set of extra brackets is interpreted as a multiple-expression body. The rest are interpreted as usual, as lists. If you need to return a literal list from a `let` form with only one body expression, double the brackets on the *body* part:

```python
let[x << 1,
    y << 2][[
      [x, y]]]

let[[x << 1,
     y << 2] in
    [[x, y]]]

let[[[x, y]],
    where[x << 1,
          y << 2]]
```

The outermost brackets delimit the `let` form itself, the middle ones activate multiple-expression mode, and the innermost ones denote a list.

Only brackets are affected; parentheses are interpreted as usual, so returning a literal tuple works as expected:

```python
let[x << 1,
    y << 2][
      (x, y)]

let[[x << 1,
     y << 2] in
    (x, y)]

let[(x, y),
    where[x << 1,
          y << 2]]
```

#### Notes

The main difference of the `let` family to Python's own named expressions (a.k.a. the walrus operator, added in Python 3.8) is that `x := 42` does not create a scope, but `let[x << 42][...]` does. The walrus operator assigns to the name `x` in the scope it appears in, whereas in the `let` expression, the `x` only exists in that expression.

`let` and `letrec` expand into the `unpythonic.lispylet` constructs, implicitly inserting the necessary boilerplate: the `lambda e: ...` wrappers, quoting variable names in definitions, and transforming `x` to `e.x` for all `x` declared in the bindings. Assignment syntax `x << 42` transforms to `e.set('x', 42)`. The implicit environment parameter `e` is actually named using a gensym, so lexically outer environments automatically show through. `letseq` expands into a chain of nested `let` expressions.

All the `let` macros respect lexical scope, so this works as expected:

```python
letrec[z << 1][[
         print(z),
         letrec[z << 2][
                  print(z)]]]
```

The `z` in the inner `letrec` expands to the inner environment's `z`, and the `z` in the outer `letrec` to the outer environment's `z`.


### `dlet`, `dletseq`, `dletrec`, `blet`, `bletseq`, `bletrec`: decorator versions

Similar to `let`, `letseq`, `letrec`, these macros sugar the corresponding `unpythonic.lispylet` constructs, with the `dletseq` and `bletseq` constructs existing only as macros. They expand to nested `dlet` or `blet`, respectively.

Lexical scoping is respected; each environment is internally named using a gensym. Nesting is allowed.

Examples:

```python
from unpythonic.syntax import macros, dlet, dletseq, dletrec, blet, bletseq, bletrec

@dlet[x << 0]  # up to Python 3.8, use `@dlet(x << 0)` instead
def count():
    x << x + 1  # update `x` in let env
    return x
assert count() == 1
assert count() == 2

@dletrec[evenp << (lambda x: (x == 0) or oddp(x - 1)),
         oddp << (lambda x: (x != 0) and evenp(x - 1))]
def f(x):
    return evenp(x)
assert f(42) is True
assert f(23) is False

@dletseq[x << 1,
         x << x + 1,
         x << x + 2]
def g(a):
    return a + x
assert g(10) == 14

# block versions: the def takes no arguments, runs immediately, and is replaced by the return value.
@blet[x << 21]
def result():
    return 2*x
assert result == 42

@bletrec[evenp << (lambda x: (x == 0) or oddp(x - 1)),
         oddp << (lambda x: (x != 0) and evenp(x - 1))]
def result():
    return evenp(42)
assert result is True

@bletseq[x << 1,
         x << x + 1,
         x << x + 2]
def result():
    return x
assert result == 4
```

**CAUTION**: assignment to the let environment uses the syntax `name << value`, as always with `unpythonic` environments. The standard Python syntax `name = value` creates a local variable, as usual - *shadowing any variable with the same name from the `let`*.

The write of a `name << value` always occurs to the lexically innermost environment (as seen from the write site) that has that `name`. If no lexically surrounding environment has that `name`, *then* the expression remains untransformed, and means a left-shift (if `name` happens to be otherwise defined).

**CAUTION**: formal parameters of a function definition, local variables, and any names declared as `global` or `nonlocal` in a given lexical scope shadow names from the `let` environment. Mostly, this applies *to the entirety of that lexical scope*. This is modeled after Python's standard scoping rules.

As an exception to the rule, for the purposes of the scope analysis performed by `unpythonic.syntax`, creations and deletions *of lexical local variables* take effect from the next statement, and remain in effect for the **lexically** remaining part of the current scope. This allows `x = ...` to see the old bindings on the RHS, as well as allows the client code to restore access to a surrounding env's `x` (by deleting a local `x` shadowing it) when desired.

To clarify, here is a sampling from [the unit tests](../unpythonic/syntax/tests/test_letdo.py):

```python
@dlet[x << "the env x"]
def f():
    return x
assert f() == "the env x"

@dlet[x << "the env x"]
def f():
    x = "the local x"
    return x
assert f() == "the local x"

@dlet[x << "the env x"]
def f():
    return x
    x = "the unused local x"
assert f() == "the env x"

x = "the global x"
@dlet[x << "the env x"]
def f():
    global x
    return x
assert f() == "the global x"

@dlet[x << "the env x"]
def f():
    x = "the local x"
    del x           # deleting a local, ok!
    return x
assert f() == "the env x"

try:
    x = "the global x"
    @dlet[x << "the env x"]
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


### Caution on name resolution and scoping

The name resolution behavior described above **does not fully make sense**, because to define things this way is to conflate static (lexical) and dynamic (run-time) concepts. This feature unfortunately got built before I understood the matter clearly.

Python itself performs name resolution purely lexically, which is arguably the right thing to do. In any given lexical scope, an identifier such as `x` always refers to the same variable. Whether that variable has been initialized, or has already been deleted, is another matter, which has to wait until run time - but `del x` will **not** cause the identifier `x` to point to a different variable for the remainder of the same scope, like `delete[x]` **does** in the body of an `unpythonic` `let[]` or `do[]`.

#### Aside: Names and variables

To be technically correct, in Python, an identifier `x` refers to a *name*, not to a "variable". Python, like Lisp, has [*names and values*](https://nedbatchelder.com/text/names.html).

Roughly, an *identifier* is a certain kind of token in the source code text - something that everyday English calls a "name". However, in programming, a *name* is technically the *key* component of a key-value pair that is stored in a particular *environment*.

Very roughly speaking, an *environment* is just a place to store such pairs, for the purposes of "the variables subsystem" of the language. There are important details, such as that each *activation* of a function (think: "a particular call of the function") will create a new environment instance, to hold the local variables of that activation; this detail allows [lexical closures](https://en.wikipedia.org/wiki/Closure_(computer_programming)) to work. The piece of bookkeeping for this is termed an *activation record*. But the important point here is, an environment stores name-value pairs.

An identifier *refers to* a name. Scoping rules concern themselves with the details of mapping identifiers to names. In *lexical scoping* (like in Python), the position of the identifier in the source code text determines the search order of environments for the target name, when resolving a particular instance of an identifier in the source code text. Python uses the LEGB ordering (local, enclosing, global, builtin).

Finally, *values* are the run-time things names point to. They are the *value* component of the key-value pair.

In this simple example:

```python
def outer():
    x = 17
    def inner():
        x = 23
```

 - The piece of source code text `x` is an *identifier*.
 - *The outer `x`* and *the inner `x`* are *names*, both of which have the textual representation `x`.
   - *Which one of these the identifier `x` refers to depends on where it appears.* 
 - The integers `17` and `23` are *values*.

Note that classically, names have no type; values do.

Nowadays, a name may have a type annotation, which reminds the programmer about the type of *value* that is safe to bind to that particular name. In other words, the code that defines that name (e.g. as a function parameter) promises (in the sense of a contract) that the code knows how to behave if a value of that type is bound to that name (e.g. by passing such a value as a function argument that will be bound to that name).

Here *type* may be a concrete [nominal type](https://en.wikipedia.org/wiki/Nominal_type_system) such as `int`, or for example, it may represent a particular interface (such as the types in [`collections.abc`](https://docs.python.org/3/library/collections.abc.html)), or it may allow multiple mutually exclusive options (a *union*).

By default, Python treats type annotations as a form of comments; to actually statically type-check Python, [Mypy](http://mypy-lang.org/) can be used.

Compare the *name*/*value* concept to the concept of a *variable* in the classical sense, such as in C, or `cdef` in Cython. In such *low-level* [HLLs](https://en.wikipedia.org/wiki/High-level_programming_language), a *variable* is a named, fixed memory location, with a static data type determining how to interpret the bits at that memory location. The contents of the memory location can be changed, hence "variable" is an apt description.


### `let_syntax`, `abbrev`: syntactic local bindings

**Note v0.15.0.** *Now that we use `mcpyrate` as the macro expander, `let_syntax` and `abbrev` are not really needed. We are keeping them mostly for backwards compatibility, and because they exercise a different feature set in the macro expander, making the existence of these constructs particularly useful for system testing.*

*To define macros in the same module that uses them, see [multi-phase compilation](https://github.com/Technologicat/mcpyrate/blob/master/doc/compiler.md#multi-phase-compilation) in the [compiler documentation](https://github.com/Technologicat/mcpyrate/blob/master/doc/compiler.md). Using [run-time compiler access](https://github.com/Technologicat/mcpyrate/blob/master/doc/compiler.md#invoking-the-compiler-at-run-time), you can even create a macro definition module at run time (e.g. from a [quasiquoted](https://github.com/Technologicat/mcpyrate/blob/master/doc/quasiquotes.md) block) and inject it to `sys.modules`, allowing other code to import and use those macros. See the [compiler tests](https://github.com/Technologicat/mcpyrate/blob/master/mcpyrate/test/test_compiler.py) for examples.*

*To rename existing macros, you can as-import them. As of `unpythonic` v0.15.0, doing so for `unpythonic.syntax` constructs is not recommended, though, because there is still a lot of old analysis code in the macro implementations that may scan for the original name. This may or may not be fixed in a future release.*

These constructs allow to locally splice code at macro expansion time. It is almost like inlining functions.

#### `let_syntax`

```python
from unpythonic.syntax import macros, let_syntax, block, expr

def verylongfunctionname(x=1):
    return x

# works as an expr macro
y = let_syntax[f << verylongfunctionname][[  # extra brackets: implicit do in body
                 print(f()),
                 f(5)]]
assert y == 5

y = let_syntax[f[a] << verylongfunctionname(2*a)][[  # template with formal parameter "a"
                 print(f[2]),
                 f[3]]]
assert y == 6

y = let_syntax[[f << verylongfunctionname] in
               [print(f()),
                f(5)]]
y = let_syntax[[print(f()),
                f(5)],
               where[f << verylongfunctionname]]
y = let_syntax[[f[a] << verylongfunctionname(2*a)] in
               [print(f[2]),
                f[3]]]
y = let_syntax[[print(f[2]),
                f[3]],
               where[f[a] << verylongfunctionname(2*a)]]

# works as a block macro
with let_syntax:
    # with block as name:
    # with block[a0, ...] as name:
    with block[a, b, c] as makeabc:  # capture a block of statements
        lst = [a, b, c]
    makeabc(3 + 4, 2**3, 3 * 3)
    assert lst == [7, 8, 9]
    # with expr as name:
    # with expr[a0, ...] as name:
    with expr[n] as nth:             # capture a single expression
        lst[n]
    assert nth(2) == 9

with let_syntax:
    with block[a] as twice:
        a
        a
    with block[x, y, z] as appendxyz:
        lst += [x, y, z]
    lst = []
    twice(appendxyz(7, 8, 9))
    assert lst == [7, 8, 9]*2
```

After macro expansion completes, `let_syntax` has zero runtime overhead; it completely disappears in macro expansion.

The `expr` and `block` operators, if used, must be macro-imported. They may only appear in `with expr` and `with block` subforms at the top level of a `with let_syntax` or `with abbrev`. In any invalid position, `expr` and `block` are both considered a syntax error at macro expansion time.

<details>
<summary> There are two kinds of substitutions: </summary>

>*Bare name* and *template*. A bare name substitution has no parameters. A template substitution has positional parameters. (Named parameters, `*args`, `**kwargs` and default values are **not** supported.)
>
>When used as an expr macro, the formal parameter declaration is placed where it belongs; on the name side (LHS) of the binding. In the above example, `f[a]` is a template with a formal parameter `a`. But when used as a block macro, the formal parameters are declared on the `block` or `expr` "context manager" due to syntactic limitations of Python. To define a bare name substitution, just use `with block as ...:` or `with expr as ...:` with no macro arguments.
>
>In the body of `let_syntax`, a bare name substitution is invoked by name (just like a variable). A template substitution is invoked like an expr macro. Any instances of the formal parameters of the template get replaced by the argument values from the use site, at macro expansion time.
>
>Note each instance of the same formal parameter (in the definition) gets a fresh copy of the corresponding argument value. In other words, in the example above, each `a` in the body of `twice` separately expands to a copy of whatever code was given as the macro argument `a`.
>
>When used as a block macro, there are furthermore two capture modes: *block of statements*, and *single expression*. The single expression can be an explicit `do[]`, if multiple expressions are needed. When invoking substitutions, keep in mind Python's usual rules regarding where statements or expressions may appear.
>
>(If you know about Python ASTs, do not worry about the `ast.Expr` wrapper needed to place an expression in a statement position; this is handled automatically.)
</details>
<p>

**HINT**: If you get a compiler error that some sort of statement was encountered where an expression was expected, check your uses of `let_syntax`. The most likely reason is that a substitution is trying to splice a block of statements into an expression position.

<details>
 <summary> Expansion of this macro is a two-step process: </summary>

>  - First, template substitutions.
>  - Then, bare name substitutions, applied to the result of the first step.
>
>This design is to avoid accidental substitutions into formal parameters of templates (that would usually break the template, resulting at best in a mysterious error, and at worst silently doing something unexpected), if the name of a formal parameter happens to match one of the currently active bare name substitutions.
>
>Within each step, the substitutions are applied **in definition order**:
>
>  - If the bindings are `[x << y, y << z]`, then an `x` at the use site transforms to `z`. So does a `y` at the use site.
>  - But if the bindings are `[y << z, x << y]`, then an `x` at the use site transforms to `y`, and only an explicit `y` at the use site transforms to `z`.
>
>Even in block templates, arguments are always expressions, because invoking a template uses the subscript syntax. But names and calls are expressions, so a previously defined substitution (whether bare name or an invocation of a template) can be passed as an argument just fine. Definition order is then important; consult the rules above.
</details>
<p>

Nesting `let_syntax` is allowed. Lexical scoping is respected. Inner definitions of substitutions shadow outer ones.

When used as an expr macro, all bindings are registered first, and then the body is evaluated. When used as a block macro, a new binding (substitution declaration) takes effect from the next statement onward, and remains active for the lexically remaining part of the `with let_syntax` block.

#### `abbrev`

The `abbrev` macro is otherwise exactly like `let_syntax`, but it expands outside-in. Hence, it has no lexically scoped nesting support, but it has the power to locally rename also macros, because the `abbrev` itself expands before any macros invoked in its body. This allows things like:

```python
abbrev[m << macrowithverylongname][
    m[tree1] if m[tree2] else m[tree3]]
abbrev[[m << macrowithverylongname] in
       m[tree1] if m[tree2] else m[tree3]]
abbrev[m[tree1] if m[tree2] else m[tree3],
       where[m << macrowithverylongname]]
```

which is sometimes useful when writing macros. (But using `mcpyrate`, note that you can just as-import a macro if you need to rename it.)

**CAUTION**: `let_syntax` is essentially a toy macro system within the real macro system. The usual caveats of macro systems apply. Especially, `let_syntax` and `abbrev` support absolutely no form of hygiene. Be very, very careful to avoid name conflicts.

The `let_syntax` macro is meant for simple local substitutions where the elimination of repetition can shorten the code and improve its readability, in cases where the final "unrolled" code should be written out at compile time. If you need to do something complex (or indeed save a definition and reuse it somewhere else, non-locally), write a real macro directly in `mcpyrate`.

This was inspired by Racket's [`let-syntax`](https://docs.racket-lang.org/reference/let.html) and [`with-syntax`](https://docs.racket-lang.org/reference/stx-patterns.html) forms.


### Bonus: barebones `let`

As a bonus, we provide classical simple `let` and `letseq`, wholly implemented as AST transformations, providing true lexical variables, but no multi-expression body support. Just like in some Lisps, this version of `letseq` (Scheme/[Racket `let*`](https://docs.racket-lang.org/reference/let.html#%28form._%28%28lib._racket%2Fprivate%2Fletstx-scheme..rkt%29._let%2A%29%29)) expands into a chain of nested `let` expressions, which expand to lambdas.

These are provided in the separate module `unpythonic.syntax.simplelet`, and are not part of the `unpythonic.syntax` macro API. For simplicity, they support only the lispy list syntax in the bindings subform (using brackets, specifically!), and no haskelly syntax at all:

```python
from unpythonic.syntax.simplelet import macros, let, letseq

let[[x, 42], [y, 23]][...]
let[[x, 42]][...]
letseq[[x, 1], [x, x + 1]][...]
letseq[[x, 1]][...]
```

Starting with Python 3.8, assignment (rebinding) is possible also in these barebones `let` constructs via the walrus operator. For example:

```python
assert let[[x, 42]][x] == 42
assert let[[x, 42]][(x := 5)] == 5
```

However, this only works for variables created by the innermost `let` (viewed from the point where the assignment happens), because `nonlocal` is a statement and so cannot be used in expressions.


## Sequencing

Macros that run multiple expressions, in sequence, in place of one expression.

### `do` as a macro: stuff imperative code into an expression, *with style*

We provide an `expr` macro wrapper for `unpythonic.seq.do`, with some extra features.

This essentially allows writing imperative code in any expression position. For an `if-elif-else` conditional, [see `cond`](#cond-the-missing-elif-for-a-if-p-else-b); for loops, see [the functions in `unpythonic.fploop`](../unpythonic/fploop.py) (`looped` and `looped_over`).

```python
from unpythonic.syntax import macros, do, local, delete

y = do[local[x << 17],
       print(x),
       x << 23,
       x]
print(y)  # --> 23

a = 5
y = do[local[a << 17],
       print(a),  # --> 17
       delete[a],
       print(a),  # --> 5
       True]
```

Local variables are declared and initialized with `local[var << value]`, where `var` is a bare name. To explicitly denote "no value", just use `None`. The syntax `delete[...]` allows deleting a `local[...]` binding. This uses `env.pop()` internally, so a `delete[...]` returns the value the deleted local variable had at the time of deletion. (This also means that if you manually use the `do()` function in some code without macros, you can `env.pop(...)` in a do-item if needed.)

The `local[]` and `delete[]` declarations may only appear at the top level of a `do[]`, `do0[]`, or implicit `do` (extra bracket syntax, e.g. for the body of a `let` form). In any invalid position, `local[]` and `delete[]` are considered a syntax error at macro expansion time.

A `local` declaration comes into effect in the expression following the one where it appears, capturing the declared name as a local variable for the **lexically** remaining part of the `do`. In a `local`, the RHS still sees the previous bindings, so this is valid (although maybe not readable):

```python
result = []
let[lst << []][[result.append(lst),       # the let "lst"
                local[lst << lst + [1]],  # LHS: do "lst", RHS: let "lst"
                result.append(lst)]]      # the do "lst"
assert result == [[], [1]]
```

Already declared local variables are updated with `var << value`. Updating variables in lexically outer environments (e.g. a `let` surrounding a `do`) uses the same syntax.

<details>
<summary>The reason we require local variables to be declared is to allow write access to lexically outer environments.</summary>

>Assignments are recognized anywhere inside the `do`; but note that any `let` constructs nested *inside* the `do`, that define variables of the same name, will (inside the `let`) shadow those of the `do` - as expected of lexical scoping.
>
>The necessary boilerplate (notably the `lambda e: ...` wrappers) is inserted automatically, so the expressions in a `do[]` are only evaluated when the underlying `seq.do` actually runs.
>
>When running, `do` behaves like `letseq`; assignments **above** the current line are in effect (and have been performed in the order presented). Re-assigning to the same name later overwrites (this is afterall an imperative tool).
>
>We also provide a `do0` macro, which returns the value of the first expression, instead of the last.
</details>
<p>

**CAUTION**: `do[]` supports local variable deletion, but the `let[]` constructs do **not**, by design. When `do[]` is used implicitly with the extra bracket syntax, any `delete[]` refers to the scope of the implicit `do[]`, not any surrounding `let[]` scope.


## Tools for lambdas

Macros that introduce additional features for Python's lambdas.

### `multilambda`: supercharge your lambdas

**Multiple expressions**: use `[...]` to denote a multiple-expression body. The macro implements this by inserting a `do`.

**Local variables**: available in a multiple-expression body. For details on usage, see `do`.

```python
from unpythonic.syntax import macros, multilambda, let

with multilambda:
    echo = lambda x: [print(x), x]
    assert echo("hi there") == "hi there"

    count = let[x << 0][
              lambda: [x << x + 1,  # x belongs to the surrounding let
                       x]]
    assert count() == 1
    assert count() == 2

    test = let[x << 0][
             lambda: [x << x + 1,
                      local[y << 42],  # y is local to the implicit do
                      (x, y)]]
    assert test() == (1, 42)
    assert test() == (2, 42)

    myadd = lambda x, y: [print("myadding", x, y),
                          local[tmp << x + y],
                          print("result is", tmp),
                          tmp]
    assert myadd(2, 3) == 5

    # only the outermost set of brackets denote a multi-expr body:
    t = lambda: [[1, 2]]
    assert t() == [1, 2]
```

In the second example, returning `x` separately is redundant, because the assignment to the let environment already returns the new value, but it demonstrates the usage of multiple expressions in a lambda.


### `namedlambda`: auto-name your lambdas

**Changed in v0.15.0.** *When `namedlambda` encounters a lambda definition it cannot infer a name for, it instead injects source location info into the name, provided that the AST node for that particular `lambda` has a line number for it. The result looks like `<lambda at some/path/mymod.py:201>`.*

Who said lambdas have to be anonymous?

```python
from unpythonic.syntax import macros, namedlambda

with namedlambda:
    f = lambda x: x**3                       # assignment: name as "f"
    assert f.__name__ == "f"
    gn, hn = let[x << 42, g << None, h << None][[
                   g << (lambda x: x**2),    # env-assignment: name as "g"
                   h << f,                   # still "f" (no literal lambda on RHS)
                   (g.__name__, h.__name__)]]
    assert gn == "g"
    assert hn == "f"

    foo = let[[f7 << (lambda x: x)] in f7]       # let-binding: name as "f7"

    def foo(func1, func2):
        assert func1.__name__ == "func1"
        assert func2.__name__ == "func2"
    foo(func1=lambda x: x**2,  # function call with named arg: name as "func1"
        func2=lambda x: x**2)  # function call with named arg: name as "func2"

    # dictionary literal
    d = {"f": lambda x: x**2,  # literal string key in a dictionary literal: name as "f"
         "g": lambda x: x**2}  # literal string key in a dictionary literal: name as "g"
    assert d["f"].__name__ == "f"
    assert d["g"].__name__ == "g"
```

Lexically inside a `with namedlambda` block, any literal `lambda` that is assigned to a name using one of the supported assignment forms is named to have the name of the LHS of the assignment. The name is captured at macro expansion time.

Decorated lambdas are also supported, as is a `curry` (manual or auto) where the last argument is a lambda. The latter is a convenience feature, mainly for applying parametric decorators to lambdas. See [the unit tests](../unpythonic/syntax/tests/test_lambdatools.py) for detailed examples.

The naming is performed using the function `unpythonic.misc.namelambda`, which will return a modified copy with its `__name__`, `__qualname__` and `__code__.co_name` changed. The original function object is not mutated.

**Supported assignment forms**:

 - Single-item assignment to a local name, `f = lambda ...: ...`

 - Named expressions (a.k.a. walrus operator, Python 3.8+), `f := lambda ...: ...`. **Added in v0.15.0.**

 - Expression-assignment to an unpythonic environment, `f << (lambda ...: ...)`
   - Env-assignments are processed lexically, just like regular assignments. This should not cause problems, because left-shifting by a literal lambda most often makes no sense (whence, that syntax is *almost* guaranteed to mean an env-assignment).

 - Let bindings, `let[[f << (lambda ...: ...)] in ...]`, using any let syntax supported by unpythonic (here using the haskelly let-in with env-assign style bindings just as an example).

 - Named argument in a function call, as in `foo(f=lambda ...: ...)`. **Added in v0.14.2.**

 - In a dictionary literal `{...}`, an item with a literal string key, as in `{"f": lambda ...: ...}`. **Added in v0.14.2.**

Support for other forms of assignment may or may not be added in a future version. We will maintain a list here; but if you want the gritty details, see the `_namedlambda` syntax transformer in [`unpythonic.syntax.lambdatools`](../unpythonic/syntax/lambdatools.py).

### `fn`: underscore notation (quick lambdas) for Python

**Changed in v0.15.0.** *Up to 0.14.x, the `f[]` macro used to be provided by `macropy`, but now that we use `mcpyrate`, we provide this ourselves. Note that the name of the construct is now `fn[]`.*

The syntax `fn[...]` creates a lambda, where each underscore `_` in the `...` part introduces a new parameter:

```python
from unpythonic.syntax import macros, fn
from unpythonic.syntax import _  # optional, makes IDEs happy

double = fn[_ * 2]  # --> double = lambda x: x * 2
mul = fn[_ * _]  # --> mul = lambda x, y: x * y
```

The macro does not descend into any nested `fn[]`, to allow the macro expander itself to expand those separately.

We have named the construct `fn`, because `f` is often used as a function name in code examples, local temporaries, and similar. Also, `fn[]` is a less ambiguous abbreviation for a syntactic construct that means *function*, while remaining shorter than the equivalent `lambda`.

The underscore `_` itself is not a macro. The `fn` macro treats the underscore magically, just like MacroPy's `f`, but anywhere else the underscore is available to be used as a regular variable.

The underscore does not need to be imported for `fn[]` to recognize it, but if you want to make your IDE happy, there is a symbol named `_` in `unpythonic.syntax` you can import to silence any "undefined name" errors regarding the use of `_`. It is a regular run-time object, not a macro.

(It *could* be made into a `@namemacro` that triggers a syntax error when it appears in an improper context, like starting with v0.15.0, many auxiliary constructs in similar roles already do. But it was decided that in this particular case, it is more valuable to have the name `_` available for other uses in other contexts, because it is a standard dummy name in Python. The lambdas created using `fn[]` are likely short enough that not automatically detecting misplaced underscores does not cause problems in practice.)

Because in `mcpyrate`, macros can be as-imported, you can rename `fn` at import time to have any name you want. The `quicklambda` block macro (see below) respects the as-import. You **must** import also the macro `fn` if you use `quicklambda`, because `quicklambda` internally queries the expander to determine the name(s) the macro `fn` is currently bound to. If the `fn` macro is not bound to any name, `quicklambda` will do nothing.

It is sufficient that `fn` has been macro-imported by the time when the `with quicklambda` expands. So it is possible, for example, for a dialect template to macro-import just `quicklambda` and inject an invocation for it, and leave macro-importing `fn` to the user code. The `Lispy` variant of the [Lispython dialect](dialects/lispython.md) does exactly this.

### `quicklambda`: expand quick lambdas first

To be able to transform correctly, the block macros in `unpythonic.syntax` that transform lambdas (e.g. `multilambda`, `tco`) need to see all `lambda` definitions written with Python's standard `lambda`.

However, the `fn` macro uses the syntax `fn[...]`, which (to the analyzer) does not look like a lambda definition. The `quicklambda` block macro changes the expansion order, forcing any `fn[...]` lexically inside the block to expand before any other macros do.

Any expression of the form `fn[...]`, where `fn` is any name bound in the current macro expander to the macro `unpythonic.syntax.fn`, is understood as a quick lambda. (In plain English, this respects as-imports of the macro `fn`.)

Example - a quick multilambda:

```python
from unpythonic.syntax import macros, multilambda, quicklambda, fn, local
from unpythonic.syntax import _  # optional, makes IDEs happy

with quicklambda, multilambda:
    func = fn[[local[x << _],
               local[y << _],
               x + y]]
    assert func(1, 2) == 3
```

This is of course rather silly, as an unnamed formal parameter can only be mentioned once. If we are giving names to them, a regular `lambda` is shorter to write. A more realistic combo is:

```python
with quicklambda, tco:
    def g(x):
        return 2 * x
    func1 = fn[g(3 * _)]  # tail call
    assert func1(10) == 60

    func2 = fn[3 * g(_)]  # no tail call
    assert func2(10) == 60
```


### `envify`: make formal parameters live in an unpythonic `env`

When a function whose definition (`def` or `lambda`) is lexically inside a `with envify` block is entered, it copies references to its arguments into an unpythonic `env`. At macro expansion time, all references to the formal parameters are redirected to that environment. This allows rebinding, from an expression position, names that were originally the formal parameters.

Wherever could *that* be useful? For an illustrative caricature, consider [PG's accumulator puzzle](http://paulgraham.com/icad.html).

The modern pythonic solution:

```python
def foo(n):
    def accumulate(i):
        nonlocal n
        n += i
        return n
    return accumulate
```

This avoids allocating an extra place to store the accumulator `n`. If you want optimal bytecode, this is the best solution in Python 3.

But what if, instead, we consider the readability of the unexpanded source code? The definition of `accumulate` requires many lines for something that simple. What if we wanted to make it a lambda? Because all forms of assignment are statements in Python, the above solution is not admissible for a lambda, even with macros.

So if we want to use a lambda, we have to create an `env`, so that we can write into it. Let's use the let-over-lambda idiom:

```python
def foo(n0):
    return let[[n << n0] in
               (lambda i: n << n + i)]
```

Already better, but the `let` is used only for (in effect) altering the passed-in value of `n0`; we don't place any other variables into the `let` environment. Considering the source text already introduces an `n0` which is just used to initialize `n`, that's an extra element that could be eliminated.

Enter the `envify` macro, which automates this:

```python
with envify:
    def foo(n):
        return lambda i: n << n + i
```

Combining with `autoreturn` yields the fewest-elements optimal solution to the accumulator puzzle:

```python
with autoreturn, envify:
    def foo(n):
        lambda i: n << n + i
```

The `with` block adds a few elements, but if desired, it can be refactored into the definition of a custom dialect in [Pydialect](https://github.com/Technologicat/pydialect).

## Language features

To boldly go where Python without macros just won't. Changing the rules by code-walking and making significant rewrites.

### `autocurry`: automatic currying for Python

**Changed in v0.15.0.** *The macro is now named `autocurry`, to avoid shadowing the `curry` function.*

```python
from unpythonic.syntax import macros, autocurry
from unpythonic import foldr, composerc as compose, cons, nil

with autocurry:
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
assert add3(1)(2)(3) == 6
```

*Lexically* inside a `with autocurry` block:

 - All **function calls** and **function definitions** (`def`, `lambda`) are automatically curried, somewhat like in Haskell, or in `#lang` [`spicy`](https://github.com/Technologicat/spicy).

 - Function calls are autocurried, and run `unpythonic.fun.curry` in a special mode that no-ops on uninspectable functions (triggering a standard function call with the given args immediately) instead of raising `TypeError` as usual.

**CAUTION**: Some built-ins are uninspectable or may report their arities incorrectly; in those cases, `curry` may fail, occasionally in mysterious ways. The function `unpythonic.arity.arities`, which `unpythonic.fun.curry` internally uses, has a workaround for the inspectability problems of all built-ins in the top-level namespace (as of Python 3.7), but e.g. methods of built-in types are not handled.

Manual uses of the `curry` decorator (on both `def` and `lambda`) are detected, and in such cases the macro skips adding the decorator.

### `lazify`: call-by-need for Python

**Changed in v0.15.0.** *Up to 0.14.x, the `lazy[]` macro, that is used together with `with lazify`, used to be provided by `macropy`, but now that we use `mcpyrate`, we provide it ourselves. If you use `lazy[]`, change your import of that macro to `from unpythonic.syntax import macros, lazy`*.

Also known as *lazy functions*. Like [lazy/racket](https://docs.racket-lang.org/lazy/index.html), but for Python. Note if you want *lazy sequences* instead, Python already provides those; just use the generator facility (and decorate your gfunc with `unpythonic.gmemoize` if needed).

Lazy function example:

```python
with lazify:
    def my_if(p, a, b):
        if p:
            return a  # b never evaluated in this code path
        else:
            return b  # a never evaluated in this code path
    assert my_if(True, 23, 1/0) == 23
    assert my_if(False, 1/0, 42) == 42

    def g(a, b):
        return a
    def f(a, b):
        return g(2*a, 3*b)
    assert f(21, 1/0) == 42
```

In a `with lazify` block, function arguments are evaluated only when actually used, at most once each, and in the order in which they are actually used (regardless of the ordering of the formal parameters that receive them). Delayed values (*promises*) are automatically evaluated (*forced*) on access. Automatic lazification applies to arguments in function calls and to let-bindings, since they play a similar role. **No other binding forms are auto-lazified.**

Automatic lazification uses the `lazyrec[]` macro (see below), which recurses into certain types of container literals, so that the lazification will not interfere with unpacking.

Note `my_if` in the example is a regular function, not a macro. Only the `with lazify` is imbued with any magic. Essentially, the above code expands into:

```python
from unpythonic.syntax import macros, lazy
from unpythonic.syntax import force

def my_if(p, a, b):
    if force(p):
        return force(a)
    else:
        return force(b)
assert my_if(lazy[True], lazy[23], lazy[1/0]) == 23
assert my_if(lazy[False], lazy[1/0], lazy[42]) == 42

def g(a, b):
    return force(a)
def f(a, b):
    return g(lazy[2*force(a)], lazy[3*force(b)])
assert f(lazy[21], lazy[1/0]) == 42
```

plus some clerical details to allow mixing lazy and strict code. This second example relies on the magic of closures to capture f's `a` and `b` into the `lazy[]` promises.

Like `with continuations`, no state or context is associated with a `with lazify` block, so lazy functions defined in one block may call those defined in another.

Lazy code is allowed to call strict functions and vice versa, without requiring any additional effort.

Comboing with other block macros in `unpythonic.syntax` is supported, including `autocurry` and `continuations`. See the [meta](#meta) section of this README for the correct ordering.

For more details, see the docstring of `unpythonic.syntax.lazify`.

Inspired by Haskell, Racket's `(delay)` and `(force)`, and [lazy/racket](https://docs.racket-lang.org/lazy/index.html).

**CAUTION**: The functions in `unpythonic.fun` are lazify-aware (so that e.g. `curry` and `compose` work with lazy functions), as are `call` and `callwith` in `unpythonic.misc`, but a large part of `unpythonic` is not. Keep in mind that any call to a strict (regular Python) function will evaluate all of its arguments.

#### `lazy[]` and `lazyrec[]` macros

**Changed in v0.15.0.** *Previously, the `lazy[]` macro was provided by MacroPy. Now that we use `mcpyrate`, which doesn't provide it, we provide it ourselves, in `unpythonic.syntax`. Note that a lazy value now no longer has a `__call__` operator; instead, it has a `force()` method. The utility `unpythonic.lazyutil.force` (previously exported in `unpythonic.syntax`; now moved to the top-level namespace of `unpythonic`) abstracts away this detail.*

We provide the macros `unpythonic.syntax.lazy`, which explicitly lazifies a single expression, and `unpythonic.syntax.lazyrec`, which can be used to lazify expressions inside container literals, recursively.

Essentially, `lazy[...]` achieves the same result as `memoize(lambda: ...)`, with the practical difference that a `lazy[]` promise `p` is evaluated by calling `unpythonic.lazyutil.force(p)` or `p.force()`. In `unpythonic`, the promise datatype (`unpythonic.lazyutil.Lazy`) does not have a `__call__` method, because the word `force` better conveys the intent.

It is preferable to use the `force` function instead of the `.force` method, because the function will also pass through any non-promise value, whereas (obviously) a non-promise value will not have a `.force` method. Using the function, you can `force` a value just to be sure, without caring whether that value was a promise. The `force` function is available in the top-level namespace of `unpythonic`.

The `lazify` subsystem expects the `lazy[...]` notation in its analyzer, and will not recognize `memoize(lambda: ...)` as a delayed value.

The `lazyrec[]` macro allows code like `tpl = lazyrec[(1*2*3, 4*5*6)]`. Each item becomes wrapped with `lazy[]`, but the container itself is left alone, to avoid interfering with unpacking. Because `lazyrec[]` is a macro and must work by names only, it supports a fixed set of container types: `list`, `tuple`, `set`, `dict`, `frozenset`, `unpythonic.collections.frozendict`, `unpythonic.collections.box`, and `unpythonic.llist.cons` (specifically, the constructors `cons`, `ll` and `llist`).

The `unpythonic` containers **must be from-imported** for `lazyrec[]` to recognize them. Either use `from unpythonic import xxx` (**recommended**), where `xxx` is a container type, or import the `containers` subpackage by `from unpythonic import containers`, and then use `containers.xxx`. (The analyzer only looks inside at most one level of attributes. This may change in the future.)

(The analysis in `lazyrec[]` must work by names only, because in an eager language any lazification must be performed as a syntax transformation before the code actually runs, so the analysis must be performed statically - and locally, because `lazyrec[]` is an expr macro. [Fexprs](https://fexpr.blogspot.com/2011/04/fexpr.html) (along with [a new calculus to go with them](http://fexpr.blogspot.com/2014/03/continuations-and-term-rewriting-calculi.html)) are the clean, elegant solution, but this requires redesigning the whole language from ground up. Of course, if you're fine with a language not particularly designed for extensibility, and lazy evaluation is your top requirement, you could just use Haskell.)

#### Forcing promises manually

**Changed in v0.15.0.** *The functions `force1` and `force` now live in the top-level namespace of `unpythonic`, no longer in `unpythonic.syntax`.*

This is mainly useful if you `lazy[]` or `lazyrec[]` something explicitly, and want to compute its value outside a `with lazify` block.

We provide the functions `force1` and `force`. Using `force1`, if `x` is a `lazy[]` promise, it will be forced, and the resulting value is returned. If `x` is not a promise, `x` itself is returned, à la Racket. The function `force`, in addition, descends into containers (recursively). When an atom `x` (i.e. anything that is not a container) is encountered, it is processed using `force1`.

Mutable containers are updated in-place; for immutables, a new instance is created, but as a side effect the promise objects **in the input container** will be forced. Any container with a compatible `collections.abc` is supported. (See `unpythonic.collections.mogrify` for details.) In addition, as special cases `unpythonic.collections.box` and `unpythonic.llist.cons` are supported.

#### Binding constructs and auto-lazification

Why do we auto-lazify in certain kinds of binding constructs, but not in others? Function calls and let-bindings have one feature in common: both are guaranteed to bind only new names (even if that name is already in scope, they are distinct; the new binding will shadow the old one). Auto-lazification of all assignments, on the other hand, in a language that allows mutation is dangerous, because then this superficially innocuous code will fail:

```python
a = 10
a = 2*a
print(a)  # 20, right?
```

If we chose to auto-lazify assignments, then assuming a `with lazify` around the example, it would expand to:

```python
from unpythonic.syntax import macros, lazy
from unpythonic.syntax import force

a = lazy[10]
a = lazy[2*force(a)]
print(force(a))
```

In the second assignment, the `lazy[]` sets up a promise, which will force `a` *at the time when the containing promise is forced*, but at that time the name `a` points to a promise, which will force...

The fundamental issue is that `a = 2*a` is an imperative update. Therefore, to avoid this infinite loop trap for the unwary, assignments are not auto-lazified. Note that if we use two different names, this works just fine:

```python
from unpythonic.syntax import macros, lazy
from unpythonic.syntax import force

a = lazy[10]
b = lazy[2*force(a)]
print(force(b))
```

because now at the time when `b` is forced, the name `a` still points to the value we intended it to.

If you're sure you have *new definitions* and not *imperative updates*, just manually use `lazy[]` (or `lazyrec[]`, as appropriate) on the RHS. Or if it's fine to use eager evaluation, just omit the `lazy[]`, thus allowing Python to evaluate the RHS immediately.

Beside function calls (which bind the parameters of the callee to the argument values of the call) and assignments, there are many other binding constructs in Python. For a full list, see [here](http://excess.org/article/2014/04/bar-foo/), or locally [here](../unpythonic/syntax/scopeanalyzer.py), in function `get_names_in_store_context`. Particularly noteworthy in the context of lazification are the `for` loop and the `with` context manager.

In Python's `for`, the loop counter is an imperatively updated single name. In many use cases a rapid update is desirable for performance reasons, and in any case, the whole point of the loop is (almost always) to read the counter (and do something with the value) at least once per iteration. So it is much simpler, faster, and equally correct not to lazify there.

In `with`, the whole point of a context manager is that it is eagerly initialized when the `with` block is entered (and finalized when the block exits). Since our lazy code can transparently use both bare values and promises (due to the semantics of our `force1`), and the context manager would have to be eagerly initialized anyway, we can choose not to lazify there.

#### Note about TCO

To borrow a term from PG's On Lisp, to make `lazify` *pay-as-you-go*, a special mode in `unpythonic.tco.trampolined` is automatically enabled by `with lazify` to build lazify-aware trampolines in order to avoid a drastic performance hit (~10x) in trampolines built for regular strict code.

The idea is that the mode is enabled while any function definitions in the `with lazify` block run, so they get a lazify-aware trampoline when the `trampolined` decorator is applied. This should be determined lexically, but that's complicated to do API-wise, so we currently enable the mode for the dynamic extent of the `with lazify`. Usually this is close enough; the main case where this can behave unexpectedly is:

```python
@trampolined  # strict trampoline
def g():
    ...

def make_f():
    @trampolined  # which kind of trampoline is this?
    def f():
        ...
    return f

f1 = make_f()  # f1 gets the strict trampoline

with lazify:
    @trampolined  # lazify-aware trampoline
    def h():
        ...

    f2 = make_f()  # f2 gets the lazify-aware trampoline
```

TCO chains with an arbitrary mix of lazy and strict functions should work as long as the first function in the chain has a lazify-aware trampoline, because the chain runs under the trampoline of the first function (the trampolines of any tail-called functions are stripped away by the TCO machinery).

Tail-calling from a strict function into a lazy function should work, because all arguments are evaluated at the strict side before the call is made.

But tail-calling `strict -> lazy -> strict` will fail in some cases. The second strict callee may get promises instead of values, because the strict trampoline does not have the `maybe_force_args` (the mechanism `with lazify` uses to force the args when lazy code calls into strict code).

The reason we have this hack is that it allows the performance of strict code using unpythonic's TCO machinery, not even caring that a `lazify` exists, to be unaffected by the additional machinery used to support automatic lazy-strict interaction.


### `tco`: automatic tail call optimization for Python

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

All function definitions (`def` and `lambda`) lexically inside the block undergo TCO transformation. The functions are automatically `@trampolined`, and any tail calls in their return values are converted to `jump(...)` for the TCO machinery. Here *return value* is defined as:

 - In a `def`, the argument expression of `return`, or of a call to a known escape continuation.

 - In a `lambda`, the whole body, as well as the argument expression of a call to a known escape continuation.

What is a *known escape continuation* is explained below, in the section [TCO and `call_ec`](#tco-and-call_ec).

To find the tail position inside a compound return value, this recursively handles any combination of `a if p else b`, `and`, `or`; and from `unpythonic.syntax`, `do[]`, `let[]`, `letseq[]`, `letrec[]`. Support for `do[]` includes also any `multilambda` blocks that have already expanded when `tco` is processed. The macros `aif[]` and `cond[]` are also supported, because they expand into a combination of `let[]`, `do[]`, and `a if p else b`.

**CAUTION**: In an `and`/`or` expression, only the last item of the whole expression is in tail position. This is because in general, it is impossible to know beforehand how many of the items will be evaluated.

**CAUTION**: In a `def` you still need the `return`; it marks a return value. If you want the tail position to imply a `return`, use the combo `with autoreturn, tco` (on `autoreturn`, see below).

TCO is based on a strategy similar to MacroPy's `tco` macro, but using unpythonic's TCO machinery, and working together with the macros introduced by `unpythonic.syntax`. The semantics are slightly different; by design, `unpythonic` requires an explicit `return` to mark tail calls in a `def`. A call that is strictly speaking in tail position, but lacks the `return`, is not TCO'd, and Python's implicit `return None` then shuts down the trampoline, returning `None` as the result of the TCO chain.

#### TCO and continuations

The `tco` macro detects and skips any `with continuations` blocks inside the `with tco` block, because `continuations` already implies TCO. This is done **for the specific reason** of allowing the [Lispython dialect](https://github.com/Technologicat/pydialect) to use `with continuations`, because the dialect itself implies a `with tco` for the whole module (so the user code has no way to exit the TCO context).

The `tco` and `continuations` macros actually share a lot of the code that implements TCO; `continuations` just hooks into some callbacks to perform additional processing.

#### TCO and `call_ec`

(Mainly of interest for lambdas, which have no `return`, and for "multi-return" from a nested function.)

It is important to recognize a call to an escape continuation as such, because the argument given to an escape continuation is essentially a return value. If this argument is itself a call, it needs the TCO transformation to be applied to it.

For escape continuations in `tco` and `continuations` blocks, only basic uses of `call_ec` are supported, for automatically harvesting names referring to an escape continuation. In addition, the literal function names `ec`, `brk` and `throw` are always *understood as referring to* an escape continuation.

The name `ec`, `brk` or `throw` alone is not sufficient to make a function into an escape continuation, even though `tco` (and `continuations`) will think of it as such. The function also needs to actually implement some kind of an escape mechanism. An easy way to get an escape continuation, where this has already been done for you, is to use `call_ec`. Another such mechanism is the `catch`/`throw` pair.

See the docstring of `unpythonic.syntax.tco` for details.


### `continuations`: call/cc for Python

*Where control flow is your playground.*

We provide **genuine multi-shot continuations for Python**. Compare generators and coroutines, which are resumable functions, or in other words, single-shot continuations. In single-shot continuations, once execution passes a certain point, it cannot be rewound. Multi-shot continuations [can be emulated](https://gist.github.com/yelouafi/858095244b62c36ec7ebb84d5f3e5b02), but this makes the execution time `O(n**2)`, because when we want to restart again at an already passed point, the execution must start from the beginning, replaying the history. In contrast, **we implement continuations that can natively resume execution multiple times from the same point.**

This feature has some limitations and is mainly intended for experimenting with, and teaching, multi-shot continuations in a Python setting.

- There are seams between continuation-enabled code and regular Python code. (This happens with any feature that changes the semantics of only a part of a program.)

- There is no [`dynamic-wind`](https://docs.racket-lang.org/reference/cont.html#%28def._%28%28quote._~23~25kernel%29._dynamic-wind%29%29) (the generalization of `try/finally`, when control can jump back in to the block from outside it).

- Interaction of continuations with exceptions is not fully thought out.

- Interaction with async functions **is not even implemented**. An `async def` or `await` appearing inside a `with continuations` block is considered a syntax error.

- The implicit `cc` parameter might not be a good idea in the long run.
  - This design might or might not change in a future release. It suffers from the same lack of transparency, whence the same potential for bugs, as the implicit `this` in many languages (e.g. C++ and JavaScript).
  - Because `cc` is *declared* implicitly, it is easy to forget that *every* function definition anywhere inside the `with continuations` block introduces its own `cc` parameter.
    - This introduces a bug when one introduces an inner function, and attempts to use the outer `cc` inside the inner function body, forgetting that inside the inner function, the name `cc` points to **the inner function's** own `cc`.
      - The correct pattern is to `outercc = cc` in the outer function, and then use `outercc` inside the inner function body.
    - Not introducing its own `this` [was precisely why](http://tc39wiki.calculist.org/es6/arrow-functions/) the arrow function syntax was introduced to JavaScript in ES6.
  - Python gets `self` right in that while it is conveniently *passed* implicitly, it must be *declared* explicitly, eliminating the transparency issue.
  - On the other hand, a semi-explicit `cc`, like Python's `self`, was tried in an early version of this continuations subsystem, and it led to a lot of boilerplate. It is especially bad that to avoid easily avoidable bugs regarding passing in the wrong arguments, `cc` effectively must be a keyword parameter, necessitating the user to write `def f(x, *, cc)`. Not having to type out the `, *, cc` is much nicer, albeit not as pythonic.

#### General remarks on continuations

If you are new to continuations, see the [short and easy Python-based explanation](https://www.ps.uni-saarland.de/~duchier/python/continuations.html) of the basic idea.

We essentially provide a very loose pythonification of Paul Graham's continuation-passing macros, chapter 20 in [On Lisp](http://paulgraham.com/onlisp.html).

The approach differs from native continuation support (such as in Scheme or Racket) in that the continuation is captured only where explicitly requested with `call_cc[]`. This lets most of the code work as usual, while performing the continuation magic where explicitly desired.

As a consequence of the approach, our continuations are [*delimited*](https://en.wikipedia.org/wiki/Delimited_continuation) in the very crude sense that the captured continuation ends at the end of the body where the *currently dynamically outermost* `call_cc[]` was used. Notably, in `unpythonic`, a continuation eventually terminates and returns a value, without hijacking the rest of the whole-program execution.

Hence, if porting some code that uses `call/cc` from Racket to Python, in the Python version the `call_cc[]` may be need to be placed further out to capture the relevant part of the computation. For example, see `amb` in the demonstration below; a Scheme or Racket equivalent usually has the `call/cc` placed inside the `amb` operator itself, whereas in Python we must place the `call_cc[]` at the call site of `amb`.

Observe that while our outermost `call_cc` already somewhat acts like a prompt (in the sense of delimited continuations), we are currently missing the ability to set a prompt wherever (inside code that already uses `call_cc` somewhere) and terminate the capture there. So what we have right now is something between proper delimited continuations and classic whole-computation continuations - not really [co-values](http://okmij.org/ftp/continuations/undelimited.html), but not really delimited continuations, either.

For various possible program topologies that continuations may introduce, see [these clarifying pictures](callcc_topology.pdf).

For full documentation, see the docstring of `unpythonic.syntax.continuations`. The unit tests [[1]](../unpythonic/syntax/tests/test_conts.py) [[2]](../unpythonic/syntax/tests/test_conts_escape.py) [[3]](../unpythonic/syntax/tests/test_conts_gen.py) [[4]](../unpythonic/syntax/tests/test_conts_topo.py) may also be useful as usage examples.

**Note on debugging**: If a function containing a `call_cc[]` crashes below the `call_cc[]`, the stack trace will usually have the continuation function somewhere in it, containing the line number information, so you can pinpoint the source code line where the error occurred. (For a function `f`, it is named `f_cont_<some_uuid>`) But be aware that especially in complex macro combos (e.g. `continuations, curry, lazify`), the other block macros may spit out many internal function calls *after* the relevant stack frame that points to the actual user program. So check the stack trace as usual, but check further up than usual.

**Note on exceptions**: Raising an exception, or [signaling and restarting](features.md#handlers-restarts-conditions-and-restarts), will partly unwind the call stack, so the continuation *from the level that raised the exception* will be cancelled. This is arguably exactly the expected behavior.

Demonstration of continuations:

```python
from unpythonic.syntax import macros, continuations, call_cc

with continuations:
    # basic example - how to call a continuation manually:
    k = None  # kontinuation
    def setk(*args, cc):
        global k
        k = cc
        return args
    def doit():
        lst = ['the call returned']
        *more, = call_cc[setk('A')]
        return lst + list(more)
    print(doit())
    print(k('again'))
    print(k('thrice', '!'))

    # McCarthy's amb operator - yes, the real thing - in Python:
    stack = []
    def amb(lst, cc):
        if not lst:
            return fail()
        first, *rest = tuple(lst)
        if rest:
            ourcc = cc  # important: use any name other than "cc"
            stack.append(lambda: amb(rest, cc=ourcc))
        return first
    def fail():
        if stack:
            f = stack.pop()
            return f()

    # Pythagorean triples
    def pt():
        z = call_cc[amb(range(1, 21))]
        y = call_cc[amb(range(1, z+1)))]
        x = call_cc[amb(range(1, y+1))]
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
Code within a `with continuations` block is treated specially.
<details>
 <summary>Roughly:</summary>

> - Each function definition (`def` or `lambda`) in a `with continuations` block has an implicit formal parameter `cc`, **even if not explicitly declared** in the formal parameter list.
>   - The continuation machinery will set the default value of `cc` to the default continuation (`identity`), which just returns its arguments.
>     - The default value allows these functions to be called also normally without passing a `cc`. In effect, the function will then return normally.
>   - If `cc` is not declared explicitly, it is implicitly declared as a by-name-only parameter named `cc`, and the default value is set automatically.
>   - If `cc` is declared explicitly, the default value is set automatically if `cc` is in a position that can accept a default value, and no default has been set by the user.
>     - Positions that can accept a default value are the last positional parameter that has no default, and a by-name-only parameter in any syntactically allowed position.
>   - Having a hidden parameter is somewhat magic, but overall improves readability, as this allows declaring `cc` only where actually explicitly needed.
>     - **CAUTION**: Usability trap: in nested function definitions, each `def` and `lambda` comes with **its own** implicit `cc`.
>       - In the above `amb` example, the local variable is named `ourcc`, so that the continuation passed in from outside (into the `lambda`, by closure) will have a name different from the `cc` implicitly introduced by the `lambda` itself.
>       - This is possibly subject to change in a future version (pending the invention of a better API), but for now just be aware of this gotcha.
>   - Beside `cc`, there's also a mechanism to keep track of the captured tail of a computation, which is important to have edge cases work correctly. See the note on **pcc** (*parent continuation*) in the docstring of `unpythonic.syntax.continuations`, and [the pictures](callcc_topology.pdf).
>
> - In a function definition inside the `with continuations` block:
>   - Most of the language works as usual; especially, any non-tail function calls can be made as usual.
>   - `return value` or `return v0, ..., vn` is actually a tail-call into `cc`, passing the given value(s) as arguments.
>     - As in other parts of `unpythonic`, returning a `Values` means returning multiple-return-values.
>       - This is important if the return value is received by the assignment targets of a `call_cc[]`. If you get a `TypeError` concerning the arguments of a function with a name ending in `_cont`, check your `call_cc[]` invocations and the `return` in the call_cc'd function.
>       - **Changed in v0.15.0.** *Up to v0.14.3, multiple return values used to be represented as a `tuple`. Now returning a `tuple` means returning one value that is a tuple.*
>   - `return func(...)` is actually a tail-call into `func`, passing along (by default) the current value of `cc` to become its `cc`.
>     - Hence, the tail call is inserted between the end of the current function body and the start of the continuation `cc`.
>     - To override which continuation to use, you can specify the `cc=...` kwarg, as in `return func(..., cc=mycc)`.
>       - The `cc` argument, if passed explicitly, **must be passed by name**.
>         - **CAUTION**: This is **not** enforced, as the machinery does not analyze positional arguments in any great detail. The machinery will most likely break in unintuitive ways (or at best, raise a mysterious `TypeError`) if this rule is violated.
>     - The function `func` must be a defined in a `with continuations` block, so that it knows what to do with the named argument `cc`.
>       - Attempting to tail-call a regular function breaks the TCO chain and immediately returns to the original caller (provided the function even accepts a `cc` named argument).
>       - Be careful: `xs = list(args); return xs` and `return list(args)` mean different things.
>   - TCO is automatically applied to these tail calls. This uses the exact same machinery as the `tco` macro.
>
> - The `call_cc[]` statement essentially splits its use site into *before* and *after* parts, where the *after* part (the continuation) can be run a second and further times, by later calling the callable that represents the continuation. This makes a computation resumable from a desired point.
>   - The continuation is essentially a closure.
>   - Just like in Scheme/Racket, only the control state is checkpointed by `call_cc[]`; any modifications to mutable data remain.
>   - Assignment targets can be used to get the return value of the function called by `call_cc[]`.
>   - Just like in Scheme/Racket's `call/cc`, the values that get bound to the `call_cc[]` assignment targets on second and further calls (when the continuation runs) are the arguments given to the continuation when it is called (whether implicitly or manually).
>   - A first-class reference to the captured continuation is available in the function called by `call_cc[]`, as its `cc` argument.
>     - The continuation is a function that takes positional arguments, plus a named argument `cc`.
>       - The call signature for the positional arguments is determined by the assignment targets of the `call_cc[]`.
>       - The `cc` parameter is there only so that a continuation behaves just like any continuation-enabled function when tail-called, or when later used as the target of another `call_cc[]`.
>   - Basically everywhere else, `cc` points to the identity function - the default continuation just returns its arguments.
>     - This is unlike in Scheme or Racket, which implicitly capture the continuation at every expression.
>   - Inside a `def`, `call_cc[]` generates a tail call, thus terminating the original (parent) function. (Hence `call_ec` does not combo well with this.)
>   - At the top level of the `with continuations` block, `call_cc[]` generates a normal call. In this case there is no return value for the block (for the continuation, either), because the use site of the `call_cc[]` is not inside a function.
</details>

#### Differences between `call/cc` and certain other language features

 - Unlike **generators**, `call_cc[]` allows resuming also multiple times from an earlier checkpoint, even after execution has already proceeded further. Generators can be easily built on top of `call/cc`. [Python version](../unpythonic/syntax/tests/test_conts_gen.py), [Racket version](https://github.com/Technologicat/python-3-scicomp-intro/blob/master/examples/beyond_python/generator.rkt).
   - The Python version is a pattern that could be packaged into a macro with `mcpyrate`; the Racket version has been packaged as a macro.
   - Both versions are just demonstrations for teaching purposes. In production code, use the language's native functionality.
     - Python's built-in generators have no restriction on where `yield` can be placed, and provide better performance.
     - Racket's standard library provides [generators](https://docs.racket-lang.org/reference/Generators.html).

 - Unlike **exceptions**, which only perform escapes, `call_cc[]` allows to jump back at an arbitrary time later, also after the dynamic extent of the original function where the `call_cc[]` appears. Escape continuations are a special case of continuations, so exceptions can be built on top of `call/cc`.
   - [As explained in detail by Matthew Might](http://matt.might.net/articles/implementing-exceptions/), exceptions are fundamentally based on (escape) continuations; the *"unwinding the call stack"* mental image is ["not even wrong"](https://en.wikiquote.org/wiki/Wolfgang_Pauli).

So if all you want is generators or exceptions (or even resumable exceptions a.k.a. [conditions](http://www.gigamonkeys.com/book/beyond-exception-handling-conditions-and-restarts.html)), then a general `call/cc` mechanism is not needed. The point of `call/cc` is to provide the ability to *resume more than once* from *the same*, already executed point in the program. In other words, `call/cc` is a general mechanism for bookmarking the control state.

However, its usability leaves much to be desired. This has been noted e.g. in [Oleg Kiselyov: An argument against call/cc](http://okmij.org/ftp/continuations/against-callcc.html) and [John Shutt: Guarded continuations](http://fexpr.blogspot.com/2012/01/guarded-continuations.html). For example, Shutt writes:

*The traditional Scheme device for acquiring a first-class continuation object is **call/cc**, which calls a procedure and passes to that procedure the continuation to which that call would normally return.  Frankly, this was always a very clumsy way to work with continuations; one might almost suspect it was devised as an "esoteric programming language" feature, akin to INTERCAL's COME FROM statement.*

#### `call_cc` API reference

To keep things relatively straightforward, our `call_cc[]` is only allowed to appear **at the top level** of:

  - the `with continuations` block itself
  - a `def` or `async def`

Nested defs are ok; here *top level* only means the top level of the *currently innermost* `def`.

If you need to place `call_cc[]` inside a loop, use `@looped` et al. from `unpythonic.fploop`; this has the loop body represented as the top level of a `def`.

Multiple `call_cc[]` statements in the same function body are allowed. These essentially create nested closures.

In any invalid position, `call_cc[]` is considered a syntax error at macro expansion time.

**Syntax**:

In `unpythonic`, `call_cc` is a **statement**, with the following syntaxes:

```python
x = call_cc[func(...)]
*xs = call_cc[func(...)]
x0, ... = call_cc[func(...)]
x0, ..., *xs = call_cc[func(...)]
call_cc[func(...)]

x = call_cc[f(...) if p else g(...)]
*xs = call_cc[f(...) if p else g(...)]
x0, ... = call_cc[f(...) if p else g(...)]
x0, ..., *xs = call_cc[f(...) if p else g(...)]
call_cc[f(...) if p else g(...)]
```

*NOTE*: `*xs` may need to be written as `*xs,` in order to explicitly make the LHS into a tuple. The variant without the comma seems to work when run from a `.py` file with the `macropython` bootstrapper from [`mcpyrate`](https://pypi.org/project/mcpyrate/), but fails in code run interactively in the `mcpyrate` REPL.

*NOTE*: `f()` and `g()` must be **literal function calls**. Sneaky trickery (such as calling indirectly via `unpythonic.funutil.call` or `unpythonic.fun.curry`) is not supported. (The `prefix` and `curry` macros, however, **are** supported; just order the block macros as shown in the final section of this README.) This limitation is for simplicity; the `call_cc[]` needs to patch the `cc=...` kwarg of the call being made.

**Assignment targets**:

 - To destructure positional multiple-values (from a `Values` return value of the function called by the `call_cc`), use a tuple assignment target (comma-separated names, as usual). Destructuring *named* return values from a `call_cc` is currently not supported due to syntactic limitations.

 - The last assignment target may be starred. It is transformed into the vararg (a.k.a. `*args`, star-args) of the continuation function created by the `call_cc`. (It will capture a whole tuple, or any excess items, as usual.)

 - To ignore the return value, just omit the assignment part. Useful if `func` was called only to perform its side-effects (the classic side effect is to stash `cc` somewhere for later use).

**Conditional variant**:

 - `p` is any expression. If truthy, `f(...)` is called, and if falsey, `g(...)` is called.

 - Each of `f(...)`, `g(...)` may be `None`. A `None` skips the function call, proceeding directly to the continuation. Upon skipping, all assignment targets (if any are present) are set to `None`. The starred assignment target (if present) gets the empty tuple.

The main use case of the conditional variant is for things like:

```python
with continuations:
   k = None
   def setk(cc):
       global k
       k = cc
   def dostuff(x):
       call_cc[setk() if x > 10 else None]  # update stashed continuation only if x > 10
       ...
```

**Main differences to `call/cc` in Scheme and Racket**:

Compared to Scheme/Racket, where `call/cc` will capture also expressions occurring further up in the call stack, our `call_cc` may be need to be placed differently (further out, depending on what needs to be captured) due to the delimited nature of the continuations implemented here.

Scheme and Racket implicitly capture the continuation at every position, whereas we do it explicitly, only at the use sites of the `call_cc[]` macro.

Also, since there are limitations to where a `call_cc[]` may appear, some code may need to be structured differently to do some particular thing, if porting code examples originally written in Scheme or Racket.

Unlike `call/cc` in Scheme/Racket, our `call_cc` takes **a function call** as its argument, not just a function reference. Also, there's no need for it to be a one-argument function; any other args can be passed in the call. The `cc` argument is filled implicitly and passed by name; any others are passed exactly as written in the client code.

#### Combo notes

**CAUTION**: Do not use `with tco` inside a `with continuations` block; `continuations` already implies TCO. The `continuations` macro **makes no attempt** to skip `with tco` blocks inside it.

If you need both `continuations` and `multilambda` simultaneously, the incantation is:

```python
with multilambda, continuations:
    f = lambda x: [print(x), x**2]
    assert f(42) == 1764
```

This works, because the `continuations` macro understands already expanded `let[]` and `do[]`, and `multilambda` generates and expands a `do[]`. (Any explicit use of `do[]` in a lambda body or in a `return` is also ok; recall that macros expand from inside out.)

Similarly, if you need `quicklambda`, apply it first:

```python
with quicklambda, continuations:
    g = f[_**2]
    assert g(42) == 1764
```

This ordering makes the `f[...]` notation expand into standard `lambda` notation before `continuations` is expanded.

To enable both of these, use `with quicklambda, multilambda, continuations` (although the usefulness of this combo may be questionable).

#### Continuations as an escape mechanism

Pretty much by the definition of a continuation, in a `with continuations` block, a trick that *should* at first glance produce an escape is to set `cc` to the `cc` of the caller, and then return the desired value. There is however a subtle catch, due to the way we implement continuations.

First, consider this basic strategy, without any macros:

```python
from unpythonic import call_ec

def double_odd(x, ec):
    if x % 2 == 0:  # reject even "x"
        ec("not odd")
    return 2*x
@call_ec
def result1(ec):
    y = double_odd(42, ec)
    z = double_odd(21, ec)
    return z
@call_ec
def result2(ec):
    y = double_odd(21, ec)
    z = double_odd(42, ec)
    return z
assert result1 == "not odd"
assert result2 == "not odd"
```

Now, can we use the same strategy with the continuation machinery?

```python
from unpythonic.syntax import macros, continuations, call_cc

with continuations:
    def double_odd(x, ec, cc):
        if x % 2 == 0:
            cc = ec
            return "not odd"
        return 2*x
    def main1(cc):
        # cc actually has a default, so it's ok to not pass anything as cc here.
        y = double_odd(42, ec=cc)  # y = "not odd"
        z = double_odd(21, ec=cc)  # we could tail-call, but let's keep this similar to the first example.
        return z
    def main2(cc):
        y = double_odd(21, ec=cc)
        z = double_odd(42, ec=cc)
        return z
    assert main1() == 42
    assert main2() == "not odd"
```

In the first example, `ec` is the escape continuation of the `result1`/`result2` block, due to the placement of the `call_ec`. In the second example, the `cc` inside `double_odd` is the implicitly passed `cc`... which, naively, should represent the continuation of the current call into `double_odd`. So far, so good.

However, because the example code contains no `call_cc[]` statements, the actual value of `cc`, anywhere in this example, is always just `identity`. *It's not the actual continuation.* Even though we pass the `cc` of `main1`/`main2` as an explicit argument "`ec`" to use as an escape continuation (like the first example does with `ec`), it is still `identity` - and hence cannot perform an escape.

We must `call_cc[]` to request a capture of the actual continuation:

```python
from unpythonic.syntax import macros, continuations, call_cc

with continuations:
    def double_odd(x, ec, cc):
        if x % 2 == 0:
            cc = ec
            return "not odd"
        return 2*x
    def main1(cc):
        y = call_cc[double_odd(42, ec=cc)]  # <-- the only change is adding the call_cc[]
        z = call_cc[double_odd(21, ec=cc)]  # <--
        return z
    def main2(cc):
        y = call_cc[double_odd(21, ec=cc)]  # <--
        z = call_cc[double_odd(42, ec=cc)]  # <--
        return z
    assert main1() == "not odd"
    assert main2() == "not odd"
```

This variant performs as expected.

There's also a second, even subtler catch; instead of setting `cc = ec` and returning a value, just tail-calling `ec` with that value doesn't do what we want. This is because - as explained in the rules of the `continuations` macro, above - a tail-call is *inserted* between the end of the function, and whatever `cc` currently points to.

Most often that's exactly what we want, but in this particular case, it causes *both* continuations to run, in sequence. But if we overwrite `cc`, then the function's original `cc` argument (the one given by `call_cc[]`) is discarded, so it never runs - and we get the effect we want, *replacing* the `cc` by the `ec`.

Such subtleties arise essentially from the difference between a language that natively supports continuations (Scheme, Racket) and one that has continuations hacked on top of it as macros performing a CPS conversion only partially (like Python with `unpythonic.syntax`, or Common Lisp with PG's continuation-passing macros). The macro approach works, but the programmer needs to be careful.

#### What can be used as a continuation?

In `unpythonic` specifically, a continuation is just a function. ([As John Shutt has pointed out](http://fexpr.blogspot.com/2014/03/continuations-and-term-rewriting-calculi.html), in general this is not true. The calculus underlying the language becomes much cleaner if continuations are defined as a separate control flow mechanism orthogonal to function application. Continuations are not intrinsically a whole-computation device, either.)

The continuation function must be able to take as many positional arguments as the previous function in the TCO chain is trying to pass into it. Keep in mind that:

 - In `unpythonic`, multiple return values are represented as a `Values` object. So if your function does `return Values(a, b)`, and that is being fed into the continuation, this implies that the continuation must be able to take two positional arguments.

   **Changed in v0.15.0.** *Up to v0.14.3, a `tuple` used to represent multiple-return-values; now it denotes a single return value that is a tuple. The `Values` type allows not only multiple return values, but also **named** return values. These are fed as kwargs.*

 - At the end of any function in Python, at least an implicit bare `return` always exists. It will try to pass in the value `None` to the continuation, so the continuation must be able to accept one positional argument. (This is handled automatically for continuations created by `call_cc[]`. If no assignment targets are given, `call_cc[]` automatically creates one ignored positional argument that defaults to `None`.)

If there is an arity mismatch, Python will raise `TypeError` as usual. (The actual error message may be unhelpful due to the macro transformations; look for a mismatch in the number of values between a `return` and the call signature of a function used as a continuation (most often, the `f` in a `cc=f`).)

Usually, a function to be used as a continuation is defined inside the `with continuations` block. This automatically introduces the implicit `cc` parameter, and in general makes the source code undergo the transformations needed by the continuation machinery.

However, as the only exception to this rule, if the continuation is meant to act as the endpoint of the TCO chain - i.e. terminating the chain and returning to the original top-level caller - then it may be defined outside the `with continuations` block. Recall that in a `with continuations` block, returning an inert data value (i.e. not making a tail call) transforms into a tail-call into the `cc` (with the given data becoming its argument(s)); it does not set the `cc` argument of the continuation being called, or even require that it has a `cc` parameter that could accept one.

(Note also that a continuation that has no `cc` parameter cannot be used as the target of an explicit tail-call in the client code, since a tail-call in a `with continuations` block will attempt to supply a `cc` argument to the function being tail-called. Likewise, it cannot be used as the target of a `call_cc[]`, since this will also attempt to supply a `cc` argument.)

These observations make `unpythonic.fun.identity` eligible as a continuation, even though it is defined elsewhere in the library and it has no `cc` parameter.

#### This isn't `call/cc`!

Strictly speaking, `True`. The implementation is very different (much more than just [exposing a hidden parameter](https://www.ps.uni-saarland.de/~duchier/python/continuations.html)), not to mention it has to be a macro, because it triggers capture - something that would not need to be requested for separately, had we converted the whole program into [CPS](https://en.wikipedia.org/wiki/Continuation-passing_style).

The selective capture approach is however more efficient when we implement the continuation system in Python, indeed *on Python* (in the sense of [On Lisp](paulgraham.com/onlisp.html)), since we want to run most of the program the usual way with no magic attached. This way there is no need to sprinkle absolutely every statement and expression with a `def` or a `lambda`. (Not to mention Python's `lambda` is underpowered due to the existence of some language features only as statements, so we would need to use a mixture of both, which is already unnecessarily complicated.) Function definitions are not intended as [the only control flow construct](https://dspace.mit.edu/handle/1721.1/5753) in Python, so the compiler likely wouldn't optimize heavily enough (i.e. eliminate **almost all** of the implicitly introduced function definitions), if we attempted to use them as such.

Continuations only need to come into play when we explicitly request for one ([ZoP §2](https://www.python.org/dev/peps/pep-0020/)); this avoids introducing any more extra function definitions than needed.

The name is nevertheless `call_cc`, because the resulting behavior is close enough to `call/cc`.

Note our implementation provides a rudimentary form of *delimited* continuations. See [Oleg Kiselyov: Undelimited continuations are co-values rather than functions](http://okmij.org/ftp/continuations/undelimited.html). Delimited continuations return a value and can be composed, so they at least resemble functions (even though are not, strictly speaking, actually functions), whereas undelimited continuations do not even return. (For two different debunkings of the continuations-are-functions myth, approaching the problem from completely different angles, see the above post by Oleg Kiselyov, and [John Shutt: Continuations and term-rewriting calculi](http://fexpr.blogspot.com/2014/03/continuations-and-term-rewriting-calculi.html).)

Racket provides a thought-out implementation of delimited continuations and [prompts](https://docs.racket-lang.org/guide/prompt.html) to control them.

#### Why this syntax?

As for a function call in `call_cc[...]` vs. just a function reference: Typical lispy usage of `call/cc` uses an inline lambda, with the closure property passing in everything except `cc`, but in Python `def` is a statement. A technically possible alternative syntax would be:

```python
with call_cc(f):  # this syntax not supported!
    def f(cc):
        ...
```

but the expr macro variant provides better options for receiving multiple return values, and perhaps remains closer to standard Python.

The `call_cc[]` explicitly suggests that these are (almost) the only places where the `cc` argument obtains a non-default value. It also visually indicates the exact position of the checkpoint, while keeping to standard Python syntax.

(*Almost*: As explained above, a tail call passes along the current value of `cc`, and `cc` can be set manually.)



### `prefix`: prefix function call syntax for Python

Write Python almost like Lisp!

Lexically inside a `with prefix` block, any literal tuple denotes a function call, unless quoted. The first element is the operator, the rest are arguments. Bindings of the `let` macros and the top-level tuple in a `do[]` are left alone, but `prefix` recurses inside them (in the case of bindings, on each RHS).

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

If you use the `q`, `u` and `kw()` operators, they must be macro-imported. The `q`, `u` and `kw()` operators may only appear in a tuple inside a prefix block. In any invalid position, any of them is considered a syntax error at macro expansion time.

This comboes with `autocurry` for an authentic *Listhell* programming experience:

```python
from unpythonic.syntax import macros, autocurry, prefix, q, u, kw
from unpythonic import foldr, composerc as compose, cons, nil

with prefix, autocurry:  # important: apply prefix first, then autocurry
    mymap = lambda f: (foldr, (compose, cons, f), nil)
    double = lambda x: 2 * x
    (print, (mymap, double, (q, 1, 2, 3)))
    assert (mymap, double, (q, 1, 2, 3)) == ll(2, 4, 6)
```

**CAUTION**: The `prefix` macro is experimental and not intended for use in production code.


### `autoreturn`: implicit `return` in tail position

In Lisps, a function implicitly returns the value of the expression in tail position (along the code path being executed). Python's `lambda` also behaves like this (the whole body is just one return-value expression), but `def` doesn't.

Now `def` can, too:

```python
from unpythonic.syntax import macros, autoreturn

with autoreturn:
    def f():
        ...
        "I'll just return this"
    assert f() == "I'll just return this"

    def g(x):
        ...
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

Each `def` function definition lexically within the `with autoreturn` block is examined, and if the last item within the body is an expression `expr`, it is transformed into `return expr`. Additionally:

 - If the last item is an `if`/`elif`/`else` block, the transformation is applied to the last item in each of its branches.

 - If the last item is a `with` or `async with` block, the transformation is applied to the last item in its body.

 - If the last item is a `try`/`except`/`else`/`finally` block:
   - **If** an `else` clause is present, the transformation is applied to the last item in it; **otherwise**, to the last item in the `try` clause. These are the positions that indicate a normal return (no exception was raised).
   - In both cases, the transformation is applied to the last item in each of the `except` clauses.
   - The `finally` clause is not transformed; the intention is it is usually a finalizer (e.g. to release resources) that runs after the interesting value is already being returned by `try`, `else` or `except`.

If needed, the above rules are applied recursively to locate the tail position(s).

Any explicit `return` statements are left alone, so `return` can still be used as usual.

**CAUTION**: If the final `else` of an `if`/`elif`/`else` is omitted, as often in Python, then only the `else` item is in tail position with respect to the function definition - likely not what you want. So with `autoreturn`, the final `else` should be written out explicitly, to make the `else` branch part of the same `if`/`elif`/`else` block.

**CAUTION**: `for`, `async for`, `while` are currently not analyzed; effectively, these are defined as always returning `None`. If the last item in your function body is a loop, use an explicit return.

**CAUTION**: With `autoreturn` enabled, functions no longer return `None` by default; the whole point of this macro is to change the default return value. The default return value is `None` only if the tail position contains a statement other than `if`, `with`, `async with` or `try`.

If you wish to omit `return` in tail calls, this comboes with `tco`; just apply `autoreturn` first (either `with autoreturn, tco:` or in nested format, `with tco:`, `with autoreturn:`).


### `forall`: nondeterministic evaluation

Behaves the same as the multiple-body-expression tuple comprehension `unpythonic.amb.forall`, but implemented purely by AST transformation, with real lexical variables. This is essentially a macro implementation of Haskell's do-notation for Python, specialized to the List monad (but the code is generic and very short; see `unpythonic.syntax.forall`).

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

Assignment (with List-monadic magic) is `var << iterable`. It is only valid at the top level of the `forall` (e.g. not inside any possibly nested `let`).

`insist` and `deny` are not really macros; they are just the functions from `unpythonic.amb`, re-exported for convenience.

The error raised by an undefined name in a `forall` section is `NameError`.


## Convenience features

Small macros that are not essential but make some things easier or simpler.

### `cond`: the missing `elif` for `a if p else b`

Now lambdas too can have multi-branch conditionals, yet remain human-readable:

```python
from unpythonic.syntax import macros, cond

answer = lambda x: cond[x == 2, "two",
                        x == 3, "three",
                        "something else"]
print(answer(42))
```

Syntax is `cond[test1, then1, test2, then2, ..., otherwise]`. Expansion raises an error if the `otherwise` branch is missing.

Any part of `cond` may have multiple expressions by surrounding it with brackets:

```python
cond[[pre1, ..., test1], [post1, ..., then1],
     [pre2, ..., test2], [post2, ..., then2],
     ...
     [postn, ..., otherwise]]
```

To denote a single expression that is a literal list, use an extra set of brackets: `[[1, 2, 3]]`.


### `aif`: anaphoric if

This is mainly of interest as a point of [comparison with Racket](https://github.com/Technologicat/python-3-scicomp-intro/blob/master/examples/beyond_python/aif.rkt); `aif` is about the simplest macro that relies on either the lack of hygiene or breaking thereof.

```python
from unpythonic.syntax import macros, aif, it

aif[2*21,
    print(f"it is {it}"),
    print("it is falsey")]
```

Syntax is `aif[test, then, otherwise]`. The magic identifier `it` (which **must** be imported as a macro, if used) refers to the test result while (lexically) inside the `then` and `otherwise` parts of `aif`, and anywhere else is considered a syntax error at macro expansion time.

Any part of `aif` may have multiple expressions by surrounding it with brackets (implicit `do[]`):

```python
aif[[pre, ..., test],
    [post_true, ..., then],        # "then" branch
    [post_false, ..., otherwise]]  # "otherwise" branch
```

To denote a single expression that is a literal list, use an extra set of brackets: `[[1, 2, 3]]`.


### `autoref`: implicitly reference attributes of an object

Ever wish you could `with(obj)` to say `x` instead of `obj.x` to read attributes of an object? Enter the `autoref` block macro:

```python
from unpythonic.syntax import macros, autoref
from unpythonic import env

e = env(a=1, b=2)
c = 3
with autoref(e):
    assert a == 1  # a --> e.a
    assert b == 2  # b --> e.b
    assert c == 3  # no c in e, so just c
```

The transformation is applied for names in `Load` context only, including names found in `Attribute` or `Subscript` nodes.

Names in `Store` or `Del` context are not redirected. To write to or delete attributes of `o`, explicitly refer to `o.x`, as usual.

Nested autoref blocks are allowed (lookups are lexically scoped).

Reading with `autoref` can be convenient e.g. for data returned by [SciPy's `.mat` file loader](https://docs.scipy.org/doc/scipy/reference/generated/scipy.io.loadmat.html).

See the [unit tests](../unpythonic/syntax/tests/test_autoref.py) for more usage examples.

This is similar to the JavaScript [`with` construct](https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Statements/with), which is nowadays [deprecated](https://2ality.com/2011/06/with-statement.html). See also [the ES6 reference on `with`](https://www.ecma-international.org/ecma-262/6.0/#sec-with-statement).

**CAUTION**: This construct was deprecated in JavaScript **for security reasons**. Since the autoref'd object **will hijack all name lookups**, use `with autoref` only with an object you trust!

**CAUTION**: `with autoref` also complicates static code analysis or makes it outright infeasible, for the same reason. It is impossible to statically know whether something that looks like a bare name in the source code is actually a true bare name, or a reference to an attribute of the autoref'd object. That status can also change at any time, since the lookup is dynamic, and attributes can be added and removed dynamically.


## Testing and debugging

### `unpythonic.test.fixtures`: a test framework for macro-enabled Python

**Added in v0.14.3.**

We provide a lightweight, `mcpyrate`-based test framework for testing macro-enabled Python:

```python
from unpythonic.syntax import macros, test, test_raises, fail, error, warn, the
from unpythonic.test.fixtures import session, testset, terminate, returns_normally

def f():
    raise RuntimeError("argh!")

def g(a, b):
    return a * b
    fail["this line should be unreachable"]

count = 0
def counter():
    global count
    count += 1
    return count

with session("simple framework demo"):
    with testset():
        test[2 + 2 == 4]
        test_raises[RuntimeError, f()]
        test[returns_normally(g(2, 3))]
        test[g(2, 3) == 6]
        # Use `the[]` (or several) in a `test[]` to declare what you want to inspect if the test fails.
        test[counter() < the[counter()]]

    with testset("outer"):
        with testset("inner 1"):
            test[g(6, 7) == 42]
        with testset("inner 2"):
            test[None is None]
        with testset("inner 3"):  # an empty testset is considered 100% passed.
            pass
        with testset("inner 4"):
            warn["This testset not implemented yet"]

    with testset("integration"):
        try:
            import blargly
        except ImportError:
            error["blargly not installed, cannot test integration with it."]
        else:
            ... # blargly integration tests go here

    with testset(postproc=terminate):
        test[2 * 2 == 5]  # fails, terminating the nearest dynamically enclosing `with session`
        test[2 * 2 == 4]  # not reached
```

By default, running this script through the `macropython` wrapper (from `mcpyrate`) will produce an ANSI-colored test report in the terminal. To actually see how the output looks like, for actual runnable examples, see `unpythonic`'s own automated tests.

If you want to turn coloring off (e.g. for redirecting stderr to a file), see the `TestConfig` bunch of constants in `unpythonic.test.fixtures`.

The following is an overview of the framework. For details, look at the docstrings of the various constructs in `unpythonic.test.fixtures` (which provides much of this), those of the test macros, and finally, the automated tests of `unpythonic` itself.

How to test code using conditions and restarts can be found in [`unpythonic.tests.test_conditions`](../unpythonic/tests/test_conditions.py).

How to test macro utilities (e.g. syntax transformer functions that operate on ASTs) can be found in [`unpythonic.syntax.tests.test_letdoutil`](../unpythonic/syntax/tests/test_letdoutil.py).

#### Overview

We provide the low-level syntactic constructs `test[]`, `test_raises[]` and `test_signals[]`, with the usual meanings. The last one is for testing code that uses the `signal` function and its sisters (related to conditions and restarts à la Common Lisp); see [`unpythonic.conditions`](features.md#handlers-restarts-conditions-and-restarts).

By default, the `test[expr]` macro asserts that the value of `expr` is truthy. If you want to assert only that `expr` runs to completion normally, use `test[returns_normally(expr)]`.

The test macros also come in block variants, `with test`, `with test_raises[exctype]`, `with test_signals[exctype]`.

As usual in test frameworks, the test constructs behave somewhat like `assert`, with the difference that a failure or error will not abort the whole unit (unless explicitly asked to do so). There is no return value; upon success, the test constructs return `None`. Upon failure (test assertion not satisfied) or error (unexpected exception or signal), the failure or error is reported, and further tests continue running.

All the test variants catch any uncaught exceptions and signals from inside the test expression or block. Any unexpected uncaught exception or signal is considered an error.

Because `unpythonic.test.fixtures` is, by design, a minimalistic *no-framework* (cf. "NoSQL"), it is up to you to define - in your custom test runner - whether having any failures, errors or warnings should lead to the whole test suite failing (whether the program's exit code is zero is important e.g. for GitHub's CI workflows). For example, in `unpythonic`'s own tests (see the very short [`runtests.py`](../runtests.py)), warnings do not cause the test suite to fail, but errors and failures do.

#### Testing syntax quick reference

**Imports** - complete list:

```python
from unpythonic.syntax import (macros, test, test_raises, test_signals,
                               fail, error, warn, the, expand_testing_macros_first)
from unpythonic.test.fixtures import (session, testset, returns_normally,
                                      catch_signals, terminate)
```

**Overall structure** of typical unit test module:

```python
from unpythonic.syntax import macros, test, test_raises, the
from unpythonic.test.fixtures import session, testset

def runtests():
    with testset("something 1"):
        ...
    with testset("something 2"):
        ...
    ...

if __name__ == '__main__':  # pragma: no cover
    with session(__file__):
        runtests()
```

The if-main idiom allows running this test module individually, but it is tagged with `# pragma: no cover`, so that the coverage reporter won't yell about it when the module is run by the test runner as part of the complete test suite (which, incidentally, is also a good opportunity to measure coverage).

If you want to ensure that testing macros expand before anything else - including your own code-walking block macros (when you have tests inside the body) - import the macro `expand_testing_macros_first`, and put a `with expand_testing_macros_first` around the affected code. (See [Expansion order](#expansion-order), below.)

**Sessions and testsets**:

```python
with session(name):
    with testset(name):
        ...

    with testset(name):
        ...
        with testset(name):
            ...

    with testset(name):
        with catch_signals(False):
            ...
```

Each `name` above is human-readable and optional. The purpose of the naming feature is to improve [scannability](https://www.teachingenglish.org.uk/article/scanning) of the testing report for the human reader.

Note that even if `name` is omitted, the parentheses are still mandatory, because `session` and `testset` are just garden variety context managers that must be instantiated in order for them to perform their jobs.

A session implicitly introduces a top-level testset, for convenience.

Testsets can be nested arbitrarily deep.

The function `terminate`, when called, exits the test session immediately. Usually it is not needed, but it is provided for convenience.

Additional tools for code using **conditions and restarts**:

The `catch_signals` context manager controls the signal barrier of `with testset` and the `test` family of syntactic constructs. It is provided for writing tests for code that uses conditions and restarts.

Used as `with catch_signals(False)`, it disables the signal barrier. Within the dynamic extent of the block, an uncaught signal (in the sense of `unpythonic.conditions.signal` and its sisters) is not considered an error. This can be useful, because sometimes leaving a signal uncaught is the right thing to do. See [`unpythonic.tests.test_conditions`](../unpythonic/tests/test_conditions.py) for examples.

It can be nested. Used as `with catch_signals(True)`, it re-enables the barrier, if currently disabled.

When a `with catch_signals` block exits, the previous state of the signal barrier is automatically restored.

**Expression** forms:

```python
test[expr]
test[expr, message]
test[returns_normally(expr)]
test[returns_normally(expr), message]
test_raises[exctype, expr]
test_raises[exctype, expr, message]
test_signals[exctype, expr]
test_signals[exctype, expr, message]
fail[message]
error[message]
warn[message]
```

Inside a `test`, the helper macro `the[]` is available to mark interesting subexpressions inside `expr`, for failure and error reporting. An `expr` may contain an arbitrary number of `the[]`. By default, if `expr` is a comparison, the leftmost term is automatically marked (so that e.g. `test[x < 3]` will automatically report the value of `x` if the test fails); otherwise nothing. The default is only used if there is no explicit `the[]` inside `expr`.

The constructs `test_raises`, `test_signals`, `fail`, `error` and `warn` do **not** support `the[]`.

Tests can be nested; this is sometimes useful as an explicit signal barrier.

Note the macros `error[]` and `warn[]` have nothing to do with the functions with the same name in `unpythonic.conditions`. The macros are part of the test framework; the functions with the same name are signaling protocols of the conditions and restarts system. Following the usual naming conventions in both systems, this naming conflict is unfortunately what we get.

**Block** forms:

```python
with test:
    body
    ...
with test:
    body
    ...
    return expr
with test[message]:
    body
    ...
with test[message]:
    body
    ...
    return expr
with test_raises[exctype]:
    body
    ...
with test_raises[exctype, message]:
    body
    ...
with test_signals[exctype]:
    body
    ...
with test_signals[exctype, message]:
    body
    ...
```

In `with test`, the `the[]` helper macro is available. It can be used to mark any number of expressions and/or subexpressions in the block body.

The constructs `with test_raises`, `with test_signals` do **not** support `the[]`.

Tests can be nested; this is sometimes useful as an explicit signal barrier.

#### Expansion order

**Changed in v0.15.0**. *The testing macros now expand outside-in; this allows `mcpyrate.debug.step_expansion` to treat them as a separate step. In v0.14.3, which introduced the test framework, they used to be two-pass macros.*

Your test macro invocations may get partially expanded code, if those invocations reside in the body of an invocation of a block macro that also expands outside-in:

```python
with yourblockmacro:  # outside-in
    test[...]
```

Here the `...` may be edited by `yourblockmacro` before `test[]` sees it. (It likely **will** be edited, since this pattern will commonly appear in the tests for `yourblockmacro`, where the whole point is to have the `...` depend on what `yourblockmacro` outputs.)

If you need testing macros to expand before anything else even in this scenario (so you can more clearly see where in the unexpanded source code a particular expression came from), you can do this:

```python
from unpythonic.syntax import macros, expand_testing_macros_first

with expand_testing_macros_first:
    with yourblockmacro:
        test[...]
```

The `expand_testing_macros_first` macro is itself a code-walking block macro that does as it says on the tin. The testing macros are identified by scanning the bindings of the current macro expander; names don't matter, so it respects as-imports.

This does imply that `your_block_macro` will then receive the expanded form of `test[...]` as input, but that's macros for you. You'll have to choose which is more important: seeing the unexpanded code in error messages, or receiving unexpanded `test[]` expressions in `yourblockmacro`.

#### `with test`: test blocks

Test blocks are meant for testing code that requires Python statements; i.e. does not fit into Python's expression sublanguage.

In `unpythonic.test.fixtures`, **a test block is implicitly lifted into a function**. Hence, any local variables assigned to inside the block remain local to the implicit function. Use Python's `nonlocal` and `global` keywords, if needed.

By default, a `with test` block asserts just that it completes normally. If you instead want to assert that an expression is truthy, use `return expr` to terminate the implicit function and return the value of the desired `expr`. The return value is passed to the test asserter for checking that it is truthy.

(Another way to view the default behavior is that the `with test` macro injects a `return True` at the end of the block, if there is no `return`. This is actually how the default behavior is implemented.)

The `with test_raises[exctype]` and `with test_signals[exctype]` blocks assert that the block raises (respectively, signals) the declared exception (condition) type. These blocks are implicitly lifted into functions, too, but they do not check the return value. For them, **not** raising/signaling the declared exception/condition type is considered a test failure. Raising/signaling some other (hence unexpected) exception/condition type is considered an error.

#### `the`: capture the value of interesting subexpressions

The point of `unpythonic.test.fixtures` is to make testing macro-enabled Python as frictionless as reasonably possible.

Inside a `test[]` expression, or anywhere within the code in a `with test` block, the `the[]` macro can be used to declare any number of subexpressions as interesting, for capturing the source code and value into the test failure message, which is shown if the test fails. Each `the[]` captures one subexpression (as many times as it is evaluated, in the order evaluated).

Because test macros expand outside-in, the source code is captured before any nested inside-out macros expand. (Many macros defined by `unpythonic` expand inside-out.) The value is captured at run time as a side effect just after the value has been evaluated.

By default (if no explicit `the[]` is present), `test[]` implicitly inserts a `the[]` for the leftmost term if the top-level expression is a comparison (common use case), and otherwise does not capture anything.

When nothing is captured, if the test fails, the value of the whole expression is shown. Of course, you'll then already know the value is falsey, but there's still the possibly useful distinction of whether it's, say, `False`, `None`, `0` or `[]`.

A `test[]` or `with test` can have any number of subexpressions marked as `the[]`. It is possible to even nest a `the[]` inside another `the[]`, if you need the value of some subexpression as well as one of *its* subexpressions. The captured values are gathered, in the order they were evaluated (by Python's standard evaluation rules), into a list that is shown upon test failure.

Following Python's standard evaluation rules implies that short-circuiting expressions such as `test[all(pred(the[x]) for x in iterable)]` may actually capture fewer `x` than `iterable` has, because `all` will terminate evaluation after the first failing term (i.e. the first one for which `pred(x)` is falsey). Similarly, expressions involving the logical `and` and `or` operators (which in Python are short-circuiting) might not evaluate all of the terms before the test is known to fail (and evaluation terminates).

In case of nested `test[]` or nested `with test`, each `the[...]` is understood as belonging to the lexically innermost surrounding test.

The `the[]` mechanism is smart enough to skip reporting trivialities for literals, such as `(1, 2, 3) = (1, 2, 3)` in `test[4 in the[(1, 2, 3)]]`, or `4 = 4` in `test[4 in (1, 2, 3)]`. In the second case, note the implicit `the[]` on the LHS, because `in` is a comparison operator.

If nothing but such trivialities were captured, the failure message will instead report the value of the whole expression. (The captures still remain inspectable in the exception instance.)

To make testing/debugging macro code more convenient, the `the[]` mechanism automatically unparses an AST value into its source code representation for display in the test failure message. This is meant for debugging macro utilities, to which a test case hands some quoted code (i.e. code lifted into its AST representation using mcpyrate's `q[]` macro). See [`unpythonic.syntax.tests.test_letdoutil`](unpythonic/syntax/tests/test_letdoutil.py) for some examples. (Note the unparsing is done for display only; the raw value remains inspectable in the exception instance.)

**CAUTION**: The source code is back-converted from the AST representation; hence its surface syntax may look slightly different to the original (e.g. extra parentheses). See `mcpyrate.unparse`.

**CAUTION**: The name of the `the[]` construct was inspired by Common Lisp, but the semantics are completely different. Common Lisp's `THE` is a return-type declaration (pythonistas would say *return-type annotation*), meant as a hint for the compiler to produce performance-optimized compiled code (see [chapter 32 of Peter Seibel's Practical Common Lisp](http://www.gigamonkeys.com/book/conclusion-whats-next.html)), whereas our `the[]` captures a value for test reporting. The only common factors are the name, and that neither construct changes the semantics of the marked code, much. In `unpythonic.test.fixtures`, the reason behind picking this name was that it doesn't change the flow of the source code as English that much, specifically to suggest, between the lines, that it doesn't change the semantics much. The reasoning behind CL's `THE` may be similar.

#### Test sessions and testsets

The `with session()` in the example session above is optional. The human-readable session name is also optional, used for display purposes only. The session serves two roles: it provides an exit point for `terminate`, and defines an implicit top-level `testset`.

Tests can optionally be grouped into testsets. Each `testset` tallies passed, failed and errored tests within it, and displays the totals when it exits. Testsets can be named and nested.

It is useful to have at least one `testset` (the implicit top-level one established by `with session` is sufficient), because the `testset` mechanism forms one half of the test framework. It is possible to use the test macros without a `testset`, but that is only intended for building alternative test frameworks.

Testsets also provide an option to locally install a `postproc` handler that gets a copy of each failure or error in that testset (and by default, any of its inner testsets), after the failure or error has been printed. In nested testsets, the dynamically innermost `postproc` wins. A failure is an instance of `unpythonic.test.fixtures.TestFailure`, an error is an instance of `unpythonic.test.fixtures.TestError`, and a warning is an instance of `unpythonic.test.fixtures.TestWarning`. All three inherit from `unpythonic.test.fixtures.TestingException`. Beside the human-readable message, these exception types contain attributes with programmatically inspectable information about what happened.

If you want to set a default global `postproc`, which is used when no local `postproc` is in effect, this too is configured in the `TestConfig` bunch of constants in `unpythonic.test.fixtures`.

The `with testset` construct comes with one other important feature. The nearest dynamically enclosing `with testset` **catches any stray exceptions or signals** that occur within its dynamic extent, but outside a test construct.

In case of an uncaught signal, the error is reported, and the testset resumes.

In case of an uncaught exception, the error is reported, and the testset terminates, because the exception model does not support resuming.

Catching of uncaught *signals*, in both the low-level `test` constructs and the high-level `testset`, can be disabled using `with catch_signals(False)`. This is useful in testing code that uses conditions and restarts; sometimes allowing a signal (e.g. from `unpythonic.conditions.warn`) to remain uncaught is the right thing to do.

#### Producing unconditional failures, errors, and warnings

The helper macros `fail[message]`, `error[message]` and `warn[message]` unconditionally produce a test failure, a test error, or a testing warning, respectively. This can be useful:

- `fail[...]` if that expression should be unreachable when the code being tested works properly.
- `error[...]` if some part of your tests is unable to run.
- `warn[...]` if some tests are temporarily disabled and need future attention, e.g. for syntactic compatibility to make the code run for now on an old Python version.

Currently (v0.14.3), warnings produced by `warn[]` are not counted in the total number of tests run. But you can still get the warning count from the separate counter `unpythonic.test.fixtures.tests_warned` (see `unpythonic.collections.box`; basically you can `b.get()` or `unbox(b)` to read the value currently inside a box).

#### Advanced: building a custom test framework

If `unpythonic.test.fixtures` does not fit your needs and you want to experiment with creating your own framework, the test asserter macros are reusable. For reference, their implementations can be found in `unpythonic.syntax.testingtools`. They refer to a few objects in `unpythonic.test.fixtures`; consider these a common ground that is not strictly part of the surrounding framework.

Start by reading the docstring of the `test` macro, which documents some low-level details.

Set up a condition handler to intercept test failures and errors. These will be signaled via `cerror`, using the conditions and restarts mechanism. See `unpythonic.conditions`. Report the failure/error in any way you desire, and then invoke the `proceed` restart (from your condition handler) to let testing continue.

Look at the implementation of `testset` as an example.

#### Why another test framework?

Because `unpythonic` is effectively a language extension, the standard options were not applicable.

The standard library's [`unittest`](https://docs.python.org/3/library/unittest.html) fails with `unpythonic` due to technical reasons related to `unpythonic`'s unfortunate choice of module names. The `unittest` framework chokes if a module in a library exports anything that has the same name as the module itself, and the library's top-level init then `from`-imports that construct into its namespace, causing the *module reference*, that was [implicitly brought in](http://python-notes.curiousefficiency.org/en/latest/python_concepts/import_traps.html#the-submodules-are-added-to-the-package-namespace-trap) by the `from`-import itself, to be overwritten with what was explicitly imported: a reference to the construct that has the same name as the module. (Bad naming on my part, yes, but as of v0.15.0, I see no reason to cross that particular bridge yet.)

Also, in my opinion, `unittest` is overly verbose to use; automated tests are already a particularly verbose kind of program, even if the testing syntax is minimal.

[Pytest](https://docs.pytest.org/en/latest/), on the other hand, provides compact syntax by hijacking the assert statement, but its import hook (to provide that syntax) can't coexist with a macro expander, which also needs to install a different import hook. It's also fairly complex.

The central functional requirement for whatever would be used for testing `unpythonic` was to be able to easily deal with macro-enabled Python. No hoops to jump through, compared to testing regular Python, in order to be able to test all of `unpythonic` (including `unpythonic.syntax`) in a uniform way.

Simple and minimalistic would be a bonus. As of v0.14.3, the whole test framework is about 1.8k SLOC, counting docstrings, comments and blanks; under 700 SLOC if counting only active code lines. Add another 800 SLOC (all) / 200 SLOC (active code lines) for the machinery that implements conditions and restarts.

The framework will likely still evolve a bit as I find more holes in the [UX](https://en.wikipedia.org/wiki/User_experience) - which so far has led to features such as `the[]` and AST value auto-unparsing - but most of the desired functionality is already there. For example, I consider pytest-style implicit fixtures and a central test discovery system as outside the scope of this system.

It's clear that `unpythonic.test.fixtures` is not going to replace `pytest`, nor does it aim to do so - [any more than Chuck Moore's Forth-based VLSI tools](https://yosefk.com/blog/my-history-with-forth-stack-machines.html) were intended to replace the commercial [VLSI](https://en.wikipedia.org/wiki/Very_Large_Scale_Integration) offerings.

What we have is small, simple, custom-built for its purpose (works well with macro-enabled Python; integrates with conditions and restarts), arguably somewhat pedagogic (demonstrates how to build a test framework in under 700 active SLOC), and importantly, works just fine.

#### Etymology and roots

[Test fixture](https://en.wikipedia.org/wiki/Test_fixture) *is an environment used to consistently test some item, device, or piece of software*. In automated tests, it is typically a piece of code that is reused within the test suite of a project, to perform initialization and/or teardown tasks common to several test cases.

A test framework can be reused across many different projects, and the error-catching and reporting code, if anything, is something that is shared across all test cases. Also, following our naming scheme, it had to be called `unpythonic.test.something`, and `fixtures` just happened to fit the theme.

Inspired by [Julia](https://julialang.org/)'s standard-library [`Test` package](https://docs.julialang.org/en/v1/stdlib/Test/), and [chapter 9 of Peter Seibel's Practical Common Lisp](http://www.gigamonkeys.com/book/practical-building-a-unit-test-framework.html).


### `dbg`: debug-print expressions with source code

**Changed in 0.14.2.** The `dbg[]` macro now works in the REPL, too. You can use `mcpyrate.repl.console` (a.k.a. `macropython -i` in the shell) or the IPython extension `mcpyrate.repl.iconsole`.

[DRY](https://en.wikipedia.org/wiki/Don't_repeat_yourself) out your [qnd](https://en.wiktionary.org/wiki/quick-and-dirty) debug printing code. Both block and expression variants are provided:

```python
from unpythonic.syntax import macros, dbg

with dbg:
    x = 2
    print(x)   # --> [file.py:5] x: 2

with dbg:
    x = 2
    y = 3
    print(x, y, 17 + 23)   # --> [file.py:10] x: 2, y: 3, (17 + 23): 40
    print(x, y, 17 + 23, sep="\n")   # --> [file.py:11] x: 2
                                     #     [file.py:11] y: 3
                                     #     [file.py:11] (17 + 23): 40

z = dbg[25 + 17]  # --> [file.py:15] (25 + 17): 42
assert z == 42    # surrounding an expression with dbg[...] doesn't alter its value
```

**In the block variant**, just like in `nb`, a custom print function can be supplied as the first positional argument. This avoids transforming any uses of built-in `print`:

```python
prt = lambda *args, **kwargs: print(*args)

with dbg[prt]:
    x = 2
    prt(x)     # --> ('x',) (2,)
    print(x)   # --> 2

with dbg[prt]:
    x = 2
    y = 17
    prt(x, y, 1 + 2)  # --> ('x', 'y', '(1 + 2)'), (2, 17, 3)

```

The reference to the custom print function (i.e. the argument to the `dbg` block) **must be a bare name**. Support for methods may or may not be added in a future version.

**In the expr variant**, to customize printing, just assign a function to the dynvar `dbgprint_expr` via `with dyn.let(dbgprint_expr=...)`. If no custom printer is set, a default implementation is used.

For details on implementing custom debug print functions, see the docstrings of `unpythonic.syntax.dbgprint_block` and `unpythonic.syntax.dbgprint_expr`, which provide the default implementations.

**CAUTION**: The source code is back-converted from the AST representation; hence its surface syntax may look slightly different to the original (e.g. extra parentheses). See `mcpyrate.unparse`.

Inspired by the [dbg macro in Rust](https://doc.rust-lang.org/std/macro.dbg.html).

## Other

Stuff that didn't fit elsewhere.

### `nb`: silly ultralight math notebook

Mix regular code with math-notebook-like code in a `.py` file. To enable notebook mode, `with nb`:

```python
from unpythonic.syntax import macros, nb
from sympy import symbols, pprint

with nb:
    2 + 3
    assert _ == 5
    _ * 42
    assert _ == 210

with nb[pprint]:
    x, y = symbols("x, y")
    x * y
    assert _ == x * y
    3 * _
    assert _ == 3 * x * y
```

Expressions at the top level auto-assign the result to `_`, and auto-print it if the value is not `None`. Only expressions do that; for any statement that is not an expression, `_` retains its previous value.

A custom print function can be supplied as the first positional argument to `nb`. This is useful with SymPy (and [latex-input](https://github.com/clarkgrubb/latex-input) to use α, β, γ, ... as actual variable names).

Obviously not intended for production use, although is very likely to work anywhere.

## Meta

Is this just a set of macros, a language extension, or a compiler for a new language that just happens to be implemented in `mcpyrate`, à la *On Lisp*? All of the above, really.

### The xmas tree combo

The macros in `unpythonic.syntax` are designed to work together, but some care needs to be taken regarding the order in which they expand. This complexity unfortunately comes with any pick-and-mix-your-own-language kit, because some features inevitably interact. For example, it is possible to lazify [continuation-enabled](https://en.wikipedia.org/wiki/Continuation-passing_style) code, but running the transformations the other way around produces nonsense.

The correct **xmas tree invocation** is:

```python
with prefix, autoreturn, quicklambda, multilambda, envify, lazify, namedlambda, autoref, autocurry, tco:
    ...
```

Here `tco` can be replaced with `continuations`, if needed.

We have taken into account that:

 - Outside-in: `prefix`, `autoreturn`, `quicklambda`, `multilambda`
 - Two-pass: `envify`, `lazify`, `namedlambda`, `autoref`, `autocurry`, `tco`/`continuations`

[The dialect examples](dialects.md) use this ordering.

For simplicity, **the block macros make no attempt to prevent invalid combos**, unless there is a specific technical reason to do that for some particular combination. Be careful; e.g. don't nest several `with tco` blocks (lexically), that won't work.

As an example of a specific technical reason, the `tco` macro skips already expanded `with continuations` blocks lexically contained within the `with tco`. This allows the [Lispython dialect](dialects/lispython.md) to support `continuations`.


#### AST edit order vs. macro invocation order

The **AST edits** performed by the block macros are designed to run in the following order (leftmost first):

```
prefix > autoreturn, quicklambda > multilambda > continuations or tco > ...
                                                ... > autocurry > namedlambda, autoref > lazify > envify
```

The `let_syntax` (and `abbrev`) block may be placed anywhere in the chain; just keep in mind what it does.

The `dbg` block can be run at any position after `prefix` and before `tco` (or `continuations`). It must be able to see function calls in Python's standard format, for detecting calls to the print function.

The correct ordering for **block macro invocations** - which is the actual user-facing part - is somewhat complicated by the fact that some of the above are two-pass macros. Consider this artificial example, where `mac` is a two-pass macro:

```python
with mac:
    with cheese:
        ...
```

The invocation `with mac` is *lexically on the outside*, thus the macro expander sees it first. The expansion order then becomes:

 1. First pass (outside in) of `with mac`.
 2. Explicit recursion by `with mac`. This expands the `with cheese`.
 3. Second pass (inside out) of `with mac`.

So, for example, even though `lazify` must *perform its AST edits* after `autocurry`, it happens to be a two-pass macro. The first pass (outside in) only performs some preliminary analysis; the actual lazification happens in the second pass (inside out). So the correct invocation comboing these two is `with lazify, autocurry`. Similarly, `with lazify, continuations` is correct, even though the CPS transformation must occur first; these are both two-pass macros that perform their edits in the inside-out pass.

Further details on individual block macros can be found in our [notes on macros](design-notes.md#detailed-notes-on-macros).


#### Single-line vs. multiline invocation format

Example combo in the single-line format:

```python
with autoreturn, lazify, tco:
    ...
```

The same combo in the multiline format:

```python
with autoreturn:
  with lazify:
    with tco:
      ...
```

In MacroPy (which was used up to v0.14.3), there sometimes were [differences](https://github.com/azazel75/macropy/issues/21) between the behavior of the single-line and multi-line invocation format, but in `mcpyrate` (which is used by v0.15.0 and later), they should behave the same.

With `mcpyrate`, there is still [a minor difference](https://github.com/Technologicat/mcpyrate/issues/3) if there are at least three nested macro invocations, and a macro is scanning the tree for another macro invocation; then the tree looks different depending on whether the single-line or the multi-line format was used. The differences in that are as one would expect knowing [how `with` statements look like](https://greentreesnakes.readthedocs.io/en/latest/nodes.html#With) in the Python AST. The reason the difference manifests only for three or more macro invocations is that `mcpyrate` pops the macro that is being expanded before it hands over the tree to the macro code; hence if there are only two, the inner tree will have only one "context manager" in its `with`.

**NOTE** to the curious, and to future documentation maintainers: To see if something is a two-pass macro, grep the codebase for `expander.visit_recursively`; that is the *explicit recursion* mentioned above, and means that within that function, anything below that line will run in the inside-out pass. See [the `mcpyrate` manual](https://github.com/Technologicat/mcpyrate/blob/master/doc/main.md#expand-macros-inside-out).


### Emacs syntax highlighting

This Elisp snippet can be used to add syntax highlighting for keywords specific to `mcpyrate` and `unpythonic.syntax` to your Emacs setup:

```elisp
  (defun my/unpythonic-syntax-highlight-setup ()
    "Set up additional syntax highlighting for `unpythonic.syntax' and `mcpyrate` in Python mode."
    ;; adapted from code in dash.el
    (let ((new-keywords '("test" "test_raises" "test_signals" "fail" "the"
                          "error" "warn"  ; both testing macros and condition signaling protocols
                          "signal" "cerror" "handlers" "restarts" ; not macros, but in a role similar to exception handling constructs in the conditions/restarts system.
                          "let" "dlet" "blet"
                          "letseq" "dletseq" "bletseq"
                          "letrec" "dletrec" "bletrec"
                          "let_syntax" "abbrev"
                          "where"
                          "do" "local" "delete"
                          "continuations" "call_cc"
                          "autocurry" "lazify" "envify" "tco" "prefix" "autoreturn" "forall"
                          "multilambda" "namedlambda" "quicklambda"
                          "cond" "aif" "autoref" "dbg" "nb"
                          "macros" "dialects" "q" "u" "n" "a" "s" "t" "h")) ; mcpyrate
          (special-variables '("it"
                               "dyn")))
      (font-lock-add-keywords 'python-mode `((,(concat "\\_<" (regexp-opt special-variables 'paren) "\\_>")
                                              1 font-lock-variable-name-face)) 'append)
      ;; "(\\s-*" maybe somewhere?
      (font-lock-add-keywords 'python-mode `((,(concat "\\_<" (regexp-opt new-keywords 'paren) "\\_>")
                                              1 font-lock-keyword-face)) 'append)
  ))
  (add-hook 'python-mode-hook 'my/unpythonic-syntax-highlight-setup)
```

*Known issue*: For some reason, during a given session, this takes effect only starting with the second Python file opened. The first Python file opened during a session shows with the default Python syntax highlighting. Probably something to do with the initialization order of font-lock and whichever `python-mode` is being used.

Tested with `anaconda-mode`.

#### How to use (for Emacs beginners)

If you use the [Spacemacs](http://spacemacs.org/) kit, the right place to insert the snippet is into the function `dotspacemacs/user-config`. Here's [my spacemacs.d](https://github.com/Technologicat/spacemacs.d/) for reference; the snippet is in `prettify-symbols-config.el`, and it's invoked from `dotspacemacs/user-config` in `init.el`.

In a basic Emacs setup, the snippet goes into the `~/.emacs` startup file, or if you have an `.emacs.d/` directory, then into `~/.emacs.d/init.el`.

### This is semantics, not syntax!

[Strictly speaking](https://stackoverflow.com/questions/17930267/what-is-the-difference-between-syntax-and-semantics-of-programming-languages), `True`. We just repurpose Python's existing syntax to give it new meanings. However, in [the Racket reference](https://docs.racket-lang.org/reference/), **a** *syntax* designates a macro, in contrast to a *procedure* (regular function). We provide syntaxes in this particular sense. The name `unpythonic.syntax` is also shorter to type than `unpythonic.semantics`, less obscure, and close enough to convey the intended meaning.

If you want custom *syntax* proper, or want to package a set of block macros as a custom language that extends Python, then you may be interested in our sister project [`mcpyrate`](https://github.com/Technologicat/mcpyrate).
