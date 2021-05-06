**Navigation**

- [README](../README.md)
- [Pure-Python feature set](features.md)
- [Syntactic macro feature set](macros.md)
- [Examples of creating dialects using `mcpyrate`](dialects.md)
- [REPL server](repl.md)
- **Troubleshooting**
- [Design notes](design-notes.md)
- [Additional reading](readings.md)
- [Contribution guidelines](../CONTRIBUTING.md)

<!-- markdown-toc start - Don't edit this section. Run M-x markdown-toc-refresh-toc -->
**Table of Contents**

- [Troubleshooting](#troubleshooting)
    - [Cannot import the name `macros`?](#cannot-import-the-name-macros)
    - [I'm hacking a macro inside a module in `unpythonic.syntax` and my changes don't take?](#im-hacking-a-macro-inside-a-module-in-unpythonicsyntax-and-my-changes-dont-take)

<!-- markdown-toc end -->

## Troubleshooting

### Cannot import the name `macros`?

Could be a stale bytecode cache that Python thinks is still valid. This can happen especially if you first accidentally run `python3 some_macro_program.py`, and only then realize the invocation should have been `macropython some_macro_program.py`.

The invocation with bare Python may compile to bytecode successfully and write the bytecode cache, but there is indeed no run-time object named `macros`, so the program will crash at that point. When the program is run again via `macropython`, the loader sees the bytecode cache, and because its `mtime` (as compared to the `.py` file) suggests it's up to date, the `.py` file is not automatically recompiled.

Try clearing the bytecode caches in the affected directory with `macropython -c .`; this will force a recompile of the `.py` files the next time they are loaded. Then run normally, with `macropython some_macro_program.py`.


### I'm hacking a macro inside a module in `unpythonic.syntax` and my changes don't take?

As of `mcpyrate` 3.4.0, macro re-exports, as done by `unpythonic.syntax.__init__`, may confuse the macro-dependency analyzer that determines bytecode cache validity. It only looks at the macro-import dependency graph, not the full dependency graph. I might change this in the future, but doing so will make it a lot slower than it needs to be in most circumstances.

Try clearing the bytecode cache in `unpythonic/syntax/`; this will force a recompile.
