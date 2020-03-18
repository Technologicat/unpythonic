# Links to relevant reading

This document collects links to blog posts, online articles and papers on topics relevant in the context of `unpythonic`.

- [Evelyn Woods, 2017: A comparison of object models of Python, Lua, JavaScript and Perl](https://eev.ee/blog/2017/11/28/object-models/).
  - Useful reading for anyone interested in how the object models differ.
  - It can be argued **Python is actually prototype-based**, like JavaScript.
    - [Prototypes in OOP on Wikipedia](https://en.wikipedia.org/wiki/Prototype-based_programming). Actually a nice summary.
  - See also [prototype.py](https://github.com/airportyh/prototype.py) (unfortunately 2.7; to run it in 3.x, would need at least replacing `new` with the appropriate classes from `types`).

- [William R. Cook, OOPSLA 2009: On Understanding Data Abstraction, Revisited](https://www.cs.utexas.edu/~wcook/Drafts/2009/essay.pdf).
  - This is a nice paper illustrating the difference between *abstract data types* and *objects*.
  - In section 4.3: *"In the 1970s [...] Reynolds noticed that abstract data types facilitate adding new operations, while 'procedural data values' (objects) facilitate adding new representations. Since then, this duality has been independently discovered at least three times [18, 14, 33]."* Then: *"The extensibility problem has been solved in numerous ways, and it still inspires new work on extensibility of data abstractions [48, 15]. Multi-methods are another approach to this problem [11]."*
    - Multi-methods (as in multiple dispatch in CLOS or in Julia) seem nice, in that they don't enfore a particular way to slice the operation/representation matrix. Instead, one fills in individual cells as desired.
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

- [PyPy3](http://pypy.org/), fast, JIT-ing Python 3 that's mostly a drop-in replacement for CPython 3.6. MacroPy works, too.

- [Brython](https://brython.info/): Python 3 in the browser, as a replacement for JavaScript.
  - No separate compile step - the compiler is implemented in JS. Including a script tag of type text/python invokes it.
  - Doesn't have the `ast` module, so no MacroPy.
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
