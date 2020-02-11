# -*- coding: utf-8; -*-
"""Simple client for the REPL server, with remote tab completion and Ctrl+C.

A second TCP connection on a different port is used as a control channel for
the remote tab completion and Ctrl+C requests.

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
import re
import time

from .msg import MessageDecoder
from .util import socketsource, ReceiveBuffer
from .common import ApplevelProtocolMixin

__all__ = ["connect"]


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


def connect(host, repl_port, control_port):
    """Connect to a remote REPL server.

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
            csock.connect((host, control_port))  # TODO: IPv6 support
            controller = ControlClient(csock)

            # Get prompts for use with input()
            metadata = controller.describe_server()
            ps1 = metadata["prompts"]["ps1"]
            ps2 = metadata["prompts"]["ps2"]
            bps1 = ps1.encode("utf-8")
            bps2 = ps2.encode("utf-8")

            # Set up remote tab completion, using a custom completer for readline.
            # https://stackoverflow.com/questions/35115208/is-there-any-way-to-combine-readline-rlcompleter-and-interactiveconsole-in-pytho
            readline.set_completer(controller.complete)
            readline.parse_and_bind("tab: complete")  # TODO: do we need to call this, PyPy doesn't support it?

            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:  # remote REPL session
                sock.connect((host, repl_port))  # TODO: IPv6 support

                # TODO: refactor. This is partial copypasta from unpythonic.net.msg.decodemsg.
                src = socketsource(sock)
                buf = ReceiveBuffer()
                def read_more_input():
                    try:
                        data = next(src)
                    except StopIteration:
                        raise EOFError
                    buf.append(data)
                    return buf.getvalue()

                # The first line of text contains the session id.
                # We can't use the message protocol; this information must arrive on the primary channel.
                # So we read input until the first newline, storing it all to be printed later.
                try:
                    val = buf.getvalue()
                    while True:
                        if b"\n" in val:
                            text = val.decode("utf-8")
                            first_line, *rest = text.split("\n")
                            matches = re.findall(r"session (\d+) connected", first_line)
                            assert len(matches) == 1, "Expected server to print session id on the first line"
                            repl_session_id = int(matches[0])
                            break
                        val = read_more_input()
                except EOFError:
                    print("unpythonic.net.client: disconnected by server.")
                    raise SessionExit
                controller.pair_with_session(repl_session_id)

                # We run readline at the client side. Only the tab completion
                # results come from the server, via the custom remote completer.
                #
                # The first time for each "R" in "REPL", the input prompt is
                # sent by the server, but then during line editing, it needs to
                # be re-printed by `readline`, so `input` needs to know what
                # the prompt text should be.
                #
                # So at our end, `input` should be the one to print the prompt.
                #
                # For this, we read the socket until we see a new prompt,
                # and then switch from the "P" in "REPL" to the "R" and "E".
                #
                val = buf.getvalue()
                while True:  # The "L" in the "REPL"
                    try:
                        # Wait for the prompt.
                        #
                        # We rely on the fact that it's always the last thing the console sends
                        # before listening for more input.
                        #
                        # TODO: The current implementation leaves one race condition that can't be solved easily.
                        # If the prompt string appears in the data stream, but is not actually a prompt,
                        # we might interpret it as a prompt, and things will go south from there.
                        #
                        # This only happens when partial data recv'd on the socket ends exactly at the end of
                        # the prompt string (e.g. ">>>"). So it's unlikely, but it may happen.
                        #
                        # The at-a-glance-almost-correct hack of prefixing bps1 and bps2 with b"\n" doesn't
                        # work, because the newline won't be there when we handle the server's response to a
                        # `KeyboardInterrupt` request. So doing that would cause the client to hang.
                        #
                        # As a semi-working hack, our server sets its prompts to ">>>>" and "...." (like PyPy
                        # does). Whereas "..." may appear in Python code or English, these strings usually don't.
                        if val.endswith(bps1) or val.endswith(bps2):
                            # "P"
                            text = val.decode("utf-8")
                            prompt = ps1 if text.endswith(ps1) else ps2
                            text = text[:-len(prompt)]
                            sys.stdout.write(text)
                            buf.set(b"")

                            # "R", "E" (but evaluate remotely)
                            try:
                                inp = input(prompt)
                                sock.sendall((inp + "\n").encode("utf-8"))
                            except EOFError:
                                print("unpythonic.net.client: Ctrl+D pressed, asking server to disconnect.")
                                print("unpythonic.net.client: if the server does not respond, press Ctrl+C to force.")
                                try:
                                    print("quit()")  # local echo
                                    sock.sendall("quit()\n".encode("utf-8"))
                                except KeyboardInterrupt:
                                    print("unpythonic.net.client: Ctrl+C pressed, forcing disconnect.")
                                finally:
                                    raise SessionExit
                            except BrokenPipeError:
                                print("unpythonic.net.client: socket closed unexpectedly, exiting.")
                                raise SessionExit

                        else:  # no prompt yet, just print whatever came in, and clear the buffer
                            text = val.decode("utf-8")
                            sys.stdout.write(text)
                            buf.set(b"")

                        val = read_more_input()

                    # TODO: It's very difficult to get this 100% right, and right now we don't even try.
                    # The problem is that KeyboardInterrupt may occur on any line of code here, so we may
                    # lose some text, or print some twice, depending on the exact moment Ctrl+C is pressed.
                    except KeyboardInterrupt:
                        controller.send_kbinterrupt()
                        # When KeyboardInterrupt occurs, the server will send
                        # the string "KeyboardInterrupt" and a new prompt when
                        # we send a blank line to it (but sending the blank line
                        # seems to be mandatory for that to happen).
                        sock.sendall(("\n").encode("utf-8"))

                        # If the interrupt happened inside read_more_input, it has closed the socketsource
                        # by terminating the generator that was blocking on its internal select() call.
                        # So let's re-instantiate the socketsource, just to be safe.
                        #
                        # (This cannot lose data, since the source object itself has no buffer. There is
                        # an app-level buffer in ReceiveBuffer, and the underlying socket has a buffer,
                        # but at the level of the "source" abstraction, there is no buffer.)
                        #
                        # PyPy recommends closing generators explicitly when not needed anymore,
                        # but not exhausted, instead of leaving the instance lying around to be
                        # picked up by the GC some time later (if ever). CPython's refcounting GC
                        # of course picks it up immediately when the last reference goes out of scope.
                        #
                        # I have no idea if that piece of advice applies also when a generator exits
                        # due to an exception. Probably not (control has escaped the body of that
                        # generator instance permanently, right?), but closing it shouldn't hurt,
                        # because when a generator has already exited, close() is a no-op. See:
                        #    https://amir.rachum.com/blog/2017/03/03/generator-cleanup/
                        #    https://www.python.org/dev/peps/pep-0342/
                        src.close()
                        src = socketsource(sock)

                        # Process the server's response to the blank line.
                        #
                        # TODO: Fix this mess properly. Hacking it for now. This would really benefit
                        # TODO: from trying harder to understand WTF is going on.
                        #
                        # It seems that:
                        #   - If the Ctrl+C arrives when at the prompt, the server sends back one batch of data.
                        #     The response is essentially the text "KeyboardInterrupt", and a new prompt.
                        #   - If the Ctrl+C arrives when the server is actually running some code, it sends
                        #     back two responses, with a small delay in between. We may get two new prompts.
                        #
                        # Currently, to work around this, we gather incoming data, until the server stops
                        # hiccuping in response to the Ctrl+C. This won't likely work over a congested network,
                        # where our arbitrary delay is just too short, but responsiveness for localhost use
                        # is important.
                        #
                        # A good test snippet for the REPL is::
                        #     for _ in range(int(1e9)):
                        #       pass
                        # This should give enough time to hit Ctrl+C with the loop still running.
                        def hasdata(sck):
                            rs, ws, es = select.select([sck], [], [], 0)
                            return rs
                        val = read_more_input()
                        while True:
                            time.sleep(0.1)
                            if not hasdata(sock):
                                break
                            val = read_more_input()

    except SessionExit:
        print("Session closed.")

    except EOFError:
        print("unpythonic.net.client: disconnected by server.")


# TODO: IPv6 support
# https://docs.python.org/3/library/socket.html#example
def main():
    if len(sys.argv) < 2:
        print("USAGE: {} host [repl_port] [control_port]".format(sys.argv[0]))
        print("By default, repl_port=1337, control_port=8128.")
        sys.exit(255)
    host = sys.argv[1]
    rport = int(sys.argv[2]) if len(sys.argv) >= 3 else 1337
    cport = int(sys.argv[3]) if len(sys.argv) >= 4 else 8128
    connect(host, rport, cport)

if __name__ == '__main__':
    main()
