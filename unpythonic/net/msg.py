# -*- coding: utf-8; -*-
"""A simplistic message protocol.

This adds rudimentary message framing and stream re-synchronization on top of a
stream-based transport layer, such as TCP. This is a pure sans-IO implementation.

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

from io import BytesIO

from .util import ReceiveBuffer

__all__ = ["encodemsg", "decodemsg", "MessageDecoder"]

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

            For an OOP API to `decodemsg` that manages the `ReceiveBuffer`
            internally, see `MessageDecoder`.

    source: *Message source*: an iterator that yields chunks of data from some
            data stream, and raises `StopIteration` when it reaches EOF.

            See the helper functions `bytessource`, `streamsource` and
            `socketsource` in `unpythonic.net.util`; these give you an iterator
            for (respectively) `bytes` objects, IO streams (such as files
            opened with `open` and in-memory `BytesIO` streams), and sockets.
            If you need to implement a new source, see their source code; each
            is less than 15 lines.

            The chunks don't have to be of any particular size; the iterator
            should just yield "some more" data wherever it gets its data from.
            For example, when working with TCP sockets, 4096 is a typical chunk
            size.

            A read of the iterator is allowed to return less data, if less data
            (but still indeed some data) is currently waiting to be read.

            If no data is currently available, but EOF has not been signaled,
            the read is allowed to block.

            `source` just abstracts away the details of how to read a particular
            kind of data stream, and does no buffering itself. The underlying
            data stream representation is allowed to perform such buffering,
            if it wants to.

    **CAUTION**: The read on the source *is allowed to block* if no data is
    currently available, but the underlying message source has not indicated
    EOF. This typically occurs with inputs that represent a connection, such as
    a socket or stdin. Use a thread if needed.

    **NOTE**: This is a sans-IO implementation. To actually receive a message
    over a TCP socket, use something like::

        from unpythonic.net.msg import decodemsg
        from unpythonic.net.util import ReceiveBuffer, socketsource

        # ...open a TCP socket `sock`...

        buf = ReceiveBuffer()
        source = socketsource(sock)
        while True:
            data = decodemsg(buf, source)  # get the next message
            if not data:
                break
            ...

    See also `MessageDecoder` for an OOP API in which you don't need to care
    about the `ReceiveBuffer`.
    """
    source = iter(source)

    class MessageHeaderParseError(Exception):
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
        (0xFF) is found in the message source.

        After `synchronize()`, the sync byte `0xFF` is guaranteed to be
        the first byte held in the receive buffer.

        **Usage note**:

        Utf-8 encoded text bodies are safe, but if the message body is binary,
        false positives may occur.

        To make sure, call `read_header` after synchronizing; it will raise
        a `MessageHeaderParseError` if the current receive buffer contents
        cannot be interpreted as a header.
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
            raise MessageHeaderParseError
        if val[1:4] != b"v01":  # protocol version 01
            raise MessageHeaderParseError
        if val[4:5] != b"l":  # length-of-body field
            raise MessageHeaderParseError
        # The len(val) check prevents a junk flood attack.
        # The maximum value of the length has 4090 base-10 digits, all nines.
        # The 4096 is arbitrarily chosen, but matches the typical socket read size.
        while len(val) < 4096:
            j = val.find(b";")  # end of length-of-body field
            if j != -1:  # found
                break
            val = lowlevel_read()
        if j == -1:  # maximum length of length-of-body field exceeded, terminator not found.
            raise MessageHeaderParseError
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
        except MessageHeaderParseError:  # Re-synchronize on false positives.
            # Advance receive buffer by one byte before trying again.
            # TODO: Unfortunately we must copy data for now, because synchronize()
            # TODO: operates on the value, not the BytesIO object.
            val = buf.getvalue()
            buf.set(val[1:])
            # buf._buffer.seek(+1, SEEK_CUR)  # having this effect would be much better
        except EOFError:  # EOF on message source before a complete message was received.
            return None

class MessageDecoder:
    """Object-oriented sugar on top of `decodemsg`.

    Usage::

        from unpythonic.net.msg import MessageDecoder
        from unpythonic.net.util import socketsource

        # ...open a TCP socket `sock`...

        decoder = MessageDecoder(socketsource(sock))
        while True:
            data = decoder.decode()  # get the next message
            if not data:
                break
            ...

    If you need to access data remaining in the internal buffer (e.g. when
    you're done receiving messages and would like to switch to a raw stream),
    call `get_buffered_data`.
    """
    def __init__(self, source):
        """The `source` is a message source in the sense of `decodemsg`."""
        self.buffer = ReceiveBuffer()
        self.source = source

    def decode(self):
        """Decode next message from source, and update receive buffer."""
        return decodemsg(self.buffer, self.source)

    def get_buffered_data(self):
        """Return data currently in the receive buffer.

        Usually this is not needed; an application may need this if you intend
        to switch over from messages back to raw data on an existing stream
        transport.

        When you're done receiving messages, any remaining data already in the
        receive buffer should be processed first, before you resume reading and
        processing any more data from your original stream.
        """
        return self.buffer.getvalue()
