# Examples of creating dialects using `mcpyrate`

What if Python had automatic tail-call optimization, an implicit return statement, and automatically named, multi-expression lambdas? Look no further:

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

# - brackets denote a multiple-expression lambda body
#   (if you want to have one expression that is a literal list,
#    double the brackets: `lambda x: [[5 * x]]`)
# - local[name << value] makes an expression-local variable
lam = lambda x: [local[y << 2 * x],
                 y + 1]
assert lam(10) == 21

t = letrec[((evenp, lambda x: (x == 0) or oddp(x - 1)),
            (oddp, lambda x:(x != 0) and evenp(x - 1))) in
           [local[x << evenp(100)],
            (x, evenp.__name__, oddp.__name__)]]
assert t == (True, "evenp", "oddp")
```

The [dialects subsystem of `mcpyrate`](https://github.com/Technologicat/mcpyrate/blob/master/doc/dialects.md) makes Python into a language platform, à la [Racket](https://racket-lang.org/).
It provides the plumbing that allows to create, in Python, dialects that compile into Python
at import time. It is geared toward creating languages that extend Python
and look almost like Python, but extend or modify its syntax and/or semantics.
Hence *dialects*.

As examples of what can be done with a dialects system together with a kitchen-sink language extension macro package such as `unpythonic`, we currently provide the following dialects:

  - [**Lispython**: The love child of Python and Scheme](dialects/lispython.md)
  - [**Pytkell**: Because it's good to have a kell](dialects/pytkell.md)
  - [**Listhell**: It's not Lisp, it's not Python, it's not Haskell](dialects/listhell.md)

All three dialects support `unpythonic`'s ``continuations`` block macro, to add ``call/cc`` to the language; but it is not enabled automatically.

Mostly, these dialects are intended as a cross between teaching material and a (fully functional!) practical joke, but Lispython may occasionally come in handy.
