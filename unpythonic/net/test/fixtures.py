# -*- coding: utf-8; -*-
"""Unit test fixtures for network code."""

import threading
import socket
from time import sleep

# Server bind address for testing.
addrspec = ("127.0.0.1", 7777)

def nettest(server_recv_func, client_send_func):
    """Server receives and the client sends.

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
