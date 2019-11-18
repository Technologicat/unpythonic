# Unpythonic: Python meets Lisp and Haskell

In the spirit of [toolz](https://github.com/pytoolz/toolz), we provide missing features for Python, mainly from the list processing tradition, but with some Haskellisms mixed in. We extend the language with a set of [syntactic macros](https://en.wikipedia.org/wiki/Macro_(computer_science)#Syntactic_macros). We emphasize **clear, pythonic syntax**, and **making features work together**.

The features are built out of, in increasing order of [magic](https://macropy3.readthedocs.io/en/latest/discussion.html#levels-of-magic):

 - Pure Python (e.g. batteries for `itertools`),
 - Macros driving a pure-Python core (e.g. `do`, `let`),
 - Pure macros (e.g. `continuations`, `lazify`, `dbg`).

This depends on the purpose of each feature, as well as ease-of-use considerations. See our [design notes](doc/design-notes.md) for more information.

### Dependencies

None required.  
[MacroPy](https://github.com/azazel75/macropy) optional, to enable the syntactic macro layer.

### Documentation

[Pure-Python feature set](doc/features.md)  
[Syntactic macro feature set](macro_extras/README.md)  
[Design notes](doc/design-notes.md): for more insight into the design choices of ``unpythonic``.


### Examples

Small, limited-space overview of the overall flavor. There's a lot more that doesn't fit here, especially in the pure-Python feature set. See the [full documentation](doc/features.md) and [unit tests](unpythonic/test/) for more.

Click each example to expand.

#### Unpythonic in 30 seconds: Pure Python

<details><summary>Scan, fold and unfold like a boss.</summary>

[[docs](doc/features.md#batteries-for-itertools)]

```python
from operator import add
from unpythonic import scanl, foldl, unfold, take

assert tuple(scanl(add, 0, range(1, 5))) == (0, 1, 3, 6, 10)

def op(e1, e2, acc):
    return acc + e1 * e2
assert foldl(op, 0, (1, 2), (3, 4)) == 11  # we accept multiple input sequences, like Racket

def nextfibo(a, b):       # *oldstates
    return (a, b, a + b)  # value, *newstates
assert tuple(take(10, unfold(nextfibo, 1, 1))) == (1, 1, 2, 3, 5, 8, 13, 21, 34, 55)
```
</details>  
<details><summary>Allow a lambda to call itself.</summary>

[[docs](doc/features.md#batteries-for-functools)]

```python
from unpythonic import withself

fact = withself(lambda self, n: n * self(n - 1) if n > 1 else 1)
assert fact(5) == 120
```
</details>  
<details><summary>Break infinite recursion cycles.</summary>

[[docs](doc/features.md#fix-break-infinite-recursion-cycles)]

```python
from typing import NoReturn
from unpythonic import fix

@fix()
def a(k):
    return b((k + 1) % 3)
@fix()
def b(k):
    return a((k + 1) % 3)
assert a(0) is NoReturn
```
</details>  
<details><summary>Build number sequences by example. Slice general iterables.</summary>

[[docs for `s`](doc/features.md#s-m-mg-lazy-mathematical-sequences-with-infix-arithmetic)] [[docs for `islice`](doc/features.md#islice-slice-syntax-support-for-itertoolsislice)]

```python
from unpythonic import s, islice

seq = s(1, 2, 4, ...)
assert tuple(islice(seq)[:10]) == (1, 2, 4, 8, 16, 32, 64, 128, 256, 512)
```
</details>  
<details><summary>Memoize functions and generators.</summary>

[[docs for `memoize`](doc/features.md#batteries-for-functools)] [[docs for `gmemoize`](doc/features.md#gmemoize-imemoize-fimemoize-memoize-generators)]

```python
from itertools import count, takewhile
from unpythonic import memoize, gmemoize, islice

# "memoize lambda": classic evaluate-at-most-once thunk
thunk = memoize(lambda: print("hi from thunk"))
thunk()
thunk()

@gmemoize  # <-- important part
def primes():  # FP sieve of Eratosthenes
    yield 2
    for n in count(start=3, step=2):
        if not any(n % p == 0 for p in takewhile(lambda x: x*x <= n, primes())):
            yield n

assert tuple(islice(primes())[:10]) == (2, 3, 5, 7, 11, 13, 17, 19, 23, 29)
```
</details>  
<details><summary>Make functional updates.</summary>

[[docs](doc/features.md#fup-functional-update-shadowedsequence)]

```python
from itertools import repeat
from unpythonic import fup

t = (1, 2, 3, 4, 5)
s = fup(t)[0::2] << tuple(repeat(10, 3))
assert s == (10, 2, 10, 4, 10)
assert t == (1, 2, 3, 4, 5)
```
</details>  
<details><summary>View list slices writably, re-slicably.</summary>

[[docs](doc/features.md#view-writable-sliceable-view-into-a-sequence)]

```python
from unpythonic import view

lst = list(range(10))
v = view(lst)[::2]  # [0, 2, 4, 6, 8]
v[2:4] = (10, 20)
assert lst == [0, 1, 2, 3, 10, 5, 20, 7, 8, 9]

lst[2] = 42
assert v == [0, 42, 10, 20, 8]
```
</details>  
<details><summary>Focus on data flow in function composition.</summary>

[[docs](doc/features.md#pipe-piped-lazy_piped-sequence-functions)]

```python
from unpythonic import piped, getvalue

double = lambda x: 2 * x
inc    = lambda x: x + 1
x = piped(42) | double | inc | getvalue
assert x == 85
```
</details>


#### Unpythonic in 30 seconds: Language extensions with macros

<details><summary>Introduce expression-local variables.</summary>

[[docs](macro_extras/README.md#let-letseq-letrec-as-macros)]

```python
from unpythonic.syntax import macros, let

x = let[((a, 1), (b, 2)) in a + b]
```
</details>  
<details><summary>Introduce definition-local variables.</summary>

[[docs](macro_extras/README.md#dlet-dletseq-dletrec-blet-bletseq-bletrec-decorator-versions)]

```python
from unpythonic.syntax import macros, dlet

@dlet((x, 0))  # let-over-lambda for Python
def count():
    return x << x + 1  # `name << value` rebinds in the let env
assert count() == 1
assert count() == 2
```
</details>  
<details><summary>Code imperatively in an expression.</summary>

[[docs](macro_extras/README.md#do-as-a-macro-stuff-imperative-code-into-an-expression-with-style)]

```python
from unpythonic.syntax import macros, do, local, delete

x = do[local[a << 21],
       local[b << 2 * a],
       print(b),
       delete[b],  # do[] local variables can be deleted, too
       4 * a]
assert x == 84
```
</details>  
<details><summary>Apply tail call optimization (TCO) automatically.</summary>

[[docs](macro_extras/README.md#tco-automatic-tail-call-optimization-for-python)]

```python
from unpythonic.syntax import macros, tco

with tco:
    # expressions are automatically analyzed to detect tail position, too.
    evenp = lambda x: (x == 0) or oddp(x - 1)
    oddp  = lambda x: (x != 0) and evenp(x - 1)
    assert evenp(10000) is True
```
</details>  
<details><summary>Curry automatically, à la Haskell.</summary>

[[docs](macro_extras/README.md#curry-automatic-currying-for-python)]

```python
from unpythonic.syntax import macros, curry
from unpythonic import foldr, composerc as compose, cons, nil, ll

with curry:
    def add3(a, b, c):
        return a + b + c
    assert add3(1)(2)(3) == 6

    mymap = lambda f: foldr(compose(cons, f), nil)
    double = lambda x: 2 * x
    assert mymap(double, (1, 2, 3)) == ll(2, 4, 6)
```
</details>  
<details><summary>Make lazy functions, a.k.a. call-by-need.</summary>

[[docs](macro_extras/README.md#lazify-call-by-need-for-python)]

```python
from unpythonic.syntax import macros, lazify

with lazify:
    def my_if(p, a, b):
        if p:
            return a  # b never evaluated in this code path
        else:
            return b  # a never evaluated in this code path
    assert my_if(True, 23, 1/0) == 23
    assert my_if(False, 1/0, 42) == 42
```
</details>  
<details><summary>Capture and use continuations (call/cc).</summary>

[[docs](macro_extras/README.md#continuations-callcc-for-python)]

```python
from unpythonic.syntax import macros, continuations, call_cc

with continuations:  # automatically enables also TCO
    # McCarthy's amb() operator
    stack = []
    def amb(lst, cc):
        if not lst:
            return fail()
        first, *rest = tuple(lst)
        if rest:
            remaining_part_of_computation = cc
            stack.append(lambda: amb(rest, cc=remaining_part_of_computation))
        return first
    def fail():
        if stack:
            f = stack.pop()
            return f()

    # Pythagorean triples using amb()
    def pt():
        z = call_cc[amb(range(1, 21))]  # capture continuation, auto-populate cc arg
        y = call_cc[amb(range(1, z+1)))]
        x = call_cc[amb(range(1, y+1))]
        if x*x + y*y != z*z:
            return fail()
        return x, y, z
    t = pt()
    while t:
        print(t)
        t = fail()  # note pt() has already returned when we call this.
```
</details>


## Installation

**PyPI**

``pip3 install unpythonic --user``

or

``sudo pip3 install unpythonic``

**GitHub**

Clone (or pull) from GitHub. Then,

``python3 setup.py install --user``

or

``sudo python3 setup.py install``

**Uninstall**

Uninstallation must be invoked in a folder which has no subfolder called ``unpythonic``, so that ``pip`` recognizes it as a package name (instead of a filename). Then,

``pip3 uninstall unpythonic``

or

``sudo pip3 uninstall unpythonic``

## License

All original code is released under the 2-clause [BSD license](LICENSE.md).

For sources and licenses of fragments originally seen on the internet, see [AUTHORS](AUTHORS.md).


## Acknowledgements

Thanks to [TUT](http://www.tut.fi/en/home) for letting me teach [RAK-19006 in spring term 2018](https://github.com/Technologicat/python-3-scicomp-intro); early versions of parts of this library were originally developed as teaching examples for that course. Thanks to @AgenttiX for feedback.

The trampoline implementation of ``unpythonic.tco`` takes its remarkably clean and simple approach from ``recur.tco`` in [fn.py](https://github.com/fnpy/fn.py). Our main improvements are a cleaner syntax for the client code, and the addition of the FP looping constructs.

Another important source of inspiration was [tco](https://github.com/baruchel/tco) by Thomas Baruchel, for thinking about the possibilities of TCO in Python.

## Python-related FP resources

Python clearly wants to be an impure-FP language. A decorator with arguments *is a curried closure* - how much more FP can you get?

- [Awesome Functional Python](https://github.com/sfermigier/awesome-functional-python), especially a list of useful libraries. Some picks:

  - [fn.py: Missing functional features of fp in Python](https://github.com/fnpy/fn.py) (actively maintained fork). Includes e.g. tail call elimination by trampolining, and a very compact way to recursively define infinite streams.

  - [more-itertools: More routines for operating on iterables, beyond itertools.](https://github.com/erikrose/more-itertools)

  - [boltons: Like builtins, but boltons.](https://github.com/mahmoud/boltons) Includes yet more itertools, and much more.

  - [toolz: A functional standard library for Python](https://github.com/pytoolz/toolz)

  - [funcy: A fancy and practical functional tools](https://github.com/suor/funcy/)

  - [pyrsistent: Persistent/Immutable/Functional data structures for Python](https://github.com/tobgu/pyrsistent)

  - [pampy: Pattern matching for Python](https://github.com/santinic/pampy) (pure Python, no AST transforms!)

- [List of languages that compile to Python](https://github.com/vindarel/languages-that-compile-to-python) including Hy, a Lisp (in the [Lisp-2](https://en.wikipedia.org/wiki/Lisp-1_vs._Lisp-2) family) that can use Python libraries.

Old, but interesting:

- [Peter Norvig (2000): Python for Lisp Programmers](http://www.norvig.com/python-lisp.html)

- [David Mertz (2001): Charming Python - Functional programming in Python, part 2](https://www.ibm.com/developerworks/library/l-prog2/index.html)
