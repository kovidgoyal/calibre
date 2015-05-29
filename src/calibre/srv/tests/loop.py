#!/usr/bin/env python2
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2015, Kovid Goyal <kovid at kovidgoyal.net>'

import httplib, ssl, os, socket
from unittest import skipIf

try:
    from calibre.utils.certgen import create_server_cert
except ImportError:
    create_server_cert = None


from calibre.srv.pre_activated import has_preactivated_support
from calibre.srv.tests.base import BaseTest, TestServer
from calibre.ptempfile import TemporaryDirectory

class LoopTest(BaseTest):

    def test_workers(self):
        ' Test worker semantics '
        with TestServer(lambda data:(data.path[0] + data.read()), worker_count=3) as server:
            self.ae(3, sum(int(w.is_alive()) for w in server.loop.pool.workers))
            server.loop.stop()
            server.join()
            self.ae(0, sum(int(w.is_alive()) for w in server.loop.pool.workers))

    def test_ring_buffer(self):
        class FakeSocket(object):
            def __init__(self, data):
                self.data = data

            def recv_into(self, mv):
                sz = min(len(mv), len(self.data))
                mv[:sz] = self.data[:sz]
                return sz
        from calibre.srv.loop import ReadBuffer, READ, WRITE
        buf = ReadBuffer(100)
        def write(data):
            return buf.recv_from(FakeSocket(data))
        def set(data, rpos, wpos, state):
            buf.ba = bytearray(data)
            buf.buf = memoryview(buf.ba)
            buf.read_pos, buf.write_pos, buf.full_state = rpos, wpos, state

        self.ae(b'', buf.read(10))
        self.assertTrue(buf.has_space), self.assertFalse(buf.has_data)
        self.ae(write(b'a'*50), 50)
        self.ae(write(b'a'*50), 50)
        self.ae(write(b'a'*50), 0)
        self.ae(buf.read(1000), bytes(buf.ba))
        self.ae(b'', buf.read(10))
        self.ae(write(b'a'*10), 10)
        numbers = bytes(bytearray(xrange(10)))
        set(numbers, 1, 3, READ)
        self.ae(buf.read(1), b'\x01')
        self.ae(buf.read(10), b'\x02')
        self.ae(buf.full_state, WRITE)
        set(numbers, 3, 1, READ)
        self.ae(buf.read(1), b'\x03')
        self.ae(buf.read(10), b'\x04\x05\x06\x07\x08\x09\x00')
        set(numbers, 1, 3, READ)
        self.ae(buf.readline(), b'\x01\x02')
        set(b'123\n', 0, 3, READ)
        self.ae(buf.readline(), b'123')
        set(b'123\n', 0, 0, READ)
        self.ae(buf.readline(), b'123\n')
        self.ae(buf.full_state, WRITE)
        set(b'1\n2345', 2, 2, READ)
        self.ae(buf.readline(), b'23451\n')
        self.ae(buf.full_state, WRITE)
        set(b'1\n2345', 1, 1, READ)
        self.ae(buf.readline(), b'\n')
        set(b'1\n2345', 4, 1, READ)
        self.ae(buf.readline(), b'451')
        set(b'1\n2345', 4, 2, READ)
        self.ae(buf.readline(), b'451\n')
        set(b'123456\n7', 4, 2, READ)
        self.ae(buf.readline(), b'56\n')

    @skipIf(create_server_cert is None, 'certgen module not available')
    def test_ssl(self):
        'Test serving over SSL'
        with TestServer(lambda data:(data.path[0] + data.read())) as server:
            address = server.address[0]
        with TemporaryDirectory('srv-test-ssl') as tdir:
            cert_file, key_file, ca_file = map(lambda x:os.path.join(tdir, x), 'cka')
            create_server_cert(address, ca_file, cert_file, key_file, key_size=1024)
            ctx = ssl.create_default_context(cafile=ca_file)
            with TestServer(lambda data:(data.path[0] + data.read()), ssl_certfile=cert_file, ssl_keyfile=key_file) as server:
                conn = httplib.HTTPSConnection(server.address[0], server.address[1], strict=True, context=ctx)
                conn.request('GET', '/test', 'body')
                r = conn.getresponse()
                self.ae(r.status, httplib.OK)
                self.ae(r.read(), b'testbody')
                cert = conn.sock.getpeercert()
                subject = dict(x[0] for x in cert['subject'])
                self.ae(subject['commonName'], address)

    @skipIf(not has_preactivated_support, 'pre_activated_socket not available')
    def test_socket_activation(self):
        'Test socket activation'
        os.closerange(3, 4)  # Ensure the socket gets fileno == 3
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM, 0)
        s.bind(('localhost', 0))
        port = s.getsockname()[1]
        self.ae(s.fileno(), 3)
        os.environ['LISTEN_PID'] = str(os.getpid())
        os.environ['LISTEN_FDS'] = '1'
        with TestServer(lambda data:(data.path[0] + data.read()), allow_socket_preallocation=True) as server:
            conn = server.connect()
            conn.request('GET', '/test', 'body')
            r = conn.getresponse()
            self.ae(r.status, httplib.OK)
            self.ae(r.read(), b'testbody')
            self.ae(server.loop.bound_address[1], port)
