"""REPL server for inspecting and hot-patching a running Python process.

This module makes your Python app serve up a REPL (read-eval-print-loop)
over TCP, somewhat like the Swank server in Common Lisp.

In a REPL session, you can inspect and mutate the global state of your running
program. You can e.g. replace top-level function definitions with new versions
in your running process.

To enable it in your app::

    from unpythonic.net import server
    server.start(locals=globals())

To connect to a running REPL server::

    python3 -m unpythonic.replclient localhost 1337

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

**CAUTION**: as Python was not designed for arbitrary hot-patching, if you
change a **class** definition, only new instances will use the new definition,
unless you specifically monkey-patch existing instances to change their type.
The language docs hint it is somehow possible to retroactively change an
object's type, if you're careful with it:
    https://docs.python.org/3/reference/requestmodel.html#id8

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
import json
import atexit

from ..collections import ThreadLocalBox, Shim
#from ..misc import async_raise

from .util import ReuseAddrThreadingTCPServer
from .msg import encodemsg, MessageDecoder, socketsource
from .ptyproxy import PTYSocketProxy

_server_instance = None
_active_connections = set()
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


class ControlSession(socketserver.BaseRequestHandler):
    """Entry point for connections to the control server.

    We use a separate connection for control to avoid head-of-line blocking.

    In a session, the client sends us requests for remote tab completion. We
    invoke `rlcompleter` on the server side, and return its response to the
    client.

    We encode the payload as JSON encoded dictionaries. This format was chosen
    instead of pickle to ensure the client and server can talk to each other
    regardless of the Python versions on each end of the connection.
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
            backend = rlcompleter.Completer(_console_locals_namespace)
            sock = self.request
            decoder = MessageDecoder(socketsource(sock))
            while True:
                # TODO: Add support for requests to inject Ctrl+C. Needs a command protocol layer.
                # TODO: Can use JSON dictionaries; we're guaranteed to get whole messages only.
                data_in = decoder.decode()
                if not data_in:
                    raise ClientExit
                request = json.loads(data_in.decode("utf-8"))
                reply = backend.complete(request["text"], request["state"])
                # server_print(request, reply)
                data_out = json.dumps(reply).encode("utf-8")
                sock.sendall(encodemsg(data_out))
        except ClientExit:
            server_print("Control channel for {} closed.".format(client_address_str))
        except BaseException as err:
            server_print(err)


class ConsoleSession(socketserver.BaseRequestHandler):
    """Entry point for connections from the TCP server."""
    def handle(self):
        # TODO: ipv6 support
        caddr, cport = self.client_address
        client_address_str = "{}:{}".format(caddr, cport)

        try:
            _active_connections.add(id(self))  # for exit monitoring

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

                    if _banner != "":
                        print(_banner)  # ...at the client side

                    self.console = code.InteractiveConsole(locals=_console_locals_namespace)

                    # All errors except SystemExit are caught inside interact(), only
                    # sys.exit() is escalated, in this situation we want to close the
                    # connection, not kill the server ungracefully. We have halt()
                    # to do that gracefully.
                    try:
                        server_print("Opening session for {}.".format(client_address_str))

                        # # TEST: Try injecting Ctrl+C with one of the dirtiest hacks ever...
                        # # (Yes, it works. The console gets a KeyboardInterrupt.
                        # # TODO: We should be able to use this to inject a Ctrl+C over the network,
                        # # but we need yet another connection (or maybe a general "control" channel
                        # # like IPython has, to support both tab completion and Ctrl+C) to listen
                        # # for requests to perform a Ctrl+C and then fire it when requested.
                        # # For that, we need to keep track of the thread object corresponding
                        # # to each session.)
                        # def stupid_test(target_thread):
                        #     time.sleep(3)
                        #     server_print("killzorz! {} is in for a Ctrl+C.".format(target_thread))
                        #     async_raise(target_thread, KeyboardInterrupt)
                        # testthread = threading.Thread(target=stupid_test, args=(threading.current_thread(),))
                        # testthread.start()

                        self.console.interact(banner=None, exitmsg="Bye.")
                    except SystemExit:
                        pass
                    finally:
                        server_print('Closing PTY on {} for client {}.'.format(os.ttyname(adaptor.slave), client_address_str))
                        adaptor.stop()
                        server_print("Closing session for {}.".format(client_address_str))
        except BaseException as err:
            server_print(err)
        finally:
            _active_connections.remove(id(self))


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

    # TODO: support multiple instances in the same process (use a dictionary to store instance data)
    global _server_instance, _console_locals_namespace
    if _server_instance is not None:
        raise RuntimeError("The current process already has a running REPL server.")

    _console_locals_namespace = locals

    global _banner
    if banner is None:
        # TODO: get name of module whose globals the session can update
        default_msg = ("Unpythonic REPL server at {addr}:{port}, on behalf of:\n"
                       "  {argv}\n"
                       "  Top-level assignments and definitions update the module's globals.\n"
                       "    quit() or EOF (Ctrl+D) at the prompt disconnects this session.\n"
                       "    halt() tells the server to close after the last session has disconnected.\n"
                       "    print() prints in the REPL session.\n"
                       "    server_print(...) prints on the stdout of the server.")
        _banner = default_msg.format(addr=addr, port=port, argv=" ".join(sys.argv))
    else:
        _banner = banner

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


# demo app
def main():
    server_print("REPL server starting...")
    addr, port = start(locals=globals())
    server_print("Started REPL server on {}:{}.".format(addr, port))
    try:
        while True:
            time.sleep(1)
            if _halt_pending and not _active_connections:
                break
        server_print("REPL server closed.")
    except KeyboardInterrupt:
        server_print("Server process got Ctrl+C, closing REPL server and all connections NOW.")

if __name__ == '__main__':
    main()
