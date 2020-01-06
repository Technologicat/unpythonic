# -*- coding: utf-8; -*-
"""Utilities for networking."""

__all__ = ["ReuseAddrThreadingTCPServer",
           "ReceiveBuffer",
           "bytessource", "streamsource", "socketsource",
           "recvall",
           "netstringify"]

import socket
import socketserver
import select
from io import BytesIO, IOBase

# https://docs.python.org/3/library/socketserver.html#socketserver.ThreadingTCPServer
# https://docs.python.org/3/library/socketserver.html#socketserver.ThreadingMixIn
# https://docs.python.org/3/library/socketserver.html#socketserver.TCPServer
class ReuseAddrThreadingTCPServer(socketserver.ThreadingTCPServer):
    def server_bind(self):
        """Custom server_bind ensuring the socket is available for rebind immediately."""
        # from https://stackoverflow.com/a/18858817
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.socket.bind(self.server_address)


# We could achieve the same result using a `unpythonic.collections.box` to
# hold a `BytesIO`, but a class allows us to encapsulate also the set and
# append operations. So here OOP is really the right solution.
class ReceiveBuffer:
    """A receive buffer for message protocols running on top of stream-based transports.

    To use this, read data from your original stream into this buffer, and get
    the data from here.

    The advantage over using a bare `BytesIO` is that we support partially
    clearing the buffer when a complete message has been received. (This allows
    removing the received message from the buffer, while keeping any bytes that
    arrived on the stream transport after that particular message ended - most
    likely containing the beginning of a new message.)

    It is the caller's responsibility to define what a message is; we just
    provide methods to `append` and `set` the buffer contents.
    """

    def __init__(self, initial_contents=b""):
        """A receive buffer object for use with `decodemsg`."""
        self._buffer = BytesIO()
        self.set(initial_contents)

    # The contents are potentially large, so we don't dump them into the TypeError messages.
    def append(self, more_contents=b""):
        """Append `more_contents` to the buffer."""
        if not isinstance(more_contents, bytes):
            raise TypeError("Expected a bytes object, got {}".format(type(more_contents)))
        self._buffer.write(more_contents)
        return self  # convenience

    def set(self, new_contents=b""):
        """Replace buffer contents with `new_contents`."""
        if not isinstance(new_contents, bytes):
            raise TypeError("Expected a bytes object, got {}".format(type(new_contents)))
        # Use write() to supply the new contents instead of ctor arg, so the
        # stream position will be at the end, so any new writes continue from
        # wherever the initial contents leave off.
        self._buffer = BytesIO()
        self._buffer.write(new_contents)
        return self

    def getvalue(self):
        """Return the data currently in the buffer, as a `bytes` object.

        Mostly this is for internal use by message protocols; but an application
        may need this if you intend to switch over from messages back to raw data
        on an existing stream transport.

        When you're done receiving messages, if you need to read the remaining data
        after the last message, the data in the buffer should be processed first,
        before you read and process any more data from your original stream.
        """
        return self._buffer.getvalue()


def bytessource(data, chunksize=4096):
    """Generator that reads from a `bytes` object in chunksize-sized chunks.

    Returns a generator instance.

    The generator yields each chunk as a `bytes` object. The last one may be
    smaller than `chunksize`. Stops iteration when data runs out.

    Acts as a message source for `decodemsg`, for receiving data from a `bytes` object.

    See also `streamsource`, `socketsource`.
    """
    # Package the generator in an inner function to fail-fast.
    if not isinstance(data, bytes):
        raise TypeError("Expected a `bytes` object, got {}".format(type(data)))
    def bytes_chunk_iterator():
        j = 0
        while True:
            if j * chunksize >= len(data):
                return
            chunk = data[(j * chunksize):((j + 1) * chunksize)]
            yield chunk
            j += 1
    return bytes_chunk_iterator()

def streamsource(stream, chunksize=4096):
    """Generator that reads from an IO stream in (at most) chunksize-sized chunks.

    This can be used with files opened with `open()`, in-memory `BytesIO` streams,
    and such.

    Returns a generator instance.

    The generator yields each chunk as a `bytes` object. Each chunk may be
    smaller than `chunksize`, if fewer than `chunksize` bytes are available in
    the stream at the time when `next()` is called. (Consider `sys.stdin`.)

    Blocks when no data is available, but the stream has not signaled EOF.
    Stops iteration at EOF.

    Acts as a message source for `decodemsg`, for receiving data from a binary IO stream.

    See also `bytessource`, `socketsource`.
    """
    if not isinstance(stream, IOBase):
        raise TypeError("Expected a derivative of `IOBase`, got {}".format(type(stream)))
    def stream_chunk_iterator():
        while True:
            data = stream.read(4096)
            if len(data) == 0:
                return
            yield data
    return stream_chunk_iterator()

def socketsource(sock, chunksize=4096):
    """Generator that reads from a socket in (at most) chunksize-sized chunks.

    Returns a generator instance.

    The generator yields each chunk as a `bytes` object. Each chunk may be
    smaller than `chunksize`, if fewer than `chunksize` bytes are available on
    the socket at the time when `next()` is called.

    Blocks when no data is available, but the socket is still open.
    Stops iteration when the socket is closed.

    Acts as a message source for `decodemsg`, for receiving data over a socket.

    See also `bytessource`, `streamsource`.
    """
    if not isinstance(sock, socket.SocketType):
        raise TypeError("Expected a socket object, got {}".format(type(sock)))
    def socket_chunk_iterator():
        while True:
            rs, ws, es = select.select([sock], [], [])
            for r in rs:
                data = sock.recv(chunksize)
                if len(data) == 0:
                    return
            yield data
    return socket_chunk_iterator()


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
