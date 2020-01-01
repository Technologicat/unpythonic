# -*- coding: utf-8; -*-
"""A simplistic message protocol.

This adds rudimentary message framing and stream re-synchronization on top of a
stream-based transport layer, such as TCP. This is a sans-IO implementation.

The decoder uses a receive buffer to decode or receive messages. This is used
as a staging area for incoming data, since the decoder must hold on to data
already received from the source, but not yet consumed by inclusion into a
complete message. This is needed because stream-based transports have no
concept of a message boundary. Thus it may (and will) occur, near the seam of
two messages, that a chunk read from the source includes not only the end of
one message, but also the beginning of the next one.

**Technical details**

A message consists of a header and a body, concatenated without any separator, where:

  header:
    0xFF: sync byte, start of new message
      Chosen because our primary payload target is utf-8 encoded text,
      where the byte 0xFF never appears.
    literal "v": start of protocol version field
    two bytes containing the protocol version, currently the characters "01" as utf-8.
      These don't need to be number characters, any Unicode codepoints below 127 will do.
      It's unlikely more than (127 - 32)**2 = 95**2 = 9025 backward incompatible versions
      of this protocol will ever be needed, even in the extremely unlikely case this code
      ends up powering someone's 31st century starship.
    literal "l": start of message length field
    utf-8 string, containing the number of bytes in the message body
      In other words, `str(len(body)).encode("utf-8")`.
    literal ";": end of message length field (in v01, also the end of the header)
  body:
    arbitrary payload, exactly as many bytes as the header said.

**Notes**

On sans-IO, see:
    https://sans-io.readthedocs.io/
"""

__all__ = ["encodemsg",
           "ReceiveBuffer",
           "socketsource", "streamsource", "bytessource",
           "decodemsg"]

import select
import socket
from io import BytesIO, IOBase


# Send

def encodemsg(data):
    """Package given `data` into a message.

    data: Arbitrary data as a `bytes` object.

    Returns the message as a `bytes` object.

    **NOTE**: This is a sans-IO implementation. To actually send the message
    over a TCP socket, use something like::

        sock.sendall(encodemsg(data))
    """
    buf = BytesIO()
    # header
    buf.write(b"\xff")  # sync byte
    buf.write(b"v01")  # message protocol version
    buf.write(b"l")
    buf.write(str(len(data)).encode("utf-8"))
    buf.write(b";")
    # body
    buf.write(data)
    return buf.getvalue()


# Receive

