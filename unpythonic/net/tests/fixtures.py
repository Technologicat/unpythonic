# -*- coding: utf-8; -*-
"""Unit test fixtures for network code."""

import socket
import threading


def nettest(server_recv_func, client_send_func):
    """Server receives and the client sends.

    server_recv_func: 1-arg callable; take socket, return data read from it.

    client_send_func: 1-arg callable; take socket, send data into it.
                      No return value.
    """
    # Bind to port 0 so the kernel picks a free port for us, then read the
    # actual port back via `getsockname()`.  Using a hardcoded port causes
    # mysterious `OSError: Address already in use` failures when another
    # process (or another test) happens to hold the port.
    #
    # We call `bind()` and `listen()` in the main thread, synchronously,
    # *before* spawning either worker thread.  That's what makes the
    # fixture race-free without any explicit readiness signal: by the
    # time the client thread calls `connect()`, the listening socket
    # already exists, and the kernel will queue the incoming connection
    # on the accept backlog until the server thread gets around to
    # calling `accept()`.  No `threading.Event` needed — the TCP stack
    # is already the synchronization primitive.
    server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_sock.bind(("127.0.0.1", 0))
    server_sock.listen()
    addrspec = server_sock.getsockname()

    # Exceptions captured and re-raised in the main thread after the worker
    # threads join.  Previously these were swallowed into a `print(err)`,
    # which buried the real cause of any failure in the test output and
    # made the test subsequently `IndexError` on the empty `result` list.
    errors = []
    result = []

    def recv_server():
        try:
            conn, _addr = server_sock.accept()
            try:
                data = server_recv_func(conn)
                result.append(data)
            finally:
                conn.close()
        except BaseException as err:
            errors.append(err)

    def send_client():
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.connect(addrspec)
                client_send_func(sock)
        except BaseException as err:
            errors.append(err)

    ts = threading.Thread(target=recv_server)
    tc = threading.Thread(target=send_client)
    try:
        ts.start()
        tc.start()
        ts.join()
        tc.join()
    finally:
        server_sock.close()

    if errors:
        raise errors[0]
    return result[0]
