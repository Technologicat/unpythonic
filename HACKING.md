# Hacking unpythonic, a.k.a. contribution guidelines

**Rule #1**: Code and/or documentation contributions are welcome!

- **Scope**: language extensions and utilities.
  - Lispy, haskelly, and/or functional features all fit. It can be anything from a small utility function to a complete (optional) change of language semantics.
    - Lisp should be understood in the familial sense, including e.g. [Common Lisp](http://clhs.lisp.se/Front/index.htm), [Scheme](https://schemers.org/) (including the [SRFI extensions](https://srfi.schemers.org/)), and [Racket](https://racket-lang.org/).
    - Some lispy features are actually imperative, not functional. This is fine. Just like Python, Lisp is a multi-paradigm language.
    - Borrowing ideas from random other languages is fine, too. The `dbg[]` macro was inspired by [Rust](https://www.rust-lang.org/). What next... [Julia](https://julialang.org/)?
  - If a feature is large, and useful by itself, a separate project may be The Right Thing.
    - Consider [`pydialect`](https://github.com/Technologicat/pydialect) and [`imacropy`](https://github.com/Technologicat/imacropy), which are closely related to `unpythonic`, but separate. (Those features are now part of [`mcpyrate`](https://github.com/Technologicat/mcpyrate), but the point stands.)
    - The hot-patching [REPL server](doc/repl.md) (`unpythonic.net`) is a borderline case. Hot-patching live processes is a legendary Common Lisp feature (actually powered by Swank [[0]](https://common-lisp.net/project/slime/doc/html/Connecting-to-a-remote-lisp.html) [[1]](https://stackoverflow.com/questions/31377098/interact-with-a-locally-long-running-common-lisp-image-possibly-daemonized-fro) [[2]](https://github.com/LispCookbook/cl-cookbook/issues/115) [[3]](https://stackoverflow.com/questions/8874615/how-to-replace-a-running-function-in-common-lisp)), so arguably it belongs; but the machinery is large and only loosely coupled to the rest of `unpythonic`, which favors splitting it off into a separate project.
  - When in doubt, osmosis: if it feels like a particular feature is missing, chances are high that it will fit.

- **Motivation**: teaching, learning, bringing Python closer to perfection, increasing productivity.
  - `unpythonic` started as a collection of code analysis exercises, developed while teaching the special course [RAK-19006: Python 3 in Scientific Computing](https://github.com/Technologicat/python-3-scicomp-intro/) at Tampere University of Technology, spring term 2018.
  - Aim at clarity. Target generally intelligent readers, who are not necessarily familiar with the specific construct you're writing about, or even with the language that may have inspired it.
    - For example, the special course was aimed at M.Sc. and Ph.D. students in the engineering sciences. It's common in fields of science involving computing to be proficient in mathematics, yet not have much programming experience.
  - Aim at increasing your own future productivity. Is Python missing some batteries and/or language features?
    - Not all ideas have to be good, especially right away. Generally the only way to find out is to try, and then iterate.


## Most importantly

- **Be pythonic**: *find pythonic ways to do unpythonic things.*
  - Fitting user expectations of how Python behaves beats mathematical elegance.
  - For example, `scanr` returns its results in the same order as it scans them, even though this breaks Haskell tradition.

- **Be obsessively correct.**
  - **Get the terminology right**. This promotes clear thinking. For example:
      - A function definition has [(formal) *parameters*, which are filled by *arguments* at call time](https://docs.python.org/3/faq/programming.html#faq-argument-vs-parameter).
      - *Dynamic assignment* is descriptive, while *dynamic scoping* is nonsense, because *scope* is arguably a lexical concept (cf. dynamic *extent*).
    - Sometimes different subcultures have different names for the same ideas (e.g. Python's *unpacking* vs. Lisp's *destructuring*). When there is no universal standard, feel free to pick one option, but list the alternative names if reasonably possible. Bringing [a touch of the Rosetta stone](http://rosettacode.org/wiki/Rosetta_Code) helps discoverability.
    - If I have made a terminology mistake, please challenge it, to get it fixed in a future release.
  - **Lack of robustness is a bug.** The code should do the right thing in edge cases, possibly in corner cases too.
    - For example, `memoize` catches and caches exceptions. The singleton-related abstractions (`Singleton`, `sym` and `gsym`) worry about the thread-safety of constructing the singleton instance. All custom data structure types worry about pickling.
    - When it doesn't make sense to cover all corner cases, think it through, and give examples (in documentation) of what isn't covered.

- **Be obsessively complete** when going the extra mile adds value.
  - For example:
    - Not only a summarizing `minmax` utility, but `running_minmax` as well. The former is then just a one-liner expressed in terms of the latter.
    - `foldl` accepts multiple iterables, has a switch to terminate either on the shortest or on the longest input, and takes its arguments in a curry-friendly order. It also *requires* at least one iterable, so that `curry` knows to not trigger the call until at least one iterable has been provided.
    - `curry` changes Python's reduction semantics to be more similar to Haskell's, to pass extra arguments through on the right, and keep calling if an intermediate result is a function, and there are still such passed-through arguments remaining. This extends what can be expressed concisely, [for example](http://www.cse.chalmers.se/~rjmh/Papers/whyfp.html) a classic lispy `map` is `curry(lambda f: curry(foldr, composerc(cons, f), nil))`. Feed that a function and an iterable, and get a linked list with the mapped results. Note the arity mismatch; `f` is 1-to-1, but `cons` is 2-to-1.
  - **Make features work together** when it makes sense. Aim at composability. Try to make features orthogonal when reasonably possible, so that making them work together requires no extra effort. When not possible, purposefully minimizing friction in interaction between features makes for a coherent, easily understandable language extension.

- **Be concise but readable**, like in mathematics.
  - If an implementation could be made shorter, perhaps it should. But resist the temptation to [golf](https://en.wikipedia.org/wiki/Code_golf). If readability or features would suffer, that's when to stop.
    - Some extra complexity (and hence length) is tolerable when it adds value.
    - Leaving a commented-out, elegant illustrative example version of the code (in addition to the battle-ready production version that's actually in use) can be useful to document the core idea. See `memoize` and `curry` for examples.
  - As a **rough guideline**, at most ~700 *lines* per module. Python is expressive; that's a lot.
    - Language extensions and utilities tend to be much more dense than e.g. GUI or database code.
    - Functional style can also enable very dense code by taking advantage of the ability to define custom higher-order functions and use function composition.
  - Prefer ~100-300 [*SLOC*](https://en.wikipedia.org/wiki/Source_lines_of_code) per module, if reasonably possible.
    - Don't obsess over it, if going over allows a better solution.
    - Docstrings, comments and blanks don't count towards SLOC. The included `countlines.py` is what I've used for measurement.

- **Test aggressively.**
  - Beside guarding against [regressions](https://en.wikipedia.org/wiki/Software_regression), automated tests also serve as documentation (possibly with useful comments).
  - Write tests for each module (unit), as well as any relevant interactions between features (integration).
  - Keep in mind the [Practical Test Pyramid (Ham Vocke, 2018)](https://martinfowler.com/articles/practical-test-pyramid.html).

- **Document aggressively.**
  - *Useful* docstrings for public API functions are mandatory in release-worthy code.
    - Explain important points, omit boilerplate.
    - Use [reStructuredText](https://docutils.sourceforge.io/docs/user/rst/quickref.html) syntax.
      - Prefer basic features that enhance readability, yet avoid ruining the plain-text aesthetics.
  - *Having no docstring is better than having a placeholder docstring.*
    - If a function is not documented, make that fact explicit, to help [static analyzers](https://pypi.org/project/pyflakes/) flag it as needing documentation.
  - To help discoverability, the full documentation `doc/features.md` (or `doc/macros.md`, as appropriate) should contain at least a mention of each public feature. Examples are nice, too.
  - Features that have non-obvious uses (e.g. `@call`), as well as those that cannot be assumed to be familiar to Python developers (e.g. Common Lisp style *conditions and restarts*) should get a more detailed explanation.


## Technical overview

In short: regular code is in `unpythonic`, macros are in `unpythonic.syntax`, and REPL server related stuff is in `unpythonic.net`.

Automated tests are in `tests` (note plural), under the directory whose modules they test. The test runner is, unsurprisingly, `runtests.py`, at the top level. Yes, I know many developers [prefer to separate](https://blog.ionelmc.ro/2014/05/25/python-packaging/#the-structure) the `src` and `tests` hierarchies at the top level; we currently don't, mostly for historical reasons.

For coverage analysis, [`coverage.py`](https://github.com/nedbat/coveragepy) works fine for analyzing [statement coverage](https://en.wikipedia.org/wiki/Code_coverage#Basic_coverage_criteria). Block macros do cause [some false negatives](https://github.com/nedbat/coveragepy/issues/1004), but this is minor.

We use a custom testing framework, which lives in the modules `unpythonic.test.fixtures` (note singular `test`, part of the framework name) and `unpythonic.syntax.testingtools`. It uses conditions and restarts to communicate between individual tests and the testset, which acts as a reporter.

In retrospect, given that the main aim was compact testing syntax for macro-enabled Python code (without installing another import hook, doing which would disable the macro expander), it might have made more sense to make the testing macros compile to [pytest](https://docs.pytest.org/en/latest/). But hey, it's short, may have applications in teaching... and now we can easily write custom test runners, since the testing framework is just a `mcpyrate` library. It's essentially a *no-framework* (cf. "NoSQL"), which provides the essentials and lets the user define the rest.

(The whole framework is about 1.3k SLOC, counting docstrings, comments and blanks; under 600 SLOC if counting only active code lines. Add another 800 SLOC (all) / 200 SLOC (active code lines) for the condition system.)

Since `unpythonic` is a relatively loose collection of language extensions and utilities, that's about it for the 30 000 ft (9 144 m) view.

To study a particular feature, just start from the entry point that piques your interest, and follow the definitions recursively. Use an IDE or Emacs's `anaconda-mode` ~for convenience~ to stay sane. Look at the automated tests; those double as usage examples, sometimes containing finer points that didn't make it to prose documentation.

`curry` has some [cross-cutting concerns](https://en.wikipedia.org/wiki/Cross-cutting_concern), but nothing that a grep wouldn't find.

The `lazify` and `continuations` macros are the most complex (and perhaps fearsome?) parts. As for the lazifier, grep also for `passthrough_lazy_args` and `maybe_force_args`. As for continuations, read the `tco` macro first, and keep in mind how that works when reading `continuations`. The `continuations` macro is essentially what [academics call](https://cs.brown.edu/~sk/Publications/Papers/Published/pmmwplck-python-full-monty/paper.pdf) *"a standard [CPS](https://en.wikipedia.org/wiki/Continuation-passing_style) transformation"*, plus some technical details due to various bits of impedance mismatch.

`unpythonic.syntax.scopeanalyzer` is a unfortunate artifact that is needed to implement macros that interact with Python's scoping rules, notably `let`. Fortunately, [the language reference explicitly documents](https://docs.python.org/3/reference/executionmodel.html#naming-and-binding) what is needed for a lexical scope analysis for Python. So we have just implemented that (better, as an AST analysis, rather than scanning the surface syntax text).

As of the first half of 2021, the main target platforms are **CPython 3.8** and **PyPy3 3.7** (since as of April 2021, PyPy3 does not have 3.8 yet). The code should run on 3.6 or any later Python. We have [a GitHub workflow](https://github.com/Technologicat/unpythonic/actions?query=workflow%3A%22Python+package%22) that runs the test suite on CPython 3.6 through 3.9, and on PyPy3.


## Style guide

- **Use [semantic versioning](https://semver.org/).**
  - For now (early 2020), there's a leading zero, but the intent is to drop it sooner rather than later.

- **Use from-imports**.
  - The `unpythonic` style is `from ... import ...`.
  - The from-import syntax is mandatory for macro imports in user code, anyway, since macro expanders for Python (including `mcpyrate`) support only `from ... import macros, ...` for importing macros. We just use the same style also for regular imports.
  - For imports of certain features of `unpythonic` (including, but not limited to, `curry`), our macro code depends on those features being referred to by their original bare names at the use site. This won't work if the `import ...` syntax is used. For the same reason, locally renaming `unpythonic` features with `from ... import ... as ...` should be avoided.
  - For imports of stuff from outside `unpythonic`, it's a matter of convention. Sometimes `import ...` can be clearer.
  - No star-import `from ... import *`, except in the top-level `__init__.py`, where it is allowed for re-exporting the public APIs.

- **Try to pick good names.**
  - *"There are only two hard things in Computer Science: cache invalidation and naming things."* --[Phil Karlton](https://martinfowler.com/bliki/TwoHardThings.html)
  - Try to pick a short, descriptive name that doesn't need to be changed soon.
  - Preferably one word, but if there is none that will fit, and no chance for a newly coined yet obvious word (e.g. SymPy's `lambdify`), then perhaps two or more words separated by underscores must do the job... for now.
  - When coining a new term, try to quickly check that it's not in common use for something entirely different in some other programming subculture.
    - Observe the two different meanings of `throw`/`catch` in [Common Lisp](http://www.gigamonkeys.com/book/the-special-operators.html) vs. [C++](https://en.cppreference.com/w/cpp/language/try_catch)/[Java](https://www.w3schools.com/java/java_try_catch.asp).

- **Try to keep backward compatibility. But build for the long term.**
  - Practicality beats purity. Backward compatibility is important.
  - But sometimes elegance beats practicality. If a breaking change makes the code much simpler, it may be The Right Thing... to schedule for the next major version milestone.

- **Avoid external dependencies.**
  - Diametrically opposite to the sensible approach for most software projects, but `unpythonic` is meant as a standalone base to build on. Few dependencies makes it easy to install, and more unlikely to break.
  - [`mcpyrate`](https://github.com/Technologicat/mcpyrate) is fine, but keep the macro features (and the `mcpyrate` dependency) **strictly optional**.
    - `unpythonic` should be able to run, without its macro features, on a standard Python.
    - Macros can depend on regular code. `unpythonic.syntax` is a subpackage, so the parent level `__init__.py` has already finished running when it's imported.

- **Build a tower of abstractions.**
  - Internal dependencies are encouraged. It is precisely the role of a language extension and utility library to make code shorter. As long as the result imports without errors, it's fine.
  - For example, some parts already use `dyn`, some `box`, yet others `scanl` or `foldl`.

- **Export explicitly.**
  - In regular (non-macro) code, any names intended as exports **must** be present in [`__all__`](https://docs.python.org/3/tutorial/modules.html#importing-from-a-package). Although not everyone uses it, this is the official mechanism to declare a module's public API, [recommended by PEP8](https://www.python.org/dev/peps/pep-0008/#public-and-internal-interfaces).
  - It makes re-export trivial, so that `from .somemodule import *`, in the top-level `__init__.py`, automatically pulls in the public API, and *only* the public API of `somemodule`.
  - This in turn helps properly support `from unpythonic import *` for interactive sessions.
  - While *"anything without a leading underscore is public"* is often a reasonable guideline, that includes also any imports done by the module... which more often than not should not be blindly re-exported. So be explicit.
  - Only populate `__all__` explicitly, manually, to allow IDEs and static analysis tools to work properly. (No tricks. See commented-out code in `unpythonic.llist` for an example of a bad idea.)

- **Be curry-friendly** whenever reasonably possible.
  - Even though it is more pythonic to pass arguments by name, passing them positionally should not be ruled out.
  - **Parameters that change the least often**, and hence are meaningful to partially apply for, should **go on the left**.
    - For higher-order functions this usually means the user function on the left, data on the right.
  - To say `def f(other, args, *things)` in situations where passing in at least one `thing` is mandatory, the correct signature is `def f(other, args, thing0, *things)`.
    - This makes it explicit that at least a `thing0` must be supplied before `f` can be meaningfully called.
      - **`curry` needs this information to work properly.**
    - The syntactic issue is that Python has a Kleene-star `*args`, but no [Kleene-plus](https://en.wikipedia.org/wiki/Kleene_star#Kleene_plus) `+args` that would *require* at least one.
    - The standard library doesn't bother, so e.g. `map` may fire prematurely when curried. (Hence we provide a curry-friendly wrapper for `map`.)

- **Be functional** ([FP](https://en.wikipedia.org/wiki/Functional_programming)) when it makes sense.
  - Don't mutate input unnecessarily. Construct and/or edit a copy instead, and return that.
    - Macros are an exception to this. Syntax transformers usually edit the AST in-place, not build a copy.
  - If there is a useful value that could be returned, return it, even if the function performs a mutating operation. This allows chaining operations.

- **Refactor aggressively**. Extract reusable utilities.
  - When implementing something, if you run into an empty niche, add the missing utility, and implement your higher-level functionality in terms of it.
  - This keeps code at each level of abstraction short, and exposes parts that can later be combined in new ways.

- **Follow [PEP8](https://www.python.org/dev/peps/pep-0008/) style**, *including* the official recommendation to violate PEP8 when the guidelines do not apply. Specific to `unpythonic`:
  - Conserve vertical space when reasonable. Even on modern laptops, a display can only fit ~50 lines at a time.
  - `x = x or default` for initializing `x` inside the function body of `def f(x=None)` (when it makes no sense to publish the actual default value) is concise and very readable.
    - But avoid overusing if-expressions.
  - Line width ~110 columns. This still allows two columns in a modern editor.
    - Can locally go a character or three over, if that gives globally a more pleasing layout for the text. Examples include a long word at the end of a line, or if a full stop wouldn't fit.
    - No line breaks in URLs, even if over 110 characters. URLs should be copy'n'pasteable, as well as allow `link-hint-open-link-at-point` to work in Emacs.
  - European style: *one* space between a full stop and the next sentence.
  - **A blank line in code plays the role of a paragraph break in prose.**
    - Insert a blank line when the topic changes, or when doing so significantly increases clarity.
    - Sometimes a group of related very short methods or functions looks clearer **without** blank lines separating them. This makes the grouping explicit.
    - One blank line after most function definitions, **as well as class definitions**.
    - Two blank lines only if the situation already requires a blank line, **and the topic changes**.
      - Use your judgment. E.g. maybe there should be two blank lines between the class definitions of `ThreadLocalBox` and `Shim`, but on the other hand, maybe not. The deciding question is whether we consider them as belonging to the same conceptual set of abstractions.

- [**Contracts**](https://en.wikipedia.org/wiki/Design_by_contract) and **type checking**.
  - **Contracts**. State clearly in the docstrings what your code expects and what it provides. **Semantics are crucial.** Type is nice to know, but not terribly important.
    - What is the service the function provides? (General explanation.)
    - What are the requirements on its input, for it to perform that service? (Parameters.)
      - What happens if those requirements are violated? (E.g. possible exception types, and why each of them may be raised. Obvious ones may be omitted.)
    - Provided those requirements are satisfied, what is guaranteed about its output? (Return value(s).)
    - Are there invariants the function preserves? (Notes.)
      - In case it's not obvious, is the function [pure](https://en.wikipedia.org/wiki/Pure_function)? This is important in a multi-paradigm language.
  - **Dynamic type checking** is ok, both `isinstance` and duck variants.
    - A *thin* abstraction layer (in the sense of [On Lisp](http://www.paulgraham.com/onlisp.html)) might not even need a type check of its own, if, upon a type error, it's clear from the resulting stack trace that the function crashed because a specific argument didn't make sense. This keeps the codebase clutter-free.
    - In cases where an error message more specific to your function is helpful, then a dynamic type check and a corresponding `raise` upon failure is The Right Thing.
    - Report what was expected, what the actual value was instead - at least the type, but preferably also the value. This helps track down bugs in code using that function, based on the stack trace alone.
  - **Contract validation** at run time is also ok - it's a Turing-complete language, after all.
    - If the requirements on the input don't hold, then the caller is at fault. If the guarantees about output don't hold, then the function broke its own contract. This helps narrow down bugs.
    - Obviously, some properties cannot be automatically checked (e.g., is the given iterable finite?). **The docstring is the most important.**
  - **To help avoid accidental transpositions of arguments in function calls**, take advantage of Python's named arguments.
    - Passing arguments positionally can be risky. Even static type declarations won't help detect accidental transpositions of arguments that have the same type.
    - Any arguments that don't have a standard ordering are good candidates to be made **keyword-only**.
      - E.g. a triple of coordinates is almost always ordered `(x, y, z)`, so individual coordinate arguments are a good candidate to be passed positionally. But the `src` and `dst` parameters in a file copy operation could be defined either way around. So to prevent bugs, The Right Thing is to *require* stating, at the call site, which is intended to be which.
  - **Static type declarations** are not considered part of `unpythonic` style.
    - Technically, Python's object model [is based on the prototype paradigm](https://eev.ee/blog/2017/11/28/object-models/), so strictly speaking the language doesn't even have static types. [This is perfectly fine](https://medium.com/@samth/on-typed-untyped-and-uni-typed-languages-8a3b4bedf68c).
      - Because in Python, it is possible to arbitrarily monkey-patch object instances, there's no guarantee that two object instances that advertise themselves as having the same type are actually alike in any meaningful way.
      - `isinstance` only checks if the object instance was minted by a particular constructor. Until someone [retroactively changes the type](https://github.com/ActiveState/code/tree/master/recipes/Python/160164_automatically_upgrade_class_instances). (Python's `isinstance` is a close relative of JavaScript's [`instanceof`](https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Operators/instanceof).)
      - In practice, there is rarely a need to exploit all of this dynamism. Actual Python code is often much more static, which allows things like the static type checker [mypy](http://www.mypy-lang.org/) to work.
    - So, static type declarations are not frowned upon, but I likely won't bother with any for the code I write for the library.

- **Macros.**
  - *Macros are the nuclear option of software engineering.*
    - Only make a macro when a regular function can't do what is needed.
    - Sometimes a regular code core with a thin macro layer on top, to improve the user experience, is the appropriate solution for [minimizing magic](https://macropy3.readthedocs.io/en/latest/discussion.html#minimize-macro-magic). See `do`, `let` for examples.
  - `unpythonic/syntax/__init__.py` is very long (> 2000 lines), because:
    - For technical reasons, as of MacroPy 1.1.0b2, it's not possible to re-export macros defined in another module. (As of `unpythonic` 0.15, this is no longer relevant, since we use `mcpyrate`, which **can** re-export macros. So `unpythonic.syntax` may be revised in a future version of `unpythonic`.)
    - Therefore, all macro entry points must reside in `unpythonic/syntax/__init__.py`, so that user code can `from unpythonic.syntax import macros, something`, without caring about how the `unpythonic.syntax` package is internally organized.
    - The docstring must be placed on the macro entry point, so that the REPL will find it. This forces all macro docstrings into that one module. (That's less magic than injecting them dynamically when `unpythonic` boots up.)
    - A macro entry point can be just a thin wrapper around the relevant [*syntax transformer*](http://www.greghendershott.com/fear-of-macros/): a regular function, which takes and returns an AST.
  - You can have an expr, block and decorator macro with the same name, in the same module, by making the macro interface into a dispatcher. See the `syntax` kw in `mcpyrate`.
    - If you do this, the docstring should be placed in whichever of those is defined last, because that one will be the definition left standing at run time (hence used for docstring lookup by the REPL).
  - Syntax transformers can and should be sensibly organized into modules, just like any other regular (non-macro) code.
    - But they don't need docstrings, since the macro entry point already has the docstring.
  - If your syntax transformer (or another one it internally uses) needs `mcpyrate` `**kw` arguments:
    - Declare the relevant `**kw`s as parameters for the macro entry point, therefore requesting `mcpyrate` to provide them. Stuff them into `dyn` using `with dyn.let(...)`, and call your syntax transformer, which can then get the `**kw`s from `dyn`. See the existing macros for examples.
    - Using `dyn` keeps the syntax transformer call signatures clean, while limiting the dynamic extent of what is effectively a global assignment. If we used only function parameters, some of the high-level syntax transformers would have to declare `expander` just to pass it through, possibly through several layers, until it reaches the low-level syntax transformer that actually needs it. Avoiding such a parameter definition cascade is exactly the use case `dyn` was designed for.
  - If a set of macros shares common utilities, but those aren't needed elsewhere, that's a prime candidate for placing all that in one module.
    - See e.g. `tailtools.py`, which implements `tco` and `continuations`. The common factor is tail-position analysis.

- **Violate these guidelines when it makes sense to do so.**
