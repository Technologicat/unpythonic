"""REPL server for inspecting and hot-patching a running Python process.

This module makes your Python app serve up a REPL (read-eval-print-loop)
over TCP, somewhat like the Swank server in Common Lisp.

In a REPL session, you can inspect and mutate the global state of your running
program. You can e.g. replace top-level function definitions with new versions
in your running process, or reload modules from disk (with `importlib.reload`).

The REPL server runs in a daemon thread. Terminating the main thread of your
process will terminate the server, also forcibly terminating all open REPL
sessions in that process.


**SECURITY WARNING**: A REPL SERVER IS ESSENTIALLY A BACK DOOR.

Currently, we provide NO authentication or encryption. Anyone can connect, and
once connected, do absolutely anything that the user account running your app
can do. Connections are anonymous.

Hence, only use this server in carefully controlled environments, such as:

a) Your own local machine, with no untrusted human users on it,

b) A dedicated virtual server running only your app, in which case
   the OS level already provides access control and encrypted connections.

Even then, serve this ONLY on the loopback interface, to force users to connect
to the machine via SSH first (or have physical local console access).


With that out of the way, to enable the server in your app::

    from unpythonic.net import server
    server.start(locals=globals())

The `locals=...` argument sets the top-level namespace for variables for use by
the REPL. It is shared between REPL sessions.

Using `locals=globals()` makes the REPL directly use the calling module's
top-level scope. If you want a clean environment, where you must access any
modules through `sys.modules`, use `locals={}`.


To connect to a running REPL server (with tab completion and Ctrl+C support)::

    python3 -m unpythonic.net.client localhost 1337

If you're already running in a local Python REPL, this should also work::

    from unpythonic.net import client
    client.connect(("127.0.0.1", 1337))

For basic use (history, but no tab completion), you can use::

    rlwrap netcat localhost 1337

or even just (no history, no tab completion)::

    netcat localhost 1337


**CAUTION**: Python's builtin `help(foo)` does not work in this REPL server.
It cannot, because the client runs a complete second input prompt (that holds
the local TTY), separate from the input prompt running on the server.
So the stdin/stdout are not just redirected to the socket.

Trying to open the built-in help will open the help locally on the server,
causing the client to hang. The top-level `help()`, which uses a command-based
interface, appears to work, until you ask for a help page, at which point it
runs into the same problem.

As a workaround, we provide `doc(foo)`, which just prints the docstring (if any),
and performs no paging.


**CAUTION**: Python was not designed for arbitrary hot-patching. If you change
a **class** definition (whether by re-assigning the reference or by reloading
the module containing the definition), only new instances will use the new
definition, unless you specifically monkey-patch existing instances to change
their type.

The language docs hint it is somehow possible to retroactively change an
object's type, if you're careful with it:
    https://docs.python.org/3/reference/requestmodel.html#id8
In fact, ActiveState recipe 160164 explicitly tells how to do it,
and even automate that with a custom metaclass:
    https://github.com/ActiveState/code/tree/master/recipes/Python/160164_automatically_upgrade_class_instances

Based on socketserverREPL by Ivor Wanders, 2017. Used under the MIT license.
    https://github.com/iwanders/socketserverREPL
Based on macropy.core.MacroConsole by Li Haoyi, Justin Holmgren, Alberto Berti and all the other contributors,
2013-2019. Used under the MIT license.
    https://github.com/azazel75/macropy
Based on imacropy.console by the same author as unpythonic. 2-clause BSD license.
    https://github.com/Technologicat/imacropy


**Trivia**:

Default port is 1337, because connecting to a live Python program can be
considered somewhat that. Refer to https://megatokyo.com/strip/9.

The `socketserverREPL` package uses the same default, and actually its
`repl_tool.py` can talk to this server (but doesn't currently feature
remote tab completion).
"""

# TODO: use logging module instead of server-side print
# TODO: support several server instances? (makes sense if each is connected to a different module)

__all__ = ["start", "stop"]  # Exports for code that wants to embed the server.

import rlcompleter  # yes, just rlcompleter without readline; backend for remote tab completion.
import threading
import sys
import os
import time
import socketserver
import atexit
import inspect
from itertools import count

