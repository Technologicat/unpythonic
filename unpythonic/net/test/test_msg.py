# -*- coding: utf-8; -*-

from io import BytesIO, SEEK_SET

from .fixtures import nettest

from ..msg import ReceiveBuffer, encodemsg, decodemsg, \
                  bytessource, streamsource, socketsource, \
                  recvmsg, sendmsg

def test():
    # sans-IO

    # Basic use.
    # Encode a message:
    rawdata = b"hello world"
    message = encodemsg(rawdata)
    # Decode a message:
    source = bytessource(message)  # NOTE: sources are stateful...
    buf = ReceiveBuffer()          # ...as are receive buffers.
    assert decodemsg(buf, source) == b"hello world"
    assert decodemsg(buf, source) is None  # The message should have been consumed by the first decode.

    # Decoding a message gets a whole message and only that message.
    bio = BytesIO()
    bio.write(message)
    bio.write(b"junk junk junk")
    bio.seek(0, SEEK_SET)
    source = streamsource(bio)
    buf = ReceiveBuffer()
    assert decodemsg(buf, source) == b"hello world"
    assert decodemsg(buf, source) is None

    # - Messages are received in order.
    # - Any leftover bytes already read into the receive buffer by the previous decodemsg()
    #   are consumed *from the buffer* by the next decodemsg(). This guarantees it doesn't
    #   matter if the transport does not honor message boundaries (which is the whole point
    #   of having this protocol).
    #     - Note this means that should you wish to stop receiving messages on a particular
    #       source, and resume reading a raw stream from it instead, you must manually prepend
    #       the final contents of the receive buffer (see `buf.getvalue()`) to whatever data
    #       you later receive from that source (since that data has already been placed
    #       into the receive buffer, so it is no longer available at the source).
    #     - So it's recommended to have a dedicated channel to communicate using messages,
    #       e.g. a dedicated TCP connection on which all communication is done with messages.
    bio = BytesIO()
    bio.write(encodemsg(b"hello world"))
    bio.write(encodemsg(b"hello again"))
    bio.seek(0, SEEK_SET)
    source = streamsource(bio)
    buf = ReceiveBuffer()
    assert decodemsg(buf, source) == b"hello world"
    assert decodemsg(buf, source) == b"hello again"
    assert decodemsg(buf, source) is None

    # Synchronization to message start is performed upon decode.
    # It doesn't matter if there is junk between messages (the junk is discarded).
    bio = BytesIO()
    bio.write(encodemsg(b"hello world"))
    bio.write(b"junk junk junk")
    bio.write(encodemsg(b"hello again"))
    bio.seek(0, SEEK_SET)
    source = streamsource(bio)
    buf = ReceiveBuffer()
    assert decodemsg(buf, source) == b"hello world"
    assert decodemsg(buf, source) == b"hello again"
    assert decodemsg(buf, source) is None

    # Junk containing sync bytes (0xFF) does not confuse or hang the decoder.
    bio = BytesIO()
    bio.write(encodemsg(b"hello world"))
    bio.write(b"\xff" * 10)
    bio.write(encodemsg(b"hello again"))
    bio.seek(0, SEEK_SET)
    source = streamsource(bio)
    buf = ReceiveBuffer()
    assert decodemsg(buf, source) == b"hello world"
    assert decodemsg(buf, source) == b"hello again"
    assert decodemsg(buf, source) is None

    # with TCP sockets

    def server1(sock):
        buf = ReceiveBuffer()
        data = recvmsg(buf, sock)
        return data
    def client1(sock):
        sendmsg(b"hello world", sock)
    assert nettest(server1, client1) == b"hello world"

    def server2(sock):
        buf = ReceiveBuffer()
        data = recvmsg(buf, sock)
        return data
    def client2(sock):
        sendmsg(b"hello world", sock)
        sendmsg(b"hello again", sock)
    assert nettest(server2, client2) == b"hello world"

    def server3(sock):
        # If you need to receive many small messages on the same socket, use a
        # `socketsource` with `decodemsg`. This combination produces exactly
        # the same result as multiple calls of `recvmsg`, but avoids generating
        # garbage, because it wraps the socket in a message source only once,
        # instead of doing that separately for each message.
        buf = ReceiveBuffer()
        source = socketsource(sock)
        data = []
        data.append(decodemsg(buf, source))
        data.append(decodemsg(buf, source))
        return data
    def client3(sock):
        sendmsg(b"hello world", sock)
        sendmsg(b"hello again", sock)
    assert nettest(server3, client3) == [b"hello world", b"hello again"]

    print("All tests PASSED")

if __name__ == '__main__':
    test()
