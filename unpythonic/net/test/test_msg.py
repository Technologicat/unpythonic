# -*- coding: utf-8; -*-

from .fixtures import nettest

from ..msg import mkrecvbuf, recvmsg, sendmsg

def test():
    # basic use of message protocol
    def server1(sock):
        buf = mkrecvbuf()
        data = recvmsg(buf, sock)
        return data
    def client1(sock):
        sendmsg(b"hello world", sock)
    assert nettest(server1, client1) == b"hello world"

    # receiving a message gets a whole message and only that message
    def server2(sock):
        buf = mkrecvbuf()
        data = recvmsg(buf, sock)
        return data
    def client2(sock):
        sendmsg(b"hello world", sock)
        sendmsg(b"hello again", sock)
    assert nettest(server2, client2) == b"hello world"

    # messages are received in order
    def server3(sock):
        buf = mkrecvbuf()
        data = []
        data.append(recvmsg(buf, sock))
        data.append(recvmsg(buf, sock))
        return data
    def client3(sock):
        sendmsg(b"hello world", sock)
        sendmsg(b"hello again", sock)
    assert nettest(server3, client3) == [b"hello world", b"hello again"]

    print("All tests PASSED")

if __name__ == '__main__':
    test()