try:
    from macropy.core.macros import WrappedFunction
except ModuleNotFoundError:  # probably no MacroPy installed
    WrappedFunction = None

try:
    # Improved macro-enabled console. Imacropy semantics; ?, ?? docstring/source viewing syntax;
    # improved handling of macro import errors; can reload macros and re-establish macro bindings.
    from imacropy.console import MacroConsole as Console
except ModuleNotFoundError:
    try:
        # MacroPy's own macro-enabled console
        import macropy.activate  # noqa: F401, just needed to boot up MacroPy.
        from macropy.core.console import MacroConsole as Console
    except ModuleNotFoundError:
        from code import InteractiveConsole as Console

from ..collections import ThreadLocalBox, Shim
from ..misc import async_raise, namelambda
from ..symbol import sym

from .util import ReuseAddrThreadingTCPServer, socketsource
from .msg import MessageDecoder
from .common import ApplevelProtocolMixin
from .ptyproxy import PTYSocketProxy

# Because "These are only defined if the interpreter is in interactive mode.",
# we have to do something like this.
# https://docs.python.org/3/library/sys.html#sys.ps1
try:
    _original_ps1, _original_ps2 = sys.ps1, sys.ps2
except AttributeError:
    _original_ps1, _original_ps2 = None, None

_server_instance = None
_active_sessions = {}
_session_counter = count(start=1)  # for generating session ids, needed for pairing control and REPL sessions.
_halt_pending = False
_original_stdin = sys.stdin
_original_stdout = sys.stdout
_original_stderr = sys.stderr
_threadlocal_stdin = ThreadLocalBox(_original_stdin)
_threadlocal_stdout = ThreadLocalBox(_original_stdout)
_threadlocal_stderr = ThreadLocalBox(_original_stderr)
_console_locals_namespace = None
_banner = None

# --------------------------------------------------------------------------------
# Exports for REPL sessions

# This is a copy of `imacropy.doc` (from v0.3.0) with a slightly modified docstring.
# We strictly need a local copy of this only if `imacropy` is not installed,
# to allow viewing docstrings in the MacroPy or stdlib consoles.
def doc(obj):
    """Print an object's docstring, non-interactively.

    Additionally, if the information is available, print the filename
    and the starting line number of the definition of `obj` in that file.
    This is printed before the actual docstring.

    This works around the problem that in a REPL session, the stdin/stdout
    of the builtin `help()` are not properly redirected.

    And that looking directly at `some_macro.__doc__` prints the string
    value as-is, without formatting it.

    NOTE: if you have the `imacropy` package installed, you can use
    the IPython-like `obj?` and `obj??` syntax instead (provided by
    `imacropy.console.MacroConsole`).
    """
    if not hasattr(obj, "__doc__") or not obj.__doc__:
        print("<no docstring>")
        return
    try:
        if isinstance(obj, WrappedFunction):
            obj = obj.__wrapped__  # this is needed to make inspect.getsourcefile work with macros
        filename = inspect.getsourcefile(obj)
        source, firstlineno = inspect.getsourcelines(obj)
        print(f"{filename}:{firstlineno}")
    except (TypeError, OSError):
        pass
    print(inspect.cleandoc(obj.__doc__))

# TODO: detect stdout, stderr and redirect to the appropriate stream.
def server_print(*values, **kwargs):
    """Print to the original stdout of the server process."""
    print(*values, **kwargs, file=_original_stdout)

def halt(doit=True):
    """Tell the REPL server to shut down after the last client has disconnected.

    To cancel a pending halt, use `halt(False)`.
    """
    if doit:
        msg = "Halt requested, REPL server will shut down after the last client disconnects."
    else:
        msg = "Halt canceled, REPL server will remain running."
    global _halt_pending
    _halt_pending = doit
    print(msg)
    server_print(msg)

_bg_results = {}
_bg_running = sym("_bg_running")
_bg_success = sym("_bg_success")
_bg_fail = sym("_bg_fail")
def bg(thunk):
    """Spawn a thread to run `thunk` in the background. Return the thread object.

    To get the return value of `thunk`, see `fg`.
    """
    @namelambda(thunk.__name__)
    def worker():
        _bg_results[thread.ident] = (_bg_running, None)
        try:
            result = thunk()
        except Exception as err:
            _bg_results[thread.ident] = (_bg_fail, err)
        else:
            _bg_results[thread.ident] = (_bg_success, result)
    thread = threading.Thread(target=worker, name=thunk.__name__, daemon=True)
    thread.start()
    return thread

