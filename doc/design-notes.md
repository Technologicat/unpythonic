# Design Notes

- [Design Philosophy](#design-philosophy)
- [Macros do not Compose](#macros-do-not-compose)
- [Language Discontinuities](#language-discontinuities)
- [What Belongs in Python?](#what-belongs-in-python)
- [Killer features of Common Lisp](#killer-features-of-common-lisp)
- [Common Lisp, Python, and productivity](#common-lisp-python-and-productivity)
- [Python is not a Lisp](#python-is-not-a-lisp)
- [On ``let`` and Python](#on-let-and-python)
- [Assignment Syntax](#assignment-syntax)
- [TCO Syntax and Speed](#tco-syntax-and-speed)
- [No Monads?](#no-monads)
- [No Types?](#no-types)
- [Detailed Notes on Macros](#detailed-notes-on-macros)
- [Miscellaneous notes](#miscellaneous-notes)

## Design Philosophy

The main design considerations of `unpythonic` are simplicity, robustness, and minimal dependencies. Some complexity is tolerated, if it is essential to make features interact better, or to provide a better user experience.

The whole library is pure Python. No foreign extensions are required. We also try to avoid depending on anything beyond "the Python standard", to help `unpythonic` run on any conforming Python implementation. (Provided its AST representation is sufficiently similar to CPython's, to allow the macros to work.)

As of this writing (0.14.2), we test on CPython 3.6, and consider it as the primary target platform. However, if anything fails to work on another 3.6-compliant Python 3 such as [PyPy3](https://doc.pypy.org/en/latest/index.html) ([version 2.3.1 or later](http://pypy.org/compat.html)), issue reports and pull requests are welcome.

The library is split into **two layers**, providing **three kinds of features**:

 - Pure Python (e.g. batteries for `itertools`),
 - Macros driving a pure-Python core (e.g. `do`, `let`),
 - Pure macros (e.g. `continuations`, `lazify`, `dbg`).

We believe syntactic macros are [*the nuclear option of software engineering*](https://www.factual.com/blog/thinking-in-clojure-for-java-programmers-part-2/). Accordingly, we aim to [minimize macro magic](https://macropy3.readthedocs.io/en/latest/discussion.html#minimize-macro-magic). If a feature can be implemented - *with a level of usability on par with pythonic standards* - without resorting to macros, then it belongs in the pure-Python layer. (The one exception is when building the feature as a macro is the *simpler* solution. Consider `unpythonic.amb.forall` (overly complicated, to avoid macros) vs. `unpythonic.syntax.forall` (a clean macro-based design of the same feature) as an example. Keep in mind [ZoP](https://www.python.org/dev/peps/pep-0020/) §17 and §18.)

When that is not possible, we implement the actual feature as a pure-Python core, not meant for direct use, and provide a macro layer on top. The purpose of the macro layer is then to improve usability, by eliminating the [accidental complexity](https://en.wikipedia.org/wiki/No_Silver_Bullet) from the user interface of the pure-Python core. Examples are *automatic* currying, *automatic* tail-call optimization, and (beside a much leaner syntax) lexical scoping for the ``let`` and ``do`` constructs. We believe a well-designed macro layer can bring a difference in user experience similar to that between programming in [Brainfuck](https://en.wikipedia.org/wiki/Brainfuck) (or to be fair, in Fortran or in Java) versus in Python.

Finally, when the whole purpose of the feature is to automatically transform a piece of code into a particular style (`continuations`, `lazify`, `autoreturn`), or when run-time access to the original [AST](https://en.wikipedia.org/wiki/Abstract_syntax_tree) is essential to the purpose (`dbg`), then the feature belongs squarely in the macro layer, with no pure-Python core underneath.

When to implement your own feature as a syntactic macro, see the discussion in Chapter 8 of [Paul Graham: On Lisp](http://paulgraham.com/onlisp.html). MacroPy's documentation also provides [some advice on the topic](https://macropy3.readthedocs.io/en/latest/discussion.html).

### Macros do not Compose

Making macros work together is nontrivial, essentially because *macros don't compose*. [As pointed out by John Shutt](https://fexpr.blogspot.com/2013/12/abstractive-power.html), in a multilayered language extension implemented with macros, the second layer of macros needs to understand all of the first layer. The issue is that the macro abstraction leaks the details of its expansion. Contrast with functions, which operate on values: the process that was used to arrive at a value doesn't matter. It's always possible for a function to take this value and transform it into another value, which can then be used as input for the next layer of functions. That's composability at its finest.

The need for interaction between macros may arise already in what *feels* like a single layer of abstraction; for example, it's not only that the block macros must understand ``let[]``, but some of them must understand other block macros. This is because what feels like one layer of abstraction is actually implemented as a number of separate macros, which run in a specific order. Thus, from the viewpoint of actually applying the macros, if the resulting software is to work correctly, the mere act of allowing combos between the block macros already makes them into a multilayer system. The compartmentalization of conceptually separate features into separate macros facilitates understanding and maintainability, but fails to reach the ideal of modularity.

Therefore, any particular combination of macros that has not been specifically tested might not work. That said, if some particular combo doesn't work and *is not at least documented as such*, that's an error; please raise an issue. The unit tests should cover the combos that on the surface seem the most useful, but there's no guarantee that they cover everything that actually is useful somewhere.

Some aspects in the design of `unpythonic` could be simplified by expanding macros in an outside-in order (first pass in MacroPy; then e.g. no need to identify and parse an expanded `let` form), but that complicates other things (e.g. lexical scoping in `let` constructs), as well as cannot remove the fundamental requirement that the macros must still know about each other (e.g. parse an *unexpanded* `let` form instead).

The lack of composability is a problem mainly when using macros to create a language extension, because the features of the extended language often interact. Macros can also be used in a much more everyday way, where composability is mostly a non-issue - to abstract and name common patterns that just happen to be of a nature that cannot be extracted as a regular function. See [Peter Seibel: Practical Common Lisp, chapter 3](http://www.gigamonkeys.com/book/practical-a-simple-database.html) for an example.

### Language Discontinuities

The very act of extending a language creates points of discontinuity between the extended language and the original. This can become a particularly bad source of extra complexity, if the extension can be enabled locally for a piece of code - as is the case with block macros. Then the design of the extended language must consider how to treat interactions between pieces of code that use the extension and those that don't. Then exponentiate those design considerations by the number of extensions that can be enabled independently. This issue is simply absent when designing a new language from scratch.

For an example, look at what the rest of `unpythonic` has to do to make `lazify` behave as the user expects! Grep the codebase for `lazyutil`; especially the `passthrough_lazy_args` decorator, and its sister, the utility `maybe_force_args`. The decorator is essentially just an annotation for the `lazify` transformer, that marks a function as *not necessarily needing* evaluation of its arguments. Such functions often represent language-level constructs, such as `let` or `curry`, that essentially just *pass through* user data to other user-provided code, without *accessing* that data. The annotation is honored by the compiler when programming in the lazy (call-by-need) extended language, and otherwise it does nothing. Another pain point is the need of a second trampoline implementation (that only differs in one minor detail) just to make `lazify` interact correctly with TCO (while not losing an order of magnitude of performance in the trampoline used with standard Python).

For another example, it's likely that e.g. `continuations` still doesn't integrate completely seamlessly - and I'm not sure if that is possible even in principle. Calling a traditional function from a [CPS](https://en.wikipedia.org/wiki/Continuation-passing_style) function is no problem; the traditional function uses no continuations, and (barring exceptions) will always return normally. The other way around can be a problem. Also, having TCO implemented as a trampoline system on top of the base language (instead of being already provided under the hood, like in Scheme) makes the `continuations` transformer more complex than absolutely necessary.

For a third example, consider *decorated lambdas*. This is an `unpythonic` extension - essentially, a compiler feature implemented (by calling some common utility code) by each of the transformers of the pure-macro features - that understands a lambda enclosed in a nested sequence of single-argument function calls *as a decorated function definition*. This is painful, because the Python AST has no place to store the decorator list for a lambda; Python sees it just as a nested sequence of function calls, terminating in a lambda. This has to be papered over by the transformers. We also introduce a related complication, the decorator registry (see `regutil`), so that we can automatically sort decorator invocations - so that pure-macro features know at which index to inject a particular decorator (so it works properly) when they need to do that. Needing such a registry is already a complication, but the *decorated lambda* machinery feels the pain more acutely.

### What Belongs in Python?

If you feel [my hovercraft is full of eels](http://stupidpythonideas.blogspot.com/2015/05/spam-spam-spam-gouda-spam-and-tulips.html), it is because they come with the territory.

Some have expressed the opinion [the statement-vs-expression dichotomy is a feature](http://stupidpythonideas.blogspot.com/2015/01/statements-and-expressions.html). The BDFL himself has famously stated that TCO has no place in Python [[1]](http://neopythonic.blogspot.com/2009/04/tail-recursion-elimination.html) [[2]](http://neopythonic.blogspot.fi/2009/04/final-words-on-tail-calls.html), and less famously that multi-expression lambdas or continuations have no place in Python [[3]](https://www.artima.com/weblogs/viewpost.jsp?thread=147358). Several potentially interesting PEPs have been deferred [[1]](https://www.python.org/dev/peps/pep-3150/) [[2]](https://www.python.org/dev/peps/pep-0403/) or rejected [[3]](https://www.python.org/dev/peps/pep-0511/) [[4]](https://www.python.org/dev/peps/pep-0463/) [[5]](https://www.python.org/dev/peps/pep-0472/).

Of course, if I agreed, I wouldn't be doing this (or [pydialect](https://github.com/Technologicat/pydialect), or [imacropy](https://github.com/Technologicat/imacropy)).

On a point raised [here](https://www.artima.com/weblogs/viewpost.jsp?thread=147358) with respect to indentation-sensitive vs. indentation-insensitive parser modes, having seen [SRFI-110: Sweet-expressions (t-expressions)](https://srfi.schemers.org/srfi-110/srfi-110.html), I think Python is confusing matters by linking the mode to statements vs. expressions. A workable solution is to make *everything* support both modes (or even preprocess the source code text to use only one of the modes), which *uniformly* makes parentheses an alternative syntax for grouping.

It would be nice to be able to use indentation to structure expressions to improve their readability, like one can do in Racket with [sweet](https://docs.racket-lang.org/sweet/), but I suppose ``lambda x: [expr0, expr1, ...]`` will have to do for a multiple-expression lambda in MacroPy. Unless I decide at some point to make a source filter for [Pydialect](https://github.com/Technologicat/pydialect) to auto-convert between indentation and parentheses; but for Python this is somewhat difficult to do, because statements **must** use indentation whereas expressions **must** use parentheses, and this must be done before we can invoke the standard parser to produce an AST. (And I don't want to maintain a [Pyparsing](https://github.com/pyparsing/pyparsing) grammar to parse a modified version of Python.)

### Killer features of Common Lisp

In my opinion, Common Lisp has three legendary killer features:

 1. [Conditions and restarts](http://www.gigamonkeys.com/book/beyond-exception-handling-conditions-and-restarts.html), i.e. resumable exceptions,
 2. [Hot-patching](https://stackoverflow.com/questions/46499463/hot-debug-and-swap-in-common-lisp) (with Swank), and
 3. Compiling a high-level language into efficient machine code.

But for those of us that [don't like parentheses](https://srfi.schemers.org/srfi-110/srfi-110.html) or accumulated historical cruft (bad naming, API irregularities), and/or consider it essential to have the extensive third-party library ecosystem of a popular language such as Python, switching to CL is not a solution. Design of a completely new language aside, which of these features can be transplanted onto an existing language?

 1. We have [a form of conditions and restarts](features.md#handlers-restarts-conditions-and-restarts).
    - The experience is not seamless, because conditions and exceptions - Python's native error-handling paradigm - do not mix.
    - What we have may work, to a limited extent, for a project that chooses to consistently use conditions instead of exceptions throughout. But all third-party libraries and the standard library will still raise exceptions.
    - It would seem the error-handling model is something that must be chosen at the start when designing a language.

 2. We have [hot-patching](repl.md).
    - This can be made to have a native feel in any sufficiently dynamic language. Both CL and Python qualify.
    - In CL, connecting to a running Lisp app and monkey-patching it live is powered by *Swank*, the server component of [SLIME](https://en.wikipedia.org/wiki/SLIME). See [[0]](https://common-lisp.net/project/slime/doc/html/Connecting-to-a-remote-lisp.html), [[1]](https://stackoverflow.com/questions/31377098/interact-with-a-locally-long-running-common-lisp-image-possibly-daemonized-fro), [[2]](https://github.com/LispCookbook/cl-cookbook/issues/115) and [[3]](https://stackoverflow.com/questions/8874615/how-to-replace-a-running-function-in-common-lisp).
    - Our implementation (`unpythonic.net.server` and `unpythonic.net.client`) doesn't talk with SLIME, but this being Python, it doesn't need to. The important point (and indeed [the stuff of legends](http://www.flownet.com/gat/jpl-lisp.html)) is to run **some kind of** [REPL](https://en.wikipedia.org/wiki/Read%E2%80%93eval%E2%80%93print_loop) server in the background, so that the user may later connect to a running process to inspect and modify its state interactively. The exact tools and workflow may vary depending on the language, but having this feature **in some form** is, at least in my opinion, *obviously expected* of any serious dynamic language.
    - As for the original Swank in CL, see [server setup](https://common-lisp.net/project/slime/doc/html/Setting-up-the-lisp-image.html), [SLIME](https://cliki.net/SLIME-HOWTO) and [swank-client](https://github.com/brown/swank-client). Swank servers [for Python](https://github.com/fgallina/swank-python) and [for Racket](https://github.com/mbal/swank-racket) also exist.

 3. Generating efficient compiled code is not in CPython's design goals. Ouch!
    - Cython does it, but essentially requires keeping to a feature set easily compilable to C, not just some gradual type-tagging like in [typed/racket](https://docs.racket-lang.org/ts-guide/), Common Lisp or [Julia](https://docs.julialang.org/en/v1/manual/methods/), plus compiler hints like in Common Lisp.
    - But there's [PyPy](https://www.pypy.org/), which (as of March 2020) supports Python 3.6.9. It JIT-compiles arbitrary Python code into native machine code.
      - A quick test by running `python3 -m unpythonic.test.test_fploop` suggests that with `@unpythonic.looped`, for a do-nothing FP loop, PyPy3 is 6-7⨉ faster than CPython. Instead of a ~70⨉ slowdown compared to CPython's native `for` loop, in PyPy3 the overhead becomes only ~10⨉ (w.r.t. PyPy's native `for` loop). This is probably closer to the true overhead caused by the dynamic nature of Python, when the language is implemented with performance in mind.
      - PyPy speeds up Python-heavy sections of code (the simpler the better; this makes it more amenable for analysis by the JIT), but interfacing with C extensions tends to be slower in PyPy than in CPython, because this requires an emulation layer (`cpyext`) for the CPython C API. Some core assumptions of PyPy are different enough from CPython (e.g. no reference counting; objects may move around in memory) that emulating the CPython semantics makes this emulation layer rather complex.
      - Due to being a JIT, PyPy doesn't speed up small one-shot programs, or typical unit tests; the code should have repetitive sections (such as loops), and run for at least a few seconds for the JIT to warm up. This is pretty much [the MATLAB execution model](https://blogs.mathworks.com/loren/2016/02/12/run-code-faster-with-the-new-matlab-execution-engine/), for Python (whereas CL performs ahead-of-time compilation).
      - PyPy (the JIT-enabled Python interpreter) itself is not the full story; the [RPython](https://rpython.readthedocs.io/en/latest/) toolchain from the PyPy project can *automatically produce a JIT for an interpreter for any new dynamic language implemented in the RPython language* (which is essentially a restricted dialect of Python 2.7). Now **that's** higher-order magic if anything is.
    - For the use case of numerics specifically, instead of Python, [Julia](https://docs.julialang.org/en/v1/manual/methods/) may be a better fit for writing high-level, yet performant code. It's a spiritual heir of Common Lisp, Fortran, *and Python*. Compilation to efficient machine code, with the help of gradual typing and automatic type inference, is a design goal.

### Common Lisp, Python, and productivity

The various essays by Paul Graham, especially [Revenge of the Nerds (2002)](http://paulgraham.com/icad.html), have given the initial impulse to many programmers for studying Lisp. The essays are well written and have provided a lot of exposure for Lisp. So how does the programming world look in that light now, 20 years later?

The base abstraction level of programming languages, even those in popular use, has increased. The trend was visible already then, and was indeed noted in the essays. The focus on low-level languages such as C++ has decreased. Java is still popular, but high-level FP languages that compile to JVM bytecode (Kotlin, Scala, Clojure) are rising.

Python has become highly popular, and is now also closer to Lisp than it was 20 years ago, especially after `MacroPy` introduced syntactic macros to Python (in 2013, [according to the git log](https://github.com/lihaoyi/macropy/commits/python2/macropy/__init__.py)). Python wasn't bad as a Lisp replacement even back in 2000 - see Peter Norvig's essay [Python for Lisp Programmers](https://norvig.com/python-lisp.html). Some more historical background, specifically on lexically scoped closures (and the initial lack thereof), can be found in [PEP 3104](https://www.python.org/dev/peps/pep-3104/), [PEP 227](https://www.python.org/dev/peps/pep-0227/), and [Historical problems with closures in JavaScript and Python](http://giocc.com/problems-with-closures-in-javascript-and-python.html).

In 2020, does it still make sense to learn [the legendary](https://xkcd.com/297/) Common Lisp?

To know exactly what it has to offer, yes. As baroque as some parts are, there are a lot of great ideas there. [Conditions](http://www.gigamonkeys.com/book/beyond-exception-handling-conditions-and-restarts.html) are one. [CLOS](http://www.gigamonkeys.com/book/object-reorientation-generic-functions.html) is another. (Nowadays [Julia](https://docs.julialang.org/en/v1/manual/methods/) has CLOS-style [multiple-dispatch generic functions](https://docs.julialang.org/en/v1/manual/methods/).) More widely, in the ecosystem, Swank is one. Having more perspectives at one's disposal makes one a better programmer.

But as a practical tool? Is CL hands-down better than Python? Maybe no. Python has already delivered on 90% of the productivity promise of Lisp. Both languages cut down significantly on [accidental complexity](https://en.wikipedia.org/wiki/No_Silver_Bullet). Python has a huge library ecosystem. `MacroPy`, `unpythonic` and `pydialect` are trying to push the language-level features a further 5%. (A full 100% is likely impossible when extending an existing language; if nothing else, there will be seams.)

As for productivity, [it may be](https://medium.com/smalltalk-talk/lisp-smalltalk-and-the-power-of-symmetry-8bd96aaa0c0c) that a form of code-data equivalence (symmetry!), not macros specifically, is what makes Lisp powerful. If so, there may be other ways to reach that equivalence. For example Smalltalk, like Lisp, *runs in the same context it's written in*. All Smalltalk data are programs. Smalltalk [may be making a comeback](https://hackernoon.com/how-to-evangelize-a-programming-language-0p7p3y02), in the form of [Pharo](https://pharo.org/).

Haskell aims at code-data equivalence from a third angle (memoized pure functions are in essence infinite lookup tables), but I haven't used it in practice, so I don't have the experience to say whether this is enough to make it feel powerful in the same way.

Image-based programming (live programming) is a common factor between Pharo and Common Lisp + Swank. This is another productivity booster that much of the programming world isn't that familiar with. It eliminates not only the edit/compile/restart cycle, but the edit/restart cycle as well, making the workflow a concurrent *edit/run* instead (without restarting the whole app at each change). Julia has [Revise.jl](https://github.com/timholy/Revise.jl) for something similar.

### Python is not a Lisp

The point behind providing `let` and `begin` (and the ``let[]`` and ``do[]`` [macros](macros.md)) is to make Python lambdas slightly more useful - which was really the starting point for the whole `unpythonic` experiment.

The oft-quoted single-expression limitation of the Python ``lambda`` is ultimately a herring, as this library demonstrates. The real problem is the statement/expression dichotomy. In Python, the looping constructs (`for`, `while`), the full power of `if`, and `return` are statements, so they cannot be used in lambdas. (This observation has been earlier made by others, too; see e.g. the [Wikipedia page on anonymous functions](https://en.wikipedia.org/wiki/Anonymous_function#Python).) We can work around some of this:

 - The expr macro ``cond[]`` gives us a general ``if``/``elif``/``else`` expression.
   - Without it, the expression form of `if` (that Python already has) could be used, but readability suffers if nested, since it has no ``elif``. Actually, [`and` and `or` are sufficient for full generality](https://www.ibm.com/developerworks/library/l-prog/), but readability suffers even more.
   - So we use MacroPy to define a ``cond`` expression, essentially duplicating a feature the language already almost has. See [our macros](macros.md).
 - Functional looping (with TCO, to boot) is possible. See the constructs in ``unpythonic.fploop``.
 - ``unpythonic.ec.call_ec`` gives us ``return`` (the ec).
 - ``unpythonic.misc.raisef`` gives us ``raise``, and ``unpythonic.misc.tryf`` gives us ``try``/``except``/``else``/``finally``.
 - A lambda can be named (``unpythonic.misc.namelambda``, with some practical limitations on the fully qualified name of nested lambdas).
 - Even an anonymous function can recurse with some help (``unpythonic.fun.withself``).
 - Context management (``with``) is currently **not** available for lambdas, even in ``unpythonic``.

Still, ultimately one must keep in mind that Python is not a Lisp. Not all of Python's standard library is expression-friendly; some standard functions and methods lack return values - even though a call is an expression! For example, `set.add(x)` returns `None`, whereas in an expression context, returning `x` would be much more useful, even though it does have a side effect.

### On ``let`` and Python

Why no `let*`, as a function? In Python, name lookup always occurs at runtime. Python gives us no compile-time guarantees that no binding refers to a later one - in [Racket](http://racket-lang.org/), this guarantee is the main difference between `let*` and `letrec`.

Even Racket's `letrec` processes the bindings sequentially, left-to-right, but *the scoping of the names is mutually recursive*. Hence a binding may contain a lambda that, when eventually called, uses a binding defined further down in the `letrec` form.

In contrast, in a `let*` form, attempting such a definition is *a compile-time error*, because at any point in the sequence of bindings, only names found earlier in the sequence have been bound. See [TRG on `let`](https://docs.racket-lang.org/guide/let.html).

Our `letrec` behaves like `let*` in that if `valexpr` is not a function, it may only refer to bindings above it. But this is only enforced at run time, and we allow mutually recursive function definitions, hence `letrec`.

Note the function versions of our `let` constructs, in the pure-Python API, are **not** properly lexically scoped; in case of nested ``let`` expressions, one must be explicit about which environment the names come from.

The [macro versions](macros.md) of the `let` constructs **are** lexically scoped. The macros also provide a ``letseq[]`` that, similarly to Racket's ``let*``, gives a compile-time guarantee that no binding refers to a later one.

Inspiration: [[1]](https://nvbn.github.io/2014/09/25/let-statement-in-python/) [[2]](https://stackoverflow.com/questions/12219465/is-there-a-python-equivalent-of-the-haskell-let) [[3]](http://sigusr2.net/more-about-let-in-python.html).

### Assignment syntax

Why the clunky `e.set("foo", newval)` or `e << ("foo", newval)`, which do not directly mention `e.foo`? This is mainly because in Python, the language itself is not customizable. If we could define a new operator `e.foo <op> newval` to transform to `e.set("foo", newval)`, this would be easily solved.

Our [macros](macros.md) essentially do exactly this, but by borrowing the ``<<`` operator to provide the syntax ``foo << newval``, because even with MacroPy, it is not possible to define new [BinOp](https://greentreesnakes.readthedocs.io/en/latest/nodes.html#BinOp)s in Python. That would be possible essentially as a *reader macro* (as it's known in the Lisp world), to transform custom BinOps into some syntactically valid Python code before proceeding with the rest of the import machinery, but it seems as of this writing, no one has done this.

If you want a framework to play around with reader macros in Python, see [Pydialect](https://github.com/Technologicat/pydialect). You'll still have to write a parser, where [Pyparsing](https://github.com/pyparsing/pyparsing) may help; but supporting something as complex as a customized version of the surface syntax of Python is still a lot of work, and may quickly go out of date.

Without macros, in raw Python, we could abuse `e.foo << newval`, which transforms to `e.foo.__lshift__(newval)`, to essentially perform `e.set("foo", newval)`, but this requires some magic, because we then need to monkey-patch each incoming value (including the first one when the name "foo" is defined) to set up the redirect and keep it working.

 - Methods of builtin types such as `int` are read-only, so we can't just override `__lshift__` in any given `newval`.
 - For many types of objects, at the price of some copy-constructing, we can provide a wrapper object that inherits from the original's type, and just adds an `__lshift__` method to catch and redirect the appropriate call. See commented-out proof-of-concept in [`unpythonic/env.py`](unpythonic/env.py).
 - But that approach doesn't work for function values, because `function` is not an acceptable base type to inherit from. In this case we could set up a proxy object, whose `__call__` method calls the original function (but what about the docstring and such? Is `@functools.wraps` enough?). But then there are two kinds of wrappers, and the re-wrapping logic (which is needed to avoid stacking wrappers when someone does `e.a << e.b`) needs to know about that.
 - It's still difficult to be sure these two approaches cover all cases; a read of `e.foo` gets a wrapped value, not the original; and this already violates [The Zen of Python](https://www.python.org/dev/peps/pep-0020/) #1, #2 and #3.

If we later choose go this route nevertheless, `<<` is a better choice for the syntax than `<<=`, because `let` needs `e.set(...)` to be valid in an expression context.

The current solution for the assignment syntax issue is to use macros, to have both clean syntax at the use site and a relatively hackfree implementation.

### TCO syntax and speed

Benefits and costs of ``return jump(...)``:

 - Explicitly a tail call due to ``return``.
 - The trampoline can be very simple and (relatively speaking) fast. Just a dumb ``jump`` record, a ``while`` loop, and regular function calls and returns.
 - The cost is that ``jump`` cannot detect whether the user forgot the ``return``, leaving a possibility for bugs in the client code (causing an FP loop to immediately exit, returning ``None``). Unit tests of client code become very important.
   - This is somewhat mitigated by the check in `__del__`, but it can only print a warning, not stop the incorrect program from proceeding.
   - We could mandate that trampolined functions must not return ``None``, but:
     - Uniformity is lost between regular and trampolined functions, if only one kind may return ``None``.
     - This breaks the *don't care about return value* use case, which is rather common when using side effects.
     - Failing to terminate at the intended point may well fall through into what was intended as another branch of the client code, which may correctly have a ``return``. So this would not even solve the problem.

The other simple-ish solution is to use exceptions, making the jump wrest control from the caller. Then ``jump(...)`` becomes a verb, but this approach is 2-5x slower, when measured with a do-nothing loop. (See the old default TCO implementation in v0.9.2.)

Our [macros](macros.md) provide an easy-to use solution. Just wrap the relevant section of code in a ``with tco:``, to automatically apply TCO to code that looks exactly like standard Python. With the macro, function definitions (also lambdas) and returns are automatically converted. It also knows enough not to add a ``@trampolined`` if you have already declared a ``def`` as ``@looped`` (or any of the other TCO-enabling decorators in ``unpythonic.fploop``, or ``unpythonic.fix.fixtco``).

For other libraries bringing TCO to Python, see:

 - [tco](https://github.com/baruchel/tco) by Thomas Baruchel, based on exceptions.
 - [ActiveState recipe 474088](https://github.com/ActiveState/code/tree/master/recipes/Python/474088_Tail_Call_Optimization_Decorator), based on ``inspect``.
 - ``recur.tco`` in [fn.py](https://github.com/fnpy/fn.py), the original source of the approach used here.
 - [MacroPy](https://github.com/azazel75/macropy) uses an approach similar to ``fn.py``.

### No Monads?

(Beside List inside ``forall``.)

Admittedly unpythonic, but Haskell feature, not Lisp. Besides, already done elsewhere, see [OSlash](https://github.com/dbrattli/OSlash) if you need them.

If you want to roll your own monads for whatever reason, there's [this silly hack](https://github.com/Technologicat/python-3-scicomp-intro/blob/master/examples/monads.py) that wasn't packaged into this; or just read Stephan Boyer's quick introduction [[part 1]](https://www.stephanboyer.com/post/9/monads-part-1-a-design-pattern) [[part 2]](https://www.stephanboyer.com/post/10/monads-part-2-impure-computations) [[super quick intro]](https://www.stephanboyer.com/post/83/super-quick-intro-to-monads) and figure it out, it's easy. (Until you get to `State` and `Reader`, where [this](http://brandon.si/code/the-state-monad-a-tutorial-for-the-confused/) and maybe [this](https://gaiustech.wordpress.com/2010/09/06/on-monads/) can be helpful.)

### No Types?

The `unpythonic` project will likely remain untyped indefinitely, since I don't want to enter that particular marshland with things like `curry` and `with continuations`. It may be possible to gradually type some carefully selected parts - but that's currently not on [the roadmap](https://github.com/Technologicat/unpythonic/milestones). I'm not against it, if someone wants to contribute.

In general, on type systems, [this three-part discussion on LtU](http://lambda-the-ultimate.org/node/220) was interesting:

- "Dynamic types" held by values are technically **tags**.
- Type checking can be seen as another stage of execution that runs at compilation time. In a dynamically typed language, this can be implemented by manually delaying execution until type tags have been checked - *[lambda, the ultimate staging annotation](http://lambda-the-ultimate.org/node/175#comment-1198)*. Witness [statically typed Scheme](http://lambda-the-ultimate.org/node/100#comment-1197) using manually checked tags, and then automating that with macros. (Kevin Millikin)
- Dynamically typed code **always contains informal/latent, static type information** - that's how we reason about it as programmers. *There are rules to determine which operations are legal on a value, even if these rules are informal and enforced only manually.* (Anton van Straaten, paraphrased)
- The view of untyped languages as [*unityped*](https://news.ycombinator.com/item?id=8206562), argued by Robert Harper, using a single `Univ` type that contains all values, is simply an *embedding* of untyped code into a typed environment. It does not (even attempt to) encode the latent type information.
  - [Sam Tobin-Hochstadt, one of the Racket developers, argues](https://medium.com/@samth/on-typed-untyped-and-uni-typed-languages-8a3b4bedf68c) taking that view is missing the point, if our goal is to understand how programmers reason when they write in dynamically typed languages. It is useful as a type-theoretical justification for dynamically typed languages, nothing more.

Taking this into a Python context, if *explicit is better than implicit* (ZoP §2), why not make at least some of this latent information, **that must be there anyway**, machine-checkable? Hence type annotations (PEP [3107](https://www.python.org/dev/peps/pep-3107/), [484](https://www.python.org/dev/peps/pep-0484/), [526](https://www.python.org/dev/peps/pep-0526/)) and [mypy](http://mypy-lang.org/).

More on type systems:

- Haskell's [typeclasses](http://learnyouahaskell.com/types-and-typeclasses).
- Some postings on the pros and cons of statically vs. dynamically typed languages:
  - [Paul Chiusano: The advantages of static typing, simply stated](https://pchiusano.github.io/2016-09-15/static-vs-dynamic.html)
  - [Jonathan Gros-Dubois: Statically typed vs dynamically typed languages](https://hackernoon.com/statically-typed-vs-dynamically-typed-languages-e4778e1ca55)
- [Laurence Tratt: Another non-argument in type systems](https://tratt.net/laurie/blog/entries/another_non_argument_in_type_systems.html) (a rebuttal to Robert Harper)
  - See also [Dynamically typed languages, Laurence Tratt, Advances in Computers, vol. 77, pages 149-184, July 2009](https://tratt.net/laurie/research/pubs/html/tratt__dynamically_typed_languages/).
- Serious about types? [Bartosz Milewski: Category Theory for Programmers](https://bartoszmilewski.com/2014/10/28/category-theory-for-programmers-the-preface/) (online book)
- [Chris Smith: What To Know Before Debating Type Systems](http://blogs.perl.org/users/ovid/2010/08/what-to-know-before-debating-type-systems.html)
- [Martin Fowler on dynamic typing](https://www.martinfowler.com/bliki/DynamicTyping.html)
- Do we need types? At least John Shutt (the author of the [Kernel](https://web.cs.wpi.edu/~jshutt/kernel.html) programming language) seems to think we don't: [Where do types come from?](http://fexpr.blogspot.com/2011/11/where-do-types-come-from.html)
- In physics, units as used for dimension analysis are essentially a form of static typing.
  - This has been discussed on LtU, see e.g. [[1]](http://lambda-the-ultimate.org/node/33) [[2]](http://lambda-the-ultimate.org/classic/message11877.html).

### Detailed Notes on Macros

 - ``continuations`` and ``tco`` are mutually exclusive, since ``continuations`` already implies TCO.
   - However, the ``tco`` macro skips any ``with continuations`` blocks inside it, **for the specific reason** of allowing modules written in the [Lispython dialect](https://github.com/Technologicat/pydialect) (which implies TCO for the whole module) to use ``with continuations``.

 - ``prefix``, ``autoreturn``, ``quicklambda`` and ``multilambda`` are first-pass macros (expand from outside in), because they change the semantics:
   - ``prefix`` transforms things-that-look-like-tuples into function calls,
   - ``autoreturn`` adds ``return`` statements where there weren't any,
   - ``quicklambda`` transforms things-that-look-like-list-lookups into ``lambda`` function definitions,
   - ``multilambda`` transforms things-that-look-like-lists (in the body of a ``lambda``) into sequences of multiple expressions, using ``do[]``.
   - Hence, a lexically outer block of one of these types *will expand first*, before any macros inside it are expanded, in contrast to the default *from inside out* expansion order.
   - This yields clean, standard-ish Python for the rest of the macros, which then don't need to worry about their input meaning something completely different from what it looks like.

 - An already expanded ``do[]`` (including that inserted by `multilambda`) is accounted for by all ``unpythonic.syntax`` macros when handling expressions.
   - For simplicity, this is **the only** type of sequencing understood by the macros.
   - E.g. the more rudimentary ``unpythonic.seq.begin`` is not treated as a sequencing operation. This matters especially in ``tco``, where it is critically important to correctly detect a tail position in a return-value expression or (multi-)lambda body.
   - *Sequencing* is here meant in the Racket/Haskell sense of *running sub-operations in a specified order*, unrelated to Python's *sequences*.

 - The TCO transformation knows about TCO-enabling decorators provided by ``unpythonic``, and adds the ``@trampolined`` decorator to a function definition only when it is not already TCO'd.
   - This applies also to lambdas; they are decorated by directly wrapping them with a call: ``trampolined(lambda ...: ...)``.
   - This allows ``with tco`` to work together with the functions in ``unpythonic.fploop``, which imply TCO.

 - Macros that transform lambdas (notably ``continuations`` and ``tco``):
   - Perform a first pass to take note of all lambdas that appear in the code *before the expansion of any inner macros*. Then in the second pass, *after the expansion of all inner macros*, only the recorded lambdas are transformed.
     - This mechanism distinguishes between explicit lambdas in the client code, and internal implicit lambdas automatically inserted by a macro. The latter are a technical detail that should not undergo the same transformations as user-written explicit lambdas.
     - The identification is based on the ``id`` of the AST node instance. Hence, if you plan to write your own macros that work together with those in ``unpythonic.syntax``, avoid going overboard with FP. Modifying the tree in-place, preserving the original AST node instances as far as sensible, is just fine.
     - For the interested reader, grep the source code for ``userlambdas``.
   - Support a limited form of *decorated lambdas*, i.e. trees of the form ``f(g(h(lambda ...: ...)))``.
     - The macros will reorder a chain of lambda decorators (i.e. nested calls) to use the correct ordering, when only known decorators are used on a literal lambda.
       - This allows some combos such as ``tco``, ``unpythonic.fploop.looped``, ``curry``.
     - Only decorators provided by ``unpythonic`` are recognized, and only some of them are supported. For details, see ``unpythonic.regutil``.
     - If you need to combo ``unpythonic.fploop.looped`` and ``unpythonic.ec.call_ec``, use ``unpythonic.fploop.breakably_looped``, which does exactly that.
       - The problem with a direct combo is that the required ordering is the trampoline (inside ``looped``) outermost, then ``call_ec``, and then the actual loop, but because an escape continuation is only valid for the dynamic extent of the ``call_ec``, the whole loop must be run inside the dynamic extent of the ``call_ec``.
       - ``unpythonic.fploop.breakably_looped`` internally inserts the ``call_ec`` at the right step, and gives you the ec as ``brk``.
     - For the interested reader, look at ``unpythonic.syntax.util``.

 - ``namedlambda`` is a two-pass macro. In the first pass (outside-in), it names lambdas inside ``let[]`` expressions before they are expanded away. The second pass (inside-out) of ``namedlambda`` must run after ``curry`` to analyze and transform the auto-curried code produced by ``with curry``. In most cases, placing ``namedlambda`` in a separate outer ``with`` block runs both operations in the correct order.

 - ``autoref`` does not need in its output to be curried (hence after ``curry`` to gain some performance), but needs to run before ``lazify``, so that both branches of each transformed reference get the implicit forcing. Its transformation is orthogonal to what ``namedlambda`` does, so it does not matter in which exact order these two run.

 - ``lazify`` is a rather invasive rewrite that needs to see the output from most of the other macros.

 - ``envify`` needs to see the output of ``lazify`` in order to shunt function args into an unpythonic ``env`` without triggering the implicit forcing.

 - Some of the block macros can be comboed as multiple context managers in the same ``with`` statement (expansion order is then *left-to-right*), whereas some (notably ``curry`` and ``namedlambda``) require their own ``with`` statement.
   - This is a [known issue in MacroPy](https://github.com/azazel75/macropy/issues/21). I have made a [fix](https://github.com/azazel75/macropy/pull/22), but still need to make proper test cases to get it merged.
   - If something goes wrong in the expansion of one block macro in a ``with`` statement that specifies several block macros, surprises may occur.
   - When in doubt, use a separate ``with`` statement for each block macro that applies to the same section of code, and nest the blocks.
     - Test one step at a time with the ``macropy.tracing.show_expanded`` block macro to make sure the expansion looks like what you intended.

### Miscellaneous notes

- [Nick Coghlan (2011): Traps for the unwary in Python's import system](http://python-notes.curiousefficiency.org/en/latest/python_concepts/import_traps.html).

- Beware of the *double-import shared-resource decorator trap*. From the [Pyramid web framework documentation](https://docs.pylonsproject.org/projects/pyramid/en/latest/designdefense.html):
  - *Module-localized mutation is actually the best-case circumstance for double-imports. If a module only mutates itself and its contents at import time, if it is imported twice, that's OK, because each decorator invocation will always be mutating an independent copy of the object to which it's attached, not a shared resource like a registry in another module. This has the effect that double-registrations will never be performed.*
  - In case of `unpythonic`, the `dynassign` module only mutates its own state, so it should be safe. But `regutil.register_decorator` is potentially dangerous, specifically in that if the same module is executed once as `__main__` (running as the main app) and once as itself (due to also getting imported from another module), a decorator may be registered twice. (It doesn't cause any ill effects, though, except for a minor slowdown, and the list of all registered decorators not looking as clean as it could.)
