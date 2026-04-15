# -*- coding: utf-8; -*-

from ...syntax import macros, test, warn  # noqa: F401
from ...test.fixtures import session, testset

from io import BytesIO, SEEK_SET

from .fixtures import nettest

from ..msg import encodemsg, decodemsg, MessageDecoder
from ..util import ReceiveBuffer, bytessource, streamsource, socketsource

def runtests():
    with testset("sans-IO"):
        with testset("basic usage"):
            # Encode a message:
            rawdata = b"hello world"
            message = encodemsg(rawdata)
            # Decode a message:
            decoder = MessageDecoder(bytessource(message))
            test[decoder.decode() == b"hello world"]
            test[decoder.decode() is None]  # The message should have been consumed by the first decode.

        # Decoding a message gets a whole message and only that message.
        with testset("decode robustness"):
            bio = BytesIO()
            bio.write(message)
            bio.write(b"junk junk junk")
            bio.seek(0, SEEK_SET)
            decoder = MessageDecoder(streamsource(bio))
            test[decoder.decode() == b"hello world"]
            test[decoder.decode() is None]

        # - Messages are received in order.
        # - Any leftover bytes already read into the receive buffer by the previous decode
        #   are consumed *from the buffer* by the next decode. This guarantees it doesn't
        #   matter if the transport does not honor message boundaries (which is indeed the
        #   whole point of having this protocol).
        #     - Note this means that should you wish to stop receiving messages on a particular
        #       source, and resume reading a raw stream from it instead, you must manually prepend
        #       the final contents of the receive buffer (`decoder.get_buffered_data()`) to whatever
        #       data you later receive from that source (since that data has already been placed
        #       into the receive buffer, so it is no longer available at the source).
        #     - So it's recommended to have a dedicated channel to communicate using messages,
        #       e.g. a dedicated TCP connection on which all communication is done with messages.
        #       This way you don't need to care about the receive buffer.
        with testset("message ordering"):
            bio = BytesIO()
            bio.write(encodemsg(b"hello world"))
            bio.write(encodemsg(b"hello again"))
            bio.seek(0, SEEK_SET)
            decoder = MessageDecoder(streamsource(bio))
            test[decoder.decode() == b"hello world"]
            test[decoder.decode() == b"hello again"]
            test[decoder.decode() is None]

        # Synchronization to message start is performed upon decode.
        # It doesn't matter if there is junk between messages (the junk is discarded).
        with testset("stream synchronization"):
            bio = BytesIO()
            bio.write(encodemsg(b"hello world"))
            bio.write(b"junk junk junk")
            bio.write(encodemsg(b"hello again"))
            bio.seek(0, SEEK_SET)
            decoder = MessageDecoder(streamsource(bio))
            test[decoder.decode() == b"hello world"]
            test[decoder.decode() == b"hello again"]
            test[decoder.decode() is None]

        # Junk containing sync bytes (0xFF) does not confuse or hang the decoder.
        with testset("junk containing sync bytes"):
            bio = BytesIO()
            bio.write(encodemsg(b"hello world"))
            bio.write(b"\xff" * 10)
            bio.write(encodemsg(b"hello again"))
            bio.seek(0, SEEK_SET)
            decoder = MessageDecoder(streamsource(bio))
            test[decoder.decode() == b"hello world"]
            test[decoder.decode() == b"hello again"]
            test[decoder.decode() is None]

    with testset("decodemsg (free function form)"):
        # `MessageDecoder` wraps `decodemsg` and manages the `ReceiveBuffer`
        # internally; the tests above exercise both via the class-based path.
        # `decodemsg` itself is also in `msg.__all__` as a public free-function
        # entry point, so it deserves a direct test that doesn't route through
        # the class.
        with testset("basic roundtrip"):
            buf = ReceiveBuffer()
            source = bytessource(encodemsg(b"hello world"))
            test[decodemsg(buf, source) == b"hello world"]
            # Subsequent call: source is exhausted, returns None.
            test[decodemsg(buf, source) is None]

        with testset("multiple messages with stream synchronization"):
            # Junk between the two messages must be discarded; both messages
            # must decode in order. Exercises the same invariants as the
            # `MessageDecoder` tests above, via the free-function API.
            bio = BytesIO()
            bio.write(encodemsg(b"first"))
            bio.write(b"junk junk junk")
            bio.write(encodemsg(b"second"))
            bio.seek(0, SEEK_SET)
            buf = ReceiveBuffer()
            source = streamsource(bio)
            test[decodemsg(buf, source) == b"first"]
            test[decodemsg(buf, source) == b"second"]
            test[decodemsg(buf, source) is None]

        with testset("binary-safe payload"):
            # Messages may contain arbitrary bytes, including the sync-byte
            # value (0xFF) inside the payload.
            payload = bytes(range(256))
            buf = ReceiveBuffer()
            source = bytessource(encodemsg(payload))
            test[decodemsg(buf, source) == payload]

    with testset("with TCP sockets"):
        def server1(sock):
            decoder = MessageDecoder(socketsource(sock))
            data = decoder.decode()
            return data
        def client1(sock):
            sock.sendall(encodemsg(b"hello world"))
        test[nettest(server1, client1) == b"hello world"]

        def server2(sock):
            decoder = MessageDecoder(socketsource(sock))
            data = decoder.decode()
            return data
        def client2(sock):
            sock.sendall(encodemsg(b"hello world"))
            sock.sendall(encodemsg(b"hello again"))
        test[nettest(server2, client2) == b"hello world"]

        def server3(sock):
            decoder = MessageDecoder(socketsource(sock))
            data = []
            data.append(decoder.decode())
            data.append(decoder.decode())
            return data
        def client3(sock):
            sock.sendall(encodemsg(b"hello world"))
            sock.sendall(encodemsg(b"hello again"))
        test[nettest(server3, client3) == [b"hello world", b"hello again"]]

if __name__ == '__main__':  # pragma: no cover
    with session(__file__):
        runtests()
