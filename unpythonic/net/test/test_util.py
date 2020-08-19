# -*- coding: utf-8; -*-

from ...syntax import macros, test  # noqa: F401
from ...test.fixtures import testset

from .fixtures import nettest

from ..util import recvall, netstringify

def runtests():
    # TODO: As of MacroPy 1.1.0b2, this test module crashes at macro expansion time
    # TODO: due to a MacroPy bug involving `bytes` literals.
    # TODO: https://github.com/azazel75/macropy/issues/26
    with testset("unpythonic.net.util"):
        test[netstringify(b"hello world") == b"11:hello world,"]

        server = lambda sock: recvall(1024, sock)
        client = lambda sock: [sock.sendall(b"x" * 512), sock.sendall(b"x" * 512)]
        test[len(nettest(server, client)) == 1024]

if __name__ == '__main__':
    runtests()
