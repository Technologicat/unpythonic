# -*- coding: utf-8; -*-

from io import BytesIO, SEEK_SET

from .fixtures import nettest

from ..msg import encodemsg, MessageDecoder
from ..util import bytessource, streamsource, socketsource

def test():
    # sans-IO

    # Basic use.
    # Encode a message:
    rawdata = b"hello world"
    message = encodemsg(rawdata)
    # Decode a message:
    decoder = MessageDecoder(bytessource(message))
    assert decoder.decode() == b"hello world"
    assert decoder.decode() is None  # The message should have been consumed by the first decode.

    # Decoding a message gets a whole message and only that message.
    bio = BytesIO()
    bio.write(message)
    bio.write(b"junk junk junk")
    bio.seek(0, SEEK_SET)
    decoder = MessageDecoder(streamsource(bio))
    assert decoder.decode() == b"hello world"
    assert decoder.decode() is None

    # - Messages are received in order.
    # - Any leftover bytes already read into the receive buffer by the previous decode
    #   are consumed *from the buffer* by the next decode. This guarantees it doesn't
    #   matter if the transport does not honor message boundaries (which is indeed the
    #   whole point of having this protocol).
    #     - Note this means that should you wish to stop receiving messages on a particular
    #       source, and resume reading a raw stream from it instead, you must manually prepend
    #       the final contents of the receive buffer (`decoder.buffer.getvalue()`) to whatever
    #       data you later receive from that source (since that data has already been placed
    #       into the receive buffer, so it is no longer available at the source).
    #     - So it's recommended to have a dedicated channel to communicate using messages,
    #       e.g. a dedicated TCP connection on which all communication is done with messages.
    #       This way you don't need to care about the receive buffer.
    bio = BytesIO()
    bio.write(encodemsg(b"hello world"))
    bio.write(encodemsg(b"hello again"))
    bio.seek(0, SEEK_SET)
    decoder = MessageDecoder(streamsource(bio))
    assert decoder.decode() == b"hello world"
    assert decoder.decode() == b"hello again"
    assert decoder.decode() is None

    # Synchronization to message start is performed upon decode.
    # It doesn't matter if there is junk between messages (the junk is discarded).
    bio = BytesIO()
    bio.write(encodemsg(b"hello world"))
    bio.write(b"junk junk junk")
    bio.write(encodemsg(b"hello again"))
    bio.seek(0, SEEK_SET)
    decoder = MessageDecoder(streamsource(bio))
    assert decoder.decode() == b"hello world"
    assert decoder.decode() == b"hello again"
    assert decoder.decode() is None

    # Junk containing sync bytes (0xFF) does not confuse or hang the decoder.
    bio = BytesIO()
    bio.write(encodemsg(b"hello world"))
    bio.write(b"\xff" * 10)
    bio.write(encodemsg(b"hello again"))
    bio.seek(0, SEEK_SET)
    decoder = MessageDecoder(streamsource(bio))
    assert decoder.decode() == b"hello world"
    assert decoder.decode() == b"hello again"
    assert decoder.decode() is None

    # Use with TCP sockets.

    def server1(sock):
        decoder = MessageDecoder(socketsource(sock))
        data = decoder.decode()
        return data
    def client1(sock):
        sock.sendall(encodemsg(b"hello world"))
    assert nettest(server1, client1) == b"hello world"

    def server2(sock):
        decoder = MessageDecoder(socketsource(sock))
        data = decoder.decode()
        return data
    def client2(sock):
        sock.sendall(encodemsg(b"hello world"))
        sock.sendall(encodemsg(b"hello again"))
    assert nettest(server2, client2) == b"hello world"

    def server3(sock):
        decoder = MessageDecoder(socketsource(sock))
        data = []
        data.append(decoder.decode())
        data.append(decoder.decode())
        return data
    def client3(sock):
        sock.sendall(encodemsg(b"hello world"))
        sock.sendall(encodemsg(b"hello again"))
    assert nettest(server3, client3) == [b"hello world", b"hello again"]

    print("All tests PASSED")

if __name__ == '__main__':
    test()