# TODO: we could use a better API, but I don't want timeouts or a default return value.
def fg(thread):
    """Get the return value of a `bg` thunk.

    `thread` is the thread object returned by `bg` when the computation was started.

    If the thread is still running, return `thread` itself.

    If completed, **pop** the result. If the thread:
      - returned normally: return the value.
      - raised an exception: raise that exception.
    """
    if "ident" not in thread:
        raise TypeError("Expected a Thread object, got {} with value {}.".format(type(thread), thread))
    if thread.ident not in _bg_results:
        raise ValueError("No result for thread {}".format(thread))
    # This pattern is very similar to that used by unpythonic.fun.memoize...
    status, value = _bg_results[thread.ident]
    if status is _bg_running:
        return thread
    _bg_results.pop(thread.ident)
    if status is _bg_success:
        return value
    elif status is _bg_fail:
        raise value
    assert False


# Exports available in REPL sessions.
# These will be injected to the `locals` namespace of the REPL session when the server starts.
_repl_exports = {doc, server_print, halt, bg, fg}


# --------------------------------------------------------------------------------
# Server itself

class ControlSession(socketserver.BaseRequestHandler, ApplevelProtocolMixin):
    """Entry point for connections to the control server.

    We use a separate connection for control to avoid head-of-line blocking.

    For example, how the remote tab completion works: the client sends us
    a request. We invoke `rlcompleter` on the server side, and return its
    response to the client.
    """
    def handle(self):
        # TODO: ipv6 support
        caddr, cport = self.client_address
        client_address_str = "{}:{}".format(caddr, cport)
        class ClientExit(Exception):
            pass
        try:
            server_print("Control channel for {} opened.".format(client_address_str))
            # TODO: fancier backend? See examples in https://pymotw.com/3/readline/
            completer_backend = rlcompleter.Completer(_console_locals_namespace)
            # From the docstring of `socketserver.BaseRequestHandler`:
            #     This class is instantiated for each request to be handled.
            #     ...
            #     Since a separate instance is created for each request, the
            #     handle() method can define other arbitrary instance variables.
            self.sock = self.request
            self.decoder = MessageDecoder(socketsource(self.sock))
            self.paired_repl_session_id = None
            while True:
                # The control server follows a request-reply application-level
                # protocol, which is essentially a remote procedure call
                # interface. We use ApplevelProtocolMixin, which allows us to
                # transmit the function name, arguments and return values in
                # a dictionary format.
                #
                # A request from the client is a dictionary, with str keys. It
                # must contain the field "command", with its value set to one
                # of the recognized command names as an `str`.
                #
                # Existence and type of any other fields depends on each
                # individual command. This server source code is the official
                # documentation of this small app-level protocol.
                #
                # For each request received, the server sends a reply, which is
                # also a dictionary with str keys. It has one compulsory field:
                # "status". Upon success, it must contain the string "ok". The
                # actual return value(s) (if any) may be provided in arbitrary
                # other fields, defined by each individual command.
                #
                # Upon failure, the "status" field must contain the string
                # "failed". An optional (but strongly recommended!) "reason"
                # field may contain a short description about the failure.
                # More information may be included in arbitrary other fields.
                request = self._recv()
                if not request:
                    server_print("Socket for {} closed by client.".format(client_address_str))
                    raise ClientExit

                if "command" not in request:
                    reply = {"status": "failed", "reason": "Request is missing the 'command' field."}

                elif request["command"] == "DescribeServer":
                    reply = {"status": "ok",
                             # needed by client's prompt detector
                             "prompts": {"ps1": sys.ps1, "ps2": sys.ps2},
                             # for future-proofing only
                             "control_protocol_version": "1.0",
                             "supported_commands": ["DescribeServer", "PairWithSession", "TabComplete", "KeyboardInterrupt"]}

                elif request["command"] == "PairWithSession":
                    if "id" not in request:
                        reply = {"status": "failed", "reason": "Request is missing the PairWithSession parameter 'id'."}
                    else:
                        if request["id"] not in _active_sessions:
                            errmsg = "Pairing control session failed; there is no active REPL session with id={}.".format(request["id"])
                            reply = {"status": "failed", "reason": errmsg}
                            server_print(errmsg)
                        else:
                            server_print("Pairing control session for {} to REPL session {}.".format(client_address_str, request["id"]))
                            self.paired_repl_session_id = request["id"]
                            reply = {"status": "ok"}

                elif request["command"] == "TabComplete":
                    if "text" not in request or "state" not in request:
                        reply = {"status": "failed", "reason": "Request is missing at least one of the TabComplete parameters 'text' and 'state'."}
                    else:
                        completion = completer_backend.complete(request["text"], request["state"])
                        # server_print(request, reply)  # DEBUG
                        reply = {"status": "ok", "result": completion}

                elif request["command"] == "KeyboardInterrupt":
                    server_print("Client {} sent request for remote Ctrl+C.".format(client_address_str))
                    if not self.paired_repl_session_id:
                        errmsg = "This control channel is not currently paired with a REPL session."
                        reply = {"status": "failed", "reason": errmsg}
                        server_print(errmsg)
                    else:
                        server_print("Remote Ctrl+C in session {}.".format(self.paired_repl_session_id))
                        try:
                            target_session = _active_sessions[self.paired_repl_session_id]
                            target_thread = target_session.thread
                        except KeyError:
                            errmsg = "REPL session {} no longer active.".format(self.paired_repl_session_id)
                            reply = {"status": "failed", "reason": errmsg}
                            server_print(errmsg)
                        except AttributeError:
                            errmsg = "REPL session {} has no 'thread' attribute.".format(self.paired_repl_session_id)
                            reply = {"status": "failed", "reason": errmsg}
                            server_print(errmsg)
                        else:
                            try:
                                # The implementation of async_raise is one of the dirtiest hacks ever,
                                # and only works on Python implementations providing the `ctypes` module,
                                # since Python has no officially exposed mechanism to trigger an asynchronous
                                # exception (such as KeyboardInterrupt) in an arbitrary thread.
                                async_raise(target_thread, KeyboardInterrupt)
                            except (ValueError, SystemError, RuntimeError) as err:
                                server_print(err)
                                reply = {"status": "failed", "reason": err.args, "failure_type": str(type(err))}
                            else:
                                reply = {"status": "ok"}

                else:
                    reply = {"status": "failed", "reason": "Command '{}' not understood by this server.".format(request["command"])}

                self._send(reply)

        except ClientExit:
            server_print("Control channel for {} closed.".format(client_address_str))
        except BaseException as err:
            server_print(err)


