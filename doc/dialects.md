**Navigation**

- [README](../README.md)
- [Pure-Python feature set](features.md)
- [Syntactic macro feature set](macros.md)
- **Examples of creating dialects using `mcpyrate`**
  - [Lispython](dialects/lispython.md)
  - [Listhell](dialects/listhell.md)
  - [Pytkell](dialects/pytkell.md)
- [REPL server](repl.md)
- [Troubleshooting](troubleshooting.md)
- [Design notes](design-notes.md)
- [Additional reading](readings.md)
- [Contribution guidelines](../CONTRIBUTING.md)

<!-- markdown-toc start - Don't edit this section. Run M-x markdown-toc-refresh-toc -->
**Table of Contents**

- [Examples of creating dialects using `mcpyrate`](#examples-of-creating-dialects-using-mcpyrate)

<!-- markdown-toc end -->


# Examples of creating dialects using `mcpyrate`

What if Python had automatic tail-call optimization and an implicit return statement? Look no further:

```python
from unpythonic.dialects import dialects, Lispython  # noqa: F401

def factorial(n):
    def f(k, acc):
        if k == 1:
            return acc
        f(k - 1, k * acc)
    f(n, acc=1)
assert factorial(4) == 24
factorial(5000)  # no crash
```

The [dialects subsystem of `mcpyrate`](https://github.com/Technologicat/mcpyrate/blob/master/doc/dialects.md) makes Python into a language platform, à la [Racket](https://racket-lang.org/).
It provides the plumbing that allows to create, in Python, dialects that compile into Python
at macro expansion time. It is geared toward creating languages that extend Python
and look almost like Python, but extend or modify its syntax and/or semantics.
Hence *dialects*.

As examples of what can be done with a dialects system together with a kitchen-sink language extension macro package such as `unpythonic`, we currently provide the following dialects:

  - [**Lispython**: The love child of Python and Scheme](dialects/lispython.md)
  - [**Pytkell**: Because it's good to have a kell](dialects/pytkell.md)
  - [**Listhell**: It's not Lisp, it's not Python, it's not Haskell](dialects/listhell.md)

All three dialects support `unpythonic`'s ``continuations`` block macro, to add ``call/cc`` to the language; but it is not enabled automatically.

Mostly, these dialects are intended as a cross between teaching material and a (fully functional!) practical joke, but Lispython may occasionally come in handy.
