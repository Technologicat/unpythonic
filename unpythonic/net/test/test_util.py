# -*- coding: utf-8; -*-

from .fixtures import nettest

from ..util import recvall, \
                   netstringify

def test():
    assert netstringify(b"hello world") == b"11:hello world,"

    server = lambda sock: recvall(1024, sock)
    client = lambda sock: [sock.sendall(b"x" * 512), sock.sendall(b"x" * 512)]
    assert len(nettest(server, client)) == 1024

    print("All tests PASSED")

if __name__ == '__main__':
    test()
