**0.14.2** (in progress; updated 13 Nov 2019) - *"Greenspun" [edition](https://en.wikipedia.org/wiki/Greenspun%27s_tenth_rule)*:

I think that with the arrival of [conditions and restarts](http://www.gigamonkeys.com/book/beyond-exception-handling-conditions-and-restarts.html), it is now fair to say `unpythonic` contains an ad-hoc, informally-specified, slow implementation of half of Common Lisp. To avoid *bug-ridden*, we have tests - but it's not entirely impossible for some to have slipped through.

This release welcomes the first external contribution. Thanks to @aisha-w for the much improved organization and presentation of the documentation!

**Language version**:

Rumors of the demise of Python 3.4 support are exaggerated. While the testing of `unpythonic` has moved to 3.6, there neither is nor will there be any active effort to intentionally drop 3.4 support until `unpythonic` reaches 0.15.0.

That is, support for 3.4 will likely be dropped with the arrival of the next batch of breaking changes. The current plan is visible in the roadmap [as the 0.15.0 milestone](https://github.com/Technologicat/unpythonic/milestone/1).

If you still use 3.4 and find something in `unpythonic` doesn't work there, please file an issue.

**New**:

- Improve organization and presentation of documentation (#28).
- Macro README: Emacs syntax highlighting for `unpythonic.syntax` and MacroPy.
- `fix`: Break infinite recursion cycles (for pure functions). Drawing inspiration from original implementations by [Matthew Might](http://matt.might.net/articles/parsing-with-derivatives/) and [Per Vognsen](https://gist.github.com/pervognsen/8dafe21038f3b513693e).
- *Resumable exceptions*, a.k.a. conditions and restarts. One of the famous killer features of Common Lisp. Drawing inspiration from [python-cl-conditions](https://github.com/svetlyak40wt/python-cl-conditions/) by Alexander Artemenko. See `with restarts` (`RESTART-CASE`), `with handlers` (`HANDLER-BIND`), `signal`, `invoke_restart`. Many convenience forms are also exported; see `unpythonic.conditions` for a full list. For an introduction to conditions, see [Chapter 19 in Practical Common Lisp by Peter Seibel](http://www.gigamonkeys.com/book/beyond-exception-handling-conditions-and-restarts.html).
- More batteries for itertools:
  - `fixpoint`: Arithmetic fixed-point finder (not to be confused with `fix`).
  - `within`: Yield items from iterable until successive iterates are close enough (useful with [Cauchy sequences](https://en.wikipedia.org/wiki/Cauchy_sequence)).
  - `chunked`: Split an iterable into constant-length chunks.
  - `lastn`: Yield the last `n` items from an iterable.
  - `pad`: Extend iterable to length `n` with a `fillvalue`.
  - `interleave`: For example, `interleave(['a', 'b', 'c'], ['+', '*']) --> ['a', '+', 'b', '*', 'c']`. Interleave items from several iterables, slightly differently from `zip`.
  - `find`: From an iterable, get the first item matching a given predicate. Convenience function.
  - `powerset`: Compute the power set (set of all subsets) of an iterable. Works also for infinite iterables.
  - `CountingIterator`: Count how many items have been yielded, as a side effect.
  - `slurp`: Extract all items from a `queue.Queue` (until it is empty) into a list, returning that list.
  - `map`: Curry-friendly thin wrapper for the builtin `map`, making it mandatory to specify at least one iterable.
- `ulp`: Given a float `x`, return the value of the unit in the last place (the "least significant bit"). At `x = 1.0`, this is the [machine epsilon](https://en.wikipedia.org/wiki/Machine_epsilon), by definition of the machine epsilon.
- `dyn` now supports rebinding, using the assignment syntax `dyn.x = 42`. For an atomic mass update, see `dyn.update`.
- `box` now supports `.set(newvalue)` to rebind (returns the new value as a convenience), and `unbox(b)` to extract contents. Syntactic sugar for rebinding is `b << newvalue` (where `b` is a box).
- `islice` now supports negative start and stop. (**Caution**: no negative step; and it must consume the whole iterable to determine where it ends, if at all.)

**Non-breaking changes**:

- `setescape`/`escape` have been renamed `catch`/`throw`, to match the standard terminology in the Lisp family. **The old nonstandard names are now deprecated, and will be removed in 0.15.0.**
- Move macro documentation to `doc/macros.md`. (Was `macro_extras/README.md`.)

**Fixed**:

- Fix initialization crash in `lazyutil` if MacroPy is not installed.
- Fix bug in `identity` and `const` with zero args (#7).
- Use standard Python semantics for negative indices (#6).
- Escape continuation analysis in `unpythonic.syntax.util` now interprets also the literal name `throw` as invoking an escape continuation.

---

**0.14.1** 9 June 2019 - *Retrofuturistic edition*:

**Language version**:

- Support Python 3.6. First released in 2016, supported until 2021, most distros should have it by now.
- This will be the final release that supports Python 3.4; upstream support for 3.4 ended in March 2019.

**New**:

- ``Popper``, a pop-while iterator.
- ``window``, a length-n sliding window iterator for general iterables.
- ``autoref[]`` can now be nested.
- ``dbg[]`` now supports also an expression variant, customizable by lexically assigning ``dbgprint_expr``. See the README on macros for details.

**Bugfixes**:

- Fix crash when SymPy or mpmath are not installed.
- ``mogrify`` is now part of the public API, as it should have been all along.
- Docs: Mention the ``mg`` function in the README.

**Non-breaking changes**:

- Future-proof ``namelambda`` for Python 3.8.
- Docs: ``dbg[]`` is now listed as a convenience feature in the README.

---

**0.14.0** 18 March 2019 - "Dotting the t's and crossing the i's" edition:

**Bugfixes**:

 - ``setup.py``: macros are not zip safe, because ``ZipImporter`` fails to return source code for the module and MacroPy needs that.
 - fix splicing in the ``do[]`` macro; ``ExpandedDoView`` should now work correctly
 - fix lambda handling in the ``lazify`` macro
 - fix ``dict_items`` handling in ``mogrify`` (fixes the use of the ``curry`` macro with code using ``frozendict``)

**New**:

 - ``roview``: a read-only view into a sequence. Behaves mostly the same as ``view``, but has no ``__setitem__`` or ``reverse``.
 - ``mg``: a decorator to mathify a gfunc, so that it will ``m()`` the generator instances it makes.
 - The ``do[]`` macro now supports ``delete[name]`` to delete a local variable previously created in the same do-expression using ``local[name << value]``.
 - ``envify`` block macro, to make formal parameters live in an unpythonic ``env``.
 - ``autoref`` block macro, to implicitly reference attributes of an object (for reading only).

**Breaking changes**:

 - The ``macropy3`` bootstrapper now takes the ``-m`` option; ``macropy3 -m somemod``, like ``python3 -m somemod``. The alternative is to specify a filename positionally; ``macropy3 somescript.py``, like ``python3 somescript.py``. In either case, the bootstrapper will import the module in a special mode that pretends its ``__name__ == '__main__'``, to allow using the pythonic conditional main idiom also in macro-enabled code.
 - The constructor of the writable ``view`` now checks that the input is not read-only (``roview``, or a ``Sequence`` that is not also a ``MutableSequence``) before allowing creation of the writable view.
 - ``env`` now checks finalization status also when deleting attrs (a finalized ``env`` cannot add or delete bindings)

**Non-breaking improvements**:

 - ``env`` now provides also the ``collections.abc.MutableMapping`` API.
 - The ``tco`` macro now skips nested ``continuations`` blocks (to allow [Lispython](https://github.com/Technologicat/pydialect/tree/master/lispython) in [Pydialect](https://github.com/Technologicat/pydialect) to support ``continuations``).
 - ``setup.py`` now installs the ``macropy3`` bootstrapper.

---

**0.13.1** 1 March 2019 - "Maybe a slice?" [edition](https://en.wikipedia.org/wiki/Everybody%27s_Golf_4)

**New**:

 - `view`: writable, sliceable view into a sequence. Use like `view(lst)[::2]`. Can be nested (i.e. sliced again). Any access (read or write) goes through to the original underlying sequence. Can assign a scalar to a slice à la NumPy. Stores slices, not indices; works also if the length of the underlying sequence suddenly changes.
 - `islice`: slice syntax support for `itertools.islice`, use like `islice(myiterable)[100:10:2]` or `islice(myiterable)[42]`. (It's essentially a curried function, where the second step uses the subscript syntax instead of the function call syntax.)
 - `prod`: like `sum`, but computes the product. A missing battery.
 - `iindex`: like `list.index`, but for iterables. A missing battery. (Makes sense mostly for memoized input.)
 - `inn(x, iterable)`: contains-check (`x in iterable`) for monotonic infinite iterables, with [automatic](http://wiki.c2.com/?LazinessImpatienceHubris) termination.
 - `getattrrec`, `setattrrec` (**rec**ursive): access underlying data in an onion of wrappers.
 - `primes` and `fibonacci` generators, mainly intended for testing and usage examples.
 - ``SequenceView`` and ``MutableSequenceView`` abstract base classes; ``view`` is a ``MutableSequenceView``.

**Breaking changes**:

 - The `fup[]` utility macro to functionally update a sequence **is gone and has been replaced** by the `fup` utility function, with slightly changed syntax to accommodate. New syntax is like `fup(lst)[3:17:2] << values`. (This is a two-step curry utilizing the subscript and lshift operators.)
 - `ShadowedSequence`, and hence also `fupdate`, now raise the semantically more appropriate `IndexError` (instead of the previous `ValueError`) if the replacement sequence is too short.
 - `namelambda` now returns a modified copy; the original function object is no longer mutated.

**Non-breaking improvements**:

 - `ShadowedSequence` now supports slicing (read-only), equality comparison, `str` and `repr`. Out-of-range access to a single item emits a meaningful error, like in `list`.
 - `env` and `dyn` now provide the `collections.abc.Mapping` API.
 - `cons` and friends: `BinaryTreeIterator` and `JackOfAllTradesIterator` now support arbitarily deep cons structures.

---

**0.13.0** 25 February 2019 - "I'll evaluate this later" edition:

**New**:

 - ``lazify`` macro: call-by-need for Python (a.k.a. lazy functions, like in Haskell)
 - ``frozendict``: an immutable dictionary
 - ``mogrify``: in-place ``map`` for mutable containers
 - ``timer``: a context manager for performance testing
 - `s`: create lazy mathematical sequences. For example, `s(1, ...)`, `s(1, 2, ...)`, `s(1, 2, 4, ...)` and `s(1, 2, ...)**2` are now valid Python. Regular function, no macros.
 - `m`: endow any iterable with infix math support. (But be aware that after that, applying an operation meant for general iterables drops the math support; to restore it, `m(result)` again.)
 - The ``unpythonic.llist`` module now provides ``JackOfAllTradesIterator`` that understands both trees and linked lists (with some compromises).
 - ``nb`` macro: a silly ultralight math notebook.

**Breaking changes**:

 - ``dyn``: the ``asdict`` and ``items`` methods now return a live view.
 - The mutable single-item container ``Box`` and its data attribute ``value`` have been renamed to ``box`` and ``x``, respectively.
 - ``namedlambda`` macro: Env-assignments are now processed lexically, just like regular assignments. Added support for let-bindings.
 - ``curry`` macro: The special mode for uninspectables is now enabled lexically within the ``with curry`` block. Also, manual uses of the ``curry`` decorator (on both ``def`` and ``lambda``) are now detected, and in such cases the macro now skips adding the ``curry`` decorator.

**Non-breaking improvements**:

 - ``namelambda`` now supports renaming any function object, and also multiple times.
 - The single-item special binding syntax is now supported also by the bindings block of the ``dlet``, ``dletseq``, ``dletrec``, ``blet``, ``bletseq`` and ``bletrec`` macros.

---

**0.12.0** 9 January 2019 - "[Metamagical](https://en.wikipedia.org/wiki/Metamagical_Themas) engineering" edition:

*What does "metamagical" mean? To me, it means "going one level beyond magic". There is an ambiguity here: on the one hand, the word might mean "ultramagical" - magic of a higher order - yet on the other hand, the magical thing about magic is that what lies behind it is always nonmagical. That's metamagic for you!*
  --Douglas R. Hofstadter, *On Self-Referential Sentences* (essay, 1981)

**New**:

 - Alternative, haskelly ``let`` syntax ``let[((x, 2), (y, 3)) in x + y]`` and ``let[x + y, where((x, 2), (y, 3))]``
   - Supported by all ``let`` forms: ``let``, ``letseq``, ``letrec``, ``let_syntax``, ``abbrev``
 - When making just one binding, can now omit outer parentheses in ``let``: ``let(x, 1)[...]``, ``let[(x, 1) in ...]``, ``let[..., where(x, 1)]``
 - ``unpythonic.misc.Box``: the classic rackety single-item mutable container
 - Many small improvements to documentation

**Breaking changes**:

 - New, perhaps more natural ``call_cc[]`` syntax for continuations, replaces earlier ``with bind[...]``
   - Conditional continuation capture with ``call_cc[f() if p else None]``
   - ``cc`` parameter now added implicitly, no need to declare explicitly unless actually needed (reduces visual noise in client code)
 - Local variables in a ``do`` are now declared using macro-expr syntax ``local[x << 42]``, looks more macropythonic
 - Silly ``(lambda)`` suffix removed from names of named lambdas (to detect them in client code, it's enough that ``isinstance(f, types.LambdaType)``)

---

**0.11.1** 22 November 2018 - "Cleaning up, vol. 2" edition:

**Enhancements**:

- Create a proper decorator registry for the syntax machinery.
  - Can now register priorities for custom decorators to tell the syntax system about their correct ordering (for ``sort_lambda_decorators``, ``suggest_decorator_index``).
  - Register priorities for (some of) unpythonic's own decorators using this new system, replacing the old hardcoded decorator registry.
  - Now lives in ``unpythonic.regutil``; used only by the syntax subsystem, but doesn't require MacroPy just to start up.
- Try to determine correct insertion index for ``trampolined`` and ``curry`` decorators in macros that insert them to ``decorator_list`` of ``FunctionDef`` nodes (using any already applied known decorators as placement hints, [like a programmer would](http://wiki.c2.com/?LazinessImpatienceHubris)).
- ``namedlambda``: recognize also decorated lambdas, and calls to ``curry`` where the last argument is a lambda (useful for ``looped_over`` et al.).

**Breaking change**:

- Remove the special jump target ``SELF``.
  - Was always a hack; no longer needed now that v0.11.0 introduced the general solution: the ``withself`` function that allows a lambda to refer to itself anywhere, not just in a ``jump``.
  - Now the whole thing is easier to explain, so likely a better idea ([ZoP](https://www.python.org/dev/peps/pep-0020/) §17, 18).

---

**0.11.0** 15 November 2018 - "Spring cleaning in winter" edition:

New:

- Add @callwith: freeze arguments, choose function later
- Add withself: allow a lambda to refer to itself
- Add let_syntax: splice code at macro expansion time
- Add quicklambda: block macro to combo our blocks with MacroPy's quick_lambda
- Add debug option to MacroPy bootstrapper

Enhancements:

- prefix macro now works together with let and do

Bugfixes:

- detect TCO'd lambdas correctly (no longer confused by intervening FunctionDef nodes with TCO decorators)
- scoping: detect also names bound by For, Import, Try, With

Breaking changes:

- Rename dynscope --> dynassign; technically dynamic assignment, not scoping
- Rename localdef --> local; shorter, more descriptive
- scanr now returns results in the order computed (**CAUTION**: different from Haskell)
- simple_let, simple_letseq --> let, letseq in unpythonic.syntax.simplelet
- cons now prints pythonically by default, to allow eval; use .lispyrepr() to get the old output
- Remove separate dynvar curry_toplevel_passthrough; expose curry_context instead

Other:

- Reorganize source tree, tests now live inside the project
- Pythonize runtests, no more bash script
- Add countlines Python script to estimate project size

---

**0.10.4** 29 October 2018 - "573 combo!" edition[*](http://www.dancedancerevolution.wikia.com/wiki/573):

- new: macro wrappers for the let decorators
- fix: trampolined() should go on the outside even if the client code manually uses curry()
- enh: improve tco, fploop combo
- enh: improve lexical scoping support

---

**0.10.3** 25 October 2018 - "Small fixes" edition:

- enh: ``curry`` macro now curries also definitions (``def``, ``lambda``), not only calls
- fix: spurious recomputation bug in ``do[]``
- update and fix READMEs and docstrings

---

**0.10.2** 24 October 2018 - "Just a few more things" edition:

Bugfixes:

- Arities:
  - Compute arities of methods correctly
  - Workaround for some builtins being uninspectable or reporting incorrect arities
- Macros:
  - An implicit ``curry(f)`` should call ``f`` also if no args
  - Fix missing ``optional_vars`` in manually created ``withitem`` nodes

---

**0.10.1** 23 October 2018 - "Just one more thing" edition:

- ``continuations``: create continuation using same node type (``FunctionDef`` or ``AsyncFunctionDef``) as its parent function
- ``autoreturn``: fix semantics of try block
- fix docstring of tco

---

**0.10.0** 23 October 2018 - "0.10.0 is more than 0.9.∞" edition:

- Add more macros, notably ``continuations``, ``tco``, ``autoreturn``
- Polish macros, especially their interaction
- Remove old exception-based TCO, rename ``fasttco`` to ``tco``

---

**0.9.2** 9 October 2018 - "Through the looking glass" edition:

 - new `multilambda` block macro: supercharge regular Python lambdas, contained lexically inside the block, with support for multiple expressions and local variables. Use brackets to denote a multi-expression body.
 - new `fup` macro providing more natural syntax for functional updates; allows using slice syntax.
 - upgrade: the `let` macros can now optionally have a multi-expression body. To enable, wrap the body in an extra set of brackets.
 - remove the 0.9.0 multilambda `λ`; brittle and was missing features.

The macros implement the multi-expression bodies by inserting a `do`; this introduces an internal-definition context for local variables. See its documentation in the macro_extras README for usage.

The macro_extras README now includes a table of contents for easy browsability.

---

**0.9.0** 5 October 2018 - "Super Syntactic Fortress MACROS" edition:

- **Macros!** New module `unpythonic.syntax`, adding syntactic macros for constructs where this improves usability. See [`macro_extras`](macro_extras/) for documentation.
  - Notable macros include `curry` (automatic currying for Python) and `cond` (multi-branch conditional expression, usable in a lambda), and macro variants of the `let` constructs (no boilerplate).
  - As of this writing, requires the [latest MacroPy3](https://github.com/azazel75/macropy) from git HEAD.
  - Not loaded by default. To use, `from unpythonic.syntax import macros, ...`.
- Include generic MacroPy3 bootstrapper for convenience, to run macro-enabled Python programs.
- Fix bug in let constructs: should require unique names in the same `let`/`letrec`.
- Fix bug in `unpythonic.fun.apply`.

---

**0.8.8** 25 September 2018 - "More spicy" edition:

Changes:

- ``curry``: by default, ``TypeError`` if args remaining when exiting top-level curry context
  - add dynvar ``curry_toplevel_passthrough`` to switch the error off
- ``rotate`` now conceptually shifts the arg slots, not the values; this variant seems easier to reason about.
- accept just tuple (not list) as the pythonic multiple-return-values thing in ``curry``, ``compose``, ``pipe``

New:

- add ``make_dynvar``, to set a default value for a dynamic variable. Eliminates the need for ``if 'x' in dyn`` checks.
- as an optional extra, add a [MacroPy3](https://github.com/azazel75/macropy) based autocurry macro, which automatically curries all function calls that lexically reside in a ``with curry`` block. (Make your Python look somewhat like Haskell.)

Bugfixes/optimizations:

- ``nth``: fix off-by-one bug
- ``dyn``: skip pushing/popping a scope if no bindings given

---

**0.8.7** 24 September 2018 - "More iterable" edition:

Changes:

 - `scanr` now syncs the left ends of multiple inputs, as it should.
 - robustness: add a typecheck to `ShadowedSequence.__init__`
 - rename: for consistency with `rscanl`, `rfoldl`, the new names of *sync right ends of multiple inputs, then map/zip from the right*, are `rmap`, `rzip`.
 - `llist`, `lreverse` are now more ducky/pythonic.

New:

 - add `rscanl`, `rscanl1`, `rfoldl`, `rreducel`: reverse each input, then left-scan/left-fold. This approach syncs the right ends if multiple inputs.
 - add `mapr`, `zipr` (map-then-reverse): sync left ends of multiple inputs, then map/zip from the right.
 - add convenience function `rev`: try `reversed(...)`, if `TypeError` then `reversed(tuple(...))`
 - add `butlast`, `butlastn`, `partition`

---

**0.8.6** 20 September 2018 - "Adding in the missing parts" edition:

New features:

 - add `unfold`, `unfold1`: generate a sequence corecursively
 - add memoization for iterables (`imemoize`, `fimemoize`)

Enhancements:

 - `call` now accepts also args (see docstring)
 - gtco: allow tail-chaining into any iterable
 - document new features in README (also those from 0.8.5)

Bugfixes:

 - fix bugs in gtco
   - strip trampolines correctly in nested generator-TCO chains
   - fix handling of generator return values

---

**0.8.5** 19 September 2018 - "Liberté, égalité, fraternité" edition:

 - add `gtrampolined`: TCO (tail chaining) for generators
 - add `gmemoize`: memoization for generators
 - bring convenience features of `dyn` to parity with `env`

---

**0.8.4** 18 September 2018 - "Hunt for the missing operators" edition:

 - Parameterize scan and fold; can now terminate on longest input
 - Add `map_longest`, `mapr_longest`, `zipr_longest`
 - `unpack` is now curry-friendly

Technical enhancements:

 - refactor `unpythonic.it` to use `itertools` where possible
 - remove unnecessary conversions from iterator to generator

---

**0.8.3** 18 September 2018 - "I have always wanted to code in Listhonkell" edition:

 - Add `scanl`, `scanr`: lazy partial fold (a.k.a. accumulate) that returns a generator yielding intermediate results.
   - Also provided are `scanl1`, `scanr1` variants with one input sequence and optional init.
 - Add `iterate`: return an infinite generator yielding `x`, `f(x)`, `f(f(x))`, ...
   - 1-in-1-out (`iterate1`) and n-in-n-out (`iterate`) variants are provided. The n-in-n-out variant unpacks each result to the argument list of the next call.

For usage examples see `test()` in [it.py](unpythonic/it.py).

---

**0.8.2** 17 September 2018

New features:

 - Add currying compose functions and currying pipe (names suffixed with ``c``)

Enhancements:

 - Improve reversing support in linked lists:
   - Linked lists now support the builtin ``reversed`` (by internally building a reversed copy)
   - ``llist`` just extracts the internal reversed copy when the input is ``reversed(some_ll)``
 - Prevent stacking curried wrappers in ``curry``
 - More logical naming for the ``compose`` variants.
   - The first suffix, if present, is either ``1`` for one-arg variants, or ``c`` for the new currying variants.
   - The ``i`` suffix for iterable input always goes last.

---

**0.8.1** 14 September 2018

New feature:

 - Add a toy nondeterministic evaluator `forall`; see `unpythonic.amb` module

Enhancements:

 - Improve curry; see updated examples in README
 - cons structures are now pickleable
 - `unpythonic.llist` no longer depends on `unpythonic.tco`

---

**0.8.0** 12 September 2018

Features:

 - `unpythonic.it`: batteries for itertools (new)
 - `unpythonic.fun`: batteries for functools (significant changes)
 - m-in-n-out for pipes and function composition (new)
 - `unpythonic.fup`: functionally update sequences and mappings (new)
 - Load `unpythonic.llist` by default (easier, no special cases for the user)

Bugfix:

 - `curry` with passthrough: use up all kwargs at the first step which got too many positional arguments (since no simple reasonable way to decide to which later application they would belong)

---

**0.7.0** 4 September 2018

 - Add batteries for functools: `unpythonic.fun`
 - Add `cons` and friends: `unpythonic.llist` (not loaded by default; depends on `unpythonic.tco`)
 - Bugfix: `rc.py` was missing from the distribution, breaking TCO

---

**0.6.1** 29 August 2018 (hotfix for 0.6.0)

Bugfix:

 - Catch `UnknownArity` in all modules that use `unpythonic.arity.arity_includes()`.

---

**0.6.0** 29 August 2018

New and improved sequencing constructs.

 - Rename the v0.5.1 `do` --> `pipe`
 - Add `piped`, `lazy_piped` for shell-like pipe syntax
 - Add a new `do`: an improved `begin` that can name intermediate results

---

**0.5.1** 13 August 2018

 - Catch more errors in client code:
   - Validate arity of callable value in `letrec` (both versions)
   - Validate callability and arity of body in all `let` constructs
   - In `env`, require name to be an identifier even when subscripting
 - Add flag to `enable_fasttco()` to be able to switch it back off (during the same run of the Python interpreter)
 - Internal enhancement: add unit tests for `env`

---

**0.5.0** 10 August 2018

- Make the TCO implementation switchable at run time, see `enable_fasttco()`.
- Default to the slower exception-based TCO that has easier syntax.

---

**0.4.3** 9 August 2018

- Print a warning for unclaimed TCO jump instances (to help detect bugs in client code)

---

**0.4.2** 6 August 2018 (hotfix for 0.4.1)

- fix install bug

---

**0.4.1** 6 August 2018 (hotfix for 0.4.0)

- Export `unpythonic.misc.pack`
- Update description for PyPI

---

**0.4.0** 6 August 2018

- First version published on PyPI
- Add `@breakably_looped`, `@breakably_looped_over`
- Rename `@immediate` to `@call`; maybe the most descriptive short name given `call/ec` and similar.

---

**0.3.0** 6 August 2018

- refactor looping constructs into `unpythonic.fploop`
- add exception-based alternative TCO implementation
- add `raisef`
- change API of `escape` to perform the `raise` (simplifies trampoline, improves feature orthogonality)

---

**0.2.0** 3 August 2018

- add `@call/ec`
- add `arity` utilities
- rename `@loop` -> `@looped`; now `loop` is the magic first positional parameter for the loop body
- add `@looped_over`
- unify `let` behavior between the two implementations
- make `@trampolined` preserve docstrings
- `@setescape`: parameter should be named `tags` since it accepts a tuple
- improve README

---

**0.1.0** 30 July 2018

Initial release.
