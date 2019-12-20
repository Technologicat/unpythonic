"""REPL server for inspecting and hot-patching a running Python process.

This module makes your Python app serve up a REPL (read-eval-print-loop)
over TCP, somewhat like the Swank server in Common Lisp.

In a REPL session, you can inspect and mutate the global state of your running
program. You can e.g. replace top-level function definitions with new versions
in your running process.

To enable it in your app::

    from unpythonic import server
    server.start()

To connect to a running REPL server::

    python3 -m unpythonic.replclient localhost 1337

If you're already running in a local Python REPL, this should also work::

    from unpythonic import replclient
    replclient.connect(("127.0.0.1", 1337))

For basic use (history, but no tab completion), you can use::

    rlwrap netcat localhost 1337

or even just (no history, no tab completion)::

    netcat localhost 1337

The REPL is scoped to the top-level scope of the module from which you call
`server.start()`. The REPL sessions have write access to that module's globals;
that's the whole point of this tool.

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
# TODO: support several server instances (makes sense if each is connected to a different module)
# TODO: support syntactic macros
#   TODO: macro expander
#   TODO: per-session macro definitions like in imacropy
#   TODO: import macro stubs for inspection like in imacropy
#   TODO: helper magic function macros() to list currently enabled macros
# TODO: history fixes (see repl_tool in socketserverREPL), syntax highlight?

try:
    import ctypes
except ImportError:  # not on CPython
    ctypes = None

import code
import rlcompleter  # yes, just rlcompleter without readline; backend for remote tab completion.
import threading
import sys
import os
import select
import time
import socket
import socketserver
import json
import atexit

from .ptyproxy import PTYSocketProxy
from ..collections import ThreadLocalBox, Shim
#from ..misc import async_raise

_server_instance = None
_active_connections = set()
_halt_pending = False
_original_stdin = sys.stdin
_original_stdout = sys.stdout
_original_stderr = sys.stderr
_stdin_streams = ThreadLocalBox(sys.stdin)
_stdout_streams = ThreadLocalBox(sys.stdout)
_stderr_streams = ThreadLocalBox(sys.stderr)
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

# TODO: do we really need this class? Could we tune things just a bit and use the original InteractiveConsole?
# TODO: The main thing is, we want to exit on empty input and the default one doesn't do that.
# TODO: Otherwise with our current stream proxy setup the stdlib class works just fine.
class StreamInteractiveConsole(code.InteractiveConsole):
    def __init__(self, rfile, wfile, locals=None):
        """Interactive REPL console, communicating over a pair of streams.

        `rfile` and `wfile` are the input and output streams to use, respectively.
        """
        code.InteractiveConsole.__init__(self, locals)
        self.rfile = rfile
        self.wfile = wfile
        if _banner != "":
            print(_banner)

    # https://docs.python.org/3/library/code.html#code.InteractiveInterpreter.write
    def write(self, request):
        """Write request to stderr of this REPL session.

        See `InteractiveInterpreter.write`.
        """
        if not self.wfile.closed:
            self.wfile.write(request.encode('utf-8'))
            self.wfile.flush()

    # https://docs.python.org/3/library/code.html#code.InteractiveConsole.raw_input
    def raw_input(self, prompt=""):
        """Write a prompt and read a line.

        See `InteractiveConsole.raw_input`.
        """
        if self.wfile.closed:
            raise EOFError("Socket closed.")

        self.write(prompt)

        raw_value = self.rfile.readline().rstrip()
        str_value = raw_value.decode('utf-8')

        # The default repl quits on Ctrl-D; pressing Ctrl-D sends the line
        # typed so far. Having the sys.ps2 prompt means we are on a
        # continuation line. An empty continuation line should just end the
        # current command, but an empty first line should close the session.
        if len(str_value) == 0 and prompt != sys.ps2:
            raise EOFError("Empty input, disconnect requested by client.")

        return str_value


class RemoteTabCompletionSession(socketserver.BaseRequestHandler):
    """Entry point for connections to the remote tab completion server.

    In a session, a `RemoteTabCompletionClient` sends us requests. We invoke
    `rlcompleter` on the server side, and return its response to the client.

    For communication, we use JSON encoded dictionaries. This format was chosen
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
            server_print("Remote tab completion session for {} opened.".format(client_address_str))
            # TODO: fancier backend? See examples in https://pymotw.com/3/readline/
            # TODO: grab correct globals namespace, must be the same the REPL session uses.
            backend = rlcompleter.Completer(globals())
            sock = self.request
            while True:
                rs, ws, es = select.select([sock], [], [])
                for r in rs:
                    data_in = sock.recv(4096).decode("utf-8")
                    if len(data_in) == 0:  # EOF on network socket
                        raise ClientExit
                    request = json.loads(data_in)
                    reply = backend.complete(request["text"], request["state"])
                    # server_print(request, reply)
                    data_out = json.dumps(reply).encode("utf-8")
                    sock.send(data_out)
        except ClientExit:
            server_print("Remote tab completion session for {} closed.".format(client_address_str))
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

            def on_slave_disconnect(adaptor):
                server_print('PTY on {} for client {} disconnected by PTY slave.'.format(os.ttyname(adaptor.slave), client_address_str))
            def on_socket_disconnect(adaptor):
                server_print('PTY on {} for client {} disconnected by client.'.format(os.ttyname(adaptor.slave), client_address_str))
                os.write(adaptor.master, "exit()\n".encode("utf-8"))
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
                    _stdin_streams << rfile
                    _stdout_streams << wfile
                    _stderr_streams << wfile

                    # TODO: Capture the reference to the calling module's globals dictionary, not ours.
                    # TODO: We could just stash it in a global here, since there's only one REPL server per process.
                    # self.console = StreamInteractiveConsole(rfile, wfile,
                    #                                         locals=globals())
                    self.console = code.InteractiveConsole(locals=globals())  # works except no exit on Ctrl+D

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


