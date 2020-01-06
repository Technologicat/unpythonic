"""REPL server for inspecting and hot-patching a running Python process.

This module makes your Python app serve up a REPL (read-eval-print-loop)
over TCP, somewhat like the Swank server in Common Lisp.

In a REPL session, you can inspect and mutate the global state of your running
program. You can e.g. replace top-level function definitions with new versions
in your running process, or reload modules from disk (with `importlib.reload`).

To enable it in your app::

    from unpythonic.net import server
    server.start(locals=globals())

To connect to a running REPL server (with tab completion and Ctrl+C support)::

    python3 -m unpythonic.net.client localhost 1337

If you're already running in a local Python REPL, this should also work::

    from unpythonic.net import client
    client.connect(("127.0.0.1", 1337))

For basic use (history, but no tab completion), you can use::

    rlwrap netcat localhost 1337

or even just (no history, no tab completion)::

    netcat localhost 1337

The REPL server runs in a daemon thread. Terminating the main thread of your
process will terminate the server, also forcibly terminating all open REPL
sessions in that process.

**CAUTION**: `help(foo)` currently does not work in this REPL server. Its
stdin/stdout are not redirected to the socket; instead, it will run locally on
the server, causing the client to hang. The top-level `help()`, which uses a
command-based interface, appears to work, until you ask for a help page, at
which point it runs into the same problem.

**CAUTION**: as Python was not designed for arbitrary hot-patching, if you
change a **class** definition (whether by re-assigning the reference or by
reloading the module containing the definition), only new instances will use
the new definition, unless you specifically monkey-patch existing instances to
change their type.

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
# TODO: support syntactic macros
#   TODO: macro expander
#   TODO: per-session macro definitions like in imacropy
#   TODO: import macro stubs for inspection like in imacropy
#   TODO: helper magic function macros() to list currently enabled macros
# TODO: history fixes (see repl_tool in socketserverREPL), syntax highlight?
# TODO: figure out how to make help() work, if possible?

__all__ = ["start", "stop", "server_print", "halt"]

try:
    import ctypes
except ImportError:  # not on CPython
    ctypes = None

import code
import rlcompleter  # yes, just rlcompleter without readline; backend for remote tab completion.
import threading
import sys
import os
import time
import socketserver
import atexit

from ..collections import ThreadLocalBox, Shim
from ..misc import async_raise

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
_session_counter = 0  # for generating session ids, needed for pairing control and REPL sessions.
_halt_pending = False
_original_stdin = sys.stdin
_original_stdout = sys.stdout
_original_stderr = sys.stderr
_threadlocal_stdin = ThreadLocalBox(_original_stdin)
_threadlocal_stdout = ThreadLocalBox(_original_stdout)
_threadlocal_stderr = ThreadLocalBox(_original_stderr)
_console_locals_namespace = None
_banner = None

# TODO: inject this to globals of the target module
#   - Maybe better to inject just a single "repl" container which has this and
#     the other stuff, and print out at connection time where to find this stuff.
def halt(doit=True):
    """Tell the REPL server to shut down after the last client has disconnected.

    This function is available in the REPL.

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

# TODO: inject this to globals of the target module
# TODO: detect stdout, stderr and redirect to the appropriate stream.
def server_print(*values, **kwargs):
    """Print to the original stdout of the server process.

    This function is available in the REPL.
    """
    print(*values, **kwargs, file=_original_stdout)


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
                # The control server follows a request-reply application-level protocol,
                # layered on top of the `unpythonic.net.msg` protocol, layered on top
                # of a TCP socket.
                #
                # A message sent by the client contains exactly one request.
                # A request is a UTF-8 encoded JSON dictionary with one
                # compulsory field: "command". It must contain one of the
                # recognized command names as `str`.
                #
                # Existence and type of any other fields depends on each
                # individual command. This server source code is the official
                # documentation of this small app-level protocol.
                #
                # For each request received, the server sends a reply.
                # A reply is a UTF-8 encoded JSON dictionary with one
                # compulsory field: "status". Upon success, it must contain
                # the string "ok". The actual return value(s) (if any) may
                # be provided in arbitrary other fields, defined by each
                # individual command.
                #
                # Upon failure, the "status" must contain the string "failed".
                # An optional (and recommended!) "reason" field may contain
                # a short description about the failure. More information
                # may be included in arbitrary other fields.
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
                        server_print("Pairing control session for {} to REPL session {} for remote Ctrl+C requests.".format(client_address_str, request["id"]))
                        self.paired_repl_session_id = request["id"]
                        reply = {"status": "ok"}

                elif request["command"] == "TabComplete":
                    if "text" not in request or "state" not in request:
                        reply = {"status": "failed", "reason": "Request is missing at least one of the TabComplete parameters 'text' and 'state'."}
                    else:
                        completion = completer_backend.complete(request["text"], request["state"])
                        # server_print(request, reply)
                        reply = {"status": "ok", "result": completion}

                elif request["command"] == "KeyboardInterrupt":
                    server_print("Client {} sent request for remote Ctrl+C.".format(client_address_str))
                    if not self.paired_repl_session_id:
                        reply = {"status": "failed", "reason": "This control channel is not currently paired with a REPL session."}
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
                                # and only works on CPython, since Python has no officially exposed
                                # mechanism to trigger an asynchronous exception in an arbitrary thread.
                                async_raise(target_thread, KeyboardInterrupt)
                            except (ValueError, SystemError, RuntimeError) as err:
                                server_print(err)
                                reply = {"status": "failed", "reason": err.args, "failure_type": type(err)}
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
            global _session_counter
            _session_counter += 1
            self.session_id = _session_counter
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
                    print("REPL session {} connected.".format(self.session_id))  # ...at the client side

                    if _banner != "":
                        print(_banner)

                    self.console = code.InteractiveConsole(locals=_console_locals_namespace)

                    # All errors except SystemExit are caught inside interact(), only
                    # sys.exit() is escalated, in this situation we want to close the
                    # connection, not kill the server ungracefully. We have halt()
                    # to do that gracefully.
                    try:
                        server_print("Opening REPL session {} for {}.".format(self.session_id, client_address_str))
                        self.console.interact(banner=None, exitmsg="Bye.")
                    except SystemExit:
                        pass
                    finally:
                        server_print('Closing PTY on {} for {}.'.format(os.ttyname(adaptor.slave), client_address_str))
                        adaptor.stop()
                        server_print("Closing REPL session {} for {}.".format(self.session_id, client_address_str))
        except BaseException as err:
            server_print(err)
        finally:
            del _active_sessions[self.session_id]


