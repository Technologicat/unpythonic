# -*- coding: utf-8; -*-

from ...syntax import macros, test, test_raises, warn  # noqa: F401
from ...test.fixtures import session, testset

from .fixtures import nettest

from ..util import ReceiveBuffer, recvall, netstringify

def runtests():
    with testset("netstringify"):
        test[netstringify(b"hello world") == b"11:hello world,"]

    with testset("sendall"):
        server = lambda sock: recvall(1024, sock)
        client = lambda sock: [sock.sendall(b"x" * 512), sock.sendall(b"x" * 512)]
        test[len(nettest(server, client)) == 1024]

    with testset("ReceiveBuffer"):
        # `ReceiveBuffer` is a thin `BytesIO` wrapper with message-protocol
        # semantics: append bytes as more arrive on a transport, `getvalue()`
        # to inspect what's there, `set()` to replace (typically after a
        # message boundary has been consumed and the remainder needs to
        # stay in the buffer for the next message).  It's part of
        # `unpythonic.net.util.__all__` — a public API used internally by
        # `MessageDecoder` and externally by at least one fleet-outside
        # consumer (`raven.common.netutil`).

        with testset("construction"):
            # Default: empty buffer.
            test[ReceiveBuffer().getvalue() == b""]
            # Initial contents populate the buffer.
            test[ReceiveBuffer(b"hello").getvalue() == b"hello"]
            # `getvalue()` is non-destructive — calling twice returns
            # the same bytes, buffer still has them afterwards.
            buf = ReceiveBuffer(b"abc")
            test[buf.getvalue() == b"abc"]
            test[buf.getvalue() == b"abc"]

        with testset("append"):
            buf = ReceiveBuffer()
            buf.append(b"hello")
            test[buf.getvalue() == b"hello"]
            # Multiple appends accumulate in order.
            buf.append(b" ")
            buf.append(b"world")
            test[buf.getvalue() == b"hello world"]
            # Empty append is a no-op.
            buf.append(b"")
            test[buf.getvalue() == b"hello world"]
            # `append` returns self — chainable.
            test[buf.append(b"!") is buf]
            test[buf.getvalue() == b"hello world!"]

        with testset("set replaces contents"):
            buf = ReceiveBuffer(b"old contents")
            buf.set(b"new")
            test[buf.getvalue() == b"new"]
            # set() with empty bytes clears the buffer.
            buf.set(b"")
            test[buf.getvalue() == b""]
            # `set` also returns self.
            test[ReceiveBuffer().set(b"x") is not None]

        with testset("set + append: position is at end, not zero"):
            # This is a subtle but documented property: `set(new_contents)`
            # must leave the internal stream position at the *end* of the
            # new contents, so a subsequent `append` continues from where
            # `set` left off.  The naive refactor `self._buffer =
            # BytesIO(new_contents)` puts the position at 0 and the next
            # write would overwrite — this test guards that regression.
            buf = ReceiveBuffer()
            buf.set(b"abc")
            buf.append(b"def")
            test[buf.getvalue() == b"abcdef"]
            # Also via the __init__ path, which delegates to set().
            buf2 = ReceiveBuffer(b"foo")
            buf2.append(b"bar")
            test[buf2.getvalue() == b"foobar"]

        with testset("type errors"):
            # `ReceiveBuffer` rejects non-`bytes` inputs strictly — `bytearray`,
            # `memoryview`, and `str` are all refused even though `BytesIO`
            # itself would accept some of them.  This is deliberate: message-
            # protocol code expects immutable `bytes` boundaries and a
            # `bytearray` input could mutate under the buffer's feet.
            test_raises[TypeError, ReceiveBuffer().append("not bytes")]
            test_raises[TypeError, ReceiveBuffer().append(bytearray(b"nope"))]
            test_raises[TypeError, ReceiveBuffer().append(memoryview(b"nope"))]
            test_raises[TypeError, ReceiveBuffer().append(42)]
            test_raises[TypeError, ReceiveBuffer().append(None)]
            test_raises[TypeError, ReceiveBuffer().set("not bytes")]
            test_raises[TypeError, ReceiveBuffer().set(bytearray(b"nope"))]
            # Construction delegates to `set`, so the same check applies.
            test_raises[TypeError, ReceiveBuffer("not bytes")]
            test_raises[TypeError, ReceiveBuffer(bytearray(b"nope"))]

if __name__ == '__main__':  # pragma: no cover
    with session(__file__):
        runtests()
