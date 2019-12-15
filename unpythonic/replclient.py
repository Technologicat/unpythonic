# -*- coding: utf-8; -*-
"""Simple client for the REPL server, with remote tab completion."""

import readline  # noqa: F401, input() uses the readline module if it has been loaded.
import socket
import json
import select
import sys
import threading

__all__ = ["connect"]


def _make_remote_completion_client(sock):
    """Make a tab completion function for a remote REPL session.

    `sock` must be a socket already connected to a `RemoteTabCompletionServer`.
    The caller is responsible for managing the socket.

    The return value can be used as a completer in `readline.set_completer`.
    """
    def complete(text, state):
        try:
            request = {"text": text, "state": state}
            data_out = json.dumps(request).encode("utf-8")
            sock.send(data_out)
            # TODO: is there a race condition here? How to ensure we don't begin reading until the server is done writing?
            data_in = sock.recv(4096).decode("utf-8")
            # print("text '{}' state '{}' reply '{}'".format(text, state, data_in))
            if not data_in:
                print("Tab completion server exited, socket closed!")
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
    """
    class SessionExit(Exception):
        pass
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:  # remote REPL session
            sock.connect(addrspec)

            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as csock:  # remote tab completion
                # TODO: configurable tab completion port
                csock.connect((addrspec[0], 8128))  # TODO: IPv6 support

                # Set a custom tab completer for readline.
                # https://stackoverflow.com/questions/35115208/is-there-any-way-to-combine-readline-rlcompleter-and-interactiveconsole-in-pytho
                completer = _make_remote_completion_client(csock)
                readline.set_completer(completer)
                readline.parse_and_bind("tab: complete")

                def sock_to_stdout():
                    try:
                        while True:
                            rs, ws, es = select.select([sock], [], [])
                            for r in rs:
                                data = sock.recv(4096)
                                if len(data) == 0:
                                    print("replclient: EOF on network socket, exiting.")
                                    raise SessionExit
                                sys.stdout.write(data.decode("utf-8"))
                    except SessionExit:
                        pass
                t = threading.Thread(target=sock_to_stdout, daemon=True)
                t.start()

                # TODO: fix multiline editing (see repl_tool.py in socketserverREPL for reference)

                # Run readline at the client side. (Only the tab completion
                # results come from the server.)
                #
                # Important: this must be outside the forwarder loop (since
                # there will be multiple events on stdin for each line sent),
                # so we use a different thread (here specifically, the main
                # thread).
                while True:
                    inp = input()
                    if len(inp) == 0:
                        print("replclient: EOF on stdin, exiting.")
                        raise SessionExit
                    sock.send((inp + "\n").encode("utf-8"))

    except KeyboardInterrupt:
        print("replclient: KeyboardInterrupt, exiting.")
    except SessionExit:
        pass


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
