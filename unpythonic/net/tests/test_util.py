# -*- coding: utf-8; -*-

from ...syntax import macros, test, warn  # noqa: F401
from ...test.fixtures import session, testset

from .fixtures import nettest

from ..util import recvall, netstringify

def runtests():
    with testset("netstringify"):
        test[netstringify(b"hello world") == b"11:hello world,"]

    with testset("sendall"):
        server = lambda sock: recvall(1024, sock)
        client = lambda sock: [sock.sendall(b"x" * 512), sock.sendall(b"x" * 512)]
        test[len(nettest(server, client)) == 1024]

if __name__ == '__main__':  # pragma: no cover
    with session(__file__):
        runtests()