# https://docs.python.org/3/library/socketserver.html#socketserver.ThreadingTCPServer
# https://docs.python.org/3/library/socketserver.html#socketserver.ThreadingMixIn
# https://docs.python.org/3/library/socketserver.html#socketserver.TCPServer
class ReuseAddrThreadingTCPServer(socketserver.ThreadingTCPServer):
    def server_bind(self):
        """Custom server_bind ensuring the socket is available for rebind immediately."""
        # from https://stackoverflow.com/a/18858817
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.socket.bind(self.server_address)


# TODO: extract the correct globals namespace
# TODO: allow multiple REPL servers in the same process? (Use a dictionary.)
def start(addr=None, port=1337, banner=None):
    """Start the REPL server.

    addr: Server TCP address (default None, meaning localhost)
    port: TCP port to listen on (default 1337)
    banner: startup message. Default is to show help for usage.
            To suppress, use banner="".

    To connect to the REPL server (assuming default settings)::

        telnet localhost 1337

    **NOTE**: Currently, only one REPL server is supported per process.
    Only one is needed; it accepts multiple simultaneous connections.
    A new thread is spawned to serve each new connection.

    **CAUTION**: There is absolutely no authentication support, so it is
    recommended to only serve to localhost, and only on a machine whose
    users you trust.
    """
    # TODO: support multiple instances in the same process
    global _server_instance
    if _server_instance is not None:
        raise RuntimeError("The current process already has a running REPL server.")

    addr = addr or "127.0.0.1"  # TODO: support ipv6, too

    global _banner
    if banner is None:
        # TODO: get name of module whose globals the session can update
        default_msg = ("Unpythonic REPL server at {addr}:{port}, on behalf of:\n"
                       "  {argv}\n"
                       "  Top-level assignments and definitions update the module's globals.\n"
                       "    exit() or a blank command disconnects this session.\n"
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
    # thread-local boxes.
    sys.stdin = Shim(_stdin_streams)
    sys.stdout = Shim(_stdout_streams)
    sys.stderr = Shim(_stderr_streams)

    # https://docs.python.org/3/library/socketserver.html#socketserver.BaseServer.server_address
    # https://docs.python.org/3/library/socketserver.html#socketserver.BaseServer.RequestHandlerClass
    server = ReuseAddrThreadingTCPServer((addr, port), ConsoleSession)
    # Set whether Python is allowed to exit even if there are connection threads alive.
    server.daemon_threads = True
    server_thread = threading.Thread(target=server.serve_forever, name="Unpythonic REPL server", daemon=True)
    server_thread.start()

    # remote tab completion server
    # TODO: configurable tab completion port
    cserver = ReuseAddrThreadingTCPServer((addr, 8128), RemoteTabCompletionSession)
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
    global _server_instance
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
        atexit.unregister(stop)


# demo app
def main():
    server_print("REPL server starting...")
    addr, port = start()
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