class ConsoleSession(socketserver.BaseRequestHandler):
    """Entry point for connections from the TCP server.

    Primary channel. This serves the actual REPL session.
    """
    def handle(self):
        # TODO: ipv6 support
        caddr, cport = self.client_address
        client_address_str = "{}:{}".format(caddr, cport)

        try:
            # for control/REPL pairing
            self.session_id = next(_session_counter)
            _active_sessions[self.session_id] = self  # also for exit monitoring

            # self.request is the socket. We don't need a StreamRequestHandler with self.rfile and self.wfile,
            # since we in any case only forward raw bytes between the PTY master FD and the socket.
            # https://docs.python.org/3/library/socketserver.html#socketserver.StreamRequestHandler

            def on_socket_disconnect(adaptor):
                server_print('PTY on {} for client {} disconnected by client.'.format(os.ttyname(adaptor.slave), client_address_str))
                os.write(adaptor.master, "quit()\n".encode("utf-8"))  # as if this text arrived from the socket
            def on_slave_disconnect(adaptor):
                server_print('PTY on {} for client {} disconnected by PTY slave.'.format(os.ttyname(adaptor.slave), client_address_str))
            adaptor = PTYSocketProxy(self.request, on_socket_disconnect, on_slave_disconnect)
            adaptor.start()
            server_print('PTY on {} for client {} opened.'.format(os.ttyname(adaptor.slave), client_address_str))

            # fdopen the slave side of the PTY to get file objects to work with.
            # Be sure not to close the fd when exiting, it is managed by PTYSocketProxy.
            #
            # Note we can open the slave side in text mode, so these streams can behave
            # exactly like standard input and output. The proxying between the master side
            # and the network socket runs in binary mode inside PTYSocketProxy.
            with open(adaptor.slave, "wt", encoding="utf-8", closefd=False) as wfile:
                with open(adaptor.slave, "rt", encoding="utf-8", closefd=False) as rfile:
                    # Set up the input and output streams for the thread we are running in.
                    # We use ThreadingTCPServer, so each connection gets its own thread.
                    # Here we just send the relevant object into each thread-local box.
                    _threadlocal_stdin << rfile
                    _threadlocal_stdout << wfile
                    _threadlocal_stderr << wfile

                    self.thread = threading.current_thread()  # needed by remote Ctrl+C

                    # This must be the first thing printed by the server, so that the client
                    # can get the session id from it. This hack is needed for netcat compatibility.
                    #
                    # (In case of the custom client, it establishes two independent TCP connections.
                    #  The REPL session must give an ID for attaching the control channel, but since
                    #  we want it to remain netcat-compatible, it can't use the message protocol to
                    #  send that information.)
                    print("REPL session {} connected.".format(self.session_id))  # ...at the client side

                    if _banner != "":
                        print(_banner)

                    self.console = Console(locals=_console_locals_namespace)

                    # All errors except SystemExit are caught inside interact().
                    try:
                        server_print("Opening REPL session {} for {}.".format(self.session_id, client_address_str))
                        self.console.interact(banner=None, exitmsg="Bye.")
                    except SystemExit:  # Close the connection upon server process exit.
                        pass
                    finally:
                        server_print('Closing PTY on {} for {}.'.format(os.ttyname(adaptor.slave), client_address_str))
                        adaptor.stop()
                        server_print("Closing REPL session {} for {}.".format(self.session_id, client_address_str))
        except BaseException as err:  # yes, SystemExit and KeyboardInterrupt, too.
            server_print(err)
        finally:
            del _active_sessions[self.session_id]


