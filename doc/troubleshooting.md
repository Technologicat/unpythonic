**Navigation**

- [README](../README.md)
- [Pure-Python feature set](features.md)
- [Syntactic macro feature set](macros.md)
- [Examples of creating dialects using `mcpyrate`](dialects.md)
- [REPL server](repl.md)
- **Troubleshooting**
- [Design notes](design-notes.md)
- [Essays](essays.md)
- [Additional reading](readings.md)
- [Contribution guidelines](../CONTRIBUTING.md)

<!-- markdown-toc start - Don't edit this section. Run M-x markdown-toc-refresh-toc -->
**Table of Contents**

- [Common issues and questions](#common-issues-and-questions)
    - [Do I need a macro expander to use `unpythonic`?](#do-i-need-a-macro-expander-to-use-unpythonic)
    - [Why `mcpyrate` and not MacroPy?](#why-mcpyrate-and-not-macropy)
    - [Cannot import the name `macros`?](#cannot-import-the-name-macros)
    - [But I did run my program with `macropython`?](#but-i-did-run-my-program-with-macropython)
    - [I'm hacking a macro inside a module in `unpythonic.syntax`, and my changes don't take?](#im-hacking-a-macro-inside-a-module-in-unpythonicsyntax-and-my-changes-dont-take)
    - [Both `unpythonic` and library `x` provide language-extension feature `y`. Which is better?](#both-unpythonic-and-library-x-provide-language-extension-feature-y-which-is-better)
    - [How to list the whole public API, and only the public API?](#how-to-list-the-whole-public-api-and-only-the-public-api)

<!-- markdown-toc end -->

## Common issues and questions

### Do I need a macro expander to use `unpythonic`?

If you intend to only use the [Pure-Python feature set](features.md), then no. This is why `unpythonic` does not automatically pull in a macro expander when you install it.

On the other hand, `unpythonic` is a kitchen-sink language extension, and half of the functionality comes from macros. Even the test framework for `unpythonic`'s own automated tests uses macros!

If you intend to **use** `unpythonic.syntax` or `unpythonic.dialects`, or if you intend to **develop** `unpythonic` (specifically: to be able to run its test suite), then you will need a macro expander.

As of v0.15.0, specifically you will need [`mcpyrate`](https://github.com/Technologicat/mcpyrate).


### Why `mcpyrate` and not MacroPy?

[`mcpyrate`](https://github.com/Technologicat/mcpyrate) is an advanced, third-generation macro expander (and language lab) for Python, taking in the lessons learned from both [`macropy3`](https://github.com/azazel75/macropy) and [`mcpy`](https://github.com/delapuente/mcpy), and expanding (pun not intended) on that.

Beside the advanced features, the reason we use `mcpyrate` is that the `unpythonic.syntax` rabbit hole has become deep enough to benefit from agile experimentation at the meta-metaprogramming level. Allowing the macro expander and the syntax layer of `unpythonic` to co-evolve results in better software.


### Cannot import the name `macros`?

In `mcpyrate`-based programs, there is no run-time object named `macros`, so failing to import that usually means that, for some reason, the macro expander is not enabled.

Macro-enabled, `mcpyrate`-based programs expect to be run with `macropython` (included in the [`mcpyrate` PyPI package](https://pypi.org/project/mcpyrate/)) instead of bare `python3`.

Basically, you can `macropython script.py` or `macropython -m some.module`, like you would with `python3`. The advantage is you can run macro-enabled code without a per-project bootstrapper, since `macropython` handles bootstrapping the macro expander for you.

See the [`macropython` documentation](https://github.com/Technologicat/mcpyrate/blob/master/doc/repl.md#macropython-the-universal-bootstrapper) for details.


### But I did run my program with `macropython`?

The problem could be a stale bytecode cache that `mcpyrate` thinks is still valid. This can happen especially if you first accidentally run `python3 some_macro_program.py`, and only then realize the invocation should have been `macropython some_macro_program.py`.

The invocation with bare Python may compile to bytecode successfully and write the bytecode cache, but there is indeed no run-time object named `macros`, so the program will crash at that point. When the program is run again via `macropython`, `mcpyrate`'s loader sees the existing bytecode cache, and because its `mtime` (as compared to the `.py` file) suggests it's up to date, the `.py` file is not automatically recompiled.

Try clearing the bytecode caches in the affected directory with:
```bash
macropython -c .
```
This will force a recompile of the `.py` files the next time they are loaded. Then run normally, with `macropython some_macro_program.py`.


### I'm hacking a macro inside a module in `unpythonic.syntax`, and my changes don't take?

This is also likely due to a stale bytecode cache. As of `mcpyrate` 3.4.0, macro re-exports, used by `unpythonic.syntax.__init__`, are not seen by the macro-dependency analyzer that determines bytecode cache validity.

The important point to realize here is that as per macropythonic tradition, in `mcpyrate`, a function being a macro is a property of its **use site**, not of its definition site. So how do we re-export a macro? We simply re-export the macro function, like we would do for any other function.

The import to make that re-export happen does not look like a macro-import. This is the right way to do it, since we want to make the object (macro function) available for clients to import, **not** establish bindings in the macro expander *for compiling the module `unpythonic.syntax.__init__` itself*. (The latter is what a macro-import does - it establishes macro bindings *for the module it lexically appears in*.)

The problem is, the macro-dependency analyzer only looks at the macro-import dependency graph, not the full dependency graph, so when analyzing the user program (e.g. a unit test module in `unpythonic.syntax.tests`), it does not scan the re-export that points to the changed macro definition.

I might modify the `mcpyrate` analyzer in the future, but doing so will make the dependency scan a lot slower than it needs to be in most circumstances, because a large majority of imports in Python have nothing to do with macros.

For now, we just note that this issue mainly concerns developers of large macro packages (such as `unpythonic.syntax`) that need to split - for factoring reasons - their macro definitions into separate modules, while presenting all macros to the user in one interface module. This issue does not affect the development of macro-using programs, or any programs where macros are imported from their original definition site (like they always were with MacroPy).

Try clearing the bytecode cache in `unpythonic/`; this will force a recompile.


### Both `unpythonic` and library `x` provide language-extension feature `y`. Which is better?

The point of having these features in `unpythonic` is integration, and a consistent API. So if you need only one specific language-extension feature, then a library that concentrates on that particular feature is likely a good choice. If you need the kitchen sink, too, then it's better to use our implementation, since our implementations of the various features are designed to work together.

In some cases (e.g. the condition system), our implementation may offer extra features not present in the original library that inspired it.

In other cases (e.g. multiple dispatch), the *other* implementation may be better (e.g. runs much faster).


### How to list the whole public API, and only the public API?

In short, use Python's introspection capabilities. There are some subtleties here; below are some ready-made recipes.

To view **the public API of a given submodule**:

```python
import sys
print(sys.modules["unpythonic.collections"].__all__)  # for example
```

If the `__all__` attribute for some submodule is missing, that submodule has no public API.

For most submodules, you could just

```python
print(unpythonic.collections.__all__)  # for example
```

but there are some public API symbols in `unpythonic` that have the same name as a submodule. In these cases, the object overrides the submodule in the top-level namespace of `unpythonic`. So, for example, for `unpythonic.llist`, the second approach fails because `unpythonic.llist` points to a function, not to a module. Therefore, the first approach is preferable, as it always works.

To view **the whole public API**, grouped by submodule:

```python
import sys

import unpythonic

submodules = [name for name in dir(unpythonic)
              if f"unpythonic.{name}" in sys.modules] 

for name in submodules:
    module = sys.modules[f"unpythonic.{name}"]
    if hasattr(module, "__all__"):  # has a public API?
        print("=" * 79)
        print(f"Public API of 'unpythonic.{name}':")
        print(module.__all__)
```

Note that even if you examine the API grouped by submodule, `unpythonic` guarantees all of its public API symbols to be present in the top-level namespace, too, so when you actually import the symbols, you can import them from the top-level namespace. (Actually, the macros expect you to do so, to recognize uses of various `unpythonic` constructs when analyzing code.)

**Do not** do this to retrieve the submodules:

```python
import types
submodules_wrong = [name for name in dir(unpythonic)
                    if issubclass(type(getattr(unpythonic, name)), types.ModuleType)] 
```

for the same reason as above; in this variant, any submodules that have the same name as an object will be missing from the list.

To view **the whole public API** available in the top-level namespace:

```python
import types

import unpythonic

non_module_names = [name for name in dir(unpythonic)
                    if not issubclass(type(getattr(unpythonic, name)), types.ModuleType)]
print(non_module_names)
```

Now be very very careful: for the same reason as above, for the correct semantics we must use `issubclass(..., types.ModuleType)`, not `... in sys.modules`. Here we want to list each symbol in the top-level namespace of `unpythonic` that does not point to a module; **including** any objects that override a module in the top-level namespace.
