**Navigation**

- [README](../README.md)
- [Pure-Python feature set](features.md)
- [Syntactic macro feature set](macros.md)
- [Examples of creating dialects using `mcpyrate`](dialects.md)
- [REPL server](repl.md)
- [Troubleshooting](troubleshooting.md)
- [Design notes](design-notes.md)
- [Essays](essays.md)
- **Additional reading**
- [Contribution guidelines](../CONTRIBUTING.md)

<!-- markdown-toc start - Don't edit this section. Run M-x markdown-toc-refresh-toc -->
**Table of Contents**

- [Links to relevant reading](#links-to-relevant-reading)
- [Python-related FP resources](#python-related-fp-resources)

<!-- markdown-toc end -->

# Links to relevant reading

This document collects links to blog posts, online articles and actual scientific papers on topics at least somewhat relevant in the context of `unpythonic`.

The common denominator is programming. Some relate to language design, some to curious individual technical details, and some are just cool finds, archived here because I don't currently have a better place for them.

- [Matthias Felleisen, 1991: On the expressive power of programming languages](https://www.sciencedirect.com/science/article/pii/016764239190036W). Science of Computer Programming, 17(1--3), 1991, 35--75. [doi:10.1016/0167-6423(91)90036-W](https://doi.org/10.1016/0167-6423(91)90036-W)
  - A seminal paper on how to quantify the difference in "power" between programming languages.

- [Evelyn Woods, 2017: A comparison of object models of Python, Lua, JavaScript and Perl](https://eev.ee/blog/2017/11/28/object-models/).
  - Useful reading for anyone interested in how the object models differ.
  - It can be argued **Python is actually prototype-based**, like JavaScript.
    - [Prototypes in OOP on Wikipedia](https://en.wikipedia.org/wiki/Prototype-based_programming). Actually a nice summary.
  - See also [prototype.py](https://github.com/airportyh/prototype.py) (unfortunately 2.7; to run it in 3.x, would need at least replacing `new` with the appropriate classes from `types`).

- [William R. Cook, OOPSLA 2009: On Understanding Data Abstraction, Revisited](https://www.cs.utexas.edu/~wcook/Drafts/2009/essay.pdf).
  - This is a nice paper illustrating the difference between *abstract data types* and *objects*.
  - In section 4.3: *"In the 1970s [...] Reynolds noticed that abstract data types facilitate adding new operations, while 'procedural data values' (objects) facilitate adding new representations. Since then, this duality has been independently discovered at least three times [18, 14, 33]."* Then: *"The extensibility problem has been solved in numerous ways, and it still inspires new work on extensibility of data abstractions [48, 15]. Multi-methods are another approach to this problem [11]."*
    - Multimethods (as in multiple dispatch in CLOS or in Julia) seem nice, in that they don't enfore a particular way to slice the operation/representation matrix. Instead, one fills in individual cells as desired. It solves [the expression problem](https://en.wikipedia.org/wiki/Expression_problem).
  - In section 5.4, on Smalltalk: *"One conclusion you could draw from this analysis is that the untyped λ-calculus was the first object-oriented language."*
  - In section 6: *"Academic computer science has generally not accepted the fact that there is another form of data abstraction besides abstract data types. Hence the textbooks give the classic stack ADT and then say 'objects are another way to implement abstract data types'. [...] Some textbooks do better than others. Louden [38] and Mitchell [43] have the only books I found that describe the difference between objects and ADTs, although Mitchell does not go so far as to say that objects are a distinct kind of data abstraction."*

- [Joel Spolsky, 2000: Things you should never do, part I](https://www.joelonsoftware.com/2000/04/06/things-you-should-never-do-part-i/)
  - Classic, and still true:

    *"We’re programmers. Programmers are, in their hearts, architects, and the first thing they want to do when they get to a site is to bulldoze the place flat and build something grand. We’re not excited by incremental renovation: tinkering, improving, planting flower beds.*

    *There’s a subtle reason that programmers always want to throw away the code and start over. The reason is that they think the old code is a mess. And here is the interesting observation:* they are probably wrong. *The reason that they think the old code is a mess is because of a cardinal, fundamental law of programming:*

    ***It’s harder to read code than to write it.***"

- [Geoffrey Thomas, 2015: signalfd is useless](https://ldpreload.com/blog/signalfd-is-useless)
 - [Martin Sústrik, 2012: EINTR and What It Is Good For](http://250bpm.com/blog:12)

- [Nathaniel Smith, 2018: Notes on structured concurrency, or: Go statement considered harmful](https://vorpus.org/blog/notes-on-structured-concurrency-or-go-statement-considered-harmful/)
   - Very insightful posting on the near isomorphism between classic goto, and classic approaches to handling async concurrency. Based on the analysis, [he's built a more structured solution](https://github.com/python-trio/trio).

- [Olin Shivers (1998) on 80% and 100% designs](http://www.ccs.neu.edu/home/shivers/papers/sre.txt)

- [Faré Rideau (2012): Consolidating Common Lisp libraries](https://fare.livejournal.com/169346.html)
  - A call to action to counter the [Lisp Curse](http://winestockwebdesign.com/Essays/Lisp_Curse.html).

- [Common Lisp style guide](https://lisp-lang.org/style-guide/)

- Some opinions on modularity [[1]](https://gist.github.com/substack/5075355) [[2]](http://blog.millermedeiros.com/mout-and-modularity/)

- [Stefan Ram summarizing the subtleties of defining referential transparency](http://userpage.fu-berlin.de/~ram/pub/pub_jf47ht81Ht/referential_transparency) (link [from this discussion](https://www.thecodingforums.com/threads/some-basic-questions.677086/)).
   - Søndergaard and Sestoft's original paper is [Referential transparency, definiteness and unfoldability](https://link.springer.com/article/10.1007/BF00277387) (Acta Informatica 27(6), 505-517, 1990).

- [Oleg Kiselyov (2007): Dynamic binding, binding evaluation contexts, and (delimited) control effects](http://okmij.org/ftp/Computation/dynamic-binding.html). Could be interesting to be able to refer to previous (further up the stack) values of a dynamically bound variable.

- [SICP is now an internet meme](https://knowyourmeme.com/forums/meme-research/topics/47038-structure-and-interpretation-of-computer-programs-hugeass-image-dump-for-evidence). See e.g. [this one](http://i.imgur.com/1ZGjEDn.jpg).

- [sans-io](https://sans-io.readthedocs.io/), the right way to define network protocols.

- [Clean Architecture](https://blog.cleancoder.com/uncle-bob/2012/08/13/the-clean-architecture.html).
  - In a nutshell, turning dependencies upside down. Push any platform-specific details to the edges of your system. Keep your core business logic free of dependencies. An outer part is allowed to depend on an inner one, but not the other way around.
  - Requires a bit more glue code than the traditional approach, but allows easily switching out platform-specific components.
  - E.g. your database glue code should depend on your business logic; but the business logic should assume nothing about a database.

- [Clean Code for Python](https://github.com/zedr/clean-code-python)
  - *Software engineering principles, from Robert C. Martin's book [Clean Code](https://www.amazon.com/Clean-Code-Handbook-Software-Craftsmanship/dp/0132350882), adapted for Python.*

- [PyPy3](http://pypy.org/), fast, JIT-ing Python 3 that's mostly a drop-in replacement for CPythons 3.6 and 3.7. As of April 2021, support for 3.8 is in the works. Macro expanders (`macropy`, `mcpyrate`) work, too.

- [Brython](https://brython.info/): Python 3 in the browser, as a replacement for JavaScript.
  - No separate compile step - the compiler is implemented in JS. Including a script tag of type text/python invokes it.
  - Doesn't have the `ast` module, so no way to run macro expanders.
  - Also quite a few other parts are missing, understandably. Keep in mind the web client is rather different as an environment from the server side or the desktop. So for new apps, Brython is ok, but if you have some existing Python code you want to move into the browser, it might or might not work, depending on what your code needs.

- Counterpoint: [Eric Torreborre (2019): When FP does not save us](https://medium.com/barely-functional/when-fp-does-not-save-us-92b26148071f)

- [SRFI-45](https://srfi.schemers.org/srfi-45/) promises. Similar in spirit to MacroPy promises.
    - We define the term *promise* [as Scheme/Racket do](https://docs.racket-lang.org/reference/Delayed_Evaluation.html): *memoized, delayed evaluation*. In JavaScript the same term means [something completely different](https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/Promise), related to [`async`/`await`](https://javascript.info/async-await).
      - As an aside, JS's `async`/`await` work pretty much just [like in Python](https://snarky.ca/how-the-heck-does-async-await-work-in-python-3-5/).
      - As another aside, Racket doesn't have `async`/`await`, but it has [futures with true parallelism](https://docs.racket-lang.org/reference/futures.html). The `shift`/`reset` delimited continuation operators can be used to implement [something akin to `async`/`await`](http://www.gregrosenblatt.com/writing/reinvert-control-delim-cont.html).

- Now [this remark](https://docs.python.org/3/reference/datamodel.html#id8) sounds interesting. Retroactively *changing an object's type* in Python, [like in CLOS](https://en.wikipedia.org/wiki/Circle-ellipse_problem#Change_the_programming_language).
    - Michael Hudson has done this (2002, 2004): [ActiveState Python recipe 160164: Automatically upgrade class instances](https://github.com/ActiveState/code/tree/master/recipes/Python/160164_automatically_upgrade_class_instances) when you redefine the class.
      - Triggered on module reloads, too. To decide what class to upgrade, it looks for a class of the same name in the scope that defined the new class. Then there's an instance tracker that keeps weakrefs to the existing instances of the old class.
    - A simpler solution might be to just [`gc.get_objects()`](https://docs.python.org/3/library/gc.html#gc.get_objects), and filter for what we want to find the instances to be updated. (Provided we still have a reference to the old class object, to use in the filter predicate. That part needs some thought.)

- C2 Wiki on the [Compile-time typing problem](http://wiki.c2.com/?CompileTimeTypingProblem)
  - This is one of the best-written pages on the C2 Wiki.

- [dmbarbour, 2012: Why not events](https://awelonblue.wordpress.com/2012/07/01/why-not-events/)
  - Linked from an [LtU discussion on (functional) reactive programming](http://lambda-the-ultimate.org/node/2057).

- [StackOverflow: What is functional reactive programming?](https://stackoverflow.com/questions/1028250/what-is-functional-reactive-programming) contains some links to introductory material on FRP.

- Ingo Maier, Tiark Rompf, Martin Odersky 2010: Deprecating the Observer Pattern [PDF](http://archive.www6.in.tum.de/www6/pub/Main/TeachingWs2013MSE/2_OderskyDeprecatingObservers.pdf) [LtU discussion](http://lambda-the-ultimate.org/node/4028)
  - According to the paper, the observer pattern *"violates an impressive line-up of important software engineering principles"*; as a remedy, the authors propose a reactive dataflow model (`Scala.React`). Note this was in 2010.
    - As of 2020, for Python 3.6 and later, see [RxPY: Reactive Extensions for Python](https://github.com/ReactiveX/RxPY).
  - In section 6.4, the authors also mention having developed a CPS transformation based continuations system in Scala 2.8. Since `unpythonic` does that for Python, their other writings might contain useful hints as to how to make such a system usable enough for writing production code.

- [Shaula Yemini, Daniel M. Berry 1985: A Modular Verifiable Exception-Handling Mechanism](https://citeseerx.ist.psu.edu/viewdoc/download?doi=10.1.1.146.1148&rep=rep1&type=pdf). ACM Transactions on Programming Languages and Systems, Vol. 7, No. 2, April 1985.
  - In section 1.2: *"Exceptions are characterized by a pair of assertions, the exception condition, and the corresponding resumption condition. The resumption condition describes the condition that any handler resuming the signaller must satisfy in order for the operation to eventually satisfy its normal case output assertion. [...] The full significance of an exception may not be apparent in the context of the detecting module (otherwise it would not be an exception). Rather, it is the invoker of the operation which knows the purpose of the application of the operation and therefore the significance of the detection of the exception."*
    - *Resumption* condition? This suggests conditions and restarts, as in Common Lisp. CL dates from 1984, so the timing seems about right.
  - In section 2.1: *"A programming language is said to be orthogonal if it is constructed from a small set of primitive features whose functions have no overlap and which can be composed arbitrarily, with no or few exceptions, to obtain its full coverage. [...] Although many disagree with us, we believe that the restrictions born of the lack of orthogonality in a language are a drawback far outweighing the seemingly excess generality resulting from orthogonality in a language. Excess generality can simply not be used, while restrictions must be known, adhered to, and sometimes programmed around, even if they are present for the purpose of keeping programs simple."*
    - Nice, compact definition, and a good point about the lack of symmetry between excess restrictions vs. excess generality.
  - In section 2.3: *"When exceptions are signalled, it should be possible to pass parameters to whatever handler is prepared to field the exception. This in turn requires that handlers have formal parameters. Without this capability, [...] 2. a separate handler for each possible raising point must be provided, which knows its unique circumstances for raising. This decreases strength because many more handlers with similar, though not exactly the same, function must be provided."*
    - **And that's exactly what people do, 35 years later!** As of 2020, it's still uncommon in Python programs to pack useful recovery information into an exception instance, and abstract the exception handler into a reusable function that takes the exception instance (containing that useful context-specific recovery information, not just a type and a stack trace) as an argument.
      - Perhaps Python's focus on statements and blocks, instead of allowing `def` as an expression, and making `except` take a function instead of a literal block of code, is partly to blame for this? C++ and Java are no better. But Lisps often get this right. When an exception handler is too specific to be useful as a reusable named function, you can always just `λ (err) (...)` instead, and the slot to plug in a named function (instead of a lambda) remains there to take advantage of elsewhere, where applicable. If you don't have that slot, then the syntax itself suggests against extracting reusable exception handlers into named functions. As if there was no [DRY](https://en.wikipedia.org/wiki/Don't_repeat_yourself), or an ability to define functions, or any of that [jazz](https://en.wikipedia.org/wiki/Take_Five).
  - In section 2.4: *"As a typical example of this situation, consider the exception subscript out of bounds being propagated to the invoker of a function using stack operations. The parameter of this exception is the invalid subscript. By getting this exception, the invoker of the stack operation is told that an array is used to implement the stack."*
    - Nice point about leaky abstractions, and now we have an actual paper to cite that discusses this often-brought-out example.
  - In section 2.4: *"In cases in which the exception can be meaningfully propagated to the invoker’s invoker, it is as a different exception relevant to the level of abstraction visible to the invoker’s invoker. To achieve this, the handler of the first exception can signal an exception which is visible in the scope of the invoker’s invoker. This exception is likely to have a different identifier and a different set of parameters from the original exception."*
    - Python: `raise ... from ...`.
  - Lots more, but stopping here; that's already enough quoted from one paper in a readings list.

- Gregor Kiczales, John Lamping, Cristina Videira Lopes, Chris Maeda, Anurag Mendhekar, Gail Murphy 1997: Open Implementation Design Guidelines. In ICSE '97: Proceedings of the 19th international conference on Software engineering. May 1997. Pages 481--490. [doi:10.1145/253228.253431](https://doi.org/10.1145/253228.253431).
  - In the introduction: *"The open implementation approach works by somewhat shifting the black-box guidelines for module design. Whereas black-box modules hide all aspects of their implementation, open implementation modules allow clients some control over selection of their implementation strategy, while still hiding many true details of their implementation. In doing this, open implementation module designs strive for an appropriate balance between preserving the kind of opacity black-box modules have, and providing the kind of performance tailorability some clients require."*

- [Arjun Guha, Jacob Matthews, Robert Bruce Findler, Shriram Krishnamurthi 2007: Relationally-Parametric Polymorphic Contracts](http://cs.brown.edu/~sk/Publications/Papers/Published/gmfk-rel-par-poly-cont/).
  - In section 1, summary about the type/contract analogy: *"Because most dynamic languages lack static type systems, dynamically-enforced contracts play an invaluable role in both documenting and checking the obedience of pre- and post-conditions. Even in languages with static type systems, they enable the statement of richer conditions than the type system can capture."* And later: *"Where type systems provide static proofs, contracts provide a corresponding notion of dynamic falsification."*
  - In section 1, note on how parametric polymorphism provides guarantees by restricting possible behavior: *"As Wadler has shown, relational parametricity provides strong guarantees about functions just from their types. Informally, if a function f accepts an argument of type α, parametricity ensures that the argument is abstract to f — the argument may not be examined or deconstructed by f in any way. Moreover, f may not determine the concrete type of α."*
  - In section 2.2 (emphasis mine): *"An error projection is a function that returns its argument unmolested, with the exception that it may signal an error on some inputs. Note that the contracts of section 2.1 are precisely error projections. This model is, however, oversimplified, because it does not track blame. **The utility of contracts hinges on their ability to correctly blame the supplier of an invalid value.**"*

- [Guillaume Marceau, Gregory H. Cooper, Jonathan P. Spiro, Shriram Krishnamurthi, Steven P. Reiss 2007: The Design and Implementation of a Dataflow Language for Scriptable Debugging](http://cs.brown.edu/~sk/Publications/Papers/Published/mcskr-dataflow-lang-script-debug-journal/).
  - This is the paper that introduces the [MzTake](http://www.cs.brown.edu/research/plt/software/mztake/) debugger for PLT Scheme (the predecessor of Racket). It makes the case that also in debugging, scripting is needed to automate menial work. A language that supports a reactive paradigm (here FrTime, built on top of Scheme), combined with general-purpose functionality and readily available libraries makes interactive debugging easy - and may allow realtime visualization of things not actually explicitly encoded in the data structures of the program being debugged.
  - In section 11, critique of non-interactive tools for detecting bugs:

    *"Contracts also capture invariants, but they too suffer from the need for static compilation. In addition, data structures sometimes obey a stronger contract in a specific context than they do normally. For instance, in our running example, priority heaps permit keys to change, which means there is no a priori order on a key’s values. As we saw, however, Dijkstra’s algorithm initializes keys to ∞ and decreases them monotonically; importantly, failure to do so results in an error. The topicality of the contract means it should not be associated with the priority heap in general.*

    *Finally, unit testing frameworks provide a mechanism for checking that output from a function matches the expected answer. With respect to debugging, unit testing suffers from the same limitations as contracts. Namely, they operate statically and only along interface lines."*

- [Joe Gibbs Politz, Alejandro Martinez, Matthew Milano, Sumner Warren, Daniel Patterson, Junsong Li, Anand Chitipothu, Shriram Krishnamurthi 2013: Python: The Full Monty - A Tested Semantics for the Python Programming Language. OOPSLA '13.](https://cs.brown.edu/~sk/Publications/Papers/Published/pmmwplck-python-full-monty/paper.pdf) [doi: 10.1145/2509136.2509536](http://dx.doi.org/10.1145/2509136.2509536)
  - A very ambitious undertaking, with nice results.
  - Scope analysis in Python is painful, because the language's syntax conflates definition and rebinding.
  - A special `uninitialized` value (which the paper calls ☠) is needed, because Scope - in the sense of controlling lexical name resolution - is a static (purely lexical) concept, but whether a particular name (once lexically resolved) has been initialized (or, say, whether it has been deleted) is a dynamic (run-time) feature. (I would say "property", if that word didn't have an entirely different technical meaning in Python.)
  - Our `continuations` macro essentially does what the authors call *a standard [CPS](https://en.wikipedia.org/wiki/Continuation-passing_style) transformation*, plus some technical details due to various bits of impedance mismatch.

- [John Shutt's blog](https://fexpr.blogspot.com/) contains many interesting posts on programming language design. He [was](http://lambda-the-ultimate.org/node/5623) the author of the [Kernel](https://web.cs.wpi.edu/~jshutt/kernel.html) Lisp dialect. Some pickings from his blog:
  - [Fexpr (2011)](https://fexpr.blogspot.com/2011/04/fexpr.html).
    - The common wisdom that macros were a better choice is misleading.
  - [Bypassing no-go theorems (2013)](https://fexpr.blogspot.com/2013/07/bypassing-no-go-theorems.html).
    - Especially relevant is the section on Mitchell Wand's no-go theorem [*The Theory of Fexprs is Trivial*](https://www.ccs.neu.edu/home/wand/pubs.html#Wand98).
  - [Abstractive power (2013)](https://fexpr.blogspot.com/2013/12/abstractive-power.html).
  - [Where do types come from? (2011)](https://fexpr.blogspot.com/2011/11/where-do-types-come-from.html).
  - [Continuations and term-rewriting calculi (2014)](https://fexpr.blogspot.com/2014/03/continuations-and-term-rewriting-calculi.html).
  - Discussion of Kernel on LtU: [Decomposing lambda - the Kernel language](http://lambda-the-ultimate.org/node/1680).

- [Walid Taha 2003: A Gentle Introduction to Multi-stage Programming](https://www.researchgate.net/publication/221024597_A_Gentle_Introduction_to_Multi-stage_Programming)

- *Holy traits*:
  - [Tom Kwong 2020: Holy Traits Pattern](https://ahsmart.com/pub/holy-traits-design-patterns-and-best-practice-book/) (book excerpt)
  - [Lyndon White 2019: Emergent features of Julialang: Part II - Traits](https://www.juliabloggers.com/the-emergent-features-of-julialang-part-ii-traits/)
  - [Harrison Grodin 2019: Multiple inheritance, sans inheritance](https://github.com/HarrisonGrodin/radical-julia/tree/master/traits)
  - [Types vs. traits for dispatch](https://discourse.julialang.org/t/types-vs-traits-for-dispatch/46296) (discussion)
  - We have a demonstration in [unpythonic.tests.test_dispatch](../unpythonic/tests/test_dispatch.py).

- [Pascal Costanza's Highly Opinionated Guide to Lisp (2013)](http://www.p-cos.net/lisp/guide.html)

- [Peter Seibel (2005): Practical Common Lisp](https://gigamonkeys.com/book/)
  - This book is an excellent introduction that walks through Common Lisp, including some advanced features. It is also useful for non-lispers to take home interesting ideas from CL.

- R. Kent Dybvig, Simon Peyton Jones, Amr Sabry (2007). A Monadic Framework for Delimited Continuations. Journal of functional programming, 17(6), 687-730. Preprint [here](https://legacy.cs.indiana.edu/~dyb/pubs/monadicDC.pdf).
  - Particularly approachable explanation of delimited continuations.
  - Could try building that for `unpythonic` in a future version.

- [Wat: Concurrency and Metaprogramming for JS](https://github.com/manuel/wat-js)
  - [pywat: Interpreter of the Wat language written in Python](https://github.com/piokuc/pywat)
  - [Example of Wat in Manuel Simoni's blog (2013)](http://axisofeval.blogspot.com/2013/05/green-threads-in-browser-in-20-lines-of.html)

- [Richard P. Gabriel, Kent M. Pitman (2001): Technical Issues of Separation in Function Cells and Value Cells](https://dreamsongs.com/Separation.html)
  - A discussion of [Lisp-1 vs. Lisp-2](https://en.wikipedia.org/wiki/Lisp-1_vs._Lisp-2).

- [`hoon`: The C of Functional Programming](https://urbit.org/docs/hoon/)
  - Interesting take on an alternative computing universe where the functional camp won systems programming. These people have built [a whole operating system](https://github.com/urbit/urbit) on a Turing-complete non-lambda automaton, Nock.
  - For my take, see [the opinion piece in Essays](essays.md#hoon-the-c-of-functional-programming).
  - Judging by the docs, `hoon` is definitely ha-ha-only-serious, but I am not sure of whether it is serious-serious. See the comments to [the entry on Manuel Simoni's blog](http://axisofeval.blogspot.com/2015/07/what-i-learned-about-urbit-so-far.html) - some people do think `hoon` is actually useful.
  - Technical points:
    - `hoon` does not have syntactic macros. The reason given in the docs is the same as sometimes heard in the Python community - having a limited number of standard control structures, you always know what you are looking at.
    - Interestingly, `hoon` has uniform support for *wide* and *tall* modes; it does not use parentheses, but uses a single space (in characteristic `hoon` fashion, termed an *ace*) versus multiple spaces (respectively, a *gap*). "Multiple spaces" allows also newlines, like in LaTeX. So [SRFI-110](https://srfi.schemers.org/srfi-110/srfi-110.html) is not the only attempt at a two-mode uniform grouping syntax.

- *Ab initio* programming language efforts:
  - `hoon`, see separate entry above.
  - [Arc](http://www.paulgraham.com/arc.html) by Paul Graham and Robert Morris.
  - [Discussion on](https://news.ycombinator.com/item?id=10535364) the Nile programming language developed by Ian Piumarta, Alan Kay, et al.
    - Especially the low-level [Maru](https://www.piumarta.com/software/maru/) language by Ian Piumarta seems interesting.
      - *Maru is a symbolic expression evaluator that can compile its own implementation language.*
      - It compiles s-expressions to IA32 machine code, and has a metacircular evaluator implemented in less than 2k SLOC. It bootstraps from C.

- [LtU: Why is there no widely accepted progress for 50 years?](http://lambda-the-ultimate.org/node/5590)
  - Discussion on how programming languages *have* improved.
  - Contains interesting viewpoints, such as dmbarbour's suggestion that much of modern hardware is essentially "compiled" from a hardware description language such as VHDL.


# Python-related FP resources

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
