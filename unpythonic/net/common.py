# -*- coding: utf-8; -*-

import json

from .msg import encodemsg

__all__ = ["ApplevelProtocol"]

class ApplevelProtocol:
    """Application-level communication protocol.

    We encode the payload as JSON encoded dictionaries, then encoded as utf-8
    text. The bytes are stuffed into a message using the `unpythonic.net.msg`
    low-level message protocol.

    This format was chosen instead of pickle to ensure the client and server
    can talk to each other regardless of the Python versions on each end of the
    connection.

    Transmission is synchronous; when one end is sending, the other one must be
    receiving. Both sending and receiving will block until success, or until
    the socket is closed.

    This can be used as a common base class for server/client object pairs.

    **NOTE**: The derived class must define two attributes:

      - `sock`: an open TCP socket connected to the peer to communicate with.

      - `decoder`: `unpythonic.net.msg.MessageDecoder` instance for receiving
        messages. Typically this is connected to `sock` using an
        `unpythonic.net.msg.socketsource`, like
        `MessageDecoder(socketsource(sock))`.

    These are left to the user code to define, because typically the client and
    server sides must handle this differently. The client can create `sock` and
    `decoder` in its constructor, whereas a TCP server typically inherits from
    `socketserver.BaseRequestHandler`, and receives an incoming connection in
    its `handle` method (which is then the official place to create any
    session-specific attributes).
    """
    def _send(self, data):
        """Send a message using the application-level protocol.

        data: dict-like.
        """
        json_data = json.dumps(data)
        bytes_out = json_data.encode("utf-8")
        self.sock.sendall(encodemsg(bytes_out))

    def _recv(self):
        """Receive a message using the application-level protocol.

        Returns a dict-like, or `None` if the decoder's message source
        signaled EOF.

        Blocks if no data is currently available at the message source,
        but EOF has not been signaled.
        """
        bytes_in = self.decoder.decode()
        if not bytes_in:
            return None
        json_data = bytes_in.decode("utf-8")
        return json.loads(json_data)
