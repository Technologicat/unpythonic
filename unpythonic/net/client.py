# -*- coding: utf-8; -*-
"""Simple client for the REPL server, with remote tab completion."""

import readline  # noqa: F401, input() uses the readline module if it has been loaded.
import socket
import json
import select
import sys
import signal
import threading

from .msg import mkrecvbuf, socketsource, decodemsg, sendmsg

__all__ = ["connect"]


# Install system signal handler for forcibly terminating the stdin input() when
# an EOF is received on the socket in the other thread.
# https://en.wikiversity.org/wiki/Python_Concepts/Console_Input#Detecting_timeout_on_stdin
# https://docs.python.org/3/library/signal.html
def _handle_alarm(signum, frame):
    sys.exit(255)  # we will actually catch this.
signal.signal(signal.SIGALRM, _handle_alarm)


# Note we must use one recvbuf per control connection, even if several
# functionalities receive messages on that connection.
def _make_remote_completion_client(buf, sock):
    """Make a tab completion function for a remote REPL session.

    `buf` is a receive buffer for the message protocol (see
    `unpythonic.net.util.mkrecvbuf`).

    `sock` must be a socket already connected to a `ControlSession`.
    The caller is responsible for managing the socket.

    The return value can be used as a completer in `readline.set_completer`.
    """
    # Wrap the socket into a message source just once, and then use `decodemsg`
    # instead of `recvmsg` (which wraps the socket in a new message source
    # instance each time). The source is just an abstraction over the details
    # of how to actually read data from a specific type of data source;
    # buffering occurs in the receive buffer `buf`.
    source = socketsource(sock)
    def complete(text, state):
        try:
            request = {"text": text, "state": state}
            data_out = json.dumps(request).encode("utf-8")
            sendmsg(data_out, sock)
            data_in = decodemsg(buf, source).decode("utf-8")
            # print("text '{}' state '{}' reply '{}'".format(text, state, data_in))
            if not data_in:
                print("Control server exited, socket closed!")
                return None
            reply = json.loads(data_in)
            return reply
        except BaseException as err:
            print(type(err), err)
        return None
    return complete


def connect(addrspec):
    """Connect to a remote REPL server.

    `addrspec` is passed to `socket.connect`. For IPv4, it is the tuple
    `(ip_or_hostname, port)`.

    To disconnect politely, send `exit()`, or as a shortcut, press Ctrl+D.
    This asks the server to terminate the REPL session, and is the official
    way to exit cleanly.

    To disconnect forcibly, press Ctrl+C. This just drops the connection
    immediately. (The server should be smart enough to notice the client
    is gone, and clean up any relevant resources.)
    """
    class SessionExit(Exception):
        pass
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:  # remote REPL session
            sock.connect(addrspec)

            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as csock:  # control channel (remote tab completion, remote Ctrl+C)
                # TODO: configurable control port
                csock.connect((addrspec[0], 8128))  # TODO: IPv6 support

                # Set a custom tab completer for readline.
                # https://stackoverflow.com/questions/35115208/is-there-any-way-to-combine-readline-rlcompleter-and-interactiveconsole-in-pytho
                cbuf = mkrecvbuf()
                completer = _make_remote_completion_client(cbuf, csock)
                readline.set_completer(completer)
                readline.parse_and_bind("tab: complete")

                def sock_to_stdout():
                    try:
                        while True:
                            rs, ws, es = select.select([sock], [], [])
                            for r in rs:
                                data = sock.recv(4096)
                                if len(data) == 0:
                                    print("replclient: disconnected by server.")
                                    raise SessionExit
                                sys.stdout.write(data.decode("utf-8"))
                    except SessionExit:
                        # Exit also in main thread, which is waiting on input() when this happens.
                        signal.alarm(1)
                t = threading.Thread(target=sock_to_stdout, daemon=True)
                t.start()

                # TODO: fix multiline editing (see repl_tool.py in socketserverREPL for reference)
                #
                # This needs prompt detection so we'll know how to set up
                # `input`. The first time on a new line, the prompt is sent
                # by the server, but then during line editing, it needs to be
                # re-printed by `readline`, so `input` needs to know what the
                # prompt text should be.
                #
                # For this, we need to read the socket until we see a new prompt.

                # Run readline at the client side. Only the tab completion
                # results come from the server.
                #
                # Important: this must be outside the forwarder loop (since
                # there will be multiple events on stdin for each line sent),
                # so we use a different thread (here specifically, the main
                # thread).
                try:
                    while True:
                        try:
                            inp = input()
                            sock.sendall((inp + "\n").encode("utf-8"))
                        except KeyboardInterrupt:
                            # TODO: refactor control channel logic; send command on control channel
                            sock.sendall("\x03\n".encode("utf-8"))
                except EOFError:
                    print("replclient: Ctrl+D pressed, asking server to disconnect.")
                    print("replclient: if the server does not respond, press Ctrl+C to force.")
                    try:
                        print("quit()")  # local echo
                        sock.sendall("quit()\n".encode("utf-8"))
                        t.join()  # wait for the EOF response
                    except KeyboardInterrupt:
                        print("replclient: Ctrl+C pressed, forcing disconnect.")
                    finally:
                        raise SessionExit
                except SystemExit:  # catch the alarm signaled by the socket-listening thread.
                    raise SessionExit
                except BrokenPipeError:
                    print("replclient: socket closed unexpectedly, exiting.")
                    raise SessionExit

    except SessionExit:
        print("Session closed.")


# TODO: IPv6 support
# https://docs.python.org/3/library/socket.html#example
def main():
    if len(sys.argv) != 2:
        print(f"USAGE: {sys.argv[0]} host:port")
        sys.exit(255)
    host, port = sys.argv[1].split(":")
    port = int(port)
    connect((host, port))

if __name__ == '__main__':
    main()
