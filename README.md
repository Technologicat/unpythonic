# Unpythonic: `let`, dynamic scoping, and more!

## Tour

```python
from unpythonic import *
```

**TODO**

## Features

**TODO**

## Rationale

**TODO**

### On `let` and Python

Summary

The forms `let` and `letrec` are supported(-ish).

We provide the `begin` and `begin0` sequencing forms, like [Racket](http://racket-lang.org/).

In the basic *parallel binding* `let` form, bindings are independent (do not see each other).

In `letrec`, any binding can refer to any other. However, this implementation of `letrec` is only intended for locally defining mutually recursive functions.

Finally, since we don't depend on MacroPy, we obviously have implemented everything as run-of-the-mill functions, not actual syntactic forms.


Wait, no `let*`?

In Python, name lookup always occurs at runtime. Hence, if we allow using
the environment instance in the RHS of the bindings, that automatically
gives us `letrec`. (Each binding is only looked up when we attempt to use it.)

Also, Python gives us no compile-time guarantees that no binding refers
to a later one - in Racket, this guarantee is the main difference between
`let*` and `letrec`.

Even `letrec` processes the bindings sequentially, left-to-right, but *it makes all the bindings available to all of the bindings*. Hence a binding may
contain a lambda that, when eventually called, uses a binding defined further down in the `letrec` form, and that's ok.

In contrast, in a `let*` form, attempting such a definition *is a compile-time error*, because at any point in the sequence of bindings, only names found
earlier in the sequence have been bound. See [TRG on `let`](https://docs.racket-lang.org/guide/let.html).

This behavior cannot be easily (if at all) supported in Python.


Why does this `letrec` work only with functions?

We abuse kwargs to provide a pythonic assignment syntax for the bindings.

Because Python evaluates kwargs in an arbitrary order, this approach
**cannot** support bare variable definitions that depend on earlier
definitions in the same let* or letrec block - since "earlier" is not defined.

It is possible to nest let forms manually, or to implement a different
(more lispy than pythonic) syntax that enforces a left-to-right ordering.
For the latter, see the following example on SO (it's actually a letrec,
with the syntax reminiscent of Racket and MATLAB):
    https://stackoverflow.com/a/44737147


Why write yet another implementation?

Teaching.

Also, the SO solution linked above is more perlish than pythonic, as it
attempts to DWIM based on the type of the value in each binding. This may fail
if we want attempt to bind a lambda that doesn't need the env. If we accidentally
write  foo=lambda x: ...  instead of  foo=lambda env: lambda x: ...,  we still
have an instance of types.FunctionType, but its API is not what the LET construct
expects.

It's probably hard to do better, while keeping the implementation concise and the
cognitive overhead at the use sites minimal. To anyone with some FP experience,
it's obvious what a let (or a letrec) with a  lambda env: ...  does, but
anything more than that requires reading the docs.

The usability issue - in the Python world, where explicit is considered better
than implicit - is that the operation mode of LET depends on the type of the
value being bound.

A pythonic solution is to support let and letrec, separately - so that we can
explictly mark whether the bindings should have the  lambda env: ...  or not.

As a bonus, we provide decorator versions to allow let-over-defs for named functions.

This gets us 90% there, and is what this implementation is about.


Python is not a Lisp

The ultimate reason behind this module is to make Python lambdas more useful.

Having support for only a single expression is, ultimately, a herring - it can
be fixed with a suitable begin form - or a function to approximate one.
(Besides, multiple expressions in a function are mostly useful with side
effects, which are not very FP; with the possible exception of "define".)

However, in Python, looping constructs, the full power of if, and return
are statements, so they cannot be used in lambdas. The expression form of if
(and "and" and "or") can be used to a limited extent, and functional looping
is possible for short loops - where the lack of tail call elimination does not
yet crash the program - but still, ultimately one must keep in mind that Python
is not a Lisp.

Yet another factor here is that not all of Python's standard library is
expression-friendly. Some standard functions lack return values. For example,
set.add(x) returns None, whereas in an expression context, returning x would be
much more useful. (This can be worked around like the similar situation with
set! in Scheme, using a begin(), hence its inclusion here.)


Inspiration:
    https://nvbn.github.io/2014/09/25/let-statement-in-python/
    https://stackoverflow.com/questions/12219465/is-there-a-python-equivalent-of-the-haskell-let
    http://sigusr2.net/more-about-let-in-python.html


### Wait, no monads?

Already done elsewhere. See PyMonad or OSlash, or if you want to roll your own, [this silly hack](https://github.com/Technologicat/python-3-scicomp-intro/blob/master/examples/monads.py).


### License

BSD.

Dynamic scoping based on [StackOverflow answer by Jason Orendorff (2010)], used under CC-BY-SA.

