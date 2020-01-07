# -*- coding: utf-8; -*-
"""Simple client for the REPL server, with remote tab completion and Ctrl+C.

A second TCP connection (on port 8128) is used as a control channel for the
remote tab completion and Ctrl+C requests.

**CAUTION**: The current client implementation is silly and over-complicated.

What we really want is a dumb connection that forwards keypresses one by one,
and as far as the server is concerned, looks and acts exactly like a TTY.

What we instead have is an overengineered and brittle client that has a
separate client-side `input()` loop, with a client-side GNU readline (with a
custom tab completer that requests completions from the server side), and a
setup to translate Ctrl+C to a remote procedure call. (With one of the dirtiest
hacks ever, on the server side, to raise KeyboardInterrupt in the session thread.)

But no combination of `netcat`, `stty` and `rlwrap` seems to give what we want.
It doesn't seem to matter that the server actually does connect a PTY to the
stdin/stdout streams of the `code.InteractiveConsole` that provides the REPL
session. So to hell with it, let's build a ***ing client.

(Things tried include `stty raw`, `stty -icanon -echo`, and `stty -icanon`.
For example, `stty -icanon && rlwrap nc localhost 1337`. If you play around
with `stty`, the incantation `stty sane` may be useful to restore your terminal
back to a working state.

Another issue here is that Python's `readline` module seems to be hardwired to
use the original stdin/stdout; it doesn't care if we mutate `sys.stdin` or
`sys.stdout`. So we couldn't use the server side's `readline` even if we
had a dumb connection; the client must supply its own. Which implies the need
for a remote tab completer, and a separate client-side `input()` loop.)
"""

import readline  # noqa: F401, input() uses the readline module if it has been loaded.
import socket
import select
import sys
import signal
import threading

from .msg import MessageDecoder
from .util import socketsource
from .common import ApplevelProtocolMixin

__all__ = ["connect"]


# Install system signal handler for forcibly terminating the stdin input() when
# an EOF is received on the socket in the other thread.
# https://en.wikiversity.org/wiki/Python_Concepts/Console_Input#Detecting_timeout_on_stdin
# https://docs.python.org/3/library/signal.html
def _handle_alarm(signum, frame):
    sys.exit(255)  # we will actually catch this.
signal.signal(signal.SIGALRM, _handle_alarm)


# Protocol for establishing a paired control/REPL connection:
#  - 1: Handshake: open the control channel, ask for metadata (prompts: sys.ps1, sys.ps2)
#       to configure the client's prompt detector before opening the primary channel.
#       - To keep us netcat compatible, the handshake is optional. It is legal
#         to just immediately connect on the primary channel, in which case
#         there will be no control channel paired with the REPL session.
#  - 2: Open the primary channel. Parse the session id from the first line of text.
#       - To keep us netcat compatible, we must transmit the session id as
#         part of the primary data stream; it cannot be packaged into a message
#         since only `unpythonic` knows about the message protocol, and the
#         REPL and control session server objects operate independently
#         (they must, since each accepts a separate incoming TCP connection,
#         which have nothing to do with each other).
#       - So, the server prints "session XX connected\n" on the first line
#         when a client connects. The client parses the first line (beside
#         printing it as usual, to have the same appearance for both unpythonic
#         client and netcat connections).
#  - 3: Send a command on the control channel to pair that control channel
#       to session id XX.

# Messages must be processed by just one central decoder, to prevent data
# races, but also to handle buffering of incoming data correctly, because
# the underlying transport (TCP) has no notion of message boundaries. Thus
# typically, at the seam between two messages, some of the data belonging
# to the beginning of the second message has already arrived and been read
# from the socket, when trying to read the last batch of data belonging to
# the end of the first message.
class ControlClient(ApplevelProtocolMixin):
    # TODO: manage the socket internally. We need to make this into a context manager,
    # so that __enter__ can set up the socket and __exit__ can tear it down.
    def __init__(self, sock):
        """Initialize session for control channel (client side).

        `sock` must be a socket connected to a `ControlSession` at the remote.
        The caller is responsible for managing the socket.
        """
        self.sock = sock
        # The source is just an abstraction over the details of how to actually
        # read data from a specific type of message source; buffering occurs in
        # ReceiveBuffer inside MessageDecoder.
        self.decoder = MessageDecoder(socketsource(sock))

    # This belongs only to the client side of the application-level protocol,
    # so it lives here, not in ApplevelProtocolMixin.
    def _remote_execute(self, request):
        """Send a command to the server, get the reply.

        request: a dict-like, containing the "command" field and any required
                 parameters (specific to each particular command).

        On success, return the `reply` dict. On failure, return `None`.
        """
        try:
            self._send(request)
            reply = self._recv()
            if not reply:
                print("Socket closed by server.")
                return None
            if reply["status"] == "ok":
                return reply
            elif reply["status"] == "failed":
                if "reason" in reply:
                    print("Server command failed, reason: {}".format(reply["reason"]))
        except BaseException as err:
            print(type(err), err)
        return None

    def describe_server(self):
        """Return server metadata such as prompt settings and version."""
        return self._remote_execute({"command": "DescribeServer"})

    def pair_with_session(self, session_id):
        """Pair this control channel with a REPL session."""
        return self._remote_execute({"command": "PairWithSession", "id": session_id})

    def complete(self, text, state):
        """Tab-complete in a remote REPL session.

        This is a completer for `readline.set_completer`.
        """
        reply = self._remote_execute({"command": "TabComplete", "text": text, "state": state})
        if reply:
            return reply["result"]
        return None

    def send_kbinterrupt(self):
        """Request the server to perform a `KeyboardInterrupt` (Ctrl+C).

        The `KeyboardInterrupt` occurs in the REPL session paired with
        this control channel.

        Returns truthy on success, falsey on failure.
        """
        return self._remote_execute({"command": "KeyboardInterrupt"})