# TODO: IPv6 support
def start(locals, bind="127.0.0.1", repl_port=1337, control_port=8128, banner=None):
    """Start the REPL server.

    bind:         Interface to bind to. The default value is recommended,
                  to accept connections from the local machine only.
    repl_port:    TCP port number for main channel (REPL session).
    control_port: TCP port number for the control channel (tab completion
                  and Ctrl+C requests).

    locals:       Namespace (dict-like) to use as the locals namespace
                  of REPL sessions that connect to this server. It is
                  shared between sessions.

                  Some useful values for `locals`:

                    - `{}`, to make a clean environment which is seen by
                      the REPL sessions only. Maybe the most pythonic.

                    - `globals()`, the top-level namespace of the calling
                      module. Can be convenient, especially if the server
                      is started from your main module.

                  This is not set automatically, because explicit is
                  better than implicit.

                  In any case, note you can just grab modules from
                  `sys.modules` if you need to access their top-level scopes.

    banner:       Startup message. Default is to show help for usage.
                  To suppress, use banner="".

    To connect to the REPL server (assuming default settings)::

        python3 -m unpythonic.net.client localhost

    **NOTE**: Currently, only one REPL server is supported per process,
    but it accepts multiple simultaneous connections. A new thread is
    spawned to serve each new connection.

    **CAUTION**: There is absolutely no authentication support, so it is
    recommended to only serve to localhost, and only on a machine whose
    users you trust.
    """
    global _server_instance, _console_locals_namespace
    if _server_instance is not None:
        raise RuntimeError("The current process already has a running REPL server.")

    _console_locals_namespace = locals
    for function in _repl_exports:  # Inject REPL utilities
        _console_locals_namespace[function.__name__] = function

    global _banner
    if banner is None:
        default_msg = ("Unpythonic REPL server at {addr}:{port}, on behalf of:\n"
                       "  {argv}\n"
                       "    quit(), exit() or EOF (Ctrl+D) at the prompt disconnects this session.\n"
                       "    halt() tells the server to close after the last session has disconnected.\n"
                       "    print() prints in the REPL session.\n"
                       "       NOTE: print() is only properly redirected in the session's main thread.\n"
                       "    doc(obj) shows obj's docstring. Use this instead of help(obj) in the REPL.\n"
                       "    server_print(...) prints on the stdout of the server.\n"
                       "  A very limited form of job control is available:\n"
                       "    bg(thunk) spawns and returns a background thread that runs thunk.\n"
                       "    fg(thread) pops the return value of a background thread.\n"
                       "  If you stash the thread object in the REPL locals, you can disconnect the\n"
                       "  session, and read the return value in another session later.")
        _banner = default_msg.format(addr=bind, port=repl_port, argv=" ".join(sys.argv))
    else:
        _banner = banner

    # Set the prompts. We use four "." to make semi-sure the prompt string only appears as a prompt.
    # The client needs to identify the prompts from the data stream in order to know when to switch
    # between listening and prompting, so "..." is not even semi-safe (it's valid Python, as well as
    # valid English).
    sys.ps1 = ">>>> "
    sys.ps2 = ".... "

    # We use a combo of Shim and ThreadLocalBox to redirect attribute lookups
    # to the thread-specific read/write streams.
    #
    # sys.stdin et al. are replaced by shims, which hold their targets in
    # thread-local boxes. In the main thread (and as a default), the boxes contain
    # the original sys.stdin et al., whereas in session threads, the boxes are filled
    # with streams established for that particular session.
    sys.stdin = Shim(_threadlocal_stdin)
    sys.stdout = Shim(_threadlocal_stdout)
    sys.stderr = Shim(_threadlocal_stderr)

    # https://docs.python.org/3/library/socketserver.html#socketserver.BaseServer.server_address
    # https://docs.python.org/3/library/socketserver.html#socketserver.BaseServer.RequestHandlerClass
    server = ReuseAddrThreadingTCPServer((bind, repl_port), ConsoleSession)
    server.daemon_threads = True  # Allow Python to exit even if there are REPL sessions alive.
    server_thread = threading.Thread(target=server.serve_forever, name="Unpythonic REPL server", daemon=True)
    server_thread.start()

    # Control channel for remote tab completion and remote Ctrl+C requests.
    # Default port is 8128 because it's for *completing* things, and https://en.wikipedia.org/wiki/Perfect_number
    # This is the first one above 1024, and was already known to Nicomachus around 100 CE.
    cserver = ReuseAddrThreadingTCPServer((bind, control_port), ControlSession)
    cserver.daemon_threads = True
    cserver_thread = threading.Thread(target=cserver.serve_forever, name="Unpythonic REPL control server", daemon=True)
    cserver_thread.start()

    _server_instance = (server, server_thread, cserver, cserver_thread)
    atexit.register(stop)
    return bind, repl_port, control_port