# We need a buffer object that holds the underlying `BytesIO` buffer in an
# attribute, because a `BytesIO` cannot be cleared. So when a complete message
# has been read, any remaining data must be written into a new `BytesIO` instance.
#
# We could achieve the same result using a `unpythonic.collections.box` to hold
# a `BytesIO`, but a class allows us to encapsulate also the set and append
# operations. So here OOP is really the right solution.
class ReceiveBuffer:
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

        Mostly for internal use; but you may need this if you intend to
        switch over from messages back to raw data on an existing data stream.

        When you're done receiving messages, if you need to read the remaining data
        after the last message, the data in `buf` should be processed first, before
        you read and process any more data from your original stream.
        """
        return self._buffer.getvalue()


_CHUNKSIZE = 4096
def bytessource(data):
    """Message source for `decodemsg`, for receiving data from a `bytes` object."""
    # Package the generator in an inner function to fail-fast.
    if not isinstance(data, bytes):
        raise TypeError("Expected a `bytes` object, got {}".format(type(data)))
    def bytesiterator():
        j = 0
        while True:
            if j * _CHUNKSIZE >= len(data):
                return
            chunk = data[(j * _CHUNKSIZE):((j + 1) * _CHUNKSIZE)]
            yield chunk
            j += 1
    return bytesiterator()

def streamsource(stream):
    """Message source for `decodemsg`, for receiving data from a binary IO stream.

    This can be used with files opened with `open()`, in-memory `BytesIO` streams,
    and such.
    """
    if not isinstance(stream, IOBase):
        raise TypeError("Expected a derivative of `IOBase`, got {}".format(type(stream)))
    def IOiterator():
        while True:
            data = stream.read(4096)
            if len(data) == 0:
                return
            yield data
    return IOiterator()

def socketsource(sock):
    """Message source for `decodemsg`, for receiving data over a socket."""
    if not isinstance(sock, socket.SocketType):
        raise TypeError("Expected a socket object, got {}".format(type(sock)))
    def socketiterator():
        while True:
            rs, ws, es = select.select([sock], [], [])
            for r in rs:
                data = sock.recv(_CHUNKSIZE)
                if len(data) == 0:
                    return
            yield data
    return socketiterator()


def decodemsg(buf, source):
    """Decode next message from source, and update receive buffer.

    Returns the message body as a `bytes` object, or `None` if EOF occurred on
    `source` before a complete message was received.

    buf:    A `ReceiveBuffer` instance. This is used as a staging area for
            incoming data, since we must hold on to data already received
            from the source, but not yet consumed by inclusion into a
            complete message.

            Note it is the caller's responsibility to hold on to the receive
            buffer during a message-communication session; often, at the seam
            of two messages, it will contain the start of the next message,
            which is needed for the next run of `decodemsg`.

    source: *Message source*: an iterator that yields chunks of data from some
            data stream, and raises `StopIteration` when it reaches EOF.

            See the helper functions `bytessource`, `streamsource` and
            `socketsource`, which give you a message source for (respectively)
            `bytes` objects, IO streams (such as files opened with `open` and
            in-memory `BytesIO` streams), and sockets. If you need to implement
            a new source, see their source code; each is less than 15 lines.

            The chunks don't have to be of any particular size; the iterator
            should just yield "some more" data wherever it gets its data from.
            For example, when working with TCP sockets, 4096 is a typical chunk
            size. The read is allowed to return less data, if less data (but
            still indeed some data) is currently waiting to be read.

            `source` just abstracts away the details of how to read a particular
            kind of data stream, and does no buffering itself. The underlying
            data stream representation is allowed to perform such buffering,
            if it wants to.

    **CAUTION**: The decoding operation is **synchronous**. That is, the read
    on the source *is allowed to block* if no data is currently available,
    but the underlying data source has not indicated EOF. This typically occurs
    with inputs that represent a connection, such as a socket or stdin. Use a
    thread if needed.

    **NOTE**: This is a sans-IO implementation. To actually receive a message
    over a TCP socket, use something like::

        from unpythonic.net.msg import ReceiveBuffer, socketsource, decodemsg

        # ...open a TCP socket `sock`...

        buf = ReceiveBuffer()
        source = socketsource(sock)
        while not terminated:
            data = decodemsg(buf, source)  # get the next message
            ...

    See also `MessageDecoder` for an OOP API.
    """
    source = iter(source)

    class MessageParseError(Exception):
        pass

    def lowlevel_read():
        """Read some more data from source into the receive buffer.

        Return the current contents of the receive buffer. (All of it,
        not just the newly added data.)

        Invariant: the identity of the `BytesIO` in `buf` does not change.
        """
        try:
            data = next(source)
        except StopIteration:
            raise EOFError
        buf.append(data)
        return buf.getvalue()

    def synchronize():
        """Synchronize the stream to the start of a new message.

        This is done by reading and discarding data until the next sync byte
        (0xFF) is found in the data source.

        After `synchronize()`, the sync byte `0xFF` is guaranteed to be
        the first byte held in the receive buffer.

        **Usage note**:

        Utf-8 encoded text bodies are safe, but if the message body is binary,
        false positives may occur.

        To make sure, call `read_header` after synchronizing; it will raise a
        `MessageParseError` if the current receive buffer contents cannot be
        interpreted as a header.
        """
        val = buf.getvalue()
        while True:
            if b"\xff" in val:
                j = val.find(b"\xff")
                junk, start_of_msg = val[:j], val[j:]  # noqa: F841
                # Discard previous BytesIO, start the new one with the sync byte (0xFF).
                buf.set(start_of_msg)
                return
            # Clear the receive buffer after each chunk that didn't have a sync
            # byte in it. This prevents a malicious sender from crashing the
            # receiver by flooding it with nothing but junk.
            buf.set(b"")
            val = lowlevel_read()

    def read_header():
        """Parse message header.

        Return the message body length.

        If successful, advance the receive buffer, discarding the header.
        """
        val = buf.getvalue()
        while len(val) < 5:
            val = lowlevel_read()
        # CAUTION: val[0] == 255, but val[0:1] == b"\xff".
        if val[0:1] != b"\xff":  # sync byte
            raise MessageParseError
        if val[1:4] != b"v01":  # protocol version 01
            raise MessageParseError
        if val[4:5] != b"l":  # length-of-body field
            raise MessageParseError
        # The len(val) check prevents a junk flood attack.
        # The maximum value of the length has 4090 base-10 digits, all nines.
        # The 4096 is arbitrarily chosen, but matches the typical socket read size.
        while len(val) < 4096:
            j = val.find(b";")  # end of length-of-body field
            if j != -1:  # found
                break
            val = lowlevel_read()
        if j == -1:  # maximum length of length-of-body field exceeded, terminator not found.
            raise MessageParseError
        j = val.find(b";")
        body_len = int(val[5:j].decode("utf-8"))
        buf.set(val[(j + 1):])
        return body_len

    def read_body(body_len):
        """Read and return message body as a `bytes` object.

        Advance the receive buffer, discarding the body from the receive buffer.
        """
        # TODO: We need to hold the data in memory twice: once in the receive buffer,
        # TODO: once in the output buffer. This doubles memory use, which is bad for
        # TODO: very large messages.
        val = buf.getvalue()
        while len(val) < body_len:
            val = lowlevel_read()
        # Any bytes left over belong to the next message.
        body, leftovers = val[:body_len], val[body_len:]
        buf.set(leftovers)
        return body

    # With these, receiving a message is as simple as:
    while True:
        try:
            synchronize()
            body_len = read_header()
            return read_body(body_len)
        except MessageParseError:  # Re-synchronize on false positives.
            # Advance receive buffer by one byte before trying again.
            # TODO: Unfortunately we must copy data for now, because synchronize()
            # TODO: operates on the value, not the BytesIO object.
            val = buf.getvalue()
            buf.set(val[1:])
            # buf._buffer.seek(+1, SEEK_CUR)  # having this effect would be much better
        except EOFError:  # EOF on data source before a complete message was received.
            return None

class MessageDecoder:
    """Object-oriented sugar on top of `decodemsg`.

    Usage::

        from unpythonic.net.msg import socketsource, MessageDecoder

        # ...open a TCP socket `sock`...

        decoder = MessageDecoder(socketsource(sock))
        while not terminated:
            data = decoder.decode()  # get the next message
            ...

    A `ReceiveBuffer` is created internally. If you need to access it (e.g.
    when you're done receiving messages and would like to switch to a raw
    stream), it's the `buffer` attribute.
    """
    def __init__(self, source):
        """The `source` is a message source in the sense of `decodemsg`."""
        self.buffer = ReceiveBuffer()
        self.source = source

    def decode(self):
        """Decode next message from source, and update receive buffer."""
        return decodemsg(self.buffer, self.source)