def connect(addrspec):
    """Connect to a remote REPL server.

    `addrspec` is passed to `socket.connect`. For IPv4, it is the tuple
    `(ip_or_hostname, port)`.

    To disconnect politely, send `exit()`, or as a shortcut, press Ctrl+D.
    This asks the server to terminate the REPL session, and is the official
    way to exit cleanly.

    To disconnect forcibly, follow it with a Ctrl+C. This just drops the
    connection immediately. (The server should be smart enough to notice
    the client is gone, and clean up any relevant resources.)
    """
    class SessionExit(Exception):
        pass
    try:
        # First handshake on control channel to get prompt information.
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as csock:  # control channel (remote tab completion, remote Ctrl+C)
            # TODO: configurable control port
            csock.connect((addrspec[0], 8128))  # TODO: IPv6 support
            controller = ControlClient(csock)

            # TODO: use the prompts information in calls to input()
            metadata = controller.describe_server()
            # print(metadata["prompts"])

            # Set up remote tab completion, using a custom completer for readline.
            # https://stackoverflow.com/questions/35115208/is-there-any-way-to-combine-readline-rlcompleter-and-interactiveconsole-in-pytho
            readline.set_completer(controller.complete)
            readline.parse_and_bind("tab: complete")

            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:  # remote REPL session
                sock.connect(addrspec)

                # TODO: refactor
                # The first line of text contains the session id.
                # We can't use the message protocol; this information must arrive on the primary channel.
                rs, ws, es = select.select([sock], [], [])
                for r in rs:
                    data = sock.recv(4096)
                    if len(data) == 0:
                        print("unpythonic.net.client: disconnected by server.")
                        raise SessionExit
                    text = data.decode("utf-8")
                    sys.stdout.write(text)
                    if "\n" in text:
                        first_line, *rest = text.split("\n")
                        import re
                        matches = re.findall(r"session (\d+) connected", first_line)
                        assert len(matches) == 1, "Expected server to print session id on the first line"
                        repl_session_id = int(matches[0])
                    else:
                        # TODO: make sure we always receive a whole line
                        assert False
                controller.pair_with_session(repl_session_id)

                # TODO: This can't be a separate thread, we must listen for input only when a prompt has appeared.
                def sock_to_stdout():
                    try:
                        while True:
                            rs, ws, es = select.select([sock], [], [])
                            for r in rs:
                                data = sock.recv(4096)
                                if len(data) == 0:
                                    print("unpythonic.net.client: disconnected by server.")
                                    raise SessionExit
                                text = data.decode("utf-8")
                                sys.stdout.write(text)
                    except SessionExit:
                        # Exit also in main thread, which is waiting on input() when this happens.
                        signal.alarm(1)
                t = threading.Thread(target=sock_to_stdout, daemon=True)
                t.start()

                # TODO: fix prompts in multiline inputs (see repl_tool.py in socketserverREPL for reference)
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
                            controller.send_kbinterrupt()
                except EOFError:
                    print("unpythonic.net.client: Ctrl+D pressed, asking server to disconnect.")
                    print("unpythonic.net.client: if the server does not respond, press Ctrl+C to force.")
                    try:
                        print("quit()")  # local echo
                        sock.sendall("quit()\n".encode("utf-8"))
                        t.join()  # wait for the EOF response
                    except KeyboardInterrupt:
                        print("unpythonic.net.client: Ctrl+C pressed, forcing disconnect.")
                    finally:
                        raise SessionExit
                except SystemExit:  # catch the alarm signaled by the socket-listening thread.
                    raise SessionExit
                except BrokenPipeError:
                    print("unpythonic.net.client: socket closed unexpectedly, exiting.")
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
