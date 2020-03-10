# Hacking unpythonic, a.k.a. contribution guidelines

**Rule #1**: Code and/or documentation contributions are welcome!


## Most importantly

- **Scope**: language extensions and utilities.
  - Lispy, haskelly, and/or functional features all fit. Anything from a small utility function to a complete (but optional) change of language semantics may fit.
    - Lisp should be understood in the familial sense, including e.g. [Common Lisp](http://clhs.lisp.se/Front/index.htm), [Scheme](https://schemers.org/), [Racket](https://racket-lang.org/), and Scheme's [SRFI extensions](https://srfi.schemers.org/).
    - Some lispy features are actually imperative, not functional. This is fine. Just like Python, Lisp is a multi-paradigm language.
  - If a feature is large, and useful by itself, a separate project may be The Right Thing.
    - Consider [`pydialect`](https://github.com/Technologicat/pydialect) and [`imacropy`](https://github.com/Technologicat/imacropy), which are closely related to `unpythonic`, but separate.
    - The hot-patching [REPL server](doc/repl.md) (`unpythonic.net`) is a borderline case. Hot-patching live processes is a legendary Common Lisp feature (actually powered by Swank [[0]](https://common-lisp.net/project/slime/doc/html/Connecting-to-a-remote-lisp.html) [[1]](https://stackoverflow.com/questions/31377098/interact-with-a-locally-long-running-common-lisp-image-possibly-daemonized-fro) [[2]](https://github.com/LispCookbook/cl-cookbook/issues/115) [[3]](https://stackoverflow.com/questions/8874615/how-to-replace-a-running-function-in-common-lisp)), so arguably it belongs; but the machinery is large and only loosely coupled to the rest of `unpythonic`, which favors splitting it off into a separate project.
  - When in doubt, osmosis: if it feels like a particular feature is missing, chances are high that it will fit.

- **Motivation**: teaching, learning, bringing Python closer to perfection, increasing productivity.
  - `unpythonic` started as a collection of code analysis exercises, developed while teaching the special course [RAK-19006: Python 3 in Scientific Computing](https://github.com/Technologicat/python-3-scicomp-intro/) at Tampere University of Technology, spring term 2018.
  - Aim at clarity. Aim what you write at generally intelligent readers, who are not necessarily familiar with the specific construct you're writing about.
    - For example, the special course was aimed at M.Sc. and Ph.D. students in the engineering sciences. It's common in fields of science involving computing to be proficient in mathematics, yet not have much programming experience.
  - Aim at increasing your own future productivity, by implementing missing batteries and missing language features.
    - Not all ideas have to be good; generally the only way to find out is to try.

- **Be pythonic**: *find pythonic ways to do unpythonic things.*
  - Fitting user expectations of how Python behaves beats mathematical elegance.
  - For example, `scanr` returns its results in the same order as it scans them, even though this breaks Haskell tradition.

- **Be obsessively correct.**
  - **Get the terminology right**. This promotes clear thinking. For example:
    - A function definition has [(formal) *parameters*, which are filled by *arguments* at call time](https://docs.python.org/3/faq/programming.html#faq-argument-vs-parameter).
    - *Dynamic assignment* is descriptive, while *dynamic scoping* is nonsense, because *scope* is arguably a lexical concept (cf. dynamic *extent*).
    - If I have made a terminology mistake, please challenge it! It's nice to get things fixed in a future release.
  - **Lack of robustness is a bug.** The code should the right thing in edge cases, possibly in corner cases too.
    - For example, `memoize` catches and caches exceptions. The singleton-related abstractions (`Singleton`, `sym` and `gsym`) worry about the thread-safety of constructing the singleton instance. All custom data structure types worry about pickling.
    - When it doesn't make sense to cover all corner cases, think it through, and give examples (in documentation) of what isn't covered.

- **Be obsessively complete** when going the extra mile adds value.
  - For example:
    - Not only a summarizing `minmax` utility, but `running_minmax` as well. The former is then just a one-liner expressed in terms of the latter.
    - `foldl` accepts multiple iterables, has a switch to terminate either on the shortest or on the longest input, and takes its arguments in a curry-friendly order. It also *requires* at least one iterable, so that `curry` knows to not trigger the call until at least one iterable has been provided.
    - `curry` changes Python's reduction semantics to be more similar to Haskell's, to pass extra arguments through on the right, and keep calling if an intermediate result is a function, and there are still such passed-through arguments remaining. This extends what can be expressed concisely, for example a classic lispy `map` is `curry(lambda f: curry(foldr, composerc(cons, f), nil))`. Feed that a function and an iterable, and get a linked list with the mapped results. Note the arity mismatch; `f` is 1-to-1, but `cons` is 2-to-1.
  - **Make features work together** when it makes sense. Aim at composability. Try to make features orthogonal when reasonably possible, but when not, minimizing friction in interaction between features makes for a coherent, easily understandable language extension.

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
    - No placeholder docstrings, because that just hides problems from [static analysis](https://pypi.org/project/pyflakes/).
  - To help discoverability, `doc/features.md` (or `doc/macros.md`, as appropriate) should contain at least a mention of each public feature. Examples are nice, too.
  - Features that have non-obvious uses (e.g. `@call`), as well as those that cannot be assumed to be familiar to Python developers (e.g. Common Lisp style *conditions and restarts*) should get a more detailed explanation.


## Technical overview

In short: regular code is in `unpythonic`, macros are in `unpythonic.syntax`, and REPL server related stuff is in `unpythonic.net`. Since `unpythonic` is a relatively loose collection of language extensions and utilities, that's about it.

To study a particular feature, just start from the entry point, and follow the definitions recursively. An IDE or Emacs's `anaconda-mode` can make this convenient.

`curry` has some consequences, but nothing that a grep wouldn't find.

The `lazify` and `continuations` macros are the most complex parts. As for the lazifier, grep also for `passthrough_lazy_args` and `maybe_force_args`. As for continuations, read the `tco` macro first, and keep in mind how that works when reading `continuations`.

`unpythonic.syntax.scoping` is a unfortunate artifact that is needed to implement macros that interact with Python's scoping rules, notably `let`.

As of early 2020, the main target is Python 3.6, both **CPython** and **PyPy3**. The code should run on 3.4 or any later Python. The intent is to drop support for 3.4 and 3.5 in the next major version. Special attention should be devoted to compatibility with 3.8, which flipped the switch on the compiler so that now it generates `ast.Constant` nodes for literals. We may have some macro code dealing with the old `ast.Num`, `ast.Str` or `ast.NamedConstant`, which should be made to accept `ast.Constant` (in addition to the old types, as long as we support Python 3.6 and 3.7).


## Style guide

- **Use [semantic versioning](https://semver.org/).**
  - For now (early 2020), there's a leading zero, but the intent is to drop it sooner rather than later.

- **Use from-imports**, `from ... import ...`. This is the `unpythonic` style.
  - The from-import syntax is mandatory for macro imports in user code, anyway, since MacroPy (as of 1.1.0b2) supports only `from ... import macros, ...` for importing macros. We just use the from-import syntax for regular imports, too.
  - For imports of certain features of `unpythonic` (e.g. `curry`), our macro code depends on those features being referred to by their original bare names at the use site. This won't work if the `import ...` syntax, or the `from ... import ... as ...` syntax is used.
  - For imports of stuff from outside `unpythonic`, it's a matter of convention. Sometimes `import ...` can be clearer.
  - The star-import `from ... import *` is allowed in exactly one place: the top-level `__init__.py`. When used together with the magic `__all__` in modules, it's the pythonic idiom for *import public API for re-export*.

- **Try to pick good names.**
  - *"There are only two hard things in Computer Science: cache invalidation and naming things."* --[Phil Karlton](https://martinfowler.com/bliki/TwoHardThings.html)
  - Try to pick a short, descriptive name that doesn't need to be changed soon.
  - Preferably one word, but if there is none that will fit, and no chance for a newly coined yet obvious word (e.g. SymPy's `lambdify`), then perhaps two or more words separated by underscores must do the job... for now.

- **Try to keep backward compatibility.**
  - Practicality beats purity.
  - But sometimes elegance of implementation beats practicality. If a breaking change makes the code much simpler, it may be The Right Thing to schedule that for the next major version milestone.

- **Avoid external dependencies.**
  - Directly opposite to the sensible approach for most software projects, but `unpythonic` is meant as a standalone base to build on. Few dependencies makes it easy to install, and more unlikely to break.
  - [MacroPy](https://github.com/azazel75/macropy) is fine, but keep the macro features (and the MacroPy dependency) **strictly optional**.
    - `unpythonic` should be able to run, without its macro features, on a standard Python.
    - Macros can depend on regular code. `unpythonic.syntax` is a subpackage, so the parent level `__init__.py` has already finished running when it's imported.

- **Build a tower of abstractions.**
  - Internal dependencies are encouraged. It is precisely the role of a language extension and utility library to make code shorter. As long as the result imports without errors, it's fine.
  - For example, some parts already use `dyn`, some `box`, yet others `scanl` or `foldl`.

- **Export explicitly.**
  - In regular (non-macro) code, any names intended as exports **must** be present in [`__all__`](https://docs.python.org/3/tutorial/modules.html#importing-from-a-package). Although not everyone uses it, this is the official mechanism to declare a module's public API, [recommended by PEP8](https://www.python.org/dev/peps/pep-0008/#public-and-internal-interfaces).
  - It makes re-export trivial, so that `from .somemodule import *`, in the top-level `__init__.py`, automatically pulls in the public API, and *only* the public API of `somemodule`.
  - This in turn helps properly support `from unpythonic import *`, which is convenient for interactive sessions.
  - While *"anything without a leading underscore is public"* is often a reasonable guideline, that includes also any imports done by the module... which more often than not should not be blindly re-exported. So be explicit.
  - Only populate `__all__` explicitly, manually, to allow IDEs and static analysis tools to work properly. (No tricks. See commented-out code in `unpythonic.llist` for an example of a bad idea.)

- **Be curry-friendly** whenever reasonably possible.
  - Even though it can be more pythonic to pass arguments by name, passing them positionally should not be ruled out.
  - Parameters that change the least often, and hence are meaningful to partially apply for, should go on the left.
    - For higher-order functions this usually means the user function on the left, data on the right.

- **Be functional** ([FP](https://en.wikipedia.org/wiki/Functional_programming)) when it makes sense.
  - Don't mutate input unnecessarily. Construct and/or edit a copy instead, and return that.
    - Macros are an exception to this; due to how MacroPy works, syntax transformers should edit the AST, not build a new one.
  - If there is a useful value that could be returned, return it, even if the function performs a mutating operation. This allows chaining operations.

- **Refactor aggressively**: extract reusable utilities.
  - When implementing something, if you run into an empty niche, add the missing utility, and implement your higher-level functionality in terms of it.
  - This keeps code at each level of abstraction short, and exposes parts that can later be combined in new ways.

- **Type checking** and beyond.
  - **Contracts**. State clearly in the docstrings what your code expects and what it provides. Not just the type, but the semantics.
    - What is the service the function provides?
    - What are the requirements on its input, for it to perform that service?
    - Provided those requirements are satisfied, what is guaranteed about its output?
    - Are there invariants the function preserves?
      - In case it's not obvious, is the function [pure](https://en.wikipedia.org/wiki/Pure_function)? This is important in a multi-paradigm language.
  - **Dynamic type checking** is ok, both `isinstance` and duck variants.
  - **Contract validation** at run time is also ok - it's a Turing-complete language, after all.
    - If the requirements on the input don't hold, then the caller is at fault. If the guarantees about output don't hold, then the function broke its own contract. This helps narrow down bugs.
    - Obviously, some properties cannot be automatically checked, because some questions are not decidable. So the docstring is the most important.
  - **To help avoid accidental transpositions of arguments in function calls**, take advantage of Python's named arguments.
    - Passing arguments positionally can be risky. Even static type declarations won't help detect accidental transpositions of arguments that have the same type.
    - Any arguments that don't have a standard ordering are good candidates to be made **keyword-only**.
      - E.g. a triple of coordinates is almost always ordered `(x, y, z)`, so individual coordinate arguments are a good candidate to be passed positionally. But the `src` and `dst` parameters in a file copy operation could be defined either way around. So to prevent bugs, The Right Thing is to *require* stating, at the call site, which is intended to be which.
  - **Static type declarations** are not considered part of `unpythonic` style, but are not frowned upon.

- **Macros.**
  - *Macros are the nuclear option of software engineering.*
    - Only make a macro when a regular function can't do what is needed.
    - Sometimes a regular code core with a thin macro layer on top, to improve the user experience, is the appropriate solution for [minimizing magic](https://macropy3.readthedocs.io/en/latest/discussion.html#minimize-macro-magic). See `do`, `let` for examples.
  - `unpythonic/syntax/__init__.py` is very long (> 2000 lines), because:
    - For technical reasons, as of MacroPy 1.1.0b2, it's not possible to re-export macros defined in another module.
    - Therefore, all macro entry points must reside in `unpythonic/syntax/__init__.py`, so that user code can `from unpythonic.syntax import macros, something`, without caring about how the `unpythonic.syntax` package is internally organized.
    - The docstring must be placed on the macro entry point, so that the REPL will find it. This forces all macro docstrings into that one module. (That's less magic than injecting them when `unpythonic` boots up.)
    - A macro entry point can be just a thin wrapper around the relevant [*syntax transformer*](http://www.greghendershott.com/fear-of-macros/): a regular function, which takes and returns an AST.
  - You can have an expr, block and decorator macro with the same name, in the same module, because MacroPy holds each kind in a separate registry.
    - If you do this, the docstring should be placed in whichever of those is defined last, because that one will be the definition left standing at run time (hence used for docstring lookup by the REPL).
  - Syntax transformers can and should be sensibly organized into modules, just like any other regular (non-macro) code.
    - But they don't need docstrings, since the macro entry point already has the docstring.
  - If your syntax transformer (or another one it internally uses) needs `gen_sym` or other MacroPy `**kw` arguments:
    - Declare the relevant `**kw`s as parameters for the entry point, therefore requesting MacroPy to provide them. Stuff them into `dyn`, and call your syntax transformer, which can then get the `**kw`s from `dyn`. See the existing macros for examples.
    - Using `dyn` keeps the syntax transformer call signatures clean, while limiting the dynamic extent of what is effectively a global assignment. If we used only function parameters, some of the high-level syntax transformers would have to declare `gen_sym` just to pass it through, possibly through several layers, until it reaches the low-level syntax transformer that actually needs it. Avoiding such a parameter definition cascade is exactly the use case `dyn` was designed for.

- **Violate these guidelines when it makes sense to do so.**
