# Unpythonic: Python meets Lisp and Haskell

In the spirit of [toolz](https://github.com/pytoolz/toolz), we provide missing features for Python, mainly from the list processing tradition, but with some Haskellisms mixed in. We extend the language with a set of [syntactic macros](https://en.wikipedia.org/wiki/Macro_(computer_science)#Syntactic_macros). We also provide an in-process, background [REPL](https://en.wikipedia.org/wiki/Read%E2%80%93eval%E2%80%93print_loop) server for live inspection and hot-patching. The emphasis is on **clear, pythonic syntax**, **making features work together**, and **obsessive correctness**.

![100% Python](https://img.shields.io/github/languages/top/Technologicat/unpythonic) ![supported language versions](https://img.shields.io/pypi/pyversions/unpythonic) ![supported implementations](https://img.shields.io/pypi/implementation/unpythonic) ![CI status](https://img.shields.io/github/workflow/status/Technologicat/unpythonic/Python%20package) [![codecov](https://codecov.io/gh/Technologicat/unpythonic/branch/master/graph/badge.svg)](https://codecov.io/gh/Technologicat/unpythonic)  
![version on PyPI](https://img.shields.io/pypi/v/unpythonic) ![PyPI package format](https://img.shields.io/pypi/format/unpythonic) ![dependency status](https://img.shields.io/librariesio/github/Technologicat/unpythonic)  
![license: BSD](https://img.shields.io/pypi/l/unpythonic) ![open issues](https://img.shields.io/github/issues/Technologicat/unpythonic) [![contributions welcome](https://img.shields.io/badge/contributions-welcome-brightgreen.svg?style=flat)](HACKING.md)

*Some hypertext features of this README, such as local links to detailed documentation, and expandable example highlights, are not supported when viewed on PyPI; [view on GitHub](https://github.com/Technologicat/unpythonic) to have those work properly.*


### Dependencies

None required.

 - [MacroPy](https://github.com/azazel75/macropy) optional, to enable the syntactic macro layer.
 - [imacropy](https://github.com/Technologicat/imacropy) optional, to enable the improved interactive macro REPL.

The officially supported language version is **Python 3.6**, on both CPython and PyPy3.

The 0.14.x series should run on CPythons 3.4 through 3.7, and on PyPy3; the [CI](https://en.wikipedia.org/wiki/Continuous_integration) process verifies the tests pass on those platforms. Support for 3.8 is planned in one of the next few releases. Pure-Python features should already work; but macro code still needs changes to account for AST representation changes in 3.8, see issue [#16](https://github.com/Technologicat/unpythonic/issues/16).

### Documentation

[Pure-Python feature set](doc/features.md)  
[Syntactic macro feature set](doc/macros.md)  
[REPL server](doc/repl.md): interactively hot-patch your running Python program.  
[Design notes](doc/design-notes.md): for more insight into the design choices of ``unpythonic``.

The features of `unpythonic` are built out of, in increasing order of [magic](https://macropy3.readthedocs.io/en/latest/discussion.html#levels-of-magic):

 - Pure Python (e.g. batteries for `itertools`),
 - Macros driving a pure-Python core (`do`, `let`),
 - Pure macros (e.g. `continuations`, `lazify`, `dbg`).

This depends on the purpose of each feature, as well as ease-of-use considerations. See the design notes for more information.


### Examples

Small, limited-space overview of the overall flavor. There's a lot more that doesn't fit here, especially in the pure-Python feature set. See the [full documentation](doc/features.md) and [unit tests](unpythonic/test/) for more examples.

#### Unpythonic in 30 seconds: Pure Python

<details><summary>Loop functionally, with tail call optimization.</summary>

[[docs](doc/features.md#looped-looped_over-loops-in-fp-style-with-tco)]

```python
from unpythonic import looped, looped_over

@looped
def result(loop, acc=0, i=0):
    if i == 10:
        return acc
    else:
        return loop(acc + i, i + 1)  # tail call optimized, no call stack blowup.
assert result == 45

@looped_over(range(3), acc=[])
def result(loop, i, acc):
    acc.append(lambda x: i * x)  # fresh "i" each time, no mutation of loop counter.
    return loop()
assert [f(10) for f in result] == [0, 10, 20]
```
</details>  
<details><summary>Introduce dynamic variables.</summary>

[[docs](doc/features.md#dyn-dynamic-assignment)]

```python
from unpythonic import dyn, make_dynvar

make_dynvar(x=42)  # set a default value

def f():
    assert dyn.x == 17
    with dyn.let(x=23):
        assert dyn.x == 23
        g()
    assert dyn.x == 17

def g():
    assert dyn.x == 23

assert dyn.x == 42
with dyn.let(x=17):
    assert dyn.x == 17
    f()
assert dyn.x == 42
```
</details>  
<details><summary>Interactively hot-patch your running Python program.</summary>

[[docs](doc/repl.md)]

To opt in, add just two lines of code to your main program:

```python
from unpythonic.net import server
server.start(locals={})  # automatically daemonic

import time

def main():
    while True:
        time.sleep(1)

if __name__ == '__main__':
    main()
```

Or if you just want to take this for a test run, start the built-in demo app:

```bash
python3 -m unpythonic.net.server
```

Once a server is running, to connect:

```bash
python3 -m unpythonic.net.client 127.0.0.1
```

This gives you a REPL, inside your live process, with all the power of Python. You can `importlib.reload` any module, and through `sys.modules`, inspect or overwrite any name at the top level of any module. You can `pickle.dump` your data. Or do anything you want with/to the live state of your app.

You can have multiple REPL sessions connected simultaneously. When your app exits (for any reason), the server automatically shuts down, closing all connections if any remain. But exiting the client leaves the server running, so you can connect again later - that's the whole point.

Optionally, if you have MacroPy, the REPL sessions support importing and invoking macros. If you additionally have [imacropy](https://github.com/Technologicat/imacropy), the improved interactive macro REPL is used automatically.
</details>  
<details><summary>Industrial-strength scan and fold.</summary>

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
<details><summary>Allow a lambda to call itself. Name a lambda.</summary>

[[docs for `withself`](doc/features.md#batteries-for-functools)] [[docs for `namelambda`](doc/features.md#namelambda-rename-a-function)]

```python
from unpythonic import withself, namelambda

fact = withself(lambda self, n: n * self(n - 1) if n > 1 else 1)  # see @trampolined to do this with TCO
assert fact(5) == 120

square = namelambda("square")(lambda x: x**2)
assert square.__name__ == "square"
assert square.__qualname__ == "square"  # or e.g. "somefunc.<locals>.square" if inside a function
assert square.__code__.co_name == "square"  # used by stack traces
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

# "memoize lambda": classic evaluate-at-most-once thunk
thunk = memoize(lambda: print("hi from thunk"))
thunk()  # the message is printed only the first time
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
<details><summary>Functional updates.</summary>

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
<details><summary>Lispy data structures.</summary>

[[docs for `box`](doc/features.md#box-a-mutable-single-item-container)] [[docs for `cons`](doc/features.md#cons-and-friends-pythonic-lispy-linked-lists)] [[docs for `frozendict`](doc/features.md#frozendict-an-immutable-dictionary)]

```python
from unpythonic import box, unbox  # mutable single-item container
cat = object()
cardboardbox = box(cat)
assert cardboardbox is not cat  # the box is not the cat
assert unbox(cardboardbox) is cat  # but the cat is inside the box
assert cat in cardboardbox  # ...also syntactically
dog = object()
cardboardbox << dog  # hey, it's my box! (replace contents)
assert unbox(cardboardbox) is dog

from unpythonic import cons, nil, ll, llist  # lispy linked lists
lst = cons(1, cons(2, cons(3, nil)))
assert ll(1, 2, 3) == lst  # make linked list out of elements
assert llist([1, 2, 3]) == lst  # convert iterable to linked list

from unpythonic import frozendict  # immutable dictionary
d1 = frozendict({'a': 1, 'b': 2})
d2 = frozendict(d1, c=3, a=4)
assert d1 == frozendict({'a': 1, 'b': 2})
assert d2 == frozendict({'a': 4, 'b': 2, 'c': 3})
```
</details>  
<details><summary>Live list slices.</summary>

[[docs](doc/features.md#view-writable-sliceable-view-into-a-sequence)]

```python
from unpythonic import view

lst = list(range(10))
v = view(lst)[::2]  # [0, 2, 4, 6, 8]
v[2:4] = (10, 20)  # re-slicable, still live.
assert lst == [0, 1, 2, 3, 10, 5, 20, 7, 8, 9]

lst[2] = 42
assert v == [0, 42, 10, 20, 8]
```
</details>  
<details><summary>Pipes: focus on data flow in function composition.</summary>

[[docs](doc/features.md#pipe-piped-lazy_piped-sequence-functions)]

```python
from unpythonic import piped, exitpipe

double = lambda x: 2 * x
inc    = lambda x: x + 1
x = piped(42) | double | inc | exitpipe
assert x == 85
```
</details>  
<details><summary>Conditions: resumable, modular error handling, like in Common Lisp.</summary>

[[docs](doc/features.md#handlers-restarts-conditions-and-restarts)]

Contrived example:

```python
from unpythonic import error, restarts, handlers, invoke, use_value, unbox

class MyError(ValueError):
    def __init__(self, value):  # We want to act on the value, so save it.
        self.value = value

def lowlevel(lst):
    _drop = object()  # gensym/nonce
    out = []
    for k in lst:
        # Provide several different error recovery strategies.
        with restarts(use_value=(lambda x: x),
                      halve=(lambda x: x // 2),
                      drop=(lambda: _drop)) as result:
            if k > 9000:
                error(MyError(k))
            # This is reached when no error occurs.
            # `result` is a box, send k into it.
            result << k
        # Now the result box contains either k,
        # or the return value of one of the restarts. 
        r = unbox(result)  # get the value from the box
        if r is not _drop:
            out.append(r)
    return out

def highlevel():
    # Choose which error recovery strategy to use...
    with handlers((MyError, lambda c: use_value(c.value))):
        assert lowlevel([17, 10000, 23, 42]) == [17, 10000, 23, 42]

    # ...on a per-use-site basis...
    with handlers((MyError, lambda c: invoke("halve", c.value))):
        assert lowlevel([17, 10000, 23, 42]) == [17, 5000, 23, 42]

    # ...without changing the low-level code.
    with handlers((MyError, lambda: invoke("drop"))):
        assert lowlevel([17, 10000, 23, 42]) == [17, 23, 42]

highlevel()
```

Conditions only shine in larger systems, with restarts set up at multiple levels of the call stack; this example is too small to demonstrate that. The single-level case here could be implemented as a error-handling mode parameter for the example's only low-level function.

With multiple levels, it becomes apparent that this mode parameter must be threaded through the API at each level, unless it is stored as a dynamic variable (see [`unpythonic.dyn`](doc/features.md#dyn-dynamic-assignment)). But then, there can be several types of errors, and the error-handling mode parameters - one for each error type - have to be shepherded in an intricate manner. A stack is needed, so that an inner level may temporarily override the handler for a particular error type...

The condition system is the clean, general solution to this problem. It automatically scopes handlers to their dynamic extent, and manages the handler stack automatically. In other words, it dynamically binds error-handling modes (for several types of errors, if desired) in a controlled, easily understood manner. The local programmability (i.e. the fact that a handler is not just a restart name, but an arbitrary function) is a bonus for additional flexibility.

If this sounds a lot like an exception system, that's because conditions are the supercharged sister of exceptions. The condition model cleanly separates mechanism from policy, while otherwise remaining similar to the exception model.
</details>


#### Unpythonic in 30 seconds: Language extensions with macros

<details><summary>unpythonic.test.fixtures: a minimalistic test framework for macro-enabled Python code.</summary>

*[docs TODO]*; for now, look at the docstrings of the various constructs in the example below, the module `unpythonic.test.fixtures` (which provides much of this), and the automated tests of `unpythonic` itself. (Particularly, how to test code using conditions and restarts can be found in `unpythonic.test.test_conditions`.)

```python
from unpythonic.syntax import macros, test, test_raises, fail, error
from unpythonic.test.fixtures import session, testset, terminate, returns_normally

def f():
    raise RuntimeError("argh!")

def g(a, b):
    return a * b
    fail["this line should be unreachable"]

with session("simple framework demo"):
    with testset():
        test[2 + 2 == 4]
        test_raises[RuntimeError, f()]
        test[returns_normally(g(2, 3))]
        test[g(2, 3) == 6]

    with testset("outer"):
        with testset("inner 1"):
            test[g(6, 7) == 42]
        with testset("inner 2"):
            test[None is None]
        with testset("inner 3"):  # an empty testset is considered 100% passed.
            pass

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

We provide the low-level syntactic constructs `test[]`, `test_raises[]` and `test_signals[]`, with the usual meanings. The last one is for testing code that uses conditions and restarts; see `unpythonic.conditions`.

The test macros also come in block variants, `with test`, `with test_raises`, `with test_signals`.

We provide the helper macros `fail[message]` and `error[message]` for producing unconditional failures or errors. These can be useful e.g. if a test reached a line that should be unreachable, or when an optional dependency for an integration test is not installed.

As usual in test frameworks, the testing constructs behave somewhat like `assert`, with the difference that a failure or error will not abort the whole unit (unless explicitly asked to do so).

The `with session()` is optional. The human-readable session name is also optional, used for display purposes only. The session serves two roles: it provides an exit point for `terminate`, and defines an implicit top-level `testset`.

Tests can optionally be grouped into testsets. Each `testset` tallies passed, failed and errored tests within it, and displays the totals when it exits. Testsets can be named and nested.

Testsets also provide the option to locally install a `postproc` handler that gets a copy of each failure or error in that testset (and by default, any of its inner testsets), after the failure or error has been printed. In nested testsets, the dynamically innermost `postproc` wins. A failure is an instance of `unpythonic.test.fixtures.TestFailure`, and an error is an instance of `unpythonic.test.fixtures.TestError`. Both inherit from `unpythonic.test.fixtures.TestingException`.

If you want to set a default global `postproc`, which is used when no local `postproc` is in effect, see the `TestConfig` bunch of constants in `unpythonic.test.fixtures`. It also contains some other configuration options.

The `with testset` construct comes with one other important feature. The nearest dynamically enclosing `with testset` catches any stray exceptions or signals that occur within its dynamic extent, but outside a test. In case of an uncaught signal, the error is reported, and the testset resumes. In case of an uncaught exception, the error is reported, and the testset terminates (because the exception model does not support resuming).

Catching of uncaught *signals*, in both the low-level `test` constructs and the high-level `testset`, can be disabled using `with catch_signals(False)`. This is useful in testing code that uses conditions and restarts; sometimes allowing a signal (e.g. from `unpythonic.conditions.warn`) to remain uncaught is the right thing to do.

We provide a custom testing framework, because `unpythonic` is effectively a language extension. Inspired by [Julia](https://julialang.org/)'s standard-library [`Test` package](https://docs.julialang.org/en/v1/stdlib/Test/).
</details>  

<details><summary>let: expression-local variables.</summary>

[[docs](doc/macros.md#let-letseq-letrec-as-macros)]

```python
from unpythonic.syntax import macros, let, letseq, letrec

x = let[((a, 1), (b, 2)) in a + b]
y = letseq[((c, 1),  # LET SEQuential, like Scheme's let*
            (c, 2 * c),
            (c, 2 * c)) in
           c]
z = letrec[((evenp, lambda x: (x == 0) or oddp(x - 1)),  # LET mutually RECursive, like in Scheme
            (oddp,  lambda x: (x != 0) and evenp(x - 1)))
           in evenp(42)]
```
</details>  
<details><summary>let-over-lambda: stateful functions.</summary>

[[docs](doc/macros.md#dlet-dletseq-dletrec-blet-bletseq-bletrec-decorator-versions)]

```python
from unpythonic.syntax import macros, dlet

@dlet((x, 0))  # let-over-lambda for Python
def count():
    return x << x + 1  # `name << value` rebinds in the let env
assert count() == 1
assert count() == 2
```
</details>  
<details><summary>do: code imperatively in any expression position.</summary>

[[docs](doc/macros.md#do-as-a-macro-stuff-imperative-code-into-an-expression-with-style)]

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
<details><summary>Automatically apply tail call optimization (TCO), à la Scheme/Racket.</summary>

[[docs](doc/macros.md#tco-automatic-tail-call-optimization-for-python)]

```python
from unpythonic.syntax import macros, tco

with tco:
    # expressions are automatically analyzed to detect tail position.
    evenp = lambda x: (x == 0) or oddp(x - 1)
    oddp  = lambda x: (x != 0) and evenp(x - 1)
    assert evenp(10000) is True
```
</details>  
<details><summary>Curry automatically, à la Haskell.</summary>

[[docs](doc/macros.md#curry-automatic-currying-for-python)]

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
<details><summary>Lazy functions, a.k.a. call-by-need.</summary>

[[docs](doc/macros.md#lazify-call-by-need-for-python)]

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
<details><summary>Genuine multi-shot continuations (call/cc).</summary>

[[docs](doc/macros.md#continuations-callcc-for-python)]

```python
from unpythonic.syntax import macros, continuations, call_cc

with continuations:  # enables also TCO automatically
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
        y = call_cc[amb(range(1, z+1))]
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


## Support

Not working as advertised? Missing a feature? Documentation needs improvement?

**[Issue reports](https://github.com/Technologicat/unpythonic/issues) and [pull requests](https://github.com/Technologicat/unpythonic/pulls) are welcome.** [Contribution guidelines](HACKING.md).

While `unpythonic` is intended as a serious tool for improving productivity as well as for teaching, right now my work priorities mean that it's developed and maintained on whatever time I can spare for it. Thus getting a response may take a while, depending on which project I happen to be working on.


## License

All original code is released under the 2-clause [BSD license](LICENSE.md).

For sources and licenses of fragments originally seen on the internet, see [AUTHORS](AUTHORS.md).


## Acknowledgements

Thanks to [TUT](http://www.tut.fi/en/home) for letting me teach [RAK-19006 in spring term 2018](https://github.com/Technologicat/python-3-scicomp-intro); early versions of parts of this library were originally developed as teaching examples for that course. Thanks to @AgenttiX for feedback.

The trampoline implementation of ``unpythonic.tco`` takes its remarkably clean and simple approach from ``recur.tco`` in [fn.py](https://github.com/fnpy/fn.py). Our main improvements are a cleaner syntax for the client code, and the addition of the FP looping constructs.

Another important source of inspiration was [tco](https://github.com/baruchel/tco) by Thomas Baruchel, for thinking about the possibilities of TCO in Python.


## Relevant reading

Links to blog posts, online articles and papers on topics relevant in the context of `unpythonic` have been collected to [a separate document](doc/readings.md).