def start(locals, addrspec=("127.0.0.1", 1337), banner=None):
    """Start the REPL server.

    locals:   Namespace (dict-like) to use as the locals namespace
              of REPL sessions that connect to this server.

              A useful value is `globals()`, the top-level namespace
              of the calling module. This is not set automatically,
              because explicit is better than implicit.)

    addrspec: Server TCP address and port. This is given as a single
              parameter for future compatibility with IPv6.

              For the format, see the `socket` stdlib module.

    banner:   Startup message. Default is to show help for usage.
              To suppress, use banner="".

    To connect to the REPL server (assuming default settings)::

        python3 -m unpythonic.net.client localhost:1337

    **NOTE**: Currently, only one REPL server is supported per process,
    but it accepts multiple simultaneous connections. A new thread is
    spawned to serve each new connection.

    **CAUTION**: There is absolutely no authentication support, so it is
    recommended to only serve to localhost, and only on a machine whose
    users you trust.
    """
    # TODO: support IPv6
    addr, port = addrspec

    global _server_instance, _console_locals_namespace
    if _server_instance is not None:
        raise RuntimeError("The current process already has a running REPL server.")

    _console_locals_namespace = locals

    global _banner
    if banner is None:
        default_msg = ("Unpythonic REPL server at {addr}:{port}, on behalf of:\n"
                       "  {argv}\n"
                       "  Top-level assignments and definitions update the session locals;\n"
                       "  typically, these correspond to the globals of a module in the running app.\n"
                       "    quit() or EOF (Ctrl+D) at the prompt disconnects this session.\n"
                       "    halt() tells the server to close after the last session has disconnected.\n"
                       "    print() prints in the REPL session.\n"
                       "    server_print(...) prints on the stdout of the server.")
        _banner = default_msg.format(addr=addr, port=port, argv=" ".join(sys.argv))
    else:
        _banner = banner

    # Set the prompts.
    if not hasattr(sys, "ps1"):
        sys.ps1 = ">>> "
    if not hasattr(sys, "ps2"):
        sys.ps2 = "... "

    # We use a combo of Shim and ThreadLocalBox to redirect attribute lookups
    # to the thread-specific read/write streams.
    #
    # sys.stdin et al. are replaced by shims, which hold their targets in
    # thread-local boxes. In the main thread, the boxes contain the original
    # sys.stdin et al., whereas in session threads, the boxes are filled with
    # streams established for that particular session.
    sys.stdin = Shim(_threadlocal_stdin)
    sys.stdout = Shim(_threadlocal_stdout)
    sys.stderr = Shim(_threadlocal_stderr)

    # https://docs.python.org/3/library/socketserver.html#socketserver.BaseServer.server_address
    # https://docs.python.org/3/library/socketserver.html#socketserver.BaseServer.RequestHandlerClass
    server = ReuseAddrThreadingTCPServer((addr, port), ConsoleSession)
    # Set whether Python is allowed to exit even if there are connection threads alive.
    server.daemon_threads = True
    server_thread = threading.Thread(target=server.serve_forever, name="Unpythonic REPL server", daemon=True)
    server_thread.start()

    # control channel for remote tab completion and remote Ctrl+C requests
    # TODO: configurable port
    # Default is 8128 because it's for *completing* things, and https://en.wikipedia.org/wiki/Perfect_number
    # (This is the first one above 1024, and was already known to Nicomachus around 100 CE.)
    cserver = ReuseAddrThreadingTCPServer((addr, 8128), ControlSession)
    cserver.daemon_threads = True
    cserver_thread = threading.Thread(target=cserver.serve_forever, name="Unpythonic REPL remote tab completion server", daemon=True)
    cserver_thread.start()

    _server_instance = (server, server_thread, cserver, cserver_thread)
    atexit.register(stop)
    return addr, port


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
    addr, port = start(locals=globals())
    server_print("Started REPL server on {}:{}.".format(addr, port))
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