def stop():
    """Stop the REPL server.

    If the server has been started, this will be called automatically when the
    process exits. It can be called earlier manually to shut down the server if
    desired.
    """
    global _server_instance, _console_locals_namespace
    if _server_instance is not None:
        server, server_thread, cserver, cserver_thread = _server_instance
        server.shutdown()
        server.server_close()
        server_thread.join()
        cserver.shutdown()
        cserver.server_close()
        cserver_thread.join()
        _server_instance = None
        sys.stdin = _original_stdin
        sys.stdout = _original_stdout
        sys.stderr = _original_stderr
        _console_locals_namespace = None
        atexit.unregister(stop)
        if _original_ps1:
            sys.ps1 = _original_ps1
        else:
            delattr(sys, "ps1")
        if _original_ps2:
            sys.ps2 = _original_ps2
        else:
            delattr(sys, "ps2")


# demo app
def main():
    server_print("REPL server starting...")
    bind, repl_port, control_port = start(locals={})
    server_print("Started REPL server on {}:{}.".format(bind, repl_port))
    try:
        while True:
            time.sleep(1)
            if _halt_pending and not _active_sessions:
                break
        server_print("REPL server closed.")
    except KeyboardInterrupt:
        server_print("Server process got Ctrl+C, closing REPL server and all connections NOW.")

if __name__ == '__main__':
    main()
