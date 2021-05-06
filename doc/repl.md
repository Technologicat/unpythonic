**Navigation**

- [README](../README.md)
- [Pure-Python feature set](features.md)
- [Syntactic macro feature set](macros.md)
- [Examples of creating dialects using `mcpyrate`](dialects.md)
- **REPL server**
- [Troubleshooting](troubleshooting.md)
- [Design notes](design-notes.md)
- [Additional reading](readings.md)
- [Contribution guidelines](../CONTRIBUTING.md)

<!-- markdown-toc start - Don't edit this section. Run M-x markdown-toc-refresh-toc -->
**Table of Contents**

- [The Unpythonic REPL server](#the-unpythonic-repl-server)
    - [Try the server](#try-the-server)
    - [Connect with the client](#connect-with-the-client)
        - [Netcat compatibility](#netcat-compatibility)
    - [Embed the server in your Python app](#embed-the-server-in-your-python-app)
    - [SECURITY WARNING!](#security-warning)
    - [Design for hot-patching](#design-for-hot-patching)
        - [ZODB in 5 minutes](#zodb-in-5-minutes)
    - [Why a custom REPL server/client](#why-a-custom-repl-serverclient)
    - [Future directions](#future-directions)
        - [Authentication and encryption](#authentication-and-encryption)
    - [Note on macro-enabled consoles](#note-on-macro-enabled-consoles)

<!-- markdown-toc end -->

# The Unpythonic REPL server

Hot-patch a running Python process! With **syntactic macros** in the [REPL](https://en.wikipedia.org/wiki/Read%E2%80%93eval%E2%80%93print_loop)!

Inspired by [Swank](https://www.cliki.net/swank) in Common Lisp. Need to fix a space probe in flight? [Hot-patching has you covered](http://www.flownet.com/gat/jpl-lisp.html).

## Try the server

To easily start an instance to play around with:

```python
python3 -m unpythonic.net.server
```

It will bind to `127.0.0.1` on ports `1337` (main channel) and `8128` (control channel). When you want to shut it down, press `Ctrl+C` in the server's terminal window.

Multiple clients may be connected simultaneously to the same server. Each client gets an independent REPL session. The top-level namespace is shared between all sessions.

The actual REPL console you get when you connect to the server depends on what you have installed in the environment where the server is running. The following will be tried in order. The first one that imports successfully wins:
  - If you have [`mcpyrate`](https://github.com/Technologicat/mcpyrate) installed, you will get `mcpyrate.repl.console.MacroConsole`. (Recommended.)
  - Otherwise you will get [`code.InteractiveConsole`](https://docs.python.org/3/library/code.html), and macro support will not be enabled.

**In a REPL session**:

- `print()` works as usual. Stdout is redirected to the client only in the REPL session's main thread.
  - If you must, look at the value of `sys.stdout` (et al.) in the REPL session's main thread. After the REPL server has been started, it's actually an `unpythonic.Shim` that holds the underlying stream in an `unpythonic.ThreadLocalBox`, so you can get the stream from there if you really need to. For any thread that hasn't sent a value into that box, the box will return the default, which is the original stdin/stdout/stderr of the server process.

- `server_print()` prints to the original stdout of the server process. 

- To view docstrings, use `doc(obj)` instead of `help(obj)`.
  - **Do not use** `help(obj)` in the REPL. Trying to do that hangs the client, because `help`'s stdin/stdout are not redirected properly.
  - `doc(obj)` just prints the docstring without paging, while emulating `help`'s dedenting. It's not a perfect solution, but should work well enough to view docstrings of *live objects in a live Python process*.
    - If you want to look at docstrings for definitions currently on disk instead, just use a regular IPython session or similar.
  - `doc(obj)` also works when `obj` is a syntactic macro.
    - For example, `from unpythonic.syntax import macros, let`, and then `doc(let)`.

- For very rudimentary job control (spawn background task, retrieve result later, possibly in another session), see `bg` and `fg`.

**Technical**:

- IPv4 only for now. IPv6 would be nice, but something for a later release.

- Tested only on Linux (with CPython 3.6 and PyPy3).
  - At least the [PTY](https://en.wikipedia.org/wiki/Pseudoterminal) stuff on the server side is *nix-specific.
  - Also, I make no guarantees that [`select.select`](https://docs.python.org/3/library/select.html#select.select) is not called on an fd that is not a socket.
  - Probably possible to make this work in Windows, but I don't need that. PRs are welcome, though.


## Connect with the client

```python
python3 -m unpythonic.net.client 127.0.0.1
```

This connects to the REPL server running on `localhost`, and opens a REPL session, where:

- **Line editing** (GNU `readline`) is available, with history, and *remote tab completion*.
  - When you use tab completion, the client transparently queries for completions from the server.
  - History is currently not saved; it is only available back to the start of the session. For the intended use case this is probably enough.
    - If you need to preserve commands across sessions, maybe store them in a file?
    - If you need to refresh large sections of code, consider hot-patching with the help of `importlib.reload`, instead of pasting new definitions directly into the REPL. It's possible to `importlib.reload(somemodule)` from the REPL.

- Pressing `Ctrl+D` at the prompt politely asks to disconnect. If the server fails to respond for whatever reason, following that with `Ctrl+C` forces a client-side disconnect.

- At any other time, pressing `Ctrl+C` in a REPL session sends a `KeyboardInterrupt` to the remote.
  - This works by injecting a `KeyboardInterrupt` *[asynchronous exception](https://en.wikipedia.org/wiki/Exception_handling#Exception_synchronicity)* into the thread running that particular session. Any other threads in the process running the server are unaffected.
  - That feature is actually documented [in the CPython C API docs](https://docs.python.org/3/c-api/init.html#c.PyThreadState_SetAsyncExc), and is part of the public API. But it's a bit hard to find, and was never intended to be called from Python code, without writing a custom C extension. It just happens that `ctypes.pythonapi` makes that possible. Thanks go to LIU Wei and Federico Ficarelli for the original detective work.
  - Due to technical reasons, remote Ctrl+C currently only works on CPython. Support for PyPy3 would be nice, but currently not possible. See `unpythonic.misc.async_raise` and [#58](https://github.com/Technologicat/unpythonic/issues/58) for details.
  - Be sure to press `Ctrl+C` **just once**. Hammering the key combo may raise a `KeyboardInterrupt` locally in the code that is trying to send the remote `KeyboardInterrupt` (or in code waiting for the server's response), thus forcibly terminating the client. Starting immediately after the server has responded, remote Ctrl+C is available again. (The server indicates this by sending the text `KeyboardInterrupt`, possibly with a stack trace, and then giving a new prompt, just like a standard interactive Python session does.)

### Netcat compatibility

If you don't need tab completion or `Ctrl+C` support, the main channel is also `netcat` compatible. Use `rlwrap` to get basic readline functionality (history):

```bash
rlwrap netcat localhost 1337
```    

The really barebones way, no history:

```bash
netcat localhost 1337
```


## Embed the server in your Python app

```python
from unpythonic.net import server
server.start(locals={})
```

That's all.

- The REPL server is strictly opt-in; it must be imported and started explicitly. There's no way to turn it on in a running process that didn't opt in when it started.

- The `locals` parameter of `start` specifies the top-level namespace of REPL sessions served by the server.
  - If this is one of your modules' `globals()`, you can directly write to that namespace in the REPL simply by assigning to variables. E.g. `x = 42` will actually do `mymod.x = 42`, where `mymod` is the module that called `server.start(locals=globals())`.
  - If you want a namespace that's only accessible from (and shared by) REPL sessions, use an empty dictionary: `server.start(locals={})`.
  - For write access to module-level globals in other modules, access them as module attributes, like in [Manhole](https://github.com/ionelmc/python-manhole/). For example, `sys.modules['myothermod'].x`.

- There's no need to `server.stop()` manually; this is automatically registered as an `atexit` handler.

- **The server runs in the background, in a daemon thread**. By design, it doesn't hijack any existing thread.
  - This does mean that if you shut down your app in any way (or if your app crashes), the server will also shut down immediately. This will forcibly disconnect clients, if any remain.
  - We use threads instead of an asyncio model to let you choose whatever async framework you want for the rest of your app. This is important especially because as of 2020, the game-changer [Trio](https://github.com/python-trio/trio) is a thing, but not yet the de facto standard. Not many simultaneous sessions are needed, so the OS can easily spare the resources to run a classical threaded server.


## SECURITY WARNING!

**A general-purpose REPL server, by its very nature, essentially is an opt-in back door.** While the intended use is to allow you to hot-patch your running app, the server gives access to anything that can be imported, including `os` and `sys`. It is trivial to use it as a shell that just happens to use Python as the command language, or to obtain traditional shell access (e.g. `bash`) via it.

This particular REPL server has no authentication support whatsoever. **The server accepts any incoming connection**, with no way to audit who it is. There is no encryption for network traffic, either.

Note this is exactly the same level of security (i.e. none whatsoever) as provided by the Python REPL itself. If you have access to `python`, you have access to the system, with the privileges the `python` process itself runs under.

**Therefore, to remain secure**:

 - **Only bind the server to the loopback interface**. This is the default. This ensures connections only come from users who can log in to the machine running your app. (Physical local access or an SSH session are both fine.)
 - **Only enable the server if** you trust **any** logged in user to allow them REPL access under **your** credentials. The two most common scenarios are:
   - The app runs on your local machine, where you are the only user, or which otherwise has no untrusted human users.
   - The app runs on a dedicated virtual server, which runs only your app.

In both cases, access control, auditing and encrypted connections (SSH) can then provided by the OS itself.


## Design for hot-patching

**As usual, [the legends](http://www.flownet.com/gat/jpl-lisp.html) are exaggerated.**

Making full use of hot-patching requires foresight, adhering to a particular programming style. Some elements of this style may be considered [antipatterns](https://en.wikipedia.org/wiki/Anti-pattern) in programs that are not designed for hot-patching. An example is to save important data in global variables, so that it can later be accessed from the REPL, instead of keeping as much as possible in the locals of a function. Hot-patching and [FP](https://en.wikipedia.org/wiki/Functional_programming)-ness are opposing goals. For hot-patching (and its cousin, live programming), [*local state is poison*](https://awelonblue.wordpress.com/2012/10/21/local-state-is-poison/).

- **It is possible to reload arbitrary modules.**
  - Just use `importlib.reload`.
  - But if someone has from-imported anything from the module you're reloading, tough luck. The from-import will refer to the old version of the imported object, unless you reload the module that performed the from-import, too. Good luck catching all of them.

- **You can access only things which you can refer to through the top-level namespace.**
  - Keep in mind you can access the top-level namespace of **any** module via `sys.modules`.
  - If the logic you need to hot-patch happens to be inside a closure, tough luck. The only way is then to replace the thing that produces the closures (if that happens to live at the top level), and re-instantiate the closure.
  - So think ahead, and store the things you need to be able to access in a container accessible from the top-level namespace.

- **You may need to `box` a lot more stuff than usual.**
  - Especially things that you provide for other modules to from-import from yours.
  - A module should export a `box` containing the useful thing, not directly the thing itself, since the thing may get replaced later. When a caller indirects via the box, they always get the latest version of the thing.

- **It is impossible to patch a running loop.**
  - Unless it's an FP loop with the body defined as a function at the top level. In this case it's possible to rebind the function name that refers to the loop body.
  - In `unpythonic`, this setup is possible using `@trampolined` (but not `@looped`, because `@looped` overwrites the def'd name with the loop's return value). Define the loop body as a `@trampolined` top-level function, and start the loop by calling this function from wherever you want. Python's dynamic name lookup will then ensure that during each iteration, the latest definition is always used.

- **Even if you replace a class definition, any existing instances will still use the old definition.**
  - Though you could retroactively change its `__class__`. Automating that is exactly what [ActiveState recipe 160164](https://github.com/ActiveState/code/tree/master/recipes/Python/160164_automatically_upgrade_class_instances) is for.

- **There is no way to save a "Python image".**
  - Python wasn't really designed, as a language, for the style of development where an image is kept running for years and hot-patched as necessary.
  - We don't have anything like [SBCL](http://www.sbcl.org/)'s [`save-lisp-and-die`](http://www.sbcl.org/manual/#Function-sb_002dext-save_002dlisp_002dand_002ddie), or indeed the difference between `defvar` (initialize only if it does not already exist in the running process) and `defparameter` (always initialize) (for details, see [Chapter 6](http://www.gigamonkeys.com/book/variables.html) in Peter Seibel's [Practical Common Lisp](http://www.gigamonkeys.com/book/)).
  - So what we have is not "image based programming" as in Common Lisp. **If you need to restart the process, it needs to cold-boot in the usual manner.**
    - Therefore, in Python, **never just hot-patch; always change your definitions on disk**, so your program will run with the new definitions also the next time it's cold-booted.
    - Once you're done testing, *then reload those definitions in the live process*, if you need/want to.
  - The next best thing: if you want semi-transparently persist objects between program runs, look into [ZODB](http://www.zodb.org/en/latest/).

Happy live hacking!


### ZODB in 5 minutes

To make the objects in your hot-patchable program persistent, see ZODB [[1]](http://www.zodb.org/en/latest/articles/old-guide/prog-zodb.html) [[2]](http://www.zodb.org/en/latest/guide/writing-persistent-objects.html) [[3]](https://zodb.readthedocs.io/en/latest/api.html). It originally comes from Zope, which as of early 2020 is dead, but ZODB itself is very much alive.

ZODB can semi-transparently store and retrieve any Python object that subclasses `persistent.Persistent`. (I haven't tried that class as a mixin, though. That could be useful for persisting `unpythonic` containers `box`, `cons`, and `frozendict`).

Here *persistent* means the data lives on disk. This is not to be confused with the other sense of *persistent data structures*, as in immutable ones, as in [pyrsistent](https://github.com/tobgu/pyrsistent/).

Persistence using ZODB is only *semi*-transparent. **You have to explicitly assign** your to-be-persisted object into the DB instance to track it, and `transaction.commit()` to apply pending changes. (*Explicit is better than implicit.*) Any data stored under the DB root dict (recursively) is saved.

Notes:

- Stuff that's related to ZODB, but not obvious from the name: the `persistent` and `transaction` packages (in the top-level namespace for packages), and `.fs` files (ZODB database store).

- ZODB saves only data, not code. It uses `pickle` under the hood, so functions are always loaded from their definitions on disk.
  - ZODB is essentially `pickle` on [ACID](https://en.wikipedia.org/wiki/ACID): *atomicity, consistency, isolation, durability*.

- API style concerns:
  - Transactions have also a context manager interface; modern style is to use that.
  - The DB root exposes both a dict-like interface as well as an attribute-access interface. So `dbroot['x'] = x` and `dbroot.x = x` do the same thing; the second way is modern style. The old way is useful mainly when the key is not a valid Python identifier.

- Think of the DB root as the top-level namespace for persistent storage.
  - So it's a bit like our `dyn`, a special place into which you can store attributes, and which plays by its own rules.
  - **Place all of your stuff into a container object**, and store only that at the top level, so that ZODB database files for separate applications can be easily merged later if the need arises. Also, the performance of the DB root isn't tuned to store a large number of objects directly at the top level. If you need a scalable container, look into the various `BTrees` in ZODB.

- Naming conventions, with semantics:
  - Any attributes beginning with `_v_` are volatile, i.e. not saved.
    - Use this naming scheme to mark your caches and such (when stored in an attribute of a persistent object).
    - **Volatile attributes may suddenly vanish** between any two method invocations, if the object instance is in the saved state, because ZODB may choose to unload saved instances at any time to conserve memory.
  - Any attributes beginning with `_p_` are reserved for use by ZODB machinery.
    - For example, set `x._p_changed = True` to force ZODB to consider an object instance `x` as modified.
    - This can be useful e.g. when `x.foo` is a builtin `list` that was mutated by calling its methods. Otherwise ZODB won't know that `x` has changed when we `x.foo.append("bar")`. Another way to signal the change to ZODB is to rebind the attribute, `x.foo = x.foo`.

- If your class subclasses `Persistent`, it's not allowed to later change your mind on this (i.e. make it non-persistent), if you want the storage file to remain compatible. See [ZODB issue #99](https://github.com/zopefoundation/ZODB/issues/99).

- Be careful when changing which data attributes your classes have; **this is a database schema change** and needs to be treated accordingly.
  - New data attributes can be added, but if you remove or rename old ones, the code in your class needs to account for that (checking for the presence of the old attribute, migrating it), or you'll need to write a script to migrate your stored objects as an offline batch job.
  - The ZODB docs were unclear [on the point](http://www.zodb.org/en/latest/guide/writing-persistent-objects.html#properties), and there was nothing else on it on the internet, so by testing it myself: *ZODB handles properties correctly*.
    - The property itself is recognized as a method. Only raw data attributes are stored into the DB.
    - After an object instance is loaded from the DB, reading a property will unghost it, just like reading a data attribute.

- Beware of persisting classes defined in `__main__`, because **the module name must remain the same** when the data is loaded back.

- The ZODB [tutorial](http://www.zodb.org/en/latest/tutorial.html) says:
  *Non-persistent objects are essentially owned by their containing persistent object and if multiple persistent objects refer to the same non-persistent subobject, they’ll (eventually) get their own copies.*
  - So beware, anything that should be preserved up to object identity and relationships should be made a persistent object.
  - ZODB has persistent list and dict types, if you need them.


## Why a custom REPL server/client

Support for syntactic macros, **in a REPL connected to a live Python process**, is why this feature is included in `unpythonic`, instead of just recommending [Manhole](https://github.com/ionelmc/python-manhole/), [socketserverREPL](https://github.com/iwanders/socketserverREPL), or similar existing solutions.

Also, the focus is subtly different from most similar projects. This server is primarily intended for hot-patching, not so much for debugging. So we don't care about debugger hooks, or instantly embedding a REPL into a particular local scope (to give the full Python user experience for examining program state, pausing the thread that spawned the REPL). We care about running the REPL server in the background (listening for connections as part of normal operation of your app), and making write access to module globals easy.

A hot-patching REPL server is also useful for agile development of oldschool style computational science scripts that run directly via `python3 -m mysolver` (no Jupyter notebook there), because it *reduces the burden of planning ahead*.

Seeing the first plots from a new study often raises new questions... some of which could be answered by re-plotting the same data (that often took two hours to compute) in alternative ways. Which would be easy if you could get your hands on the NumPy arrays your program just finished computing. But the program doesn't yet have the code to save anything to disk, because the run was supposed to be just for testing. You know that when you close that last figure window, the process will terminate, and all that delicious data will be gone.

If the arrays can be accessed from module scope, an embedded REPL server can still save the day. You just connect to your running process while it's still live, and in the REPL, save whatever you want, before closing that last figure window and letting the process terminate. It's all about having a *different kind of conversation* with your scientific problem. (Cf. Paul Graham on software development in *On Lisp*; [original quotation](https://www.ics.uci.edu/~pattis/quotations.html#G).)

## Future directions

### Authentication and encryption

SSH with key-based authentication is the primary future direction of interest. It would enable security, making actual remote access feasible.

This may be added in an eventual v2.0 (using [Paramiko](https://github.com/paramiko/paramiko/)), but right now it's not on the immediate roadmap. This would allow a client to be sure the server is who it claims to be, as well as letting users log in based on an `authorized_keys` file. It would also make it possible to audit who has connected and when.

What we want is to essentially treat our Python REPL as the shell for the SSH session. There are a lot of Paramiko client examples on the internet (oddly, with a focus mainly on security testing), but [demo_server.py](https://github.com/paramiko/paramiko/blob/master/demos/demo_server.py) in the distribution seems to be the only server example, and leaves unclear important issues such as how to set up a session and a shell. Reading [paramiko/server.py](https://github.com/paramiko/paramiko/blob/master/paramiko/server.py) as well as [paramiko/transport.py](https://github.com/paramiko/paramiko/blob/master/paramiko/transport.py) didn't make me much wiser.

So right now, I'm not going to bother with SSH support. If interested, help is welcome.

## Note on macro-enabled consoles

Back in 0.14.x, drop-in replacing `code.InteractiveConsole` in `unpythonic.net.server` with `macropy.core.console.MacroConsole` gave rudimentary macro support. However, to have the same semantics as in the [`imacropy.iconsole`](https://github.com/Technologicat/imacropy) IPython extension, a custom console was needed. This was added to `imacropy` as `imacropy.console.MacroConsole`. An updated version of this technology (including an updated IPython extension) was then included in [`mcpyrate`](https://github.com/Technologicat/mcpyrate).

Why `mcpyrate.repl.console.MacroConsole`:

 - Catches and reports import errors when importing macros.
 - Allows importing the same macros again in the same session, to refresh their definitions.
   - When you `from somemod import macros, ...`, this console automatically first reloads `somemod`, so that a macro import always sees the latest definitions.
 - Makes viewing macro docstrings easy.
   - When you import macros, beside loading them into the macro expander, the console automatically imports the macro stubs as regular runtime objects. They're functions, so just look at their `__doc__`.
   - This also improves UX. Without loading the stubs, `from unpythonic.syntax import macros, let`, would not define the name `let` at runtime. Now it does, with the name pointing to the macro stub.
 - IPython-like `obj?` and `obj??` syntax to view the docstring and source code of `obj`.
 - Can list macros imported to the session, using the command `macros?`.


For historical interest, refer to and compare [imacropy/iconsole.py](https://github.com/Technologicat/imacropy/blob/master/imacropy/iconsole.py) and [macropy/core/console.py](https://github.com/azazel75/macropy/blob/master/macropy/core/console.py). The result was [imacropy/console.py](https://github.com/Technologicat/imacropy/blob/master/imacropy/console.py). Now this technology lives in [mcpyrate/repl/console.py](https://github.com/Technologicat/mcpyrate/blob/master/mcpyrate/repl/console.py) and [mcpyrate/repl/iconsole.py](https://github.com/Technologicat/mcpyrate/blob/master/mcpyrate/repl/iconsole.py).
