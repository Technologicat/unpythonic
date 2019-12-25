# -*- coding: utf-8; -*-
"""Utilities for networking."""

__all__ = ["ReuseAddrThreadingTCPServer",
           "recvall",
           "netstringify"]

import socket
import socketserver
from io import BytesIO

# https://docs.python.org/3/library/socketserver.html#socketserver.ThreadingTCPServer
# https://docs.python.org/3/library/socketserver.html#socketserver.ThreadingMixIn
# https://docs.python.org/3/library/socketserver.html#socketserver.TCPServer
class ReuseAddrThreadingTCPServer(socketserver.ThreadingTCPServer):
    def server_bind(self):
        """Custom server_bind ensuring the socket is available for rebind immediately."""
        # from https://stackoverflow.com/a/18858817
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.socket.bind(self.server_address)

def recvall(n, sock):
    """Receive **exactly** `n` bytes from a socket.

    Missing battery for the stdlib `socket` module (compare `socket.sendall`).

    Returns a `bytes` object containing the bytes read, or `None` if the socket
    is closed by the other end before `n` bytes have been received.

    See:
        http://stupidpythonideas.blogspot.com/2013/05/sockets-are-byte-streams-not-data.html
    """
    buf = BytesIO()
    while n:
        data = sock.recv(n)
        if not data:
            return None
        buf.write(data)
        n -= len(data)
    return buf.getvalue()

def netstringify(data):
    """Return a `bytes` object of `data` (also `bytes`), converted into a netstring."""
    if not isinstance(data, bytes):
        raise TypeError("Data must be bytes; got {} with value '{}'".format(type(data), data))
    n = len(data)
    buf = BytesIO()
    header = "{}:".format(n)
    footer = ","
    buf.write(header.encode("utf-8"))
    buf.write(data)
    buf.write(footer.encode("utf-8"))
    return buf.getvalue()
