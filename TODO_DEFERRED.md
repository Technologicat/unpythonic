# Deferred Issues

Next unused item code: D10

- **D5**: `dispatch.py` — moved to GitHub issue #99. Dispatch-layer improvements for parametric ABCs (warn/error on indistinguishable multimethods). Typecheck-layer part resolved.


- **D8: Audit typing: abstract parameter types, concrete return types**: Parameters should use abstract types from `collections.abc` (`Mapping`, `Sequence`, `Iterable`) for widest-possible-accepted semantics. Return types should use concrete lowercase builtins (`tuple[int, int]`, `list[int]`, `dict[str, int]`) — PEP 585, Python 3.9+. The capitalized `typing` forms (`Dict`, `List`, `Tuple`) are deprecated aliases for the builtins and offer no extra width — avoid them. Audit existing type hints across the codebase for consistency. (Discovered during raven-cherrypick compare mode planning, 2026-03-30.)


- **D9: Port `unpythonic.net` (REPL server/client) to MS Windows**: The remote-REPL subsystem (`unpythonic.net.server`, `unpythonic.net.client`, `unpythonic.net.ptyproxy`) is currently documented as POSIX-only (see 2.0.0 CHANGELOG). The blockers are in `ptyproxy.py`, which uses `termios`, `fcntl`, `pty`, and `select` to create a pseudoterminal pair for the server-side `code.InteractiveConsole` to read/write through. None of those modules exist on Windows.

  **Rough list of Windows equivalents**, in order of plausibility:

  - **`pywinpty`** (third-party, ~active maintenance) — the preferred option. Wraps the Windows **Pseudo Console API** (ConPTY, introduced in Windows 10 1809, October 2018). Used by JupyterLab's terminal and by `xterm.js`-based backends. Provides a pty-like interface that `ptyproxy.py` could consume with a thin adapter. Would need to become a Windows-only optional dependency of unpythonic.
  - **`msvcrt`** (stdlib) — low-level Windows console I/O. NOT a pty equivalent: it's just console-focused character access (`kbhit`, `getch`, `getwch`, etc.). Probably not useful on its own for this purpose — it doesn't give you the "line discipline + bidirectional pipe" semantics that `pty` provides on POSIX.
  - **`winpty`** (pre-ConPTY, C-level library, third-party) — the older Cygwin-era solution. ConPTY supersedes it and `pywinpty` can use ConPTY directly on recent Windows. Only relevant if we need to support Windows versions before 10-1809, which we don't.
  - **`ptyprocess` / `pexpect`** — pexpect has a Windows backend, but it uses `wexpect` under the hood and has historically been finicky. Not currently recommended as the primary approach, but could serve as a higher-level wrapper *on top of* pywinpty.
  - **Raw Windows API via `ctypes`** — `CreatePseudoConsole()`, `ResizePseudoConsole()`, `ClosePseudoConsole()` can be called directly through `ctypes` if we want to avoid the `pywinpty` dependency. More work; smaller dep footprint. Decision to make at design time.

  **Likely decomposition** of the work:

  1. Split `ptyproxy.py` into a platform-dispatch wrapper that imports either a `ptyproxy_posix` submodule (current code) or a new `ptyproxy_windows` submodule. Both expose the same `PTYSocketProxy` class.
  2. Implement `ptyproxy_windows` using `pywinpty` — or, if that turns out to be heavy for an optional dep, using direct `ctypes` calls to ConPTY. ConPTY's semantics differ from Unix pty in subtle ways (output buffering, line-discipline equivalent, terminal-resize signalling), so this will need careful testing against the existing unit/integration tests once those exist (see the interactive-REPL testing strategy designed in this same session).
  3. Make `pywinpty` (or whatever is chosen) a Windows-only optional dep via `[project.optional-dependencies]` — e.g. `windows = ["pywinpty>=2.0"]` — with a helpful ImportError message if someone tries to use `unpythonic.net.{server,client}` on Windows without it installed.
  4. Add Windows cells to `unpythonic.net`'s test matrix (which depends on tests existing in the first place — currently `unpythonic.net` has no tests, also covered by the testing-strategy discussion this session).
  5. Update the 2.0.0 CHANGELOG entry that currently documents `unpythonic.net` as POSIX-only once this lands.

  **Why deferred**: this is a non-trivial port that probably deserves its own design session — at minimum a careful read of pywinpty's API surface, a mapping of pty primitives to their ConPTY equivalents, and a plan for how to test the result without having a Windows dev machine. User currently has only Linux dev boxes; any debugging would be entirely via CI, which is feasible but slow-iterating.

  **Related**: the `parse_and_bind` Darwin-branch fix in `net/client.py` (2026-04-15) was a prerequisite refactor — `net/client.py` is now in the right shape for the Windows port to plug into. Also, the three-tier hybrid readline fallback pattern documented in `raven.librarian.minichat` and `mcpyrate.repl.macropython` (same session) is directly reusable for `net/client.py` once `net/client.py`'s top-level `import readline` is moved inside the client function and guarded.

  (Added 2026-04-15, based on audit + discussion during the Windows-CI expansion session.)
