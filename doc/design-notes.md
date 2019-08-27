# Design Notes

- [On ``let`` and Python](#on-let-and-python)
- [Python is Not a Lisp](#python-is-not-a-lisp)
- [Assignment Syntax](#assignment-syntax)
- [TCO Syntax and Speed](#tco-syntax-and-speed)
- [No Monads?](#wait-no-monads)
- [Further Explanation](#your-hovercraft-is-full-of-eels)

### On ``let`` and Python

Why no `let*`, as a function? In Python, name lookup always occurs at runtime. Python gives us no compile-time guarantees that no binding refers to a later one - in [Racket](http://racket-lang.org/), this guarantee is the main difference between `let*` and `letrec`.

Even Racket's `letrec` processes the bindings sequentially, left-to-right, but *the scoping of the names is mutually recursive*. Hence a binding may contain a lambda that, when eventually called, uses a binding defined further down in the `letrec` form.

In contrast, in a `let*` form, attempting such a definition is *a compile-time error*, because at any point in the sequence of bindings, only names found earlier in the sequence have been bound. See [TRG on `let`](https://docs.racket-lang.org/guide/let.html).

Our `letrec` behaves like `let*` in that if `valexpr` is not a function, it may only refer to bindings above it. But this is only enforced at run time, and we allow mutually recursive function definitions, hence `letrec`.

Note the function versions of our `let` constructs, presented here, are **not** properly lexically scoped; in case of nested ``let`` expressions, one must be explicit about which environment the names come from.

The [macro versions](../macro_extras/) of the `let` constructs **are** lexically scoped. The macros also provide a ``letseq[]`` that, similarly to Racket's ``let*``, gives a compile-time guarantee that no binding refers to a later one.

Inspiration: [[1]](https://nvbn.github.io/2014/09/25/let-statement-in-python/) [[2]](https://stackoverflow.com/questions/12219465/is-there-a-python-equivalent-of-the-haskell-let) [[3]](http://sigusr2.net/more-about-let-in-python.html).

### Python is not a Lisp

The point behind providing `let` and `begin` (and the ``let[]`` and ``do[]`` [macros](macro_extras/)) is to make Python lambdas slightly more useful - which was really the starting point for this whole experiment.

The oft-quoted single-expression limitation of the Python ``lambda`` is ultimately a herring, as this library demonstrates. The real problem is the statement/expression dichotomy. In Python, the looping constructs (`for`, `while`), the full power of `if`, and `return` are statements, so they cannot be used in lambdas. We can work around some of this:

 - The expression form of `if` can be used, but readability suffers if nested. Actually, [`and` and `or` are sufficient for full generality](https://www.ibm.com/developerworks/library/l-prog/), but readability suffers there too. Another possibility is to use MacroPy to define a ``cond`` expression, but it's essentially duplicating a feature the language already almost has. (Our [macros](macro_extras/) do exactly that, providing a ``cond`` expression as a macro.)
 - Functional looping (with TCO, to boot) is possible.
 - ``unpythonic.ec.call_ec`` gives us ``return`` (the ec), and ``unpythonic.misc.raisef`` gives us ``raise``.
 - Exception handling (``try``/``except``/``else``/``finally``) and context management (``with``) are currently **not** available for lambdas, even in ``unpythonic``.

Still, ultimately one must keep in mind that Python is not a Lisp. Not all of Python's standard library is expression-friendly; some standard functions and methods lack return values - even though a call is an expression! For example, `set.add(x)` returns `None`, whereas in an expression context, returning `x` would be much more useful, even though it does have a side effect.

### Assignment syntax

Why the clunky `e.set("foo", newval)` or `e << ("foo", newval)`, which do not directly mention `e.foo`? This is mainly because in Python, the language itself is not customizable. If we could define a new operator `e.foo <op> newval` to transform to `e.set("foo", newval)`, this would be easily solved.

Our [macros](macro_extras/) essentially do exactly this, but by borrowing the ``<<`` operator to provide the syntax ``foo << newval``, because even with MacroPy, it is not possible to define new [BinOp](https://greentreesnakes.readthedocs.io/en/latest/nodes.html#BinOp)s in Python. That would be possible essentially as a *reader macro* (as it's known in the Lisp world), to transform custom BinOps into some syntactically valid Python code before proceeding with the rest of the import machinery, but it seems as of this writing, no one has done this.

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

Our [macros](macro_extras/) provide an easy-to use solution. Just wrap the relevant section of code in a ``with tco:``, to automatically apply TCO to code that looks exactly like standard Python. With the macro, function definitions (also lambdas) and returns are automatically converted. It also knows enough not to add a ``@trampolined`` if you have already declared a ``def`` as ``@looped`` (or any of the other TCO-enabling decorators in ``unpythonic.fploop``).

For other libraries bringing TCO to Python, see:

 - [tco](https://github.com/baruchel/tco) by Thomas Baruchel, based on exceptions.
 - [ActiveState recipe 474088](https://github.com/ActiveState/code/tree/master/recipes/Python/474088_Tail_Call_Optimization_Decorator), based on ``inspect``.
 - ``recur.tco`` in [fn.py](https://github.com/fnpy/fn.py), the original source of the approach used here.
 - [MacroPy](https://github.com/azazel75/macropy) uses an approach similar to ``fn.py``.

### Wait, no monads?

(Beside List inside ``forall``.)

Admittedly unpythonic, but Haskell feature, not Lisp. Besides, already done elsewhere, see [OSlash](https://github.com/dbrattli/OSlash) if you need them.

If you want to roll your own monads for whatever reason, there's [this silly hack](https://github.com/Technologicat/python-3-scicomp-intro/blob/master/examples/monads.py) that wasn't packaged into this; or just read Stephan Boyer's quick introduction [[part 1]](https://www.stephanboyer.com/post/9/monads-part-1-a-design-pattern) [[part 2]](https://www.stephanboyer.com/post/10/monads-part-2-impure-computations) [[super quick intro]](https://www.stephanboyer.com/post/83/super-quick-intro-to-monads) and figure it out, it's easy. (Until you get to `State` and `Reader`, where [this](http://brandon.si/code/the-state-monad-a-tutorial-for-the-confused/) and maybe [this](https://gaiustech.wordpress.com/2010/09/06/on-monads/) can be helpful.)

### Your hovercraft is full of eels!

[Naturally](http://stupidpythonideas.blogspot.com/2015/05/spam-spam-spam-gouda-spam-and-tulips.html), they come with the territory.

Some have expressed the opinion [the statement-vs-expression dichotomy is a feature](http://stupidpythonideas.blogspot.com/2015/01/statements-and-expressions.html). The BDFL himself has famously stated that TCO has no place in Python [[1]](http://neopythonic.blogspot.com/2009/04/tail-recursion-elimination.html) [[2]](http://neopythonic.blogspot.fi/2009/04/final-words-on-tail-calls.html), and less famously that multi-expression lambdas or continuations have no place in Python [[3]](https://www.artima.com/weblogs/viewpost.jsp?thread=147358). Several potentially interesting PEPs have been deferred [[1]](https://www.python.org/dev/peps/pep-3150/) [[2]](https://www.python.org/dev/peps/pep-0403/) or rejected [[3]](https://www.python.org/dev/peps/pep-0511/) [[4]](https://www.python.org/dev/peps/pep-0463/) [[5]](https://www.python.org/dev/peps/pep-0472/).

Of course, if I agreed, I wouldn't be doing this (or [this](https://github.com/Technologicat/pydialect)).

On a point raised [here](https://www.artima.com/weblogs/viewpost.jsp?thread=147358) with respect to indentation-sensitive vs. indentation-insensitive parser modes, having seen [sweet expressions](https://srfi.schemers.org/srfi-110/srfi-110.html) I think Python is confusing matters by linking the mode to statements vs. expressions. A workable solution is to make *everything* support both modes (or even preprocess the source code text to use only one of the modes), which *uniformly* makes parentheses an alternative syntax for grouping.

It would be nice to be able to use indentation to structure expressions to improve their readability, like one can do in Racket with [sweet](https://docs.racket-lang.org/sweet/), but I suppose ``lambda x: [expr0, expr1, ...]`` will have to do for a multiple-expression lambda in MacroPy. Unless I decide at some point to make a source filter for [Pydialect](https://github.com/Technologicat/pydialect) to auto-convert between indentation and parentheses; but for Python this is somewhat difficult to do, because statements **must** use indentation whereas expressions **must** use parentheses, and this must be done before we can invoke the standard parser to produce an AST.
