**Navigation**

- [README](../README.md)
- [Pure-Python feature set](features.md)
- [Syntactic macro feature set](macros.md)
- [Examples of creating dialects using `mcpyrate`](dialects.md)
- [REPL server](repl.md)
- [Troubleshooting](troubleshooting.md)
- [Design notes](design-notes.md)
- **Essays**
- [Additional reading](readings.md)
- [Contribution guidelines](../CONTRIBUTING.md)

<!-- markdown-toc start - Don't edit this section. Run M-x markdown-toc-refresh-toc -->
**Table of Contents**

- [What Belongs in Python?](#what-belongs-in-python)
- [`hoon`: The C of Functional Programming](#hoon-the-c-of-functional-programming)
- [Common Lisp, Python, and productivity](#common-lisp-python-and-productivity)

<!-- markdown-toc end -->


# What Belongs in Python?

You may feel that [my hovercraft is full of eels](http://stupidpythonideas.blogspot.com/2015/05/spam-spam-spam-gouda-spam-and-tulips.html). It is because they come with the territory.

Some have expressed the opinion [the statement-vs-expression dichotomy is a feature](http://stupidpythonideas.blogspot.com/2015/01/statements-and-expressions.html). The BDFL himself has famously stated that TCO has no place in Python [[1]](http://neopythonic.blogspot.com/2009/04/tail-recursion-elimination.html) [[2]](http://neopythonic.blogspot.fi/2009/04/final-words-on-tail-calls.html), and less famously that multi-expression lambdas or continuations have no place in Python [[3]](https://www.artima.com/weblogs/viewpost.jsp?thread=147358). Several potentially interesting PEPs have been deferred [[1]](https://www.python.org/dev/peps/pep-3150/) [[2]](https://www.python.org/dev/peps/pep-0403/) or rejected [[3]](https://www.python.org/dev/peps/pep-0511/) [[4]](https://www.python.org/dev/peps/pep-0463/) [[5]](https://www.python.org/dev/peps/pep-0472/).

In general, I like Python. My hat is off to the devs. It is no mean feat to create a high-level language that focuses on readability and approachability, keep it alive for 30 years and counting, and have a large part of the programming community adopt it. But regarding the particular points above, if I agreed, I would not have built `unpythonic`, or [`mcpyrate`](https://github.com/Technologicat/mcpyrate) either.

I think that with macros, Python can be so much more than just a beginner's language. Language-level extensibility is just the logical endpoint of that. I do not share the sentiment of the Python community against metaprogramming, or toward some language-level features. For me, macros (and full-module transforms a.k.a. dialects) are just another tool for creating abstractions, at yet another level. We can already extract procedures, methods, and classes. Why limit that ability - namely, the ability to create abstractions - to what an [eager](https://en.wikipedia.org/wiki/Evaluation_strategy#Strict_evaluation) language can express at run time?

If the point is to keep code understandable, I respect the goal; but that is a matter of education. It is perfectly possible to write unreadable code without macros, and in Python, no less. Just use a complex class hierarchy so that the programmer reading the code must hunt through everything to find each method definition; write big functions without abstracting the steps of the overall algorithm; keep lots of mutable state, and store it in top-level variables; and maybe top that off with an overuse of dependency injection. No one will be able to figure out how the program works, at least not in any reasonable amount of time.

It is also perfectly possible to write readable code with macros. Just keep in mind that macros are a different kind of abstraction, and use them where that kind of abstraction lends itself to building a clean solution. I am willing to admit the technical objection that *macros do not compose*; but that does not make them useless.

Of the particular points above, in my opinion TCO should at least be an option. I like that *by default*, Python will complain about a call stack overflow rather than hang, when entering an accidentally infinite mutual recursion. I do occasionally make such mistakes when developing complex algorithms - especially when quickly sketching out new ideas. But sometimes, it would be nice to enable TCO selectively. If you ask for it, you know what to expect. This is precisely why `unpythonic.syntax` has `with tco`. I am not very happy with a custom TCO layer on top of a language core that eschews the whole idea, because TCO support in the core (like Scheme and Racket have) would simplify the implementation of certain other language extensions; but then again, [this is exactly what Clojure did](https://clojuredocs.org/clojure.core/trampoline), in similar technical circumstances.

As for a multi-expression `lambda`, on the surface it sounds like a good idea. But really the issue is that in Python, the `lambda` construct itself is broken. It is essentially a duplicate of `def`, but lacking some features. As of Python 3.8, the latest addition of insult to injury is the lack of support for type annotations. A more uniform solution would be to make `def` into an expression. Much of the time, anonymous functions are not a good idea, because names help understanding and debugging - especially when all you have is a traceback. But defining closures inline **is** a great idea - and sometimes, the most readily understandable presentation order for an algorithm requires to do that in an expression position. The convenience is similar to being able to nest `def` statements, an ability Python already has.

The macros in `unpythonic.syntax` inject many lambdas, because that makes them much simpler to implement than if we had to always lift a `def` statement into the nearest enclosing statement context. Another case in point is [`pampy`](https://github.com/santinic/pampy). The code to perform a pattern match would read a lot nicer if one could define also slightly more complex actions inline (see [Racket's pattern matcher](https://docs.racket-lang.org/reference/match.html) for a comparison). It is unlikely that the action functions will be needed elsewhere, and it is just silly to define a bunch of functions *before* the call to `match`. If this is not a job for either something like `let-where` (to invert the presentation order locally) or a multi-expression lambda (to define the actions inline), I do not know what is.

While on the topic of usability, why are lambdas strictly anonymous? In cases where it is useful to be able to omit a name, because sometimes many small helper functions may be needed and [naming is hard](https://martinfowler.com/bliki/TwoHardThings.html), why not include the source location information in the auto-generated name, instead of just `"<lambda>"`? (As of v0.15.0, the `with namedlambda` macro does this.)

On a point raised [here by the BDFL](https://www.artima.com/weblogs/viewpost.jsp?thread=147358), with respect to indentation-sensitive vs. indentation-insensitive parser modes; having seen [SRFI-110: Sweet-expressions (t-expressions)](https://srfi.schemers.org/srfi-110/srfi-110.html), I think Python is confusing matters by linking the parser mode to statements vs. expressions. A workable solution is to make *everything* support both modes (or even preprocess the source code text to use only one of the modes), which *uniformly* makes parentheses an alternative syntax for grouping.

It would be nice to be able to use indentation to structure expressions to improve their readability, like one can do in Racket with [sweet](https://docs.racket-lang.org/sweet/), but I suppose ``lambda x: [expr0, expr1, ...]`` will have to do for a multi-expression lambda. Unless I decide at some point to make a source filter for [`mcpyrate`](https://github.com/Technologicat/mcpyrate) to auto-convert between indentation and parentheses; but for Python this is somewhat difficult to do, because statements **must** use indentation whereas expressions **must** use parentheses, and this must be done before we can invoke the standard parser to produce an AST. (And I do not want to maintain a [Pyparsing](https://github.com/pyparsing/pyparsing) grammar to parse a modified version of Python.)

As for true multi-shot continuations, `unpythonic.syntax` has `with continuations` for that, but I am not sure if I will ever use it in production code. Most of the time, it seems to me full continuations are a solution looking for a problem. (A very elegant solution, even if the usability of the `call/cc` interface leaves much to be desired.) For everyday use, one-shot continuations (a.k.a. resumable functions, a.k.a. generators in Python) are often all that is needed to simplify certain patterns, especially those involving backtracking. I am a big fan of the idea that, for example, you can make your anagram-making algorithm only yield valid anagrams, with the backtracking state (to eliminate dead-ends) implicitly stored in the paused generator! However, having multi-shot continuations is great for teaching the concept of continuations in a programming course, when teaching in Python.

Finally, there is the issue of implicitly encouraging subtly incompatible Python-like languages (see the rejected [PEP 511](https://www.python.org/dev/peps/pep-0511/)). It is pretty much the point of language-level extensibility, to allow users to do that if they want. I would not worry about it. Racket is *designed* for extensibility, and its community seems to be doing just fine - they even *encourage* the creation of new languages to solve problems. On the other hand, Racket demands some sophistication on the part of its user, and it is not very popular in the programming community at large.

What I can say is, `unpythonic` is not meant for the average Python project, either. If used intelligently, it can make code shorter, yet readable. For a lone developer who needs to achieve as much as possible in the fewest lines reasonably possible, it seems to me that language extension - and in general, as Alexis King put it, [climbing the infinite ladder of abstraction](https://lexi-lambda.github.io/blog/2016/08/11/climbing-the-infinite-ladder-of-abstraction/) - is the way to go. In a large project with a high developer turnover, the situation is different.

For general programming in the early 2020s, Python still has the ecosystem advantage, so it does not make sense to move to anything else, at least yet. So, let us empower what we have. Even if we have to build something that could be considered *unpythonic*.


# `hoon`: The C of Functional Programming

Some days I wonder if this `unpythonic` endeavor even makes any sense. Then, turning the pages of the [book of sand](https://en.wikipedia.org/wiki/The_Book_of_Sand) that is the web, I [happen to run into something](http://axisofeval.blogspot.com/2015/07/what-i-learned-about-urbit-so-far.html) like `hoon`.

Its philosophy is best described by this gem from an [early version of its documentation](https://github.com/cgyarvin/urbit/blob/master/doc/book/0-intro.markdown#hoon):

*So we could describe Hoon as a pure, strict, higher-order typed functional language. But don't do this in front of a Haskell purist, unless you put quotes around "typed," "functional," and possibly even "language." We could also say "object-oriented," with the same scare quotes for the cult of Eiffel.*

While I am not sure if I will ever *use* `hoon`, it is hard not to like a language that puts quotes around "language". Few languages go that far in shaking up preconceptions. Critically examining what we believe, and why, often leads to useful insights.

The claim that `hoon` is not a language, but a "language", fully makes sense after reading some of the documentation. `hoon` is essentially an *ab initio* language with an axiomatic approach to defining its operational semantics, similarly to how *Arc* approaches defining Lisp. Furthermore, `hoon` is the *functional equivalent of C* to the underlying virtual assembly language, `nock`. From a certain viewpoint, the "language" essentially consists of *glorified Nock macros*. Glorified assembly macros are pretty much all a *low-level* [HLL](https://en.wikipedia.org/wiki/High-level_programming_language) essentially is, so the claim seems about right.

Nock is a peculiar assembly language. According to the comments in [`hoon.hoon`](https://github.com/cgyarvin/urbit/blob/master/urb/zod/arvo/hoon.hoon), it is a *Turing-complete non-lambda automaton*. The instruction set is permanently frozen, as if it was a physical CPU chip. Opcodes are just natural numbers, 0 through 11, and it is very minimalistic. For example, there is not even a decrement opcode. This is because from an axiomatic viewpoint, decrement can be defined recursively via increment. At which point, every systems programmer objects, rightfully, that no one sane actually does so, because that costs `O(n)`. Indeed, the `hoon` standard library uses C FFI to take advantage of the physical processor's instruction set to perform arithmetic operations. Each piece of C code used for such acceleration purposes is termed a *jet*.

Since - by the fact that the programmer called a particular standard library function - the system knows we want to compute a decrement (or a multiplication, a power, maybe some floating point operation, etc.), it can *accelerate* that particular operation by using the available hardware.

The important point is, you *could* write out a `nock` macro that does the same thing, only it would be unbearably slow. In the axiomatic perspective - which is about proving programs correct - speed does not matter. At the same time, FFI gives speed for the real world.

To summarize; as someone already put it, `hoon` offers a glimpse into an alternate universe of systems programming, where the functional camp won. It may also be a useful tool, or a source for further unconventional ideas - but to know for sure, I will have to read more about it.

I think the perfect place to end this piece is to quote a few lines from the language definition [`hoon.hoon`](https://github.com/cgyarvin/urbit/blob/master/urb/zod/arvo/hoon.hoon), to give a flavor:

```
++  doos                                              ::  sleep until
  |=  hap=path  ^-  (unit ,@da)
  (doze:(wink:(vent bud (dink (dint hap))) now 0 (beck ~)) now [hap ~])
::
++  hurl                                              ::  start loop no id
  |=  ovo=ovum
  ^-  [p=(list ovum) q=(list ,[p=@tas q=vase])]
  (kick [[~ [[(dint p.ovo) ~] p.ovo ~] q.ovo] ~])
::
++  hymn                                              ::  start loop with id
  |=  [who=ship ovo=ovum]
  ^-  [p=(list ovum) q=(list ,[p=@tas q=vase])]
  (kick [[[~ %iron who] [[(dint p.ovo) ~] p.ovo ~] q.ovo] ~])
::
++  kick                                              ::  complete loop
  |=  mor=(list move)
  =|  ova=(list ovum)
  |-  ^-  [p=(list ovum) q=(list ,[p=@tas q=vase])]
  ?~  mor
    [(flop ova) fan]
  ::  ~&  [%kick-move q.i.mor -.r.i.mor]
  ?>  ?=(^ q.i.mor)
  ?~  t.q.i.mor
    $(mor t.mor, ova [[i.q.i.mor r.i.mor] ova])
  ?>  ?=(^ i.q.i.mor)
  =-  $(mor (weld p.nyx t.mor), fan q.nyx)
  ^=  nyx
  =+  naf=fan
  |-  ^-  [p=(list move) q=_fan]
  ?~  naf  [~ ~]
  ?.  =(i.i.q.i.mor p.i.naf)
    =+  tuh=$(naf t.naf)
    [p.tuh [i.naf q.tuh]]
  =+  ven=(vent bud q.i.naf)
  =+  win=(wink:ven now (shax now) (beck p.i.mor))
  =+  ^=  yub
      %-  beat:win
      [p.i.mor t.i.q.i.mor t.q.i.mor r.i.mor]
  [p.yub [[p.i.naf ves:q.yub] t.naf]]
--
```

The Lisp family (particularly the Common Lisp branch) has a reputation for silly terminology, but I think `hoon` deserves the crown. All control structures are punctuation-only ASCII digraphs, and almost every name is a monosyllabic nonsense word. Still, this Lewis-Carroll-esque naming convention of making words mean what you define them to mean makes at least as much sense as the standard naming convention in mathematics, naming theorems after their discoverers! (Or at least, [after someone else](https://en.wikipedia.org/wiki/Stigler's_law_of_eponymy).)

I actually like the phonetic base, making numbers sound like [*sorreg-namtyv*](https://urbit.org/docs/hoon/hoon-school/nouns/); that is 5 702 400 for the rest of us. And I think I will, quite seriously, adopt the verb *bunt*, meaning *to take the default value of*. That is such a common operation in programming that I find it hard to believe there is no standard abbreviation. I wonder what other discoveries await.

Finally, in some way I cannot quite put a finger on, to me the style has echoes of [Jorge Luis Borges](https://en.wikipedia.org/wiki/Jorge_Luis_Borges). I can imagine `hoon` as the *official* programming language of *[Tlön](https://en.wikipedia.org/wiki/Tl%C3%B6n%2C_Uqbar%2C_Orbis_Tertius)*.

So maybe there is a place for `unpythonic`, too.


**Links**

- [Latest documentation for `hoon`](https://urbit.org/docs/hoon/)
- There is a [whole operating system](https://github.com/urbit/urbit) built on `hoon` and `nock`.
- [Wikipedia has an entry on it](https://en.wikipedia.org/wiki/Urbit). Deconstructing the client-server model sounds very [postmodern](https://en.wikipedia.org/wiki/Deconstructivism).


**Note on natural-number opcodes**

Using natural numbers for the opcodes at first glance sounds like a [Gödel numbering](https://en.wikipedia.org/wiki/G%C3%B6del_numbering) for the program space; but actually, the input to [the VM](https://urbit.org/docs/nock/definition/) contains some linked-list structure, which is not represented that way. Also, **any** programming language imposes its own Gödel numbering on the program space. Just take, for example, the UTF-8 representation of the source code text (which, in Python terms, is a `bytes` object), and interpret those bytes as one single bignum.

Obviously, any interesting programs correspond to very large numbers, and are few and far between, so decoding random numbers via a Gödel numbering is not a practical way to generate interesting programs. [Genetic programming](https://en.wikipedia.org/wiki/Genetic_programming) works much better, because unlike Gödel numbering, it was actually designed specifically to do that. GP takes advantage of the semantic structure present in the source code (or AST) representation.

The purpose of the original Gödel numbering was to prove Gödel's incompleteness theorem. In the case of `nock`, my impression is that the opcodes are natural numbers just for flavoring purposes. If you are building an ab initio software stack, what better way to announce that than to use natural numbers as your virtual machine's opcodes?


# Common Lisp, Python, and productivity

The various essays Paul Graham wrote near the turn of the millennium, especially [Revenge of the Nerds (2002)](http://paulgraham.com/icad.html), have given the initial impulse to many programmers for studying Lisp. The essays are well written and have provided a lot of exposure for the Lisp family of languages. So how does the programming world look in that light now, 20 years later?

The base abstraction level of programming languages, even those in popular use, has increased. The trend was visible already then, and was indeed noted in the essays. The focus on low-level languages such as C++ has decreased. Java is still popular, but high-level FP languages that compile to JVM bytecode (Kotlin, Scala, Clojure) are rising.

Python has become highly popular, and is now also closer to Lisp than it was 20 years ago, especially after `MacroPy` introduced syntactic macros to Python (in 2013, [according to the git log](https://github.com/lihaoyi/macropy/commits/python2/macropy/__init__.py)). Python was not bad as a Lisp replacement even back in 2000 - see Peter Norvig's essay [Python for Lisp Programmers](https://norvig.com/python-lisp.html). Some more historical background, specifically on lexically scoped closures (and the initial lack thereof), can be found in [PEP 3104](https://www.python.org/dev/peps/pep-3104/), [PEP 227](https://www.python.org/dev/peps/pep-0227/), and [Historical problems with closures in JavaScript and Python](http://giocc.com/problems-with-closures-in-javascript-and-python.html).

In 2020, does it still make sense to learn [the legendary](https://xkcd.com/297/) Common Lisp?

As a practical tool? Is CL hands-down better than Python? Maybe no. Python has already delivered on 90% of the productivity promise of Lisp. Both languages cut down significantly on [accidental complexity](https://en.wikipedia.org/wiki/No_Silver_Bullet). Python has a huge library ecosystem. [`mcpyrate`](https://github.com/Technologicat/mcpyrate) and `unpythonic` are trying to push the language-level features a further 5%. (A full 100% is likely impossible when extending an existing language; if nothing else, there will be seams.)

As for productivity, [it may be](https://medium.com/smalltalk-talk/lisp-smalltalk-and-the-power-of-symmetry-8bd96aaa0c0c) that a form of code-data equivalence (symmetry!), not macros specifically, is what makes Lisp powerful. If so, there may be other ways to reach that equivalence. For example Smalltalk, like Lisp, *runs in the same context it's written in*. All Smalltalk data are programs. Smalltalk [may be making a comeback](https://hackernoon.com/how-to-evangelize-a-programming-language-0p7p3y02), in the form of [Pharo](https://pharo.org/).

Haskell aims at code-data equivalence from a third angle (memoized pure functions are in essence infinite lookup tables), but I have not used it in practice, so I do not have the experience to say whether this is enough to make it feel powerful in a similar way.

Image-based programming (live programming) is a common factor between Pharo and Common Lisp + Swank. This is another productivity booster that much of the programming world is not that familiar with. It eliminates not only the edit/compile/restart cycle, but the edit/restart cycle as well, making the workflow a concurrent *edit/run* instead - without restarting the whole app at each change. Julia has [Revise.jl](https://github.com/timholy/Revise.jl) for something similar. In web applications, [REST](https://en.wikipedia.org/wiki/Representational_state_transfer) is a small step in a somewhat similar direction (as long as one can restart the server app easily, to make it use the latest definitions).

But to know exactly what Common Lisp has to offer, **yes**, it does make sense to learn it. As baroque as some parts are, there are a lot of great ideas there. [Conditions](http://www.gigamonkeys.com/book/beyond-exception-handling-conditions-and-restarts.html) are one. [CLOS](http://www.gigamonkeys.com/book/object-reorientation-generic-functions.html) is another. (Nowadays [Julia](https://docs.julialang.org/en/v1/manual/methods/) has CLOS-style [multiple-dispatch generic functions](https://docs.julialang.org/en/v1/manual/methods/).) More widely, in the ecosystem, Swank is one.

Having more perspectives at one's disposal makes one a better programmer - and that is what ultimately counts. As [Alan Perlis said in 1982](https://en.wikiquote.org/wiki/Alan_Perlis):

*A language that doesn't affect the way you think about programming, is not worth knowing.*

In this sense, Common Lisp is very much worth knowing. Although, if you want a beautiful, advanced Lisp, maybe go for [Racket](https://racket-lang.org/) first; but that is an essay for another day. 
