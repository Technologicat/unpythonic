**Navigation**

- [README](../README.md)
- [Pure-Python feature set](features.md)
- [Syntactic macro feature set](macros.md)
- **Examples of creating dialects using `mcpyrate`**
  - [Lispython](dialects/lispython.md)
  - [Listhell](dialects/listhell.md)
  - [Pytkell](dialects/pytkell.md)
  - [BF](dialects/bf.md)
- [REPL server](repl.md)
- [Troubleshooting](troubleshooting.md)
- [Design notes](design-notes.md)
- [Essays](essays.md)
- [Additional reading](readings.md)
- [Contribution guidelines](../CONTRIBUTING.md)

<!-- markdown-toc start - Don't edit this section. Run M-x markdown-toc-refresh-toc -->
**Table of Contents**

- [Examples of creating dialects using `mcpyrate`](#examples-of-creating-dialects-using-mcpyrate)

<!-- markdown-toc end -->


# Examples of creating dialects using `mcpyrate`

The [dialects subsystem of `mcpyrate`](https://github.com/Technologicat/mcpyrate/blob/master/doc/dialects.md) makes Python into a language platform, à la [Racket](https://racket-lang.org/).
It provides the plumbing that allows to create, in Python, dialects that compile into Python
at macro expansion time. It is geared toward creating languages that extend Python
and look almost like Python, but extend or modify its syntax and/or semantics.
Hence *dialects*.

As examples of what can be done with a dialects system together with a kitchen-sink language extension macro package such as `unpythonic`, we currently provide the following dialects:

  - [**Lispython**: The love child of Python and Scheme](dialects/lispython.md)
  - [**Listhell**: It's not Lisp, it's not Python, it's not Haskell](dialects/listhell.md)
  - [**Pytkell**: Because it's good to have a kell](dialects/pytkell.md)
  - [**BF**: The classical human-incomprehensible automaton](dialects/bf.md)

Lispython, Listhell, and Pytkell are AST-transforming dialects, built on top of `unpythonic`'s macro layer. All three support `unpythonic`'s `continuations` block macro, to add `call/cc` to the language; but it is not enabled automatically. BF is a source-to-source compiler — the body of a BF file is not parseable as Python — and demonstrates the other half of `mcpyrate`'s dialect system.

Mostly, these dialects are intended as a cross between teaching material and a (fully functional!) practical joke, but Lispython may occasionally come in handy.
