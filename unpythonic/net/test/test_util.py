# -*- coding: utf-8; -*-

import threading
import socket
from time import sleep

from ..util import recvall, \
                   netstringify, \
                   mkrecvbuf, recvmsg, sendmsg

addrspec = ("127.0.0.1", 7777)
def nettest(server_recv_func, client_send_func):
    """Harness/fixture.

    It doesn't really matter which way client/server are, so we (arbitrarily)
    run our tests in a setup where the server receives and the client sends.

    server_recv_func: 1-arg callable; take socket, return data read from it.

    client_send_func: 1-arg callable; take socket, send data into it.
                      No return value.
    """
    # TODO: IPv6 support
    result = []
    def recv_server():
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                sock.bind(addrspec)
                sock.listen()
                conn, addr = sock.accept()
                with conn:
                    data = server_recv_func(conn)
            result.append(data)
        except Exception as err:
            print(err)
    def send_client():
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.connect(addrspec)
                client_send_func(sock)
        except Exception as err:
            print(err)
    ts = threading.Thread(target=recv_server)
    tc = threading.Thread(target=send_client)
    ts.start()
    sleep(0.05)
    tc.start()
    ts.join()
    tc.join()
    return result[0]


def test():
    assert netstringify(b"hello world") == b"11:hello world,"

    # s = server, c = client

    # basic use of recvall
    s = lambda sock: recvall(1024, sock)
    c = lambda sock: [sock.sendall(b"x" * 512), sock.sendall(b"x" * 512)]
    assert len(nettest(s, c)) == 1024

    # basic use of message protocol
    def s2(sock):
        buf = mkrecvbuf()
        data = recvmsg(buf, sock)
        return data
    def c2(sock):
        sendmsg(b"hello world", sock)
    assert nettest(s2, c2) == b"hello world"

    # receiving a message gets a whole message and only that message
    def s3(sock):
        buf = mkrecvbuf()
        data = recvmsg(buf, sock)
        return data
    def c3(sock):
        sendmsg(b"hello world", sock)
        sendmsg(b"hello again", sock)
    assert nettest(s3, c3) == b"hello world"

    # messages are received in order
    def s4(sock):
        buf = mkrecvbuf()
        data = []
        data.append(recvmsg(buf, sock))
        data.append(recvmsg(buf, sock))
        return data
    def c4(sock):
        sendmsg(b"hello world", sock)
        sendmsg(b"hello again", sock)
    assert nettest(s4, c4) == [b"hello world", b"hello again"]

    print("All tests PASSED")

if __name__ == '__main__':
    test()
